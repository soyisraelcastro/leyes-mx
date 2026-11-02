"""Extraccion: texto de pdftotext -layout -> articulos, transitorios y notas.

Nada de contenido legal se escribe a mano: todo sale del texto del PDF oficial.
"""
import re
import subprocess
from dataclasses import dataclass, field

from .ids import normalizar_id, PALABRAS

# ---------------------------------------------------------------- texto crudo

def pdf_a_texto(pdf_path, layout=True):
    cmd = ["pdftotext"] + (["-layout"] if layout else []) + [str(pdf_path), "-"]
    return subprocess.run(cmd, check=True, capture_output=True).stdout.decode("utf-8", "replace")


RE_CAMARA = re.compile(r"^\s*C[ÁA]MARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNI[ÓO]N")
RE_SECRETARIA = re.compile(r"^\s*Secretar[íi]a (General|de Servicios Parlamentarios)\s*$")
RE_PAGINA = re.compile(r"^\s*\d+\s+de\s+\d+\s*$")
RE_ULT_REFORMA = re.compile(r"(?:[ÚU]ltima [Rr]eforma(?: publicada)?|Nuevo (?:Reglamento|C[óo]digo|Ley)|Texto vigente)[^\n]*?DOF\s+(\d{2})-(\d{2})-(\d{4})")

# Notas marginales que la Camara imprime al margen derecho
_ANN_INI = (r"(?:P[áa]rrafos?|Fracci[óo]n(?:es)?|Incisos?|Subincisos?|Art[íi]culos?|Numeral(?:es)?|Apartados?|Cap[íi]tulos?|"
            r"Secci[óo]n(?:es)?|T[íi]tulos?|Libros?|Denominaci[óo]n|Ep[íi]grafe|Fe de erratas|Reforma[s]?|Derogad[oa]s?|Adicionad[oa]s?|"
            r"Reformad[oa]s?|Primer|Segundo|Tercer|Cuarto|Quinto|Sexto|[ÚU]ltimo|Pen[úu]ltimo|Multas?|Cantidad(?:es)?|Compilad[oa]s?|"
            r"Actualizad[oa]s?|Tabla|Rubro|Letra|Oraci[óo]n|Texto|Palabra|Frase|Tarifa|Cuota|Monto|Importe|Nota|Ley|Decreto|"
            r"\d{2}-\d{2}-\d{4}|DOF)")
RE_NOTA = re.compile(r"^" + _ANN_INI + r"\b.*\bDOF\b.*\d{2}-\d{2}-\d{4}.*$", re.I)
RE_NOTA_EN_LINEA = re.compile(r"^(.*?\S)\s{5,}(" + _ANN_INI + r"\b.*\bDOF\b.*\d{2}-\d{2}-\d{4}.*)$", re.I)
RE_NOTA_CORTA_EN_LINEA = re.compile(r"^(.*?\S)\s{2,}((?:P[áa]rrafo|Fracci[óo]n|Inciso|Numeral|Subinciso|Apartado)\s+(?:reformad|adicionad|derogad|recorrid)\w*\s+DOF\s+[\d\-,\s.y]*\d{4})\s*$")
RE_NOTA_CONT = re.compile(r"^(?:[\d,.\-;:\s]|DOF|y|Reformad[oa]s?|Adicionad[oa]s?|Derogad[oa]s?|Fe de erratas|Actualizad[oa]s?|Compilad[oa]s?)+$")
RE_FECHA_DOF = re.compile(r"DOF\s+\d{2}-\d{2}-\d{4}")


def fecha_ultima_reforma(texto):
    m = RE_ULT_REFORMA.search(texto[:6000])
    if not m:
        return None
    d, mth, y = m.groups()
    return f"{y}-{mth}-{d}"


def titulo_documento(texto):
    for l in texto.splitlines():
        if l.strip():
            return l.strip()
    return ""


