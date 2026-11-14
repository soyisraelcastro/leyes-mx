#!/usr/bin/env python3
"""Empaqueta los datos (leyes/, proyectos/ sin PDF, tablas/, rmf/, decretos/, fuentes.json y glosario.json) para el Release de datos.

Genera en --salida:
  leyes-mx-datos.tar.gz   tarball determinista (mismo contenido -> mismos bytes -> mismo sha256)
  manifest.json           version, fecha, sha256 del tarball, ultima reforma DOF por ley

Dentro del tarball va INTEGRIDAD.json con el sha256 de cada archivo; el cliente (npx leyes-mx) lo verifica.

El repo guarda las leyes de un año posterior a la base como CAPAS (solo los artículos que cambian; ver docs/criterio-anios.md).
Por omisión el tarball MATERIALIZA la vista completa de cada capa en leyes/<año>/<SIGLA>/ (así lo leen también los clientes
npm anteriores, que esperan el año completo; gzip hace barato lo repetido) y manifest.json lleva "materializado": true.
Con --sin-materializar el tarball lleva las capas tal cual (manifest esquema 2: los clientes viejos lo rechazan en lugar de leerlo mal).
Uso: python3 scripts/empaquetar_datos.py --salida build/datos --version 2026.11.02 [--fecha 2026-11-02] [--sin-materializar]
"""
import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from leyes_mx import versiones  # noqa: E402

NOMBRE_TARBALL = "leyes-mx-datos.tar.gz"
ESQUEMA = 1
ESQUEMA_CAPAS = 2  # paquete con capas sin materializar: un cliente que solo conoce el esquema 1 no lo puede leer


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def archivos_a_empaquetar(raiz):
    res = []
    for base in ("leyes", "proyectos", "tablas", "rmf", "temas", "decretos"):
        if not (raiz / base).is_dir():
            continue
        for p in sorted((raiz / base).rglob("*")):
            if not p.is_file() or p.name == ".DS_Store":
                continue
            rel = p.relative_to(raiz)
            if p.suffix.lower() == ".pdf" or "documentos" in rel.parts:
                continue
            res.append(rel.as_posix())
    for suelto in ("fuentes.json", "glosario.json", "temas.json"):
        if (raiz / suelto).is_file():
            res.append(suelto)
    return sorted(res)


def _capas_con_herencia(raiz):
    """[(año, sigla)] de las leyes cuya capa hereda de otra."""
    res = []
    for a in versiones.anios(raiz):
        for sig in versiones.siglas(raiz, a):
            if versiones.capa(raiz, sig, a).hereda_de is not None:
                res.append((a, sig))
    return res


def _reescribir_heredado(datos, anio, meta):
    """Front matter de un artículo heredado, tal como lo ve la vista del año: vigencia_anio y ultima_reforma_dof del año pedido,
    y heredado_de_anio con el año de la capa de origen (equivale a lo que dejaba copiar_anio.py con copiado_de_anio)."""
    t = datos.decode("utf-8")
    origen = re.search(r"^vigencia_anio: (\d+)$", t, flags=re.M)
    t = re.sub(r"^vigencia_anio: \d+$", f"vigencia_anio: {anio}", t, count=1, flags=re.M)
    if meta.get("ultima_reforma_dof"):
        t = re.sub(r"^ultima_reforma_dof: .*$", "ultima_reforma_dof: " + json.dumps(meta["ultima_reforma_dof"], ensure_ascii=False), t, count=1, flags=re.M)
    if origen:
        t = re.sub(r"^(vigencia_anio: .*)$", rf"\1\nheredado_de_anio: {origen.group(1)}", t, count=1, flags=re.M)
    return t.encode("utf-8")


