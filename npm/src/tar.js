// Lector mínimo de tar (ustar, GNU y pax) sobre un Buffer ya descomprimido. Sin dependencias.
import path from "node:path";

const texto = (b, ini, len) => {
  const s = b.subarray(ini, ini + len);
  const z = s.indexOf(0);
  return s.subarray(0, z < 0 ? s.length : z).toString("utf8");
};
const octal = (b, ini, len) => parseInt(texto(b, ini, len).trim() || "0", 8);

/** Devuelve [{ nombre, datos }] solo de archivos regulares. Rechaza rutas absolutas o con "..". */
export function leerTar(buf) {
  const res = [];
  let pos = 0;
  let largo = null;
  while (pos + 512 <= buf.length) {
    const h = buf.subarray(pos, pos + 512);
    if (h.every((x) => x === 0)) break;
    let nombre = texto(h, 0, 100);
    const prefijo = texto(h, 345, 155);
    if (prefijo && texto(h, 257, 5) === "ustar") nombre = prefijo + "/" + nombre;
    const tam = octal(h, 124, 12);
    const tipo = String.fromCharCode(h[156] || 48);
    pos += 512;
    const datos = buf.subarray(pos, pos + tam);
    pos += Math.ceil(tam / 512) * 512;
    if (tipo === "L") { largo = texto(datos, 0, datos.length); continue; }
    if (tipo === "x") {
      const m = /\d+ path=([^\n]*)\n/.exec(datos.toString("utf8"));
      if (m) largo = m[1];
      continue;
    }
    if (largo) { nombre = largo; largo = null; }
    if (tipo === "0" || tipo === "\0" || tipo === "7") {
      const norm = path.posix.normalize(nombre);
      if (norm.startsWith("/") || norm.split("/").includes("..") || /^[A-Za-z]:/.test(norm)) throw new Error(`ruta insegura en el tarball: ${nombre}`);
      res.push({ nombre: norm, datos: Buffer.from(datos) });
    } else if (tipo !== "5" && tipo !== "g") {
      throw new Error(`tipo de entrada no admitido en el tarball: ${JSON.stringify(tipo)} (${nombre})`);
    }
  }
  return res;
}
