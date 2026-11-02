"""Anexo 8 de la RMF (tarifas de ISR): extraccion determinista del PDF del DOF, verificacion aritmetica,
escritura a rmf/<anio>/anexo-8/ y consulta.

El texto sale del PDF oficial (pdftotext -layout); nada se escribe a mano. Cada tarifa es un archivo
Markdown con front matter; la verificacion aritmetica y el conteo de filas contra el texto crudo rompen la
validacion si algo no cuadra (ver scripts/validar.py y scripts/extraer_anexo8.py).
"""
import hashlib
import json
import os
import re
from decimal import Decimal
from pathlib import Path

from .extraer import pdf_a_texto

RAIZ = Path(os.environ.get("LEYES_MX_RAIZ") or Path(__file__).resolve().parent.parent)

DOCUMENTO = "Anexo 8 de la RMF 2026"
NOMBRE_COMPLETO = "Anexo 8 de la Resolución Miscelánea Fiscal para 2026: Tarifas aplicables a pagos provisionales, retenciones y cálculo del ISR"
ANIO = 2026
PUBLICADO_DOF = "2025-12-28"
FECHA_FIRMA = "2025-12-17"
FUENTE_URL = ("https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rmf/anexos/"
              "Anexo-8-RMF-2026_DOF-28122025.pdf")
NOMBRE_PDF = "RMF-2026-Anexo-8.pdf"  # en fuentes/2026/ (ignorado por git)
COLUMNAS = ["Límite inferior ($)", "Límite superior ($)", "Cuota fija ($)", "% sobre el excedente del límite inferior"]
TASAS = ["1.92", "6.40", "10.88", "16.00", "17.92", "21.36", "23.52", "30.00", "32.00", "34.00", "35.00"]
AVISO = ("Texto informativo copiado del PDF del Anexo 8 publicado en el DOF; no sustituye al DOF ni al sitio del SAT. "
         "La fuente oficial prevalece.")

# Rutas que los artículos 96 y 152 de la LISR deben citar (las comprueba scripts/validar.py).
RUTA_MENSUAL = "rmf/2026/anexo-8/B-V-tarifa-mensual-2026.md"
RUTA_ANUAL = "rmf/2026/anexo-8/C-II-tarifa-anual-2026.md"
AVISO_LISR = ("La tabla de este artículo es la de la ley. Para 2026 se aplica la tarifa actualizada del Anexo 8 de la RMF 2026: "
              "rmf/2026/anexo-8/B-V-tarifa-mensual-2026.md (mensual) y C-II-tarifa-anual-2026.md (anual)")

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
_LISR, _RLISR, _RMF = "LISR", "RLISR", "RMF 2026"
_R3122 = [f"{_LISR} art. 96", f"{_RLISR} art. 175", f"{_RMF} regla 3.12.2"]
_DEC = "Decreto DOF 2021-11-12, art. Segundo, fracción IX"
_RIF = [f"{_LISR} art. 111 (vigente hasta 2021)", _DEC]

