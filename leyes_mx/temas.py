"""Etiquetado por temas: un vocabulario controlado (temas.json) aplicado de forma determinista a TODO lo que hay en la base.

No hay etiquetas puestas a mano ni por un modelo: cada tema es una lista de palabras en el idioma de la ley y la
regla para etiquetar es una sola, escrita abajo. El mismo vocabulario sobre los mismos textos da siempre el mismo
índice, así que se puede regenerar, auditar y exigir en la validación.

Un documento (artículo de leyes/ o regla de rmf/) recibe un tema si:
  - alguna palabra del tema aparece en su ENCABEZADO (la ubicación Título/Capítulo/Sección de un artículo; el título y
    la ubicación de una regla), o
  - alguna palabra aparece al menos `umbral` veces en el texto (por omisión 2; 1 si el texto tiene menos de 1,500
    caracteres, porque un artículo corto que nombra el tema una vez trata de él), o
  - es una regla cuyo fundamento cita una de las leyes de `citas` del tema.
El puntaje ordena los resultados: 5 por cada coincidencia de encabezado, 1 por cada una en el texto (máximo 20) y 3 por cita.

Salida (derivada, se regenera con scripts/etiquetar.py): temas/<anio>/_indice.json, _resumen.md y <tema>.md.
"""
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from . import store
from .ids import clave_orden

RAIZ = Path(__file__).resolve().parent.parent
ESQUEMA = 1
UMBRAL_POR_OMISION = 2
# Un texto corto que nombra el tema una vez trata de ese tema: por debajo de este largo (caracteres) el umbral baja a 1.
TEXTO_CORTO = 1500
MAX_TEXTO = 20
PESO_ENCABEZADO = 5
PESO_CITA = 3
RE_ID_TEMA = re.compile(r"^[a-z][a-z0-9\-]*$")


def normalizar(t):
    """Minúsculas, sin acentos y con todo lo que no es letra o número convertido en un espacio."""
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def cargar_vocabulario(raiz=None):
    ruta = Path(raiz or RAIZ) / "temas.json"
    return json.loads(ruta.read_text(encoding="utf-8")), ruta


def validar_vocabulario(voc):
    """Errores de forma del vocabulario (lista de textos)."""
    errs, vistos = [], set()
    for i, t in enumerate(voc.get("temas", [])):
        tid = t.get("id", f"#{i}")
        if not RE_ID_TEMA.match(str(t.get("id", ""))):
            errs.append(f"tema {tid}: id inválido (minúsculas, números y guiones)")
        if tid in vistos:
            errs.append(f"tema {tid}: id repetido")
        vistos.add(tid)
        for k in ("nombre", "descripcion"):
            if not str(t.get(k, "")).strip():
                errs.append(f"tema {tid}: falta {k}")
        pal = t.get("palabras", [])
        if not pal and not t.get("citas"):
            errs.append(f"tema {tid}: sin palabras ni citas")
        norm = [normalizar(p) for p in pal]
        if any(not n for n in norm):
            errs.append(f"tema {tid}: palabra vacía")
        if len(set(norm)) != len(norm):
            errs.append(f"tema {tid}: palabras repetidas")
        if "umbral" in t and (not isinstance(t["umbral"], int) or t["umbral"] < 1):
            errs.append(f"tema {tid}: umbral inválido")
        for ch in "—«»":
            if ch in json.dumps(t, ensure_ascii=False):
                errs.append(f"tema {tid}: lleva el carácter {ch!r}")
    return errs


def _patron(palabras):
    """Una sola expresión por tema: las palabras más largas primero; cada una admite plural (s, es)."""
    alt = []
    for p in sorted({normalizar(x) for x in palabras if normalizar(x)}, key=lambda x: (-len(x), x)):
        alt.append(r"\s+".join(re.escape(w) for w in p.split()) + r"(?:s|es)?")
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alt) + r")(?![a-z0-9])") if alt else None


# ---------------------------------------------------------------- documentos

