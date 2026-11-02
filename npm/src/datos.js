// Descarga, verificación y activación atómica de los datos.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";
import { leerTar } from "./tar.js";
import { MANIFEST_URL_DEFECTO, archivoActual, archivoAnterior, carpetaBase, carpetaDatos, versionActual, versionAnterior } from "./rutas.js";

export const ESQUEMA_SOPORTADO = 1;
export const sha256 = (b) => crypto.createHash("sha256").update(b).digest("hex");

export const urlManifest = () => process.env.LEYES_MX_MANIFEST || MANIFEST_URL_DEFECTO;

/** Lee un recurso desde https://, file:// o una ruta local. */
export async function leerRecurso(ref, { timeoutMs = 60000 } = {}) {
  if (/^https?:\/\//i.test(ref)) {
    const r = await fetch(ref, { redirect: "follow", signal: AbortSignal.timeout(timeoutMs), headers: { "user-agent": "leyes-mx" } });
    if (!r.ok) throw new Error(`HTTP ${r.status} al descargar ${ref}`);
    return Buffer.from(await r.arrayBuffer());
  }
  const p = ref.startsWith("file:") ? fileURLToPath(ref) : ref;
  return fs.readFileSync(p);
}

export function resolverRelativo(base, rel) {
  if (/^(https?:|file:)/i.test(rel) || path.isAbsolute(rel)) return rel;
  if (/^https?:\/\//i.test(base)) return new URL(rel, base).toString();
  const b = base.startsWith("file:") ? fileURLToPath(base) : base;
  return path.join(path.dirname(b), rel);
}

export async function leerManifest(ref = urlManifest(), opts) {
  const buf = await leerRecurso(ref, opts);
  let m;
  try { m = JSON.parse(buf.toString("utf8")); } catch { throw new Error(`manifest.json inválido en ${ref}`); }
  if (!m.version || !m.tarball?.sha256 || !m.tarball?.nombre) throw new Error("manifest.json incompleto (faltan version o tarball)");
  if (m.esquema > ESQUEMA_SOPORTADO) throw new Error(`El manifest usa el esquema ${m.esquema}, más nuevo que el que entiende esta versión de leyes-mx. Actualiza el paquete: npx leyes-mx@latest actualizar`);
  return m;
}

/** Compara versiones tipo "2026.11.02" o "2026.11.02.2". Devuelve <0, 0, >0. */
export function compararVersiones(a, b) {
  const pa = String(a).split(".").map(Number), pb = String(b).split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d) return d;
  }
  return 0;
}

const versionSegura = (v) => /^[0-9A-Za-z][0-9A-Za-z._-]*$/.test(v) && !v.includes("..");

function escribirAtomico(destino, contenido) {
  const tmp = `${destino}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, contenido);
  fs.renameSync(tmp, destino);
}

/** Verifica una carpeta extraída contra su INTEGRIDAD.json. Devuelve { ok, revisados, problemas[] }. */
export function verificarCarpeta(carpeta) {
  const ruta = path.join(carpeta, "INTEGRIDAD.json");
  if (!fs.existsSync(ruta)) return { ok: false, revisados: 0, problemas: ["falta INTEGRIDAD.json"] };
  const integ = JSON.parse(fs.readFileSync(ruta, "utf8"));
  const problemas = [];
  let n = 0;
  for (const [rel, hash] of Object.entries(integ.archivos)) {
    n++;
    const p = path.join(carpeta, ...rel.split("/"));
    if (!fs.existsSync(p)) problemas.push(`falta ${rel}`);
    else if (sha256(fs.readFileSync(p)) !== hash) problemas.push(`sha256 distinto en ${rel}`);
  }
  return { ok: problemas.length === 0, revisados: n, problemas };
}

/**
 * Descarga el tarball del manifest, verifica sha256, extrae a una carpeta temporal, verifica cada archivo y activa.
 * Nada queda activo si algo falla.
 */
export async function instalarDesdeManifest(manifest, refManifest, { log = () => {}, forzar = false } = {}) {
  const v = manifest.version;
  if (!versionSegura(v)) throw new Error(`versión no válida en el manifest: ${v}`);
  const destino = path.join(carpetaDatos(), v);
  if (fs.existsSync(destino) && !forzar) {
    if (verificarCarpeta(destino).ok) { activar(v); return { version: v, reutilizada: true }; }
    log(`La carpeta ${destino} existe pero no pasa la verificación; se descarga de nuevo.`);
  }
  const urlTar = resolverRelativo(refManifest, manifest.tarball.nombre);
  log(`Descargando ${urlTar} (${(manifest.tarball.bytes / 1048576).toFixed(1)} MB)...`);
  const buf = await leerRecurso(urlTar, { timeoutMs: 300000 });
  const hash = sha256(buf);
  if (hash !== manifest.tarball.sha256) {
    throw new Error(`sha256 del tarball NO coincide (esperado ${manifest.tarball.sha256}, obtenido ${hash}). Descarga rechazada; no se activó nada.`);
  }
  log("sha256 del tarball verificado.");
  const archivos = leerTar(zlib.gunzipSync(buf));
  fs.mkdirSync(carpetaDatos(), { recursive: true });
  const tmp = path.join(carpetaDatos(), `.tmp-${v}-${process.pid}`);
  fs.rmSync(tmp, { recursive: true, force: true });
  try {
    for (const { nombre, datos } of archivos) {
      const p = path.join(tmp, ...nombre.split("/"));
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, datos);
    }
    const ver = verificarCarpeta(tmp);
    if (!ver.ok) throw new Error(`verificación por archivo fallida: ${ver.problemas.slice(0, 3).join("; ")}`);
    log(`Verificados ${ver.revisados} archivos.`);
    fs.writeFileSync(path.join(tmp, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
    fs.rmSync(destino, { recursive: true, force: true });
    fs.renameSync(tmp, destino);
  } catch (e) {
    fs.rmSync(tmp, { recursive: true, force: true });
    throw e;
  }
  activar(v);
  return { version: v, reutilizada: false };
}

/** Marca v como actual (archivo `actual`, escritura atómica), guarda la anterior y poda lo que sobre. */
export function activar(v) {
  const previa = versionActual();
  fs.mkdirSync(carpetaBase(), { recursive: true });
  if (previa && previa !== v) escribirAtomico(archivoAnterior(), previa + "\n");
  escribirAtomico(archivoActual(), v + "\n");
  podar();
}

export function revertir() {
  const ant = versionAnterior();
  if (!ant || !fs.existsSync(path.join(carpetaDatos(), ant))) throw new Error("No hay versión anterior para revertir.");
  const act = versionActual();
  escribirAtomico(archivoActual(), ant + "\n");
  if (act) escribirAtomico(archivoAnterior(), act + "\n");
  return { actual: ant, anterior: act };
}

function podar() {
  const guardar = new Set([versionActual(), versionAnterior()].filter(Boolean));
  const base = carpetaDatos();
  if (!fs.existsSync(base)) return;
  for (const n of fs.readdirSync(base)) {
    if (n.startsWith(".tmp-")) continue;
    if (!guardar.has(n)) fs.rmSync(path.join(base, n), { recursive: true, force: true });
  }
}

export function manifestInstalado() {
  const v = versionActual();
  if (!v) return null;
  try { return JSON.parse(fs.readFileSync(path.join(carpetaDatos(), v, "manifest.json"), "utf8")); } catch { return null; }
}
