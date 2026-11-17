"""Genera la capa de un año nuevo: compara el texto completo del PDF nuevo contra la vista heredada y escribe en
leyes/<año>/<SIGLA>/ SOLO los artículos que difieren (más _meta.json, _indice.md y, si cambiaron, transitorios.md).

Reemplaza a scripts/copiar_anio.py. Criterio y modelo: docs/criterio-anios.md. Procedimiento: docs/publicar-reforma.md.

Comparación: el cuerpo del artículo con los espacios normalizados Y su front matter (estatus, ubicacion, tablas_transcritas,
formulas_latex...), salvo los campos que cambian en cada descarga o con cada reforma de la ley y no dicen nada del artículo
(CAMPOS_IGNORADOS). Las leyes anuales (campo "anual" de fuentes.json, p. ej. la LIF) y las que se pidan con completa=True no heredan:
se escribe la ley completa, sin hereda_de.

La escritura es atómica: la capa se arma en una carpeta temporal hermana y se renombra al final.
"""
import importlib.util
import json
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from . import store, versiones
from .ids import clave_orden, id_desde_archivo, nombre_archivo

RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Del front matter no cuentan como cambio del artículo: el año y la fecha de descarga, el sha256 y la fuente (cambian en cada
# descarga) ni la última reforma de la LEY (cambia en todos los artículos cuando la ley se reforma, aunque el artículo no).
CAMPOS_IGNORADOS = frozenset({"vigencia_anio", "fecha_descarga", "sha256_fuente", "ultima_reforma_dof", "fuente_url", "ruta"})


def cuerpo_normalizado(ruta):
    """Cuerpo del archivo sin front matter y con los espacios colapsados."""
    _, cuerpo = store.parse_front_matter(Path(ruta).read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", cuerpo).strip()


def firma(ruta):
    """(front matter sin los campos ignorados, cuerpo normalizado): lo que debe coincidir para que un artículo cuente como sin cambios."""
    fm, cuerpo = store.parse_front_matter(Path(ruta).read_text(encoding="utf-8"))
    campos = json.dumps({k: v for k, v in fm.items() if k not in CAMPOS_IGNORADOS}, sort_keys=True, ensure_ascii=False)
    return campos, re.sub(r"\s+", " ", cuerpo).strip()


def iguales_a(a, b):
    return firma(a) == firma(b)


def fecha_valida(s):
    if not isinstance(s, str) or not RE_FECHA.match(s):
        return False
    try:
        date.fromisoformat(s)
    except ValueError:
        return False
    return True


def _hereda_por_omision(raiz, sigla, anio):
    previas = [c for c in versiones.capas(raiz, sigla) if c.anio < int(anio)]
    return previas[-1].anio if previas else None


def comparar(heredada, completo):
    """(modificados, nuevos, sin_cambios, faltantes) por id. `heredada` es una Vista; `completo` una carpeta con art-*.md."""
    nuevos_arch = {id_desde_archivo(p.name): p for p in Path(completo).glob("art-*.md") if id_desde_archivo(p.name)}
    viejos = {id_desde_archivo(n): p for n, p in heredada.archivos().items()}
    modificados, nuevos, iguales = [], [], []
    for id_, p in nuevos_arch.items():
        if id_ not in viejos:
            nuevos.append(id_)
        elif not iguales_a(p, viejos[id_]):
            modificados.append(id_)
        else:
            iguales.append(id_)
    faltantes = [i for i in viejos if i not in nuevos_arch]
    ordenar = lambda xs: sorted(xs, key=clave_orden)  # noqa: E731
    return ordenar(modificados), ordenar(nuevos), ordenar(iguales), ordenar(faltantes)


def _reescribir_indice(texto, base, propios, dest):
    """El índice de la capa lista TODOS los artículos; los que no están en la capa se enlazan a la capa heredada (ruta relativa)."""
    def destino(nombre):
        if nombre in propios:
            return nombre
        origen = base.archivo(nombre)
        return nombre if origen is None else os.path.relpath(origen, dest).replace(os.sep, "/")
    texto = re.sub(r"\[(art-[^\]]+\.md)\]\(\1\)", lambda m: f"[{m.group(1)}]({destino(m.group(1))})", texto)
    return texto.replace("[Transitorios](transitorios.md)", f"[Transitorios]({destino('transitorios.md')})")


def _publicar(tmp, dest):
    """Reemplaza `dest` por `tmp` con renombres (si algo falla, lo que había queda donde estaba)."""
    previo = None
    if dest.exists():
        previo = dest.with_name(f".{dest.name}.previo-{os.getpid()}")
        shutil.rmtree(previo, ignore_errors=True)
        os.rename(dest, previo)
    try:
        os.rename(tmp, dest)
    except OSError:
        if previo is not None:
            os.rename(previo, dest)
        raise
    if previo is not None:
        shutil.rmtree(previo, ignore_errors=True)


def _temporal(raiz, anio, sigla):
    padre = Path(raiz) / "leyes" / str(anio)
    padre.mkdir(parents=True, exist_ok=True)
    tmp = padre / f".{sigla}.nueva-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    return tmp


def escribir_capa(raiz, sigla, anio, completo, *, vigente_desde, hereda_de=None, fuente=None, dry_run=False, completa=False):
    """Escribe leyes/<anio>/<SIGLA>/ con solo lo que difiere de la vista heredada (o la ley completa, sin hereda_de, si completa=True).

    `completo` es la carpeta con el texto íntegro de la ley en `anio` (art-*.md, _indice.md, _meta.json y transitorios.md, tal
    como los deja leyes_mx.pipeline.construir). Devuelve un resumen; con dry_run no escribe nada. Lanza ValueError si no se puede.
    """
    raiz, completo, sigla, anio = Path(raiz), Path(completo), sigla.upper(), int(anio)
    if not fecha_valida(vigente_desde):
        raise ValueError(f"vigente_desde no es una fecha ISO válida: {vigente_desde!r}")
    meta_nuevo = json.loads((completo / "_meta.json").read_text(encoding="utf-8"))
    dest = raiz / "leyes" / str(anio) / sigla
    if completa:
        if hereda_de is not None:
            raise ValueError(f"{sigla}: una capa completa no hereda (hereda_de {hereda_de})")
        ids = [id_desde_archivo(p.name) for p in completo.glob("art-*.md") if id_desde_archivo(p.name)]
        resumen = {"sigla": sigla, "anio": anio, "hereda_de": None, "vigente_desde": vigente_desde, "modificados": [], "nuevos": [], "derogados": [],
                   "sin_cambios": 0, "transitorios": False, "total": len(ids), "completa": True}
        if dry_run:
            return resumen
        tmp = _temporal(raiz, anio, sigla)
        shutil.rmtree(tmp)
        shutil.copytree(completo, tmp)
        meta = dict(meta_nuevo)
        meta["vigente_desde"] = vigente_desde
        if fuente:
            meta["fuente"] = fuente
        (tmp / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _publicar(tmp, dest)
        return resumen

    hereda_de = int(hereda_de) if hereda_de is not None else _hereda_por_omision(raiz, sigla, anio)
    if hereda_de is None or hereda_de >= anio:
        raise ValueError(f"{sigla}: no hay una capa anterior a {anio} de la cual heredar")
    base = versiones.vista(raiz, sigla, hereda_de)
    if base is None:
        raise ValueError(f"{sigla}: no existe leyes/{hereda_de}/{sigla}")
    cap_base = versiones.cadena(raiz, sigla, hereda_de)[0]
    previo = cap_base.vigente_desde or f"{hereda_de}-01-01"
    if vigente_desde <= previo:
        raise ValueError(f"{sigla}: vigente_desde {vigente_desde} debe ser posterior al de la capa heredada ({previo})")
    modificados, nuevos, iguales, faltantes = comparar(base, completo)
    if faltantes:
        raise ValueError(f"{sigla}: {len(faltantes)} artículo(s) de {hereda_de} no están en el texto nuevo ({', '.join(faltantes[:10])}...). "
                         "Una derogación es un artículo con estatus derogado, no una ausencia: revisar el PDF y el extractor antes de seguir.")
    cambian = sorted(modificados + nuevos, key=clave_orden)
    transit_nuevo = completo / "transitorios.md"
    transit_viejo = base.archivo("transitorios.md")
    cambia_transit = transit_nuevo.is_file() and (transit_viejo is None or cuerpo_normalizado(transit_nuevo) != cuerpo_normalizado(transit_viejo))
    derogados = [i for i in cambian if store.parse_front_matter((completo / nombre_archivo(i)).read_text(encoding="utf-8"))[0].get("estatus") == "derogado"]
    resumen = {"sigla": sigla, "anio": anio, "hereda_de": hereda_de, "vigente_desde": vigente_desde, "modificados": [i for i in cambian if i not in nuevos],
               "nuevos": nuevos, "derogados": derogados, "sin_cambios": len(iguales), "transitorios": cambia_transit, "total": len(iguales) + len(cambian)}
    if dry_run:
        return resumen

    tmp = _temporal(raiz, anio, sigla)
    try:
        for i in cambian:
            shutil.copy2(completo / nombre_archivo(i), tmp / nombre_archivo(i))
        if cambia_transit:
            shutil.copy2(transit_nuevo, tmp / "transitorios.md")
        # imágenes de tablas: solo las que citan los archivos de la capa
        citados = "".join(p.read_text(encoding="utf-8") for p in tmp.glob("*.md"))
        for img in (completo / "tablas").glob("*") if (completo / "tablas").is_dir() else []:
            if img.is_file() and f"tablas/{img.name}" in citados:
                (tmp / "tablas").mkdir(exist_ok=True)
                shutil.copy2(img, tmp / "tablas" / img.name)
        meta = dict(meta_nuevo)
        meta["articulos_extraidos"] = resumen["total"]
        meta["hereda_de"] = hereda_de
        meta["vigente_desde"] = vigente_desde
        meta["articulos_modificados"] = cambian
        if nuevos:
            meta["articulos_nuevos"] = nuevos
        if fuente:
            meta["fuente"] = fuente
        (tmp / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if cambian or cambia_transit:  # el índice se regenera completo (es chico); una capa sin cambios no lo necesita
            propios = {nombre_archivo(i) for i in cambian} | ({"transitorios.md"} if cambia_transit else set())
            idx = (completo / "_indice.md").read_text(encoding="utf-8")
            # los enlaces relativos se calculan contra el destino final, que está a la misma profundidad que la carpeta temporal
            (tmp / "_indice.md").write_text(_reescribir_indice(idx, base, propios, dest), encoding="utf-8")
        _publicar(tmp, dest)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return resumen


def _validador(raiz_repo):
    spec = importlib.util.spec_from_file_location("validar_leyes_mx", Path(raiz_repo) / "scripts" / "validar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def generar(ley, pdf, anio, raiz=None, **kw):
    """Extrae el PDF a un directorio temporal (texto completo), VALIDA esa extracción completa y escribe la capa.
    La extracción usa tablas/<anio>/ del repo. Una ley con "anual": true en fuentes.json se escribe completa, sin heredar."""
    from . import pipeline
    raiz = Path(raiz or pipeline.RAIZ)
    kw.setdefault("completa", bool(ley.get("anual")))
    if kw["completa"] and kw.get("hereda_de") is not None:
        raise ValueError(f"{ley['sigla']}: ley anual o completa: no se puede pedir hereda_de")
    with tempfile.TemporaryDirectory(prefix="leyes-mx-capa-") as tmp:
        pipeline.construir(ley, pdf, anio, destino_raiz=tmp, fecha_descarga=kw.pop("fecha_descarga", None))
        completo = Path(tmp) / str(anio) / ley["sigla"].upper()
        rep = _validador(pipeline.RAIZ).validar_ley(completo, int(anio), ley.get("ultimo_articulo_esperado"), False)
        if rep["errores"]:
            raise ValueError(f"{ley['sigla']}: la extracción completa no pasa la validación: " + " | ".join(rep["errores"][:5]))
        return escribir_capa(raiz, ley["sigla"], anio, completo, **kw)
