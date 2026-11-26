// Búsqueda léxica local sin dependencias: índice invertido en memoria con BM25.
// Sin acentos, prefijos para términos de más de 2 letras, primero todas las palabras (AND) y si no hay nada, cualquiera (OR).
// Se justifica no usar minisearch: son ~2500 documentos, el índice se arma en menos de un segundo y así no hay otra dependencia.
import path from "node:path";

export const plegar = (s) => s.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "");
export const tokens = (s) => plegar(s).match(/[\p{L}\p{N}_]+/gu) || [];

const ABIERTOS = new Set(["vigente", "derogado"]);

// Palabras vacías: solo se quitan de la consulta (no del índice) y solo si queda al menos una palabra con contenido.
// Sin esto, "para" se expande por prefijo a "paraestatal", "paraprocesales", etc., y arrastra artículos sin relación.
// "no" se conserva a propósito: "no deducibles" no es lo mismo que "deducibles".
export const VACIAS = new Set(["a", "al", "ante", "con", "como", "cual", "cuales", "de", "del", "el", "ella", "en", "es", "esta", "este", "la", "las", "le", "les", "lo", "los", "mas",
  "me", "mi", "o", "para", "pero", "por", "que", "se", "si", "sin", "sobre", "son", "su", "sus", "te", "tu", "u", "un", "una", "uno", "unas", "unos", "y"]);
export const tokensConsulta = (s) => {
  const t = tokens(s);
  const util = t.filter((x) => !VACIAS.has(x));
  return util.length ? util : t;
};

export const claveArticulo = (ley, articulo) => `${String(ley).toUpperCase()}|${plegar(String(articulo)).replace(/\s+/g, "-")}`;

/** Un artículo que el glosario relaciona con la consulta sube BONO_REFERENCIA veces el mejor puntaje léxico (no lo reemplaza). */
export const BONO_REFERENCIA = 0.8;

/**
 * Raíz del plural para la búsqueda por prefijo: "actualizaciones" -> "actualizacion", "deducibles" -> "deducible",
 * "trabajadores" -> "trabajador", "personas" -> "persona". Solo quita la terminación de plural; "partes" o "meses" no se tocan.
 */
export function singular(t) {
  if (t.length < 5 || /\d/.test(t)) return t;
  if (/(ci|si|xi)ones$|dades$|[aeiou][rl]es$/.test(t)) return t.slice(0, -2);
  if (/[aeiou]s$|bles$/.test(t)) return t.slice(0, -1);
  return t;
}

/** Peso de un término agregado por el glosario respecto de uno escrito por quien consulta (1). */
export const PESO_AGREGADO = 0.6;

