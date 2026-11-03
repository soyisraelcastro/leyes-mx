// La skill "leyes-mx" (formato Agent Skills: una carpeta con SKILL.md). Viaja dentro del paquete npm, en npm/skills/leyes-mx/.
// Dónde se instala (verificado en la documentación oficial, ver docs/npx.md):
//   Claude Code  ~/.claude/skills/leyes-mx/SKILL.md   (code.claude.com/docs/en/skills; con CLAUDE_CONFIG_DIR, esa carpeta)
//   Codex        ~/.agents/skills/leyes-mx/SKILL.md   (learn.chatgpt.com/docs/build-skills; $CODEX_HOME/skills es la ruta antigua, aún se lee)
//   Claude Desktop  no hay carpeta documentada: solo se sube un .zip desde la app (npx leyes-mx skill --zip)
// Misma disciplina que el registro del servidor: solo toca lo suyo (lleva una marca), respalda antes de cambiar y se puede quitar.
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";
import { dirClaudeCode } from "./clientes.js";
import { carpetaBase } from "./rutas.js";
import { VERSION } from "./version.js";

export const SKILL_NOMBRE = "leyes-mx";
export const MARCA = ".leyes-mx-skill.json";
export const CLIENTES_CON_CARPETA = ["claude-code", "codex"];
export const ZIP_NOMBRE = "leyes-mx-skill.zip";

export const carpetaFuente = () => fileURLToPath(new URL(`../skills/${SKILL_NOMBRE}/`, import.meta.url)).replace(/[\\/]$/, "");

export function destinoSkill(cliente) {
  if (cliente === "claude-code") return path.join(dirClaudeCode(), "skills", SKILL_NOMBRE);
  if (cliente === "codex") return path.join(os.homedir(), ".agents", "skills", SKILL_NOMBRE);
  return null;
}

function archivos(dir) {
  const res = [];
  const rec = (d, pref) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      if (e.name === MARCA || e.name === ".DS_Store") continue;
      if (e.isDirectory()) rec(path.join(d, e.name), `${pref}${e.name}/`);
      else if (e.isFile()) res.push(`${pref}${e.name}`);
    }
  };
  rec(dir, "");
  return res;
}

/** sha256 del contenido de una carpeta de skill (nombres y bytes, sin la marca). */
export function huella(dir) {
  const h = crypto.createHash("sha256");
  for (const rel of archivos(dir)) { h.update(rel + "\0"); h.update(fs.readFileSync(path.join(dir, ...rel.split("/")))); h.update("\0"); }
  return h.digest("hex");
}

export function parseSkillMd(texto) {
  const m = /^---\n([\s\S]*?)\n---\n/.exec(texto);
  if (!m) return null;
  const fm = {};
  for (const l of m[1].split("\n")) { const i = l.indexOf(":"); if (i > 0) fm[l.slice(0, i).trim()] = l.slice(i + 1).trim(); }
  return fm;
}

/** Revisa la skill que viaja en el paquete: formato de Agent Skills y límites de claude.ai (nombre = carpeta, descripción de hasta 200 caracteres). */
export function verificarFuente() {
  const dir = carpetaFuente();
  const p = [];
  const ruta = path.join(dir, "SKILL.md");
  if (!fs.existsSync(ruta)) return ["falta SKILL.md en el paquete"];
  const t = fs.readFileSync(ruta, "utf8");
  const fm = parseSkillMd(t);
  if (!fm) return ["SKILL.md sin front matter (--- name / description ---)"];
  if (fm.name !== SKILL_NOMBRE) p.push(`name ${JSON.stringify(fm.name)} debe ser ${SKILL_NOMBRE}`);
  if (path.basename(dir) !== fm.name) p.push("name debe coincidir con el nombre de la carpeta");
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(fm.name || "") || (fm.name || "").length > 64) p.push("name: minúsculas, números y guiones, hasta 64 caracteres");
  if (!fm.description) p.push("falta description");
  else if (fm.description.length > 200) p.push(`description de ${fm.description.length} caracteres: claude.ai admite hasta 200`);
  if (t.split("\n").length > 500) p.push("SKILL.md pasa de 500 líneas");
  return p;
}

