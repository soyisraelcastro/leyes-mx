"""Subsidio para el empleo (SPE): decretos del DOF y valor de la UMA, a decretos/<año>/spe/.

El texto sale del DOF (nota_detalle.php) tal como se publicó; nada se escribe a mano. El SPE no es una
tarifa (no entra en rmf/<año>/anexo-8/): desde el decreto del 01-05-2024 es una cuota mensual igual a un
porcentaje del valor mensual de la UMA, con un tope de ingresos mensuales. Se guardan:

  decreto-2024-05-01.md          "Decreto que otorga el subsidio para el empleo" (DOF 01-05-2024), completo
  modificacion-2024-12-31.md     reforma del Artículo Segundo (DOF 31-12-2024), completa
  modificacion-2025-12-31.md     reforma del Artículo Segundo (DOF 31-12-2025), completa: la que rige en 2026
  uma-2025.md, uma-2026.md       valor de la UMA que publica el INEGI en el DOF (10-01-2025 y 09-01-2026)
  vigente-2026.md                texto consolidado: el decreto de 2024 con los párrafos 1, 3, 4 y 5 del
                                 Artículo Segundo sustituidos por los del decreto de 2025 (armado por este
                                 proyecto, nunca editado a mano; no es una publicación oficial)
  _meta.json, _indice.md         parámetros, sha256 de cada texto y avisos

Con cualquier discrepancia en los controles, la extracción falla sin escribir (ver scripts/extraer_spe.py).
"""
import hashlib
import html
import json
import os
import re
import subprocess
import time
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RAIZ = Path(os.environ.get("LEYES_MX_RAIZ") or Path(__file__).resolve().parent.parent)
ANIO = 2026
DIRECTORIO = f"decretos/{ANIO}/spe"
URL_NOTA = "https://dof.gob.mx/nota_detalle.php?codigo={codigo}&fecha={fecha}"

# archivo -> (código de nota del DOF, fecha DOF dd/mm/aaaa, tipo, estatus, qué es)
FUENTES = {
    "decreto-2024-05-01": ("5725287", "01/05/2024", "decreto",
                           "vigente, con los párrafos 1, 3, 4 y 5 del Artículo Segundo reformados",
                           "Decreto que otorga el subsidio para el empleo (DOF 01-05-2024)"),
    "modificacion-2024-12-31": ("5746529", "31/12/2024", "modificacion",
                                "superada: el decreto de 31-12-2025 reforma los mismos párrafos desde el 01-01-2026",
                                "Decreto por el que se modifica el diverso que otorga el subsidio para el empleo (DOF 31-12-2024, vigente 2025)"),
    "modificacion-2025-12-31": ("5777649", "31/12/2025", "modificacion",
                                "vigente desde el 01-01-2026",
                                "Decreto por el que se modifica el diverso que otorga el subsidio para el empleo (DOF 31-12-2025, vigente 2026)"),
    "uma-2025": ("5746930", "10/01/2025", "uma", "vigente del 01-02-2025 al 31-01-2026 (aplica a enero de 2026)",
                 "Valor de la Unidad de Medida y Actualización 2025 (INEGI, DOF 10-01-2025)"),
    "uma-2026": ("5778072", "09/01/2026", "uma", "vigente desde el 01-02-2026",
                 "Valor de la Unidad de Medida y Actualización 2026 (INEGI, DOF 09-01-2026)"),
}
CONSOLIDADO = "vigente-2026"
AVISO = ("Texto informativo copiado del DOF; no sustituye al DOF. La fuente oficial prevalece. Los decretos se citan por "
         "su fecha de publicación; el valor de la UMA lo publica el INEGI cada año.")
AVISO_VIGENTE = ("Texto consolidado por leyes-mx a partir de dos publicaciones del DOF (decreto del 01-05-2024 y su reforma del "
                 "31-12-2025): no es una publicación oficial ni está en el DOF como tal. Para citar, usa cada decreto.")

# Valores que se verifican contra el texto (y que el servidor MCP entrega como estructurados).
PARAMETROS_2026 = {
    "limite_ingresos_mensuales": "11492.66",
    "porcentaje_uma_febrero_a_diciembre": "15.02",
    "porcentaje_uma_enero": "15.59",
    "divisor_periodos_menores_a_un_mes": "30.4",
    "vigencia_desde": "2026-01-01",
}
UMA = {2025: {"diario": "113.14", "mensual": "3439.46", "anual": "41273.52", "vigente_desde": "2025-02-01", "archivo": "uma-2025"},
       2026: {"diario": "117.31", "mensual": "3566.22", "anual": "42794.64", "vigente_desde": "2026-02-01", "archivo": "uma-2026"}}