def materializar_capa(raiz, anio, sigla):
    """{ruta relativa: bytes} del directorio completo leyes/<anio>/<sigla>/ a partir de la vista de la capa."""
    raiz = Path(raiz)
    v = versiones.vista(raiz, sigla, anio)
    base = f"leyes/{anio}/{v.dir.name}"
    res = {}
    for c in reversed(v.cadena):  # archivos que no son artículos (imágenes de tablas): la capa más reciente gana
        for p in sorted(c.dir.rglob("*")):
            rel = p.relative_to(c.dir)
            if p.is_file() and p.name != ".DS_Store" and p.suffix.lower() != ".pdf" and not re.fullmatch(r"art-.*\.md|_meta\.json|_indice\.md|transitorios\.md", rel.as_posix()):
                res[f"{base}/{rel.as_posix()}"] = p.read_bytes()
    for nombre, p in v.archivos().items():
        datos = p.read_bytes()
        res[f"{base}/{nombre}"] = _reescribir_heredado(datos, anio, v.meta) if v.heredado(p) else datos
    p = v.archivo("transitorios.md")
    if p is not None:
        res[f"{base}/transitorios.md"] = _reescribir_heredado(p.read_bytes(), anio, v.meta) if v.heredado(p) else p.read_bytes()
    p = v.archivo("_indice.md")
    if p is not None:
        res[f"{base}/_indice.md"] = p.read_bytes()
    meta = dict(v.meta)
    meta["materializada"] = True
    res[f"{base}/_meta.json"] = (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return res


def resumen_leyes(raiz):
    leyes = []
    for meta in sorted((raiz / "leyes").glob("*/*/_meta.json")):
        m = json.loads(meta.read_text(encoding="utf-8"))
        leyes.append({
            "sigla": m["sigla"], "nombre": m["nombre_oficial"], "tipo": m.get("tipo"),
            "anio_vigencia": m["vigencia_anio"], "ultima_reforma_dof": m["ultima_reforma_dof"],
            "articulos": m["articulos_extraidos"], "fecha_descarga": m["fecha_descarga"],
        })
    return sorted(leyes, key=lambda x: (x["anio_vigencia"], x["sigla"]))


def resumen_proyectos(raiz):
    res = []
    for est in sorted((raiz / "proyectos").glob("*/estado.json")):
        e = json.loads(est.read_text(encoding="utf-8"))
        res.append({"anio": e.get("anio"), "actualizado": e.get("actualizado"),
                    "es_ley_vigente": e.get("es_ley_vigente", False), "resumen": e.get("resumen")})
    return res


def resumen_anexos(raiz):
    res = []
    for meta in sorted((raiz / "rmf").glob("*/*/_meta.json")) if (raiz / "rmf").is_dir() else []:
        m = json.loads(meta.read_text(encoding="utf-8"))
        if "documento" not in m:  # las resoluciones de la RMF (una regla por archivo) van en resumen_rmf
            continue
        res.append({"documento": m.get("documento"), "anio_vigencia": m.get("vigencia_anio"), "publicado_dof": m.get("publicado_dof"),
                    "tarifas": m.get("tarifas"), "sha256_pdf": m.get("sha256_pdf")})
    return res


def resumen_rmf(raiz):
    res = []
    for meta in sorted((raiz / "rmf").glob("*/*/_meta.json")) if (raiz / "rmf").is_dir() else []:
        m = json.loads(meta.read_text(encoding="utf-8"))
        if "reglas_extraidas" in m:
            res.append({"sigla": m.get("sigla"), "anio": int(meta.parent.parent.name), "reglas": m["reglas_extraidas"],
                        "publicacion_dof": m.get("publicacion_dof"), "sha256_pdf": m.get("sha256_pdf")})
    return res


def resumen_glosario(raiz, hashes):
    """Versión y tamaño del glosario de sinónimos, para que `estado` y `doctor` lo reporten sin abrir el tarball."""
    ruta = raiz / "glosario.json"
    if not ruta.is_file():
        return None
    g = json.loads(ruta.read_text(encoding="utf-8"))
    return {"version": g.get("version"), "entradas": len(g.get("entradas", [])), "sha256": hashes.get("glosario.json")}


def construir(raiz, salida, version, fecha, materializar=True):
    raiz, salida = Path(raiz), Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    rels = archivos_a_empaquetar(raiz)
    contenidos = {r: (raiz / r).read_bytes() for r in rels}
    capas = _capas_con_herencia(raiz)
    if materializar:
        for anio, sigla in capas:
            for r in [r for r in contenidos if r.startswith(f"leyes/{anio}/{sigla}/")]:
                del contenidos[r]
            contenidos.update(materializar_capa(raiz, anio, sigla))
        rels = sorted(contenidos)
    hashes = {r: sha256_bytes(b) for r, b in contenidos.items()}
    contenido_sha = sha256_bytes("\n".join(f"{hashes[r]}  {r}" for r in rels).encode("utf-8"))
    integridad = json.dumps({"esquema": ESQUEMA, "contenido_sha256": contenido_sha, "archivos": hashes},
                            ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8") + b"\n"

    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=9, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
            for nombre, datos in [("INTEGRIDAD.json", integridad)] + [(r, contenidos[r]) for r in rels]:
                ti = tarfile.TarInfo(nombre)
                ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = len(datos), 0, 0o644, 0, 0, "", ""
                tar.addfile(ti, io.BytesIO(datos))
    tgz = buf.getvalue()
    (salida / NOMBRE_TARBALL).write_bytes(tgz)

    leyes = resumen_leyes(raiz)
    manifest = {
        "esquema": ESQUEMA_CAPAS if capas and not materializar else ESQUEMA,
        "materializado": bool(materializar),
        "capas": len(capas),
        "version": version,
        "publicado": fecha,
        "contenido_sha256": contenido_sha,
        "tarball": {"nombre": NOMBRE_TARBALL, "sha256": sha256_bytes(tgz), "bytes": len(tgz)},
        "archivos": len(rels),
        "anios": sorted({l["anio_vigencia"] for l in leyes}),
        "leyes": leyes,
        "proyectos": resumen_proyectos(raiz),
        "anexos": resumen_anexos(raiz),
        "rmf": resumen_rmf(raiz),
        "glosario": resumen_glosario(raiz, hashes),
    }
    (salida / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", default=str(RAIZ / "build" / "datos"))
    ap.add_argument("--version", required=True, help="p. ej. 2026.11.02 (o 2026.11.02.2 si hay mas de una el mismo dia)")
    ap.add_argument("--fecha", help="AAAA-MM-DD de publicacion (por omision, la de la version)")
    ap.add_argument("--raiz", default=str(RAIZ))
    ap.add_argument("--sin-materializar", action="store_true",
                    help="lleva las capas tal cual (solo los artículos que cambian) en lugar de la vista completa de cada año; "
                         "los clientes anteriores a las capas no lo pueden leer (el manifest sube a esquema 2)")
    a = ap.parse_args(argv)
    fecha = a.fecha or "-".join(a.version.split(".")[:3])
    m = construir(a.raiz, a.salida, a.version, fecha, materializar=not a.sin_materializar)
    print(f"version {m['version']} | {m['archivos']} archivos | tarball {m['tarball']['bytes']} bytes | sha256 {m['tarball']['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
