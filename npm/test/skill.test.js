import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { correr, NPM, REPO } from "./ayuda.js";
import { parseSkillMd, verificarFuente, construirZip, crc32, huella } from "../src/skill.js";

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "leyes-mx-skill-"));
test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
for (const k of ["CLAUDE_CONFIG_DIR", "CODEX_HOME", "LEYES_MX_DATOS"]) delete process.env[k];

let n = 0;
/** Entorno aislado: HOME temporal, datos del repo, sin red (manifest inexistente). */
function entorno() {
  const base = path.join(tmp, `e${++n}`);
  const HOME = path.join(base, "home");
  fs.mkdirSync(path.join(HOME, "Library", "Application Support", "Claude"), { recursive: true });
  fs.mkdirSync(path.join(HOME, ".codex"), { recursive: true });
  const env = { HOME, LEYES_MX_HOME: path.join(base, "lm"), LEYES_MX_DATOS: REPO, LEYES_MX_MANIFEST: path.join(base, "no-existe.json"), CLAUDE_CONFIG_DIR: "", CODEX_HOME: "" };
  const run = (args, extra = {}) => correr(args, { ...env, ...extra });
  return { base, HOME, env, run, claudeSkill: path.join(HOME, ".claude", "skills", "leyes-mx"), codexSkill: path.join(HOME, ".agents", "skills", "leyes-mx") };
}
const salida = (r) => r.stdout + r.stderr;
const leer = (p) => fs.readFileSync(p, "utf8");

test("la skill del paquete cumple el formato de Agent Skills y los límites de claude.ai", () => {
  assert.deepEqual(verificarFuente(), []);
  const t = leer(path.join(NPM, "skills", "leyes-mx", "SKILL.md"));
  const fm = parseSkillMd(t);
  assert.equal(fm.name, "leyes-mx");
  assert.ok(fm.description.length <= 200 && fm.description.length > 50, `${fm.description.length} caracteres`);
  assert.ok(t.split("\n").length < 500);
  assert.ok(!/[\u2014\u00ab\u00bb]/.test(t), "sin raya larga ni comillas angulares");
  for (const re of [/obtener_articulo/, /buscar/, /obtener_tarifa/, /npx leyes-mx buscar/, /npx leyes-mx obtener/, /npx leyes-mx tarifa/, /npx leyes-mx reforma/, /PREGUNTA|pregunta al usuario/i, /2027/, /proyecto/, /Anexo 8/,
    /fracción/, /última reforma/, /Cámara de Diputados/]) assert.match(t, re);
});