def sha256_texto(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def dec(x):
    return Decimal(str(x))


def peso(x):
    return f"{Decimal(x):,.2f}"


def cent(x):
    return dec(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------------------------------- descarga

def descargar_nota(codigo, fecha):
    """Texto plano de una nota del DOF (sin menús ni indicadores): (url, texto)."""
    url = URL_NOTA.format(codigo=codigo, fecha=fecha)
    t = ""
    for intento in range(4):  # el DOF a veces responde con una página de error; se reintenta
        raw = subprocess.run(["curl", "-sL", "--max-time", "120", "-A", "Mozilla/5.0", url], capture_output=True, check=True).stdout
        try:
            t = raw.decode("utf-8")
        except UnicodeDecodeError:
            t = raw.decode("latin-1")
        if "DOF: " in t and "En el documento que usted" in t:
            break
        time.sleep(3 * (intento + 1))
    t = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", t)
    t = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"\n\s*\n+", "\n", t)
    if "DOF: " not in t or "En el documento que usted" not in t:
        raise ValueError(f"nota {codigo}: la página del DOF no tiene la forma esperada")
    return url, t[t.index("DOF: "):t.index("En el documento que usted")]


def partir_nota(texto):
    """(fecha_dof, titulo, parrafos, notas): el primer renglón trae el título dos veces y 'Al margen'."""
    lineas = [x.strip() for x in texto.split("\n") if x.strip()]
    m = re.match(r"DOF:\s*(\d\d/\d\d/\d{4})", lineas[0])
    if not m:
        raise ValueError("no se encontró la fecha DOF")
    m2 = re.match(r"^(.+?)\s{2,}(.+?\.)\s{2,}(Al margen.*)$", lineas[1])
    if not m2:
        raise ValueError("no se pudo separar el título del primer párrafo")
    titulo, cuerpo = m2.group(2), [m2.group(3)] + lineas[2:]
    notas = [x for x in cuerpo if re.match(r"^\d+\s+https?://", x)]
    parrafos = [re.sub(r"[ \t]+", " ", x) for x in cuerpo if x not in notas]
    return m.group(1), titulo, parrafos, [re.sub(r"\s+", " ", x) for x in notas]


# ------------------------------------------------------------------------------------------- consolidación

def _indice(parrafos, prefijo, desde=0):
    for i in range(desde, len(parrafos)):
        if parrafos[i].startswith(prefijo):
            return i
    raise ValueError(f"no se encontró el párrafo que empieza con {prefijo!r}")


def consolidar(d2024, d2025):
    """Decreto 2024 con los párrafos 1, 3, 4 y 5 del Artículo Segundo sustituidos por los del decreto de 2025.
    Devuelve (lista de secciones [(titulo, [parrafos])], errores)."""
    errores = []
    a = _indice(d2024, "Artículo Segundo.")
    b = _indice(d2024, "Artículo Tercero.")
    seg = d2024[a:b]
    if len(seg) != 7:
        errores.append(f"el Artículo Segundo de 2024 tiene {len(seg)} párrafos y se esperaban 7")
        return [], errores
    r = _indice(d2025, "Artículo Segundo.")
    t = _indice(d2025, "TRANSITORIOS", r)
    nuevos = [p.rstrip('"').strip() for p in d2025[r:t] if p.strip(' "') not in ("...", "…")]
    nuevos = [p for p in nuevos if p]
    if len(nuevos) != 4:
        errores.append(f"la reforma de 2025 trae {len(nuevos)} párrafos sustitutos y se esperaban 4 (párrafos 1, 3, 4 y 5)")
        return [], errores
    final = [nuevos[0], seg[1], nuevos[1], nuevos[2], nuevos[3], seg[5], seg[6]]
    primero = _indice(d2024, "Artículo Primero.")
    trans24 = _indice(d2024, "TRANSITORIOS")
    firma24 = _indice(d2024, "Dado en la residencia")
    trans25 = _indice(d2025, "TRANSITORIOS")
    firma25 = _indice(d2025, "Dado en la residencia")
    secciones = [
        ("Artículo Primero (decreto del 01-05-2024, sin cambios)", d2024[primero:primero + 1]),
        ("Artículo Segundo (decreto del 01-05-2024; párrafos 1, 3, 4 y 5 según el decreto del 31-12-2025, vigente desde el 01-01-2026)", final),
        ("Artículos Tercero a Quinto (decreto del 01-05-2024, sin cambios)", d2024[b:trans24]),
        ("Transitorios del decreto del 01-05-2024", d2024[trans24 + 1:firma24]),
        ("Transitorios del decreto del 31-12-2025 (rigen el Artículo Segundo en 2026)", d2025[trans25 + 1:firma25]),
    ]
    return secciones, errores


def texto_consolidado(secciones):
    cab = ["# Subsidio para el empleo: texto vigente en 2026 (consolidado)", "", f"> {AVISO_VIGENTE}", "",
           "El Artículo Segundo, párrafos 2, 6 y 7, queda como en el decreto de 2024 (la reforma de 2025 los marca con \"...\"). "
           "La modificación del 31-12-2024 (vigente en 2025, con la regla de enero de 2025) quedó sustituida por la de 2025 en los mismos párrafos.", ""]
    for tit, ps in secciones:
        cab += [f"## {tit}", ""] + [p + "\n" for p in ps]
    return "\n".join(cab).rstrip() + "\n"


# ------------------------------------------------------------------------------------------------- controles

def verificar(textos, consolidado_secciones):
    """textos: {clave: (fecha_dof, titulo, parrafos, notas)}. Devuelve la lista de errores."""
    err = []
    m25 = " ".join(textos["modificacion-2025-12-31"][2])
    p = PARAMETROS_2026
    if m25.count(f"{p['porcentaje_uma_febrero_a_diciembre']}%") < 5:  # 4 párrafos + el transitorio
        err.append("el decreto de 2025 debería citar 15.02% en los 4 párrafos del Artículo Segundo y en el transitorio segundo")
    if f"{p['porcentaje_uma_enero']}%" not in m25:
        err.append("el decreto de 2025 no cita 15.59% (enero de 2026)")
    if "$11,492.66" not in m25 or "once mil cuatrocientos noventa y dos pesos 66/100" not in m25:
        err.append("el decreto de 2025 no trae el límite de $11,492.66 en cifra y letra")
    if "entrará en vigor el 1 de enero de 2026" not in m25:
        err.append("el decreto de 2025 no dice que entra en vigor el 1 de enero de 2026")
    if "30.4" in m25 and p["divisor_periodos_menores_a_un_mes"] != "30.4":
        err.append("divisor inconsistente")
    if "30.4" not in m25:
        err.append("el decreto de 2025 no cita el divisor 30.4")
    for k, clave in (("2025", "uma-2025"), ("2026", "uma-2026")):
        u = UMA[int(k)]
        t = " ".join(textos[clave][2])
        for campo in ("diario", "mensual", "anual"):
            if f"${peso(u[campo])}" not in t:
                err.append(f"UMA {k}: el DOF no trae el valor {campo} ${peso(u[campo])}")
        if cent(dec(u["diario"]) * dec("30.4")) != dec(u["mensual"]):
            err.append(f"UMA {k}: diario por 30.4 no da el mensual")
        if cent(dec(u["mensual"]) * 12) != dec(u["anual"]):
            err.append(f"UMA {k}: mensual por 12 no da el anual")
    if consolidado_secciones:
        seg = " ".join(consolidado_secciones[1][1])
        if "11.82%" in seg or "13.8%" in seg or "9,081" in seg or "10,171" in seg:
            err.append("el Artículo Segundo consolidado conserva cifras de 2024 o 2025")
        if seg.count("15.02%") != 4:
            err.append("el Artículo Segundo consolidado debería citar 15.02% cuatro veces")
    return err


def calculo_derivado():
    """Importe mensual máximo, calculado por este proyecto (el decreto no fija redondeo ni cita este monto)."""
    ene = cent(dec(UMA[2025]["mensual"]) * dec(PARAMETROS_2026["porcentaje_uma_enero"]) / 100)
    feb = cent(dec(UMA[2026]["mensual"]) * dec(PARAMETROS_2026["porcentaje_uma_febrero_a_diciembre"]) / 100)
    return {
        "aviso": ("Cálculo aritmético de este proyecto, redondeado a centavos (el decreto no fija redondeo); NO es texto del DOF. "
                  "El considerando del decreto de 2025 cita $536.22 para 15.02%."),
        "enero_2026": {"uma_mensual": UMA[2025]["mensual"], "porcentaje": PARAMETROS_2026["porcentaje_uma_enero"], "subsidio_mensual_maximo": str(ene)},
        "febrero_a_diciembre_2026": {"uma_mensual": UMA[2026]["mensual"], "porcentaje": PARAMETROS_2026["porcentaje_uma_febrero_a_diciembre"], "subsidio_mensual_maximo": str(feb)},
    }


# -------------------------------------------------------------------------------------------------- escritura

def _fm(campos):
    out = ["---"]
    for k, v in campos.items():
        out.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    out.append("---")
    return "\n".join(out) + "\n"


def _dof_iso(f):
    d, m, a = f.split("/")
    return f"{a}-{m}-{d}"


def archivo_decreto(clave, url, fecha_dof, titulo, parrafos, notas, hoy):
    codigo, fecha, tipo, estatus, desc = FUENTES[clave]
    cuerpo = [f"# {titulo.rstrip('.')}", "", f"> {AVISO}", ""] + [p + "\n" for p in parrafos]
    if notas:
        cuerpo += ["## Notas del DOF", ""] + [f"- {n}" for n in notas] + [""]
    cuerpo_t = "\n".join(cuerpo).rstrip() + "\n"
    fm = _fm({"documento": desc, "id": clave, "tipo": tipo, "titulo": titulo.rstrip("."), "publicado_dof": _dof_iso(fecha_dof),
              "nota_dof": codigo, "fuente_url": url, "fecha_descarga": hoy, "sha256_texto": sha256_texto("\n".join(parrafos)),
              "estatus": estatus, "vigencia_anio": ANIO})
    return fm + "\n" + cuerpo_t, sha256_texto("\n".join(parrafos))


def construir(textos, urls, hoy):
    """textos: {clave: partir_nota(...)}; devuelve ({ruta_relativa: contenido}, errores)."""
    secciones, err = consolidar(textos["decreto-2024-05-01"][2], textos["modificacion-2025-12-31"][2])
    err += verificar(textos, secciones)
    if err:
        return {}, err
    archivos, hashes = {}, {}
    for clave in FUENTES:
        f, t, ps, ns = textos[clave]
        contenido, h = archivo_decreto(clave, urls[clave], f, t, ps, ns, hoy)
        archivos[f"{clave}.md"] = contenido
        hashes[clave] = h
    cons = texto_consolidado(secciones)
    fm = _fm({"documento": "Subsidio para el empleo, texto vigente en 2026 (consolidado por leyes-mx)", "id": CONSOLIDADO, "tipo": "consolidado",
              "titulo": "Decreto que otorga el subsidio para el empleo, con la reforma de 31-12-2025", "vigencia_anio": ANIO,
              "construido_de": ["decreto-2024-05-01", "modificacion-2025-12-31"], "fecha_descarga": hoy,
              "sha256_texto": sha256_texto(cons), "estatus": "vigente", "aviso": AVISO_VIGENTE})
    archivos[f"{CONSOLIDADO}.md"] = fm + "\n" + cons
    meta = {
        "documento": "Subsidio para el empleo (decreto del 01-05-2024 y sus reformas)", "tipo": "decreto_spe", "vigencia_anio": ANIO,
        "estatus": "vigente", "fecha_descarga": hoy, "aviso": AVISO,
        "fundamento": "LISR art. 96 (el subsidio se aplica contra el ISR a cargo); LISR art. 94, primer párrafo y fracción I",
        "parametros_2026": PARAMETROS_2026,
        "uma": {str(a): {k: v for k, v in d.items() if k != "archivo"} | {"fuente_url": urls[d["archivo"]], "fuente_archivo": f"{d['archivo']}.md"} for a, d in UMA.items()},
        "calculo_derivado": calculo_derivado(),
        "no_verificado": ["Modificaciones al decreto publicadas después del 31-12-2025: no se encontraron, pero la búsqueda no es exhaustiva; "
                          "revisar el DOF antes de afirmar que no hay."],
        "documentos": [{"id": c, "tipo": FUENTES[c][2], "publicado_dof": _dof_iso(FUENTES[c][1]), "nota_dof": FUENTES[c][0], "fuente_url": urls[c],
                        "sha256_texto": hashes[c], "estatus": FUENTES[c][3]} for c in FUENTES]
                      + [{"id": CONSOLIDADO, "tipo": "consolidado", "sha256_texto": sha256_texto(cons), "estatus": "vigente"}],
    }
    archivos["_meta.json"] = json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    idx = ["# Subsidio para el empleo 2026", "", f"> {AVISO}", "", f"> {AVISO_VIGENTE}", "",
           "Subsidio mensual contra el ISR del art. 96 de la LISR: tope de ingresos mensuales y una cuota igual a un porcentaje del valor "
           "mensual de la UMA. Parámetros 2026 en `_meta.json` (`parametros_2026`).", "", "| Archivo | Qué es | Estatus |", "|---|---|---|"]
    for c, (cod, fe, tipo, est, desc) in FUENTES.items():
        idx.append(f"| [{c}.md]({c}.md) | {desc} | {est} |")
    idx.append(f"| [{CONSOLIDADO}.md]({CONSOLIDADO}.md) | Texto consolidado (armado por este proyecto) | vigente |")
    archivos["_indice.md"] = "\n".join(idx) + "\n"
    return archivos, []


def extraer(destino=None, escribir=True, hoy=None):
    """Descarga las cinco notas, verifica y escribe. Devuelve (errores, archivos)."""
    hoy = hoy or date.today().isoformat()
    textos, urls = {}, {}
    for clave, (codigo, fecha, *_r) in FUENTES.items():
        url, t = descargar_nota(codigo, fecha)
        urls[clave] = url
        textos[clave] = partir_nota(t)
        if _dof_iso(textos[clave][0]) != _dof_iso(fecha):
            return [f"{clave}: la nota dice DOF {textos[clave][0]} y se esperaba {fecha}"], {}
    archivos, err = construir(textos, urls, hoy)
    if err or not escribir:
        return err, archivos
    dest = Path(destino) if destino else RAIZ / DIRECTORIO
    dest.mkdir(parents=True, exist_ok=True)
    for ruta, cont in archivos.items():
        (dest / ruta).write_text(cont, encoding="utf-8")
    return [], archivos


# ------------------------------------------------------------------------------------------------ validación

def _leer(ruta):
    t = ruta.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    fm = {}
    if m:
        for ln in m.group(1).split("\n"):
            k, _, v = ln.partition(": ")
            try:
                fm[k] = json.loads(v)
            except ValueError:
                fm[k] = v
    return fm, t[m.end():] if m else t


def validar(raiz=None):
    """(errores, avisos) sobre decretos/<año>/spe/ ya escrito; no usa la red."""
    raiz = Path(raiz or RAIZ)
    d = raiz / DIRECTORIO
    if not d.is_dir():
        return [], []
    err, avisos = [], []
    meta_p = d / "_meta.json"
    if not meta_p.is_file():
        return ["decretos/spe: falta _meta.json"], []
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    textos = {}
    for clave in FUENTES:
        p = d / f"{clave}.md"
        if not p.is_file():
            err.append(f"decretos/spe: falta {clave}.md")
            continue
        fm, cuerpo = _leer(p)
        parrafos = [x.strip() for x in cuerpo.split("\n") if x.strip()]
        # la verificación del hash se hace sobre los párrafos del DOF, que son lo que guarda el front matter
        ini = next((i for i, x in enumerate(parrafos) if x.startswith("> ")), -1)
        fin = next((i for i, x in enumerate(parrafos) if x == "## Notas del DOF"), len(parrafos))
        ps = parrafos[ini + 1:fin]
        if sha256_texto("\n".join(ps)) != fm.get("sha256_texto"):
            err.append(f"decretos/spe/{clave}.md: el sha256 del texto no coincide con el front matter (¿se editó a mano?)")
        textos[clave] = ("", fm.get("titulo", ""), ps, [])
    if err:
        return err, avisos
    secciones, e2 = consolidar(textos["decreto-2024-05-01"][2], textos["modificacion-2025-12-31"][2])
    err += e2 + verificar(textos, secciones)
    if not err:
        esperado = texto_consolidado(secciones)
        _, cons = _leer(d / f"{CONSOLIDADO}.md") if (d / f"{CONSOLIDADO}.md").is_file() else ({}, "")
        if cons.strip() != esperado.strip():
            err.append(f"decretos/spe/{CONSOLIDADO}.md no es el que resulta de los decretos (regenerar con scripts/extraer_spe.py)")
    if meta.get("parametros_2026") != PARAMETROS_2026:
        err.append("decretos/spe/_meta.json: parametros_2026 no coincide con los verificados contra el decreto")
    if meta.get("calculo_derivado") != calculo_derivado():
        err.append("decretos/spe/_meta.json: calculo_derivado no coincide con el cálculo")
    return err, avisos