def quitar_encabezados(texto):
    """Devuelve lista de lineas sin encabezado/pie de pagina, con marca '\\f' (linea) en cada salto de pagina."""
    titulo = titulo_documento(texto)
    salida = []
    for pagina in texto.split("\f"):
        lineas = pagina.split("\n")
        # posicion del encabezado "CAMARA DE DIPUTADOS" entre las primeras lineas
        idx = None
        for i, l in enumerate(lineas[:8]):
            if RE_CAMARA.match(l):
                idx = i
                break
        quitar = set()
        if idx is not None:
            for j in range(max(0, idx - 1), idx):
                if lineas[j].strip() == titulo:
                    quitar.add(j)
        for i, l in enumerate(lineas):
            if i < 10 and (RE_CAMARA.match(l) or RE_SECRETARIA.match(l)):
                quitar.add(i)
            elif RE_PAGINA.match(l) and i >= len(lineas) - 8:
                quitar.add(i)
        salida.append("\f")
        salida.extend(l.rstrip() for i, l in enumerate(lineas) if i not in quitar)
    return salida


def separar_notas(lineas):
    """Separa las notas marginales ('Parrafo reformado DOF ...'). Devuelve (lineas_limpias, [(indice_linea_limpia, nota)])."""
    limpias, notas = [], []
    prev_nota = False
    for l in lineas:
        if l == "\f":
            limpias.append(l)
            prev_nota = False
            continue
        s = l.strip()
        if not s:
            limpias.append(l)
            continue
        indent = len(l) - len(l.lstrip())
        if RE_NOTA.match(s) and (indent >= 25 or s[:5] in ("Multa", "Canti", "Compi", "Actua") or True):
            # una linea que EMPIEZA como nota y trae fecha DOF
            if re.match(r"^Art[íi]culo\s+\d", s):  # encabezado de articulo, no nota
                limpias.append(l); prev_nota = False; continue
            notas.append((len(limpias), s)); prev_nota = True
            continue
        m = RE_NOTA_EN_LINEA.match(l) or RE_NOTA_CORTA_EN_LINEA.match(l)
        if m and not re.match(r"^\s*Art[íi]culo\s+\d", l):
            limpias.append(m.group(1)); notas.append((len(limpias), m.group(2).strip())); prev_nota = False
            continue
        if prev_nota and indent >= 40 and RE_NOTA_CONT.match(s):
            # continuacion (renglon) de una nota larga
            notas.append((len(limpias), s)); continue
        prev_nota = False
        limpias.append(l)
    return limpias, notas


# ---------------------------------------------------------------- encabezados de articulo

_WORDS = "|".join(PALABRAS + ["qu[áa]ter"])
RE_ART = re.compile(
    r"^(?P<ind>\s*)Art[íi]culo\s+(?P<num>\d+)\s?(?P<ord>[oº°])?"
    r"(?P<suf>(?:\.?-[A-ZÑ](?![a-záéíóúñ])|\.?\s{0,4}-?\s{0,4}(?i:" + _WORDS + r")\b)*)"
    r"(?:\.(?P<term>-?)|(?P<term2>-))(?=\s|$)"
)


def encabezado_articulo(linea):
    m = RE_ART.match(linea)
    if not m:
        return None
    suf = m.group("suf") or ""
    crudo = m.group("num") + suf
    id_ = normalizar_id(crudo)
    if not id_:
        return None
    return id_, m.end(), crudo


RE_FIN_CUERPO = re.compile(
    r"^\s*(?:TRANSITORIOS?|ART[ÍI]CULOS?\s+TRANSITORIOS?(?:\s+DE\s+.*)?|DISPOSICIONES\s+(?:DE\s+VIGENCIA\s+TEMPORAL|TRANSITORIAS)\b.*|"
    r"ART[ÍI]CULO\s+[A-ZÁÉÍÓÚ]+(?:\s+[A-ZÁÉÍÓÚ]+)?\s*[.\-].*|DECRETO\b.*)\s*$"
)

RE_ESTRUCT = re.compile(
    r"^\s*(?:(?:LIBRO|T[ÍI]TULO|CAP[ÍI]TULO|SECCI[ÓO]N|APARTADO)\b.*|"
    r"(?:Libro|T[íi]tulo|Cap[íi]tulo|Secci[óo]n|Apartado)\s+(?:[IVXLC]+|\d+)(?:\s+(?:[Bb]is|[Tt]er|[Qq]u[áa]ter))?\s*|"
    r"(?:Libro|T[íi]tulo|Cap[íi]tulo|Secci[óo]n|Apartado)\s+(?:Primer[oa]|Segund[oa]|Tercer[oa]|Cuart[oa]|Quint[oa]|Sext[oa]|S[ée]ptim[oa]|Octav[oa]|Noven[oa]|D[ée]cim[oa]|[ÚU]nic[oa])"
    r"(?:\s+(?:[Bb]is|[Tt]er))?(?:\s+[A-ZÁÉÍÓÚÑ][^.;,]*)?\s*)$"
)
RE_ESTRUCT_KW = re.compile(r"^\s*(LIBRO|T[ÍI]TULO|TITULO|CAP[ÍI]TULO|CAPITULO|SECCI[ÓO]N|SECCION|APARTADO|Libro|T[íi]tulo|Cap[íi]tulo|Secci[óo]n|Apartado)\b")