test("el paquete npm incluye la skill (files de package.json)", () => {
  const pkg = JSON.parse(leer(path.join(NPM, "package.json")));
  assert.ok(pkg.files.includes("skills"));
  const r = spawnSync("npm", ["pack", "--dry-run", "--json"], { cwd: NPM, encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  const nombres = JSON.parse(r.stdout)[0].files.map((f) => f.path);
  assert.ok(nombres.includes("skills/leyes-mx/SKILL.md"), nombres.join(", "));
  assert.ok(!nombres.some((x) => x.startsWith("test/") || x.includes("glosario.json")));
});

test("instalar --dry-run no escribe la skill", () => {
  const e = entorno();
  const r = e.run(["instalar", "--cliente", "todos", "--dry-run", "--sin-binario"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /Skill leyes-mx en claude-code: agregada \(simulación\)/);
  assert.match(r.stdout, /Skill leyes-mx en codex: agregada \(simulación\)/);
  assert.ok(!fs.existsSync(e.claudeSkill) && !fs.existsSync(e.codexSkill));
});

test("instalar copia la skill donde corresponde, es idempotente y Claude Desktop recibe solo la indicación del .zip", () => {
  const e = entorno();
  const r = e.run(["instalar", "--cliente", "claude-desktop,claude-code,codex", "--sin-binario"]);
  assert.equal(r.status, 0, salida(r));
  for (const d of [e.claudeSkill, e.codexSkill]) {
    assert.ok(fs.existsSync(path.join(d, "SKILL.md")), d);
    assert.equal(JSON.parse(leer(path.join(d, ".leyes-mx-skill.json"))).paquete, "leyes-mx");
    assert.equal(leer(path.join(d, "SKILL.md")), leer(path.join(NPM, "skills", "leyes-mx", "SKILL.md")));
  }
  assert.match(r.stdout, /Skill para Claude Desktop: es opcional.*npx leyes-mx skill --zip/);
  assert.ok(!fs.existsSync(path.join(e.HOME, "Library", "Application Support", "Claude", "skills")));
  const otra = e.run(["instalar", "--cliente", "claude-code,codex", "--sin-binario"]);
  assert.equal((otra.stdout.match(/Skill leyes-mx en \S+: sin cambios/g) || []).length, 2, otra.stdout);
  assert.ok(!fs.existsSync(path.join(e.base, "lm", "respaldos")), "sin cambios no genera respaldos");
});

test("--sin-skill omite la skill; CLAUDE_CONFIG_DIR cambia la carpeta de Claude Code", () => {
  const e = entorno();
  let r = e.run(["instalar", "--cliente", "claude-code,codex", "--sin-binario", "--sin-skill"]);
  assert.equal(r.status, 0, salida(r));
  assert.ok(!fs.existsSync(e.claudeSkill) && !fs.existsSync(e.codexSkill));
  const otra = path.join(e.base, "otra-config");
  r = e.run(["instalar", "--cliente", "claude-code", "--sin-binario"], { CLAUDE_CONFIG_DIR: otra });
  assert.ok(fs.existsSync(path.join(otra, "skills", "leyes-mx", "SKILL.md")), salida(r));
  assert.ok(!fs.existsSync(e.claudeSkill));
});

test("actualizar refresca la skill modificada o vieja con respaldo FUERA de la carpeta de skills, y no la agrega donde no estaba", () => {
  const e = entorno();
  e.run(["instalar", "--cliente", "claude-code", "--sin-binario"]);
  const md = path.join(e.claudeSkill, "SKILL.md");
  const original = leer(md);
  fs.writeFileSync(md, original + "\nEdición manual.\n");
  let r = e.run(["estado"]);
  assert.match(r.stdout, /claude-code\s+modificada a mano/);
  r = e.run(["doctor"]);
  assert.match(r.stdout, /AVISO  claude-code: skill modificada a mano/);
  r = e.run(["actualizar"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /Skill \(claude-code\): actualizada \(respaldo: /);
  assert.equal(leer(md), original);
  const resp = path.join(e.base, "lm", "respaldos");
  const dirs = fs.readdirSync(resp);
  assert.equal(dirs.length, 1);
  assert.match(leer(path.join(resp, dirs[0], "SKILL.md")), /Edición manual/);
  assert.ok(fs.readdirSync(path.dirname(e.claudeSkill)).every((x) => x === "leyes-mx"), "ningún respaldo dentro de ~/.claude/skills");
  assert.ok(!fs.existsSync(e.codexSkill), "actualizar no agrega la skill en Codex");
  // skill de una versión anterior del paquete: archivos distintos a los actuales, pero la marca coincide con ellos
  fs.writeFileSync(md, "---\nname: leyes-mx\ndescription: versión anterior\n---\nvieja\n");
  const marca = path.join(e.claudeSkill, ".leyes-mx-skill.json");
  fs.writeFileSync(marca, JSON.stringify({ paquete: "leyes-mx", version: "0.0.1", sha256: huella(e.claudeSkill) }));
  r = e.run(["estado"]);
  assert.match(r.stdout, /claude-code\s+desactualizada/);
  e.run(["actualizar"]);
  assert.equal(leer(md), original);
  assert.match(e.run(["estado"]).stdout, /claude-code\s+al día/);
});

test("una carpeta leyes-mx ajena no se toca ni al instalar ni al desinstalar", () => {
  const e = entorno();
  fs.mkdirSync(e.claudeSkill, { recursive: true });
  fs.writeFileSync(path.join(e.claudeSkill, "SKILL.md"), "---\nname: leyes-mx\ndescription: mía\n---\nmi skill\n");
  let r = e.run(["instalar", "--cliente", "claude-code", "--sin-binario"]);
  assert.match(r.stdout, /Skill leyes-mx en claude-code: omitida\. ya hay una carpeta leyes-mx que no puso este paquete/);
  assert.match(leer(path.join(e.claudeSkill, "SKILL.md")), /mi skill/);
  r = e.run(["desinstalar", "--cliente", "claude-code", "--sin-binario"]);
  assert.match(r.stdout, /skill \(.*\): omitida/);
  assert.match(leer(path.join(e.claudeSkill, "SKILL.md")), /mi skill/);
  assert.match(e.run(["doctor"]).stdout, /AVISO  claude-code: skill hay otra carpeta con ese nombre/);
});

test("desinstalar quita la skill con respaldo; --dry-run no toca nada", () => {
  const e = entorno();
  e.run(["instalar", "--cliente", "claude-code,codex", "--sin-binario"]);
  let r = e.run(["desinstalar", "--sin-binario", "--dry-run"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /skill \(.*\): se quitaría/);
  assert.ok(fs.existsSync(e.claudeSkill) && fs.existsSync(e.codexSkill));
  r = e.run(["desinstalar", "--sin-binario"]);
  assert.equal(r.status, 0, salida(r));
  assert.ok(!fs.existsSync(e.claudeSkill) && !fs.existsSync(e.codexSkill));
  assert.equal(fs.readdirSync(path.join(e.base, "lm", "respaldos")).length, 2);
  r = e.run(["desinstalar", "--sin-binario"]);
  assert.doesNotMatch(r.stdout, /skill \(/, "si no estaba, no dice nada");
});

test("skill --zip escribe un .zip válido con la carpeta en la raíz, determinista, y explica cómo cargarlo", () => {
  const e = entorno();
  const dir = path.join(e.base, "salida");
  let r = e.run(["skill", "--zip", "--salida", dir]);
  assert.equal(r.status, 0, salida(r));
  const zip = path.join(dir, "leyes-mx-skill.zip");
  assert.ok(fs.existsSync(zip));
  assert.match(r.stdout, /Personalizar \(Customize\)/);
  assert.match(r.stdout, /Subir una skill/);
  assert.match(r.stdout, /opcional/);
  const py = spawnSync("python3", ["-I", "-c", "import sys, zipfile\nz = zipfile.ZipFile(sys.argv[1])\nassert z.testzip() is None\nprint('\\n'.join(z.namelist()))\nprint('@@@')\nprint(z.read('leyes-mx/SKILL.md').decode()[:40])", zip], { encoding: "utf8" });
  assert.equal(py.status, 0, py.stderr);
  const [nombres, inicio] = py.stdout.split("@@@\n");
  assert.equal(nombres.trim(), "leyes-mx/SKILL.md");
  assert.match(inicio, /^---\nname: leyes-mx/);
  const h1 = crypto.createHash("sha256").update(fs.readFileSync(zip)).digest("hex");
  fs.rmSync(zip);
  e.run(["skill", "--zip", "--salida", dir]);
  assert.equal(crypto.createHash("sha256").update(fs.readFileSync(zip)).digest("hex"), h1);
  r = e.run(["skill", "--zip", "--salida", path.join(e.base, "otra"), "--dry-run"]);
  assert.ok(!fs.existsSync(path.join(e.base, "otra", "leyes-mx-skill.zip")));
  assert.match(r.stdout, /simulación/);
  assert.equal(crc32(Buffer.from("123456789")), 0xcbf43926);
  assert.ok(construirZip([{ nombre: "a/b.txt", datos: Buffer.from("hola") }]).length > 30);
});

test("skill sin banderas informa el estado por cliente", () => {
  const e = entorno();
  let r = e.run(["skill"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /claude-code\s+no instalada/);
  assert.match(r.stdout, /claude-desktop\s+carga manual y opcional/);
  e.run(["instalar", "--cliente", "codex", "--sin-binario"]);
  r = e.run(["skill"]);
  assert.match(r.stdout, /codex\s+al día/);
});

test("instalar termina en español llano: reiniciar, pregunta de prueba y señal de que funcionó", () => {
  const e = entorno();
  const r = e.run(["instalar", "--cliente", "claude-desktop", "--sin-binario"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /Reinicia Claude Desktop por completo: ciérralo del todo.*vuelve a abrirlo/);
  assert.match(r.stdout, /¿Qué dice el artículo 28 de la LISR\?/);
  assert.match(r.stdout, /cita la ley, el artículo y la vigencia/);
  assert.match(r.stdout, /no lo hará sin tu permiso/);
  assert.ok(!/[\u2014\u00ab\u00bb]/.test(r.stdout));
});

test("doctor dice en una línea si Claude Desktop quedó listo", () => {
  const e = entorno();
  let r = e.run(["doctor"]);
  assert.match(r.stdout, /Claude Desktop: NO está listo \(todavía no está conectado\)\. Solución: npx leyes-mx instalar --cliente claude-desktop/);
  e.run(["instalar", "--cliente", "claude-desktop", "--sin-binario"]);
  r = e.run(["doctor"]);
  assert.equal(r.status, 0, salida(r));
  assert.match(r.stdout, /Claude Desktop: LISTO\. Ciérralo por completo, ábrelo de nuevo y pregunta: "¿Qué dice el artículo 28 de la LISR\?"/);
  fs.rmSync(path.join(e.HOME, "Library"), { recursive: true });
  r = e.run(["doctor"]);
  assert.match(r.stdout, /Claude Desktop: no lo encontré en este equipo/);
});