export class Indice {
  constructor(almacen, { proyectos = false } = {}) {
    this.docs = [];
    this.porClave = new Map(); // "LISR|28" (ley en mayúsculas, artículo plegado) -> [docId]; para los artículos que cita el glosario
    this.post = new Map(); // término -> Map(docId -> frecuencia)
    let total = 0;
    for (const { fm, texto, ruta } of almacen.recorrer({ proyectos })) {
      const cuerpo = texto.replace(/^> \*\*PROYECTO[^\n]*\n+/gm, "").replace(/^# Art[^\n]*\n+/, "").trim();
      const id = this.docs.length;
      const toks = tokens(cuerpo + " " + (fm.ley ?? "") + " " + (fm.articulo ?? ""));
      this.docs.push({ ley: fm.ley, articulo: fm.articulo, anio: fm.vigencia_anio, estatus: fm.estatus, reforma: fm.ultima_reforma_dof ?? null,
        ruta: path.relative(almacen.raiz, ruta).split(path.sep).join("/"), texto: cuerpo, len: toks.length, ...(fm._texto !== undefined ? { fm } : {}) });
      total += toks.length;
      const clave = claveArticulo(fm.ley, fm.articulo);
      (this.porClave.get(clave) || this.porClave.set(clave, []).get(clave)).push(id);
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
    tok = singular(tok);
    if (tok.length <= 2) return this.post.has(tok) ? [tok] : [];
    // prefijo: búsqueda binaria del primer término >= tok
    let lo = 0, hi = this.terminos.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (this.terminos[mid] < tok) lo = mid + 1; else hi = mid; }
    const out = [];
    for (let i = lo; i < this.terminos.length && this.terminos[i].startsWith(tok); i++) out.push(this.terminos[i]);
    return out;
  }

  /** Puntúa un término (con expansión por prefijo): Map(docId -> BM25 * peso). */
  puntosToken(tok, peso, permitido) {
    const N = this.docs.length;
    const docsToken = new Map();
    for (const term of this.expandir(tok)) {
      const mp = this.post.get(term);
      const idf = Math.log(1 + (N - mp.size + 0.5) / (mp.size + 0.5));
      for (const [d, f] of mp) {
        if (!permitido(this.docs[d])) continue;
        const len = this.docs[d].len;
        const s = peso * idf * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * len / this.promedio));
        docsToken.set(d, (docsToken.get(d) || 0) + s);
      }
    }
    return docsToken;
  }

  /**
   * AND: todas las palabras de la consulta; OR: cualquiera. Los términos `agregados` (del glosario) nunca son
   * obligatorios: solo suman puntaje, así que una consulta que ya tenía resultados no los pierde por ampliarse.
   * Devuelve { lista: [[docId, puntaje]] ordenada, marcados: Set de docId que subieron por una referencia del glosario }.
   */
  puntuar(toksConsulta, modo, permitido, agregados = [], referencias = []) {
    let candidatos = null;
    const puntos = new Map();
    for (const tok of toksConsulta) {
      const docsToken = this.puntosToken(tok, 1, permitido);
      for (const [d, s] of docsToken) puntos.set(d, (puntos.get(d) || 0) + s);
      // en AND, una palabra que no está en ningún artículo (una sigla, un anglicismo) no vuelve imposible la búsqueda
      if (modo === "AND" && this.expandir(tok).length) {
        candidatos = candidatos === null ? new Set(docsToken.keys()) : new Set([...candidatos].filter((d) => docsToken.has(d)));
      }
    }
    for (const tok of agregados) {
      for (const [d, s] of this.puntosToken(tok, PESO_AGREGADO, permitido)) {
        if (modo === "AND" && !candidatos?.has(d)) continue;
        puntos.set(d, (puntos.get(d) || 0) + s);
      }
    }
    const ids = new Set(modo === "AND" ? [...(candidatos || [])] : [...puntos.keys()]);
    // artículos que cita el glosario: siempre elegibles (respetando ley, año y proyectos) y con bono sobre el mejor puntaje léxico
    const marcados = new Set();
    if (referencias.length && (ids.size || modo === "OR")) {
      const mejor = Math.max(1, ...[...ids].map((d) => puntos.get(d) || 0));
      for (const r of referencias) {
        for (const d of this.porClave.get(claveArticulo(r.ley, r.articulo)) || []) {
          if (!permitido(this.docs[d]) || marcados.has(d)) continue;
          marcados.add(d);
          ids.add(d);
          puntos.set(d, (puntos.get(d) || 0) + BONO_REFERENCIA * mejor);
        }
      }
    }
    const lista = [...ids].map((d) => [d, puntos.get(d) || 0]).sort((a, b) => b[1] - a[1] || a[0] - b[0]);
    return { lista, marcados };
  }

  buscar(consulta, opciones = {}) {
    return this.buscarConDetalle(consulta, opciones).resultados;
  }

  /**
   * Como buscar, pero devuelve también la ampliación que hizo el glosario (si se pasa uno), para que la respuesta la declare.
   * `glosario` es una instancia de Glosario o null (sin ampliar).
   */
  buscarConDetalle(consulta, { ley = null, anio = null, incluirProyectos = false, limite = 10, anioDefecto = null, glosario = null } = {}) {
    const toks = tokensConsulta(consulta);
    if (!toks.length) return { resultados: [], ampliacion: null };
    const permitido = (d) => {
      if (ley && String(d.ley).toUpperCase() !== String(ley).toUpperCase()) return false;
      const abierto = ABIERTOS.has(d.estatus);
      if (!incluirProyectos && !abierto) return false;
      const a = anio || anioDefecto;
      if (a !== null && abierto && d.anio !== a) return false;
      return true;
    };
    const ampliacion = glosario ? glosario.expandir(consulta) : null;
    // las siglas que el texto no usa (ISR, PTU, CFDI...) se sustituyen; si la consulta era solo la sigla, la sustituyen sus equivalentes
    let base = ampliacion ? toks.filter((t) => !ampliacion.quitar.includes(t)) : toks;
    if (!base.length && ampliacion) base = ampliacion.terminos;
    const agregados = ampliacion ? ampliacion.terminos.filter((t) => !base.includes(t)) : [];
    const referencias = ampliacion ? ampliacion.entradas.filter((e) => e.relacionar).flatMap((e) => e.articulos) : [];
    const amp = ampliacion && ampliacion.entradas.length ? ampliacion : null;
    for (const modo of ["AND", "OR"]) {
      const { lista, marcados } = this.puntuar(base, modo, permitido, agregados, referencias);
      const r = lista.slice(0, limite);
      if (r.length) {
        const resultados = r.map(([d, score]) => {
          const x = this.docs[d];
          const o = { ley: x.ley, articulo: x.articulo, anio_vigencia: x.anio, ultima_reforma_dof: x.reforma, estatus: x.estatus,
            fragmento: fragmento(x.texto, [consulta, ...agregados].join(" "), 220, base), ruta: x.ruta, relevancia: Math.round(score * 100) / 100 };
          if (marcados.has(d)) o.relacionado_por_glosario = true;
          return o;
        });
        return { resultados, ampliacion: amp };
      }
    }
    return { resultados: [], ampliacion: amp };
  }
}

