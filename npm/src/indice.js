// Búsqueda léxica local sin dependencias: índice invertido en memoria con BM25.
// Sin acentos, prefijos para términos de más de 2 letras, primero todas las palabras (AND) y si no hay nada, cualquiera (OR).
// Se justifica no usar minisearch: son ~2500 documentos, el índice se arma en menos de un segundo y así no hay otra dependencia.
import path from "node:path";

export const plegar = (s) => s.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "");
export const tokens = (s) => plegar(s).match(/[\p{L}\p{N}_]+/gu) || [];

const ABIERTOS = new Set(["vigente", "derogado"]);

export class Indice {
  constructor(almacen, { proyectos = false } = {}) {
    this.docs = [];
    this.post = new Map(); // término -> Map(docId -> frecuencia)
    let total = 0;
    for (const { fm, texto, ruta } of almacen.recorrer({ proyectos })) {
      const cuerpo = texto.replace(/^> \*\*PROYECTO[^\n]*\n+/gm, "").replace(/^# Art[^\n]*\n+/, "").trim();
      const id = this.docs.length;
      const toks = tokens(cuerpo + " " + (fm.ley ?? "") + " " + (fm.articulo ?? ""));
      this.docs.push({ ley: fm.ley, articulo: fm.articulo, anio: fm.vigencia_anio, estatus: fm.estatus, reforma: fm.ultima_reforma_dof ?? null,
        ruta: path.relative(almacen.raiz, ruta).split(path.sep).join("/"), texto: cuerpo, len: toks.length });
      total += toks.length;
      for (const t of toks) {
        let m = this.post.get(t);
        if (!m) this.post.set(t, (m = new Map()));
        m.set(id, (m.get(id) || 0) + 1);
      }
    }
    this.promedio = total / Math.max(1, this.docs.length);
    this.terminos = [...this.post.keys()].sort();
  }

  expandir(tok) {
    if (tok.length <= 2) return this.post.has(tok) ? [tok] : [];
    // prefijo: búsqueda binaria del primer término >= tok
    let lo = 0, hi = this.terminos.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (this.terminos[mid] < tok) lo = mid + 1; else hi = mid; }
    const out = [];
    for (let i = lo; i < this.terminos.length && this.terminos[i].startsWith(tok); i++) out.push(this.terminos[i]);
    return out;
  }

  puntuar(toksConsulta, modo, permitido) {
    const N = this.docs.length;
    const porToken = toksConsulta.map((t) => this.expandir(t));
    let candidatos = null;
    const puntos = new Map();
    for (const exp of porToken) {
      const docsToken = new Map();
      for (const term of exp) {
        const mp = this.post.get(term);
        const idf = Math.log(1 + (N - mp.size + 0.5) / (mp.size + 0.5));
        for (const [d, f] of mp) {
          if (!permitido(this.docs[d])) continue;
          const len = this.docs[d].len;
          const s = idf * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * len / this.promedio));
          docsToken.set(d, (docsToken.get(d) || 0) + s);
        }
      }
      for (const [d, s] of docsToken) puntos.set(d, (puntos.get(d) || 0) + s);
      if (modo === "AND") {
        candidatos = candidatos === null ? new Set(docsToken.keys()) : new Set([...candidatos].filter((d) => docsToken.has(d)));
      }
    }
    const ids = modo === "AND" ? [...(candidatos || [])] : [...puntos.keys()];
    return ids.map((d) => [d, puntos.get(d) || 0]).sort((a, b) => b[1] - a[1] || a[0] - b[0]);
  }

  buscar(consulta, { ley = null, anio = null, incluirProyectos = false, limite = 10, anioDefecto = null } = {}) {
    const toks = tokens(consulta);
    if (!toks.length) return [];
    const permitido = (d) => {
      if (ley && String(d.ley).toUpperCase() !== String(ley).toUpperCase()) return false;
      const abierto = ABIERTOS.has(d.estatus);
      if (!incluirProyectos && !abierto) return false;
      const a = anio || anioDefecto;
      if (a !== null && abierto && d.anio !== a) return false;
      return true;
    };
    for (const modo of ["AND", "OR"]) {
      const r = this.puntuar(toks, modo, permitido).slice(0, limite);
      if (r.length) {
        return r.map(([d, score]) => {
          const x = this.docs[d];
          const o = { ley: x.ley, articulo: x.articulo, anio_vigencia: x.anio, ultima_reforma_dof: x.reforma, estatus: x.estatus,
            fragmento: fragmento(x.texto, consulta), ruta: x.ruta, relevancia: Math.round(score * 100) / 100 };
          return o;
        });
      }
    }
    return [];
  }
}

export function fragmento(texto, q, ancho = 220) {
  const t = texto.replace(/\s+/g, " ");
  const plano = plegar(t);
  let pos = -1;
  for (const w of tokens(q)) { pos = plano.indexOf(w); if (pos >= 0) break; }
  pos = Math.max(0, pos - 60);
  return (pos ? "... " : "") + t.slice(pos, pos + ancho) + (pos + ancho < t.length ? " ..." : "");
}
