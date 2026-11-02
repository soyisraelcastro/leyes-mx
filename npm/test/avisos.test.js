import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { esRutaVersionada } from "../src/clientes.js";
import { correr, REPO } from "./ayuda.js";

test("esRutaVersionada: detecta gestores de versiones de Node", () => {
  for (const p of [
    "/Users/a/.nvm/versions/node/v24.15.0/bin/npx",
    "/home/a/.local/state/fnm_multishells/123_456/bin/npx",
    "/home/a/.asdf/installs/nodejs/22.1.0/bin/npx",
    "/home/a/.nodenv/versions/20.1.0/bin/npx",
    "/home/a/.fnm/node-versions/v22.0.0/installation/bin/npx",
  ]) assert.equal(esRutaVersionada(p), true, p);
  for (const p of ["/opt/homebrew/bin/npx", "/usr/local/bin/npx", "/usr/bin/npx", "npx", ""]) assert.equal(esRutaVersionada(p), false, p);
});

function homeConEntrada(command) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "leyes-mx-aviso-"));
  fs.mkdirSync(path.join(home, ".cursor"), { recursive: true });
  fs.writeFileSync(path.join(home, ".cursor", "mcp.json"),
    JSON.stringify({ mcpServers: { "leyes-mx": { command, args: ["-y", "leyes-mx", "servir"], env: {} } } }));
  return home;
}

test("doctor: falla si la ruta de npx registrada ya no existe", () => {
  const home = homeConEntrada("/no/existe/.nvm/versions/node/v1.0.0/bin/npx");
  const r = correr(["doctor"], { HOME: home, USERPROFILE: home, LEYES_MX_DATOS: REPO, LEYES_MX_HOME: path.join(home, "lm") });
  assert.match(r.stdout, /FALLO\s+cursor: la ruta de npx registrada ya no existe \(\/no\/existe\/\.nvm/);
  assert.match(r.stdout, /npx leyes-mx instalar --cliente cursor/);
  assert.notEqual(r.status, 0);
  fs.rmSync(home, { recursive: true, force: true });
});

test("doctor: avisa si la ruta existe pero incluye la versión de Node", () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "leyes-mx-nvm-"));
  const npx = path.join(base, ".nvm", "versions", "node", "v9.9.9", "bin", "npx");
  fs.mkdirSync(path.dirname(npx), { recursive: true });
  fs.writeFileSync(npx, "#!/bin/sh\n", { mode: 0o755 });
  const home = homeConEntrada(npx);
  const r = correr(["doctor"], { HOME: home, USERPROFILE: home, LEYES_MX_DATOS: REPO, LEYES_MX_HOME: path.join(home, "lm") });
  assert.match(r.stdout, /AVISO\s+cursor: la ruta de npx registrada incluye la versión de Node/);
  assert.doesNotMatch(r.stdout, /FALLO\s+cursor/);
  fs.rmSync(home, { recursive: true, force: true }); fs.rmSync(base, { recursive: true, force: true });
});
