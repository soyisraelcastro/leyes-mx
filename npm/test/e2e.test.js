import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";
import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import { correr, REPO } from "./ayuda.js";

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "leyes-mx-e2e-"));
const HOME = path.join(tmp, "home");
const LM = path.join(tmp, "lm");
const A = path.join(tmp, "pub1"), B = path.join(tmp, "pub2"), C = path.join(tmp, "pub3");
const ENV = { HOME, LEYES_MX_HOME: LM, LEYES_MX_MANIFEST: path.join(A, "manifest.json"), CLAUDE_CONFIG_DIR: "", CODEX_HOME: "", LEYES_MX_DATOS: "" };
for (const k of ["CLAUDE_CONFIG_DIR", "CODEX_HOME", "LEYES_MX_DATOS"]) delete process.env[k];
const run = (args, extra = {}) => correr(args, { ...ENV, ...extra });
const salida = (r) => r.stdout + r.stderr;
const sha = (b) => crypto.createHash("sha256").update(b).digest("hex");

const desktop = path.join(HOME, "Library", "Application Support", "Claude", "claude_desktop_config.json");
const cursor = path.join(HOME, ".cursor", "mcp.json");
const codex = path.join(HOME, ".codex", "config.toml");
const claudeJson = path.join(HOME, ".claude.json");
const leer = (p) => fs.readFileSync(p, "utf8");

function empaquetar(salidaDir, version, raiz = REPO) {
  const r = spawnSync("python3", ["-I", path.join(REPO, "scripts", "empaquetar_datos.py"), "--salida", salidaDir, "--version", version, "--raiz", raiz], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
}

test.before(() => {
  fs.mkdirSync(path.dirname(desktop), { recursive: true });
  fs.writeFileSync(desktop, JSON.stringify({ globalShortcut: "Ctrl+Space", mcpServers: { otro: { command: "node", args: ["x.js"] } } }, null, 2));
  fs.mkdirSync(path.dirname(cursor), { recursive: true });
  fs.writeFileSync(cursor, JSON.stringify({ mcpServers: { otro: { command: "uvx", args: ["y"] } } }));
  fs.mkdirSync(path.dirname(codex), { recursive: true });
  fs.writeFileSync(codex, 'model = "gpt-x"\n\n[mcp_servers.otro]\ncommand = "node"\nargs = ["z.js"]\n');
  fs.writeFileSync(claudeJson, JSON.stringify({ numStartups: 3, mcpServers: { otro: { type: "stdio", command: "a", args: [] } } }));
  empaquetar(A, "2026.11.02");
});
test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));

