#!/usr/bin/env python3
"""Empaqueta los datos (leyes/, proyectos/ sin PDF, tablas/, rmf/, decretos/, fuentes.json y glosario.json) para el Release de datos.

Genera en --salida:
  leyes-mx-datos.tar.gz   tarball determinista (mismo contenido -> mismos bytes -> mismo sha256)
  manifest.json           version, fecha, sha256 del tarball, ultima reforma DOF por ley

Dentro del tarball va INTEGRIDAD.json con el sha256 de cada archivo; el cliente (npx leyes-mx) lo verifica.
Uso: python3 scripts/empaquetar_datos.py --salida build/datos --version 2026.11.02 [--fecha 2026-11-02]
"""
import argparse
import gzip
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOMBRE_TARBALL = "leyes-mx-datos.tar.gz"
ESQUEMA = 1


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


def construir(raiz, salida, version, fecha):
    raiz, salida = Path(raiz), Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    rels = archivos_a_empaquetar(raiz)
    contenidos = {r: (raiz / r).read_bytes() for r in rels}
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
        "esquema": ESQUEMA,
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
    a = ap.parse_args(argv)
    fecha = a.fecha or "-".join(a.version.split(".")[:3])
    m = construir(a.raiz, a.salida, a.version, fecha)
    print(f"version {m['version']} | {m['archivos']} archivos | tarball {m['tarball']['bytes']} bytes | sha256 {m['tarball']['sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
