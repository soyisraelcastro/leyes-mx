"""Genera la capa de un año nuevo: compara el texto completo del PDF nuevo contra la vista heredada y escribe en
leyes/<año>/<SIGLA>/ SOLO los artículos que difieren (más _meta.json, _indice.md y, si cambiaron, transitorios.md).

Reemplaza a scripts/copiar_anio.py. Criterio y modelo: docs/criterio-anios.md. Procedimiento: docs/publicar-reforma.md.

Comparación: cuerpo del artículo (sin el front matter) con los espacios normalizados. El front matter lleva fechas, año y
sha256 que cambian en cada descarga y no cuentan como cambio de texto.
"""
import json
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from . import store, versiones
from .ids import clave_orden, id_desde_archivo

RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def cuerpo_normalizado(ruta):
    """Cuerpo del archivo sin front matter y con los espacios colapsados."""
    _, cuerpo = store.parse_front_matter(Path(ruta).read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", cuerpo).strip()


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
        elif cuerpo_normalizado(p) != cuerpo_normalizado(viejos[id_]):
            modificados.append(id_)
        else:
            iguales.append(id_)
    faltantes = [i for i in viejos if i not in nuevos_arch]
    ordenar = lambda xs: sorted(xs, key=clave_orden)  # noqa: E731
    return ordenar(modificados), ordenar(nuevos), ordenar(iguales), ordenar(faltantes)


def _reescribir_indice(texto, vista, dir_capa):
    """El índice de la capa lista TODOS los artículos de la vista; los que viven en una capa anterior se enlazan hacia allá."""
    def destino(nombre):
        origen = vista.archivo(nombre)
        if origen is None or origen.parent == dir_capa:
            return nombre
        return os.path.relpath(origen, dir_capa).replace(os.sep, "/")
    texto = re.sub(r"\[(art-[^\]]+\.md)\]\(\1\)", lambda m: f"[{m.group(1)}]({destino(m.group(1))})", texto)
    return texto.replace("[Transitorios](transitorios.md)", f"[Transitorios]({destino('transitorios.md')})")


def escribir_capa(raiz, sigla, anio, completo, *, vigente_desde, hereda_de=None, fuente=None, dry_run=False):
    """Escribe leyes/<anio>/<SIGLA>/ con solo lo que difiere de la vista heredada.

    `completo` es la carpeta con el texto íntegro de la ley en `anio` (art-*.md, _indice.md, _meta.json y transitorios.md, tal
    como los deja leyes_mx.pipeline.construir). Devuelve un resumen; con dry_run no escribe nada. Lanza ValueError si no se puede.
    """
    raiz, completo, sigla, anio = Path(raiz), Path(completo), sigla.upper(), int(anio)
    if not fecha_valida(vigente_desde):
        raise ValueError(f"vigente_desde no es una fecha ISO válida: {vigente_desde!r}")
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
    meta_nuevo = json.loads((completo / "_meta.json").read_text(encoding="utf-8"))
    modificados, nuevos, iguales, faltantes = comparar(base, completo)
    if faltantes:
        raise ValueError(f"{sigla}: {len(faltantes)} artículo(s) de {hereda_de} no están en el texto nuevo ({', '.join(faltantes[:10])}...). "
                         "Una derogación es un artículo con estatus derogado, no una ausencia: revisar el PDF y el extractor antes de seguir.")
    cambian = sorted(modificados + nuevos, key=clave_orden)
    transit_nuevo = completo / "transitorios.md"
    transit_viejo = base.archivo("transitorios.md")
    cambia_transit = transit_nuevo.is_file() and (transit_viejo is None or cuerpo_normalizado(transit_nuevo) != cuerpo_normalizado(transit_viejo))
    derogados = [i for i in cambian if store.parse_front_matter((completo / _nombre(i)).read_text(encoding="utf-8"))[0].get("estatus") == "derogado"]
    resumen = {"sigla": sigla, "anio": anio, "hereda_de": hereda_de, "vigente_desde": vigente_desde, "modificados": [i for i in cambian if i not in nuevos],
               "nuevos": nuevos, "derogados": derogados, "sin_cambios": len(iguales), "transitorios": cambia_transit, "total": len(iguales) + len(cambian)}
    if dry_run:
        return resumen

    dest = raiz / "leyes" / str(anio) / sigla
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for i in cambian:
        shutil.copy2(completo / _nombre(i), dest / _nombre(i))
    if cambia_transit:
        shutil.copy2(transit_nuevo, dest / "transitorios.md")
    # imágenes de tablas: solo las que citan los archivos de la capa
    citados = "".join(p.read_text(encoding="utf-8") for p in dest.glob("*.md"))
    for img in (completo / "tablas").glob("*") if (completo / "tablas").is_dir() else []:
        if img.is_file() and f"tablas/{img.name}" in citados:
            (dest / "tablas").mkdir(exist_ok=True)
            shutil.copy2(img, dest / "tablas" / img.name)
    meta = dict(meta_nuevo)
    meta["articulos_extraidos"] = resumen["total"]
    meta["hereda_de"] = hereda_de
    meta["vigente_desde"] = vigente_desde
    meta["articulos_modificados"] = cambian
    if nuevos:
        meta["articulos_nuevos"] = nuevos
    if fuente:
        meta["fuente"] = fuente
    (dest / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if cambian or cambia_transit:  # el índice se regenera completo (es chico); una capa sin cambios no lo necesita
        v = versiones.vista(raiz, sigla, anio)
        idx = (completo / "_indice.md").read_text(encoding="utf-8")
        (dest / "_indice.md").write_text(_reescribir_indice(idx, v, dest), encoding="utf-8")
    return resumen


def _nombre(id_):
    from .ids import nombre_archivo
    return nombre_archivo(id_)


def generar(ley, pdf, anio, raiz=None, **kw):
    """Extrae el PDF a un directorio temporal (texto completo) y escribe la capa. La extracción usa tablas/<anio>/ del repo."""
    from . import pipeline
    raiz = Path(raiz or pipeline.RAIZ)
    with tempfile.TemporaryDirectory(prefix="leyes-mx-capa-") as tmp:
        pipeline.construir(ley, pdf, anio, destino_raiz=tmp, fecha_descarga=kw.pop("fecha_descarga", None))
        return escribir_capa(raiz, ley["sigla"], anio, Path(tmp) / str(anio) / ley["sigla"].upper(), **kw)
