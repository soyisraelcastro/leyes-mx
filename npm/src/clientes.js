// Registro del servidor en cada cliente MCP. Fusiona sin pisar, respalda, es idempotente y solo revierte lo suyo.
// Sintaxis verificada en la documentación oficial de cada cliente (ver docs/npx.md).
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

export const NOMBRE = "leyes-mx";
export const ARGS = ["-y", "leyes-mx", "servir"];
export const CLIENTES = ["claude-desktop", "claude-code", "codex", "cursor"];
const GUI = new Set(["claude-desktop", "cursor"]); // apps de escritorio: heredan un PATH reducido

export const MARCA_INI = "<!-- leyes-mx:inicio -->";
export const MARCA_FIN = "<!-- leyes-mx:fin -->";
const TOML_INI = "# >>> leyes-mx (lo gestiona npx leyes-mx; se quita con npx leyes-mx desinstalar) >>>";
const TOML_FIN = "# <<< leyes-mx <<<";

export const BLOQUE_INSTRUCCIONES = `${MARCA_INI}
## Consulta de leyes (leyes-mx)

Antes de responder cualquier consulta fiscal o laboral de México (ISR, IVA, deducciones, retenciones, CFDI, aguinaldo, PTU, vacaciones, despido, tarifas, "qué dice el artículo", "fundamento legal") y antes de citar un artículo de la LISR, LIVA, CFF, LFT, LSS, LFDC, LCF, LOPDC o sus reglamentos (RLISR, RLIVA, RCFF, RACERF), consulta el servidor MCP "leyes-mx". No respondas de memoria ni busques en internet primero.

1. Herramientas: buscar, temas, obtener_articulo, obtener_regla, obtener_tarifa, obtener_subsidio_empleo, obtener_transitorios, estado_reforma, listar_leyes. Sin MCP, por terminal: npx leyes-mx buscar | obtener | tarifa | subsidio | reforma.
2. Reformula con los términos de la ley, no con los del uso corriente ("accesorios de las contribuciones", no "actualizaciones"). buscar es léxico y solo devuelve fragmentos.
3. Lee siempre el artículo completo con obtener_articulo antes de afirmar algo: un fragmento puede omitir la excepción o la fracción que cambia la respuesta.
4. Cita ley, artículo, fracción, año de vigencia y fecha de última reforma, tal como los devuelve la herramienta.
5. Tarifas de ISR: con obtener_tarifa (Anexo 8), nunca de memoria ni de la tabla de los arts. 96 y 152 de la LISR. Subsidio para el empleo: con obtener_subsidio_empleo (decreto del DOF y UMA), nunca de memoria.
6. Nunca presentes un proyecto de reforma (por ejemplo el de 2027) como ley vigente. Respeta las líneas ADVERTENCIA.
7. Si no está en la base, dilo ("no verificado") y PREGUNTA al usuario si desea que lo busques en internet. Nunca busques sin su permiso; si lo autoriza, usa solo fuentes oficiales (DOF, SAT, Cámara de Diputados) y aclara que ese dato no proviene de la base verificada.
8. Si tienes la skill "leyes-mx" (/leyes-mx), úsala: trae este flujo completo.
${MARCA_FIN}
`;

// ------------------------------------------------------------------ utilidades

export function buscarEnPath(nombre) {
  const exts = process.platform === "win32" ? (process.env.PATHEXT || ".EXE;.CMD;.BAT").split(";") : [""];
  for (const dir of (process.env.PATH || "").split(path.delimiter).filter(Boolean)) {
    for (const e of exts) {
      const p = path.join(dir, nombre + e);
      try { fs.accessSync(p, fs.constants.X_OK); if (fs.statSync(p).isFile()) return p; } catch { /* siguiente */ }
    }
  }
  return null;
}

const casa = () => os.homedir();
export const dirClaudeCode = () => process.env.CLAUDE_CONFIG_DIR || path.join(casa(), ".claude");
export const dirCodex = () => process.env.CODEX_HOME || path.join(casa(), ".codex");

