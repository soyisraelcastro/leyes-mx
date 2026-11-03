// Glosario de sinónimos contables: amplía la consulta de `buscar` con los términos que usa la ley.
// La búsqueda es léxica (BM25): "actualizaciones" no encuentra "accesorios de las contribuciones". El glosario cierra
// esa brecha de forma transparente: cada ampliación se declara en la respuesta y ninguna es obligatoria para el resultado.
//
// Formato de glosario.json (se versiona en la raíz del repo y viaja en el paquete de datos):
//   { "esquema": 1, "version": "2026-11-02", "entradas": [ {
//       "id": "actualizacion",
//       "disparadores": ["actualizacion", "factor de actualizacion"],   // frases; basta una. "a + b": ambas, en cualquier orden
//       "agregar": ["accesorios", "recargos"],                         // palabras o frases que se suman a la consulta
//       "sustituir": ["isr"],                                          // (opcional) palabras de la consulta que se quitan: siglas que el texto no usa
//       "relacionar": false,                                           // (opcional) false: sus artículos no suben en el ranking, solo documentan
//       "articulos": [{ "ley": "CFF", "articulo": "17-A", "evidencia": "no será deducible ni acreditable" }],
//       "nota": "por qué la ley dice esto con otras palabras" } ] }
// Los disparadores se comparan sin acentos y sin distinguir mayúsculas; una palabra de 5 o más letras también coincide
// con sus derivadas (el disparador "actualizacion" coincide con "actualizaciones"). `articulos` y `evidencia` no cambian
// el ranking: documentan (y scripts/validar.py y la prueba de npm verifican contra el texto) por qué existe la entrada.
import fs from "node:fs";
import path from "node:path";
import { tokens } from "./indice.js";

export const ESQUEMA_GLOSARIO = 1;
export const ARCHIVO_GLOSARIO = "glosario.json";
const MAX_TERMINOS = 16;

/** Problemas de estructura (lista vacía si está bien). No toca los artículos; eso lo verifica validar.py y la prueba. */
export function validarEstructura(d) {
  const p = [];
  if (!d || typeof d !== "object") return ["el glosario no es un objeto JSON"];
  if (d.esquema !== ESQUEMA_GLOSARIO) p.push(`esquema ${JSON.stringify(d.esquema)}: esta versión entiende el ${ESQUEMA_GLOSARIO}`);
  if (!Array.isArray(d.entradas) || !d.entradas.length) return [...p, "sin entradas"];
  const ids = new Set();
  d.entradas.forEach((e, i) => {
    const n = `entrada ${i + 1}${e?.id ? ` (${e.id})` : ""}`;
    if (!e || typeof e !== "object") return p.push(`${n}: no es un objeto`);
    if (!/^[a-z0-9-]+$/.test(e.id || "")) p.push(`${n}: id inválido (minúsculas, números y guiones)`);
    if (ids.has(e.id)) p.push(`${n}: id repetido`);
    ids.add(e.id);
    for (const k of ["disparadores", "agregar"]) if (!Array.isArray(e[k]) || !e[k].length || e[k].some((x) => typeof x !== "string" || !x.trim())) p.push(`${n}: ${k} debe ser una lista de textos no vacía`);
    if (e.sustituir !== undefined && (!Array.isArray(e.sustituir) || e.sustituir.some((x) => typeof x !== "string" || tokens(x).length !== 1))) p.push(`${n}: sustituir debe ser una lista de palabras sueltas`);
    if (e.relacionar !== undefined && typeof e.relacionar !== "boolean") p.push(`${n}: relacionar debe ser true o false`);
    if (typeof e.nota !== "string" || e.nota.trim().length < 20) p.push(`${n}: falta la nota (por qué existe la entrada)`);
    if (!Array.isArray(e.articulos) || !e.articulos.length) p.push(`${n}: falta articulos (al menos uno con evidencia)`);
    for (const a of e.articulos || []) if (!a?.ley || !a?.articulo || !a?.evidencia) p.push(`${n}: cada artículo lleva ley, articulo y evidencia`);
  });
  return p;
}

export class Glosario {
  constructor(datos, ruta = null) {
    this.datos = datos;
    this.ruta = ruta;
    this.version = datos.version ?? null;
    this.entradas = datos.entradas.map((e) => ({
      ...e,
      _disparadores: e.disparadores.map((f) => f.split("+").map((x) => tokens(x)).filter((t) => t.length)),
    }));
  }

  /** Lee <raiz>/glosario.json. Devuelve null si no existe o no es válido (el buscador funciona igual sin glosario). */
  static cargar(raiz) {
    const ruta = path.join(raiz, ARCHIVO_GLOSARIO);
    let datos;
    try { datos = JSON.parse(fs.readFileSync(ruta, "utf8")); } catch { return null; }
    return validarEstructura(datos).length ? null : new Glosario(datos, ruta);
  }

  /** Diagnóstico para doctor y estado: { existe, valido, entradas, version, problemas }. */
  static diagnosticar(raiz) {
    const ruta = path.join(raiz, ARCHIVO_GLOSARIO);
    if (!fs.existsSync(ruta)) return { existe: false };
    let datos;
    try { datos = JSON.parse(fs.readFileSync(ruta, "utf8")); } catch (e) { return { existe: true, valido: false, problemas: [`JSON inválido: ${e.message}`] }; }
    const problemas = validarEstructura(datos);
    return { existe: true, valido: !problemas.length, problemas, entradas: datos.entradas?.length ?? 0, version: datos.version ?? null };
  }

  /**
   * Qué agrega el glosario a esta consulta.
   * Devuelve { terminos: [palabras plegadas], agregados: [textos tal como están en el glosario], quitar: [palabras de la consulta que
   * se sustituyen], entradas: [{id, nota, articulos, relacionar, agregados, sustituye}] }.
   */
  expandir(consulta) {
    const q = tokens(consulta);
    const hay = (frase) => {
      for (let i = 0; i + frase.length <= q.length; i++) {
        if (frase.every((t, j) => q[i + j] === t || (t.length >= 5 && q[i + j].startsWith(t)))) return true;
      }
      return false;
    };
    const entradas = [], agregados = [], terminos = [], quitar = [];
    const yaEscritos = new Set(q);
    for (const e of this.entradas) {
      if (!e._disparadores.some((d) => d.every(hay))) continue;
      const nuevos = e.agregar.filter((a) => tokens(a).some((t) => !yaEscritos.has(t)));
      const sustituye = (e.sustituir || []).flatMap((x) => tokens(x)).filter((t) => q.includes(t));
      for (const t of sustituye) if (!quitar.includes(t)) quitar.push(t);
      entradas.push({ id: e.id, nota: e.nota, articulos: e.articulos.map((a) => ({ ley: a.ley, articulo: a.articulo })), relacionar: e.relacionar !== false, agregados: nuevos, sustituye });
      for (const a of nuevos) {
        if (agregados.includes(a)) continue;
        agregados.push(a);
        for (const t of tokens(a)) if (!terminos.includes(t) && !yaEscritos.has(t)) terminos.push(t);
      }
    }
    if (terminos.length > MAX_TERMINOS) terminos.length = MAX_TERMINOS;
    return { terminos, agregados, quitar, entradas };
  }
}