# (id, apartado, titulo corto, aplicable_a, fragmentos que deben aparecer en el título del PDF)
# El orden es el del PDF; el extractor falla si el título extraído no contiene los fragmentos.
CATALOGO = [
    ("A-I-enajenacion-inmuebles", "A.I", "Pagos provisionales por enajenación de inmuebles 2026",
     [f"{_LISR} art. 126, segundo párrafo", f"{_RMF} regla 3.15.4"], ["126", "3.15.4"]),
    ("B-I-trabajo-realizado", "B.I", "Retenciones: tarifa por cantidad de trabajo realizado, calculada en días (2026)", _R3122, ["trabajo realizado", "96", "175", "3.12.2"]),
    ("B-II-7-dias", "B.II", "Retenciones: tarifa para pagos por periodo de 7 días (2026)", _R3122, ["7 días", "96", "175", "3.12.2"]),
    ("B-III-10-dias", "B.III", "Retenciones: tarifa para pagos por periodo de 10 días (2026)", _R3122, ["10 días", "96", "175", "3.12.2"]),
    ("B-IV-15-dias", "B.IV", "Retenciones: tarifa para pagos por periodo de 15 días (2026)", _R3122, ["15 días", "96", "175", "3.12.2"]),
    ("B-V-tarifa-mensual-2026", "B.V", "Tarifa mensual 2026 (pagos provisionales mensuales y retenciones)", _R3122, ["mensuales", "96", "175", "3.12.2"]),
] + [
    (f"B-VI-{m}", "B.VI", f"Tarifa de {m} de 2026 para pagos provisionales mensuales (art. 106 LISR)",
     [f"{_LISR} art. 106", f"{_LISR} Título IV, Capítulo II, Sección I"], [f"mes de {m} de 2026", "106"])
    for m in _MESES
] + [
    ("B-VI-arrendamiento-mensual", "B.VI", "Pagos provisionales mensuales 2026 por arrendamiento (art. 116 LISR)",
     [f"{_LISR} art. 116", f"{_LISR} Título IV, Capítulo III"], ["mensuales", "116", "arrendamiento"]),
    ("B-VI-arrendamiento-trimestral", "B.VI", "Pagos provisionales trimestrales 2026 por arrendamiento (art. 116 LISR)",
     [f"{_LISR} art. 116", f"{_LISR} Título IV, Capítulo III"], ["trimestrales", "116", "arrendamiento"]),
    ("B-VI-art-74-primer-semestre", "B.VI", "Tarifa opcional del art. 74 LISR, primer semestre de 2026",
     [f"{_LISR} art. 74", f"{_LISR} Título II, Capítulo VIII"], ["primer semestre de 2026", "74"]),
    ("B-VI-art-74-segundo-semestre", "B.VI", "Tarifa opcional del art. 74 LISR, segundo semestre de 2026",
     [f"{_LISR} art. 74", f"{_LISR} Título II, Capítulo VIII"], ["segundo semestre de 2026", "74"]),
    ("B-VII-rif-bimestral-definitivo", "B.VII", "Pagos bimestrales definitivos 2026 de contribuyentes del RIF", _RIF,
     ["bimestrales definitivos de 2026", "111"]),
] + [
    (f"B-VIII-bimestre-{b}", "B.VIII", f"Pagos provisionales del bimestre {b} de 2026 (RIF, coeficiente de utilidad)", _RIF,
     [f"bimestre {b} de 2026", "111"])
    for b in ("enero-febrero", "marzo-abril", "mayo-junio", "julio-agosto", "septiembre-octubre", "noviembre-diciembre")
] + [
    ("C-I-tarifa-anual-2025", "C.I", "Tarifa anual del ejercicio 2025 (cálculo del impuesto anual)",
     [f"{_LISR} art. 97", f"{_LISR} art. 152", f"{_RMF} regla 3.17.1"], ["ejercicio de 2025", "97", "152", "3.17.1"]),
    ("C-II-tarifa-anual-2026", "C.II", "Tarifa anual del ejercicio 2026 (cálculo del impuesto anual)",
     [f"{_LISR} art. 97", f"{_LISR} art. 152", f"{_RMF} regla 3.17.1"], ["ejercicio de 2026", "97", "152", "3.17.1"]),
]

SECCIONES = {"A": "Tarifa aplicable a pagos provisionales", "B": "Tarifas aplicables a retenciones",
             "C": "Tarifa para el cálculo del impuesto correspondiente a los ejercicios 2025 y 2026"}

RE_ENCABEZADO = re.compile(r"^\s*(DIARIO OFICIAL\s+\w+ \d+ de \w+ de \d{4}|\w+ \d+ de \w+ de \d{4}\s+DIARIO OFICIAL)\s*$")
RE_FILA = re.compile(r"^\s*([\d,]+\.\d{2})\s+([\d,]+\.\d{2}|En adelante)\s+([\d,]+(?:\.\d{2})?)\s+(\d{1,2}\.\d{2})\s*$")
RE_ENCAB_TABLA = re.compile(r"^\s*(Por ciento para|aplicarse sobre el|Límite inferior|excedente del|inferior\s*$|\$\s+\$\s+\$\s+%)")
RE_TITULO = re.compile(r"^(?:[IVX]+\.\s+)?Tarifa", re.I)
RE_SECCION = re.compile(r"^([ABC])\.\s+(Tarifas? .*)$")


class ErrorAnexo(Exception):
    pass


# ------------------------------------------------------------------ extraccion

def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def limpiar(texto):
    """Quita saltos de página y encabezados del DOF repetidos. No hay números de página en este PDF."""
    out = []
    for l in texto.replace("\f", "\n").splitlines():
        if RE_ENCABEZADO.match(l):
            continue
        out.append(l.rstrip())
    return out


