#!/usr/bin/env python3
"""Genera la capa de un año nuevo: leyes/<año>/<SIGLA>/ con SOLO los artículos que cambian respecto del año que hereda.

Descarga (si hace falta) el PDF de la Cámara, extrae el texto completo a un directorio temporal, compara cada artículo
contra el texto heredado (cuerpo sin front matter, espacios normalizados) y escribe los que difieren (modificados,
nuevos y derogados), más _meta.json (hereda_de, vigente_desde, articulos_modificados, fuente), _indice.md completo y,
si cambiaron, transitorios.md. Una ley sin cambios queda como una capa solo con _meta.json (deja constancia de que se revisó).
Reemplaza a scripts/copiar_anio.py. Modelo: docs/criterio-anios.md; procedimiento: docs/publicar-reforma.md.

Uso:
  python3 scripts/diferenciar.py LISR CFF --anio 2027 --vigente-desde 2027-01-01 \
      --decreto "DOF 2026-12-DD" --nota "Decreto por el que se reforma..." [--hereda-de 2026] [--sin-descargar] [--dry-run]

Las tablas transcritas (tablas/<año>/<SIGLA>/tablas.json) se leen del año nuevo: si el año nuevo no tiene la carpeta, hay que
crearla (copiando la del año anterior si las tablas no cambiaron) antes de correr esto, o los arts. con tabla saldrán como modificados.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import diferenciar, pipeline as P  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siglas", nargs="*")
    ap.add_argument("--anio", type=int, required=True)
    ap.add_argument("--vigente-desde", help="fecha ISO desde la que rige la capa (por omisión, AAAA-01-01 del año)")
    ap.add_argument("--hereda-de", type=int, help="año de la capa que se hereda (por omisión, la anterior más reciente)")
    ap.add_argument("--decreto", help="decreto del DOF que origina la capa, p. ej. 'DOF 2026-12-31'")
    ap.add_argument("--nota", help="nota breve sobre la fuente")
    ap.add_argument("--fecha-dof", help="fecha de publicación en el DOF (AAAA-MM-DD)")
    ap.add_argument("--sin-descargar", action="store_true", help="usa los PDF ya presentes en fuentes/<año>/")
    ap.add_argument("--dry-run", action="store_true", help="solo reporta qué cambiaría")
    a = ap.parse_args()
    cfg = P.cargar_config()
    leyes = [P.config_ley(s, cfg) for s in a.siglas] if a.siglas else cfg["leyes"]
    fuente = {k: v for k, v in (("decreto", a.decreto), ("nota", a.nota), ("fecha_dof", a.fecha_dof)) if v}
    desde = a.vigente_desde or f"{a.anio}-01-01"
    codigo = 0
    for ley in leyes:
        sigla = ley["sigla"].upper()
        pdf = P.RAIZ / "fuentes" / str(a.anio) / f"{sigla}.pdf"
        if not a.sin_descargar or not pdf.exists():
            print(f"descargando {ley['url']}")
            P.descargar(ley["url"], pdf)
        previa = P.RAIZ / "tablas" / str(a.hereda_de or a.anio - 1) / sigla
        if previa.is_dir() and not (P.RAIZ / "tablas" / str(a.anio) / sigla).is_dir():
            print(f"{sigla}: AVISO falta tablas/{a.anio}/{sigla}/ (existe la del año anterior): los artículos con tablas transcritas saldrán como modificados "
                  "mientras no se copie esa carpeta (o se transcriban las tablas nuevas)")
        try:
            r = diferenciar.generar(ley, pdf, a.anio, vigente_desde=desde, hereda_de=a.hereda_de, fuente=fuente or None, dry_run=a.dry_run)
        except ValueError as e:
            print(f"{sigla}: ERROR {e}")
            codigo = 1
            continue
        print(f"{sigla}: hereda de {r['hereda_de']}, {len(r['modificados'])} modificados, {len(r['nuevos'])} nuevos "
              f"({len(r['derogados'])} derogados), {r['sin_cambios']} sin cambios{', transitorios distintos' if r['transitorios'] else ''}"
              f"{' [dry-run]' if a.dry_run else ''}")
        if r["modificados"] or r["nuevos"]:
            print("   artículos:", ", ".join(r["modificados"] + r["nuevos"]))
    if not a.dry_run:
        print("\nSiguiente: python3 scripts/etiquetar.py && python3 scripts/validar.py")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
