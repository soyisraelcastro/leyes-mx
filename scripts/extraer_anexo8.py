#!/usr/bin/env python3
"""Extrae el Anexo 8 de la RMF para 2026 (tarifas de ISR) del PDF del DOF a rmf/2026/anexo-8/.

Pasos: descarga (si falta) -> pdftotext -layout -> quita encabezados del DOF -> parte por tarifa -> verifica
(aritmética de cada tarifa, conteo de filas contra el texto crudo, cada cifra contra el texto sin -layout)
-> escribe un .md por tarifa, _indice.md y _meta.json. Con cualquier discrepancia sale con código 1 y no escribe.

Uso:
  python3 scripts/extraer_anexo8.py                 # descarga a fuentes/2026/ si falta, verifica y escribe
  python3 scripts/extraer_anexo8.py --verificar     # solo verifica y reporta, no escribe
  python3 scripts/extraer_anexo8.py --pdf ruta.pdf  # usa un PDF local
  Opciones: --destino DIR  --fecha AAAA-MM-DD  --json
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import anexos, pipeline  # noqa: E402

RAIZ = pipeline.RAIZ


def verificar(datos):
    """Devuelve (errores, informe_por_tarifa). Falla si cualquier control no cuadra."""
    errores, informe = [], []
    conteos = anexos.contar_crudo(datos["lineas_cuerpo"], datos["tablas"])
    crudo = datos["texto_sin_layout"]
    n_adelante = crudo.count("En adelante")
    if n_adelante != len(datos["tablas"]):
        errores.append(f"'En adelante' aparece {n_adelante} veces en el texto sin -layout y hay {len(datos['tablas'])} tablas")
    tokens_crudo = set(re.findall(r"[\d,]+(?:\.\d+)?", crudo))
    for t, n_crudo in zip(datos["tablas"], conteos):
        errs = anexos.verificar_tarifa(t["id"], t["filas"])
        if n_crudo != len(t["filas"]):
            errs.append(f"{t['id']}: {n_crudo} renglones numéricos en el texto crudo y {len(t['filas'])} filas parseadas")
        for i, fila in enumerate(t["filas"], 1):
            for celda in fila:
                if celda != "En adelante" and celda not in tokens_crudo:
                    errs.append(f"{t['id']} fila {i}: la cifra {celda} no aparece en el texto sin -layout")
        ds = anexos.desviaciones(t["filas"])
        tol = anexos.tolerancia(t["id"])
        max_c = max(d[1] for d in ds)
        informe.append({"id": t["id"], "apartado": t["apartado"], "filas": len(t["filas"]), "filas_crudo": n_crudo,
                        "multiplo": anexos.multiplo(t["id"]), "desv_max_limites": str(max(d[0] for d in ds)),
                        "desv_max_cuota": f"{max_c:.4f}", "tolerancia": str(tol),
                        "estado": "exacto" if max_c == 0 else ("dentro de tolerancia" if not errs else "NO CUADRA"),
                        "errores": errs})
        errores.extend(errs)
    errores.extend(anexos.verificar_equivalencias({t["id"]: t["filas"] for t in datos["tablas"]}))
    return errores, informe


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf")
    ap.add_argument("--destino")
    ap.add_argument("--fecha")
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    pdf = Path(a.pdf) if a.pdf else RAIZ / "fuentes" / str(anexos.ANIO) / anexos.NOMBRE_PDF
    if not pdf.exists():
        print(f"descargando {anexos.FUENTE_URL}", file=sys.stderr)
        pipeline.descargar(anexos.FUENTE_URL, pdf)
    try:
        datos = anexos.extraer_pdf(pdf)
    except anexos.ErrorAnexo as ex:
        print(f"ERROR de extracción: {ex}", file=sys.stderr)
        return 1
    errores, informe = verificar(datos)
    if a.json:
        print(json.dumps({"sha256": anexos.sha256_archivo(pdf), "tarifas": informe, "errores": errores}, ensure_ascii=False, indent=2))
    else:
        for f in informe:
            print(f"{f['id']:38} filas {f['filas']}/{f['filas_crudo']} K={f['multiplo']:<2} desv. cuota {f['desv_max_cuota']} (tol. {f['tolerancia']}) {f['estado']}")
        print(f"\n{len(informe)} tarifas, {len(errores)} error(es)")
    if errores:
        for e in errores:
            print("ERROR:", e, file=sys.stderr)
        return 1
    if a.verificar:
        return 0
    destino = Path(a.destino) if a.destino else anexos.carpeta(anexos.ANIO, RAIZ)
    meta = anexos.escribir(datos, pdf, destino, a.fecha or date.today().isoformat())
    print(f"escrito {destino} ({meta['tarifas']} tarifas, sha256 {meta['sha256_pdf'][:12]}...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
