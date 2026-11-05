"""Extractor de la Resolución Miscelánea Fiscal (RMF): una regla por archivo.

A diferencia de las leyes (que se cortan por "Artículo N."), la RMF se organiza en reglas numeradas
(2.7.1.1, 3.13.30...) con un título arriba, el texto y una línea de fundamento al final
("CFF 29, 29-A, RMF 2.7.1.32."). Ese PDF distingue cada parte por TIPOGRAFÍA, no por el texto:

  - el número de la regla y su título van en NEGRITA, con el número en el margen izquierdo;
  - el fundamento va en CURSIVA, al final de la regla;
  - los encabezados Título/Capítulo/Sección van en negrita y centrados.

Por eso se lee con `pdftohtml -xml` (que conserva negrita, cursiva y posición) en lugar de `pdftotext`.
Salida: rmf/<anio>/<slug>/regla-<id>.md, _indice.md, _meta.json, glosario.md, preambulo.md, transitorios.md.
"""
import hashlib
import html
import json
import re
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path

from .ids import normalizar_id

RAIZ = Path(__file__).resolve().parent.parent

# Una línea del PDF se agrupa por `top` (tolerancia en px). Entre líneas de un mismo párrafo hay 16-19 px;
# entre párrafos, 23 o más.
TOL_LINEA = 3
GAP_PARRAFO = 21
# Entre un encabezado y el título de la regla hay 20 px o más; dentro de un mismo bloque, 16-18.
GAP_TITULO = 20
# Margen izquierdo donde cae el número de regla (hay menciones a otras reglas dentro del texto, con left >= 230).
MAX_LEFT_REGLA = 200
# Columna del texto de las reglas (títulos y cuerpo). Los encabezados centrados empiezan más a la derecha.
MAX_LEFT_TITULO = 245
# Entre dos fragmentos de una misma línea, más de GAP_COLUMNA px puede ser una columna de tabla, pero el texto
# justificado también abre huecos así (20 a 60 px). Una corrida de líneas es tabla si tiene un hueco de GAP_TABLA o más,
# o si son MIN_FILAS_TABLA líneas seguidas con huecos de columna.
GAP_COLUMNA = 25
GAP_TABLA = 60
MIN_FILAS_TABLA = 3

RE_RUIDO = re.compile(
    r"^\s*(DIARIO OFICIAL\s+(\(.*?\)\s+)?(Lunes|Martes|Mi[eé]rcoles|Jueves|Viernes|S[aá]bado|Domingo) \d+ de \w+ de \d{4}"
    r"|(\(.*?\)\s+)?(Lunes|Martes|Mi[eé]rcoles|Jueves|Viernes|S[aá]bado|Domingo) \d+ de \w+ de \d{4}\s+DIARIO OFICIAL)\s*$"
)
RE_ID = re.compile(r"^(\d{1,2}(?:\.\d{1,3}){1,4})\.?$")
RE_ENC = re.compile(r"^(T[ií]tulo|Cap[ií]tulo|Secci[oó]n|Subsecci[oó]n)\s+(\d+(?:\.\d+)*)\.?\s*(.*)$")
RE_ETIQUETA = re.compile(r"^(?:[IVXLCDM]+\.|[a-z]\)|[A-Z]\)|\d{1,2}\.|\d{1,2}\)|[a-z]{1,2}\.\)|[A-Z]\.|[a-z]\.)$")


# ---------------------------------------------------------------- lectura del PDF

def _plano(inner):
    return html.unescape(re.sub(r"<[^>]+>", "", inner))


