#!/usr/bin/env python3
"""Genera leyes/<hasta>/<SIGLA>/ copiando leyes/<desde>/<SIGLA>/ para leyes que NO cambiaron de un año a otro.

Reescribe vigencia_anio en cada artículo y en _meta.json, y anota "copiado_de" para que quede claro que el texto es el mismo.
Úsalo SOLO después de confirmar (scripts/revisar_reformas.py) que la ley no tuvo reformas con vigencia en el año nuevo.
Criterio completo en docs/criterio-anios.md.

Uso: python3 scripts/copiar_anio.py --desde 2026 --hasta 2027 LIVA CFF [--dry-run] [--raiz RUTA]
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("siglas", nargs="+")
    ap.add_argument("--desde", type=int, required=True)
    ap.add_argument("--hasta", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--raiz", type=Path, default=RAIZ)
    a = ap.parse_args()
    for sigla in [s.upper() for s in a.siglas]:
        src = a.raiz / "leyes" / str(a.desde) / sigla
        dst = a.raiz / "leyes" / str(a.hasta) / sigla
        if not src.is_dir():
            sys.exit(f"no existe {src}")
        if dst.exists():
            sys.exit(f"ya existe {dst}; no se sobrescribe")
        n = len(list(src.glob("art-*.md")))
        print(f"{sigla}: {src.name} -> {dst} ({n} artículos){' [dry-run]' if a.dry_run else ''}")
        if a.dry_run:
            continue
        shutil.copytree(src, dst)
        for p in dst.glob("*.md"):
            t = p.read_text(encoding="utf-8")
            t = re.sub(r'^vigencia_anio: \d+$', f"vigencia_anio: {a.hasta}", t, count=1, flags=re.M)
            if p.name.startswith("art-"):
                t = re.sub(r'^(vigencia_anio: .*)$', rf'\1\ncopiado_de_anio: {a.desde}', t, count=1, flags=re.M)
            p.write_text(t, encoding="utf-8")
        m = json.loads((dst / "_meta.json").read_text(encoding="utf-8"))
        m["vigencia_anio"] = a.hasta
        m["copiado_de_anio"] = a.desde
        m["nota"] = f"Texto idéntico al de {a.desde}: la ley no tuvo reformas con vigencia en {a.hasta} al momento de copiar."
        (dst / "_meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
