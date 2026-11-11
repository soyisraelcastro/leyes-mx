"""Pipeline: descargar PDF -> texto -> articulos -> archivos .md + _indice.md + _meta.json + transitorios.md"""
import hashlib
import json
import re
import shutil
import urllib.request
from datetime import date
from pathlib import Path

from . import extraer, tablas as _tablas
from .ids import nombre_archivo, clave_orden, partes_id

RAIZ = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; leyes-mx/0.1; +https://github.com/ )"


def cargar_config(ruta=None):
    return json.loads(Path(ruta or RAIZ / "fuentes.json").read_text(encoding="utf-8"))


def config_ley(sigla, cfg=None):
    cfg = cfg or cargar_config()
    for l in cfg["leyes"]:
        if l["sigla"].upper() == sigla.upper():
            return l
    raise KeyError(f"ley no configurada: {sigla}")


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def descargar(url, destino):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        datos = r.read()
    if not datos.startswith(b"%PDF"):
        raise RuntimeError(f"la descarga de {url} no es un PDF")
    tmp = destino.with_suffix(".tmp")
    tmp.write_bytes(datos)
    tmp.replace(destino)
    return destino


def _yaml(v):
    return json.dumps(v, ensure_ascii=False)


def front_matter(campos):
    return "---\n" + "".join(f"{k}: {_yaml(v)}\n" for k, v in campos.items()) + "---\n"


def construir(ley, pdf, anio, destino_raiz=None, fecha_descarga=None, escribir=True):
    """Extrae el PDF y escribe leyes/<anio>/<sigla>/. Devuelve dict con resumen (para validar/reportar)."""
    sigla = ley["sigla"]
    destino_raiz = Path(destino_raiz or RAIZ / "leyes")
    fecha_descarga = fecha_descarga or date.today().isoformat()
    texto = extraer.pdf_a_texto(pdf, layout=True)
    ultima = extraer.fecha_ultima_reforma(texto)
    sha = sha256_archivo(pdf)
    d = extraer.dividir(texto)
    arts = d["articulos"]

    dest = destino_raiz / str(anio) / sigla.upper()
    comunes = {
        "ley": sigla.upper(), "nombre_ley": ley["nombre"], "vigencia_anio": anio,
        "ultima_reforma_dof": ultima, "fuente_url": ley["url"], "fecha_descarga": fecha_descarga,
    }
    resumen = {"sigla": sigla.upper(), "n": len(arts), "ultima_reforma_dof": ultima, "sha256": sha, "archivos": {}}
    if escribir:
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
    datos_tablas, carpeta_tablas = _tablas.cargar(sigla, anio)
    indice = []
    for a in arts:
        cuerpo = extraer.formatear(a.lineas)
        cuerpo, tablas_puestas = _tablas.inyectar(a.id, cuerpo, datos_tablas)
        cuerpo, formulas_puestas = _tablas.aplicar_formulas(a.id, cuerpo, datos_tablas)
        estatus = extraer.estatus_de(cuerpo)
        fm = dict(comunes)
        fm["articulo"] = a.id
        fm["estatus"] = estatus
        fm["sha256_fuente"] = sha
        if a.ubicacion:
            fm["ubicacion"] = a.ubicacion
        if tablas_puestas:
            fm["tablas_transcritas"] = tablas_puestas
        if formulas_puestas:
            fm["formulas_latex"] = formulas_puestas
        # advertencias con "en_archivo": true se escriben también dentro del artículo (visibles para un RAG que lee el .md)
        avisos = "".join(f"> ADVERTENCIA: {adv['texto']}\n\n" for adv in ley.get("advertencias", [])
                         if adv.get("en_archivo") and a.id in adv.get("articulos", []))
        md = front_matter(fm) + f"\n# Artículo {a.id}\n\n{avisos}{cuerpo}\n"
        if a.notas:
            md += "\n## Notas de reforma (margen del PDF)\n\n" + "\n".join(f"- {n}" for n in a.notas) + "\n"
        nombre = nombre_archivo(a.id)
        resumen["archivos"][a.id] = {"archivo": nombre, "caracteres": len(cuerpo), "estatus": estatus}
        indice.append((a.id, nombre, estatus, cuerpo))
        if escribir:
            (dest / nombre).write_text(md, encoding="utf-8")

    # transitorios
    bloques = extraer.trocear_transitorios(d["transitorios"])
    if escribir:
        t = [front_matter({**comunes, "tipo": "transitorios", "estatus": "vigente", "sha256_fuente": sha}),
             f"\n# Transitorios de {ley['nombre']} ({sigla.upper()})\n\n",
             "> Texto tal cual del PDF de la Cámara de Diputados: transitorios del decreto original y de los decretos de reforma. "
             "Muchos transitorios ya agotaron sus efectos; verificar siempre su vigencia.\n"]
        colocadas = set()
        for titulo, lineas in bloques:
            cuerpo = extraer.formatear(lineas)
            cuerpo, puestas = _tablas.inyectar("transitorios", cuerpo, datos_tablas, estricto=False, excluir=colocadas)
            colocadas.update(puestas)
            if cuerpo.strip():
                t.append(f"\n## {titulo}\n\n{cuerpo}\n")
        t.append(_tablas.bloque_transitorios(datos_tablas, colocadas))
        (dest / "transitorios.md").write_text("".join(t), encoding="utf-8")
        _tablas.copiar_imagenes(datos_tablas, carpeta_tablas, dest)
    resumen["decretos_transitorios"] = len(bloques)

    # indice
    if escribir:
        filas = [f"# Índice de {ley['nombre']} ({sigla.upper()}), vigencia {anio}\n",
                 f"Última reforma publicada en el DOF: {ultima}. {len(arts)} artículos. Fuente: {ley['url']}\n",
                 "| Artículo | Archivo | Estatus | Inicio del texto |", "|---|---|---|---|"]
        for id_, nombre, est, cuerpo in indice:
            ini = re.sub(r"\s+", " ", cuerpo)[:90].replace("|", "/")
            filas.append(f"| {id_} | [{nombre}]({nombre}) | {est} | {ini} |")
        filas.append(f"\n[Transitorios](transitorios.md)\n")
        (dest / "_indice.md").write_text("\n".join(filas), encoding="utf-8")
        meta = {
            "sigla": sigla.upper(), "nombre_oficial": ley["nombre"], "tipo": ley.get("tipo"),
            "fuente_url": ley["url"], "ultima_reforma_dof": ultima, "fecha_descarga": fecha_descarga,
            "sha256_pdf": sha, "articulos_extraidos": len(arts),
            "ultimo_articulo_numerico": max(partes_id(a.id)[0] for a in arts),
            "vigencia_anio": anio, "estatus": "vigente",
            "decretos_con_transitorios": len(bloques),
            "advertencias": ley.get("advertencias", []),
        }
        (dest / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resumen["destino"] = str(dest)
    return resumen
