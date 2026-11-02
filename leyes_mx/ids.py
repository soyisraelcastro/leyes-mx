"""Identificadores de articulo: normalizacion y nombres de archivo.

Convencion canonica (ver docs/convencion-nombres.md):
  numero base sin ceros en el id ("28", "113-E", "28-bis", "32-B-bis")
  archivo: art-<numero a 4 digitos>[-<sufijo>...].md  -> art-0028.md, art-0113-E.md, art-0028-bis.md
  letras en MAYUSCULA (A..Z y Ñ, que en el nombre de archivo se escribe NN); palabras multiplicativas en minuscula sin acento (bis, ter, quater...).
"""
import re

PALABRAS = ["bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "nonies", "decies",
            "quintus", "sextus", "septimus", "octavus", "nonus", "decimus", "undecimus", "duodecimus"]
_ACENTOS = str.maketrans("áéíóúü", "aeiouu")


def _palabra(tok):
    t = tok.lower().translate(_ACENTOS)
    return t if t in PALABRAS else None


def normalizar_id(texto):
    """'113 E', '113-e', '28 Bis', '1o.-A', '32-B Bis' -> '113-E', '113-E', '28-bis', '1-A', '32-B-bis'. None si no es valido."""
    if texto is None:
        return None
    s = str(texto).strip()
    s = re.sub(r"^(art[íi]culo|art\.?)\s*", "", s, flags=re.I)
    m = re.match(r"^(\d+)(?!\d)\s*[oº°]?(?![a-zA-Z])\.?(.*)$", s) or re.match(r"^(\d+)(.*)$", s)
    if not m:
        return None
    num = int(m.group(1))
    resto = m.group(2)
    # separar letra pegada al numero ("113E")
    resto = re.sub(r"^([A-Za-zÑñ])$", r"-\1", resto.strip()) if re.fullmatch(r"\s*[A-Za-zÑñ]\s*", resto) else resto
    toks = [t for t in re.split(r"[\s\-\.]+", resto) if t]
    partes = []
    for t in toks:
        p = _palabra(t)
        if p:
            partes.append(p)
        elif re.fullmatch(r"[A-Za-zÑñ]", t):
            partes.append(t.upper())
        else:
            return None
    return "-".join([str(num)] + partes)


def partes_id(id_):
    toks = id_.split("-")  # Ñ es una sola letra
    return int(toks[0]), toks[1:]


def nombre_archivo(id_):
    num, partes = partes_id(id_)
    partes = ["NN" if p == "Ñ" else p for p in partes]  # Ñ -> NN en el nombre de archivo (ASCII)
    return "art-" + "-".join([f"{num:04d}"] + partes) + ".md"


def id_desde_archivo(nombre):
    m = re.fullmatch(r"art-(\d{4})((?:-[A-Za-z]+)*)\.md", nombre)
    if not m:
        return None
    return normalizar_id(str(int(m.group(1))) + m.group(2).replace("-NN", "-Ñ"))


def clave_orden(id_):
    num, partes = partes_id(id_)
    k = []
    for p in partes:
        if p in PALABRAS:
            k.append((1, PALABRAS.index(p)))
        else:
            k.append((0, ord("N") + 0.5 if p == "Ñ" else ord(p)))
    return (num, k)