def leer_lineas(pdf):
    """Devuelve lista de líneas: {p, top, chunks:[{left,w,t,b,i}], texto}. Sin los encabezados de página."""
    pdf = Path(pdf)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftohtml", "-xml", "-i", "-q", str(pdf), str(Path(tmp) / "doc")], check=True)
        xml = (Path(tmp) / "doc.xml").read_text(encoding="utf-8", errors="replace")
    lineas = []
    for pm in re.finditer(r'<page number="(\d+)"[^>]*>(.*?)</page>', xml, re.S):
        num = int(pm.group(1))
        chunks = []
        for m in re.finditer(r'<text top="(-?\d+)" left="(-?\d+)" width="(\d+)" height="(\d+)" font="\d+">(.*?)</text>', pm.group(2), re.S):
            top, left, w, _h, inner = m.groups()
            t = _plano(inner)
            if not t.strip():
                continue
            s = inner.lstrip()
            chunks.append({"top": int(top), "left": int(left), "w": int(w), "t": t,
                           "b": s.startswith("<b>") or s.startswith("<i><b>"), "i": s.startswith("<i>") and not s.startswith("<i><b>")})
        chunks.sort(key=lambda c: (c["top"], c["left"]))
        grupos = []
        for c in chunks:
            if grupos and abs(c["top"] - grupos[-1][0]["top"]) <= TOL_LINEA:
                grupos[-1].append(c)
            else:
                grupos.append([c])
        for g in grupos:
            g.sort(key=lambda c: c["left"])
            texto = " ".join(c["t"].strip() for c in g)
            if RE_RUIDO.match(texto):
                continue
            lineas.append({"p": num, "top": g[0]["top"], "chunks": g, "texto": limpiar(texto)})
    return lineas


def limpiar(s):
    """Quita el espaciado de justificación (dobles espacios) y espacios de extremo."""
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- clasificación de líneas

def solo_negrita(l):
    return all(c["b"] for c in l["chunks"])


def empieza_negrita(l):
    """Títulos y encabezados llevan a veces un fragmento suelto sin negrita (una coma); el primero siempre es negrita."""
    return l["chunks"][0]["b"]


def con_cursiva(l):
    """El fundamento va en cursiva, pero a veces un fragmento (p. ej. 'RMF 5.2.28.') queda sin ella."""
    return any(c["i"] for c in l["chunks"])


def id_regla(l):
    """Id de regla si la línea ABRE una regla (número en negrita en el margen); si no, None."""
    c = l["chunks"][0]
    if c["left"] > MAX_LEFT_REGLA or not c["b"]:
        return None
    m = RE_ID.match(c["t"].strip())
    return m.group(1) if m else None


def es_encabezado(l):
    return solo_negrita(l) and bool(RE_ENC.match(l["texto"])) and l["chunks"][0]["left"] > MAX_LEFT_TITULO


def clave_regla(rid):
    return tuple(int(x) for x in rid.split("."))


def nombre_archivo_regla(rid):
    return f"regla-{rid}.md"


# ---------------------------------------------------------------- segmentación

def segmentar(lineas):
    """Índices que separan preámbulo, glosario, cuerpo (Títulos 1 a 12) y transitorios finales."""
    ini_cuerpo = next(k for k, l in enumerate(lineas)
                      if solo_negrita(l) and re.match(r"^T[ií]tulo 1\.\s", l["texto"]) and l["chunks"][0]["left"] > MAX_LEFT_TITULO)
    ultima = max(k for k, l in enumerate(lineas) if id_regla(l))
    fin_cuerpo = next(k for k in range(ultima, len(lineas))
                      if solo_negrita(lineas[k]) and lineas[k]["texto"].lower() == "transitorios")
    ini_glosario = max(k for k in range(ini_cuerpo) if solo_negrita(lineas[k]) and lineas[k]["texto"].lower() == "glosario")
    ini_contenido = next((k for k, l in enumerate(lineas) if l["texto"].lower() == "contenido"), 0)
    return {"contenido": ini_contenido, "glosario": ini_glosario, "cuerpo": ini_cuerpo, "transitorios": fin_cuerpo}


_KW = {"título": "Título", "titulo": "Título", "capítulo": "Capítulo", "capitulo": "Capítulo",
       "sección": "Sección", "seccion": "Sección", "subsección": "Subsección", "subseccion": "Subsección"}
_NIVEL = {"Título": 1, "Capítulo": 2, "Sección": 3, "Subsección": 4}


def _norm(t):
    return re.sub(r"[\s“”\"']+", "", t).lower()


