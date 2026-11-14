// Versiones por capas: el único punto que resuelve qué archivo es un artículo (o el índice, o los transitorios) en un año.
// Equivale a leyes_mx/versiones.py; el modelo está en docs/criterio-anios.md.
//   leyes/<año>/<SIGLA>/ es una CAPA. La base es completa y no lleva marcas; una capa posterior guarda solo los artículos que
//   cambian y su _meta.json trae hereda_de, vigente_desde y articulos_modificados. La vista de una ley en el año Y es, para cada
//   artículo, el archivo de la capa más reciente de la cadena hereda_de que lo contenga. Un paquete materializado (cada año
//   completo) y un árbol sin capas se leen igual: una capa sin hereda_de es completa.
// Las capas se ordenan por vigente_desde (no por nombre de carpeta). Sin dependencias: lo usa también el build del sitio.
import fs from "node:fs";
import path from "node:path";
import { idDesdeArchivo } from "./ids.js";

const esDir = (p) => { try { return fs.statSync(p).isDirectory(); } catch { return false; } };
const esArchivo = (p) => { try { return fs.statSync(p).isFile(); } catch { return false; } };
const leerMeta = (dir) => { try { return JSON.parse(fs.readFileSync(path.join(dir, "_meta.json"), "utf8")); } catch { return null; } };

/** Años (carpetas numéricas) de leyes/. */
export function anios(raiz) {
  const base = path.join(raiz, "leyes");
  if (!esDir(base)) return [];
  return fs.readdirSync(base).filter((n) => /^\d+$/.test(n) && esDir(path.join(base, n))).map(Number).sort((a, b) => a - b);
}

function dirSigla(base, sigla) {
  if (!esDir(base)) return null;
  const n = fs.readdirSync(base).find((x) => x.toUpperCase() === String(sigla).toUpperCase() && esDir(path.join(base, x)));
  return n ? path.join(base, n) : null;
}

/** Carpetas de las leyes con capa (tienen _meta.json) en ese año, en orden alfabético. */
export function siglas(raiz, anio) {
  const base = path.join(raiz, "leyes", String(anio));
  if (!esDir(base)) return [];
  return fs.readdirSync(base).filter((n) => esArchivo(path.join(base, n, "_meta.json"))).sort();
}

/** La capa de una ley en un año ({anio, dir, meta, heredeDe, vigenteDesde, clave}) o null si ese año no la tiene. */
export function capa(raiz, sigla, anio) {
  const d = dirSigla(path.join(raiz, "leyes", String(anio)), sigla);
  const meta = d ? leerMeta(d) : null;
  if (!meta) return null;
  return { anio: Number(anio), dir: d, meta, heredeDe: meta.hereda_de ?? null, vigenteDesde: meta.vigente_desde ?? null };
}

const claveCapa = (c) => [c.vigenteDesde ?? "", c.anio];
const comparar = (a, b) => { const x = claveCapa(a), y = claveCapa(b); return x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : x[1] - y[1]; };

/** Todas las capas de una ley, ordenadas por vigente_desde (la base primero). */
export function capas(raiz, sigla) {
  return anios(raiz).map((a) => capa(raiz, sigla, a)).filter(Boolean).sort(comparar);
}

/** Capas que forman la vista de la ley en ese año, de la más reciente a la base. Vacía si ese año no tiene la ley. */
export function cadena(raiz, sigla, anio) {
  const res = [], vistas = new Set();
  let c = capa(raiz, sigla, anio);
  while (c && !vistas.has(c.anio)) {
    res.push(c);
    vistas.add(c.anio);
    c = c.heredeDe !== null ? capa(raiz, sigla, c.heredeDe) : null;
  }
  return res;
}

export const tiene = (raiz, sigla, anio) => capa(raiz, sigla, anio) !== null;

/** Una ley en un año: sus archivos resueltos a través de la cadena de capas. */
export class Vista {
  constructor(sigla, anio, cadena_) {
    this.sigla = sigla;
    this.anio = Number(anio);
    this.cadena = cadena_;
  }

  get meta() { return this.cadena[0].meta; }

  /** Carpeta de la capa del año pedido (la más reciente de la cadena). */
  get dir() { return this.cadena[0].dir; }

  /** Ruta del archivo (art-0028.md, transitorios.md, _indice.md...) en la capa más reciente que lo tenga, o null. */
  archivo(nombre) {
    for (const c of this.cadena) {
      const p = path.join(c.dir, nombre);
      if (esArchivo(p)) return p;
    }
    return null;
  }

  /** Nombres de archivo de artículo de la vista (la capa más reciente gana), en el orden de readdir ordenado por nombre. */
  nombres() {
    const set = new Set();
    for (const c of this.cadena) for (const f of fs.readdirSync(c.dir)) if (idDesdeArchivo(f) !== null) set.add(f);
    return [...set].sort();
  }

  esHeredado(ruta) { return path.dirname(ruta) !== this.dir; }

  /** Front matter tal como se presenta en esta vista: un artículo heredado muestra el año pedido y la última reforma de la ley en la vista. */
  ajustar(fm, ruta) {
    if (!this.esHeredado(ruta)) return fm;
    const r = { ...fm, vigencia_anio: this.anio };
    if (this.meta.ultima_reforma_dof) r.ultima_reforma_dof = this.meta.ultima_reforma_dof;
    return r;
  }
}

/** Vista de una ley en un año, o null si ese año no tiene la ley. */
export function vista(raiz, sigla, anio) {
  const ch = cadena(raiz, sigla, anio);
  return ch.length ? new Vista(ch[0].meta.sigla ?? sigla, anio, ch) : null;
}