@dataclass
class Articulo:
    id: str
    crudo: str
    lineas: list
    notas: list = field(default_factory=list)
    ubicacion: str = ""
    linea_inicio: int = 0


def _nivel(kw):
    k = kw.upper().replace("Í", "I").replace("Ó", "O")
    return {"LIBRO": 0, "TITULO": 1, "CAPITULO": 2, "SECCION": 3, "APARTADO": 4}[k]


def _cortar_estructura(lineas):
    """Separa del final de un articulo los encabezados estructurales (Titulo/Capitulo/Seccion) que el PDF intercala.
    Devuelve (lineas_articulo, lineas_estructura)."""
    for i, l in enumerate(lineas):
        if i == 0:
            continue
        if RE_ESTRUCT.match(l) and (len(l.strip()) < 90):
            # el resto hasta el final son encabezados / nombres
            return lineas[:i], lineas[i:]
    return lineas, []


def dividir(texto_layout):
    """Devuelve dict con: articulos(list[Articulo]), transitorios(list[str]), cuerpo_inicio, cuerpo_fin."""
    brutas = quitar_encabezados(texto_layout)
    limpias, notas = separar_notas(brutas)

    # 1) localizar inicio (primer 'Articulo 1') y fin del cuerpo
    inicio = None
    for i, l in enumerate(limpias):
        h = encabezado_articulo(l)
        if h and h[0] == "1":
            inicio = i
            break
    if inicio is None:
        raise ValueError("no se encontro el articulo 1")
    fin = len(limpias)
    for i in range(inicio + 1, len(limpias)):
        if RE_FIN_CUERPO.match(limpias[i]) and not encabezado_articulo(limpias[i]):
            fin = i
            break

    # 2) cortes por encabezado de articulo
    marcas = []
    for i in range(inicio, fin):
        h = encabezado_articulo(limpias[i])
        if h:
            marcas.append((i, h))
    articulos = []
    estructura = {}
    notas_por_linea = {}
    for idx, n in notas:
        notas_por_linea.setdefault(idx, []).append(n)
    for k, (i, (id_, fin_enc, crudo)) in enumerate(marcas):
        j = marcas[k + 1][0] if k + 1 < len(marcas) else fin
        bloque = list(limpias[i:j])
        bloque[0] = " " * (len(bloque[0]) - len(bloque[0].lstrip())) + bloque[0][fin_enc:].lstrip(" -")
        # (el .lstrip(" -") quita el separador '.-' ya consumido parcialmente)
        cuerpo, est = _cortar_estructura(bloque)
        # ubicacion vigente para ESTE articulo = estructura vista antes de el
        art = Articulo(id=id_, crudo=crudo, lineas=cuerpo, linea_inicio=i)
        art.ubicacion = " > ".join(estructura[n] for n in sorted(estructura))
        art.notas = [n for jj in range(i, j) for n in notas_por_linea.get(jj, [])]
        articulos.append(art)
        # actualizar estructura con los encabezados que cierran este bloque
        if est:
            nivel_actual = None
            for l in est:
                s = l.strip()
                if not s or s == "\f":
                    nivel_actual = None if not s else nivel_actual
                    continue
                m = RE_ESTRUCT_KW.match(s)
                if m:
                    nv = _nivel(m.group(1))
                    for n in [x for x in estructura if x >= nv]:
                        del estructura[n]
                    estructura[nv] = s
                    nivel_actual = nv
                elif nivel_actual is not None:
                    estructura[nivel_actual] += " " + s
    trans = limpias[fin:]
    return {"articulos": articulos, "transitorios": trans, "notas_transitorios": [n for idx, n in notas if idx >= fin],
            "cuerpo_inicio": inicio, "cuerpo_fin": fin}


# ---------------------------------------------------------------- formateo del cuerpo

