// Dónde viven los datos y la configuración local.
import os from "node:os";
import path from "node:path";
import fs from "node:fs";

export const REPO = "soyisraelcastro/leyes-mx";
export const MANIFEST_URL_DEFECTO = `https://github.com/${REPO}/releases/latest/download/manifest.json`;

/** Carpeta base: LEYES_MX_HOME, o %LOCALAPPDATA%\leyes-mx en Windows, o ~/.leyes-mx. */
export function carpetaBase() {
  if (process.env.LEYES_MX_HOME) return path.resolve(process.env.LEYES_MX_HOME);
  if (process.platform === "win32" && process.env.LOCALAPPDATA) return path.join(process.env.LOCALAPPDATA, "leyes-mx");
  return path.join(os.homedir(), ".leyes-mx");
}

export const carpetaDatos = () => path.join(carpetaBase(), "datos");
export const archivoActual = () => path.join(carpetaBase(), "actual");
export const archivoAnterior = () => path.join(carpetaBase(), "anterior");
export const archivoConfig = () => path.join(carpetaBase(), "config.json");

function leerLinea(p) {
  try { return fs.readFileSync(p, "utf8").trim() || null; } catch { return null; }
}

export const versionActual = () => leerLinea(archivoActual());
export const versionAnterior = () => leerLinea(archivoAnterior());

export function leerConfig() {
  try { return JSON.parse(fs.readFileSync(archivoConfig(), "utf8")); } catch { return {}; }
}

/**
 * Raíz de datos a usar. LEYES_MX_DATOS (por ejemplo una copia del repo) manda sobre lo instalado.
 * Devuelve { raiz, origen, version } o null si no hay datos.
 */
export function resolverDatos() {
  if (process.env.LEYES_MX_DATOS) {
    const raiz = path.resolve(process.env.LEYES_MX_DATOS);
    return { raiz, origen: "LEYES_MX_DATOS", version: null };
  }
  const v = versionActual();
  if (!v) return null;
  const raiz = path.join(carpetaDatos(), v);
  if (!fs.existsSync(path.join(raiz, "leyes"))) return null;
  return { raiz, origen: "instalada", version: v };
}
