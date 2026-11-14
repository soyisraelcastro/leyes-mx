"""Árbol sintético para probar las capas (versiones por herencia). NO es leyes/2027 real: se arma en un directorio temporal.

Ley XLEY, base 2026 (completa) y un texto completo 2027 (`completo`, como lo deja el pipeline) con:
  art. 1     sin cambios (solo cambian los espacios: no cuenta)
  art. 2     sin cambios
  art. 3     modificado
  art. 4     pasa a derogado
  art. 4-F  sin cambios
  art. 4-G  nuevo
Ley YLEY: no cambia en 2027 (la capa 2027 queda solo con _meta.json).
"""
import json
from pathlib import Path

from leyes_mx.ids import nombre_archivo

SHA26, SHA27 = "a" * 64, "b" * 64

TEXTOS_BASE = {
    "1": "Texto del artículo uno. Régimen general.",
    "2": "Texto del artículo dos.\n\nI. Primera fracción.\n\nII. Segunda fracción.",
    "3": "Texto viejo del artículo tres: la tasa es del 30%.",
    "4": "Texto vigente del artículo cuatro sobre deducciones autorizadas.",
    "4-F": "Texto del artículo 4-F.",
}


def _fm(sigla, nombre, anio, id_, estatus, reforma, sha, descarga):
    campos = {"ley": sigla, "nombre_ley": nombre, "vigencia_anio": anio, "ultima_reforma_dof": reforma,
              "fuente_url": f"https://example.com/{sigla}.pdf", "fecha_descarga": descarga, "articulo": id_,
              "estatus": estatus, "sha256_fuente": sha}
    return "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in campos.items()) + "---\n"


def escribir_articulo(dir_, sigla, anio, id_, texto, estatus="vigente", reforma="2024-04-01", sha=SHA26, descarga="2026-11-02", nombre="Ley X"):
    dir_.mkdir(parents=True, exist_ok=True)
    md = _fm(sigla, nombre, anio, id_, estatus, reforma, sha, descarga) + f"\n# Artículo {id_}\n\n{texto}\n"
    (dir_ / nombre_archivo(id_)).write_text(md, encoding="utf-8")


def _indice(dir_, sigla, anio, ids_estatus):
    filas = [f"# Índice de Ley X ({sigla}), vigencia {anio}\n", "Última reforma publicada en el DOF: x. N artículos.\n",
             "| Artículo | Archivo | Estatus | Inicio del texto |", "|---|---|---|---|"]
    for id_, est in ids_estatus:
        n = nombre_archivo(id_)
        filas.append(f"| {id_} | [{n}]({n}) | {est} | ... |")
    filas.append("\n[Transitorios](transitorios.md)\n")
    (dir_ / "_indice.md").write_text("\n".join(filas), encoding="utf-8")


def _meta(sigla, anio, n, reforma, sha, descarga):
    return {"sigla": sigla, "nombre_oficial": "Ley X", "tipo": "ley", "fuente_url": f"https://example.com/{sigla}.pdf",
            "ultima_reforma_dof": reforma, "fecha_descarga": descarga, "sha256_pdf": sha, "articulos_extraidos": n,
            "ultimo_articulo_numerico": 4, "vigencia_anio": anio, "estatus": "vigente", "decretos_con_transitorios": 1, "advertencias": []}


def _transitorios(dir_, sigla, anio, sha, texto="Primero. Entra en vigor."):
    campos = {"ley": sigla, "vigencia_anio": anio, "tipo": "transitorios", "estatus": "vigente", "sha256_fuente": sha}
    (dir_ / "transitorios.md").write_text("---\n" + "".join(f"{k}: {json.dumps(v)}\n" for k, v in campos.items()) + f"---\n\n# Transitorios\n\n{texto}\n", encoding="utf-8")


def escribir_ley_completa(raiz_leyes, sigla, anio, textos, estatus=None, reforma="2024-04-01", sha=SHA26, descarga="2026-11-02", espacios=False):
    """Escribe leyes/<anio>/<sigla>/ completo (como el pipeline) bajo `raiz_leyes` (puede ser una carpeta temporal fuera del árbol)."""
    d = Path(raiz_leyes) / str(anio) / sigla
    estatus = estatus or {}
    for id_, t in textos.items():
        if espacios:
            t = t.replace(" ", "  ")  # solo cambian los espacios: no debe contar como modificación
        escribir_articulo(d, sigla, anio, id_, t, estatus.get(id_, "vigente"), reforma, sha, descarga)
    from leyes_mx.ids import clave_orden
    orden = sorted(textos, key=clave_orden)
    _indice(d, sigla, anio, [(i, estatus.get(i, "vigente")) for i in orden])
    (d / "_meta.json").write_text(json.dumps(_meta(sigla, anio, len(textos), reforma, sha, descarga), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _transitorios(d, sigla, anio, sha)
    return d


def arbol_base(raiz):
    """leyes/2026/XLEY y leyes/2026/YLEY completas."""
    escribir_ley_completa(Path(raiz) / "leyes", "XLEY", 2026, TEXTOS_BASE)
    escribir_ley_completa(Path(raiz) / "leyes", "YLEY", 2026, {"1": "Artículo uno de Y.", "2": "Artículo dos de Y."})


def completo_2027(tmp):
    """Texto completo de XLEY 2027 (como lo dejaría pipeline.construir) y de YLEY (idéntico al 2026)."""
    textos = dict(TEXTOS_BASE)
    textos["3"] = "Texto NUEVO del artículo tres: la tasa es del 35%."
    textos["4"] = "Se deroga."
    textos["4-G"] = "Texto del artículo nuevo 4-G."
    dx = escribir_ley_completa(Path(tmp) / "x", "XLEY", 2027, textos, estatus={"4": "derogado"}, reforma="2026-12-31", sha=SHA27, descarga="2027-01-05", espacios=True)
    dy = escribir_ley_completa(Path(tmp) / "y", "YLEY", 2027, {"1": "Artículo uno de Y.", "2": "Artículo dos de Y."}, reforma="2024-04-01", sha=SHA27, descarga="2027-01-05")
    return dx, dy
