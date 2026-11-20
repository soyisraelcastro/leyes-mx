"""Consolidación de un ordenamiento que la Cámara de Diputados no publica como texto vigente compilado.

Caso: el Reglamento de Inscripción, Pago de Aportaciones y Entero de Descuentos al INFONAVIT (RIPAED). La Cámara
solo tiene, en su sección de normas, el texto original (DOF 10-02-2012) y el decreto de reforma (DOF 28-09-2017) por
separado; no hay PDF "TEXTO VIGENTE" que el pipeline pueda leer. Aquí se arma el texto vigente a partir de las dos
publicaciones del DOF (HTML de dof.gob.mx), sin escribir una sola palabra a mano:

1. `parrafos_dof` saca los párrafos de la nota del DOF (y vuelve a unir los que el DOF parte por salto de página).
2. `bloques` corta el cuerpo en artículos (unidades = párrafos, fracciones e incisos).
3. `aplicar_reforma` aplica el decreto: un artículo del decreto sin "..." sustituye al original completo; con "...",
   cada "..." conserva la unidad original que le toca y el texto nuevo sustituye o se adiciona según el mapa
   `consolidacion/<SIGLA>.json`. El mapa solo dice A QUÉ unidad va cada texto nuevo (índice o "+"); el texto sale
   siempre del DOF. Las comprobaciones (etiquetas de fracción iguales, orden, todo el decreto usado, artículos del
   decreto = artículos que enumera su ARTÍCULO ÚNICO) hacen que un mapa mal hecho falle en lugar de pasar en silencio.
4. `texto_consolidado` emite un texto con el mismo formato que el pipeline espera de pdftotext (párrafos separados
   por renglón en blanco, notas "... reformado DOF dd-mm-aaaa" en renglón propio, transitorios por decreto), que
   `pipeline.construir(..., texto=...)` procesa igual que una ley de la Cámara.

Ver docs/pipeline.md, "Ordenamientos sin texto compilado de la Cámara".
"""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

CLASES_PARRAFO = {"Texto", "ANOTACION", "Titulo_1", "Titulo_2"}
RE_ART = re.compile(r"^ART[ÍI]CULO (\d+)\.\s*")
RE_ESTRUCT = re.compile(r"^(?:CAP[ÍI]TULO|Cap[íi]tulo|SECCI[ÓO]N|Secci[óo]n|T[ÍI]TULO|T[íi]tulo)\s+[IVXLC\d]+\b")
RE_ETIQ = re.compile(r"^([IVXLC]+\.|[a-z]\))\s")
_ETIQ = r"(?:[IVXLC]+\.|[a-z]\))"
RE_ELISION = re.compile(r"^(?:ART[ÍI]CULO \d+\.\s*)?(?:(" + _ETIQ + r")(?:\s+a\s+(" + _ETIQ + r"))?\s*)?\.\.\.$")
ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pars = []  # [texto, empieza_pagina]
        self.cur = None
        self.tag = None
        self.depth = 0
        self.pagina_nueva = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.cur is None:
            if a.get("class") in CLASES_PARRAFO:
                self.cur, self.tag, self.depth = [], tag, 1
            elif tag == "div" and a.get("style") == "":
                self.pagina_nueva = True  # el DOF envuelve cada página en <div style= '' >
            return
        if tag == self.tag:
            self.depth += 1
        if tag == "br":
            self.cur.append(" ")

    def handle_startendtag(self, tag, attrs):
        if self.cur is not None and tag == "br":
            self.cur.append(" ")

    def handle_endtag(self, tag):
        if self.cur is not None and tag == self.tag:
            self.depth -= 1
            if self.depth == 0:
                t = re.sub(r"\s+", " ", "".join(self.cur).replace("\xa0", " ")).strip().replace("…", "...")
                if t:
                    self.pars.append([t, self.pagina_nueva])
                    self.pagina_nueva = False
                self.cur = None

    def handle_data(self, d):
        if self.cur is not None:
            self.cur.append(d)