test("instalar --dry-run no escribe nada", () => {
  const antes = [desktop, cursor, codex, claudeJson].map(leer);
  const r = run(["instalar", "--cliente", "todos", "--dry-run", "--sin-binario"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /Simulación/);
  assert.match(r.stdout, /claude-desktop: agregado/);
  assert.match(r.stdout, /mcp_servers\.leyes-mx/);
  assert.deepEqual([desktop, cursor, codex, claudeJson].map(leer), antes);
  assert.ok(!fs.existsSync(LM), "no debe crear la carpeta de datos");
});

test("instalar --cliente todos: datos + 4 clientes, fusionando sin pisar", () => {
  const r = run(["instalar", "--cliente", "todos", "--sin-binario", "--anio", "2026"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /Reinicia Claude Desktop/);
  assert.equal(leer(path.join(LM, "actual")).trim(), "2026.11.02");
  assert.ok(fs.existsSync(path.join(LM, "datos", "2026.11.02", "leyes", "2026", "LISR", "art-0028.md")));
  const d = JSON.parse(leer(desktop));
  assert.equal(d.globalShortcut, "Ctrl+Space");
  assert.deepEqual(d.mcpServers.otro, { command: "node", args: ["x.js"] });
  assert.deepEqual(d.mcpServers["leyes-mx"].args, ["-y", "leyes-mx", "servir"]);
  assert.match(d.mcpServers["leyes-mx"].command, /npx$/);
  assert.ok(d.mcpServers["leyes-mx"].env.PATH);
  assert.ok(fs.readdirSync(path.dirname(desktop)).some((f) => f.includes(".bak-leyes-mx-")), "respaldo del config de Claude Desktop");
  const cu = JSON.parse(leer(cursor));
  assert.ok(cu.mcpServers.otro && cu.mcpServers["leyes-mx"]);
  const cj = JSON.parse(leer(claudeJson));
  assert.equal(cj.numStartups, 3);
  assert.deepEqual(cj.mcpServers["leyes-mx"], { type: "stdio", command: "npx", args: ["-y", "leyes-mx", "servir"], env: {} });
  const t = leer(codex);
  assert.match(t, /\[mcp_servers\.otro\]/);
  assert.match(t, /\[mcp_servers\.leyes-mx\]\ncommand = "npx"\nargs = \["-y", "leyes-mx", "servir"\]\nstartup_timeout_sec = 60/);
  assert.match(t, /^model = "gpt-x"/);
  assert.equal(JSON.parse(leer(path.join(LM, "config.json"))).anio, 2026);
});

test("idempotencia: segunda corrida no cambia nada ni duplica", () => {
  const antes = [desktop, cursor, codex, claudeJson].map(leer);
  const bakAntes = fs.readdirSync(path.dirname(desktop)).length;
  const r = run(["instalar", "--cliente", "todos", "--sin-binario"]);
  assert.equal(r.status, 0, salida(r));
  assert.equal((r.stdout.match(/: sin cambios/g) || []).length, 4, r.stdout);
  assert.deepEqual([desktop, cursor, codex, claudeJson].map(leer), antes);
  assert.equal(fs.readdirSync(path.dirname(desktop)).length, bakAntes, "no genera más respaldos si no cambia");
  assert.equal((leer(codex).match(/\[mcp_servers\.leyes-mx\]/g) || []).length, 1);
});

test("instrucciones: solo con bandera y confirmación; no toca CLAUDE.md sin ella", () => {
  const claudeMd = path.join(HOME, ".claude", "CLAUDE.md");
  const agents = path.join(HOME, ".codex", "AGENTS.md");
  assert.ok(!fs.existsSync(claudeMd) && !fs.existsSync(agents));
  let r = run(["instalar", "--cliente", "claude-code,codex", "--sin-binario", "--instrucciones"], {}); // sin TTY y sin --si
  assert.match(r.stdout, /omitido: falta confirmación/);
  assert.ok(!fs.existsSync(claudeMd));
  r = run(["instalar", "--cliente", "claude-code,codex", "--sin-binario", "--instrucciones", "--si"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(leer(claudeMd), /<!-- leyes-mx:inicio -->[\s\S]*no verificado[\s\S]*<!-- leyes-mx:fin -->/);
  const una = leer(agents);
  run(["instalar", "--cliente", "claude-code,codex", "--sin-binario", "--instrucciones", "--si"]);
  assert.equal(leer(agents), una);
});

test("estado y doctor", () => {
  let r = run(["estado"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /Datos instalados: 2026\.11\.02/);
  assert.match(r.stdout, /Última publicada: 2026\.11\.02.*al día/);
  assert.match(r.stdout, /LISR\s+2026\s+2024-04-01/);
  r = run(["doctor"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /integridad: \d+ archivos con sha256 correcto/);
  assert.match(r.stdout, /initialize y tools\/list correctos/);
  assert.match(r.stdout, /claude-desktop: registrado/);
  assert.match(r.stdout, /codex: registrado/);
  assert.match(r.stdout, /Todo en orden/);
});

test("consulta directa con los datos instalados", () => {
  let r = run(["obtener", "LISR", "113", "e"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /LISR art\. 113-E \| vigencia 2026 \| última reforma DOF 2024-04-01/);
  r = run(["obtener", "LISR", "9999"]);
  assert.equal(r.status, 1);
  assert.match(r.stderr, /NO VERIFICADO/);
  r = run(["buscar", "recargos deducibles", "--ley", "LISR", "--limite", "2"]);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /LISR art\./);
});

test("actualizar con versión nueva: descarga, verifica sha256, activa y conserva la anterior", () => {
  // versión nueva simulada: copia de datos con un artículo distinto
  const copia = path.join(tmp, "copia");
  fs.mkdirSync(copia);
  for (const d of ["leyes", "tablas", "proyectos"]) fs.cpSync(path.join(REPO, d), path.join(copia, d), { recursive: true });
  fs.copyFileSync(path.join(REPO, "fuentes.json"), path.join(copia, "fuentes.json"));
  const f = path.join(copia, "leyes", "2026", "LISR", "_meta.json");
  fs.writeFileSync(f, leer(f).replace('"ultima_reforma_dof": "2024-04-01"', '"ultima_reforma_dof": "2026-12-01"'));
  empaquetar(B, "2026.11.03", copia);
  const env = { LEYES_MX_MANIFEST: path.join(B, "manifest.json") };
  let r = run(["estado"], env);
  assert.match(r.stdout, /hay una versión nueva/);
  assert.match(r.stdout, /LISR\s+2026\s+2024-04-01\s+\|\s+2026-12-01\s+\(cambió\)/);
  r = run(["actualizar"], env);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stderr, /sha256 del tarball verificado/);
  assert.equal(leer(path.join(LM, "actual")).trim(), "2026.11.03");
  assert.equal(leer(path.join(LM, "anterior")).trim(), "2026.11.02");
  assert.ok(fs.existsSync(path.join(LM, "datos", "2026.11.02")), "se conserva la anterior");
  r = run(["actualizar"], env);
  assert.match(r.stdout, /ya están al día/);
  r = run(["revertir"]);
  assert.match(r.stdout, /revertidos a 2026\.11\.02/);
  assert.equal(leer(path.join(LM, "actual")).trim(), "2026.11.02");
  run(["actualizar"], env);
  assert.equal(leer(path.join(LM, "actual")).trim(), "2026.11.03");
});

function nuevaVersionAlterada(dir, version, modo) {
  const copia = path.join(tmp, "copia2-" + version);
  fs.mkdirSync(copia);
  for (const d of ["leyes", "tablas", "proyectos"]) fs.cpSync(path.join(REPO, d), path.join(copia, d), { recursive: true });
  fs.copyFileSync(path.join(REPO, "fuentes.json"), path.join(copia, "fuentes.json"));
  empaquetar(dir, version, copia);
  const tgz = path.join(dir, "leyes-mx-datos.tar.gz");
  const man = path.join(dir, "manifest.json");
  if (modo === "bytes") { // alteración del tarball sin tocar el manifest
    const b = fs.readFileSync(tgz);
    b[Math.floor(b.length / 2)] ^= 0xff;
    fs.writeFileSync(tgz, b);
  } else { // atacante que reescribe un archivo y recalcula el sha del tarball en el manifest; INTEGRIDAD.json lo delata
    const tar = zlib.gunzipSync(fs.readFileSync(tgz));
    const marca = Buffer.from("# Artículo 28\n");
    const i = tar.indexOf(marca);
    assert.ok(i > 0);
    tar.write("# ARTÍCULO 28\n", i); // misma longitud en bytes
    const nuevo = zlib.gzipSync(tar);
    fs.writeFileSync(tgz, nuevo);
    const m = JSON.parse(leer(man));
    m.tarball.sha256 = sha(nuevo); m.tarball.bytes = nuevo.length;
    fs.writeFileSync(man, JSON.stringify(m));
  }
}

for (const modo of ["bytes", "archivo"]) {
  test(`archivo alterado (${modo}) es rechazado y NO se activa`, () => {
    const dir = path.join(tmp, "alt-" + modo);
    nuevaVersionAlterada(dir, modo === "bytes" ? "2026.11.04" : "2026.11.05", modo);
    const antes = leer(path.join(LM, "actual")).trim();
    const r = run(["actualizar"], { LEYES_MX_MANIFEST: path.join(dir, "manifest.json") });
    assert.equal(r.status, 1, salida(r));
    assert.match(r.stderr, modo === "bytes" ? /sha256 del tarball NO coincide/ : /verificación por archivo fallida/);
    assert.equal(leer(path.join(LM, "actual")).trim(), antes, "la versión activa no cambió");
    assert.ok(!fs.readdirSync(path.join(LM, "datos")).some((n) => n.includes("2026.11.04") || n.includes("2026.11.05") || n.startsWith(".tmp-")), "no queda nada a medias");
    assert.equal(run(["obtener", "LISR", "28"]).status, 0);
  });
}

test("desinstalar --dry-run no toca nada; desinstalar revierte solo lo suyo", () => {
  const antes = [desktop, cursor, codex, claudeJson].map(leer);
  let r = run(["desinstalar", "--sin-binario", "--dry-run"]);
  assert.equal(r.status, 0, salida(r));
  assert.deepEqual([desktop, cursor, codex, claudeJson].map(leer), antes);
  r = run(["desinstalar", "--sin-binario"]);
  assert.equal(r.status, 0, salida(r));
  const d = JSON.parse(leer(desktop));
  assert.deepEqual(Object.keys(d.mcpServers), ["otro"]);
  assert.equal(d.globalShortcut, "Ctrl+Space");
  assert.deepEqual(Object.keys(JSON.parse(leer(cursor)).mcpServers), ["otro"]);
  assert.deepEqual(Object.keys(JSON.parse(leer(claudeJson)).mcpServers), ["otro"]);
  const t = leer(codex);
  assert.ok(!t.includes("leyes-mx"));
  assert.match(t, /\[mcp_servers\.otro\]\ncommand = "node"\nargs = \["z\.js"\]/);
  assert.match(t, /^model = "gpt-x"/);
  assert.ok(!fs.existsSync(path.join(HOME, ".claude", "CLAUDE.md")) || !leer(path.join(HOME, ".claude", "CLAUDE.md")).includes("leyes-mx"));
  assert.ok(fs.existsSync(path.join(LM, "datos")), "los datos se conservan");
  r = run(["desinstalar", "--sin-binario"]);
  assert.match(r.stdout, /no estaba/);
});

test("entrada ajena llamada leyes-mx no se pisa", () => {
  fs.writeFileSync(cursor, JSON.stringify({ mcpServers: { "leyes-mx": { command: "python", args: ["mio.py"] } } }));
  const r = run(["instalar", "--cliente", "cursor", "--sin-datos"]);
  assert.match(r.stdout, /cursor: omitido/);
  assert.deepEqual(JSON.parse(leer(cursor)).mcpServers["leyes-mx"], { command: "python", args: ["mio.py"] });
});

test("config JSON inválido: no se sobrescribe", () => {
  fs.writeFileSync(cursor, "{ roto");
  const r = run(["instalar", "--cliente", "cursor", "--sin-datos"]);
  assert.match(r.stdout, /cursor: error/);
  assert.equal(leer(cursor), "{ roto");
});

test("sin datos instalados y sin red, la consulta falla con un mensaje claro", () => {
  const r = run(["obtener", "LISR", "28"], { LEYES_MX_HOME: path.join(tmp, "vacio") });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /No hay datos instalados/);
});
