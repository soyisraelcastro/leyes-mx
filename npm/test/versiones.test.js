// Versiones por capas (npm/src/versiones.js y almacen.js) sobre un árbol sintético en un directorio temporal. NO hay leyes/2027 real.
// El árbol lo arma el mismo código de Python que usa tests/test_versiones.py (tests/arbol_capas.py + leyes_mx.diferenciar):
// así Python y Node leen exactamente los mismos archivos y se comprueba la paridad entre los dos clientes.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { Almacen } from "../src/almacen.js";
import { Indice } from "../src/indice.js";
import * as versiones from "../src/versiones.js";
import { leerManifest } from "../src/datos.js";
import { REPO, pythonJson } from "./ayuda.js";

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "leyes-mx-capas-"));
test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
const raiz = path.join(tmp, "repo");

pythonJson(`
import json, sys
from pathlib import Path
sys.path.insert(0, ${JSON.stringify(path.join(REPO, "tests"))})
import arbol_capas as A
from leyes_mx import diferenciar
e = json.load(sys.stdin)
A.arbol_base(e["raiz"])
dx, dy = A.completo_2027(e["tmp"])
fuente = {"decreto": "DOF 2026-12-31", "nota": "prueba", "fecha_dof": "2026-12-31"}
diferenciar.escribir_capa(e["raiz"], "XLEY", 2027, dx, vigente_desde="2027-01-01", fuente=fuente)
diferenciar.escribir_capa(e["raiz"], "YLEY", 2027, dy, vigente_desde="2027-01-01")
print("{}")`, { raiz, tmp });

const alm = new Almacen(raiz);
const IDS = ["1", "2", "3", "4", "4-F", "4-G", "9"];
const leer = (a, ley, id, anio) => a.obtenerArticulo(ley, id, { anio });