def parrafos_dof(html):
    """Párrafos de una nota de dof.gob.mx. Un párrafo partido por el salto de página (el anterior no termina en . ; :
    y el siguiente abre la página) se vuelve a unir."""
    p = _Parser()
    p.feed(html)
    res = []
    for t, pag in p.pars:
        if (res and pag and not re.search(r"[.;:]$", res[-1]) and not RE_ETIQ.match(t) and not RE_ART.match(t)
                and not RE_ESTRUCT.match(res[-1]) and not RE_ESTRUCT.match(t)):
            res[-1] += " " + t
        else:
            res.append(t)
    return res


def _es_estructura(pars, i):
    """El párrafo i es un encabezado (Capítulo/Sección) o el nombre que lo sigue."""
    return bool(RE_ESTRUCT.match(pars[i])) or (i > 0 and bool(RE_ESTRUCT.match(pars[i - 1])) and not RE_ART.match(pars[i]))


def bloques(pars):
    """[(tipo, valor)] en orden: ("estructura", texto) o ("articulo", (id, [unidades]))."""
    out = []
    for i, t in enumerate(pars):
        m = RE_ART.match(t)
        if m:
            out.append(["articulo", (m.group(1), [t])])
        elif _es_estructura(pars, i):
            out.append(["estructura", t])
        elif out and out[-1][0] == "articulo":
            out[-1][1][1].append(t)
        else:
            raise ValueError(f"párrafo fuera de un artículo: {t[:80]!r}")
    return out


def partes(pars, fin_preambulo):
    """Divide los párrafos de una publicación: preámbulo (hasta el primer párrafo que cumple fin_preambulo),
    cuerpo (hasta TRANSITORIOS) y transitorios."""
    ini = next(i for i, t in enumerate(pars) if fin_preambulo(t))
    fin = next(i for i in range(ini, len(pars)) if pars[i].strip().upper() == "TRANSITORIOS")
    return pars[:ini], pars[ini:fin], pars[fin + 1:]


def _romano(s):
    n, prev = 0, 0
    for ch in reversed(s):
        v = ROMANOS[ch]
        n, prev = (n - v, prev) if v < prev else (n + v, v)
    return n


def _rango(etq):
    """Clave de orden de una etiqueta ('IV.' -> ('R', 4), 'c)' -> ('L', 3))."""
    return ("R", _romano(etq[:-1])) if etq.endswith(".") else ("L", ord(etq[0]) - 96)


def etiqueta(u):
    m = RE_ETIQ.match(u)
    return m.group(1) if m else None