export function rutaConfig(cliente) {
  switch (cliente) {
    case "claude-desktop":
      if (process.platform === "darwin") return path.join(casa(), "Library", "Application Support", "Claude", "claude_desktop_config.json");
      if (process.platform === "win32") return path.join(process.env.APPDATA || path.join(casa(), "AppData", "Roaming"), "Claude", "claude_desktop_config.json");
      return path.join(casa(), ".config", "Claude", "claude_desktop_config.json");
    case "claude-code":
      return process.env.CLAUDE_CONFIG_DIR ? path.join(process.env.CLAUDE_CONFIG_DIR, ".claude.json") : path.join(casa(), ".claude.json");
    case "codex": return path.join(dirCodex(), "config.toml");
    case "cursor": return path.join(casa(), ".cursor", "mcp.json");
    default: throw new Error(`cliente desconocido: ${cliente}`);
  }
}

export function rutaInstrucciones(cliente) {
  if (cliente === "claude-code") return path.join(dirClaudeCode(), "CLAUDE.md");
  if (cliente === "codex") return path.join(dirCodex(), "AGENTS.md");
  return null;
}

/** Entrada MCP para el cliente. Los clientes de escritorio reciben ruta absoluta de npx y su carpeta en PATH (PATH reducido). */
export function entradaPara(cliente, { rutaAbsoluta } = {}) {
  const abs = rutaAbsoluta ?? GUI.has(cliente);
  const npx = process.platform === "win32" ? null : buscarEnPath("npx");
  if (abs && npx) {
    const dir = path.dirname(npx);
    return { command: npx, args: [...ARGS], env: { PATH: [dir, "/usr/local/bin", "/usr/bin", "/bin"].join(path.delimiter) } };
  }
  return { command: "npx", args: [...ARGS] };
}

const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const esNuestra = (e) => !!e && Array.isArray(e.args) && e.args.includes("leyes-mx");

function respaldar(ruta) {
  if (!fs.existsSync(ruta)) return null;
  const sello = new Date().toISOString().replace(/[:.]/g, "-");
  const dest = `${ruta}.bak-leyes-mx-${sello}`;
  fs.copyFileSync(ruta, dest);
  return dest;
}

