#!/usr/bin/env python3
"""Atajo: python3 scripts/buscar.py obtener LISR 113-E | buscar "texto" --ley LISR"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
