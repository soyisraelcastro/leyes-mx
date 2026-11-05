"""Tablas que el PDF de la Cámara trae como imagen (pdftotext no las ve).

Se guardan aparte en tablas/<anio>/<SIGLA>/tablas.json (el pipeline regenera leyes/ completo,
así que nada manual puede vivir ahí) y se inyectan al construir cada artículo.
"""
import json
import re
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


def _val(s):
    """Número de una celda: quita $, % y comas; 'N o más' y similares toman el primer número."""
    m = re.search(r"-?\d[\d,]*\.?\d*", s.replace("$", ""))
    return float(m.group(0).replace(",", "")) if m else None


def verificar_lineal_por_fila(t):
    """Cada fila (tras la etiqueta) es una progresión lineal entre su primer y último valor (tolerancia de redondeo)."""
    errs, tol = [], t.get("tolerancia", 0.0015)
    for f in t["filas"]:
        v = [_val(x) for x in f[1:]]
        n = len(v) - 1
        for k in range(1, n):
            esp = v[0] + k * (v[n] - v[0]) / n
            if abs(esp - v[k]) > tol:
                errs.append(f"{t['id']} fila {f[0]!r} columna {k + 1}: {v[k]} vs lineal {esp:.4f}")
    return errs


def verificar_matriz_pension(t):
    """Pensión garantizada: cada fila lineal en semanas (tolerancia 1 peso) y creciente con la edad y con el salario."""
    errs, tol = [], t.get("tolerancia", 1.0)
    filas = t["filas"]
    for f in filas:
        v = [_val(x) for x in f[2:]]
        n = len(v) - 1
        for k in range(1, n):
            esp = v[0] + k * (v[n] - v[0]) / n
            if abs(esp - v[k]) > tol:
                errs.append(f"{t['id']} {f[0]} / {f[1]} columna {k + 1}: {v[k]} vs lineal {esp:.1f}")
    for i in range(1, len(filas)):
        a, b = filas[i - 1], filas[i]
        for k in range(2, len(b)):
            if _val(b[k]) < _val(a[k]):
                errs.append(f"{t['id']} {b[0]} / {b[1]} columna {k - 1}: {b[k]} es menor que la fila anterior {a[k]}")
    return errs


def verificar_progresion(t):
    """Filas que son progresiones aritméticas de paso fijo (semanas de cotización por año)."""
    errs, paso = [], t["paso"]
    for i, f in enumerate(t["filas"]):
        v = [_val(x) for x in f[1:]]
        for k in range(1, len(v)):
            if abs(v[k] - v[k - 1] - paso) > 1e-9:
                errs.append(f"{t['id']} fila {f[0]!r} columna {k + 1}: paso {v[k] - v[k - 1]} != {paso}")
        if i and abs(v[0] - _val(t["filas"][i - 1][1]) - paso) > 1e-9:
            errs.append(f"{t['id']} fila {f[0]!r}: no sube {paso} respecto a la anterior")
    return errs


def verificar_monotona(t):
    """Valores (última columna) que bajan fila a fila: cuota social por rango salarial."""
    v = [_val(f[-1]) for f in t["filas"]]
    errs = [f"{t['id']} fila {i + 1}: {v[i]} no es menor que {v[i - 1]}" for i in range(1, len(v)) if v[i] >= v[i - 1]]
    if "escalon" in t:  # si la tabla baja siempre lo mismo, se exige
        errs += [f"{t['id']} fila {i + 1}: baja {v[i - 1] - v[i]:.2f} y el escalón es {t['escalon']}"
                 for i in range(1, len(v)) if abs((v[i - 1] - v[i]) - t["escalon"]) > 1e-9]
    return errs


_VERIFICADORES = {
    "tarifa": verificar_tarifa,
    "lineal-por-fila": verificar_lineal_por_fila,
    "matriz-pension": verificar_matriz_pension,
    "progresion": verificar_progresion,
    "monotona-decreciente": verificar_monotona,
}


def verificar(t):
    """Despacha según t['tipo'] (por omisión 'tarifa'). Un tipo desconocido es un error, no un pase."""
    f = _VERIFICADORES.get(t.get("tipo", "tarifa"))
    if f is None:
        return [f"{t['id']}: tipo de verificación desconocido {t.get('tipo')!r}"]
    return f(t)


def a_markdown(t):
    if t.get("solo_imagen"):
        return f"**{t['titulo']}** (imagen del PDF, sin transcribir): ![{t['titulo']}](tablas/{t['imagen']})"
    cab = "| " + " | ".join(t["columnas"]) + " |\n|" + "---|" * len(t["columnas"]) + "\n"
    filas = "".join("| " + " | ".join(r) + " |\n" for r in t["filas"])
    return (f"**{t['titulo']}** (el PDF la publica como imagen; transcrita y verificada, "
            f"imagen original: tablas/{t['imagen']})\n\n{cab}{filas}")


def inyectar(articulo_id, cuerpo, datos, estricto=True, excluir=()):
    """Inserta cada tabla justo después del párrafo que contiene su ancla. Devuelve (cuerpo, [ids]).

    Varias tablas con la misma ancla quedan en el orden en que aparecen en tablas.json.
    Con estricto=False (transitorios, que se trocean por decreto) una ancla que no está en este
    bloque se ignora en lugar de fallar, y las tablas de `excluir` ya se colocaron en otro bloque.
    """
    puestas = []
    for t in (datos or {}).get("tablas", []):
        if t["articulo"] != articulo_id or t.get("solo_imagen") or t["id"] in excluir:
            continue
        if not t.get("ancla"):
            continue
        parrafos = cuerpo.split("\n\n")
        for i, p in enumerate(parrafos):
            if t["ancla"] in p:
                j = i + 1
                while j < len(parrafos) and parrafos[j].startswith("**") and "transcrita y verificada" in parrafos[j]:
                    j += 1
                parrafos.insert(j, a_markdown(t).rstrip())
                puestas.append(t["id"])
                break
        else:
            if estricto:
                raise ValueError(f"ancla no encontrada en art. {articulo_id}: {t['ancla']!r}")
        cuerpo = "\n\n".join(parrafos)
    return cuerpo, puestas


def copiar_imagenes(datos, carpeta_tablas, dest):
    if not datos:
        return
    (dest / "tablas").mkdir(exist_ok=True)
    for t in datos["tablas"]:
        shutil.copy2(carpeta_tablas / t["imagen"], dest / "tablas" / t["imagen"])


def bloque_transitorios(datos, colocadas=()):
    sol = [t for t in (datos or {}).get("tablas", []) if t["articulo"] == "transitorios" and t["id"] not in colocadas]
    if not sol:
        return ""
    return "\n## Tablas del PDF publicadas solo como imagen\n\n" + "\n\n".join(a_markdown(t) for t in sol) + "\n"
