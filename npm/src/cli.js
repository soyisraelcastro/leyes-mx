// Línea de comandos: instalar, actualizar, servir, estado, doctor, desinstalar, revertir, skill, obtener, tarifa, subsidio, buscar, listar, reforma.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";
import { Almacen, SinDatos, AVISO_GENERAL } from "./almacen.js";
import { Indice } from "./indice.js";
import { Glosario } from "./glosario.js";
import { citaArticulo, lineasAmpliacion, noEncontrado, respuestaSubsidio, respuestaTarifa, respuestaTarifas } from "./respuestas.js";
import { VERSION } from "./version.js";
import * as clientes from "./clientes.js";
import * as datos from "./datos.js";
import * as skill from "./skill.js";
import { archivoConfig, carpetaBase, carpetaDatos, resolverDatos, versionActual, versionAnterior } from "./rutas.js";

const AYUDA = `leyes-mx ${VERSION}: leyes fiscales y laborales de México en local, para tu asistente.

Uso: npx leyes-mx <comando> [opciones]

Instalación
  instalar [--cliente claude-desktop|claude-code|codex|cursor|todos] [--dry-run] [--anio 2026]
           [--instrucciones] [--si] [--ruta-absoluta] [--sin-binario] [--sin-datos] [--sin-skill]
                         descarga los datos, registra el servidor MCP en tus clientes y, donde aplica, copia la skill
  actualizar [--forzar]  baja la última versión de los datos y del glosario (verifica sha256) y refresca la skill
  revertir               vuelve a la versión anterior de los datos
  desinstalar [--borrar-datos] [--dry-run]
                         quita solo lo que puso este paquete (servidor, skill, instrucciones)
  skill [--zip] [--salida CARPETA] [--dry-run]
                         estado de la skill por cliente; con --zip escribe leyes-mx-skill.zip para cargarla a mano en Claude Desktop
  estado                 versión instalada vs la última publicada y última reforma por ley
  doctor                 diagnóstico de la instalación

Servidor
  servir                 servidor MCP por stdio (lo lanza el cliente, no hace falta correrlo a mano)

Consulta directa (sin MCP)
  obtener LEY ARTICULO [--anio N] [--incluir-proyectos] [--json]
  tarifa [ID|APARTADO] [--anio N] [--json]   Tarifas de ISR del Anexo 8 de la RMF (sin argumento: las lista)
  subsidio [DOCUMENTO] [--anio N] [--json]   Subsidio para el empleo (decreto del DOF y UMA); DOCUMENTO: vigente-2026, modificacion-2025-12-31...
  buscar "texto" [--ley LEY] [--anio N] [--incluir-proyectos] [--limite N] [--sin-glosario] [--json]
  listar [--incluir-proyectos] [--json]
  reforma [--anio N]     estado de la reforma en trámite (proyecto, no es ley vigente)

Variables: LEYES_MX_HOME (carpeta de datos), LEYES_MX_DATOS (usar una carpeta de datos, p. ej. este repo),
           LEYES_MX_MANIFEST (URL o ruta de otro manifest.json).
${AVISO_GENERAL}
`;

// ------------------------------------------------------------------ argumentos

const BOOLEANAS = new Set(["dry-run", "json", "incluir-proyectos", "instrucciones", "si", "sin-glosario", "sin-skill", "zip", "ruta-absoluta", "sin-binario", "sin-datos", "forzar", "borrar-datos", "ayuda", "version"]);

export function parsear(argv) {
  const pos = [], op = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "-h") op.ayuda = true;
    else if (a.startsWith("--")) {
      const [k, v] = a.slice(2).split(/=(.*)/s, 2);
      if (BOOLEANAS.has(k)) op[k] = v === undefined ? true : v !== "false";
      else if (v !== undefined) (op[k] ??= []).push(v);
      else { if (i + 1 >= argv.length) throw new Error(`falta el valor de --${k}`); (op[k] ??= []).push(argv[++i]); }
    } else pos.push(a);
  }
  return { pos, op };
}

const uno = (op, k) => (op[k] ? op[k][op[k].length - 1] : undefined);
const entero = (op, k) => {
  const v = uno(op, k);
  if (v === undefined) return undefined;
  if (!/^\d+$/.test(v)) throw new Error(`--${k} debe ser un número`);
  return Number(v);
};
const out = (s = "") => process.stdout.write(s + "\n");
const err = (s = "") => process.stderr.write(s + "\n");

async function preguntar(texto) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
  const r = await new Promise((res) => rl.question(texto, res));
  rl.close();
  return /^s(i|í)?$/i.test(r.trim());
}

// ------------------------------------------------------------------ comandos de datos

