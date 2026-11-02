"""Validación del Anexo 8 de la RMF (rmf/<año>/anexo-8/) y de las referencias cruzadas desde la LISR.

La usa scripts/validar.py. Devuelve (errores, avisos). Cada tarifa se verifica con aritmética
(anexos.verificar_tarifa), las tarifas que el anexo publica repetidas deben ser idénticas y las rutas citadas
por los artículos 96 y 152 de la LISR deben existir.
"""
import json
from pathlib import Path

from . import anexos, store, tablas as tablas_mod

CAMPOS_FM = ("documento", "apartado", "id", "titulo", "aplicable_a", "vigencia_anio", "publicado_dof", "fecha_firma",
             "fuente_url", "fecha_descarga", "sha256_fuente", "estatus")
CAMPOS_META = ("documento", "fuente_url", "publicado_dof", "fecha_firma", "fecha_descarga", "sha256_pdf", "tarifas", "vigencia_anio")


def _validar_carpeta(raiz, anio, usar_pdf):
    errores, avisos = [], []
    d = anexos.carpeta(anio, raiz)
    pref = f"rmf/{anio}/anexo-8"
    meta_p = d / "_meta.json"
    if not meta_p.exists():
        return [f"{pref}: falta _meta.json"], avisos
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    errores += [f"{pref}/_meta.json sin {k}" for k in CAMPOS_META if not meta.get(k)]
    if meta.get("vigencia_anio") != anio:
        errores.append(f"{pref}: vigencia_anio {meta.get('vigencia_anio')!r} != carpeta")
    if not (d / "_indice.md").exists():
        errores.append(f"{pref}: falta _indice.md")
    archivos = sorted(p for p in d.glob("*.md") if not p.name.startswith("_"))
    if meta.get("tarifas") != len(archivos):
        errores.append(f"{pref}: _meta dice {meta.get('tarifas')} tarifas, hay {len(archivos)} archivos")
    filas_por_id = {}
    for p in archivos:
        fm, cuerpo = store.parse_front_matter(p.read_text(encoding="utf-8"))
        rel = f"{pref}/{p.name}"
        falt = [k for k in CAMPOS_FM if not fm.get(k)]
        if falt:
            errores.append(f"{rel}: front matter sin {falt}")
        if fm.get("id") != p.stem:
            errores.append(f"{rel}: id={fm.get('id')!r} no coincide con el archivo")
        if fm.get("vigencia_anio") != anio:
            errores.append(f"{rel}: vigencia_anio={fm.get('vigencia_anio')!r} != carpeta {anio}")
        if fm.get("estatus") != "vigente":
            errores.append(f"{rel}: estatus {fm.get('estatus')!r} (se espera 'vigente')")
        if fm.get("sha256_fuente") != meta.get("sha256_pdf"):
            errores.append(f"{rel}: sha256_fuente distinto al de _meta.json")
        filas = anexos._parse_tabla_md(cuerpo)
        if fm.get("filas") != len(filas):
            errores.append(f"{rel}: el front matter dice {fm.get('filas')} filas y la tabla trae {len(filas)}")
        filas_por_id[p.stem] = filas
        try:
            errores.extend(f"{rel}: {e}" for e in anexos.verificar_tarifa(p.stem, filas))
        except KeyError:
            errores.append(f"{rel}: tarifa no registrada en leyes_mx.anexos (no se puede verificar)")
    errores.extend(f"{pref}: {e}" for e in anexos.verificar_equivalencias(filas_por_id))
    for t in meta.get("tarifas_detalle", []):
        if t["id"] not in filas_por_id:
            errores.append(f"{pref}: _meta lista {t['id']} y no existe el archivo")
        elif t["filas"] != len(filas_por_id[t["id"]]):
            errores.append(f"{pref}: _meta dice {t['filas']} filas en {t['id']}")
    if usar_pdf:
        pdf = Path(raiz) / "fuentes" / str(anio) / anexos.NOMBRE_PDF
        if not pdf.exists():
            avisos.append(f"{pref}: sin PDF local para el cruce (fuentes/ está ignorado)")
        elif anexos.sha256_archivo(pdf) != meta.get("sha256_pdf"):
            avisos.append(f"{pref}: el PDF local no coincide con el sha256 de _meta.json; se omite el cruce")
        else:
            antes = len(errores)
            try:
                datos = anexos.extraer_pdf(pdf)
            except anexos.ErrorAnexo as ex:
                errores.append(f"{pref}: la re-extracción del PDF falla: {ex}")
            else:
                conteos = anexos.contar_crudo(datos["lineas_cuerpo"], datos["tablas"])
                for t, n in zip(datos["tablas"], conteos):
                    if filas_por_id.get(t["id"]) != t["filas"]:
                        errores.append(f"{pref}/{t['id']}.md: la tabla difiere de la re-extracción del PDF")
                    if n != len(t["filas"]):
                        errores.append(f"{pref}/{t['id']}.md: {n} renglones en el texto crudo y {len(t['filas'])} filas")
                if len(errores) == antes:
                    avisos.append(f"{pref}: {len(datos['tablas'])} tarifas = re-extracción del PDF y conteo de renglones crudos (OK)")
    avisos.append(f"{pref}: {len(archivos)} tarifas verificadas con aritmética")
    return errores, avisos