def documentos(raiz, anio):
    """Todo lo etiquetable del año: artículos de leyes/ y reglas de rmf/. Cada uno: dict con ley, id, tipo, encabezado, texto, citas."""
    raiz = Path(raiz)
    docs = []
    base = raiz / "leyes" / str(anio)
    if base.is_dir():
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            for f in sorted(d.glob("art-*.md")):
                fm, cuerpo = store.parse_front_matter(f.read_text(encoding="utf-8"))
                if fm.get("estatus") == "derogado":
                    continue
                docs.append({"ley": d.name, "id": str(fm["articulo"]), "tipo": "articulo", "archivo": f"leyes/{anio}/{d.name}/{f.name}",
                             "encabezado": fm.get("ubicacion", ""), "texto": store._texto_articulo(cuerpo), "citas": []})
    rb = raiz / "rmf" / str(anio)
    if rb.is_dir():
        for meta in sorted(rb.glob("*/_meta.json")):
            d = meta.parent
            if not (d / "reglas").is_dir():
                continue
            sigla = json.loads(meta.read_text(encoding="utf-8"))["sigla"]
            for f in sorted((d / "reglas").glob("regla-*.md")):
                fm, cuerpo = store.parse_front_matter(f.read_text(encoding="utf-8"))
                if fm.get("estatus") == "derogado":
                    continue
                docs.append({"ley": sigla, "id": fm["regla"], "tipo": "regla", "archivo": f"rmf/{anio}/{d.name}/reglas/{f.name}",
                             "encabezado": f"{fm.get('titulo', '')}. {fm.get('ubicacion', '')}",
                             "texto": cuerpo.split("\n## Fundamento", 1)[0], "citas": sorted(fm.get("referencias_leyes", {}))})
    return docs


def _clave_doc(d):
    # artículos: orden numérico de la ley; reglas: orden numérico de la regla
    if d["tipo"] == "regla":
        return (d["ley"], tuple(int(x) for x in d["id"].split(".")))
    return (d["ley"], clave_orden(d["id"]))


def etiquetar(docs, voc):
    """{tema: [[ley, id, tipo, puntaje, [donde...]]...]} y {ley: [documentos, etiquetados]}."""
    temas = voc["temas"]
    pats = {t["id"]: _patron(t.get("palabras", [])) for t in temas}
    por_tema = defaultdict(list)
    cobertura = defaultdict(lambda: [0, 0])
    for d in sorted(docs, key=_clave_doc):
        enc, txt = normalizar(d["encabezado"]), normalizar(d["texto"])
        con_alguno = False
        for t in temas:
            pat, umbral = pats[t["id"]], t.get("umbral", UMBRAL_POR_OMISION)
            if len(d["texto"]) < TEXTO_CORTO:
                umbral = 1
            n_enc = len(pat.findall(enc)) if pat else 0
            n_txt = len(pat.findall(txt)) if pat else 0
            cita = bool(set(t.get("citas", [])) & set(d["citas"]))
            donde = []
            if n_enc:
                donde.append("encabezado")
            if n_txt >= umbral:
                donde.append("texto")
            if cita:
                donde.append("fundamento")
            if not donde:
                continue
            punt = PESO_ENCABEZADO * n_enc + min(n_txt, MAX_TEXTO) + (PESO_CITA if cita else 0)
            por_tema[t["id"]].append([d["ley"], d["id"], d["tipo"], punt, donde])
            con_alguno = True
        cobertura[d["ley"]][0] += 1
        cobertura[d["ley"]][1] += 1 if con_alguno else 0
    return por_tema, cobertura


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def fuentes(raiz, anio):
    """sha256 del PDF de cada ordenamiento presente: si cambia uno, o se agrega otro, el índice queda desactualizado."""
    raiz, res = Path(raiz), {}
    for m in sorted((raiz / "leyes" / str(anio)).glob("*/_meta.json")):
        res[m.parent.name] = json.loads(m.read_text(encoding="utf-8")).get("sha256_pdf")
    for m in sorted((raiz / "rmf" / str(anio)).glob("*/_meta.json")):
        meta = json.loads(m.read_text(encoding="utf-8"))
        if "reglas_extraidas" in meta:
            res[meta["sigla"]] = meta.get("sha256_pdf")
    return res