def _cuerpo(lineas):
    """Desde el segundo 'A. Tarifa aplicable a pagos provisionales' (el primero es el Contenido)."""
    idx = [i for i, l in enumerate(lineas) if re.match(r"^\s*A\.\s+Tarifa aplicable a pagos provisionales\s*$", l)]
    if len(idx) != 2:
        raise ErrorAnexo(f"se esperaban 2 encabezados 'A. Tarifa aplicable a pagos provisionales' y hay {len(idx)}")
    fin = [i for i, l in enumerate(lineas) if l.strip() == "Atentamente."]
    if len(fin) != 1:
        raise ErrorAnexo("no se encontró 'Atentamente.' una sola vez")
    return lineas[idx[1]:fin[0]], lineas[:idx[0]], lineas[fin[0]:]


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def _introduccion(previo):
    """Texto introductorio del anexo (entre el título y el Contenido)."""
    i = next(k for k, l in enumerate(previo) if "ANEXO 8 DE LA RESOLUCIÓN" in l)
    j = next(k for k, l in enumerate(previo) if l.strip() == "Contenido")
    par, pars = [], []
    for l in previo[i + 1:j] + [""]:
        if l.strip():
            par.append(l.strip())
        elif par:
            pars.append(_norm(" ".join(par)))
            par = []
    # el subtítulo centrado y el párrafo "Para los efectos..." salen pegados cuando no hay renglón en blanco entre ellos
    res = []
    for p in pars:
        k = p.find(" Para los efectos")
        res.extend([p[:k], p[k + 1:]] if k > 0 else [p])
    return res


def partir(lineas_cuerpo):
    """Devuelve lista de tablas en orden del PDF: {titulo, seccion, filas, lineas_crudas}.
    Una tabla termina en la fila 'En adelante'. Su título es el último párrafo previo que empieza con
    'Tarifa' (con o sin numeral romano)."""
    tablas, pendientes, par, seccion, cur = [], [], [], None, None

    def cerrar_par():
        nonlocal par
        if par:
            pendientes.append(_norm(" ".join(par)))
            par = []

    for l in lineas_cuerpo:
        if cur is not None:
            if not l.strip():
                continue
            m = RE_FILA.match(l)
            if not m:
                raise ErrorAnexo(f"línea que no es fila dentro de la tabla {len(tablas) + 1}: {l.strip()!r}")
            cur["filas"].append(list(m.groups()))
            cur["crudas"].append(l.strip())
            if m.group(2) == "En adelante":
                tablas.append(cur)
                cur, pendientes = None, []
            continue
        if not l.strip():
            cerrar_par()
            continue
        if RE_FILA.match(l):
            cerrar_par()
            tits = [p for p in pendientes if RE_TITULO.match(p)]
            if not tits:
                raise ErrorAnexo(f"fila sin título previo: {l.strip()!r}")
            m = RE_FILA.match(l)
            cur = {"titulo": tits[-1], "seccion": seccion, "filas": [list(m.groups())], "crudas": [l.strip()]}
            if m.group(2) == "En adelante":
                raise ErrorAnexo("tabla de una sola fila")
            continue
        if RE_ENCAB_TABLA.match(l):
            continue
        if re.match(r"^\s*(?:[ABC]|[IVX]+)\.\s+\S", l):
            cerrar_par()  # una sección o un numeral romano siempre abre párrafo nuevo
        s = RE_SECCION.match(_norm(l))
        if s:
            seccion = s.group(1)
        par.append(l.strip())
    if cur is not None:
        raise ErrorAnexo("la última tabla no termina en 'En adelante'")
    return tablas


def asignar_catalogo(tablas):
    """Une cada tabla con su entrada del catálogo por orden y comprueba que el título la reconoce."""
    if len(tablas) != len(CATALOGO):
        raise ErrorAnexo(f"el PDF trae {len(tablas)} tablas y el catálogo {len(CATALOGO)}")
    res = []
    for t, (id_, apartado, corto, aplic, claves) in zip(tablas, CATALOGO):
        for c in claves:
            if c not in t["titulo"]:
                raise ErrorAnexo(f"{id_}: el título extraído no contiene {c!r}: {t['titulo']!r}")
        letra, romano = apartado.split(".")
        if not t["titulo"].startswith(romano + ".") and apartado not in ("B.VI", "B.VIII"):
            raise ErrorAnexo(f"{id_}: el título no empieza con el numeral {romano}.: {t['titulo'][:40]!r}")
        res.append({**t, "id": id_, "apartado": apartado, "titulo_corto": corto, "aplicable_a": aplic})
    return res


