// Lectura de artículos y metadatos. Equivale a leyes_mx/store.py (sin SQLite).
import fs from "node:fs";
import path from "node:path";
import { normalizarId, nombreArchivo, idDesdeArchivo, compararIds } from "./ids.js";
import { leerConfig, resolverDatos } from "./rutas.js";
import { Glosario } from "./glosario.js";

export const AVISO_PROYECTO = "PROYECTO: este texto NO es ley vigente. Solo lo será si y cuando se publique en el DOF, " +
  "y a partir de la fecha que indique el decreto.";
export const AVISO_GENERAL = "Texto informativo de la Cámara de Diputados; no sustituye al DOF. La fuente oficial prevalece.";

export class SinDatos extends Error {}

export function parseFrontMatter(texto) {
  if (!texto.startsWith("---\n")) return [{}, texto];
  const fin = texto.indexOf("\n---\n", 4);
  if (fin < 0) return [{}, texto];
  const fm = {};
  for (const linea of texto.slice(4, fin).split("\n")) {
    const i = linea.indexOf(":");
    if (i < 0) continue;
    const k = linea.slice(0, i).trim();
    const v = linea.slice(i + 1).trim();
    try { fm[k] = JSON.parse(v); } catch { fm[k] = v; }
  }
  return [fm, texto.slice(fin + 5)];
}

// Equivalente a str.strip() de Python (espacio Unicode, no solo ASCII).
const strip = (s) => s.replace(/^[\s\u0085]+|[\s\u0085]+$/gu, "");

export function textoArticulo(cuerpo) {
  return strip(cuerpo.split("\n## Notas de reforma", 1)[0]);
}

export function notas(cuerpo) {
  if (!cuerpo.includes("\n## Notas de reforma")) return [];
  const bloque = cuerpo.split("\n## Notas de reforma").slice(1).join("\n## Notas de reforma");
  return bloque.split("\n").filter((l) => l.startsWith("- ")).map((l) => strip(l.slice(2)));
}

const esDir = (p) => { try { return fs.statSync(p).isDirectory(); } catch { return false; } };

export class Almacen {
  constructor(raiz) {
    this.raiz = raiz;
  }

  static abrir() {
    const d = resolverDatos();
    if (!d) throw new SinDatos("No hay datos instalados. Ejecuta: npx leyes-mx instalar (o npx leyes-mx actualizar).");
    const a = new Almacen(d.raiz);
    a.origen = d.origen;
    a.version = d.version;
    return a;
  }

  /** Glosario de sinónimos (glosario.json en la raíz de los datos). null si no existe o no es válido: la búsqueda funciona igual. */
  glosario() {
    if (this._glosario === undefined) this._glosario = Glosario.cargar(this.raiz);
    return this._glosario;
  }

  anios() {
    const base = path.join(this.raiz, "leyes");
    if (!esDir(base)) return [];
    return fs.readdirSync(base).filter((n) => /^\d+$/.test(n) && esDir(path.join(base, n))).map(Number).sort((a, b) => a - b);
  }

  anioProyectos() {
    const base = path.join(this.raiz, "proyectos");
    if (!esDir(base)) return [];
    return fs.readdirSync(base).filter((n) => /^\d+$/.test(n) && esDir(path.join(base, n))).map(Number).sort((a, b) => a - b);
  }

  dirLey(base, sigla) {
    if (!esDir(base)) return null;
    const n = fs.readdirSync(base).find((x) => x.toUpperCase() === String(sigla).toUpperCase() && esDir(path.join(base, x)));
    return n ? path.join(base, n) : null;
  }

  /** Año de vigencia más reciente con datos y no posterior al año en curso; config.json puede fijarlo. */
  anioPorDefecto(sigla = null, hoy = new Date()) {
    const fijo = leerConfig().anio;
    const cands = this.anios().filter((a) => !sigla || this.dirLey(path.join(this.raiz, "leyes", String(a)), sigla));
    if (!cands.length) return null;
    if (fijo && cands.includes(Number(fijo))) return Number(fijo);
    const pasados = cands.filter((a) => a <= hoy.getFullYear());
    return pasados.length ? Math.max(...pasados) : Math.min(...cands);
  }

  leerMeta(dirLey) {
    try { return JSON.parse(fs.readFileSync(path.join(dirLey, "_meta.json"), "utf8")); } catch { return null; }
  }

  siglasDisponibles(anio) {
    const base = path.join(this.raiz, "leyes", String(anio));
    if (!esDir(base)) return [];
    return fs.readdirSync(base).filter((n) => fs.existsSync(path.join(base, n, "_meta.json"))).sort();
  }