def construir(raiz, anio):
    """Devuelve {ruta relativa: bytes} de todo lo que debe haber en temas/<anio>/ (nada se escribe aquí)."""
    raiz = Path(raiz)
    voc, ruta_voc = cargar_vocabulario(raiz)
    errs = validar_vocabulario(voc)
    if errs:
        raise ValueError("vocabulario inválido: " + "; ".join(errs))
    docs = documentos(raiz, anio)
    por_tema, cobertura = etiquetar(docs, voc)
    nombres = {t["id"]: t for t in voc["temas"]}
    salida = {}
    indice = {
        "esquema": ESQUEMA, "anio": anio,
        "vocabulario_sha256": sha256_bytes(ruta_voc.read_bytes()),
        "fuentes": fuentes(raiz, anio),
        "documentos": len(docs),
        "cobertura": {k: {"documentos": v[0], "con_tema": v[1]} for k, v in sorted(cobertura.items())},
        "temas": {t["id"]: {"nombre": t["nombre"], "documentos": len(por_tema.get(t["id"], [])),
                            "entradas": [[e[0], e[1], e[3], "".join(x[0] for x in e[4])] for e in sorted(por_tema.get(t["id"], []), key=lambda e: (e[0], e[1]))]}
                  for t in voc["temas"]},
    }
    # "".join(x[0]): e=encabezado, t=texto, f=fundamento (compacto: el índice es grande)
    salida[f"temas/{anio}/_indice.json"] = (json.dumps(indice, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    filas = [f"# Temas, vigencia {anio}\n", f"{len(docs)} documentos (artículos y reglas) y {len(voc['temas'])} temas. "
             "Se generan con `scripts/etiquetar.py`; no se editan a mano.\n",
             "| Tema | Documentos | Qué cubre |", "|---|---|---|"]
    for t in voc["temas"]:
        filas.append(f"| [{t['nombre']}]({t['id']}.md) | {len(por_tema.get(t['id'], []))} | {t['descripcion']} |")
    filas += ["", "## Cobertura por ordenamiento", "", "| Ordenamiento | Documentos | Con al menos un tema |", "|---|---|---|"]
    for k, v in sorted(cobertura.items()):
        filas.append(f"| {k} | {v[0]} | {v[1]} |")
    salida[f"temas/{anio}/_resumen.md"] = ("\n".join(filas) + "\n").encode("utf-8")
    for t in voc["temas"]:
        ents = sorted(por_tema.get(t["id"], []), key=lambda e: (-e[3], e[0], e[1]))
        md = [f"# {t['nombre']}\n", f"{t['descripcion']}\n",
              f"Palabras: {', '.join(t.get('palabras', [])) or '(solo por citas)'}." + (f" Reglas cuyo fundamento cita: {', '.join(t['citas'])}." if t.get("citas") else ""),
              "", f"{len(ents)} documentos, de mayor a menor puntaje (encabezado, texto, fundamento).\n",
              "| Ley | Artículo o regla | Puntaje | Dónde | Archivo |", "|---|---|---|---|---|"]
        arch = {(d["ley"], d["id"]): d["archivo"] for d in docs}
        for ley, did, tipo, punt, donde in ents:
            a = arch[(ley, did)]
            md.append(f"| {ley} | {'regla ' if tipo == 'regla' else ''}{did} | {punt} | {', '.join(donde)} | [{a.split('/')[-1]}](../../{a}) |")
        salida[f"temas/{anio}/{t['id']}.md"] = ("\n".join(md) + "\n").encode("utf-8")
    return salida


def escribir(raiz, anio):
    raiz = Path(raiz)
    salida = construir(raiz, anio)
    dest = raiz / "temas" / str(anio)
    if dest.exists():
        for f in dest.glob("*"):
            f.unlink()
    dest.mkdir(parents=True, exist_ok=True)
    for ruta, datos in salida.items():
        (raiz / ruta).write_bytes(datos)
    return salida


def validar(raiz, anio=None):
    """(errores, avisos): vocabulario bien formado y temas/<anio>/ idéntico a lo que daría regenerarlo ahora."""
    raiz = Path(raiz)
    errs, avisos = [], []
    if not (raiz / "temas.json").exists():
        return ["falta temas.json (el vocabulario de temas)"], avisos
    voc, _ = cargar_vocabulario(raiz)
    errs += [f"temas.json: {e}" for e in validar_vocabulario(voc)]
    if errs:
        return errs, avisos
    anios = [anio] if anio else store._anios(raiz)
    for a in anios:
        esperado = construir(raiz, a)
        dest = raiz / "temas" / str(a)
        for ruta, datos in esperado.items():
            p = raiz / ruta
            if not p.exists():
                errs.append(f"{ruta}: falta. Regenerar con: python3 scripts/etiquetar.py")
            elif p.read_bytes() != datos:
                errs.append(f"{ruta}: desactualizado respecto al vocabulario o a los textos. Regenerar con: python3 scripts/etiquetar.py")
        sobran = sorted(f.name for f in dest.glob("*")) if dest.is_dir() else []
        for n in sobran:
            if f"temas/{a}/{n}" not in esperado:
                errs.append(f"temas/{a}/{n}: sobra (ya no corresponde a ningún tema)")
        idx = json.loads(esperado[f"temas/{a}/_indice.json"])
        for k, v in idx["cobertura"].items():
            if v["con_tema"] == 0:
                avisos.append(f"{a}/{k}: ningún documento recibió un tema; revisar si el vocabulario necesita palabras de esa materia")
        for t, v in idx["temas"].items():
            if v["documentos"] == 0:
                avisos.append(f"tema {t}: no etiquetó ningún documento")
    return errs, avisos