def indice_encabezados(lineas, seg):
    """Texto exacto de cada Título/Capítulo/Sección según el índice ("Contenido") del propio PDF.

    El índice trae cada encabezado completo y sin saltos de página en medio; el cuerpo, en cambio, lo parte entre
    páginas y lo mezcla con el título de la regla. Con este texto se sabe cuántas líneas ocupa cada encabezado.
    """
    toc, actual, titulo_n = {}, None, None
    for l in lineas[seg["contenido"]:seg["glosario"]]:
        t = l["texto"]
        m = RE_ENC.match(t)
        if m:
            actual = (_KW[m.group(1).lower()], m.group(2))
            toc[actual] = limpiar(m.group(3))
            continue
        m = re.match(r"^(\d{1,2})\.\s+(\S.*)$", t)
        if m and l["chunks"][0]["left"] <= 160:
            actual = ("Título", m.group(1))
            toc[actual] = limpiar(m.group(2))
        elif actual:
            toc[actual] = limpiar(toc[actual] + " " + t)
    return toc


def _cola(lineas, a, b, toc):
    """Analiza hacia atrás las líneas [a, b) que preceden al número de la regla siguiente.

    Devuelve (inicio_cola, fundamento[list de líneas], encabezados[list de [kw, num, texto]], titulo[list de líneas]).
    Orden en el PDF: ...texto de la regla, fundamento (cursiva), encabezados Título/Capítulo/Sección (negrita),
    título (negrita), número. Los encabezados se consumen con el texto exacto del índice del PDF; lo que queda de la
    corrida en negrita es el título.
    """
    e = b
    while e > a and empieza_negrita(lineas[e - 1]):
        e -= 1
    corrida = lineas[e:b]
    # texto de la regla anterior que empiece en negrita (no es encabezado ni título): se devuelve al cuerpo
    while corrida and not RE_ENC.match(corrida[0]["texto"]) and len(corrida) > 1 and corrida[0]["chunks"][0]["left"] > MAX_LEFT_TITULO:
        corrida = corrida[1:]
        e += 1
    pos, encabezados = 0, []
    while pos < len(corrida):
        m = RE_ENC.match(corrida[pos]["texto"])
        if not m:
            break
        kw, num = _KW[m.group(1).lower()], m.group(2)
        conocido = toc.get((kw, num))
        acum = limpiar(m.group(3))
        pos += 1
        if conocido is not None:
            while pos < len(corrida) and _norm(acum) != _norm(conocido) and _norm(conocido).startswith(_norm(acum + " " + corrida[pos]["texto"])[:len(_norm(conocido))]) \
                    and len(_norm(acum)) < len(_norm(conocido)):
                acum = limpiar(acum + " " + corrida[pos]["texto"])
                pos += 1
            texto = conocido if _norm(acum) == _norm(conocido) else acum
        else:
            while pos < len(corrida) and not RE_ENC.match(corrida[pos]["texto"]) and corrida[pos]["p"] == corrida[pos - 1]["p"] \
                    and corrida[pos]["top"] - corrida[pos - 1]["top"] < GAP_TITULO:
                acum = limpiar(acum + " " + corrida[pos]["texto"])
                pos += 1
            texto = acum
        encabezados.append([kw, num, texto])
    titulo = corrida[pos:]
    inicio = b - len(titulo) - pos
    fund = []
    f = e if False else inicio
    while f > a and con_cursiva(lineas[f - 1]):
        f -= 1
        fund.insert(0, lineas[f])
    return f, fund, encabezados, titulo


# ---------------------------------------------------------------- fundamento

_SIGLA = re.compile(r"^([A-Z][A-Za-z]{1,9})\s+(.+)$")
_NUM_ART = re.compile(r"^\d+[\w\-\.ºo]*(?:\s+(?:Bis|Ter|Qu[aá]ter|Quinquies|Sexies|Septies|Octies|Nonies|Decies))?$", re.I)
_REGLA = re.compile(r"^\d{1,2}(?:\.\d{1,3}){1,4}\.?$")