/** Refresca la skill donde este paquete ya la había puesto (no la agrega donde no estaba: eso lo hace `instalar`). */
function refrescarSkills() {
  for (const c of skill.CLIENTES_CON_CARPETA) {
    const r = skill.instalarSkill(c, { soloSiExiste: true });
    if (r.estado === "actualizada" || r.estado === "omitida") out(`Skill (${c}): ${r.estado}${r.detalle ? `. ${r.detalle}` : ""}${r.respaldo ? ` (respaldo: ${r.respaldo})` : ""}`);
  }
}

async function cmdActualizar(op) {
  refrescarSkills();
  return await actualizarDatos(op);
}

async function actualizarDatos(op) {
  if (process.env.LEYES_MX_DATOS) { err("LEYES_MX_DATOS está definido: se usan esos datos y no se descarga nada."); return 0; }
  const ref = datos.urlManifest();
  const m = await datos.leerManifest(ref);
  const actual = versionActual();
  if (actual && !op.forzar && datos.compararVersiones(m.version, actual) <= 0) {
    out(datos.compararVersiones(m.version, actual) === 0 ? `Los datos ya están al día (${actual}).` : `La versión instalada (${actual}) es más nueva que la publicada (${m.version}); no se cambia.`);
    return 0;
  }
  const r = await datos.instalarDesdeManifest(m, ref, { log: (s) => err(s), forzar: !!op.forzar });
  out(`Datos ${r.reutilizada ? "reactivados" : "instalados"}: ${r.version}${actual && actual !== r.version ? ` (antes ${actual}; se conserva para revertir con: npx leyes-mx revertir)` : ""}`);
  return 0;
}

const TXT_SKILL = { ausente: "no instalada (npx leyes-mx instalar)", "al-dia": "al día", desactualizada: "desactualizada (npx leyes-mx actualizar)",
  modificada: "modificada a mano (npx leyes-mx actualizar la restaura, con respaldo)", ajena: "hay otra carpeta con ese nombre; no se toca", "no-aplica": "no aplica" };

async function cmdEstado() {
  const v = versionActual();
  out(`Datos instalados: ${process.env.LEYES_MX_DATOS ? `(LEYES_MX_DATOS) ${process.env.LEYES_MX_DATOS}` : v ? `${v} (${path.join(carpetaDatos(), v)})` : "ninguno. Ejecuta: npx leyes-mx instalar"}`);
  if (versionAnterior()) out(`Versión anterior conservada: ${versionAnterior()} (revertir: npx leyes-mx revertir)`);
  let ult = null;
  try { ult = await datos.leerManifest(datos.urlManifest(), { timeoutMs: 8000 }); }
  catch (e) { out(`Última publicada: no se pudo consultar (${e.message}). Se sigue usando lo instalado, sin conexión.`); }
  if (ult) {
    const cmp = v ? datos.compararVersiones(ult.version, v) : 1;
    out(`Última publicada: ${ult.version} (${ult.publicado})${v ? (cmp > 0 ? "  -> hay una versión nueva: npx leyes-mx actualizar" : cmp === 0 ? "  -> al día" : "  -> la instalada es más nueva") : ""}`);
  }
  let alm = null;
  try { alm = Almacen.abrir(); } catch { /* sin datos */ }
  if (alm) {
    const g = Glosario.diagnosticar(alm.raiz);
    const gp = ult?.glosario;
    out(`Glosario de sinónimos: ${!g.existe ? "no incluido en estos datos (la búsqueda funciona igual)" : !g.valido ? `INVÁLIDO (${g.problemas[0]})` : `${g.entradas} entradas, versión ${g.version}`}${gp && g.valido && gp.version !== g.version ? `  |  publicado: versión ${gp.version} (npx leyes-mx actualizar)` : ""}`);
    const pub = new Map((ult?.leyes || []).map((l) => [`${l.sigla}:${l.anio_vigencia}`, l]));
    out("");
    out("Última reforma DOF por ley (instalada" + (ult ? " | publicada" : "") + "):");
    for (const l of alm.listarLeyes()) {
      const p = pub.get(`${l.sigla}:${l.anio_vigencia}`);
      const cambia = p && p.ultima_reforma_dof !== l.ultima_reforma_dof;
      out(`  ${l.sigla.padEnd(6)} ${l.anio_vigencia}  ${l.ultima_reforma_dof ?? "sin dato"}${p ? `  |  ${p.ultima_reforma_dof ?? "sin dato"}${cambia ? "  (cambió)" : ""}` : ""}`);
    }
    if (ult) for (const p of ult.leyes) if (!alm.listarLeyes().some((l) => l.sigla === p.sigla && l.anio_vigencia === p.anio_vigencia)) out(`  ${p.sigla.padEnd(6)} ${p.anio_vigencia}  (nueva en la publicada)  |  ${p.ultima_reforma_dof ?? "sin dato"}`);
  }
  out("");
  out("Skill leyes-mx (complemento):");
  for (const c of skill.CLIENTES_CON_CARPETA) { const e = skill.estadoSkill(c); out(`  ${c.padEnd(15)} ${TXT_SKILL[e.estado]}${e.ruta ? `  ${e.ruta}` : ""}`); }
  out("  claude-desktop  carga manual opcional: npx leyes-mx skill --zip");
  return 0;
}

