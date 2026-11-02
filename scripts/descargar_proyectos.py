#!/usr/bin/env python3
"""Descarga los PDF oficiales listados en proyectos/<anio>/documentos.json a proyectos/<anio>/documentos/ y verifica sha256.
Uso: python3 scripts/descargar_proyectos.py [--anio 2027]"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import pipeline  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--anio", type=int, default=2027)
a = ap.parse_args()
base = pipeline.RAIZ / "proyectos" / str(a.anio)
man = json.loads((base / "documentos.json").read_text(encoding="utf-8"))
mal = 0
for d in man["documentos"]:
    dest = base / "documentos" / d["archivo"]
    if not dest.exists():
        print("descargando", d["url"])
        pipeline.descargar(d["url"], dest)
    ok = pipeline.sha256_archivo(dest) == d["sha256"]
    print(("OK  " if ok else "DIFIERE (el documento cambió o está corrupto) ") + d["archivo"])
    mal += not ok
sys.exit(1 if mal else 0)