function escribir(ruta, contenido) {
  fs.mkdirSync(path.dirname(ruta), { recursive: true });
  const tmp = `${ruta}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, contenido);
  fs.renameSync(tmp, ruta);
}

function leerJson(ruta) {
  if (!fs.existsSync(ruta)) return {};
  const t = fs.readFileSync(ruta, "utf8");
  if (!t.trim()) return {};
  try { return JSON.parse(t); } catch (e) { throw new Error(`${ruta} no es JSON válido (${e.message}); no se modifica. Corrígelo a mano y repite.`); }
}

// ------------------------------------------------------------------ detección

export function detectar(cliente) {
  switch (cliente) {
    case "claude-desktop": return fs.existsSync(path.dirname(rutaConfig(cliente)));
    case "claude-code": return !!buscarEnPath("claude") || fs.existsSync(rutaConfig(cliente));
    case "codex": return !!buscarEnPath("codex") || fs.existsSync(dirCodex());
    case "cursor": return fs.existsSync(path.dirname(rutaConfig(cliente)));
    default: return false;
  }
}

// ------------------------------------------------------------------ JSON (Claude Desktop, Cursor, Claude Code por archivo)

function estadoJson(cliente) {
  const ruta = rutaConfig(cliente);
  const data = leerJson(ruta);
  const e = data.mcpServers?.[NOMBRE];
  return { ruta, data, entrada: e };
}

function instalarJson(cliente, opts) {
  const { ruta, data, entrada } = estadoJson(cliente);
  let nueva = entradaPara(cliente, opts);
  if (cliente === "claude-code") nueva = { type: "stdio", ...nueva, env: nueva.env || {} };
  if (entrada && !esNuestra(entrada)) return { cliente, ruta, estado: "omitido", detalle: `ya existe un servidor "${NOMBRE}" que no es de este paquete; no se toca` };
  if (igual(entrada, nueva)) return { cliente, ruta, estado: "sin cambios", entrada: nueva };
  const res = { cliente, ruta, estado: entrada ? "actualizado" : "agregado", entrada: nueva };
  if (opts.dryRun) return { ...res, dryRun: true };
  res.respaldo = respaldar(ruta);
  data.mcpServers = { ...(data.mcpServers || {}), [NOMBRE]: nueva };
  escribir(ruta, JSON.stringify(data, null, 2) + "\n");
  return res;
}

function desinstalarJson(cliente, opts) {
  const { ruta, data, entrada } = estadoJson(cliente);
  if (!entrada) return { cliente, ruta, estado: "no estaba" };
  if (!esNuestra(entrada)) return { cliente, ruta, estado: "omitido", detalle: `el servidor "${NOMBRE}" no es de este paquete; no se toca` };
  if (opts.dryRun) return { cliente, ruta, estado: "se quitaría", dryRun: true };
  const respaldo = respaldar(ruta);
  delete data.mcpServers[NOMBRE];
  escribir(ruta, JSON.stringify(data, null, 2) + "\n");
  return { cliente, ruta, estado: "quitado", respaldo };
}

// ------------------------------------------------------------------ Claude Code (binario)

function claude(args) {
  return spawnSync("claude", args, { encoding: "utf8", timeout: 60000, shell: process.platform === "win32" });
}

function instalarClaudeCode(opts) {
  const usarBinario = !opts.sinBinario && buscarEnPath("claude");
  if (!usarBinario) return { ...instalarJson("claude-code", opts), via: "archivo" };
  const entrada = entradaPara("claude-code", opts);
  const comando = ["mcp", "add", "--transport", "stdio", "--scope", "user", NOMBRE, "--", entrada.command, ...entrada.args];
  const previo = estadoJson("claude-code");
  if (previo.entrada && !esNuestra(previo.entrada)) return { cliente: "claude-code", ruta: previo.ruta, estado: "omitido", detalle: `ya existe un servidor "${NOMBRE}" que no es de este paquete; no se toca` };
  const mismo = previo.entrada && previo.entrada.command === entrada.command && igual(previo.entrada.args, entrada.args);
  if (mismo) return { cliente: "claude-code", ruta: previo.ruta, estado: "sin cambios", via: "claude mcp add", entrada };
  if (opts.dryRun) return { cliente: "claude-code", ruta: previo.ruta, estado: previo.entrada ? "actualizado" : "agregado", dryRun: true, via: "claude mcp add", comando: ["claude", ...comando].join(" "), entrada };
  if (previo.entrada) claude(["mcp", "remove", NOMBRE, "--scope", "user"]);
  const r = claude(comando);
  if (r.status !== 0) {
    const f = instalarJson("claude-code", opts); // respaldo: escribir la configuración equivalente
    return { ...f, via: "archivo (falló claude mcp add: " + (r.stderr || r.stdout || "").trim().split("\n")[0] + ")" };
  }
  return { cliente: "claude-code", ruta: previo.ruta, estado: previo.entrada ? "actualizado" : "agregado", via: "claude mcp add", entrada };
}

function desinstalarClaudeCode(opts) {
  const previo = estadoJson("claude-code");
  if (!previo.entrada) return { cliente: "claude-code", ruta: previo.ruta, estado: "no estaba" };
  if (!esNuestra(previo.entrada)) return { cliente: "claude-code", ruta: previo.ruta, estado: "omitido", detalle: `el servidor "${NOMBRE}" no es de este paquete; no se toca` };
  if (opts.dryRun) return { cliente: "claude-code", ruta: previo.ruta, estado: "se quitaría", dryRun: true };
  if (!opts.sinBinario && buscarEnPath("claude")) {
    const r = claude(["mcp", "remove", NOMBRE, "--scope", "user"]);
    if (r.status === 0) return { cliente: "claude-code", ruta: previo.ruta, estado: "quitado", via: "claude mcp remove" };
  }
  return { ...desinstalarJson("claude-code", opts), via: "archivo" };
}

// ------------------------------------------------------------------ Codex (TOML, bloque delimitado)

const tomlStr = (s) => JSON.stringify(s); // las cadenas JSON son cadenas básicas TOML válidas

function bloqueToml(entrada) {
  const l = [TOML_INI, `[mcp_servers.${NOMBRE}]`, `command = ${tomlStr(entrada.command)}`,
    `args = [${entrada.args.map(tomlStr).join(", ")}]`, "startup_timeout_sec = 60"];
  if (entrada.env) { l.push(`[mcp_servers.${NOMBRE}.env]`); for (const [k, v] of Object.entries(entrada.env)) l.push(`${k} = ${tomlStr(v)}`); }
  l.push(TOML_FIN, "");
  return l.join("\n");
}
const RE_BLOQUE = new RegExp(`\\n?${TOML_INI.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[\\s\\S]*?${TOML_FIN.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\n?`);
const RE_TABLA_MANUAL = new RegExp(`^\\s*\\[mcp_servers\\.("?)${NOMBRE}\\1(\\.[^\\]]*)?\\]`, "m");

function instalarCodex(opts) {
  const ruta = rutaConfig("codex");
  const actual = fs.existsSync(ruta) ? fs.readFileSync(ruta, "utf8") : "";
  const sinNuestro = actual.replace(RE_BLOQUE, "\n");
  if (RE_TABLA_MANUAL.test(sinNuestro)) return { cliente: "codex", ruta, estado: "omitido", detalle: `ya hay una tabla [mcp_servers.${NOMBRE}] escrita a mano; no se toca` };
  const bloque = bloqueToml(entradaPara("codex", opts));
  const base = sinNuestro.replace(/\s+$/, "");
  const nuevo = (base ? base + "\n\n" : "") + bloque;
  if (nuevo === actual) return { cliente: "codex", ruta, estado: "sin cambios", bloque };
  const hubo = RE_BLOQUE.test(actual);
  if (opts.dryRun) return { cliente: "codex", ruta, estado: hubo ? "actualizado" : "agregado", dryRun: true, bloque };
  const respaldo = respaldar(ruta);
  escribir(ruta, nuevo);
  return { cliente: "codex", ruta, estado: hubo ? "actualizado" : "agregado", respaldo, bloque };
}

function desinstalarCodex(opts) {
  const ruta = rutaConfig("codex");
  if (!fs.existsSync(ruta)) return { cliente: "codex", ruta, estado: "no estaba" };
  const actual = fs.readFileSync(ruta, "utf8");
  if (!RE_BLOQUE.test(actual)) return { cliente: "codex", ruta, estado: RE_TABLA_MANUAL.test(actual) ? "omitido" : "no estaba", detalle: RE_TABLA_MANUAL.test(actual) ? "la entrada es manual; no se toca" : undefined };
  if (opts.dryRun) return { cliente: "codex", ruta, estado: "se quitaría", dryRun: true };
  const respaldo = respaldar(ruta);
  const nuevo = actual.replace(RE_BLOQUE, "\n").replace(/\n{3,}/g, "\n\n").replace(/^\n+/, "");
  escribir(ruta, nuevo.trim() ? nuevo.replace(/\s*$/, "\n") : "");
  return { cliente: "codex", ruta, estado: "quitado", respaldo };
}

// ------------------------------------------------------------------ API pública

export function instalarCliente(cliente, opts = {}) {
  try {
    if (cliente === "claude-code") return instalarClaudeCode(opts);
    if (cliente === "codex") return instalarCodex(opts);
    return instalarJson(cliente, opts);
  } catch (e) { return { cliente, ruta: rutaConfig(cliente), estado: "error", detalle: e.message }; }
}

export function desinstalarCliente(cliente, opts = {}) {
  try {
    if (cliente === "claude-code") return desinstalarClaudeCode(opts);
    if (cliente === "codex") return desinstalarCodex(opts);
    return desinstalarJson(cliente, opts);
  } catch (e) { return { cliente, ruta: rutaConfig(cliente), estado: "error", detalle: e.message }; }
}

/** "registrado" | "distinto" | "ausente" | "ilegible" (para doctor). */
export function estadoCliente(cliente) {
  try {
    if (cliente === "codex") {
      const r = rutaConfig(cliente);
      const t = fs.existsSync(r) ? fs.readFileSync(r, "utf8") : "";
      return RE_BLOQUE.test(t) ? "registrado" : RE_TABLA_MANUAL.test(t) ? "manual" : "ausente";
    }
    const { entrada } = estadoJson(cliente);
    if (!entrada) return "ausente";
    return esNuestra(entrada) ? "registrado" : "distinto";
  } catch { return "ilegible"; }
}

/** Rutas de Node que incluyen la versión (nvm, fnm, asdf, nodenv, n): dejan de existir al cambiar o borrar esa versión. */
export function esRutaVersionada(p) {
  return /[\\/]\.nvm[\\/]versions[\\/]|[\\/]nvm[\\/]v?\d|fnm_multishells|[\\/]\.fnm[\\/]|[\\/]fnm[\\/]node-versions|[\\/]\.asdf[\\/]installs[\\/]|[\\/]\.nodenv[\\/]versions[\\/]|[\\/]n[\\/]versions[\\/]node/.test(String(p || ""));
}

/** Comando que quedó registrado para leyes-mx en ese cliente (null si no hay). Para doctor. */
export function comandoRegistrado(cliente) {
  try {
    if (cliente === "codex") {
      const r = rutaConfig(cliente);
      const t = fs.existsSync(r) ? fs.readFileSync(r, "utf8") : "";
      const bloque = t.split(TOML_INI)[1] ?? "";
      const m = bloque.match(/^\s*command\s*=\s*"((?:[^"\\]|\\.)*)"/m);
      return m ? JSON.parse(`"${m[1]}"`) : null;
    }
    const { entrada } = estadoJson(cliente);
    return entrada && esNuestra(entrada) ? entrada.command ?? null : null;
  } catch { return null; }
}

export function bloqueJsonGenerico() {
  return JSON.stringify({ mcpServers: { [NOMBRE]: { command: "npx", args: ARGS } } }, null, 2);
}

// ------------------------------------------------------------------ instrucciones (CLAUDE.md / AGENTS.md)

const RE_INSTR = new RegExp(`\\n?${MARCA_INI}[\\s\\S]*?${MARCA_FIN}\\n?`);

export function instalarInstrucciones(cliente, opts = {}) {
  const ruta = rutaInstrucciones(cliente);
  if (!ruta) return null;
  const actual = fs.existsSync(ruta) ? fs.readFileSync(ruta, "utf8") : "";
  const base = actual.replace(RE_INSTR, "\n").replace(/\s+$/, "");
  const nuevo = (base ? base + "\n\n" : "") + BLOQUE_INSTRUCCIONES;
  if (nuevo === actual) return { ruta, estado: "sin cambios" };
  const estado = RE_INSTR.test(actual) ? "actualizado" : "agregado";
  if (opts.dryRun) return { ruta, estado, dryRun: true };
  const respaldo = respaldar(ruta);
  escribir(ruta, nuevo);
  return { ruta, estado, respaldo };
}

export function desinstalarInstrucciones(cliente, opts = {}) {
  const ruta = rutaInstrucciones(cliente);
  if (!ruta || !fs.existsSync(ruta)) return null;
  const actual = fs.readFileSync(ruta, "utf8");
  if (!RE_INSTR.test(actual)) return null;
  if (opts.dryRun) return { ruta, estado: "se quitaría", dryRun: true };
  const respaldo = respaldar(ruta);
  const nuevo = actual.replace(RE_INSTR, "\n").replace(/\n{3,}/g, "\n\n").replace(/^\n+/, "").replace(/\s*$/, "\n");
  escribir(ruta, nuevo.trim() ? nuevo : "");
  return { ruta, estado: "quitado", respaldo };
}