function leerMarca(dir) {
  try { return JSON.parse(fs.readFileSync(path.join(dir, MARCA), "utf8")); } catch { return null; }
}

/**
 * Estado de la skill en un cliente:
 *   no-aplica   el cliente no tiene carpeta de skills (Claude Desktop, Cursor)
 *   ausente     no está
 *   al-dia      es la de este paquete, sin cambios
 *   desactualizada  la puso este paquete, pero ahora el paquete trae otra
 *   modificada  la puso este paquete y alguien editó sus archivos
 *   ajena       hay una carpeta con ese nombre que no puso este paquete
 */
export function estadoSkill(cliente) {
  const ruta = destinoSkill(cliente);
  if (!ruta) return { cliente, estado: "no-aplica", ruta: null };
  if (!fs.existsSync(ruta)) return { cliente, estado: "ausente", ruta };
  const marca = leerMarca(ruta);
  if (!marca || marca.paquete !== "leyes-mx") return { cliente, estado: "ajena", ruta };
  const fuente = huella(carpetaFuente());
  const actual = huella(ruta);
  const estado = actual !== marca.sha256 ? "modificada" : marca.sha256 !== fuente ? "desactualizada" : "al-dia";
  return { cliente, estado, ruta, version: marca.version };
}

function respaldarCarpeta(ruta, cliente) {
  const sello = new Date().toISOString().replace(/[:.]/g, "-");
  // fuera de la carpeta de skills: un respaldo dentro se cargaría como una segunda skill con el mismo nombre
  const dest = path.join(carpetaBase(), "respaldos", `skill-${cliente}-${sello}`);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.cpSync(ruta, dest, { recursive: true });
  return dest;
}

function copiar(destino) {
  const fuente = carpetaFuente();
  const tmp = `${destino}.tmp-${process.pid}`;
  fs.rmSync(tmp, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(destino), { recursive: true });
  fs.cpSync(fuente, tmp, { recursive: true });
  fs.writeFileSync(path.join(tmp, MARCA), JSON.stringify({ paquete: "leyes-mx", version: VERSION, sha256: huella(fuente) }, null, 2) + "\n");
  fs.rmSync(destino, { recursive: true, force: true });
  fs.renameSync(tmp, destino);
}

/** Instala o refresca la skill. { dryRun, soloSiExiste } -> { cliente, ruta, estado: agregada|actualizada|sin cambios|omitida|no aplica|no estaba, respaldo? } */
export function instalarSkill(cliente, { dryRun = false, soloSiExiste = false } = {}) {
  const e = estadoSkill(cliente);
  const base = { cliente, ruta: e.ruta };
  if (e.estado === "no-aplica") return { ...base, estado: "no aplica" };
  if (e.estado === "ajena") return { ...base, estado: "omitida", detalle: `ya hay una carpeta ${SKILL_NOMBRE} que no puso este paquete; no se toca` };
  if (e.estado === "al-dia") return { ...base, estado: "sin cambios" };
  if (e.estado === "ausente" && soloSiExiste) return { ...base, estado: "no estaba" };
  const estado = e.estado === "ausente" ? "agregada" : "actualizada";
  if (dryRun) return { ...base, estado, dryRun: true };
  const respaldo = e.estado === "ausente" ? null : respaldarCarpeta(e.ruta, cliente);
  copiar(e.ruta);
  return { ...base, estado, respaldo };
}

export function quitarSkill(cliente, { dryRun = false } = {}) {
  const e = estadoSkill(cliente);
  const base = { cliente, ruta: e.ruta };
  if (e.estado === "no-aplica") return { ...base, estado: "no aplica" };
  if (e.estado === "ausente") return { ...base, estado: "no estaba" };
  if (e.estado === "ajena") return { ...base, estado: "omitida", detalle: "no la puso este paquete; no se toca" };
  if (dryRun) return { ...base, estado: "se quitaría", dryRun: true };
  const respaldo = respaldarCarpeta(e.ruta, cliente);
  fs.rmSync(e.ruta, { recursive: true, force: true });
  return { ...base, estado: "quitada", respaldo };
}

// ------------------------------------------------------------------ .zip para Claude Desktop (carga manual)

