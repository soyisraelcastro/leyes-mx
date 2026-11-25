// Preguntas reales -> regla de la RMF dentro del top N de la lista de reglas de `buscar` (ver consultas-rmf.json).
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { Almacen } from "../src/almacen.js";
import { Indice, IndiceReglas, buscarTodo, plegar } from "../src/indice.js";
import { REPO, AQUI } from "./ayuda.js";

const { casos } = JSON.parse(fs.readFileSync(path.join(AQUI, "consultas-rmf.json"), "utf8"));
const alm = new Almacen(REPO);
const leyes = new Indice(alm), reglas = new IndiceReglas(alm);
const glosario = alm.glosario();
const buscar = (q, op = {}) => buscarTodo(alm, { leyes: () => leyes, reglas: () => reglas }, q, { glosario, ...op });

test("se indexan todas las reglas de la base", () => {
  const archivos = alm.aniosReglas().flatMap((a) => alm.resoluciones(a).flatMap((r) => fs.readdirSync(path.join(r.dir, "reglas")).filter((n) => /^regla-.*\.md$/.test(n))));
  assert.equal(reglas.docs.length, archivos.length);
  assert.ok(archivos.length > 1000);
});

for (const c of casos) {
  test(`RMF: "${c.pregunta}"`, () => {
    const f = alm.obtenerRegla(c.regla);
    assert.ok(f && plegar(`${f.titulo} ${f.texto}`).includes(plegar(c.evidencia)), `la regla ${c.regla} no contiene: ${c.evidencia}`);
    const r = buscar(c.pregunta).reglas;
    const i = r.findIndex((x) => x.regla === c.regla);
    assert.ok(i >= 0 && i < c.top, `${c.regla} debía estar en el top ${c.top}; salieron ${r.map((x) => x.regla).join(", ")}`);
  });
}

test("sin glosario, la pregunta reportada también encuentra la regla", () => {
  const r = buscar("cual es la regla que releva a las personas fisicas y morales RESICO de presentar las Diot", { glosario: null }).reglas;
  assert.ok(r.slice(0, 3).some((x) => x.regla === "3.13.17"), r.map((x) => x.regla).join(", "));
});

test("agregar las reglas no mueve el ranking de las leyes", () => {
  for (const q of ["recargos deducibles", "DIOT", "aguinaldo exento de ISR"]) {
    assert.deepEqual(buscar(q).resultados, leyes.buscarConDetalle(q, { limite: 10, anioDefecto: 2026, glosario }).resultados);
  }
});