// ------------------------------------------------------------------ instalar / desinstalar

function elegirClientes(op) {
  const pedidos = (op.cliente || []).flatMap((c) => c.split(",")).map((c) => c.trim()).filter(Boolean);
  if (pedidos.includes("todos")) return { lista: [...clientes.CLIENTES], auto: false };
  for (const c of pedidos) if (!clientes.CLIENTES.includes(c)) throw new Error(`cliente desconocido: ${c}. Opciones: ${clientes.CLIENTES.join(", ")}, todos`);
  if (pedidos.length) return { lista: [...new Set(pedidos)], auto: false };
  return { lista: clientes.CLIENTES.filter((c) => clientes.detectar(c)), auto: true };
}

function imprimirResultado(r) {
  out(`  ${r.cliente}: ${r.estado}${r.via ? ` (${r.via})` : ""}`);
  out(`    archivo: ${r.ruta}`);
  if (r.detalle) out(`    ${r.detalle}`);
  if (r.respaldo) out(`    respaldo: ${r.respaldo}`);
  if (r.dryRun) {
    if (r.comando) out(`    ejecutaría: ${r.comando}`);
    if (r.bloque) out(r.bloque.replace(/^/gm, "    | "));
    else if (r.entrada) out(JSON.stringify({ mcpServers: { [clientes.NOMBRE]: r.entrada } }, null, 2).replace(/^/gm, "    | "));
  }
}