  listarLeyes({ incluirProyectos = false } = {}) {
    const res = [];
    for (const a of this.anios()) {
      const base = path.join(this.raiz, "leyes", String(a));
      for (const n of fs.readdirSync(base).sort()) {
        const meta = this.leerMeta(path.join(base, n));
        if (meta) res.push({ sigla: meta.sigla, nombre: meta.nombre_oficial, tipo: meta.tipo, anio_vigencia: a, ultima_reforma_dof: meta.ultima_reforma_dof,
          articulos: meta.articulos_extraidos, estatus: "vigente", fecha_descarga: meta.fecha_descarga });
      }
    }
    if (incluirProyectos) {
      for (const a of this.anioProyectos()) {
        const base = path.join(this.raiz, "proyectos", String(a));
        for (const n of fs.readdirSync(base).sort()) {
          const d = path.join(base, n);
          if (esDir(d) && fs.existsSync(path.join(d, "_meta.json"))) {
            const cuenta = fs.readdirSync(d).filter((f) => /^art-.*\.md$/.test(f)).length;
            res.push({ sigla: n.toUpperCase(), nombre: null, anio_vigencia: a, ultima_reforma_dof: null, articulos: cuenta, estatus: "proyecto", aviso: AVISO_PROYECTO });
          }
        }
      }
    }
    return res;
  }

  estadoReforma(anio = null) {
    const anios = this.anioProyectos();
    const a = anio ?? (anios.length ? Math.max(...anios) : null);
    const ruta = a === null ? null : path.join(this.raiz, "proyectos", String(a), "estado.json");
    if (!ruta || !fs.existsSync(ruta)) return { anio: a, disponible: false, aviso: "sin seguimiento para ese año" };
    const d = JSON.parse(fs.readFileSync(ruta, "utf8"));
    d.disponible = true;
    d.aviso = AVISO_PROYECTO;
    return d;
  }

  // ---- Anexo 8 de la RMF (tarifas de ISR vigentes del año): rmf/<anio>/anexo-8/<id>.md
  aniosAnexo() {
    const base = path.join(this.raiz, "rmf");
    if (!esDir(base)) return [];
    return fs.readdirSync(base).filter((n) => /^\d+$/.test(n) && esDir(path.join(base, n, "anexo-8"))).map(Number).sort((a, b) => a - b);
  }

  listarTarifas(anio = null) {
    const anios = this.aniosAnexo();
    const a = anio ?? (anios.length ? Math.max(...anios) : null);
    if (a === null || !anios.includes(Number(a))) return [];
    const dir = path.join(this.raiz, "rmf", String(a), "anexo-8");
    let orden = [];
    try { orden = JSON.parse(fs.readFileSync(path.join(dir, "_meta.json"), "utf8")).tarifas_detalle.map((t) => t.id); } catch { /* sin meta: orden alfabético */ }
    const res = [];
    for (const n of fs.readdirSync(dir).filter((x) => x.endsWith(".md") && !x.startsWith("_")).sort()) {
      const [fm] = parseFrontMatter(fs.readFileSync(path.join(dir, n), "utf8"));
      res.push({ id: fm.id, apartado: fm.apartado, titulo: fm.titulo, documento: fm.documento, anio_vigencia: fm.vigencia_anio,
        publicado_dof: fm.publicado_dof, fuente_url: fm.fuente_url, filas: fm.filas, ruta: `rmf/${a}/anexo-8/${n}` });
    }
    const pos = (id) => { const i = orden.indexOf(id); return i < 0 ? orden.length : i; };
    return res.sort((x, y) => pos(x.id) - pos(y.id) || x.ruta.localeCompare(y.ruta));
  }

  /** Por id exacto, apartado ("B-V", "B.V") o prefijo de id. null si no existe; {ambiguo:[...]} si varias. Nunca inventa. */
  obtenerTarifa(clave, anio = null) {
    const todas = this.listarTarifas(anio);
    const c = String(clave).trim().replace(/\./g, "-").replace(/\s+/g, "-").toLowerCase();
    let m = todas.filter((t) => String(t.id).toLowerCase() === c);
    if (!m.length) m = todas.filter((t) => String(t.apartado).replace(/\./g, "-").toLowerCase() === c);
    if (!m.length) m = todas.filter((t) => String(t.id).toLowerCase().startsWith(`${c}-`));
    if (!m.length) return null;
    if (m.length > 1) return { ambiguo: m.map((t) => ({ id: t.id, titulo: t.titulo })) };
    const t = m[0];
    const [fm, cuerpo] = parseFrontMatter(fs.readFileSync(path.join(this.raiz, t.ruta), "utf8"));
    return { documento: fm.documento, apartado: fm.apartado, id: fm.id, titulo: fm.titulo, aplicable_a: fm.aplicable_a ?? [],
      vigencia_anio: fm.vigencia_anio, publicado_dof: fm.publicado_dof, fecha_firma: fm.fecha_firma, fuente_url: fm.fuente_url,
      fecha_descarga: fm.fecha_descarga, sha256_fuente: fm.sha256_fuente, estatus: fm.estatus, texto: strip(cuerpo), ruta: t.ruta };
  }

