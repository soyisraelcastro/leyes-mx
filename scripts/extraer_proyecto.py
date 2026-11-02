#!/usr/bin/env python3
"""Trocea el decreto de un proyecto (PDF con capa de texto) en un archivo por articulo con estatus "proyecto".

Solo sirve para PDF con texto (p. ej. iniciativas del Ejecutivo en la Gaceta). Los PDF escaneados (minutas, dictamenes)
NO se trocean: se documentan con numero de pagina en el README del proyecto. Nunca se escribe texto de memoria.
Los puntos suspensivos (...) del decreto significan "texto sin cambio" y se conservan tal cual.

Uso:
  python3 scripts/extraer_proyecto.py PDF --ley LISR --nombre "Ley del Impuesto sobre la Renta" --anio 2027 \
     --estado iniciativa --url URL --fecha-documento 2026-09-08 --entrada-en-vigor 2027-01-01
"""
import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import extraer, pipeline  # noqa: E402
from leyes_mx.ids import nombre_archivo  # noqa: E402

AVISO = ("> **PROYECTO. NO es ley vigente.** Este texto proviene de {doc} y solo sería ley si se publica en el DOF; "
         "entraría en vigor {vigor}. Estado: {estado}. {extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--ley", required=True)
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--anio", type=int, default=2027)
    ap.add_argument("--estado", required=True, choices=["iniciativa", "aprobado_camara", "aprobado_senado", "publicado_dof"])
    ap.add_argument("--url", required=True)
    ap.add_argument("--doc", required=True, help="descripcion del documento fuente")
    ap.add_argument("--fecha-documento", required=True)
    ap.add_argument("--entrada-en-vigor", required=True)
    ap.add_argument("--extra", default="")
    ap.add_argument("--inicio", default=r"ART[ÍI]CULO PRIMERO.*REFORMAN")
    ap.add_argument("--fin", default=r"^\s*ART[ÍI]CULO SEGUNDO")
    ap.add_argument("--fin-transitorios", default=r"Hoja de firma")
    a = ap.parse_args()

    texto = unicodedata.normalize("NFC", extraer.pdf_a_texto(a.pdf, layout=True)).replace("\f", "\n")
    lineas = [l.rstrip() for l in texto.split("\n")]
    i0 = next(i for i, l in enumerate(lineas) if re.search(a.inicio, l))
    i1 = next(i for i, l in enumerate(lineas) if i > i0 and re.search(a.fin, l))
    i2 = next((i for i, l in enumerate(lineas) if i > i1 and re.search(a.fin_transitorios, l)), len(lineas))
    solo_num = re.compile(r"^\s*\d{1,4}\s*$")
    cuerpo = [l for l in lineas[i0:i1] if not solo_num.match(l)]
    trans = [l for l in lineas[i1:i2] if not solo_num.match(l)]

    sha = pipeline.sha256_archivo(a.pdf)
    hoy = date.today().isoformat()
    marcas = [(i, extraer.encabezado_articulo(l.strip())) for i, l in enumerate(cuerpo)]
    marcas = [(i, h) for i, h in marcas if h]
    dest = pipeline.RAIZ / "proyectos" / str(a.anio) / a.ley.upper()
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("art-*.md"):
        old.unlink()
    aviso = AVISO.format(doc=a.doc, vigor=a.entrada_en_vigor, estado=a.estado, extra=a.extra)
    ids = []
    for k, (i, (id_, fin_enc, crudo)) in enumerate(marcas):
        j = marcas[k + 1][0] if k + 1 < len(marcas) else len(cuerpo)
        bloque = cuerpo[i:j]
        bloque[0] = bloque[0].strip()[fin_enc - (len(cuerpo[i]) - len(cuerpo[i].lstrip())):].lstrip(" -")
        bloque, _est = extraer._cortar_estructura(bloque)
        txt = extraer.formatear(bloque)
        fm = {
            "ley": a.ley.upper(), "nombre_ley": a.nombre, "articulo": id_, "vigencia_anio": a.anio,
            "ultima_reforma_dof": None, "fuente_url": a.url, "fecha_descarga": hoy, "estatus": "proyecto",
            "estado_proyecto": a.estado, "entrada_en_vigor": a.entrada_en_vigor, "fecha_documento": a.fecha_documento,
            "sha256_fuente": sha,
        }
        md = pipeline.front_matter(fm) + f"\n{aviso}\n\n# Artículo {id_} (PROYECTO)\n\n{txt}\n"
        (dest / nombre_archivo(id_)).write_text(md, encoding="utf-8")
        ids.append(id_)
    t = pipeline.front_matter({"ley": a.ley.upper(), "nombre_ley": a.nombre, "tipo": "transitorios", "vigencia_anio": a.anio,
                               "estatus": "proyecto", "estado_proyecto": a.estado, "fuente_url": a.url,
                               "fecha_descarga": hoy, "sha256_fuente": sha})
    t += f"\n{aviso}\n\n# Disposiciones transitorias y de vigencia del proyecto ({a.ley.upper()})\n\n"
    t += extraer.formatear(trans) + "\n"
    (dest / "transitorios.md").write_text(t, encoding="utf-8")
    meta = {"sigla": a.ley.upper(), "estatus": "proyecto", "estado_proyecto": a.estado, "documento": a.doc,
            "fuente_url": a.url, "sha256_pdf": sha, "fecha_documento": a.fecha_documento, "fecha_descarga": hoy,
            "entrada_en_vigor": a.entrada_en_vigor, "articulos": ids}
    (dest / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{a.ley}: {len(ids)} articulos de proyecto -> {dest}")
    print(" ".join(ids))


if __name__ == "__main__":
    main()