RE_ETIQUETA = re.compile(r"^(?:[IVXLCDM]+\.|[a-z]\)|[A-Z]\)|\d{1,2}\.|[A-Z]\.|[a-z]{1,2}\.\))\s")
RE_ETIQ_ESPACIOS = re.compile(r"^([IVXLCDM]+\.|[a-z]\)|[A-Z]\)|\d{1,2}\.|[A-Z]\.)\s{2,}")
RE_CELDA = re.compile(r"\S {3,}\S")


def _es_tabla(bloque):
    n = 0
    for l in bloque:
        s = RE_ETIQ_ESPACIOS.sub(lambda m: m.group(1) + " ", l.strip(), count=1)
        if RE_CELDA.search(s):
            n += 1
    return n >= 2


def formatear(lineas):
    """lineas -> texto markdown. Respeta parrafos, fracciones e incisos; reune renglones partidos por el ancho del PDF.
    Los bloques tabulares (tarifas) se conservan tal cual en un bloque ```text."""
    bloques, actual = [], []
    for l in lineas:
        if l == "\f":
            if actual:
                bloques.append((actual, True)); actual = []
            else:
                if bloques:
                    bloques[-1] = (bloques[-1][0], True)
            continue
        if not l.strip():
            if actual:
                bloques.append((actual, False)); actual = []
            continue
        actual.append(l)
    if actual:
        bloques.append((actual, False))

    parrafos = []  # (texto, es_tabla, cruza_pagina_previa)
    pendiente_pagina = False
    for bloque, termina_pag in bloques:
        if _es_tabla(bloque):
            minind = min(len(l) - len(l.lstrip()) for l in bloque)
            parrafos.append(["```text\n" + "\n".join(l[minind:] for l in bloque) + "\n```", True, pendiente_pagina])
            pendiente_pagina = termina_pag
            continue
        pars, cur = [], []
        for l in bloque:
            s = l.strip()
            if cur and RE_ETIQUETA.match(s):
                pars.append(cur); cur = []
            cur.append(s)
        if cur:
            pars.append(cur)
        for k, p in enumerate(pars):
            txt = " ".join(p)
            txt = RE_ETIQ_ESPACIOS.sub(lambda m: m.group(1) + " ", txt, count=1)
            txt = re.sub(r"[ \t]{2,}", " ", txt)
            parrafos.append([txt, False, pendiente_pagina and k == 0])
        pendiente_pagina = termina_pag
    # unir parrafos partidos por salto de pagina
    res = []
    for txt, tabla, cruza in parrafos:
        if (res and cruza and not tabla and not res[-1][1] and not RE_ETIQUETA.match(txt)
                and not re.search(r"[.:;]\s*$", res[-1][0])):
            res[-1][0] += " " + txt
        else:
            res.append([txt, tabla])
    return "\n\n".join(t for t, _ in res).strip()


RE_DEROGADO = re.compile(r"^\(?\s*(?:se\s+deroga|derogad[oa])\s*\)?\.?$", re.I)


def estatus_de(cuerpo):
    s = re.sub(r"\s+", " ", cuerpo).strip()
    return "derogado" if RE_DEROGADO.match(s) else "vigente"


# ---------------------------------------------------------------- transitorios por decreto

def trocear_transitorios(lineas):
    """Devuelve lista de (titulo, [lineas]). Primer bloque: transitorios del decreto original;
    luego uno por cada 'DECRETO por el que ...' (con su fecha 'Publicado en el DOF ...')."""
    bloques = []
    cur_t, cur = "Transitorios y disposiciones del decreto original", []
    i, n = 0, len(lineas)
    while i < n:
        l = lineas[i]
        if re.match(r"^DECRETO\b", l) and (i == 0 or not lineas[i - 1].strip() or lineas[i - 1] == "\f" or True):
            # el encabezado de decreto termina en 'Publicado en el Diario Oficial...'
            j = i
            while j < min(i + 12, n) and not re.search(r"Publicado en el Diario Oficial", lineas[j]):
                j += 1
            if j < min(i + 12, n):
                if cur:
                    bloques.append((cur_t, cur))
                titulo = " ".join(x.strip() for x in lineas[i:j + 1] if x.strip() and x != "\f")
                cur_t, cur = re.sub(r"\s+", " ", titulo), []
                i = j + 1
                continue
        cur.append(l)
        i += 1
    if cur:
        bloques.append((cur_t, cur))
    return bloques
