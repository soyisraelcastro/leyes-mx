import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { Almacen } from "../src/almacen.js";
import { idDesdeArchivo } from "../src/ids.js";
import { correrAsync, pythonJson, REPO } from "./ayuda.js";

const alm = new Almacen(REPO);
const todos = [];
for (const ley of fs.readdirSync(path.join(REPO, "leyes", "2026")).sort()) {
  for (const f of fs.readdirSync(path.join(REPO, "leyes", "2026", ley)).sort()) {
    const id = idDesdeArchivo(f);
    if (id) todos.push({ ley, id, ruta: path.join(REPO, "leyes", "2026", ley, f) });
  }
}

test("hay 3213 artículos en leyes/2026", () => assert.equal(todos.length, 3213));

test("obtener de Node = texto del archivo, para todos los artículos", () => {
  for (const { ley, id, ruta } of todos) {
    const f = alm.obtenerArticulo(ley, id, { anio: 2026 });
    assert.ok(f, `${ley} ${id} no encontrado`);
    const raw = fs.readFileSync(ruta, "utf8");
    const [, cabecera, cuerpo] = /^---\n([\s\S]*?)\n---\n([\s\S]*)$/.exec(raw);
    assert.equal(f.ley, /^ley: "(.*)"$/m.exec(cabecera)[1]);
    assert.equal(f.articulo, /^articulo: "(.*)"$/m.exec(cabecera)[1]);
    assert.equal(f.ultima_reforma_dof, /^ultima_reforma_dof: "(.*)"$/m.exec(cabecera)[1]);
    assert.equal(f.estatus, /^estatus: "(.*)"$/m.exec(cabecera)[1]);
    // el texto devuelto es el cuerpo del archivo, sin la sección de notas, sin espacios en los extremos
    assert.equal(f.texto, cuerpo.split("\n## Notas de reforma")[0].trim(), `${ley} ${id}`);
    assert.ok(cuerpo.includes(f.texto));
  }
});

test("obtener de Node = salida de python3 scripts/buscar.py obtener --json, para todos los artículos", async () => {
  const cola = [...todos];
  const fallos = [];
  async function obrero() {
    while (cola.length) {
      const { ley, id } = cola.pop();
      const r = await correrAsync("python3", ["-I", path.join(REPO, "scripts", "buscar.py"), "obtener", ley, id, "--anio", "2026", "--json"], { cwd: REPO });
      if (r.code !== 0) { fallos.push(`${ley} ${id}: python salió con ${r.code} ${r.e.slice(0, 100)}`); continue; }
      const py = JSON.parse(r.o);
      const nodo = alm.obtenerArticulo(ley, id, { anio: 2026 });
      try { assert.deepEqual(JSON.parse(JSON.stringify(nodo)), py); } catch (e) { fallos.push(`${ley} ${id}: ${e.message.split("\n").slice(0, 6).join(" | ")}`); }
    }
  }
  await Promise.all(Array.from({ length: 8 }, obrero));
  assert.equal(fallos.length, 0, fallos.slice(0, 5).join("\n"));
});

test("transitorios y artículos inexistentes", () => {
  assert.equal(alm.obtenerArticulo("LISR", "9999", { anio: 2026 }), null);
  assert.equal(alm.obtenerArticulo("XXXX", "1"), null);
  assert.ok(alm.obtenerTransitorios("LFT", 2026).texto.includes("TRANSITORIOS"));
  assert.throws(() => alm.obtenerArticulo("LISR", "abc"));
});

test("listar_leyes coincide con Python", () => {
  const py = pythonJson("import json\nfrom leyes_mx import store\nprint(json.dumps(store.listar_leyes()))", null);
  assert.deepEqual(JSON.parse(JSON.stringify(alm.listarLeyes().map(({ tipo, ...r }) => r))), py);
});

test("paridad de tarifas del Anexo 8 contra Python (31 tarifas)", () => {
  const lista = alm.listarTarifas(2026);
  assert.equal(lista.length, 31);
  const py = pythonJson(
    "import json, sys\nfrom leyes_mx import anexos\nids = json.load(sys.stdin)\nprint(json.dumps({i: anexos.obtener_anexo(8, i, 2026) for i in ids}))",
    lista.map((x) => x.id));
  for (const x of lista) {
    const js = alm.obtenerTarifa(x.id, 2026);
    const p = py[x.id];
    for (const k of ["documento", "apartado", "id", "titulo", "vigencia_anio", "publicado_dof", "fecha_firma", "fuente_url", "sha256_fuente", "estatus", "ruta"]) {
      assert.deepEqual(js[k], p[k], `${x.id}.${k}`);
    }
    assert.equal(js.texto, p.texto, `${x.id}.texto`);
  }
});
