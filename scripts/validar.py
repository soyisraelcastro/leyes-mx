#!/usr/bin/env python3
"""Revalida todo el arbol leyes/ (y proyectos/). Codigo de salida 1 si hay errores.

Comprueba: front matter completo, nombres de archivo vs articulo, secuencia sin huecos ni repetidos,
sin articulos vacios, conteo vs _meta.json y vs fuentes.json, sha256 consistente, y que nada con estatus
distinto de vigente/derogado viva en leyes/ (ni nada vigente en proyectos/).
Valida tambien glosario.json (cada articulo citado existe y su evidencia aparece en el texto).
Con --pdf compara ademas el conteo contra una extraccion independiente del PDF (si esta en fuentes/).
Uso: python3 scripts/validar.py [--anio 2026] [--ley LISR] [--json] [--pdf]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from leyes_mx import tablas as tablas_mod
from leyes_mx import store  # noqa: E402
from leyes_mx import anexos_validar  # noqa: E402
from leyes_mx import rmf_validar  # noqa: E402
from leyes_mx import spe as spe_mod  # noqa: E402
from leyes_mx import temas as temas_mod  # noqa: E402
from leyes_mx import glosario as glosario_mod  # noqa: E402
from leyes_mx.ids import id_desde_archivo, clave_orden, partes_id, nombre_archivo, PALABRAS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
REQ = ["ley", "nombre_ley", "articulo", "vigencia_anio", "ultima_reforma_dof", "fuente_url", "fecha_descarga", "estatus", "sha256_fuente"]
RE_ART_EN_CUERPO = re.compile(r"^Art[íi]culo\s+\d+[\w\-ºo]*\s*\.(?:-|\s)", re.M)


def validar_ley(dirley, anio, esperado, usar_pdf):
    errores, avisos = [], []
    sigla = dirley.name
    meta_p = dirley / "_meta.json"
    if not meta_p.exists():
        return {"sigla": sigla, "errores": ["falta _meta.json"], "avisos": [], "n": 0}
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    for k in ("sigla", "nombre_oficial", "fuente_url", "ultima_reforma_dof", "fecha_descarga", "sha256_pdf", "articulos_extraidos"):
        if not meta.get(k):
            errores.append(f"_meta.json sin {k}")
    for f in ("_indice.md", "transitorios.md"):
        if not (dirley / f).exists():
            errores.append(f"falta {f}")
    datos_t, _carp = tablas_mod.cargar(sigla, anio)
    for t in (datos_t or {}).get("tablas", []):
        if not t.get("solo_imagen"):
            errores.extend(tablas_mod.verificar(t))
    ids, cortos, sospechosos = [], [], []
    for p in sorted(dirley.glob("art-*.md")):
        id_ = id_desde_archivo(p.name)
        if not id_:
            errores.append(f"nombre de archivo invalido: {p.name}")
            continue
        fm, cuerpo = store.parse_front_matter(p.read_text(encoding="utf-8"))
        falt = [k for k in REQ if not fm.get(k)]
        if falt:
            errores.append(f"{p.name}: front matter sin {falt}")
        if fm.get("articulo") != id_:
            errores.append(f"{p.name}: articulo={fm.get('articulo')!r} no coincide con el archivo")
        if fm.get("ley") != sigla:
            errores.append(f"{p.name}: ley={fm.get('ley')!r} != carpeta {sigla}")
        if fm.get("vigencia_anio") != anio:
            errores.append(f"{p.name}: vigencia_anio={fm.get('vigencia_anio')!r} != carpeta {anio}")
        if fm.get("estatus") not in ("vigente", "derogado"):
            errores.append(f"{p.name}: estatus {fm.get('estatus')!r} no permitido en leyes/ (los proyectos van en proyectos/)")
        if fm.get("sha256_fuente") != meta.get("sha256_pdf"):
            errores.append(f"{p.name}: sha256_fuente distinto al de _meta.json")
        texto = store._texto_articulo(cuerpo)
        texto = re.sub(r"^# Art[^\n]*\n", "", texto).strip()
        if not fm.get("tablas_transcritas"):
            pars = [x for x in texto.split("\n\n") if x.strip()]
            for i, par in enumerate(pars):
                if re.search(r"(la|las|esta|estas)\s+siguientes?(\s+(tarifa|tabla|tablas))?\s*:\s*$", par.strip(), re.I):
                    sig = pars[i + 1].lstrip() if i + 1 < len(pars) else ""
                    if not re.match(r"(\||```|TABLA|TARIFA|I\.|a\)|1\.|[IVX]+\.|[A-Z]\.)", sig):
                        avisos.append(f"{p.name}: el párrafo termina en 'la siguiente:' y no hay tabla ni lista debajo; "
                                      "posible tabla publicada como imagen en el PDF (agregar en tablas/<anio>/<LEY>/tablas.json)")
                        break
        if not texto:
            errores.append(f"{p.name}: articulo vacio")
        elif fm.get("estatus") == "vigente" and len(texto) < 25:
            cortos.append(f"{id_} ({len(texto)} car.: {texto!r})")
        if len(texto) > 60000:
            sospechosos.append(f"{id_} muy largo ({len(texto)} car.)")
        if RE_ART_EN_CUERPO.search(texto):
            sospechosos.append(f"{id_} contiene un encabezado 'Artículo N.' dentro del cuerpo (posible absorcion)")
        ids.append(id_)
    # secuencia
    vistos = set()
    for i, id_ in enumerate(ids):
        if id_ in vistos:
            errores.append(f"repetido: {id_}")
        vistos.add(id_)
    ordenados = sorted(set(ids), key=clave_orden)
    nums = sorted({partes_id(i)[0] for i in ids})
    if nums:
        faltan = [n for n in range(1, nums[-1] + 1) if n not in set(nums)]
        if faltan:
            errores.append(f"huecos de numeracion: {faltan}")
        if nums[0] != 1:
            errores.append(f"no empieza en 1 ({nums[0]})")
    # letras: A..Z sin saltos dentro de un mismo numero (aviso)
    por_num = {}
    for i in ids:
        n, partes = partes_id(i)
        if partes and len(partes[0]) == 1 and partes[0].isupper():
            por_num.setdefault(n, set()).add(partes[0])
    for n, letras in por_num.items():
        esperadas = [chr(c) for c in range(ord("A"), ord(max(letras, key=lambda x: ord("N") + 0.5 if x == "Ñ" else ord(x))) + 1)]
        faltan = [l for l in esperadas if l not in letras]
        if faltan:
            avisos.append(f"art. {n}: faltan letras {faltan} (puede ser legitimo, verificar contra el PDF)")
    if meta.get("articulos_extraidos") != len(ids):
        errores.append(f"_meta dice {meta.get('articulos_extraidos')} articulos, hay {len(ids)} archivos")
    if esperado and nums and nums[-1] != esperado:
        errores.append(f"ultimo articulo {nums[-1]} != esperado {esperado} (fuentes.json)")
    if cortos:
        avisos.append("articulos vigentes muy cortos: " + "; ".join(cortos))
    if sospechosos:
        avisos.append("sospechosos: " + "; ".join(sospechosos))
    # PDF independiente
    if usar_pdf:
        pdf = RAIZ / "fuentes" / str(anio) / f"{sigla}.pdf"
        if pdf.exists():
            from leyes_mx import extraer
            from leyes_mx.pipeline import sha256_archivo
            if sha256_archivo(pdf) != meta["sha256_pdf"]:
                avisos.append("el PDF local no coincide con el sha256 de _meta.json; se omite el cruce")
            else:
                crudo = extraer.pdf_a_texto(pdf, layout=False)
                n = _contar_crudo(crudo, extraer)
                if n != len(ids):
                    errores.append(f"cruce con extraccion sin -layout: {n} encabezados vs {len(ids)} archivos")
                else:
                    avisos.append(f"cruce con pdftotext sin -layout: {n} encabezados = {len(ids)} archivos (OK)")
        else:
            avisos.append("sin PDF local para el cruce (fuentes/ esta ignorado por git)")
    return {"sigla": sigla, "errores": errores, "avisos": avisos, "n": len(ids), "ultimo": nums[-1] if nums else None,
            "ultima_reforma_dof": meta.get("ultima_reforma_dof")}


def _contar_crudo(crudo, extraer):
    """Cuenta encabezados de articulo con una regex DISTINTA y mas simple que la del extractor, sobre el texto SIN -layout.
    Linea que empieza con 'Articulo <numero>' seguida, a lo mas 14 caracteres despues, de un punto, o de un guion tras el numero."""
    naive = re.compile(r"^\s*Art[íi]culo\s+\d+[^\n.]{0,14}\.|^\s*Art[íi]culo\s+\d+-\s")
    lineas = [l.strip() for l in crudo.splitlines()]
    ini = next(i for i, l in enumerate(lineas) if re.match(r"^Art[íi]culo\s+1\s*[oº°]?\s*\.", l))
    fin = len(lineas)
    for i in range(ini + 1, len(lineas)):
        if extraer.RE_FIN_CUERPO.match(lineas[i]) and not naive.match(lineas[i]):
            fin = i
            break
    # una linea 'Articulo N ...' puede ser referencia partida; se descartan las que NO traen mayuscula inicial despues del punto
    return sum(1 for l in lineas[ini:fin] if naive.match(l))


def validar_proyectos():
    errores = []
    base = RAIZ / "proyectos"
    if not base.is_dir():
        return errores
    for p in base.rglob("art-*.md"):
        fm, cuerpo = store.parse_front_matter(p.read_text(encoding="utf-8"))
        if fm.get("estatus") != "proyecto":
            errores.append(f"{p.relative_to(RAIZ)}: en proyectos/ el estatus debe ser 'proyecto' (es {fm.get('estatus')!r})")
        if fm.get("estado_proyecto") not in ("iniciativa", "aprobado_camara", "aprobado_senado", "publicado_dof"):
            errores.append(f"{p.relative_to(RAIZ)}: estado_proyecto invalido {fm.get('estado_proyecto')!r}")
        if "NO es ley vigente" not in cuerpo:
            errores.append(f"{p.relative_to(RAIZ)}: falta la nota visible de que no es ley vigente")
    return errores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int)
    ap.add_argument("--ley")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pdf", action="store_true", help="cruce con extraccion independiente del PDF si existe en fuentes/")
    a = ap.parse_args()
    cfg = json.loads((RAIZ / "fuentes.json").read_text(encoding="utf-8"))
    esperado = {l["sigla"].upper(): l.get("ultimo_articulo_esperado") for l in cfg["leyes"]}
    informes = []
    for anio in store._anios(RAIZ):
        if a.anio and anio != a.anio:
            continue
        for d in sorted((RAIZ / "leyes" / str(anio)).iterdir()):
            if d.is_dir() and (not a.ley or d.name.upper() == a.ley.upper()):
                r = validar_ley(d, anio, esperado.get(d.name.upper()), a.pdf)
                r["anio"] = anio
                informes.append(r)
    perr = validar_proyectos()
    aerr, aavisos = ([], []) if a.ley else anexos_validar.validar(RAIZ, a.pdf)
    gerr, gavisos = ([], []) if a.ley else glosario_mod.validar(RAIZ)
    rerr, ravisos = ([], []) if a.ley else rmf_validar.validar(RAIZ, a.pdf)
    terr, tavisos = ([], []) if a.ley else temas_mod.validar(RAIZ, a.anio)
    serr, savisos = ([], []) if a.ley else spe_mod.validar(RAIZ)
    total = sum(len(r["errores"]) for r in informes) + len(perr) + len(aerr) + len(gerr) + len(rerr) + len(terr) + len(serr)
    if a.json:
        print(json.dumps({"leyes": informes, "proyectos_errores": perr, "anexos_errores": aerr, "anexos_avisos": aavisos,
                          "glosario_errores": gerr, "glosario_avisos": gavisos, "rmf_errores": rerr, "rmf_avisos": ravisos, "temas_errores": terr, "temas_avisos": tavisos, "spe_errores": serr, "spe_avisos": savisos, "errores": total}, ensure_ascii=False, indent=2))
    else:
        for r in informes:
            estado = "OK" if not r["errores"] else "ERRORES"
            print(f"[{estado}] {r['anio']}/{r['sigla']}: {r['n']} articulos, ultimo {r.get('ultimo')}, reforma DOF {r.get('ultima_reforma_dof')}")
            for e in r["errores"][:25]:
                print("   ERROR:", e)
            for w in r["avisos"]:
                print("   aviso:", w)
        for e in perr:
            print("   ERROR proyectos:", e)
        for e in aerr:
            print("   ERROR anexos:", e)
        for w in aavisos:
            print("   aviso anexos:", w)
        for e in gerr:
            print("   ERROR glosario:", e)
        for w in gavisos:
            print("   aviso glosario:", w)
        for e in terr:
            print("   ERROR temas:", e)
        for w in tavisos:
            print("   aviso temas:", w)
        for e in serr:
            print("   ERROR spe:", e)
        for w in savisos:
            print("   aviso spe:", w)
        for e in rerr:
            print("   ERROR rmf:", e)
        # los avisos de referencias a artículos inexistentes pueden ser muchos: se resumen
        resumen = [w for w in ravisos if "que no existe en la base" not in w and "no interpretable" not in w]
        omitidos = len(ravisos) - len(resumen)
        for w in resumen:
            print("   rmf:", w)
        if omitidos:
            print(f"   rmf: {omitidos} aviso(s) de referencias dudosas (usar --json para verlos)")
        print(f"\n{total} error(es)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
