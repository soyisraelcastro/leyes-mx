import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";

export const AQUI = path.dirname(fileURLToPath(import.meta.url));
export const NPM = path.resolve(AQUI, "..");
export const REPO = path.resolve(NPM, "..");
export const BIN = path.join(NPM, "bin", "leyes-mx.js");

export function pythonJson(codigo, entrada) {
  const r = spawnSync("python3", ["-I", "-c", `import sys; sys.path.insert(0, ${JSON.stringify(REPO)})\n` + codigo], { input: JSON.stringify(entrada), cwd: REPO, encoding: "utf8", maxBuffer: 1 << 28,
    env: { ...process.env, PYTHONPATH: REPO } });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}

export function correr(args, env = {}, entrada = null) {
  return spawnSync(process.execPath, [BIN, ...args], { encoding: "utf8", input: entrada ?? undefined, env: { ...process.env, ...env }, maxBuffer: 1 << 28 });
}

export function correrAsync(cmd, args, opts = {}) {
  return new Promise((res) => {
    const p = spawn(cmd, args, opts);
    let o = "", e = "";
    p.stdout.on("data", (d) => (o += d));
    p.stderr.on("data", (d) => (e += d));
    p.on("close", (code) => res({ code, o, e }));
  });
}
