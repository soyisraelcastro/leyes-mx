#!/usr/bin/env python3
"""Revisa si cambiaron las leyes configuradas (y si hay señal de que se publicó la reforma 2027).

Además compara el PDF del Anexo 8 de la RMF (rmf/<año>/anexo-8/) por sha256 y tamaño y avisa si cambia (el SAT
publica modificaciones de anexos durante el año); eso nunca se regenera solo.
Para cada ley de fuentes.json baja el PDF a un directorio temporal, compara "Última Reforma DOF" y sha256 con el
_meta.json guardado del año vigente, y reporta. Con --aplicar regenera el árbol afectado (solo si pasa la validación).

Códigos de salida (para cron en un servidor):
  0 = sin cambios        1 = hay cambios (o reforma publicada)        2 = error de descarga o de validación

Uso:
  python3 scripts/revisar_reformas.py --dry-run          # solo reporta; no toca el árbol
  python3 scripts/revisar_reformas.py --aplicar          # regenera lo que cambió (para el workflow)
  python3 scripts/revisar_reformas.py --dry-run --offline  # compara contra los PDF locales de fuentes/ (prueba sin red)
  Opciones: --solo LISR CFF   --anio 2026   (el Anexo 8 de la RMF se vigila siempre; con --solo, incluir ANEXO8)   --resumen-md salida.md   --json
"""
import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import anexos, diferenciar, extraer, pipeline, versiones  # noqa: E402

RAIZ = pipeline.RAIZ