export function fragmento(texto, q, ancho = 220, prioritarios = null) {
  const t = texto.replace(/\s+/g, " ");
  const plano = plegar(t);
  let pos = -1;
  // primero las palabras que escribió quien consulta (sin las vacías); luego las agregadas por el glosario
  for (const w of [...(prioritarios || []), ...tokensConsulta(q)]) { pos = plano.indexOf(w); if (pos >= 0) break; }
  pos = Math.max(0, pos - 60);
  return (pos ? "... " : "") + t.slice(pos, pos + ancho) + (pos + ancho < t.length ? " ..." : "");
}

/** Palabras de pregunta que tampoco dicen de qué trata una regla (solo se quitan al buscar en reglas). */
const PREGUNTAS = new Set(["quien", "quienes", "cuando", "donde", "cuanto", "cuantos", "existe", "hay"]);

/** Cuántas veces cuenta cada palabra del título y de la ubicación de una regla: el encabezado dice de qué trata. */
export const PESO_TITULO = 3;
export const PESO_UBICACION = 2;

/**
 * Índice de las reglas de la RMF. Va aparte del de las leyes a propósito: así el ranking de los artículos no cambia, las
 * reglas no compiten con ellos y una resolución de más de mil reglas no los entierra.
 * A diferencia del de leyes indexa el encabezado (título y ubicación), donde la RMF nombra el régimen o la materia, y no
 * exige todas las palabras: pondera cada resultado por la proporción de palabras de la consulta que contiene.
 */
export class IndiceReglas extends Indice {
  constructor(almacen) {
    super({ raiz: almacen.raiz, *recorrer() {
      for (const { fm, texto, ruta } of almacen.recorrerReglas()) {
        // "regla" y "RMF" para que una pregunta que las escriba no pierda cobertura
        const clave = ["regla RMF miscelánea", ...Array(PESO_TITULO).fill(fm.titulo ?? ""), ...Array(PESO_UBICACION).fill(fm.ubicacion ?? "")].join(" ");
        yield { fm: { ...fm, articulo: fm.regla, _encabezado: clave, _texto: texto }, texto: `${clave}\n${texto}`, ruta };
      }
    } });
    this.docs.forEach((d) => { d.texto = d.fm._texto; d.titulo = d.fm.titulo ?? null; d.ubicacion = d.fm.ubicacion ?? null; d.publicacion = d.fm.publicacion_dof ?? null; delete d.fm; });
  }