test("cada artículo resuelve a la capa que corresponde", () => {
  const r = (id, anio) => path.relative(raiz, versiones.vista(raiz, "XLEY", anio).archivo(`art-${String(parseInt(id)).padStart(4, "0")}${id.includes("-") ? "-" + id.split("-")[1] : ""}.md`)).split(path.sep).join("/");
  for (const id of ["1", "2", "4-F"]) assert.match(r(id, 2027), /^leyes\/2026\/XLEY\//, `${id} sin cambios -> 2026`);
  for (const id of ["3", "4", "4-G"]) assert.match(r(id, 2027), /^leyes\/2027\/XLEY\//, `${id} cambia -> 2027`);
  assert.match(r("3", 2026), /^leyes\/2026\//);
  assert.equal(versiones.vista(raiz, "XLEY", 2026).nombres().includes("art-0004-G.md"), false);
  assert.deepEqual(versiones.cadena(raiz, "XLEY", 2027).map((c) => c.anio), [2027, 2026]);
  assert.deepEqual(versiones.capas(raiz, "xley").map((c) => c.anio), [2026, 2027]);
  assert.equal(versiones.vista(raiz, "XLEY", 2030), null);
});

test("orden de capas por vigente_desde y no por nombre de carpeta", () => {
  const copia = path.join(tmp, "orden");
  fs.cpSync(raiz, copia, { recursive: true });
  const m27 = path.join(copia, "leyes", "2027", "XLEY", "_meta.json");
  const m = JSON.parse(fs.readFileSync(m27, "utf8"));
  fs.writeFileSync(m27, JSON.stringify({ ...m, vigente_desde: "2029-01-01" }));
  fs.mkdirSync(path.join(copia, "leyes", "2028", "XLEY"), { recursive: true });
  fs.writeFileSync(path.join(copia, "leyes", "2028", "XLEY", "_meta.json"), JSON.stringify({ ...m, vigente_desde: "2028-01-01", hereda_de: 2026, articulos_modificados: [] }));
  assert.deepEqual(versiones.capas(copia, "XLEY").map((c) => c.anio), [2026, 2028, 2027]);
});

test("heredado se presenta con el año pedido; modificado, derogado y nuevo vienen de la capa", () => {
  const a1 = leer(alm, "XLEY", "1", 2027);
  assert.equal(a1.anio_vigencia, 2027);
  assert.equal(a1.ultima_reforma_dof, "2026-12-31");
  assert.equal(a1.ruta, "leyes/2026/XLEY/art-0001.md");
  assert.equal(leer(alm, "XLEY", "1", 2026).anio_vigencia, 2026);
  assert.equal(leer(alm, "XLEY", "1", 2026).ultima_reforma_dof, "2024-04-01");
  assert.match(leer(alm, "XLEY", "3", 2027).texto, /35%/);
  assert.match(leer(alm, "XLEY", "3", 2026).texto, /30%/);
  assert.equal(leer(alm, "XLEY", "4", 2027).estatus, "derogado");
  assert.equal(leer(alm, "XLEY", "4", 2026).estatus, "vigente");
  assert.equal(leer(alm, "XLEY", "4-G", 2027).articulo, "4-G");
  assert.equal(leer(alm, "XLEY", "4-G", 2026), null);
  assert.equal(leer(alm, "XLEY", "9", 2027), null);
  assert.equal(leer(alm, "ZLEY", "1", 2027), null);
});

test("Node = Python (store.obtener_articulo) sobre el árbol con capas, años 2026 y 2027", () => {
  const py = pythonJson(`
import json, sys
from leyes_mx import store
e = json.load(sys.stdin)
print(json.dumps({f"{l}|{i}|{a}": store.obtener_articulo(l, i, anio=a, raiz=e["raiz"]) for l in ("XLEY", "YLEY") for i in e["ids"] for a in (2026, 2027)}))`, { raiz, ids: IDS });
  for (const ley of ["XLEY", "YLEY"]) for (const id of IDS) for (const anio of [2026, 2027]) {
    assert.deepEqual(JSON.parse(JSON.stringify(leer(alm, ley, id, anio))), py[`${ley}|${id}|${anio}`], `${ley} ${id} ${anio}`);
  }
});

test("listar_leyes y siglas disponibles coinciden con Python", () => {
  const py = pythonJson("import json, sys\nfrom leyes_mx import store\ne = json.load(sys.stdin)\nprint(json.dumps(store.listar_leyes(raiz=e['raiz'])))", { raiz });
  assert.deepEqual(JSON.parse(JSON.stringify(alm.listarLeyes().map(({ tipo, ...r }) => r))), py);
  assert.deepEqual(alm.siglasDisponibles(2027), ["XLEY", "YLEY"]);
  assert.deepEqual(alm.anios(), [2026, 2027]);
});

test("año por defecto: la capa 2027 no aparece antes de enero", () => {
  assert.equal(alm.anioPorDefecto("XLEY", new Date(2026, 11, 31)), 2026);
  assert.equal(alm.anioPorDefecto("XLEY", new Date(2027, 0, 1)), 2027);
});

test("transitorios: la capa sin cambios en ellos hereda los de la base, con el año de la vista", () => {
  const t27 = alm.obtenerTransitorios("XLEY", 2027);
  assert.equal(t27.ruta, "leyes/2026/XLEY/transitorios.md");
  assert.equal(t27.anio_vigencia, 2027);
  assert.equal(alm.obtenerTransitorios("XLEY", 2026).anio_vigencia, 2026);
  assert.equal(alm.obtenerTransitorios("XLEY", 2030), null);
});

test("recorrer: cada ley por su vista, en el orden de archivo", () => {
  const filas = [...alm.recorrer()].map((x) => `${x.fm.ley}|${x.fm.articulo}|${x.fm.vigencia_anio}`);
  // orden de nombre de archivo (como readdir ordenado): art-0004-F.md y art-0004-G.md van antes de art-0004.md
  assert.deepEqual(filas.filter((f) => f.startsWith("XLEY") && f.endsWith("2027")), ["XLEY|1|2027", "XLEY|2|2027", "XLEY|3|2027", "XLEY|4-F|2027", "XLEY|4-G|2027", "XLEY|4|2027"]);
  assert.deepEqual(filas.filter((f) => f.startsWith("XLEY") && f.endsWith("2026")).length, 5);
});

test("búsqueda sobre la vista", () => {
  const idx = new Indice(alm);
  const q = (txt, anio, ley = "XLEY") => idx.buscar(txt, { ley, anio, limite: 10 });
  const r27 = q("tasa", 2027);
  assert.deepEqual(r27.map((x) => [x.articulo, x.anio_vigencia]), [["3", 2027]]);
  assert.match(r27[0].fragmento, /35%/);
  assert.match(q("tasa", 2026)[0].fragmento, /30%/);
  const her = q("Régimen general", 2027);
  assert.deepEqual(her.map((x) => [x.articulo, x.anio_vigencia, x.ruta]), [["1", 2027, "leyes/2026/XLEY/art-0001.md"]]);
  assert.deepEqual(q("deducciones autorizadas", 2027), []);  // el art. 4 está derogado en 2027 ("Se deroga.")
  assert.equal(q("deducciones autorizadas", 2026).length, 1);
  assert.deepEqual(q("nuevo", 2027).map((x) => x.articulo).sort(), ["3", "4-G"]);
  assert.deepEqual(q("nuevo", 2026), []);
});

function empaquetar(salida, extra = []) {
  const r = spawnSync("python3", ["-I", path.join(REPO, "scripts", "empaquetar_datos.py"), "--raiz", raiz, "--salida", salida, "--version", "2027.01.05", "--fecha", "2027-01-05", ...extra],
    { encoding: "utf8", env: { ...process.env, PYTHONPATH: REPO } });
  assert.equal(r.status, 0, r.stderr);
  const dir = `${salida}-x`;
  fs.mkdirSync(dir, { recursive: true });
  const t = spawnSync("tar", ["-xzf", path.join(salida, "leyes-mx-datos.tar.gz"), "-C", dir]);
  assert.equal(t.status, 0);
  return { manifest: JSON.parse(fs.readFileSync(path.join(salida, "manifest.json"), "utf8")), dir };
}

const sinRuta = ({ ruta, ...r }) => r;

test("paquete materializado: año completo en leyes/2027, esquema 1, y se lee igual que las capas", async () => {
  const { manifest, dir } = empaquetar(path.join(tmp, "mat"));
  assert.equal(manifest.materializado, true);
  assert.equal(manifest.esquema, 1);
  assert.equal(manifest.capas, 2);
  assert.equal(fs.readdirSync(path.join(dir, "leyes", "2027", "XLEY")).filter((n) => /^art-/.test(n)).length, 6);
  const m = new Almacen(dir);
  for (const id of IDS) assert.deepEqual(m.obtenerArticulo("XLEY", id, { anio: 2027 }) && sinRuta(m.obtenerArticulo("XLEY", id, { anio: 2027 })),
    leer(alm, "XLEY", id, 2027) && sinRuta(leer(alm, "XLEY", id, 2027)), id);
  assert.equal(m.obtenerArticulo("XLEY", "1", { anio: 2027 }).ruta, "leyes/2027/XLEY/art-0001.md");
  assert.deepEqual(new Indice(m).buscar("nuevo", { ley: "XLEY", anio: 2027 }).map((x) => x.articulo).sort(), ["3", "4-G"]);
  assert.match(m.obtenerTransitorios("XLEY", 2027).texto, /Entra en vigor/);
  assert.equal(m.obtenerTransitorios("XLEY", 2027).anio_vigencia, 2027);
  assert.equal((await leerManifest(path.join(tmp, "mat", "manifest.json"))).materializado, true);
});

test("paquete sin materializar: lleva las capas, sube a esquema 2 y este cliente lo lee igual", async () => {
  const { manifest, dir } = empaquetar(path.join(tmp, "capas"), ["--sin-materializar"]);
  assert.equal(manifest.materializado, false);
  assert.equal(manifest.esquema, 2);
  assert.equal(fs.readdirSync(path.join(dir, "leyes", "2027", "XLEY")).filter((n) => /^art-/.test(n)).length, 3);
  const m = new Almacen(dir);
  for (const id of IDS) assert.deepEqual(JSON.parse(JSON.stringify(leer(m, "XLEY", id, 2027))), JSON.parse(JSON.stringify(leer(alm, "XLEY", id, 2027))), id);
  assert.equal((await leerManifest(path.join(tmp, "capas", "manifest.json"))).esquema, 2);
  fs.writeFileSync(path.join(tmp, "futuro.json"), JSON.stringify({ ...manifest, esquema: 3 }));
  await assert.rejects(leerManifest(path.join(tmp, "futuro.json")), /esquema 3/);
});