async function cmdInstalar(op) {
  const dry = !!op["dry-run"];
  const anio = entero(op, "anio");
  const { lista, auto } = elegirClientes(op);
  out(dry ? "Simulación (--dry-run): no se escribe ni se descarga nada.\n" : "");

  // 1. datos
  if (process.env.LEYES_MX_DATOS) out(`Datos: se usará LEYES_MX_DATOS=${process.env.LEYES_MX_DATOS}`);
  else if (op["sin-datos"]) out("Datos: omitidos (--sin-datos). Descárgalos luego con: npx leyes-mx actualizar");
  else if (dry) {
    try { const m = await datos.leerManifest(datos.urlManifest(), { timeoutMs: 8000 }); out(`Datos: ${versionActual() ? `instalados ${versionActual()}; última publicada ${m.version}` : `se descargarían ${m.version} (${(m.tarball.bytes / 1048576).toFixed(1)} MB) a ${carpetaDatos()}`}`); }
    catch (e) { out(`Datos: no se pudo consultar el manifest (${e.message}); se descargarían a ${carpetaDatos()}`); }
  } else {
    if (versionActual()) out(`Datos: ya instalados (${versionActual()}). Para revisar novedades: npx leyes-mx actualizar`);
    else { await actualizarDatos({}); }
  }

  // 2. año por defecto
  if (anio !== undefined) {
    if (!dry) {
      const a = Almacen.abrir();
      if (!a.anios().includes(anio)) throw new Error(`No hay datos del año ${anio}. Disponibles: ${a.anios().join(", ") || "ninguno"}.`);
      fs.mkdirSync(carpetaBase(), { recursive: true });
      fs.writeFileSync(archivoConfig(), JSON.stringify({ ...(JSON.parse(fs.existsSync(archivoConfig()) ? fs.readFileSync(archivoConfig(), "utf8") : "{}")), anio }, null, 2) + "\n");
    }
    out(`Año por defecto: ${anio}`);
  }

  // 3. clientes
  if (!lista.length) {
    out("No encontré Claude Desktop, Claude Code, Codex ni Cursor en este equipo. Si usas Claude Desktop, ábrelo una vez y vuelve a correr este comando; o elige uno con --cliente (claude-desktop, claude-code, codex, cursor, todos). Para cualquier otro cliente MCP, usa este bloque:\n");
    out(clientes.bloqueJsonGenerico());
  } else {
    out(`\nClientes${auto ? " detectados" : ""}: ${lista.join(", ")}`);
    const o = { dryRun: dry, rutaAbsoluta: op["ruta-absoluta"] ? true : undefined, sinBinario: !!op["sin-binario"] };
    for (const c of lista) imprimirResultado(clientes.instalarCliente(c, o));
  }

  // 4. instrucciones opcionales
  if (op.instrucciones) {
    const objetivos = lista.filter((c) => clientes.rutaInstrucciones(c));
    if (!objetivos.length) out("\nInstrucciones: solo aplican a claude-code (CLAUDE.md) y codex (AGENTS.md); no hay cliente de esos seleccionado.");
    for (const c of objetivos) {
      const ruta = clientes.rutaInstrucciones(c);
      out(`\nInstrucciones para el asistente en ${ruta}:\n${clientes.BLOQUE_INSTRUCCIONES.replace(/^/gm, "    | ")}`);
      let ok = !!op.si;
      if (!ok && !dry && process.stdin.isTTY) ok = await preguntar(`¿Agregar este bloque a ${ruta}? [s/N] `);
      if (dry) { const r = clientes.instalarInstrucciones(c, { dryRun: true }); out(`  ${r.estado} (simulación)`); }
      else if (ok) { const r = clientes.instalarInstrucciones(c, {}); out(`  ${r.estado}${r.respaldo ? ` (respaldo: ${r.respaldo})` : ""}`); }
      else out("  omitido: falta confirmación (usa --si para confirmar sin preguntar).");
    }
  }

  // 4b. skill
  if (!op["sin-skill"]) {
    for (const c of lista.filter((x) => skill.CLIENTES_CON_CARPETA.includes(x))) {
      const r = skill.instalarSkill(c, { dryRun: dry });
      out(`\nSkill leyes-mx en ${c}: ${r.estado}${dry ? " (simulación)" : ""}${r.detalle ? `. ${r.detalle}` : ""}\n    carpeta: ${r.ruta}${r.respaldo ? `\n    respaldo: ${r.respaldo}` : ""}`);
    }
    if (lista.includes("claude-desktop")) out("\nSkill para Claude Desktop: es opcional (el servidor ya funciona sin ella) y se carga a mano desde la app. Si la quieres: npx leyes-mx skill --zip");
  }

  const gui = lista.filter((c) => c === "claude-desktop" || c === "cursor");
  if (gui.length && process.platform !== "win32") {
    const cmd = clientes.entradaPara(gui[0]).command;
    if (path.isAbsolute(cmd) && clientes.esRutaVersionada(cmd)) {
      out(`\nAviso: las apps de escritorio (${gui.join(" y ")}) no heredan el PATH de tu terminal, así que ${dry ? "se registraría" : "se registró"} la ruta completa de npx, que incluye la versión de Node:\n  ${cmd}\nSi cambias o borras esa versión de Node, la app dejará de encontrar el servidor. Cuando pase, repite: npx leyes-mx instalar --cliente ${gui[0]}\n(\"npx leyes-mx doctor\" también lo detecta).`);
    }
  }
  if (!dry && lista.length) out(resumenParaPersonas(lista, !resolverDatos()));
  else if (!dry) out("Verifica con: npx leyes-mx doctor");
  else out("\nVerifica con: npx leyes-mx doctor");
  return 0;
}

/** Cierre de `instalar` en español llano para quien no es técnico: qué quedó, qué hacer ahora y cómo saber que funcionó. */
export const PRUEBA_SUGERIDA = "¿Qué dice el artículo 28 de la LISR?";
function resumenParaPersonas(lista, sinDatos = false) {
  const l = ["", "----------------------------------------------------------------------", "Listo. Esto fue lo que pasó:",
    sinDatos ? "  - OJO: las leyes todavía no están descargadas (usaste --sin-datos). Descárgalas con: npx leyes-mx actualizar" : "  - Las leyes quedaron guardadas en tu equipo y verificadas; para consultarlas no se necesita internet."];
  const nombres = { "claude-desktop": "Claude Desktop", "claude-code": "Claude Code", codex: "Codex (y la app de escritorio de ChatGPT, que según la documentación de OpenAI comparte su configuración)", cursor: "Cursor" };
  l.push(`  - Quedó conectado con: ${lista.map((c) => nombres[c]).join("; ")}.`);
  l.push("", "Qué hacer ahora:");
  let n = 1;
  if (lista.includes("claude-desktop")) l.push(`  ${n++}. Reinicia Claude Desktop por completo: ciérralo del todo (en Mac, menú Claude > Salir; no basta cerrar la ventana) y vuelve a abrirlo.`);
  if (lista.some((c) => c !== "claude-desktop")) l.push(`  ${n++}. Cierra y abre de nuevo las sesiones que tengas abiertas de ${lista.filter((c) => c !== "claude-desktop").map((c) => nombres[c].split(" (")[0]).join(", ")}.`);
  l.push(`  ${n++}. Abre una conversación nueva y pega esta pregunta de prueba:`, "", `       ${PRUEBA_SUGERIDA}`, "",
    "Si funcionó: la respuesta cita la ley, el artículo y la vigencia (por ejemplo \"LISR art. 28, vigencia 2026, última reforma DOF 2024-04-01\") y la app muestra que usó \"leyes-mx\".",
    "Si responde sin citar eso o no menciona leyes-mx, corre: npx leyes-mx doctor (te dice en una línea si quedó listo y qué falta).",
    "Cuando algo no esté en la base, el asistente te preguntará si quieres que lo busque en internet; no lo hará sin tu permiso.",
    "----------------------------------------------------------------------");
  return l.join("\n");
}

