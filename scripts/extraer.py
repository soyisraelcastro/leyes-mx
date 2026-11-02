#!/usr/bin/env python3
"""Descarga (si hace falta) y extrae las leyes configuradas en fuentes.json hacia leyes/<anio>/<SIGLA>/.

Uso:
  python3 scripts/extraer.py                    # todas las leyes, anio vigente de fuentes.json
  python3 scripts/extraer.py LISR CFF --anio 2026
  python3 scripts/extraer.py --sin-descargar    # usa los PDF ya presentes en fuentes/<anio>/
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import pipeline as P  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siglas", nargs="*")
    ap.add_argument("--anio", type=int)
    ap.add_argument("--sin-descargar", action="store_true")
    a = ap.parse_args()
    cfg = P.cargar_config()
    anio = a.anio or cfg["anio_vigencia_actual"]
    leyes = [P.config_ley(s, cfg) for s in a.siglas] if a.siglas else cfg["leyes"]
    for ley in leyes:
        pdf = P.RAIZ / "fuentes" / str(anio) / f"{ley['sigla'].upper()}.pdf"
        if not a.sin_descargar or not pdf.exists():
            print(f"descargando {ley['url']}")
            P.descargar(ley["url"], pdf)
        r = P.construir(ley, pdf, anio)
        print(f"{r['sigla']}: {r['n']} articulos, ultima reforma {r['ultima_reforma_dof']}, sha256 {r['sha256'][:12]}")


if __name__ == "__main__":
    main()