def aplicar_reforma(original, decreto, mapa, fecha):
    """original/decreto: salida de bloques(). mapa: {id: [destino por cada texto nuevo]}; destino = índice de la unidad
    original que sustituye, "+" (adición en ese punto) o "+fin" (adición al final del artículo). fecha: 'dd-mm-aaaa' para las notas.
    Devuelve (bloques consolidados, {id: [notas]}, informe)."""
    arts = {v[0]: list(v[1]) for t, v in original if t == "articulo"}
    orden = [(t, v[0] if t == "articulo" else v) for t, v in original]
    notas, informe = {}, []
    estructura_pendiente = []
    for tipo, val in decreto:
        if tipo == "estructura":
            estructura_pendiente.append(val)
            continue
        id_, uds = val
        elisiones = [RE_ELISION.match(u) for u in uds]
        if id_ not in arts:  # artículo adicionado
            if any(elisiones):
                raise ValueError(f"art. {id_}: es nuevo y trae '...'")
            pos = max(i for i, (t, v) in enumerate(orden) if t == "articulo" and int(v) < int(id_)) + 1
            for k, e in enumerate(estructura_pendiente):
                orden.insert(pos + k, ("estructura", e))
            pos += len(estructura_pendiente)
            orden.insert(pos, ("articulo", id_))
            arts[id_] = uds
            notas[id_] = [f"Artículo adicionado DOF {fecha}"]
            informe.append(f"{id_}: adicionado")
            estructura_pendiente = []
            continue
        if estructura_pendiente:
            raise ValueError(f"encabezado {estructura_pendiente} antes del art. {id_}, que ya existía: no soportado")
        if not any(elisiones):
            if id_ in mapa:
                raise ValueError(f"art. {id_}: se sustituye completo (sin '...') pero tiene entrada en el mapa")
            arts[id_] = uds
            der = len(uds) == 1 and re.match(r"^ART[ÍI]CULO \d+\.\s*Derogado\.?$", uds[0])
            notas[id_] = [f"Artículo {'derogado' if der else 'reformado'} DOF {fecha}"]
            informe.append(f"{id_}: {'derogado' if der else 'sustituido completo'}")
            continue
        if id_ not in mapa and not all(elisiones):
            raise ValueError(f"art. {id_}: el decreto trae '...' y no hay entrada en el mapa")
        orig = arts[id_]
        destinos = list(mapa.get(id_, []))
        res, ns, p = [], [], 0
        for u, el in zip(uds, elisiones):
            if el:
                ini, fin = el.group(1), el.group(2)
                if ini and fin:  # rango "I. a III. ..." o "a) a c) ..."
                    if etiqueta(orig[p]) != ini:
                        raise ValueError(f"art. {id_}: el rango {ini} a {fin} no empieza en la unidad {p} ({orig[p][:40]!r})")
                    tipo_r, hasta = _rango(fin)
                    while p < len(orig):
                        e = etiqueta(orig[p])
                        if e and _rango(e)[0] == tipo_r and _rango(e)[1] > hasta:
                            break
                        if e and _rango(e)[0] != tipo_r and tipo_r == "L":  # un inciso no se extiende a la fracción siguiente
                            break
                        res.append(orig[p]); p += 1
                    continue
                if p >= len(orig):
                    raise ValueError(f"art. {id_}: '...' de más (el original tiene {len(orig)} unidades)")
                if ini and etiqueta(orig[p]) != ini:
                    raise ValueError(f"art. {id_}: '{u}' cae en la unidad {p} con etiqueta {etiqueta(orig[p])}")
                res.append(orig[p]); p += 1
                continue
            if not destinos:
                raise ValueError(f"art. {id_}: el mapa tiene menos destinos que textos nuevos")
            d = destinos.pop(0)
            if d == "+fin":  # adición al final del artículo (p. ej. "se adiciona un último párrafo" tras fracciones que el decreto no repite)
                res.extend(orig[p:]); p = len(orig)
                d = "+"
            if d == "+":
                res.append(u)
                ns.append(f"{_que(u)} adicionad{_gen(u)} DOF {fecha}")
                continue
            if not isinstance(d, int) or d < p or d >= len(orig):
                raise ValueError(f"art. {id_}: destino {d!r} inválido (posición actual {p}, {len(orig)} unidades)")
            res.extend(orig[p:d])  # lo que el decreto no menciona queda igual
            if etiqueta(u) != etiqueta(orig[d]):
                raise ValueError(f"art. {id_}: el texto nuevo {etiqueta(u)!r} sustituye a la unidad {d} con etiqueta {etiqueta(orig[d])!r}")
            if (d == 0) != bool(RE_ART.match(u)):
                raise ValueError(f"art. {id_}: el encabezado 'ARTÍCULO' solo puede sustituir a la unidad 0")
            res.append(u)
            ns.append(f"{_que(u)} reformad{_gen(u)} DOF {fecha}")
            p = d + 1
        if destinos:
            raise ValueError(f"art. {id_}: sobran destinos en el mapa: {destinos}")
        res.extend(orig[p:])
        arts[id_] = res
        notas[id_] = ns
        informe.append(f"{id_}: {len(ns)} cambio(s) ({'; '.join(ns)})")
    if estructura_pendiente:
        raise ValueError(f"encabezado sin artículo: {estructura_pendiente}")
    out = [("articulo", (v, arts[v])) if t == "articulo" else ("estructura", v) for t, v in orden]
    return out, notas, informe


def _que(u):
    """Qué unidad es, como lo anota la Cámara al margen: Fracción, Inciso o Párrafo."""
    e = etiqueta(u)
    if e:
        return "Fracción" if e.endswith(".") else "Inciso"
    return "Párrafo"


def _gen(u):
    return "a" if _que(u) == "Fracción" else "o"