const TABLA_CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
export function crc32(buf) { let c = 0xffffffff; for (const b of buf) c = TABLA_CRC[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }

/** Zip mínimo (deflate) determinista. entradas: [{nombre, datos: Buffer}]. */
export function construirZip(entradas) {
  const locales = [], centrales = [];
  let desplazamiento = 0;
  const FECHA = 0x5a21, HORA = 0; // 2025-01-01 00:00: mismo contenido, mismos bytes
  for (const { nombre, datos } of entradas) {
    const n = Buffer.from(nombre, "utf8");
    const comp = zlib.deflateRawSync(datos, { level: 9 });
    const crc = crc32(datos);
    const loc = Buffer.alloc(30);
    loc.writeUInt32LE(0x04034b50, 0); loc.writeUInt16LE(20, 4); loc.writeUInt16LE(0x0800, 6); loc.writeUInt16LE(8, 8);
    loc.writeUInt16LE(HORA, 10); loc.writeUInt16LE(FECHA, 12); loc.writeUInt32LE(crc, 14);
    loc.writeUInt32LE(comp.length, 18); loc.writeUInt32LE(datos.length, 22); loc.writeUInt16LE(n.length, 26);
    locales.push(loc, n, comp);
    const cen = Buffer.alloc(46);
    cen.writeUInt32LE(0x02014b50, 0); cen.writeUInt16LE(0x031e, 4); cen.writeUInt16LE(20, 6); cen.writeUInt16LE(0x0800, 8); cen.writeUInt16LE(8, 10);
    cen.writeUInt16LE(HORA, 12); cen.writeUInt16LE(FECHA, 14); cen.writeUInt32LE(crc, 16); cen.writeUInt32LE(comp.length, 20);
    cen.writeUInt32LE(datos.length, 24); cen.writeUInt16LE(n.length, 28); cen.writeUInt32LE(0o100644 << 16 >>> 0, 38); cen.writeUInt32LE(desplazamiento, 42);
    centrales.push(cen, n);
    desplazamiento += loc.length + n.length + comp.length;
  }
  const cd = Buffer.concat(centrales);
  const fin = Buffer.alloc(22);
  fin.writeUInt32LE(0x06054b50, 0); fin.writeUInt16LE(entradas.length, 8); fin.writeUInt16LE(entradas.length, 10);
  fin.writeUInt32LE(cd.length, 12); fin.writeUInt32LE(desplazamiento, 16);
  return Buffer.concat([...locales, cd, fin]);
}

/** Zip con la carpeta de la skill en la raíz (leyes-mx/SKILL.md), como pide el soporte de Claude para cargar skills. */
export function zipDeSkill() {
  const dir = carpetaFuente();
  return construirZip(archivos(dir).map((rel) => ({ nombre: `${SKILL_NOMBRE}/${rel}`, datos: fs.readFileSync(path.join(dir, ...rel.split("/"))) })));
}

export function escribirZip(carpeta, { dryRun = false } = {}) {
  const ruta = path.resolve(carpeta, ZIP_NOMBRE);
  if (!dryRun) { fs.mkdirSync(path.dirname(ruta), { recursive: true }); fs.writeFileSync(ruta, zipDeSkill()); }
  return ruta;
}

/** Pasos para cargar el .zip en Claude Desktop, en español llano. Los menús varían entre versiones de la app. */
export function instruccionesZip(ruta) {
  return [
    `Skill de leyes-mx para Claude Desktop (opcional): ${ruta}`,
    "",
    "No hace falta para que funcione: el servidor ya da acceso a las leyes. La skill solo agrega el método de trabajo (reformular, leer el artículo completo, citar).",
    "Para cargarla:",
    "  1. Abre Claude Desktop.",
    "  2. Entra a Personalizar (Customize) y luego a Skills. En algunas versiones está en Configuración > Capacidades.",
    "  3. Pulsa el botón +, elige \"Subir una skill\" (Upload a skill) y selecciona el archivo .zip de arriba.",
    "  4. Activa la skill leyes-mx en la lista.",
    "Si no ves la opción, necesitas tener activada la ejecución de código (Configuración > Capacidades) o, en planes de equipo, que el administrador permita skills.",
  ].join("\n");
}
