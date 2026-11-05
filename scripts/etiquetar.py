#!/usr/bin/env python3
"""Regenera temas/<anio>/ (el índice por temas) a partir de temas.json y de TODO lo que hay en leyes/ y rmf/.

Es obligatorio cada vez que cambia el vocabulario o entra, sale o se actualiza un ordenamiento: scripts/validar.py
falla si temas/ no coincide con lo que daría regenerarlo. Ver docs/temas.md.

Uso: python3 scripts/etiquetar.py [--anio 2026] [--resumen]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import store, temas  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anio", type=int)
    ap.add_argument("--resumen", action="store_true", help="solo imprime el resumen, sin escribir")
    a = ap.parse_args()
    anios = [a.anio] if a.anio else store._anios(RAIZ)
    for anio in anios:
        salida = temas.construir(RAIZ, anio) if a.resumen else temas.escribir(RAIZ, anio)
        idx = json.loads(salida[f"temas/{anio}/_indice.json"])
        print(f"{anio}: {idx['documentos']} documentos, {len(idx['temas'])} temas")
        for k, v in idx["cobertura"].items():
            print(f"  {k:8} {v['con_tema']:5} de {v['documentos']:5} con al menos un tema")
        for t, v in sorted(idx["temas"].items(), key=lambda x: -x[1]["documentos"]):
            print(f"  {v['documentos']:5}  {t}")


if __name__ == "__main__":
    main()