async function cmdDesinstalar(op) {
  const dry = !!op["dry-run"];
  const lista = op.cliente ? elegirClientes(op).lista : clientes.CLIENTES;
  const o = { dryRun: dry, sinBinario: !!op["sin-binario"] };
  for (const c of lista) {
    imprimirResultado(clientes.desinstalarCliente(c, o));
    const r = clientes.desinstalarInstrucciones(c, o);
    if (r) out(`  instrucciones (${r.ruta}): ${r.estado}${r.respaldo ? ` (respaldo: ${r.respaldo})` : ""}`);
    if (skill.CLIENTES_CON_CARPETA.includes(c)) {
      const k = skill.quitarSkill(c, { dryRun: dry });
      if (k.estado !== "no estaba") out(`  skill (${k.ruta}): ${k.estado}${k.detalle ? `. ${k.detalle}` : ""}${k.respaldo ? ` (respaldo: ${k.respaldo})` : ""}`);
    }
  }
  if (op["borrar-datos"]) {
    if (dry) out(`Se borraría ${carpetaBase()}`);
    else { fs.rmSync(carpetaBase(), { recursive: true, force: true }); out(`Datos borrados: ${carpetaBase()}`); }
  } else out(`Los datos se conservan en ${carpetaBase()} (bórralos con --borrar-datos).`);
  if (!dry) out("Reinicia los clientes abiertos.");
  return 0;
}

function cmdSkill({ op }) {
  const dry = !!op["dry-run"];
  if (op.zip) {
    const ruta = skill.escribirZip(uno(op, "salida") ?? process.cwd(), { dryRun: dry });
    out(skill.instruccionesZip(ruta));
    if (dry) out("\n(simulación: no se escribió el archivo)");
    return 0;
  }
  const fallas = skill.verificarFuente();
  out(`Skill ${skill.SKILL_NOMBRE} (viaja en el paquete ${VERSION}): ${skill.carpetaFuente()}${fallas.length ? `\n  PROBLEMAS: ${fallas.join("; ")}` : ""}`);
  out("");
  for (const c of skill.CLIENTES_CON_CARPETA) { const e = skill.estadoSkill(c); out(`  ${c.padEnd(15)} ${TXT_SKILL[e.estado]}  ${e.ruta}`); }
  out("  claude-desktop  carga manual y opcional (no hay carpeta): npx leyes-mx skill --zip");
  out("");
  out("Se instala con: npx leyes-mx instalar (en Claude Code y Codex). Se quita con: npx leyes-mx desinstalar.");
  return fallas.length ? 1 : 0;
}

// ------------------------------------------------------------------ doctor

async function autoprueba() {
  const { Client } = await import("@modelcontextprotocol/sdk/client/index.js");
  const { StdioClientTransport } = await import("@modelcontextprotocol/sdk/client/stdio.js");
  const bin = fileURLToPath(new URL("../bin/leyes-mx.js", import.meta.url));
  const t = new StdioClientTransport({ command: process.execPath, args: [bin, "servir"], env: { ...process.env }, stderr: "ignore" });
  const c = new Client({ name: "leyes-mx-doctor", version: VERSION });
  try {
    await c.connect(t);
    const tools = (await c.listTools()).tools.map((x) => x.name);
    const r = await c.callTool({ name: "listar_leyes", arguments: {} });
    return { tools, ok: !r.isError };
  } finally { await c.close().catch(() => {}); }
}