def articulos_del_decreto(articulo_unico):
    """Números de artículo que enumera el ARTÍCULO ÚNICO de un decreto de reforma. Fracciones (romanos), incisos
    (letras) y párrafos (ordinales en palabra) no traen cifras arábigas; se descartan las referencias tipo 17-D."""
    t = re.sub(r"\b\d+-[A-Z]\b", "", articulo_unico)
    return {n for n in re.findall(r"\b(\d+)\b", t)}


def texto_consolidado(cfg, fuentes_html):
    """cfg: entrada 'consolidacion' de fuentes.json + mapa; fuentes_html: {url: html}. Devuelve (texto, informe)."""
    orig_cfg = cfg["original"]
    pars = parrafos_dof(fuentes_html[orig_cfg["url"]])
    _, cuerpo, trans_orig = partes(pars, lambda t: bool(RE_ART.match(t)) and RE_ART.match(t).group(1) == "1")
    # el título y el nombre de capítulo que preceden al art. 1 forman parte del cuerpo
    actual = bloques(_con_estructura_previa(pars, cuerpo))
    informe, notas_tot, decretos = [], {}, []
    for ref in cfg["reformas"]:
        pd = parrafos_dof(fuentes_html[ref["url"]])
        unico = next(t for t in pd if t.startswith("ARTÍCULO ÚNICO"))
        _, c, tr = partes(pd, lambda t: bool(RE_ART.match(t)))
        dec = bloques(c)
        ids_dec = {v[0] for t, v in dec if t == "articulo"}
        enumerados = articulos_del_decreto(unico)
        if ids_dec != enumerados:
            raise ValueError(f"decreto {ref['fecha_dof']}: artículos del texto {sorted(ids_dec, key=int)} "
                             f"!= artículos del ARTÍCULO ÚNICO {sorted(enumerados, key=int)}")
        fecha = "-".join(reversed(ref["fecha_dof"].split("-")))
        actual, ns, inf = aplicar_reforma(actual, dec, cfg["mapas"].get(ref["fecha_dof"], {}), fecha)
        for k, v in ns.items():
            notas_tot.setdefault(k, []).extend(v)
        informe += [f"DOF {fecha} art. {x}" for x in inf]
        decretos.append((ref, unico, tr))
    lineas = [cfg["titulo"], "", f"Texto vigente consolidado por leyes-mx desde el DOF. {cfg['nota_texto']}", ""]
    for k, (t, v) in enumerate(actual):
        if t == "estructura":  # encabezado y nombre en renglones seguidos, como en el PDF de la Cámara
            lineas += [v] + ([""] if k + 1 < len(actual) and actual[k + 1][0] != "estructura" else [])
            continue
        id_, uds = v
        for u in uds:
            lineas += [u, ""]
        if notas_tot.get(id_):
            lineas += notas_tot[id_] + [""]
    lineas += ["TRANSITORIOS", ""] + [x for t in _sin_firma(trans_orig) for x in (t, "")]
    for ref, unico, tr in decretos:
        lineas += [f"DECRETO {ref['titulo']}", f"Publicado en el Diario Oficial de la Federación el {ref['fecha_texto']}", ""]
        lineas += [x for t in _sin_firma(tr) for x in (t, "")]
    return "\n".join(lineas) + "\n", informe


def _con_estructura_previa(pars, cuerpo):
    i = pars.index(cuerpo[0])
    previos = []
    j = i - 1
    while j >= 0 and _es_estructura(pars, j):
        previos.insert(0, pars[j]); j -= 1
    return previos + cuerpo


def _sin_firma(trans):
    """Quita del final las líneas de firma ('Dado en la Residencia del Poder Ejecutivo...' y su continuación)."""
    for k, t in enumerate(trans):
        if t.startswith("Dado en la Residencia"):
            return trans[:k]
    return trans


def sha256_fuentes(fuentes_html, urls):
    h = hashlib.sha256()
    for u in urls:
        h.update(hashlib.sha256(fuentes_html[u].encode("utf-8")).hexdigest().encode())
    return h.hexdigest()


def cargar_mapa(raiz, sigla):
    return json.loads((Path(raiz) / "consolidacion" / f"{sigla}.json").read_text(encoding="utf-8"))