def extraer_pdf(pdf):
    """PDF -> {'tablas': [...], 'introduccion': [...], 'conteo_crudo': {...}}. Falla ante cualquier irregularidad."""
    texto = pdf_a_texto(pdf, layout=True)
    lineas = limpiar(texto)
    cuerpo, previo, cola = _cuerpo(lineas)
    tablas = asignar_catalogo(partir(cuerpo))
    return {"tablas": tablas, "introduccion": _introduccion(previo), "firma": _norm(" ".join(l.strip() for l in cola if l.strip())),
            "lineas_cuerpo": cuerpo, "texto_sin_layout": pdf_a_texto(pdf, layout=False)}


# ------------------------------------------------------------------ verificacion

def _d(s):
    return Decimal(s.replace(",", ""))


def desviaciones(filas):
    """Por fila 2..n: (|inferior - (superior previo + 0.01)|, |cuota - cuota recalculada|) en pesos, y la cuota recalculada sin redondear."""
    out = []
    for i in range(1, len(filas)):
        pi, ps, pc, pr = filas[i - 1]
        ni, _ns, nc, _nr = filas[i]
        d_lim = abs(_d(ni) - (_d(ps) + Decimal("0.01")))
        esp = _d(pc) + (_d(ps) - _d(pi)) * _d(pr) / 100
        out.append((d_lim, abs(esp - _d(nc)), esp))
    return out


# Tolerancia de la cuota fija recalculada, fijada por evidencia (medida sobre las 31 tarifas del PDF):
# - Tarifas "directas" (K=1): enero, diaria, arrendamiento mensual, y las de 12 meses (diciembre, A.I, semestre 2,
#   bimestre nov-dic, anual 2025 y 2026), que se calcularon aparte (12 x cuota de enero = 194.64, el PDF trae 194.59).
#   Error observado: 0.0084 a 0.0152 pesos. Teoría: redondeo de la cuota previa (0.005) + del resultado (0.005) + de
#   los dos límites por la tasa previa máxima 0.34 (0.0034) = 0.0134; el PDF 2025 llega a 0.0152.
# - Tarifas "escaladas" (K>1): 7, 10 y 15 días = K x tarifa diaria; febrero a noviembre y los bimestres 1 a 5, trimestre y
#   semestre 1 = K x enero (o K x mensual), con las cuotas multiplicadas desde valores ya redondeados, así que el error crece
#   con K. Observado: 7 días 0.0432, 10 días 0.0614, 15 días 0.0918, febrero 0.0208 ... noviembre (K=11) 0.1000.
# Regla: tolerancia = 0.02 x K. Ninguna tarifa la excede (cociente máximo observado/tolerancia = 0.76, la tarifa anual 2025).
TOL_BASE = Decimal("0.02")


def multiplo(id_):
    """K de la tarifa: 1 si se calculó directa, K>1 si es múltiplo escalado de otra (ver comentario de arriba)."""
    fijos = {"A-I-enajenacion-inmuebles": 1, "B-I-trabajo-realizado": 1, "B-II-7-dias": 7, "B-III-10-dias": 10, "B-IV-15-dias": 15,
             "B-V-tarifa-mensual-2026": 1, "B-VI-arrendamiento-mensual": 1, "B-VI-arrendamiento-trimestral": 3,
             "B-VI-art-74-primer-semestre": 6, "B-VI-art-74-segundo-semestre": 1, "B-VII-rif-bimestral-definitivo": 2,
             "C-I-tarifa-anual-2025": 1, "C-II-tarifa-anual-2026": 1, "B-VI-diciembre": 1}
    if id_ in fijos:
        return fijos[id_]
    if id_.startswith("B-VI-") and id_[5:] in _MESES:
        return _MESES.index(id_[5:]) + 1
    bim = ["enero-febrero", "marzo-abril", "mayo-junio", "julio-agosto", "septiembre-octubre", "noviembre-diciembre"]
    if id_.startswith("B-VIII-bimestre-") and id_[16:] in bim:
        k = 2 * (bim.index(id_[16:]) + 1)
        return 1 if k == 12 else k
    raise KeyError(id_)


def tolerancia(id_):
    return TOL_BASE * multiplo(id_)


