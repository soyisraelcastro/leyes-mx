#!/usr/bin/env python3
"""Control independiente: para cada articulo, que porcentaje de sus secuencias de 6 palabras aparece en el texto del PDF
extraido SIN -layout (otra via). Marca articulos con cobertura < umbral (cortes malos o texto perdido/inventado).
Requiere los PDF en fuentes/<anio>/ (ignorados por git). Uso: python3 scripts/verificar_cobertura.py [--anio 2026] [--umbral 0.97]"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import extraer, store  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def palabras(t):
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", t)


def shingles(ws, n=6):
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int, default=2026)
    ap.add_argument("--umbral", type=float, default=0.97)
    a = ap.parse_args()
    mal = 0
    for d in sorted((RAIZ / "leyes" / str(a.anio)).iterdir()):
        pdf = RAIZ / "fuentes" / str(a.anio) / f"{d.name}.pdf"
        if not pdf.exists():
            print(f"{d.name}: sin PDF local, se omite"); continue
        crudo = extraer.pdf_a_texto(pdf, layout=False)
        lim, _ = extraer.separar_notas(extraer.quitar_encabezados(crudo))
        S = shingles(palabras(" ".join(lim)))
        tot = bajos = 0
        for p in sorted(d.glob("art-*.md")):
            fm, cuerpo = store.parse_front_matter(p.read_text(encoding="utf-8"))
            sh = shingles(palabras(re.sub(r'\n```text|```', ' ', store._texto_articulo(cuerpo))))
            if not sh:
                continue
            tot += 1
            cov = len(sh & S) / len(sh)
            if cov < a.umbral:
                bajos += 1
                print(f"   {d.name} {fm['articulo']}: cobertura {cov:.0%} ({len(sh)} secuencias)")
        print(f"{d.name}: {tot} articulos con texto, {bajos} bajo {a.umbral:.0%}")
        mal += bajos
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main())
