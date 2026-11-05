"""Validación de rmf/<anio>/<carpeta>/ (una regla por archivo). Devuelve (errores, avisos)."""
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from . import store
from .ids import nombre_archivo

REQ = ["ley", "nombre_ley", "vigencia_anio", "publicacion_dof", "fuente_url", "fecha_descarga", "regla", "titulo",
       "ubicacion", "estatus", "pagina_pdf", "sha256_fuente", "fundamento", "referencias_leyes", "referencias_reglas"]
RE_NOMBRE = re.compile(r"^regla-(\d{1,2}(?:\.\d{1,3}){1,4})\.md$")


def _clave(rid):
    return tuple(int(x) for x in rid.split("."))


def _carpetas(raiz):
    base = Path(raiz) / "rmf"
    if not base.is_dir():
        return []
    return sorted(m.parent for m in base.glob("*/*/_meta.json") if (m.parent / "reglas").is_dir())


def _contar_en_pdf(pdf, primera):
    """Cuenta reglas con una ruta DISTINTA a la del extractor: texto plano (pdftotext -layout), sin tipografía,
    número de regla al margen izquierdo con texto a continuación, a partir del Título 1.
    Acepta hasta 7 niveles (el extractor, 5): si el PDF trae un nivel que el extractor no conoce, el conteo difiere."""
    txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout.splitlines()
    ini = next(i for i, l in enumerate(txt) if re.match(r"^\s*T[ií]tulo 1\.\s+Disposiciones generales\s*$", l))
    pat = re.compile(r"^\s{0,4}(\d{1,2}(?:\.\d{1,3}){1,6})\.\s{2,}\S")
    return len({m.group(1) for l in txt[ini:] if (m := pat.match(l))})


def validar(raiz, usar_pdf=False):
    raiz = Path(raiz)
    errores, avisos = [], []
    for d in _carpetas(raiz):
        etiqueta = f"{d.parent.name}/{d.name}"
        meta = json.loads((d / "_meta.json").read_text(encoding="utf-8"))
        archivos = sorted((d / "reglas").glob("regla-*.md"))
        ids = []
        for p in archivos:
            m = RE_NOMBRE.match(p.name)
            if not m:
                errores.append(f"{etiqueta}: nombre de archivo inválido {p.name}")
                continue
            rid = m.group(1)
            ids.append(rid)
            fm, cuerpo = store.parse_front_matter(p.read_text(encoding="utf-8"))
            falta = [k for k in REQ if k not in fm]
            if falta:
                errores.append(f"{etiqueta}/{p.name}: front matter sin {falta}")
                continue
            if fm["regla"] != rid:
                errores.append(f"{etiqueta}/{p.name}: regla={fm['regla']!r} no coincide con el nombre")
            if not fm["titulo"].strip():
                errores.append(f"{etiqueta}/{p.name}: sin título")
            if fm["sha256_fuente"] != meta["sha256_pdf"]:
                errores.append(f"{etiqueta}/{p.name}: sha256_fuente distinto al de _meta.json")
            if fm["estatus"] not in ("vigente", "derogado"):
                errores.append(f"{etiqueta}/{p.name}: estatus {fm['estatus']!r} no permitido")
            texto = re.sub(r"^# Regla[^\n]*\n", "", cuerpo.split("\n## Fundamento", 1)[0]).strip()
            if len(texto) < 20:
                errores.append(f"{etiqueta}/{p.name}: texto vacío o demasiado corto")
            # el fundamento citado debe existir en la base (solo para las leyes que ya están en ella)
            for sigla, arts in fm["referencias_leyes"].items():
                dley = raiz / "leyes" / str(fm["vigencia_anio"]) / sigla
                if not dley.is_dir():
                    continue
                for a in arts:
                    try:
                        if not (dley / nombre_archivo(a)).exists():
                            avisos.append(f"{etiqueta}/{p.name}: cita {sigla} {a}, que no existe en la base")
                    except Exception:
                        avisos.append(f"{etiqueta}/{p.name}: cita {sigla} {a}, con identificador no interpretable")
        # conteo y secuencia
        if len(ids) != meta["reglas_extraidas"]:
            errores.append(f"{etiqueta}: {len(ids)} archivos vs {meta['reglas_extraidas']} en _meta.json")
        if len(set(ids)) != len(ids):
            errores.append(f"{etiqueta}: reglas repetidas")
        grupos = defaultdict(list)
        for rid in ids:
            p = rid.split(".")
            grupos[".".join(p[:-1])].append(int(p[-1]))
        for g, v in grupos.items():
            hueco = sorted(set(range(1, max(v) + 1)) - set(v))
            if hueco:
                errores.append(f"{etiqueta}: faltan reglas {[g + '.' + str(h) for h in hueco[:6]]}")
        for nombre in ("glosario.md", "preambulo.md", "transitorios.md", "_indice.md"):
            if not (d / nombre).exists():
                errores.append(f"{etiqueta}: falta {nombre}")
        avisos.append(f"{etiqueta}: {len(ids)} reglas, de la {meta['primera_regla']} a la {meta['ultima_regla']}")
        if usar_pdf:
            pdf = raiz / "fuentes" / str(d.parent.name) / meta.get("archivo", "RMF.pdf")
            if pdf.exists():
                from .rmf import sha256
                if sha256(pdf) != meta["sha256_pdf"]:
                    avisos.append(f"{etiqueta}: el PDF local no coincide con el sha256 de _meta.json; se omite el cruce")
                else:
                    n = _contar_en_pdf(pdf, meta["primera_regla"])
                    if n != len(ids):
                        errores.append(f"{etiqueta}: cruce con pdftotext -layout: {n} reglas vs {len(ids)} archivos")
                    else:
                        avisos.append(f"{etiqueta}: cruce con pdftotext -layout: {n} reglas = {len(ids)} archivos (OK)")
            else:
                avisos.append(f"{etiqueta}: sin PDF local para el cruce (fuentes/ está ignorado por git)")
    return errores, avisos
