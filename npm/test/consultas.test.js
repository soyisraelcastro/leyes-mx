// Preguntas reales -> artículos esperados dentro del top N de `buscar`, con el glosario del repo.
// Los casos están en consultas.json (con la frase de la ley que respalda cada uno). Un caso nuevo que falle es un hallazgo:
// o la entrada del glosario no alcanza (agregarla o ajustarla en glosario.json) o el caso no está bien verificado.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { Almacen } from "../src/almacen.js";
import { Indice } from "../src/indice.js";
import { REPO, AQUI } from "./ayuda.js";

const casos = JSON.parse(fs.readFileSync(path.join(AQUI, "consultas.json"), "utf8")).casos;
const alm = new Almacen(REPO);
const indice = new Indice(alm);
const glosario = alm.glosario();
const buscar = (q, g) => indice.buscarConDetalle(q, { limite: 50, anioDefecto: 2026, glosario: g });

test("el glosario del repo carga", () => assert.ok(glosario && glosario.entradas.length >= 25));

test("cada caso apunta a artículos que existen y están vigentes", () => {
  for (const c of casos) for (const e of c.esperados) {
    const f = alm.obtenerArticulo(e.ley, e.articulo, { anio: 2026 });
    assert.ok(f && f.estatus === "vigente", `${c.pregunta}: ${e.ley} ${e.articulo} no existe o no está vigente`);
    assert.ok(c.por_que && c.por_que.length > 20, `${c.pregunta}: falta por_que`);
  }
});

for (const c of casos) {
  test(`"${c.pregunta}"`, () => {
    const { resultados } = buscar(c.pregunta, glosario);
    for (const e of c.esperados) {
      const i = resultados.findIndex((x) => x.ley === e.ley && x.articulo === e.articulo);
      assert.ok(i >= 0 && i + 1 <= e.top, `${e.ley} art. ${e.articulo} debía estar en el top ${e.top} y salió en la posición ${i < 0 ? "(fuera del top 50)" : i + 1}. ` +
        `Primeros: ${resultados.slice(0, 6).map((x) => `${x.ley} ${x.articulo}`).join(", ")}`);
    }
  });
}

test("el glosario mejora la búsqueda: sin él, la mayoría de los casos no pasa", () => {
  const dentro = (g) => casos.flatMap((c) => c.esperados.map((e) => {
    const i = buscar(c.pregunta, g).resultados.findIndex((x) => x.ley === e.ley && x.articulo === e.articulo);
    return i >= 0 && i + 1 <= e.top;
  })).filter(Boolean).length;
  const total = casos.reduce((n, c) => n + c.esperados.length, 0);
  const con = dentro(glosario), sin = dentro(null);
  assert.equal(con, total);
  assert.ok(sin < total * 0.6, `sin glosario pasan ${sin} de ${total}: el glosario ya no aporta lo suficiente, o los casos son demasiado fáciles`);
});

test("el caso del hallazgo: la consulta reformulada con términos legales sigue funcionando sin glosario", () => {
  const { resultados } = buscar("accesorios de las contribuciones no deducibles recargos", null);
  assert.ok(resultados.slice(0, 3).some((x) => x.ley === "LISR" && x.articulo === "28"));
});

test("la ampliación se declara: qué se agregó, qué se sustituyó y qué artículos relaciona", () => {
  const { ampliacion } = buscar("fundamento para no deducir actualizaciones", glosario);
  assert.ok(ampliacion.agregados.includes("accesorios") && ampliacion.agregados.includes("recargos"));
  assert.deepEqual(ampliacion.entradas.map((e) => e.id).sort(), ["actualizacion", "gastos-no-deducibles"]);
  const sig = buscar("IVA de PTU", glosario).ampliacion;
  assert.deepEqual(sig.quitar.sort(), ["iva", "ptu"]);
});

test("una consulta que no toca el glosario no se amplía ni cambia", () => {
  const a = buscar("tarifa del artículo 113-E retención", null).resultados;
  const b = buscar("tarifa del artículo 113-E retención", glosario);
  assert.equal(b.ampliacion, null);
  assert.deepEqual(b.resultados, a);
});

test("los resultados que suben por el glosario van marcados", () => {
  const { resultados } = buscar("fundamento para no deducir actualizaciones", glosario);
  assert.ok(resultados.filter((r) => r.relacionado_por_glosario).length >= 3);
  assert.ok(buscar("fundamento para no deducir actualizaciones", null).resultados.every((r) => !r.relacionado_por_glosario));
});

test("el glosario respeta los filtros: con ley=CFF no sale ningún artículo de la LISR", () => {
  const r = indice.buscarConDetalle("fundamento para no deducir actualizaciones", { limite: 20, anioDefecto: 2026, ley: "CFF", glosario }).resultados;
  assert.ok(r.length && r.every((x) => x.ley === "CFF"));
  assert.ok(r.slice(0, 5).some((x) => x.articulo === "17-A"));
});
