#!/usr/bin/env python3
"""Descarga (si hace falta) y extrae las resoluciones de la RMF configuradas en fuentes.json ("rmf") a rmf/<anio>/<carpeta>/.

Uso:
  python3 scripts/extraer_rmf.py                 # todas las resoluciones configuradas
  python3 scripts/extraer_rmf.py RMF --anio 2026
  python3 scripts/extraer_rmf.py --sin-descargar # usa los PDF ya presentes en fuentes/<anio>/
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import pipeline as P  # noqa: E402
from leyes_mx import rmf  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siglas", nargs="*")
    ap.add_argument("--anio", type=int)
    ap.add_argument("--sin-descargar", action="store_true")
    a = ap.parse_args()
    cfg = P.cargar_config()
    anio = a.anio or cfg["anio_vigencia_actual"]
    todas = cfg.get("rmf", [])
    sel = [r for r in todas if not a.siglas or r["sigla"].upper() in [s.upper() for s in a.siglas]]
    if not sel:
        sys.exit("ninguna resolución configurada con esa sigla (ver 'rmf' en fuentes.json)")
    for r in sel:
        pdf = P.RAIZ / "fuentes" / str(anio) / r["archivo"]
        if not a.sin_descargar or not pdf.exists():
            print(f"descargando {r['url']}")
            P.descargar(r["url"], pdf)
        res = rmf.construir(pdf, anio, r)
        print(f"{r['sigla']}: {res['reglas']} reglas, sha256 {res['sha256'][:12]}")


if __name__ == "__main__":
    main()