  ficha(fm, cuerpo, ruta) {
    const d = {
      ley: fm.ley ?? null, nombre_ley: fm.nombre_ley ?? null, articulo: fm.articulo ?? null,
      anio_vigencia: fm.vigencia_anio ?? null, ultima_reforma_dof: fm.ultima_reforma_dof ?? null,
      estatus: fm.estatus ?? null, fuente_url: fm.fuente_url ?? null, fecha_descarga: fm.fecha_descarga ?? null,
      texto: strip(cuerpo), ruta: path.relative(this.raiz, ruta).split(path.sep).join("/"),
    };
    if (fm.estatus !== "vigente" && fm.estatus !== "derogado") {
      d.aviso = AVISO_PROYECTO;
      d.estado_proyecto = fm.estado_proyecto || fm.estatus;
      d.entrada_en_vigor = fm.entrada_en_vigor ?? null;
    }
    return d;
  }

  advertencias(dirLey, id) {
    const meta = this.leerMeta(dirLey);
    if (!meta) return [];
    return (meta.advertencias || []).filter((a) => !a.articulos?.length || a.articulos.includes(id)).map((a) => a.texto);
  }

  /** Devuelve la ficha o null si no existe (nunca inventa). Lanza Error si el artículo no es reconocible. */
  obtenerArticulo(ley, articulo, { anio = null, incluirProyectos = false } = {}) {
    const id = normalizarId(articulo);
    if (!id) throw new Error(`articulo no reconocido: ${JSON.stringify(articulo)}`);
    const a = anio || this.anioPorDefecto(ley);
    if (a !== null) {
      const d = this.dirLey(path.join(this.raiz, "leyes", String(a)), ley);
      if (d) {
        const f = path.join(d, nombreArchivo(id));
        if (fs.existsSync(f)) {
          const [fm, cuerpo] = parseFrontMatter(fs.readFileSync(f, "utf8"));
          const ficha = this.ficha(fm, textoArticulo(cuerpo), f);
          ficha.notas_reforma = notas(cuerpo);
          ficha.advertencias = this.advertencias(d, id);
          return ficha;
        }
      }
    }
    if (incluirProyectos) {
      for (const ya of [...this.anioProyectos()].reverse()) {
        const d = this.dirLey(path.join(this.raiz, "proyectos", String(ya)), ley);
        if (d && fs.existsSync(path.join(d, nombreArchivo(id)))) {
          const f = path.join(d, nombreArchivo(id));
          const [fm, cuerpo] = parseFrontMatter(fs.readFileSync(f, "utf8"));
          return this.ficha(fm, textoArticulo(cuerpo), f);
        }
      }
    }
    return null;
  }

  obtenerTransitorios(ley, anio = null) {
    const a = anio || this.anioPorDefecto(ley);
    if (a === null) return null;
    const d = this.dirLey(path.join(this.raiz, "leyes", String(a)), ley);
    if (!d) return null;
    const f = path.join(d, "transitorios.md");
    if (!fs.existsSync(f)) return null;
    const [fm, cuerpo] = parseFrontMatter(fs.readFileSync(f, "utf8"));
    return { ley: fm.ley ?? null, nombre_ley: fm.nombre_ley ?? null, anio_vigencia: fm.vigencia_anio ?? null, ultima_reforma_dof: fm.ultima_reforma_dof ?? null,
      estatus: fm.estatus ?? null, fuente_url: fm.fuente_url ?? null, fecha_descarga: fm.fecha_descarga ?? null, texto: strip(cuerpo),
      advertencias: this.advertencias(d, null) , ruta: path.relative(this.raiz, f).split(path.sep).join("/") };
  }

  /** Recorre todos los artículos: callback({fm, cuerpo, texto, ruta, proyecto}). */
  *recorrer({ proyectos = false } = {}) {
    const bases = [path.join(this.raiz, "leyes")];
    if (proyectos) bases.push(path.join(this.raiz, "proyectos"));
    for (const base of bases) {
      if (!esDir(base)) continue;
      for (const anio of fs.readdirSync(base).sort()) {
        const da = path.join(base, anio);
        if (!/^\d+$/.test(anio) || !esDir(da)) continue;
        for (const sig of fs.readdirSync(da).sort()) {
          const dl = path.join(da, sig);
          if (!esDir(dl)) continue;
          for (const f of fs.readdirSync(dl).sort()) {
            if (idDesdeArchivo(f) === null) continue;
            const ruta = path.join(dl, f);
            const [fm, cuerpo] = parseFrontMatter(fs.readFileSync(ruta, "utf8"));
            yield { fm, cuerpo, texto: textoArticulo(cuerpo), ruta };
          }
        }
      }
    }
  }
}

export { compararIds };
