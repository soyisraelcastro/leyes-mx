// Identificadores de artículo. Port fiel de leyes_mx/ids.py (misma convención, mismo comportamiento).
// "113 E", "113-e", "28 bis", "32-B-bis", la Ñ se escribe NN en el nombre de archivo.

export const PALABRAS = ["bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "nonies", "decies",
  "quintus", "sextus", "septimus", "octavus", "nonus", "decimus", "undecimus", "duodecimus"];

const ACENTOS = { "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u" };

function palabra(tok) {
  const t = tok.toLowerCase().replace(/[áéíóúü]/g, (c) => ACENTOS[c]);
  return PALABRAS.includes(t) ? t : null;
}

/** '113 E', '113-e', '28 Bis', '1o.-A', '32-B Bis' -> '113-E', '113-E', '28-bis', '1-A', '32-B-bis'. null si no es válido. */
export function normalizarId(texto) {
  if (texto === null || texto === undefined) return null;
  let s = String(texto).trim();
  s = s.replace(/^(art[íi]culo|art\.?)\s*/iu, "");
  const m = /^(\d+)(?!\d)\s*[oº°]?(?![a-zA-Z])\.?(.*)$/.exec(s) || /^(\d+)(.*)$/.exec(s);
  if (!m) return null;
  const num = parseInt(m[1], 10);
  let resto = m[2];
  if (/^\s*[A-Za-zÑñ]\s*$/.test(resto)) resto = "-" + resto.trim();
  const toks = resto.split(/[\s\-.]+/).filter(Boolean);
  const partes = [];
  for (const t of toks) {
    const p = palabra(t);
    if (p) partes.push(p);
    else if (/^[A-Za-zÑñ]$/.test(t)) partes.push(t.toUpperCase());
    else return null;
  }
  return [String(num), ...partes].join("-");
}

export function partesId(id) {
  const toks = id.split("-");
  return [parseInt(toks[0], 10), toks.slice(1)];
}

export function nombreArchivo(id) {
  const [num, partes] = partesId(id);
  const p = partes.map((x) => (x === "Ñ" ? "NN" : x));
  return "art-" + [String(num).padStart(4, "0"), ...p].join("-") + ".md";
}

export function idDesdeArchivo(nombre) {
  const m = /^art-(\d{4})((?:-[A-Za-z]+)*)\.md$/.exec(nombre);
  if (!m) return null;
  return normalizarId(String(parseInt(m[1], 10)) + m[2].replaceAll("-NN", "-Ñ"));
}

export function claveOrden(id) {
  const [num, partes] = partesId(id);
  const k = partes.map((p) => (PALABRAS.includes(p) ? [1, PALABRAS.indexOf(p)] : [0, p === "Ñ" ? "N".charCodeAt(0) + 0.5 : p.charCodeAt(0)]));
  return [num, k];
}

export function compararIds(a, b) {
  const [na, ka] = claveOrden(a);
  const [nb, kb] = claveOrden(b);
  if (na !== nb) return na - nb;
  for (let i = 0; i < Math.min(ka.length, kb.length); i++) {
    if (ka[i][0] !== kb[i][0]) return ka[i][0] - kb[i][0];
    if (ka[i][1] !== kb[i][1]) return ka[i][1] - kb[i][1];
  }
  return ka.length - kb.length;
}