def _referencias_lisr(raiz):
    """Los arts. 96 y 152 de la LISR deben llevar el aviso y las rutas citadas deben existir."""
    errores = []
    raiz = Path(raiz)
    cfg = json.loads((raiz / "fuentes.json").read_text(encoding="utf-8"))
    cubiertos = set()
    for l in cfg["leyes"]:
        if l["sigla"] != "LISR":
            continue
        for adv in l.get("advertencias", []):
            rutas = adv.get("rutas", [])
            if rutas:
                cubiertos.update(adv.get("articulos", []))
            errores += [f"fuentes.json LISR: la ruta citada en la advertencia no existe: {r}" for r in rutas if not (raiz / r).is_file()]
    if not {"96", "152"} <= cubiertos:
        errores.append("fuentes.json LISR: los arts. 96 y 152 deben llevar la advertencia con rutas al Anexo 8")
    for anio in store._anios(raiz):
        d = raiz / "leyes" / str(anio) / "LISR"
        if not d.is_dir() or not anexos.carpeta(anio, raiz).is_dir():
            continue
        for art in ("0096", "0152"):
            f = d / f"art-{art}.md"
            if not f.exists() or "ADVERTENCIA" not in f.read_text(encoding="utf-8"):
                errores.append(f"leyes/{anio}/LISR/art-{art}.md: falta el aviso visible del Anexo 8")
        meta = json.loads((d / "_meta.json").read_text(encoding="utf-8"))
        rutas_meta = {r for a in meta.get("advertencias", []) for r in a.get("rutas", [])}
        if not (anexos.RUTA_MENSUAL in rutas_meta and anexos.RUTA_ANUAL in rutas_meta):
            errores.append(f"leyes/{anio}/LISR/_meta.json: las advertencias no citan las rutas de la tarifa mensual y anual del Anexo 8")
        for t in (tablas_mod.cargar("LISR", anio, raiz)[0] or {}).get("tablas", []):
            if t.get("anexo_8") and not (raiz / t["anexo_8"]).is_file():
                errores.append(f"tablas/{anio}/LISR/tablas.json: {t['id']} cita {t['anexo_8']} y no existe")
    return errores


def validar(raiz=None, usar_pdf=False):
    raiz = Path(raiz or anexos.RAIZ)
    errores, avisos = [], []
    base = raiz / "rmf"
    if not base.is_dir():
        return errores, avisos
    for anio in anexos.anios_disponibles(raiz):
        e, a = _validar_carpeta(raiz, anio, usar_pdf)
        errores += e
        avisos += a
    if anexos.anios_disponibles(raiz):
        errores += _referencias_lisr(raiz)
    return errores, avisos