def _validador():
    spec = importlib.util.spec_from_file_location("validar", RAIZ / "scripts" / "validar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cuerpo_sin_meta(ruta):
    t = ruta.read_text(encoding="utf-8")
    fin = t.find("\n---\n", 4)
    return t[fin:] if fin > 0 else t


def diff_arbol(viejo, nuevo):
    v = {p.name: p for p in viejo.glob("art-*.md")} if viejo.exists() else {}
    n = {p.name: p for p in nuevo.glob("art-*.md")}
    agregados = sorted(set(n) - set(v))
    quitados = sorted(set(v) - set(n))
    cambiados = sorted(k for k in set(v) & set(n) if _cuerpo_sin_meta(v[k]) != _cuerpo_sin_meta(n[k]))
    return agregados, quitados, cambiados


def revisar(args):
    cfg = pipeline.cargar_config()
    anio = args.anio or cfg["anio_vigencia_actual"]
    vigiladas = set()
    est = RAIZ / "proyectos" / "2027" / "estado.json"
    if est.exists():
        vigiladas = set(json.loads(est.read_text(encoding="utf-8")).get("leyes_vigiladas", []))
    leyes = [l for l in cfg["leyes"] if not args.solo or l["sigla"].upper() in [s.upper() for s in args.solo]]
    informe, errores = [], []
    tmp = Path(tempfile.mkdtemp(prefix="leyes-mx-"))
    try:
        for ley in leyes:
            sigla = ley["sigla"].upper()
            capa = versiones.capa(RAIZ, sigla, anio)
            if capa is None:
                informe.append({"sigla": sigla, "estado": "sin_datos_previos", "detalle": f"no existe leyes/{anio}/{sigla}"})
                continue
            meta = capa.meta
            pdf = tmp / f"{sigla}.pdf"
            try:
                if args.offline:
                    shutil.copy(RAIZ / "fuentes" / str(anio) / f"{sigla}.pdf", pdf)
                else:
                    pipeline.descargar(ley["url"], pdf)
                sha = pipeline.sha256_archivo(pdf)
                fecha = extraer.fecha_ultima_reforma(extraer.pdf_a_texto(pdf))
            except Exception as ex:  # noqa: BLE001
                errores.append(f"{sigla}: no se pudo descargar/leer ({ex})")
                informe.append({"sigla": sigla, "estado": "error", "detalle": str(ex)})
                continue
            fila = {"sigla": sigla, "fecha_guardada": meta["ultima_reforma_dof"], "fecha_nueva": fecha,
                    "sha_cambio": sha != meta["sha256_pdf"], "estado": "sin_cambios"}
            if fecha != meta["ultima_reforma_dof"]:
                fila["estado"] = "reforma_nueva"
            elif fila["sha_cambio"]:
                fila["estado"] = "pdf_distinto_misma_fecha"
            if fila["estado"] != "sin_cambios" and sigla in vigiladas and fila["estado"] == "reforma_nueva":
                fila["promover_2027"] = True
            if fila["estado"] != "sin_cambios" and args.aplicar and not args.dry_run:
                out = tmp / "arbol"
                try:
                    r = pipeline.construir(ley, pdf, anio, destino_raiz=out, fecha_descarga=date.today().isoformat())
                    rep = _validador().validar_ley(out / str(anio) / sigla, anio, ley.get("ultimo_articulo_esperado"), False)
                    if rep["errores"]:
                        fila["estado"] = "regeneracion_invalida"
                        fila["errores"] = rep["errores"][:10]
                        errores.append(f"{sigla}: la regeneración no pasa la validación")
                    else:
                        destino = RAIZ / "leyes" / str(anio) / sigla
                        if capa.hereda_de is not None:
                            # año con capas: se reescribe solo el delta contra lo heredado, conservando hereda_de, vigente_desde y fuente
                            res = diferenciar.escribir_capa(RAIZ, sigla, anio, out / str(anio) / sigla, vigente_desde=capa.vigente_desde,
                                                            hereda_de=capa.hereda_de, fuente=meta.get("fuente"))
                            fila.update({"agregados": res["nuevos"], "quitados": [], "cambiados": res["modificados"]})
                        else:
                            ag, qu, ca = diff_arbol(destino, out / str(anio) / sigla)
                            fila.update({"agregados": ag, "quitados": qu, "cambiados": ca})
                            shutil.rmtree(destino)
                            shutil.copytree(out / str(anio) / sigla, destino)
                        (RAIZ / "fuentes" / str(anio)).mkdir(parents=True, exist_ok=True)
                        shutil.copy(pdf, RAIZ / "fuentes" / str(anio) / f"{sigla}.pdf")
                        fila["aplicado"] = True
                except Exception as ex:  # noqa: BLE001
                    fila["estado"] = "regeneracion_invalida"
                    errores.append(f"{sigla}: falló la regeneración ({ex})")
            informe.append(fila)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return anio, informe, errores


def revisar_anexos(args):
    """Vigila el PDF de cada Anexo 8 guardado en rmf/<anio>/anexo-8/: compara sha256 y tamaño con su _meta.json.
    El SAT publica modificaciones de anexos durante el año; si el PDF cambia, se avisa y se revisa a mano
    (python3 scripts/extraer_anexo8.py --verificar): nunca se regenera solo. Devuelve (filas, errores)."""
    filas, errores = [], []
    if args.solo and "ANEXO8" not in [s.upper().replace("-", "") for s in args.solo]:
        return filas, errores
    tmp = Path(tempfile.mkdtemp(prefix="leyes-mx-anexo-"))
    try:
        for anio in anexos.anios_disponibles(RAIZ):
            meta = json.loads((anexos.carpeta(anio, RAIZ) / "_meta.json").read_text(encoding="utf-8"))
            nombre = f"ANEXO-8-RMF-{anio}"
            pdf = tmp / f"{anio}.pdf"
            try:
                if args.offline:
                    shutil.copy(RAIZ / "fuentes" / str(anio) / anexos.NOMBRE_PDF, pdf)
                else:
                    pipeline.descargar(meta["fuente_url"], pdf)
            except Exception as ex:  # noqa: BLE001
                errores.append(f"{nombre}: no se pudo descargar ({ex})")
                filas.append({"sigla": nombre, "estado": "error", "detalle": str(ex)})
                continue
            sha, tam = pipeline.sha256_archivo(pdf), pdf.stat().st_size
            cambio = sha != meta["sha256_pdf"] or tam != meta.get("tamano_bytes", tam)
            fila = {"sigla": nombre, "estado": "anexo_modificado" if cambio else "sin_cambios", "sha_cambio": cambio,
                    "sha256_guardado": meta["sha256_pdf"], "sha256_nuevo": sha,
                    "tamano_guardado": meta.get("tamano_bytes"), "tamano_nuevo": tam, "publicado_dof": meta["publicado_dof"]}
            if cambio:
                fila["detalle_corto"] = (f"{nombre} PDF distinto al de DOF {meta['publicado_dof']} "
                                         f"({meta.get('tamano_bytes')} -> {tam} bytes"
                                         + (f", sha256 {meta['sha256_pdf'][:8]} -> {sha[:8]}" if sha != meta["sha256_pdf"] else "") + "); "
                                         "revisar y correr scripts/extraer_anexo8.py")
            filas.append(fila)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return filas, errores


def resumen_md(anio, informe):
    L = [f"# Revisión de reformas ({date.today().isoformat()}, año de vigencia {anio})\n"]
    for f in informe:
        if f["estado"] in ("sin_cambios", "sin_datos_previos"):
            continue
        if f["estado"] == "anexo_modificado":
            L.append(f"## {f['sigla']}: PDF modificado\n")
            L.append(f"- {f['detalle_corto']}\n")
            continue
        L.append(f"## {f['sigla']}: {f['estado']}\n")
        L.append(f"- Última reforma DOF guardada: {f.get('fecha_guardada')}; en el PDF de la Cámara ahora: {f.get('fecha_nueva')}")
        for k, t in (("agregados", "Artículos nuevos"), ("quitados", "Artículos que desaparecen"), ("cambiados", "Artículos con texto distinto")):
            if f.get(k):
                L.append(f"- {t} ({len(f[k])}): " + ", ".join(x.replace('art-', '').replace('.md', '') for x in f[k][:60]) + (" ..." if len(f[k]) > 60 else ""))
        if f.get("errores"):
            L.append("- Errores de validación: " + "; ".join(f["errores"]))
        if f.get("promover_2027"):
            L.append("- Ley vigilada por la reforma 2027: seguir docs/publicar-reforma.md")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="solo reporta, no escribe nada en el árbol")
    ap.add_argument("--aplicar", action="store_true", help="regenera las leyes que cambiaron (si pasan la validación)")
    ap.add_argument("--offline", action="store_true", help="usa los PDF locales de fuentes/ en lugar de descargar (para probar)")
    ap.add_argument("--solo", nargs="*")
    ap.add_argument("--anio", type=int)
    ap.add_argument("--resumen-md")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    anio, informe, errores = revisar(a)
    fa, ea = revisar_anexos(a)
    informe += fa
    errores += ea
    cambios = [f for f in informe if f["estado"] not in ("sin_cambios", "sin_datos_previos", "error")]
    if a.resumen_md:
        Path(a.resumen_md).write_text(resumen_md(anio, informe), encoding="utf-8")
    if a.json:
        print(json.dumps({"anio": anio, "informe": informe, "errores": errores}, ensure_ascii=False, indent=2))
    else:
        if errores:
            print("ERROR: " + " | ".join(errores))
        if cambios:
            print("leyes-mx: " + "; ".join(f.get("detalle_corto") or f"{f['sigla']} {f['estado']} ({f.get('fecha_guardada')} -> {f.get('fecha_nueva')})" for f in cambios))
            if any(f.get("promover_2027") for f in cambios):
                print("Reforma publicada en una ley vigilada: generar la capa 2027 con scripts/diferenciar.py (docs/publicar-reforma.md)")
        elif not errores:
            print(f"leyes-mx: sin cambios ({len(informe)} leyes revisadas, año {anio})")
    if errores:
        return 2
    return 1 if cambios else 0


if __name__ == "__main__":
    sys.exit(main())