def parsear_fundamento(raw):
    """'CFF 29, 29-A, RMF 2.7.1.32., 2.7.2.14.' -> ({'CFF': ['29', '29-A']}, ['2.7.1.32', '2.7.2.14'], parcial: bool).

    Mejor esfuerzo: lo que no encaja (textos como 'Decretos región fronteriza norte 30/12/2020 Segundo') no se
    interpreta y marca `parcial`. El texto original (`fundamento`) es el que manda.
    """
    leyes, reglas, parcial, actual = OrderedDict(), [], False, None
    for tok in [t.strip() for t in raw.split(",") if t.strip()]:
        m = _SIGLA.match(tok)
        if m and m.group(1) == "RMF" and _REGLA.match(m.group(2).strip()):
            reglas.append(m.group(2).strip().rstrip(".")); actual = "RMF"; continue
        if m and m.group(1).isupper() and _NUM_ART.match(m.group(2).strip()):
            actual = m.group(1)
            _agregar(leyes, actual, m.group(2).strip())
            continue
        if actual == "RMF" and _REGLA.match(tok):
            reglas.append(tok.rstrip(".")); continue
        if actual and actual != "RMF" and _NUM_ART.match(tok):
            _agregar(leyes, actual, tok); continue
        parcial = True
        actual = None
    return {k: v for k, v in leyes.items()}, reglas, parcial


def _agregar(leyes, sigla, tok):
    i = normalizar_id(tok) or tok
    if i not in leyes.setdefault(sigla, []):
        leyes[sigla].append(i)


# ---------------------------------------------------------------- formato del cuerpo

def _es_etiqueta(chunk):
    return bool(RE_ETIQUETA.match(chunk["t"].strip()))


def _tabular(l, desde=0):
    """Línea con columnas: dos o más fragmentos separados por un hueco ancho, que no sea solo 'etiqueta + texto'."""
    ch = l["chunks"][desde:]
    if len(ch) < 2:
        return False
    if len(ch) == 2 and _es_etiqueta(ch[0]):
        return False
    huecos = sum(1 for x, y in zip(ch, ch[1:]) if y["left"] - (x["left"] + x["w"]) > GAP_COLUMNA)
    return huecos >= 1 and len(ch) >= 2


