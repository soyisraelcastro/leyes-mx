"""Validación del glosario de sinónimos contables (glosario.json en la raíz del repo).

El glosario lo consume el buscador del paquete npm (npm/src/glosario.js); el motor de búsqueda de Python
(SQLite FTS5, scripts/buscar.py) NO lo usa. Aquí solo se valida, para que ninguna entrada llegue sin sustento:
cada artículo que cita una entrada debe existir en leyes/ y su `evidencia` debe aparecer, literal, en el texto
del artículo (sin distinguir acentos ni mayúsculas). La usa scripts/validar.py. Devuelve (errores, avisos).
"""
import json
import re
import unicodedata
from pathlib import Path

from . import store

ESQUEMA = 1
ARCHIVO = "glosario.json"
PROHIBIDOS = ("—", "«", "»")  # raya larga y comillas angulares: no se usan en este repo


def _plano(s):
    s = "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s):
    return re.findall(r"[^\W_]+", _plano(s))


def validar(raiz, anio=None):
    raiz = Path(raiz)
    ruta = raiz / ARCHIVO
    if not ruta.exists():
        return [], [f"sin {ARCHIVO} (el buscador funciona igual, sin ampliar consultas)"]
    errores, avisos = [], []
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"{ARCHIVO}: JSON inválido ({e})"], avisos
    crudo = ruta.read_text(encoding="utf-8")
    for p in PROHIBIDOS:
        if p in crudo:
            errores.append(f"{ARCHIVO}: contiene {p!r} (no se usan la raya larga ni las comillas angulares)")
    if d.get("esquema") != ESQUEMA:
        errores.append(f"{ARCHIVO}: esquema {d.get('esquema')!r}, se esperaba {ESQUEMA}")
    entradas = d.get("entradas") or []
    if not entradas:
        return errores + [f"{ARCHIVO}: sin entradas"], avisos
    anio = anio or store.anio_por_defecto(raiz=raiz)
    vistos = set()
    for i, e in enumerate(entradas, 1):
        n = f"{ARCHIVO} entrada {i} ({e.get('id')})"
        if not re.fullmatch(r"[a-z0-9-]+", e.get("id") or ""):
            errores.append(f"{n}: id inválido")
        if e.get("id") in vistos:
            errores.append(f"{n}: id repetido")
        vistos.add(e.get("id"))
        for k in ("disparadores", "agregar"):
            v = e.get(k)
            if not isinstance(v, list) or not v or any(not isinstance(x, str) or not x.strip() for x in v):
                errores.append(f"{n}: {k} debe ser una lista de textos no vacía")
        if len(e.get("nota") or "") < 20:
            errores.append(f"{n}: falta la nota (por qué existe la entrada)")
        for s in e.get("sustituir") or []:
            if len(_tokens(s)) != 1:
                errores.append(f"{n}: sustituir debe llevar palabras sueltas ({s!r})")
        if "relacionar" in e and not isinstance(e["relacionar"], bool):
            errores.append(f"{n}: relacionar debe ser true o false")
        # los disparadores no deben ser tan genéricos que se activen con casi cualquier consulta
        for t in e.get("disparadores") or []:
            if len(re.sub(r"[^a-z0-9]", "", _plano(t))) < 3:
                errores.append(f"{n}: disparador demasiado corto ({t!r})")
        arts = e.get("articulos")
        if not arts:
            errores.append(f"{n}: falta articulos (al menos uno con evidencia)")
            continue
        for a in arts:
            ley, art, evid = a.get("ley"), a.get("articulo"), a.get("evidencia")
            if not (ley and art and evid):
                errores.append(f"{n}: cada artículo lleva ley, articulo y evidencia")
                continue
            ficha = store.obtener_articulo(ley, art, anio=anio, raiz=raiz)
            if not ficha:
                errores.append(f"{n}: {ley} art. {art} no existe en leyes/{anio}")
            elif ficha.get("estatus") != "vigente":
                errores.append(f"{n}: {ley} art. {art} no está vigente")
            elif _plano(evid) not in _plano(ficha["texto"]):
                errores.append(f"{n}: la evidencia {evid!r} no aparece en {ley} art. {art}")
    if len(entradas) < 25:
        avisos.append(f"{ARCHIVO}: {len(entradas)} entradas")
    return errores, avisos
