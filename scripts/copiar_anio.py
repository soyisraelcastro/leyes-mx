#!/usr/bin/env python3
"""OBSOLETO: este script ya no se usa. Duplicaba leyes/<año>/<SIGLA>/ completo para cada año nuevo.

Ahora cada año posterior a la base es una CAPA que guarda solo los artículos que cambian y hereda el resto. Se genera con:

    python3 scripts/diferenciar.py LISR CFF ... --anio 2027 --vigente-desde 2027-01-01 --decreto "DOF ..."

Modelo en docs/criterio-anios.md; procedimiento en docs/publicar-reforma.md. No se borra para que quien lo busque encuentre este aviso.
"""
import sys


if __name__ == "__main__":
    sys.exit(__doc__ + "\ncopiar_anio.py está obsoleto: usa scripts/diferenciar.py (capas que heredan, sin duplicar).")
