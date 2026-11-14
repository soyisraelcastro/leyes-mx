"""Versiones por capas: el único punto que resuelve qué archivo es un artículo (o el índice, o los transitorios) en un año.

Modelo (ver docs/criterio-anios.md):
  leyes/<año>/<SIGLA>/ es una CAPA. La base (leyes/2026/) es completa y no lleva marcas de herencia.
  Una capa posterior guarda solo los artículos que cambian (incluidos nuevos y derogados) y su _meta.json trae
  hereda_de (año de la capa anterior), vigente_desde (fecha ISO) y articulos_modificados.
  La vista de una ley en el año Y es: para cada artículo, el archivo de la capa más reciente de la cadena hereda_de
  que lo contenga. Una ley sin capas (sin hereda_de) se ve exactamente como un directorio completo.

Las capas se ordenan por vigente_desde (no por nombre de carpeta), de modo que más adelante una capa pueda ser una fecha.
vigente_hasta no se guarda: es el vigente_desde de la capa siguiente que contiene ese artículo.
"""
import json
from pathlib import Path

from .ids import clave_orden, id_desde_archivo

BASE_DESDE = ""  # la base no tiene vigente_desde: su inicio es el "inicio de cobertura", y ordena antes que cualquier fecha


def _meta(ruta):
    try:
        return json.loads((Path(ruta) / "_meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Capa:
    def __init__(self, anio, dir, meta):
        self.anio, self.dir, self.meta = anio, Path(dir), meta

    @property
    def hereda_de(self):
        return self.meta.get("hereda_de")

    @property
    def vigente_desde(self):
        return self.meta.get("vigente_desde")

    @property
    def clave(self):
        return (self.vigente_desde or BASE_DESDE, self.anio)

    def __repr__(self):
        return f"Capa({self.anio}, {self.dir.name})"


def anios(raiz):
    """Años (carpetas numéricas) de leyes/."""
    base = Path(raiz) / "leyes"
    if not base.is_dir():
        return []
    return sorted(int(p.name) for p in base.iterdir() if p.is_dir() and p.name.isdigit())


def _dir_sigla(base, sigla):
    if not base.is_dir():
        return None
    for p in base.iterdir():
        if p.is_dir() and p.name.upper() == str(sigla).upper():
            return p
    return None


def siglas(raiz, anio):
    """Nombres de carpeta de las leyes con capa (tienen _meta.json) en ese año, en orden alfabético."""
    base = Path(raiz) / "leyes" / str(anio)
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "_meta.json").exists())


def capa(raiz, sigla, anio):
    """La capa de una ley en un año, o None si ese año no tiene la ley."""
    d = _dir_sigla(Path(raiz) / "leyes" / str(anio), sigla)
    m = _meta(d) if d else None
    return Capa(int(anio), d, m) if m is not None else None


def capas(raiz, sigla):
    """Todas las capas de una ley, ordenadas por vigente_desde (la base primero)."""
    res = [c for c in (capa(raiz, sigla, a) for a in anios(raiz)) if c]
    return sorted(res, key=lambda c: c.clave)


def cadena(raiz, sigla, anio):
    """Capas que forman la vista de la ley en ese año, de la más reciente a la base. Vacía si ese año no tiene la ley."""
    c = capa(raiz, sigla, anio)
    res, vistas = [], set()
    while c and c.anio not in vistas:
        res.append(c)
        vistas.add(c.anio)
        c = capa(raiz, sigla, c.hereda_de) if c.hereda_de is not None else None
    return res


def tiene(raiz, sigla, anio):
    return capa(raiz, sigla, anio) is not None


class Vista:
    """Una ley en un año: sus archivos resueltos a través de la cadena de capas."""

    def __init__(self, sigla, anio, cadena_):
        self.sigla, self.anio, self.cadena = sigla, int(anio), cadena_

    @property
    def meta(self):
        return self.cadena[0].meta

    @property
    def dir(self):
        """Carpeta de la capa del año pedido (la más reciente de la cadena)."""
        return self.cadena[0].dir

    def archivo(self, nombre):
        """Ruta del archivo (art-0028.md, transitorios.md, _indice.md...) en la capa más reciente que lo tenga, o None."""
        for c in self.cadena:
            p = c.dir / nombre
            if p.is_file():
                return p
        return None

    def articulo(self, id_):
        from .ids import nombre_archivo
        return self.archivo(nombre_archivo(id_))

    def archivos(self):
        """{nombre: ruta} de todos los artículos de la vista (la capa más reciente gana), ordenado por nombre."""
        res = {}
        for c in reversed(self.cadena):  # de la base a la capa nueva: la nueva sobrescribe
            for p in c.dir.glob("art-*.md"):
                if id_desde_archivo(p.name):
                    res[p.name] = p
        return dict(sorted(res.items()))

    def ids(self):
        """Ids de los artículos de la vista en el orden de la ley (no el del nombre de archivo, donde art-0004-F.md precede a art-0004.md)."""
        return sorted((id_desde_archivo(n) for n in self.archivos()), key=clave_orden)

    def heredado(self, ruta):
        """True si el archivo viene de una capa anterior a la del año pedido."""
        return Path(ruta).parent != self.dir

    def capa_de(self, ruta):
        for c in self.cadena:
            if Path(ruta).parent == c.dir:
                return c
        return None

    def ajustar(self, fm, ruta):
        """Front matter tal como se debe presentar en esta vista: un artículo heredado se muestra con el año de vigencia
        pedido y la última reforma de la ley en esa vista (el archivo conserva los de su capa de origen)."""
        if not self.heredado(ruta):
            return fm
        fm = dict(fm)
        fm["vigencia_anio"] = self.anio
        if self.meta.get("ultima_reforma_dof"):
            fm["ultima_reforma_dof"] = self.meta["ultima_reforma_dof"]
        return fm


def vista(raiz, sigla, anio):
    """Vista de una ley en un año, o None si ese año no tiene la ley."""
    ch = cadena(raiz, sigla, anio)
    return Vista(ch[0].meta.get("sigla", sigla), anio, ch) if ch else None


def resolver_articulo(raiz, sigla, anio, id_):
    """Ruta del archivo del artículo en la vista del año, o None."""
    v = vista(raiz, sigla, anio)
    return v.articulo(id_) if v else None


def vigente_hasta(raiz, sigla, anio, id_):
    """Fecha en que otra capa reemplaza a la versión del artículo vigente en `anio` (vigente_desde de la capa siguiente que lo
    contiene), o None si sigue vigente en la última capa. Se deriva; no se guarda."""
    from .ids import nombre_archivo
    v = vista(raiz, sigla, anio)
    origen = v.articulo(id_) if v else None
    if origen is None:
        return None
    mias = v.capa_de(origen)
    for c in capas(raiz, sigla):
        if c.clave > mias.clave and (c.dir / nombre_archivo(id_)).is_file() and c.vigente_desde:
            return c.vigente_desde
    return None