async function cmdDoctor() {
  let fallos = 0;
  const ok = (s) => out(`  OK     ${s}`);
  const aviso = (s) => out(`  AVISO  ${s}`);
  const fallo = (s) => { fallos++; out(`  FALLO  ${s}`); };

  out(`leyes-mx ${VERSION} | ${process.platform} ${os.arch()}`);
  out("\nEntorno");
  const mayor = Number(process.versions.node.split(".")[0]);
  mayor >= 20 ? ok(`Node ${process.versions.node}`) : fallo(`Node ${process.versions.node}: se necesita 20 o superior`);
  const npx = clientes.buscarEnPath("npx");
  npx ? ok(`npx en PATH: ${npx}`) : aviso("npx no está en el PATH de esta terminal; los clientes que lo lancen no lo encontrarán (instala Node o usa --ruta-absoluta)");
  if (npx && process.platform !== "win32" && !/^\/(usr\/local|usr|opt\/homebrew)\/bin\//.test(npx)) aviso(`npx está en una ruta de usuario (${path.dirname(npx)}); las apps de escritorio no la ven por defecto. "instalar" escribe la ruta absoluta para Claude Desktop y Cursor.`);

  out("\nDatos");
  const d = resolverDatos();
  let alm = null;
  if (!d) fallo("No hay datos instalados. Ejecuta: npx leyes-mx instalar");
  else {
    ok(`${d.origen === "instalada" ? `versión ${d.version}` : "LEYES_MX_DATOS"} en ${d.raiz}`);
    alm = new Almacen(d.raiz);
    const integ = path.join(d.raiz, "INTEGRIDAD.json");
    if (fs.existsSync(integ)) { const v = datos.verificarCarpeta(d.raiz); v.ok ? ok(`integridad: ${v.revisados} archivos con sha256 correcto`) : fallo(`integridad: ${v.problemas.slice(0, 3).join("; ")}`); }
    else aviso("sin INTEGRIDAD.json (datos desde carpeta, no verificables por sha256)");
    const leyes = alm.listarLeyes();
    leyes.length ? ok(`${leyes.length} ordenamientos, años ${alm.anios().join(", ")}`) : fallo("no se encontraron leyes en los datos");
    try {
      const l = leyes[0];
      const f = alm.obtenerArticulo(l.sigla, "1", { anio: l.anio_vigencia });
      f ? ok(`lectura de prueba: ${citaArticulo(f)}`) : fallo(`no se pudo leer ${l.sigla} art. 1`);
      const t0 = Date.now();
      const res = new Indice(alm).buscar("impuesto", { limite: 1, anioDefecto: alm.anioPorDefecto() });
      res.length ? ok(`búsqueda de prueba correcta (índice en ${Date.now() - t0} ms)`) : fallo("la búsqueda de prueba no devolvió resultados");
      const g = Glosario.diagnosticar(d.raiz);
      if (!g.existe) aviso("sin glosario.json: la búsqueda funciona, pero no amplía consultas con sinónimos (npx leyes-mx actualizar)");
      else if (!g.valido) fallo(`glosario.json inválido: ${g.problemas.slice(0, 3).join("; ")}`);
      else {
        const amp = alm.glosario().expandir("actualizaciones");
        amp.entradas.length ? ok(`glosario de sinónimos: ${g.entradas} entradas (versión ${g.version})`) : fallo("el glosario cargó pero no amplió la consulta de prueba");
      }
    } catch (e) { fallo(`lectura/búsqueda: ${e.message}`); }
  }

  out("\nServidor MCP");
  let servidorOk = false;
  if (d) {
    try { const r = await autoprueba(); servidorOk = r.tools.length === 9 && r.ok; servidorOk ? ok(`initialize y tools/list correctos: ${r.tools.join(", ")}`) : fallo(`herramientas inesperadas: ${r.tools.join(", ")}`); }
    catch (e) { fallo(`el servidor no responde: ${e.message}`); }
  } else aviso("omitido (no hay datos)");

  out("\nClientes");
  let desktopMotivo = null;
  for (const c of clientes.CLIENTES) {
    const e = clientes.estadoCliente(c);
    const ruta = clientes.rutaConfig(c);
    const txt = { registrado: `registrado en ${ruta}`, ausente: clientes.detectar(c) ? `detectado pero sin registrar (npx leyes-mx instalar --cliente ${c})` : "no detectado", manual: `hay una entrada manual en ${ruta}`, distinto: `en ${ruta} existe un "${clientes.NOMBRE}" que no es de este paquete`, ilegible: `no se pudo leer ${ruta}` }[e];
    e === "registrado" ? ok(`${c}: ${txt}`) : e === "ilegible" || e === "distinto" ? fallo(`${c}: ${txt}`) : out(`  --     ${c}: ${txt}`);
    if (e === "registrado") {
      const cmd = clientes.comandoRegistrado(c);
      if (cmd && path.isAbsolute(cmd) && !fs.existsSync(cmd)) { if (c === "claude-desktop") desktopMotivo = "la ruta de npx que tiene registrada ya no existe (cambió la versión de Node)"; fallo(`${c}: la ruta de npx registrada ya no existe (${cmd}). Suele pasar al cambiar o borrar la versión de Node. Corrige con: npx leyes-mx instalar --cliente ${c}`); }
      else if (cmd && path.isAbsolute(cmd) && clientes.esRutaVersionada(cmd)) aviso(`${c}: la ruta de npx registrada incluye la versión de Node (${cmd}). Si cambias de versión, repite: npx leyes-mx instalar --cliente ${c}`);
    }
  }

  out("\nSkill (complemento opcional)");
  const fallasSkill = skill.verificarFuente();
  fallasSkill.length ? fallo(`la skill del paquete tiene problemas: ${fallasSkill.join("; ")}`) : ok("la skill que trae el paquete es válida (formato Agent Skills, descripción de hasta 200 caracteres)");
  for (const c of skill.CLIENTES_CON_CARPETA) {
    const e = skill.estadoSkill(c);
    if (e.estado === "al-dia") ok(`${c}: skill al día en ${e.ruta}`);
    else if (e.estado === "ausente") out(`  --     ${c}: skill no instalada${clientes.detectar(c) ? " (npx leyes-mx instalar)" : ""}`);
    else aviso(`${c}: skill ${TXT_SKILL[e.estado]} (${e.ruta})`);
  }
  out("  --     claude-desktop: la skill es opcional y se carga a mano (npx leyes-mx skill --zip); el servidor funciona sin ella");

  out("\nRed (solo para actualizar)");
  try { const m = await datos.leerManifest(datos.urlManifest(), { timeoutMs: 8000 }); const v = versionActual(); ok(`manifest accesible, última publicada ${m.version}${v && datos.compararVersiones(m.version, v) > 0 ? " (hay actualización: npx leyes-mx actualizar)" : ""}`); }
  catch (e) { aviso(`sin acceso al manifest (${e.message}); la consulta local funciona sin conexión`); }

  // una línea para quien no es técnico: ¿quedó listo Claude Desktop?
  out("\nResumen");
  if (!clientes.detectar("claude-desktop")) out("  Claude Desktop: no lo encontré en este equipo. Si lo usas, ábrelo una vez y corre: npx leyes-mx instalar");
  else {
    const e = clientes.estadoCliente("claude-desktop");
    const motivo = desktopMotivo ?? (e !== "registrado" ? (e === "ausente" ? "todavía no está conectado" : e === "distinto" ? "hay otro servidor con el nombre leyes-mx" : e === "ilegible" ? "no se pudo leer su configuración" : "la entrada es manual") : !d ? "no hay datos de las leyes instalados" : !servidorOk ? "el servidor no respondió" : null);
    out(motivo ? `  Claude Desktop: NO está listo (${motivo}). Solución: npx leyes-mx instalar --cliente claude-desktop`
      : `  Claude Desktop: LISTO. Ciérralo por completo, ábrelo de nuevo y pregunta: "${PRUEBA_SUGERIDA}" (debe citar la ley, el artículo y la vigencia).`);
  }

  out(fallos ? `\n${fallos} problema(s). Corrige los FALLO y repite.` : "\nTodo en orden.");
  return fallos ? 1 : 0;
}

// ------------------------------------------------------------------ consulta directa

function imprimirFicha(f) {
  out(`${f.ley} art. ${f.articulo} | vigencia ${f.anio_vigencia} | última reforma DOF ${f.ultima_reforma_dof} | estatus: ${f.estatus}`);
  if (f.aviso) { out(`>>> ${f.aviso}`); if (f.entrada_en_vigor) out(`>>> Entraría en vigor: ${f.entrada_en_vigor}`); }
  for (const a of f.advertencias || []) out(`>>> ADVERTENCIA: ${a}`);
  out(`fuente: ${f.fuente_url} (descargado ${f.fecha_descarga})`);
  out(); out(f.texto); out(); out(AVISO_GENERAL);
}

async function cmdObtener({ pos, op }) {
  if (pos.length < 3) throw new Error("uso: leyes-mx obtener LEY ARTICULO");
  const [, ley, ...art] = pos;
  const a = Almacen.abrir();
  const articulo = art.join(" ");
  const anio = entero(op, "anio");
  const f = a.obtenerArticulo(ley, articulo, { anio: anio ?? null, incluirProyectos: !!op["incluir-proyectos"] });
  if (!f) {
    err(noEncontrado(`${ley.toUpperCase()} art. ${articulo} (año ${anio ?? a.anioPorDefecto(ley)})`));
    return 1;
  }
  if (op.json) out(JSON.stringify(f, null, 2)); else imprimirFicha(f);
  return 0;
}

async function cmdBuscar({ pos, op }) {
  if (pos.length < 2) throw new Error('uso: leyes-mx buscar "texto" [--ley LEY]');
  const consulta = pos.slice(1).join(" ");
  const a = Almacen.abrir();
  const proy = !!op["incluir-proyectos"];
  const ley = uno(op, "ley") ?? null;
  const { resultados: r, ampliacion } = new Indice(a, { proyectos: proy }).buscarConDetalle(consulta, { ley, anio: entero(op, "anio") ?? null, incluirProyectos: proy,
    limite: entero(op, "limite") ?? 10, anioDefecto: a.anioPorDefecto(ley), glosario: op["sin-glosario"] ? null : a.glosario() });
  const amp = lineasAmpliacion(ampliacion);
  if (op.json) { if (amp.length) err(amp.join("\n")); out(JSON.stringify(r, null, 2)); return r.length ? 0 : 1; }
  if (amp.length) { out(amp.join("\n")); out(); }
  if (!r.length) { out(noEncontrado(`resultados para ${JSON.stringify(consulta)}`)); return 1; }
  for (const x of r) {
    const marca = (x.estatus !== "vigente" && x.estatus !== "derogado" ? "  [PROYECTO, NO ES LEY VIGENTE]" : x.estatus === "derogado" ? "  [derogado]" : "") + (x.relacionado_por_glosario ? "  [glosario]" : "");
    out(`${x.ley} art. ${x.articulo} | vigencia ${x.anio_vigencia} | última reforma DOF ${x.ultima_reforma_dof}${marca}`);
    out(`   ${x.fragmento}`);
  }
  return 0;
}

function cmdTarifa({ pos, op }) {
  const a = Almacen.abrir();
  const anio = entero(op, "anio") ?? null;
  const clave = pos[1];
  if (!clave) {
    const lista = a.listarTarifas(anio);
    if (op.json) { out(JSON.stringify(lista, null, 2)); return lista.length ? 0 : 1; }
    if (!lista.length) { err(noEncontrado("el Anexo 8 de la RMF") + "\n"); return 1; }
    out(respuestaTarifas(lista));
    return 0;
  }
  const t = a.obtenerTarifa(clave, anio);
  if (!t) { err(noEncontrado(`la tarifa ${clave} del Anexo 8 de la RMF`) + "\n"); return 1; }
  if (t.ambiguo) { err(`La clave ${clave} corresponde a varias tarifas; usa el id exacto:\n${t.ambiguo.map((x) => `  ${x.id}  ${x.titulo}`).join("\n")}\n`); return 2; }
  out(op.json ? JSON.stringify(t, null, 2) : respuestaTarifa(t));
  return 0;
}

function cmdSubsidio({ pos, op }) {
  const a = Almacen.abrir();
  const f = a.obtenerSubsidioEmpleo({ anio: entero(op, "anio") ?? null, documento: pos[1] ?? null });
  if (!f) { err(noEncontrado(pos[1] ? `el documento ${pos[1]} del subsidio para el empleo` : "el subsidio para el empleo") + "\n"); return 1; }
  out(op.json ? JSON.stringify(f, null, 2) : respuestaSubsidio(f));
  return 0;
}

function cmdListar({ op }) {
  const r = Almacen.abrir().listarLeyes({ incluirProyectos: !!op["incluir-proyectos"] });
  if (op.json) { out(JSON.stringify(r, null, 2)); return 0; }
  for (const x of r) out(`${x.sigla.padEnd(6)} ${x.anio_vigencia} ${x.estatus.padEnd(8)} arts=${String(x.articulos).padEnd(5)} última reforma DOF ${x.ultima_reforma_dof}  ${x.nombre || ""}`);
  return 0;
}

// ------------------------------------------------------------------ principal

export async function main(argv) {
  const { pos, op } = parsear(argv);
  const cmd = pos[0];
  if (op.version || cmd === "version") { out(VERSION); return 0; }
  if (!cmd || op.ayuda || cmd === "ayuda" || cmd === "help") { out(AYUDA); return 0; }
  try {
    switch (cmd) {
      case "servir": { const { servir } = await import("./servidor.js"); await servir(); return await new Promise(() => {}); }
      case "instalar": return await cmdInstalar(op);
      case "actualizar": return await cmdActualizar(op);
      case "revertir": { const r = datos.revertir(); out(`Datos revertidos a ${r.actual} (antes ${r.anterior}).`); return 0; }
      case "desinstalar": return await cmdDesinstalar(op);
      case "estado": return await cmdEstado();
      case "doctor": return await cmdDoctor();
      case "skill": return cmdSkill({ op });
      case "obtener": return await cmdObtener({ pos, op });
      case "tarifa": return cmdTarifa({ pos, op });
      case "subsidio": return cmdSubsidio({ pos, op });
      case "buscar": return await cmdBuscar({ pos, op });
      case "listar": return cmdListar({ op });
      case "reforma": out(JSON.stringify(Almacen.abrir().estadoReforma(entero(op, "anio") ?? null), null, 2)); return 0;
      default: err(`Comando desconocido: ${cmd}\n`); err(AYUDA); return 2;
    }
  } catch (e) {
    if (e instanceof SinDatos) { err(e.message); return 1; }
    err(`Error: ${e.message}`);
    return 1;
  }
}