def _texto_columnas(l, base):
    out = ""
    for c in l["chunks"]:
        col = max(0, (c["left"] - base) // 6)
        out = out.ljust(col) + limpiar(c["t"]) + " "
    return out.rstrip()


def _hueco_max(l, desde=0):
    ch = l["chunks"][desde:]
    return max((y["left"] - (x["left"] + x["w"]) for x, y in zip(ch, ch[1:])), default=0)


def _marcar_tablas(lineas, primera_sin_id):
    """Lista de booleanos: qué líneas son filas de tabla. Una corrida cuenta como tabla solo si es claramente una."""
    cand = [_tabular(l, 1 if (k == 0 and primera_sin_id) else 0) for k, l in enumerate(lineas)]
    es = [False] * len(lineas)
    k = 0
    while k < len(lineas):
        if not cand[k]:
            k += 1
            continue
        j = k
        while j < len(lineas) and cand[j]:
            j += 1
        mayor = max(_hueco_max(lineas[x], 1 if (x == 0 and primera_sin_id) else 0) for x in range(k, j))
        if mayor >= GAP_TABLA or (j - k) >= MIN_FILAS_TABLA:
            for x in range(k, j):
                es[x] = True
        k = j
    return es


def formatear(lineas, primera_sin_id=False):
    """Líneas del cuerpo de una regla -> markdown: un párrafo (o fracción/inciso) por bloque; tablas en ```text."""
    if not lineas:
        return ""
    base = min(c["left"] for l in lineas for c in l["chunks"])
    es_tabla = _marcar_tablas(lineas, primera_sin_id)
    bloques, actual, tabla = [], [], []
    prev = None

    def cerrar():
        nonlocal actual
        if actual:
            bloques.append(("p", limpiar(" ".join(actual))))
            actual = []

    def cerrar_tabla():
        nonlocal tabla
        if tabla:
            bloques.append(("t", "\n".join(tabla)))
            tabla = []

    for k, l in enumerate(lineas):
        desde = 1 if (k == 0 and primera_sin_id) else 0
        if es_tabla[k]:
            cerrar()
            tabla.append(_texto_columnas({"chunks": l["chunks"][desde:]}, base))
            prev = l
            continue
        if tabla:
            # una línea corta entre filas de la misma tabla es la continuación de una celda
            sigue = any(es_tabla[k + 1:k + 3])
            if sigue and len(l["chunks"]) <= 2 and not _es_etiqueta(l["chunks"][desde]) and prev is not None \
                    and l["top"] - prev["top"] < GAP_PARRAFO and l["p"] == prev["p"]:
                tabla.append(_texto_columnas({"chunks": l["chunks"][desde:]}, base))
                prev = l
                continue
            cerrar_tabla()
        texto = limpiar(" ".join(c["t"] for c in l["chunks"][desde:]))
        nuevo = False
        if prev is None or not actual:
            nuevo = True
        elif _es_etiqueta(l["chunks"][desde]):
            nuevo = True
        elif l["chunks"][desde]["b"] and l["chunks"][desde]["left"] <= MAX_LEFT_REGLA:
            nuevo = True  # "Primero.", "Segundo."... de los transitorios: en negrita y en el margen
        elif l["p"] == prev["p"] and l["top"] - prev["top"] >= GAP_PARRAFO:
            nuevo = True
        elif l["p"] != prev["p"] and re.search(r"[\.\:;]$", actual[-1]) and re.match(r"^[A-ZÁÉÍÓÚÑ\(“\"]", texto):
            nuevo = True  # salto de página: solo se separa si el párrafo previo terminó
        if nuevo:
            cerrar()
        actual.append(texto)
        prev = l
    cerrar()
    cerrar_tabla()
    salida = []
    for tipo, t in bloques:
        salida.append(t if tipo == "p" else "```text\n" + t + "\n```")
    return "\n\n".join(salida)


# ---------------------------------------------------------------- extracción

def extraer(lineas):
    """Devuelve (segmentos, reglas). Cada regla: id, pagina, titulo, ubicacion, fundamento, cuerpo (markdown), cuerpo_lineas."""
    seg = segmentar(lineas)
    a, b = seg["cuerpo"], seg["transitorios"]
    inicios = [k for k in range(a, b) if id_regla(lineas[k])]
    # colas[n] = lo que hay justo antes de la regla n: [fundamento de la n-1][encabezados][título de la n].
    # colas[len(inicios)] = lo que hay antes de "Transitorios": solo el fundamento de la última regla.
    toc = indice_encabezados(lineas, seg)
    colas = [_cola(lineas, a, inicios[0], toc)]
    for n in range(1, len(inicios)):
        colas.append(_cola(lineas, inicios[n - 1] + 1, inicios[n], toc))
    colas.append(_cola(lineas, inicios[-1] + 1, b, toc))
    estructura, reglas = OrderedDict(), []
    for n, s in enumerate(inicios):
        _e, _f, encs, tit = colas[n]
        for kw, num, texto in encs:
            nivel = _NIVEL[kw]
            for k in [x for x in estructura if x >= nivel]:
                del estructura[k]
            estructura[nivel] = f"{kw} {num}. {texto}".strip()
        fin_cuerpo, fund = colas[n + 1][0], colas[n + 1][1]
        cuerpo_lineas = lineas[s:fin_cuerpo]
        reglas.append({
            "id": id_regla(lineas[s]), "pagina": lineas[s]["p"], "linea": s,
            "titulo": limpiar(" ".join(l["texto"] for l in tit)),
            "ubicacion": " > ".join(estructura[k] for k in sorted(estructura)),
            "fundamento": limpiar(" ".join(l["texto"] for l in fund)),
            "cuerpo_lineas": cuerpo_lineas,
            "cuerpo": formatear(cuerpo_lineas, primera_sin_id=True),
        })
    return seg, reglas


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _yaml(v):
    return json.dumps(v, ensure_ascii=False)


def front_matter(campos):
    return "---\n" + "".join(f"{k}: {_yaml(v)}\n" for k, v in campos.items()) + "---\n"


def construir(pdf, anio, cfg, destino_raiz=None, fecha_descarga=None, escribir=True):
    """Escribe rmf/<anio>/<carpeta>/ para la resolución `cfg` (ver fuentes.json: rmf). Devuelve el resumen."""
    from datetime import date
    pdf = Path(pdf)
    lineas = leer_lineas(pdf)
    seg, reglas = extraer(lineas)
    sha = sha256(pdf)
    fecha_descarga = fecha_descarga or date.today().isoformat()
    destino_raiz = Path(destino_raiz or RAIZ / "rmf")
    dest = destino_raiz / str(anio) / cfg["carpeta"]
    comunes = OrderedDict([
        ("ley", cfg["sigla"]), ("nombre_ley", cfg["nombre"]), ("vigencia_anio", anio),
        ("publicacion_dof", cfg["publicacion_dof"]), ("fuente_url", cfg["url"]), ("fecha_descarga", fecha_descarga),
    ])
    if escribir:
        import shutil
        if dest.exists():
            shutil.rmtree(dest)
        (dest / "reglas").mkdir(parents=True)
    indice = []
    for r in reglas:
        leyes, regs, parcial = parsear_fundamento(r["fundamento"])
        fm = OrderedDict(comunes)
        fm["regla"] = r["id"]
        fm["titulo"] = r["titulo"]
        fm["ubicacion"] = r["ubicacion"]
        fm["estatus"] = "derogado" if re.match(r"^\(?\s*(se\s+deroga|derogad[oa])", r["cuerpo"], re.I) else "vigente"
        fm["pagina_pdf"] = r["pagina"]
        fm["sha256_fuente"] = sha
        fm["fundamento"] = r["fundamento"]
        fm["referencias_leyes"] = leyes
        fm["referencias_reglas"] = regs
        if parcial:
            fm["referencias_parcial"] = True
        md = front_matter(fm) + f"\n# Regla {r['id']}. {r['titulo']}\n\n{r['cuerpo']}\n"
        if r["fundamento"]:
            md += f"\n## Fundamento (cursiva del PDF)\n\n{r['fundamento']}\n"
        if escribir:
            (dest / "reglas" / nombre_archivo_regla(r["id"])).write_text(md, encoding="utf-8")
        indice.append((r["id"], r["titulo"], fm["estatus"], r["cuerpo"]))
    # glosario, preámbulo y transitorios finales
    def bloque(a, b, titulo):
        ls = lineas[a:b]
        return f"# {titulo}\n\n" + formatear(ls) + "\n"
    if escribir:
        (dest / "preambulo.md").write_text(front_matter({**comunes, "tipo": "preambulo", "sha256_fuente": sha}) + "\n" +
                                           bloque(0, seg["contenido"], "Preámbulo y considerandos"), encoding="utf-8")
        (dest / "glosario.md").write_text(front_matter({**comunes, "tipo": "glosario", "sha256_fuente": sha}) + "\n" +
                                          bloque(seg["glosario"] + 1, seg["cuerpo"] - 0, "Glosario de la RMF"), encoding="utf-8")
        (dest / "transitorios.md").write_text(front_matter({**comunes, "tipo": "transitorios", "sha256_fuente": sha}) + "\n" +
                                              bloque(seg["transitorios"] + 1, len(lineas), "Transitorios de la RMF"), encoding="utf-8")
        filas = [f"# Índice de {cfg['nombre']} ({cfg['sigla']}), vigencia {anio}\n",
                 f"Publicada en el DOF el {cfg['publicacion_dof']}. {len(reglas)} reglas. Fuente: {cfg['url']}\n",
                 "| Regla | Título | Estatus |", "|---|---|---|"]
        for rid, tit, est, _c in indice:
            filas.append(f"| {rid} | [{tit}](reglas/{nombre_archivo_regla(rid)}) | {est} |")
        (dest / "_indice.md").write_text("\n".join(filas) + "\n", encoding="utf-8")
        meta = {"sigla": cfg["sigla"], "nombre_oficial": cfg["nombre"], "fuente_url": cfg["url"], "publicacion_dof": cfg["publicacion_dof"],
                "fecha_descarga": fecha_descarga, "archivo": cfg.get("archivo", "RMF.pdf"), "sha256_pdf": sha, "paginas": max(l["p"] for l in lineas),
                "reglas_extraidas": len(reglas), "ultima_regla": reglas[-1]["id"], "primera_regla": reglas[0]["id"]}
        (dest / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"reglas": len(reglas), "sha256": sha, "segmentos": seg, "lista": reglas}
