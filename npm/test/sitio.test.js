import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { correr, REPO } from "./ayuda.js";
import { bloqueJsonGenerico, ARGS } from "../src/clientes.js";

const dist = path.join(REPO, "sitio", "dist");
const hay = fs.existsSync(path.join(dist, "index.html"));
// El sitio tiene varias páginas (portada y /docs/*): los comandos viven en la documentación, así que se leen todas.
const paginas = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? paginas(path.join(d, e.name)) : e.name.endsWith(".html") ? [path.join(d, e.name)] : []));
const leerSitio = () => paginas(dist).map((f) => fs.readFileSync(f, "utf8")).join("\n");

const decodificar = (s) => s.replaceAll("&quot;", '"').replaceAll("&#34;", '"').replaceAll("&#39;", "'").replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&amp;", "&");

test("los comandos de la landing coinciden con lo implementado", { skip: !hay && "primero: cd sitio && npm run build" }, () => {
  const html = leerSitio();
  const copiables = [...html.matchAll(/data-copiar="([^"]*)"/g)].map((m) => decodificar(m[1]));
  assert.ok(copiables.length >= 10, "debe haber bloques copiables");
  const ayuda = correr(["--ayuda"]).stdout;
  const comandosValidos = new Set(["instalar", "actualizar", "revertir", "desinstalar", "estado", "doctor", "servir", "obtener", "buscar", "listar", "reforma"]);
  const nombresAyuda = [...ayuda.matchAll(/^ {2}(\w+)/gm)].map((m) => m[1]);
  for (const c of comandosValidos) assert.ok(nombresAyuda.includes(c), `la ayuda no documenta ${c}`);

  const cmds = copiables.filter((c) => c.startsWith("npx leyes-mx "));
  assert.ok(cmds.length >= 8);
  for (const c of cmds) {
    const resto = c.slice("npx leyes-mx ".length);
    assert.ok(comandosValidos.has(resto.split(" ")[0]), `comando inexistente en la landing: ${c}`);
    for (const flag of resto.match(/--[a-z-]+/g) || []) assert.ok(ayuda.includes(flag), `bandera ${flag} no existe: ${c}`);
  }

  // los comandos "instalar --cliente X" se ejecutan de verdad en modo simulación contra una carpeta vacía
  const env = { HOME: fs.mkdtempSync(path.join(REPO, "build", "sitio-")), LEYES_MX_HOME: "", LEYES_MX_DATOS: REPO };
  try {
    for (const c of cmds.filter((x) => x.includes("instalar"))) {
      const args = c.slice("npx leyes-mx ".length).split(" ");
      const r = correr([...args, "--dry-run", "--sin-binario"], env);
      assert.equal(r.status, 0, `${c}: ${r.stderr}`);
    }
    // bloque genérico JSON, TOML de Codex y comando de Claude Code: idénticos a lo que escribe/ejecuta el instalador
    const jsons = copiables.filter((c) => c.startsWith("{")).map((c) => JSON.parse(c));
    assert.ok(jsons.length >= 2);
    for (const j of jsons) assert.deepEqual(j, JSON.parse(bloqueJsonGenerico()), "el bloque JSON de la landing no es el del instalador");
    const cod = correr(["instalar", "--cliente", "codex", "--dry-run"], env).stdout;
    const toml = copiables.find((c) => c.startsWith("[mcp_servers.leyes-mx]"));
    for (const linea of toml.split("\n")) assert.ok(cod.includes("| " + linea), `línea TOML no coincide: ${linea}`);
    const cc = correr(["instalar", "--cliente", "claude-code", "--dry-run"], { ...env, PATH: process.env.PATH }).stdout;
    const claude = copiables.find((c) => c.startsWith("claude mcp add"));
    if (cc.includes("ejecutaría:")) assert.ok(cc.includes("ejecutaría: " + claude), "el comando de claude mcp add no coincide");
    assert.deepEqual(ARGS, ["-y", "leyes-mx", "servir"]);
    assert.ok(claude.endsWith("-- npx -y leyes-mx servir"));
  } finally { fs.rmSync(env.HOME, { recursive: true, force: true }); }
});

test("la landing no usa github.io, ni llamadas a terceros, ni raya larga", { skip: !hay }, () => {
  const html = leerSitio();
  assert.ok(!html.includes("github.io"));
  assert.ok(!html.includes("\u2014") && !html.includes("\u00ab"));
  const externos = [...html.matchAll(/(?:src|href)="(https?:\/\/[^"]+)"/g)].map((m) => m[1]).filter((u) => !u.startsWith("https://github.com/soyisraelcastro/leyes-mx") && !u.startsWith("https://todoconta.com"));
  assert.deepEqual(externos.filter((u) => !u.includes("example.com") && !u.startsWith("https://leyes.todoconta.com")), []);
  void spawnSync;
});
