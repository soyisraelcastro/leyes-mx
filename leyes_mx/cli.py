"""CLI: leyes-mx obtener|buscar|listar|estado|obtener-anexo  (tambien: python3 scripts/buscar.py ...)"""
import argparse
import json
import sys

from . import store, anexos


def _imprimir_ficha(f, texto=True):
    print(f"{f['ley']} art. {f['articulo']} | vigencia {f['anio_vigencia']} | última reforma DOF {f['ultima_reforma_dof']} | estatus: {f['estatus']}")
    if f.get("aviso"):
        print(f">>> {f['aviso']}")
        if f.get("entrada_en_vigor"):
            print(f">>> Entraría en vigor: {f['entrada_en_vigor']}")
    for adv in f.get("advertencias", []):
        if adv not in f.get("texto", ""):  # las "en_archivo" ya vienen dentro del texto
            print(f">>> ADVERTENCIA: {adv}")
    print(f"fuente: {f['fuente_url']} (descargado {f['fecha_descarga']})")
    if texto:
        print()
        print(f["texto"])
        print()
        print(store.AVISO_GENERAL)


def _imprimir_tarifa(t, texto=True):
    print(f"{t['documento']} | apartado {t['apartado']} | vigencia {t['vigencia_anio']} | DOF {t['publicado_dof']} (firmado {t['fecha_firma']}) | estatus: {t['estatus']}")
    print(f"{t['titulo']}")
    print(f"aplicable a: {'; '.join(t['aplicable_a'])}")
    print(f"fuente: {t['fuente_url']} (descargado {t['fecha_descarga']}, sha256 {t['sha256_fuente'][:12]}...)")
    if texto:
        print()
        print(t["texto"])


def _cmd_anexo(a):
    try:
        if not a.tarifa:
            lista = anexos.listar_anexo(a.anexo, a.anio)
            if a.json:
                print(json.dumps(lista, ensure_ascii=False, indent=2)); return 0 if lista else 1
            if not lista:
                print(f"NO VERIFICADO: el Anexo {a.anexo} no está en la base (año {a.anio or 'más reciente'}).", file=sys.stderr); return 1
            for x in lista:
                print(f"{x['apartado']:7} {x['id']:38} {x['titulo']}")
            print(f"\n{len(lista)} tarifas | {lista[0]['documento']} | DOF {lista[0]['publicado_dof']} | vigencia {lista[0]['anio_vigencia']}")
            return 0
        t = anexos.obtener_anexo(a.anexo, a.tarifa, a.anio)
    except ValueError as ex:
        print(f"error: {ex}", file=sys.stderr); return 2
    if not t:
        print(f"NO VERIFICADO: la tarifa {a.tarifa} del Anexo {a.anexo} no está en la base. No se inventa texto: consultar el DOF / sat.gob.mx.", file=sys.stderr)
        return 1
    if "ambiguo" in t:
        print(f"La clave {a.tarifa} corresponde a varias tarifas; usar el id exacto:", file=sys.stderr)
        for x in t["ambiguo"]:
            print(f"  {x['id']}  {x['titulo']}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(t, ensure_ascii=False, indent=2)); return 0
    _imprimir_tarifa(t)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="leyes-mx", description="Consulta de leyes fiscales y laborales de México (un archivo por artículo).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("obtener", help="artículo exacto: obtener LISR 113-E")
    o.add_argument("ley"); o.add_argument("articulo", nargs="+")
    o.add_argument("--anio", type=int); o.add_argument("--incluir-proyectos", action="store_true"); o.add_argument("--json", action="store_true")
    b = sub.add_parser("buscar", help='palabras clave: buscar "recargos deducibles" --ley LISR')
    b.add_argument("texto", nargs="+"); b.add_argument("--ley"); b.add_argument("--anio", type=int)
    b.add_argument("--incluir-proyectos", action="store_true"); b.add_argument("--limite", type=int, default=10); b.add_argument("--json", action="store_true")
    l = sub.add_parser("listar", help="leyes disponibles"); l.add_argument("--incluir-proyectos", action="store_true"); l.add_argument("--json", action="store_true")
    e = sub.add_parser("estado", help="estado de la reforma (proyectos/<año>)"); e.add_argument("--anio", type=int, default=2027); e.add_argument("--json", action="store_true")
    x = sub.add_parser("obtener-anexo", help="tarifas del Anexo 8 de la RMF: obtener-anexo 8 B-V (sin tarifa: las lista)")
    x.add_argument("anexo", type=int); x.add_argument("tarifa", nargs="?")
    x.add_argument("--anio", type=int); x.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "obtener-anexo":
        return _cmd_anexo(a)

    if a.cmd == "obtener":
        art = " ".join(a.articulo)
        try:
            f = store.obtener_articulo(a.ley, art, a.anio, a.incluir_proyectos)
        except ValueError as ex:
            print(f"error: {ex}", file=sys.stderr); return 2
        if not f:
            print(f"NO VERIFICADO: {a.ley.upper()} art. {art} no está en la base (año {a.anio or store.anio_por_defecto(a.ley)}). "
                  "No se inventa texto: consultar la fuente oficial (DOF / diputados.gob.mx).", file=sys.stderr)
            return 1
        print(json.dumps(f, ensure_ascii=False, indent=2)) if a.json else _imprimir_ficha(f)
        return 0
    if a.cmd == "buscar":
        r = store.buscar(" ".join(a.texto), a.ley, a.anio, a.incluir_proyectos, a.limite)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2)); return 0 if r else 1
        if not r:
            print("Sin resultados (no verificado)."); return 1
        for x in r:
            marca = "  [PROYECTO, NO ES LEY VIGENTE]" if x["estatus"] not in ("vigente", "derogado") else ("  [derogado]" if x["estatus"] == "derogado" else "")
            print(f"{x['ley']} art. {x['articulo']} | vigencia {x['anio_vigencia']} | última reforma DOF {x['ultima_reforma_dof']}{marca}")
            print(f"   {x['fragmento']}")
        return 0
    if a.cmd == "listar":
        r = store.listar_leyes(incluir_proyectos=a.incluir_proyectos)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=2)); return 0
        for x in r:
            print(f"{x['sigla']:6} {x['anio_vigencia']} {x['estatus']:8} arts={x['articulos']:<5} última reforma DOF {x['ultima_reforma_dof']}  {x['nombre'] or ''}")
        return 0
    if a.cmd == "estado":
        r = store.estado_reforma(a.anio)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    sys.exit(main())