def verificar_tarifa(id_, filas, tol_cuota=None):
    """Errores de una tarifa. Exacto: primer inferior 0.01, inferior = superior previo + 0.01, última fila 'En adelante',
    superior > inferior, tasas = las 11 de la ley, cuota primera = 0 y cuota recalculada = cuota previa +
    (superior previo - inferior previo) x tasa previa con tolerancia tol_cuota (pesos; por omisión tolerancia(id_))."""
    errs = []
    tol_cuota = tolerancia(id_) if tol_cuota is None else tol_cuota
    if len(filas) != len(TASAS):
        errs.append(f"{id_}: {len(filas)} filas, se esperaban {len(TASAS)}")
    if not filas:
        return errs
    if filas[0][0] != "0.01":
        errs.append(f"{id_} fila 1: el límite inferior es {filas[0][0]}, debe ser 0.01")
    if _d(filas[0][2]) != 0:
        errs.append(f"{id_} fila 1: la cuota fija es {filas[0][2]}, debe ser 0")
    if filas[-1][1] != "En adelante":
        errs.append(f"{id_}: la última fila no es 'En adelante'")
    for i, f in enumerate(filas):
        if i < len(TASAS) and f[3] != TASAS[i]:
            errs.append(f"{id_} fila {i + 1}: tasa {f[3]} distinta de la de la ley {TASAS[i]}")
        if f[1] != "En adelante" and _d(f[1]) <= _d(f[0]):
            errs.append(f"{id_} fila {i + 1}: superior {f[1]} no mayor que inferior {f[0]}")
        if i < len(filas) - 1 and f[1] == "En adelante":
            errs.append(f"{id_} fila {i + 1}: 'En adelante' antes de la última fila")
    for i in range(1, len(filas)):
        if filas[i - 1][1] == "En adelante":
            break
        dl, dc, esp = desviaciones(filas[i - 1:i + 1])[0]
        if dl != 0:
            errs.append(f"{id_} fila {i + 1}: límite inferior {filas[i][0]} no sigue a {filas[i - 1][1]} + 0.01")
        if dc > tol_cuota:
            errs.append(f"{id_} fila {i + 1}: cuota fija {filas[i][2]}, recalculada {esp:.4f} (desviación {dc})")
    return errs


# Tarifas que el anexo publica varias veces para fines distintos y que deben coincidir fila por fila
# (corroboración cruzada: un error de parseo en una sola de ellas rompe la igualdad).
EQUIVALENCIAS = [
    ["B-V-tarifa-mensual-2026", "B-VI-enero", "B-VI-arrendamiento-mensual"],
    ["B-VI-febrero", "B-VII-rif-bimestral-definitivo", "B-VIII-bimestre-enero-febrero"],
    ["B-VI-marzo", "B-VI-arrendamiento-trimestral"],
    ["B-VI-abril", "B-VIII-bimestre-marzo-abril"],
    ["B-VI-junio", "B-VI-art-74-primer-semestre", "B-VIII-bimestre-mayo-junio"],
    ["B-VI-agosto", "B-VIII-bimestre-julio-agosto"],
    ["B-VI-octubre", "B-VIII-bimestre-septiembre-octubre"],
    ["A-I-enajenacion-inmuebles", "B-VI-diciembre", "B-VI-art-74-segundo-semestre", "B-VIII-bimestre-noviembre-diciembre",
     "C-II-tarifa-anual-2026"],
]


def verificar_equivalencias(filas_por_id):
    errs = []
    for grupo in EQUIVALENCIAS:
        presentes = [g for g in grupo if g in filas_por_id]
        for g in presentes[1:]:
            if filas_por_id[g] != filas_por_id[presentes[0]]:
                errs.append(f"{g} debería ser igual a {presentes[0]} (el anexo las publica idénticas)")
    return errs


def contar_crudo(lineas_cuerpo, tablas):
    """Control independiente: por cada tabla cuenta, en el texto crudo entre su título y la fila 'En adelante',
    las líneas con >= 3 cifras (regex distinta de RE_FILA). Devuelve lista de conteos."""
    cifra = re.compile(r"\d[\d,]*(?:\.\d+)?")
    conteos, pos = [], 0
    for t in tablas:
        ini = next(i for i in range(pos, len(lineas_cuerpo)) if lineas_cuerpo[i].strip() == t["crudas"][0])
        fin = next(i for i in range(ini, len(lineas_cuerpo)) if "En adelante" in lineas_cuerpo[i])
        n = sum(1 for l in lineas_cuerpo[ini:fin + 1] if len(cifra.findall(l)) >= 3)
        conteos.append(n)
        pos = fin + 1
    return conteos


