// Algunos clientes MCP (comprobado en Claude Code) le muestran al modelo solo structuredContent y descartan el
// texto de content. Por eso el texto completo debe viajar TAMBIÉN en structuredContent.texto, idéntico al de content.
import test from "node:test";
import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { BIN, REPO } from "./ayuda.js";

let c;
const llamar = (name, args) => c.callTool({ name, arguments: args });

test.before(async () => {
  const t = new StdioClientTransport({ command: process.execPath, args: [BIN, "servir"], env: { ...process.env, LEYES_MX_DATOS: REPO }, stderr: "ignore" });
  c = new Client({ name: "prueba", version: "0" });
  await c.connect(t);
});
test.after(async () => { await c.close(); });

/** structuredContent.texto es exactamente el texto de content[0]. Devuelve ese texto. */
function igual(r, que) {
  assert.ok(!r.isError, que);
  assert.equal(typeof r.structuredContent.texto, "string", `${que}: falta structuredContent.texto`);
  assert.equal(r.structuredContent.texto, r.content[0].text, `${que}: texto distinto al de content`);
  return r.content[0].text;
}

test("obtener_articulo: structuredContent.texto trae el artículo y content sigue igual", async () => {
  const r = await llamar("obtener_articulo", { ley: "LISR", articulo: "9" });
  const t = igual(r, "LISR 9");
  assert.match(r.structuredContent.texto, /la tasa del 30%/);
  assert.match(r.content[0].text, /la tasa del 30%/);
  assert.equal(r.structuredContent.encontrado, true);
  assert.equal(r.structuredContent.ley, "LISR");
  assert.equal(r.structuredContent.articulo, "9");
  assert.ok(t.length > 200);
});

test("paginación: cada página trae su propio texto en structuredContent (transitorios de la LFT, de varias páginas)", async () => {
  const p1 = await llamar("obtener_transitorios", { ley: "LFT" });
  const p2 = await llamar("obtener_transitorios", { ley: "LFT", pagina: 2 });
  assert.ok(p1.structuredContent.paginas > 1, "los transitorios de la LFT deben ser de varias páginas");
  igual(p1, "p1");
  igual(p2, "p2");
  assert.equal(p2.structuredContent.pagina, 2);
  assert.notEqual(p1.structuredContent.texto, p2.structuredContent.texto);
  assert.match(p2.structuredContent.texto, /página 2 de/);
});

test("obtener_articulo: no encontrado lleva el NO VERIFICADO y qué hacer en structuredContent.texto", async () => {
  const r = await llamar("obtener_articulo", { ley: "LISR", articulo: "9999" });
  assert.equal(r.structuredContent.encontrado, false);
  igual(r, "no encontrado");
  assert.match(r.structuredContent.texto, /^NO VERIFICADO/);
  assert.match(r.structuredContent.texto, /Pregunta al usuario/);
});

test("obtener_tarifa: structuredContent.texto trae la tabla; la lista y la tarifa inexistente también", async () => {
  const r = await llamar("obtener_tarifa", { tarifa: "B-V" });
  const t = igual(r, "B-V");
  assert.equal(r.structuredContent.encontrado, true);
  assert.match(t, /Tarifa mensual 2026/);
  assert.match(r.structuredContent.texto, /\d/);
  assert.ok(r.structuredContent.texto.split("\n").length > 10, "la tabla debe traer sus renglones");

  const lista = await llamar("obtener_tarifa", {});
  igual(lista, "lista de tarifas");
  assert.match(lista.structuredContent.texto, /B-V/);
  assert.ok(Array.isArray(lista.structuredContent.tarifas));

  const no = await llamar("obtener_tarifa", { tarifa: "Z-9" });
  igual(no, "tarifa inexistente");
  assert.match(no.structuredContent.texto, /^NO VERIFICADO/);
});

test("obtener_transitorios: structuredContent.texto trae los transitorios; inexistentes también", async () => {
  const r = await llamar("obtener_transitorios", { ley: "LFT" });
  const t = igual(r, "transitorios LFT");
  assert.equal(r.structuredContent.encontrado, true);
  assert.match(t, /Transitorios de/);
  assert.match(t, /Vigencia:/);
  const no = await llamar("obtener_transitorios", { ley: "XXX" });
  igual(no, "transitorios inexistentes");
  assert.match(no.structuredContent.texto, /^NO VERIFICADO/);
});

test("buscar: structuredContent.texto trae el mismo texto (notas del glosario incluidas) y conserva resultados", async () => {
  const r = await llamar("buscar", { consulta: "recargos deducibles" });
  const t = igual(r, "buscar");
  assert.ok(r.structuredContent.resultados.length > 0);
  assert.match(t, /Son fragmentos/);
  const vacio = await llamar("buscar", { consulta: "zzzqqqxxx wwwvvvyyy" });
  igual(vacio, "buscar sin resultados");
  assert.match(vacio.structuredContent.texto, /^NO VERIFICADO/);
});

test("listar_leyes y estado_reforma: structuredContent.texto trae el texto con sus avisos y se conservan los campos", async () => {
  const l = await llamar("listar_leyes", {});
  igual(l, "listar_leyes");
  assert.match(l.structuredContent.texto, /LISR/);
  assert.ok(Array.isArray(l.structuredContent.leyes));
  const e = await llamar("estado_reforma", {});
  igual(e, "estado_reforma");
  assert.ok("reforma" in e.structuredContent && Array.isArray(e.structuredContent.leyes));
});

test("sin raya larga ni comillas angulares en el texto de structuredContent", async () => {
  const r = await llamar("obtener_tarifa", {});
  assert.equal(typeof r.structuredContent.texto, "string");
  assert.ok(!/[—«»]/.test(r.structuredContent.texto));
});