  /**
   * Las variantes de una palabra (presenta, presentar, presentación) cuentan como UN término: se suman sus frecuencias y el
   * IDF sale de cuántas reglas traen alguna. Sumar el puntaje de cada variante inflaría las palabras comunes.
   */
  puntosToken(tok, peso, permitido) {
    const frec = new Map();
    for (const term of this.expandir(tok)) for (const [d, f] of this.post.get(term)) frec.set(d, (frec.get(d) || 0) + f);
    const idf = Math.log(1 + (this.docs.length - frec.size + 0.5) / (frec.size + 0.5));
    const res = new Map();
    for (const [d, f] of frec) {
      if (permitido(this.docs[d])) res.set(d, peso * idf * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * this.docs[d].len / this.promedio)));
    }
    return res;
  }

  /** [{ley, regla, titulo, ubicacion, anio_vigencia, publicacion_dof, estatus, fragmento, ruta, relevancia, relacionado_por_glosario?}] */
  buscarReglas(consulta, { anio = null, limite = 5, glosario = null, ampliacion = undefined } = {}) {
    let toks = [...new Set(tokensConsulta(consulta))];
    const sinPreguntas = toks.filter((t) => !PREGUNTAS.has(t));
    if (sinPreguntas.length) toks = sinPreguntas;
    if (!toks.length) return [];
    const permitido = (d) => ABIERTOS.has(d.estatus) && (anio === null || d.anio === anio);
    const amp = ampliacion !== undefined ? ampliacion : glosario ? glosario.expandir(consulta) : null;
    // una sigla que la RMF no usa (RESICO) cuenta como su nombre en la RMF, y todo el nombre cuenta como UNA palabra:
    // si no, "régimen simplificado de confianza" pesaría el triple que la materia por la que se pregunta
    const parte = new Map(); // palabra -> fracción de concepto
    for (const e of amp ? amp.entradas : []) {
      const ausentes = e.sustituye.filter((t) => !this.expandir(t).length);
      if (!ausentes.length || !e.agregadosReglas?.length) continue;
      const nombre = [...new Set(e.agregadosReglas.flatMap((x) => tokensConsulta(x)))].filter((t) => !toks.includes(t));
      for (const t of nombre) parte.set(t, 1 / nombre.length);
      toks = [...toks.filter((t) => !ausentes.includes(t)), ...nombre];
    }
    // lo que el glosario agrega pensando en las reglas, y además lo de las leyes; nada de eso es obligatorio
    // (de una entrada con términos propios para la RMF se usan solo esos)
    const deLeyes = amp ? amp.entradas.filter((e) => !e.agregadosReglas?.length).flatMap((e) => e.agregados.flatMap((x) => tokensConsulta(x))) : [];
    const agregados = amp ? [...new Set([...(amp.terminosReglas || []), ...deLeyes])].filter((t) => !toks.includes(t)) : [];
    const puntos = new Map(), cubre = new Map();
    let buscables = 0;
    for (const t of toks) {
      const peso = parte.get(t) ?? 1;
      const m = this.puntosToken(t, peso, permitido);
      if (!m.size) continue;
      buscables += peso;
      for (const [d, x] of m) { puntos.set(d, (puntos.get(d) || 0) + x); cubre.set(d, (cubre.get(d) || 0) + peso); }
    }
    for (const t of agregados) {
      const peso = amp.terminosReglas?.includes(t) ? PESO_AGREGADO : PESO_AGREGADO / 2;
      for (const [d, x] of this.puntosToken(t, peso, permitido)) puntos.set(d, (puntos.get(d) || 0) + x);
    }
    for (const [d, x] of puntos) puntos.set(d, x * (0.4 + 0.6 * (cubre.get(d) || 0) / (buscables || 1)));
    const marcados = new Set();
    const mejor = Math.max(1, ...puntos.values());
    for (const r of amp ? amp.entradas.filter((e) => e.relacionar).flatMap((e) => e.reglas || []) : []) {
      for (const d of this.porClave.get(claveArticulo("RMF", r.regla)) || []) {
        if (!permitido(this.docs[d]) || marcados.has(d)) continue;
        marcados.add(d);
        puntos.set(d, (puntos.get(d) || 0) + BONO_REFERENCIA * mejor);
      }
    }
    return [...puntos].sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, limite).map(([d, score]) => {
      const x = this.docs[d];
      const o = { ley: x.ley, regla: x.articulo, titulo: x.titulo, ubicacion: x.ubicacion, anio_vigencia: x.anio, publicacion_dof: x.publicacion, estatus: x.estatus,
        fragmento: fragmento(x.texto, [consulta, ...agregados].join(" "), 220, toks), ruta: x.ruta, relevancia: Math.round(score * 100) / 100 };
      if (marcados.has(d)) o.relacionado_por_glosario = true;
      return o;
    });
  }
}

/** Busca en leyes y en reglas. `ley`: sin valor, ambas; "RMF", solo reglas; cualquier otra, solo esa ley. */
export function buscarTodo(almacen, { leyes, reglas }, consulta, { ley = null, anio = null, incluirProyectos = false, limite = 10, glosario = null } = {}) {
  const soloRmf = String(ley ?? "").toUpperCase() === "RMF";
  const r = soloRmf ? { resultados: [], ampliacion: null } : leyes().buscarConDetalle(consulta, { ley, anio, incluirProyectos, limite, anioDefecto: almacen.anioPorDefecto(ley), glosario });
  let encontradas = [];
  let ampliacion = r.ampliacion;
  if (soloRmf || !ley) {
    const amp = glosario ? glosario.expandir(consulta) : null;
    if (amp?.entradas.length) ampliacion = amp;
    const anios = almacen.aniosReglas();
    if (anios.length) encontradas = reglas().buscarReglas(consulta, { anio: anio ?? Math.max(...anios), limite: soloRmf ? limite : Math.min(limite, 5), ampliacion: amp });
  }
  return { resultados: r.resultados, reglas: encontradas, ampliacion };
}
