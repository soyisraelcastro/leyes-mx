"""Tablas que el PDF de la Cámara trae como imagen (pdftotext no las ve).

Se guardan aparte en tablas/<anio>/<SIGLA>/tablas.json (el pipeline regenera leyes/ completo,
así que nada manual puede vivir ahí) y se inyectan al construir cada artículo.
"""
import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cargar(sigla, anio, raiz=None):
    ruta = Path(raiz or RAIZ) / "tablas" / str(anio) / sigla.upper() / "tablas.json"
    if not ruta.exists():
        return None, ruta.parent
    return json.loads(ruta.read_text(encoding="utf-8")), ruta.parent


def _num(s):
    return float(s.replace(",", ""))


def verificar_tarifa(t):
    """Devuelve lista de errores: rangos contiguos y cuota fija recalculada desde la fila previa."""
    errs, f = [], t["filas"]
    for i in range(1, len(f)):
        pi, ps, pc, pr = f[i - 1]
        ni, _ns, nc, _nr = f[i]
        if abs(_num(ni) - (_num(ps) + 0.01)) > 0.005:
            errs.append(f"{t['id']} fila {i+1}: límite inferior {ni} no sigue a {ps}")
        esp = _num(pc) + (_num(ps) - _num(pi)) * _num(pr) / 100
        if abs(esp - _num(nc)) > 0.02:
            errs.append(f"{t['id']} fila {i+1}: cuota fija {nc}, recalculada {esp:.2f}")
    return errs


def a_markdown(t):
    if t.get("solo_imagen"):
        return f"**{t['titulo']}** (imagen del PDF, sin transcribir): ![{t['titulo']}](tablas/{t['imagen']})"
    cab = "| " + " | ".join(t["columnas"]) + " |\n|" + "---|" * len(t["columnas"]) + "\n"
    filas = "".join("| " + " | ".join(r) + " |\n" for r in t["filas"])
    return (f"**{t['titulo']}** (el PDF la publica como imagen; transcrita y verificada, "
            f"imagen original: tablas/{t['imagen']})\n\n{cab}{filas}")


def inyectar(articulo_id, cuerpo, datos):
    """Inserta cada tabla justo después del párrafo que contiene su ancla. Devuelve (cuerpo, [ids])."""
    puestas = []
    for t in (datos or {}).get("tablas", []):
        if t["articulo"] != articulo_id or t.get("solo_imagen"):
            continue
        parrafos = cuerpo.split("\n\n")
        for i, p in enumerate(parrafos):
            if t["ancla"] in p:
                parrafos.insert(i + 1, a_markdown(t).rstrip())
                puestas.append(t["id"])
                break
        else:
            raise ValueError(f"ancla no encontrada en art. {articulo_id}: {t['ancla']!r}")
        cuerpo = "\n\n".join(parrafos)
    return cuerpo, puestas


def copiar_imagenes(datos, carpeta_tablas, dest):
    if not datos:
        return
    (dest / "tablas").mkdir(exist_ok=True)
    for t in datos["tablas"]:
        shutil.copy2(carpeta_tablas / t["imagen"], dest / "tablas" / t["imagen"])


def bloque_transitorios(datos):
    sol = [t for t in (datos or {}).get("tablas", []) if t["articulo"] == "transitorios"]
    if not sol:
        return ""
    return "\n## Tablas del PDF publicadas solo como imagen\n\n" + "\n\n".join(a_markdown(t) for t in sol) + "\n"
