#!/usr/bin/env python3
"""Extrae el subsidio para el empleo (SPE) 2026 del DOF a decretos/2026/spe/.

Descarga las notas del DOF (decreto del 01-05-2024, sus reformas del 31-12-2024 y 31-12-2025, y el valor de la UMA
de 2025 y 2026 que publica el INEGI), verifica cifras contra el texto, arma el texto consolidado y escribe.
Con cualquier discrepancia sale con código 1 y no escribe nada.

Uso:
  python3 scripts/extraer_spe.py              # descarga, verifica y escribe
  python3 scripts/extraer_spe.py --verificar  # descarga y verifica, no escribe
  python3 scripts/extraer_spe.py --validar    # revisa lo ya escrito (sin red), como hace validar.py
  Opciones: --destino DIR  --fecha AAAA-MM-DD
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import spe  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("--destino")
    ap.add_argument("--fecha")
    a = ap.parse_args()
    if a.validar:
        err, avisos = spe.validar()
        for e in err:
            print("ERROR:", e)
        for w in avisos:
            print("aviso:", w)
        print("SPE: OK" if not err else f"SPE: {len(err)} error(es)")
        return 1 if err else 0
    err, archivos = spe.extraer(destino=a.destino, escribir=not a.verificar, hoy=a.fecha)
    for e in err:
        print("ERROR:", e)
    if err:
        print("No se escribió nada.")
        return 1
    print(f"{'Verificado' if a.verificar else 'Escrito'}: {len(archivos)} archivos en {a.destino or spe.DIRECTORIO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
