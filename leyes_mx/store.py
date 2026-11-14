"""Biblioteca de consulta: lectura determinista por archivo y busqueda por palabras clave.

Es la capa que una API/MCP envolveria (ver docs/arquitectura.md):
  obtener_articulo, buscar, listar_leyes, estado_reforma, normalizar_articulo

Regla dura: lo que no es estatus "vigente"/"derogado" (p. ej. "proyecto") vive en proyectos/ y nunca se devuelve
sin pedirlo explicitamente (incluir_proyectos=True), siempre marcado.
"""
import json
import os
import re
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path

from . import versiones
from .ids import normalizar_id, id_desde_archivo, nombre_archivo, clave_orden

RAIZ = Path(os.environ.get("LEYES_MX_RAIZ") or Path(__file__).resolve().parent.parent)
AVISO_PROYECTO = ("PROYECTO: este texto NO es ley vigente. Solo lo sera si y cuando se publique en el DOF, "
                  "y a partir de la fecha que indique el decreto.")
AVISO_GENERAL = "Texto informativo de la Cámara de Diputados; no sustituye al DOF. La fuente oficial prevalece."


# ------------------------------------------------------------------ utilidades

def normalizar_articulo(texto):
    """'113 E', '113-e', '28 bis', 'Artículo 1o.-A' -> '113-E', '113-E', '28-bis', '1-A'. None si no se reconoce."""
    return normalizar_id(texto)


def parse_front_matter(texto):
    if not texto.startswith("---\n"):
        return {}, texto
    fin = texto.find("\n---\n", 4)
    if fin < 0:
        return {}, texto
    fm = {}
    for linea in texto[4:fin].splitlines():
        if ":" not in linea:
            continue
        k, v = linea.split(":", 1)
        v = v.strip()
        try:
            fm[k.strip()] = json.loads(v)
        except ValueError:
            fm[k.strip()] = v
    return fm, texto[fin + 5:]


def _anios(raiz=None):
    return versiones.anios(raiz or RAIZ)


def _sigla_dir(base, sigla):
    for p in base.iterdir():
        if p.is_dir() and p.name.upper() == sigla.upper():
            return p
    return None


def anio_por_defecto(sigla=None, hoy=None, raiz=None):
    """Anio de vigencia mas reciente con datos y no posterior al anio en curso (si no hay, el menor disponible)."""
    hoy = hoy or date.today()
    raiz = Path(raiz or RAIZ)
    cands = []
    for a in _anios(raiz):
        if sigla is None or versiones.tiene(raiz, sigla, a):
            cands.append(a)
    if not cands:
        return None
    pasados = [a for a in cands if a <= hoy.year]
    return max(pasados) if pasados else min(cands)


def _leer(ruta):
    texto = Path(ruta).read_text(encoding="utf-8")
    fm, cuerpo = parse_front_matter(texto)
    return fm, cuerpo


def _texto_articulo(cuerpo, sin_titulo=False):
    """Cuerpo sin la seccion de notas de reforma (y sin el titulo '# Articulo N' si sin_titulo)."""
    t = cuerpo.split("\n## Notas de reforma", 1)[0].strip()
    if sin_titulo:
        t = re.sub(r"^# Art[^\n]*\n+", "", t)
    return t


def _ficha(fm, cuerpo, ruta, raiz, vista=None):
    if vista is not None:
        fm = vista.ajustar(fm, ruta)
    d = {
        "ley": fm.get("ley"), "nombre_ley": fm.get("nombre_ley"), "articulo": fm.get("articulo"),
        "anio_vigencia": fm.get("vigencia_anio"), "ultima_reforma_dof": fm.get("ultima_reforma_dof"),
        "estatus": fm.get("estatus"), "fuente_url": fm.get("fuente_url"), "fecha_descarga": fm.get("fecha_descarga"),
        "texto": cuerpo.strip(), "ruta": str(Path(ruta).relative_to(raiz)),
    }
    if fm.get("estatus") not in ("vigente", "derogado"):
        d["aviso"] = AVISO_PROYECTO
        d["estado_proyecto"] = fm.get("estado_proyecto") or fm.get("estatus")
        d["entrada_en_vigor"] = fm.get("entrada_en_vigor")
    return d


# ------------------------------------------------------------------ listar / estado

