#!/usr/bin/env python3
"""Lista las páginas de cada PDF fuente que traen imágenes de contenido (tablas publicadas como imagen).

pdftotext no ve esas imágenes, así que su contenido falta en los .md. Ignora el logo del encabezado
(imagen chica repetida en cada página). Para cada hallazgo indica si ya está cubierto en
tablas/<anio>/<LEY>/tablas.json. Sale con código 1 si queda alguna sin cubrir.

Uso: python3 scripts/detectar_imagenes.py [--anio 2026]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def paginas_con_imagenes(pdf):
    out = subprocess.run(["pdfimages", "-list", str(pdf)], capture_output=True, text=True, check=True).stdout
    pags = {}
    for linea in out.splitlines()[2:]:
        c = linea.split()
        if len(c) < 5:
            continue
        pag, ancho, alto = int(c[0]), int(c[3]), int(c[4])
        if ancho > 200 and alto > 100:  # el logo del encabezado es más chico
            pags.setdefault(pag, []).append(f"{ancho}x{alto}")
    return pags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int, default=2026)
    a = ap.parse_args()
    sin_cubrir = 0
    for pdf in sorted((RAIZ / "fuentes" / str(a.anio)).glob("*.pdf")):
        sigla = pdf.stem
        cub = set()
        j = RAIZ / "tablas" / str(a.anio) / sigla / "tablas.json"
        if j.exists():
            cub = {t["pagina_pdf"] for t in json.loads(j.read_text(encoding="utf-8"))["tablas"]}
        for pag, tam in paginas_con_imagenes(pdf).items():
            estado = "cubierta" if pag in cub else "SIN CUBRIR"
            sin_cubrir += pag not in cub
            print(f"{sigla} pág. {pag}: {len(tam)} imagen(es) {','.join(tam)} [{estado}]")
    sys.exit(1 if sin_cubrir else 0)


if __name__ == "__main__":
    main()