# ------------------------------------------------------------------ escritura

def _yaml(v):
    return json.dumps(v, ensure_ascii=False)


def tabla_md(filas):
    cab = "| " + " | ".join(COLUMNAS) + " |\n|" + "---|" * len(COLUMNAS) + "\n"
    return cab + "".join("| " + " | ".join(r) + " |\n" for r in filas)


def archivo_md(t, comunes):
    fm = {"documento": DOCUMENTO, "apartado": t["apartado"], "id": t["id"], "titulo": t["titulo_corto"],
          "aplicable_a": t["aplicable_a"], **comunes, "estatus": "vigente", "filas": len(t["filas"])}
    cab = "---\n" + "".join(f"{k}: {_yaml(v)}\n" for k, v in fm.items()) + "---\n"
    letra = t["apartado"].split(".")[0]
    return (f"{cab}\n# {DOCUMENTO}, apartado {t['apartado']}: {t['titulo_corto']}\n\n"
            f"Sección {letra}. {SECCIONES[letra]}.\n\n"
            f"Texto del anexo:\n\n> {t['titulo']}\n\n{tabla_md(t['filas'])}\n"
            f"> {AVISO}\n")


def escribir(datos, pdf, destino, fecha_descarga):
    """Escribe destino/<id>.md para cada tarifa, _indice.md y _meta.json. Reemplaza la carpeta completa."""
    import shutil
    destino = Path(destino)
    sha = sha256_archivo(pdf)
    comunes = {"vigencia_anio": ANIO, "publicado_dof": PUBLICADO_DOF, "fecha_firma": FECHA_FIRMA,
               "fuente_url": FUENTE_URL, "fecha_descarga": fecha_descarga, "sha256_fuente": sha}
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    for t in datos["tablas"]:
        (destino / f"{t['id']}.md").write_text(archivo_md(t, comunes), encoding="utf-8")
    filas = [f"# Índice del {DOCUMENTO}, vigencia {ANIO}\n",
             f"{NOMBRE_COMPLETO}. Publicado en el DOF el {PUBLICADO_DOF} (\"ANEXOS 4, 5, 6, 8, 15 y 25 de la Resolución Miscelánea Fiscal para 2026\"), "
             f"firmado en la Ciudad de México el {FECHA_FIRMA}. Fuente: {FUENTE_URL}\n"]
    filas += [f"> {p}" for p in datos["introduccion"]]
    filas += ["", "Las tarifas de los artículos 96 y 152 de la LISR que están en `leyes/` son las de la ley; para 2026 se aplican las de este anexo.", "",
              "| Apartado | Archivo | Tarifa | Aplicable a |", "|---|---|---|---|"]
    for t in datos["tablas"]:
        filas.append(f"| {t['apartado']} | [{t['id']}.md]({t['id']}.md) | {t['titulo_corto']} | {'; '.join(t['aplicable_a'])} |")
    filas.append("")
    (destino / "_indice.md").write_text("\n".join(filas), encoding="utf-8")
    por_apartado = {}
    for t in datos["tablas"]:
        por_apartado[t["apartado"]] = por_apartado.get(t["apartado"], 0) + 1
    meta = {
        "documento": DOCUMENTO, "nombre_oficial": NOMBRE_COMPLETO, "tipo": "anexo_rmf",
        "fuente_url": FUENTE_URL, "publicado_dof": PUBLICADO_DOF, "fecha_firma": FECHA_FIRMA,
        "fecha_descarga": fecha_descarga, "sha256_pdf": sha, "tamano_bytes": Path(pdf).stat().st_size,
        "paginas_pdf": 19, "vigencia_anio": ANIO, "estatus": "vigente",
        "tarifas": len(datos["tablas"]), "tarifas_por_apartado": por_apartado,
        "tarifas_detalle": [{"id": t["id"], "apartado": t["apartado"], "archivo": f"{t['id']}.md", "filas": len(t["filas"])} for t in datos["tablas"]],
        "introduccion": datos["introduccion"],
        "subsidio_para_el_empleo": "No está en este anexo (verificado: el PDF no contiene las palabras subsidio ni empleo).",
        "advertencias": [AVISO],
    }
    (destino / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


# ------------------------------------------------------------------ lectura (para validar y buscar)

def _parse_tabla_md(cuerpo):
    filas = []
    for l in cuerpo.splitlines():
        if l.startswith("| ") and not l.startswith("| Límite") :
            celdas = [c.strip() for c in l.strip().strip("|").split("|")]
            if len(celdas) == 4:
                filas.append(celdas)
    return filas


def carpeta(anio=None, raiz=None):
    return Path(raiz or RAIZ) / "rmf" / str(anio or ANIO) / "anexo-8"


def anios_disponibles(raiz=None):
    base = Path(raiz or RAIZ) / "rmf"
    if not base.is_dir():
        return []
    return sorted(int(p.name) for p in base.iterdir() if p.is_dir() and p.name.isdigit() and (p / "anexo-8").is_dir())


def listar_tarifas(anio=None, raiz=None):
    """Una fila por tarifa del anexo: id, apartado, titulo, filas, archivo, fuente, DOF, año. Lista vacía si no hay anexo."""
    from .store import parse_front_matter
    anio = anio or (anios_disponibles(raiz) or [None])[-1]
    if anio is None or not carpeta(anio, raiz).is_dir():
        return []
    res = []
    for p in sorted(carpeta(anio, raiz).glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm, _ = parse_front_matter(p.read_text(encoding="utf-8"))
        res.append({"id": fm.get("id"), "apartado": fm.get("apartado"), "titulo": fm.get("titulo"),
                    "documento": fm.get("documento"), "anio_vigencia": fm.get("vigencia_anio"),
                    "publicado_dof": fm.get("publicado_dof"), "fuente_url": fm.get("fuente_url"),
                    "filas": fm.get("filas"), "ruta": str(p.relative_to(Path(raiz or RAIZ)))})
    orden = {c[0]: i for i, c in enumerate(CATALOGO)}  # orden del PDF
    return sorted(res, key=lambda r: (orden.get(r["id"], len(orden)), r["ruta"]))


def obtener_tarifa(clave, anio=None, raiz=None):
    """Busca una tarifa por id exacto o por apartado ('B-V', 'B.V', 'b-v') o prefijo de id. Devuelve dict con
    texto, filas y metadatos, o None. Si el apartado tiene varias tarifas (B.VI, B.VIII) devuelve la lista en 'otras'
    y la primera como principal solo si la clave es un id exacto; con apartado ambiguo devuelve {'ambiguo': [...]}."""
    from .store import parse_front_matter
    anio = anio or (anios_disponibles(raiz) or [None])[-1]
    if anio is None:
        return None
    todas = listar_tarifas(anio, raiz)
    c = clave.strip().replace(".", "-").replace(" ", "-").lower()
    exactas = [t for t in todas if t["id"].lower() == c]
    if not exactas:
        exactas = [t for t in todas if t["apartado"].replace(".", "-").lower() == c]
    if not exactas:
        exactas = [t for t in todas if t["id"].lower().startswith(c + "-")]
    if not exactas:
        return None
    if len(exactas) > 1:
        return {"ambiguo": [{"id": t["id"], "titulo": t["titulo"]} for t in exactas]}
    t = exactas[0]
    ruta = Path(raiz or RAIZ) / t["ruta"]
    fm, cuerpo = parse_front_matter(ruta.read_text(encoding="utf-8"))
    return {**{k: fm.get(k) for k in ("documento", "apartado", "id", "titulo", "aplicable_a", "vigencia_anio", "publicado_dof",
                                     "fecha_firma", "fuente_url", "fecha_descarga", "sha256_fuente", "estatus")},
            "columnas": COLUMNAS, "filas": _parse_tabla_md(cuerpo), "texto": cuerpo.strip(), "ruta": t["ruta"], "aviso": AVISO}


def listar_anexo(anexo=8, anio=None, raiz=None):
    if int(anexo) != 8:
        raise ValueError("solo está disponible el Anexo 8 de la RMF")
    return listar_tarifas(anio, raiz)


def obtener_anexo(anexo, tarifa, anio=None, raiz=None):
    """Tarifa del Anexo 8 de la RMF: obtener_anexo(8, "B-V"). Ver obtener_tarifa."""
    if int(anexo) != 8:
        raise ValueError("solo está disponible el Anexo 8 de la RMF")
    return obtener_tarifa(tarifa, anio, raiz)