def listar_leyes(raiz=None, incluir_proyectos=False):
    raiz = Path(raiz or RAIZ)
    res = []
    for a in _anios(raiz):
        for sig in versiones.siglas(raiz, a):
            meta = versiones.capa(raiz, sig, a).meta
            res.append({"sigla": meta["sigla"], "nombre": meta["nombre_oficial"], "anio_vigencia": a,
                        "ultima_reforma_dof": meta["ultima_reforma_dof"], "articulos": meta["articulos_extraidos"],
                        "estatus": "vigente", "fecha_descarga": meta["fecha_descarga"]})
    if incluir_proyectos:
        p = raiz / "proyectos"
        if p.is_dir():
            for anio in sorted(x for x in p.iterdir() if x.is_dir() and x.name.isdigit()):
                for d in sorted(x for x in anio.iterdir() if x.is_dir() and (x / "_meta.json").exists()):
                    n = len(list(d.glob("art-*.md")))
                    res.append({"sigla": d.name.upper(), "nombre": None, "anio_vigencia": int(anio.name), "ultima_reforma_dof": None,
                                "articulos": n, "estatus": "proyecto", "aviso": AVISO_PROYECTO})
    return res


def estado_reforma(anio=2027, raiz=None):
    """Lee proyectos/<anio>/estado.json (linea de tiempo con fuente y marca confirmado/no confirmado)."""
    ruta = Path(raiz or RAIZ) / "proyectos" / str(anio) / "estado.json"
    if not ruta.exists():
        return {"anio": anio, "disponible": False, "aviso": "sin seguimiento para ese anio"}
    d = json.loads(ruta.read_text(encoding="utf-8"))
    d["disponible"] = True
    d["aviso"] = AVISO_PROYECTO
    return d


# ------------------------------------------------------------------ obtener

def obtener_articulo(ley, articulo, anio=None, incluir_proyectos=False, raiz=None):
    """Lookup determinista. Devuelve dict (con 'texto') o None si no existe en leyes/ (nunca inventa).
    Si solo existe como proyecto y incluir_proyectos=False, devuelve None; con True devuelve la ficha marcada como proyecto."""
    raiz = Path(raiz or RAIZ)
    id_ = normalizar_id(articulo)
    if not id_:
        raise ValueError(f"articulo no reconocido: {articulo!r}")
    anio = anio or anio_por_defecto(ley, raiz=raiz)
    if anio is not None:
        v = versiones.vista(raiz, ley, anio)
        if v:
            f = v.articulo(id_)
            if f:
                fm, cuerpo = _leer(f)
                ficha = _ficha(fm, _texto_articulo(cuerpo), f, raiz, v)
                ficha["notas_reforma"] = _notas(cuerpo)
                ficha["advertencias"] = _advertencias(v.meta, id_)
                return ficha
    if incluir_proyectos:
        pdir = raiz / "proyectos"
        if pdir.is_dir():
            for ya in sorted((x for x in pdir.iterdir() if x.name.isdigit()), reverse=True):
                d = _sigla_dir(ya, ley)
                if d and (d / nombre_archivo(id_)).exists():
                    f = d / nombre_archivo(id_)
                    fm, cuerpo = _leer(f)
                    return _ficha(fm, _texto_articulo(cuerpo), f, raiz)
    return None


def _advertencias(meta, id_):
    return [a["texto"] for a in meta.get("advertencias", []) if not a.get("articulos") or id_ in a["articulos"]]


def _notas(cuerpo):
    if "\n## Notas de reforma" not in cuerpo:
        return []
    bloque = cuerpo.split("\n## Notas de reforma", 1)[1]
    return [l[2:].strip() for l in bloque.splitlines() if l.startswith("- ")]


# ------------------------------------------------------------------ busqueda

def _fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _firma_arbol(raiz):
    n, m = 0, 0
    for sub in ("leyes", "proyectos"):
        base = raiz / sub
        if base.is_dir():
            for p in list(base.rglob("art-*.md")) + (list(base.rglob("_meta.json")) if sub == "leyes" else []):
                n += 1
                m = max(m, int(p.stat().st_mtime))
    return f"v3:{n}:{m}"


def construir_indice(raiz=None, forzar=False):
    """SQLite FTS5 en build/indice.sqlite (ignorado por git). Se reconstruye solo si el arbol cambio."""
    raiz = Path(raiz or RAIZ)
    out = raiz / "build"
    out.mkdir(exist_ok=True)
    ruta = out / "indice.sqlite"
    firma = _firma_arbol(raiz)
    if ruta.exists() and not forzar:
        con = sqlite3.connect(ruta)
        try:
            if con.execute("select v from meta where k='firma'").fetchone()[0] == firma:
                return ruta
        except sqlite3.Error:
            pass
        con.close()
    if ruta.exists():
        ruta.unlink()
    con = sqlite3.connect(ruta)
    con.execute("create table meta(k text primary key, v text)")
    con.execute("create table art(id integer primary key, ley, articulo, anio int, estatus, ultima_reforma, ruta, texto)")
    con.execute("create virtual table fts using fts5(texto, articulo, content='', tokenize='unicode61 remove_diacritics 2')")
    i = 0

    def agregar(p, v=None):
        nonlocal i
        fm, cuerpo = _leer(p)
        if v is not None:
            fm = v.ajustar(fm, p)
        texto = re.sub(r"^> \*\*PROYECTO[^\n]*\n+", "", _texto_articulo(cuerpo), flags=re.M)
        texto = re.sub(r"^# Art[^\n]*\n+", "", texto).strip()
        i += 1
        con.execute("insert into art values (?,?,?,?,?,?,?,?)",
                    (i, fm.get("ley"), fm.get("articulo"), fm.get("vigencia_anio"), fm.get("estatus"),
                     fm.get("ultima_reforma_dof"), str(p.relative_to(raiz)), texto))
        con.execute("insert into fts(rowid, texto, articulo) values (?,?,?)",
                    (i, texto, f"{fm.get('ley')} {fm.get('articulo')}"))

    for a in versiones.anios(raiz):  # leyes: cada ley en cada año se indexa por su vista (capas heredadas incluidas)
        for sig in versiones.siglas(raiz, a):
            v = versiones.vista(raiz, sig, a)
            for p in v.archivos().values():
                agregar(p, v)
    base = raiz / "proyectos"
    if base.is_dir():
        for p in sorted(base.rglob("art-*.md")):
            agregar(p)
    con.execute("insert into meta values ('firma', ?)", (firma,))
    con.commit()
    con.close()
    return ruta


def _consulta_fts(q, op="AND"):
    toks = re.findall(r"\w+", _fold(q))
    return f" {op} ".join(f'"{t}"*' if len(t) > 2 else f'"{t}"' for t in toks)


def buscar(texto, ley=None, anio=None, incluir_proyectos=False, limite=10, raiz=None):
    """Busqueda por palabras clave (AND, prefijo, sin acentos, ranking BM25). Devuelve lista de dicts con
    ley, articulo, anio_vigencia, ultima_reforma_dof, estatus, fragmento, ruta. Excluye proyectos salvo incluir_proyectos."""
    raiz = Path(raiz or RAIZ)
    if not _consulta_fts(texto):
        return []
    for op in ("AND", "OR"):  # primero todas las palabras; si no hay nada, cualquiera
        res = _buscar(texto, _consulta_fts(texto, op), ley, anio, incluir_proyectos, limite, raiz)
        if res:
            return res
    return []


def _buscar(texto, consulta, ley, anio, incluir_proyectos, limite, raiz):
    ruta = construir_indice(raiz)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    anio_def = anio or anio_por_defecto(ley, raiz=raiz)
    filtros, args = [], [consulta]
    if ley:
        filtros.append("upper(a.ley)=upper(?)"); args.append(ley)
    if not incluir_proyectos:
        filtros.append("a.estatus in ('vigente','derogado')")
    if anio_def is not None:
        if incluir_proyectos:
            filtros.append("(a.estatus not in ('vigente','derogado') or a.anio=?)")
        else:
            filtros.append("a.anio=?")
        args.append(anio_def)
    sql = ("select a.*, bm25(fts) as r from fts join art a on a.id=fts.rowid "
           "where fts match ? " + "".join(" and " + f for f in filtros) + " order by r limit ?")
    args.append(limite)
    filas = con.execute(sql, args).fetchall()
    res = []
    for f in filas:
        d = {"ley": f["ley"], "articulo": f["articulo"], "anio_vigencia": f["anio"], "ultima_reforma_dof": f["ultima_reforma"],
             "estatus": f["estatus"], "fragmento": _fragmento(f["texto"], texto), "ruta": f["ruta"]}
        if f["estatus"] not in ("vigente", "derogado"):
            d["aviso"] = AVISO_PROYECTO
        res.append(d)
    con.close()
    return res


def _fragmento(texto, q, ancho=220):
    t = re.sub(r"\s+", " ", texto)
    plano = _fold(t)
    pos = -1
    for w in re.findall(r"\w+", _fold(q)):
        pos = plano.find(w)
        if pos >= 0:
            break
    pos = max(0, pos - 60)
    frag = t[pos:pos + ancho]
    return ("... " if pos else "") + frag + (" ..." if pos + ancho < len(t) else "")
