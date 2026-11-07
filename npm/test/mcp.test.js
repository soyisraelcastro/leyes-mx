import test from "node:test";
import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { BIN, REPO } from "./ayuda.js";

let c;
const txt = (r) => r.content.map((x) => x.text).join("\n");

test.before(async () => {
  const t = new StdioClientTransport({ command: process.execPath, args: [BIN, "servir"], env: { ...process.env, LEYES_MX_DATOS: REPO }, stderr: "ignore" });
  c = new Client({ name: "prueba", version: "0" });
  await c.connect(t);
});
test.after(async () => { await c.close(); });

test("initialize y tools/list", async () => {
  const info = c.getServerVersion();
  assert.equal(info.name, "leyes-mx");
  assert.match(c.getInstructions(), /no verificado/);
  const { tools } = await c.listTools();
  assert.deepEqual(tools.map((t) => t.name).sort(), ["buscar", "estado_reforma", "listar_leyes", "obtener_articulo", "obtener_regla", "obtener_tarifa", "obtener_transitorios", "temas"]);
  for (const t of tools) assert.equal(t.annotations.readOnlyHint, true);
});

test("las instrucciones y descripciones guían al modelo con términos de contador: cuándo consultar, reformular, artículo completo, cita, tarifas, proyectos y permiso para internet", async () => {
  const i = c.getInstructions();
  for (const re of [/antes de responder cualquier consulta fiscal o laboral de México/, /ISR, IVA, deducciones, retenciones, CFDI, aguinaldo/, /qué dice el artículo/, /fundamento legal/, /palabras de la ley/,
    /obtener_articulo/, /fracción/, /vigencia/, /última reforma/, /obtener_tarifa/, /NO es ley vigente/, /no verificado/, /PREGUNTA al usuario si desea que lo busques en internet/, /sin su permiso/, /fuentes oficiales \(DOF, SAT, Cámara de Diputados\)/]) assert.match(i, re);
  const { tools } = await c.listTools();
  const d = Object.fromEntries(tools.map((t) => [t.name, t.description]));
  assert.match(d.buscar, /ISR, IVA, deducciones/);
  assert.match(d.buscar, /ANTES de responder cualquier consulta fiscal o laboral de México/);
  assert.match(d.buscar, /NO cites a partir de ellos/);
  assert.match(d.buscar, /pregunta al usuario si desea buscar en internet/);
  assert.match(d.obtener_articulo, /qué dice el artículo 28 de la LISR/);
  assert.match(d.obtener_articulo, /fuente para CITAR/);
  assert.match(d.obtener_tarifa, /SIEMPRE/);
  assert.match(d.obtener_tarifa, /tarifa mensual de retención de sueldos/);
  assert.ok(!/[\u2014\u00ab\u00bb]/.test(i + Object.values(d).join("")));
});

test("lo que no está en la base: el RESULTADO de cada herramienta manda preguntar al usuario antes de buscar en internet", async () => {
  const pregunta = /No encontré .* en la base local de leyes-mx\. .*Pregunta al usuario si desea que lo busques en internet; no busques sin su permiso\. .*fuentes oficiales \(DOF, SAT, Cámara de Diputados\).*no proviene de la base verificada/s;
  const llamadas = [
    ["obtener_articulo", { ley: "LISR", articulo: "9999" }],
    ["obtener_articulo", { ley: "LIEPS", articulo: "1" }],
    ["buscar", { consulta: "zzzqqqxxx wwwvvvyyy" }],
    ["obtener_tarifa", { tarifa: "Z-9" }],
    ["obtener_transitorios", { ley: "XXX" }],
  ];
  for (const [name, args] of llamadas) {
    const t = txt(await c.callTool({ name, arguments: args }));
    assert.match(t, /^NO VERIFICADO/, name);
    assert.match(t, pregunta, name);
  }
});

test("obtener_articulo: cita, variantes y advertencia de la LFT", async () => {
  const r = await c.callTool({ name: "obtener_articulo", arguments: { ley: "lisr", articulo: "113 e" } });
  const t = txt(r);
  assert.match(t, /Cita: LISR art\. 113-E, vigencia 2026, última reforma DOF 2024-04-01/);
  assert.match(t, /Estatus: vigente/);
  const l = txt(await c.callTool({ name: "obtener_articulo", arguments: { ley: "LFT", articulo: "59" } }));
  assert.match(l, /ADVERTENCIA: Reforma de jornada laboral/);
});

test("artículo que no existe: lo dice y no inventa", async () => {
  const r = await c.callTool({ name: "obtener_articulo", arguments: { ley: "LISR", articulo: "9999" } });
  assert.match(txt(r), /NO VERIFICADO/);
  assert.equal(r.structuredContent.encontrado, false);
  const r2 = await c.callTool({ name: "obtener_articulo", arguments: { ley: "LIEPS", articulo: "1" } });
  assert.match(txt(r2), /NO VERIFICADO[\s\S]*no existe en la base/);
  const r3 = await c.callTool({ name: "obtener_articulo", arguments: { ley: "LISR", articulo: "xyz" } });
  assert.equal(r3.isError, true);
});

test("artículo derogado", async () => {
  const { Almacen } = await import("../src/almacen.js");
  const a = new Almacen(REPO);
  const der = [...a.recorrer()].find((x) => x.fm.estatus === "derogado" && x.fm.ley === "LISR");
  assert.ok(der);
  const r = await c.callTool({ name: "obtener_articulo", arguments: { ley: "LISR", articulo: der.fm.articulo } });
  assert.match(txt(r), /Estatus: derogado/);
  assert.match(txt(r), /derogado; no aplica/);
});

test("LFT 513 enorme: paginado, sin truncar en silencio", async () => {
  const p1 = await c.callTool({ name: "obtener_articulo", arguments: { ley: "LFT", articulo: "513" } });
  const t1 = txt(p1);
  assert.match(t1, /TEXTO EXTENSO/);
  const total = p1.structuredContent.paginas;
  assert.ok(total > 1);
  assert.ok(t1.length < 46000);
  const { Almacen } = await import("../src/almacen.js");
  const esperado = new Almacen(REPO).obtenerArticulo("LFT", "513").texto;
  for (let p = 1; p <= total; p++) {
    const r = await c.callTool({ name: "obtener_articulo", arguments: { ley: "LFT", articulo: "513", pagina: p } });
    assert.ok(!r.isError);
    assert.ok(txt(r).length < 46000);
  }
  assert.ok(esperado.length > 300000, "el 513 debe ser enorme");
  const fuera = await c.callTool({ name: "obtener_articulo", arguments: { ley: "LFT", articulo: "513", pagina: total + 1 } });
  assert.equal(fuera.isError, true);
});

test("las páginas de un texto extenso reconstruyen el texto completo", async () => {
  const { paginar } = await import("../src/respuestas.js");
  const { Almacen } = await import("../src/almacen.js");
  const esperado = new Almacen(REPO).obtenerArticulo("LFT", "513").texto;
  assert.equal(paginar(esperado).join("\n\n"), esperado);
});

test("buscar: vigente por defecto, proyectos solo si se piden y marcados", async () => {
  const r = await c.callTool({ name: "buscar", arguments: { consulta: "recargos deducibles", ley: "LISR" } });
  assert.match(txt(r), /solo ley vigente/);
  assert.ok(r.structuredContent.resultados.every((x) => ["vigente", "derogado"].includes(x.estatus)));
  const p = await c.callTool({ name: "buscar", arguments: { consulta: "78-E armadoras", incluir_proyectos: true, limite: 20 } });
  const res = p.structuredContent.resultados;
  assert.ok(res.some((x) => x.estatus === "proyecto"));
  assert.match(txt(p), /PROYECTO, NO ES LEY VIGENTE/);
  const sin = await c.callTool({ name: "buscar", arguments: { consulta: "zzzqqqxxx wwwvvvyyy" } });
  assert.match(txt(sin), /NO VERIFICADO/);
});

test("buscar con glosario: declara qué se agregó; glosario=false busca solo con las palabras dadas", async () => {
  const q = "fundamento para no deducir actualizaciones";
  const con = await c.callTool({ name: "buscar", arguments: { consulta: q, limite: 10 } });
  assert.match(txt(con), /Se amplió la consulta con: accesorios; recargos/);
  assert.match(txt(con), /\[glosario\]/);
  assert.deepEqual(con.structuredContent.ampliacion.entradas.map((e) => e.id).sort(), ["actualizacion", "gastos-no-deducibles"]);
  const top = con.structuredContent.resultados.slice(0, 3).map((r) => `${r.ley} ${r.articulo}`);
  assert.ok(top.includes("LISR 28"), top.join(", "));
  const sin = await c.callTool({ name: "buscar", arguments: { consulta: q, glosario: false } });
  assert.doesNotMatch(txt(sin), /Se amplió/);
  assert.equal(sin.structuredContent.ampliacion, null);
});

test("listar_leyes, estado_reforma y obtener_transitorios", async () => {
  const l = txt(await c.callTool({ name: "listar_leyes", arguments: {} }));
  for (const s of ["LISR", "LIVA", "CFF", "LFT", "LSS", "LFDC", "LCF", "LOPDC", "RLISR", "RLIVA", "RCFF", "RACERF"]) assert.match(l, new RegExp(s));
  const e = txt(await c.callTool({ name: "estado_reforma", arguments: {} }));
  assert.match(e, /es_ley_vigente: false/);
  assert.match(e, /NO es ley vigente/);
  const t = await c.callTool({ name: "obtener_transitorios", arguments: { ley: "LFT" } });
  assert.match(txt(t), /Transitorios de Ley Federal del Trabajo/);
  assert.match(txt(t), /ADVERTENCIA|TRANSITORIOS/);
  const n = txt(await c.callTool({ name: "obtener_transitorios", arguments: { ley: "XXX" } }));
  assert.match(n, /NO VERIFICADO/);
});

test("un proyecto nunca sale como vigente en obtener_articulo por defecto", async () => {
  const r = await c.callTool({ name: "obtener_articulo", arguments: { ley: "LISR", articulo: "78-E", anio: 2027 } });
  assert.match(txt(r), /NO VERIFICADO/);
});

test("obtener_tarifa: la mensual 2026 sale del Anexo 8 con las cifras del PDF", async () => {
  const r = await c.callTool({ name: "obtener_tarifa", arguments: { tarifa: "B-V" } });
  const t = txt(r);
  assert.match(t, /Anexo 8 de la RMF 2026, apartado B\.V \| vigencia 2026 \| publicado en el DOF 2025-12-28/);
  assert.match(t, /\| 0\.01 \| 844\.59 \| 0\.00 \| 1\.92 \|/);
  assert.match(t, /\| 844\.60 \| 7,168\.51 \| 16\.22 \| 6\.40 \|/);
  assert.match(t, /\| 425,642\.00 \| En adelante \| 133,488\.54 \| 35\.00 \|/);
  const anual = txt(await c.callTool({ name: "obtener_tarifa", arguments: { tarifa: "c.ii" } }));
  assert.match(anual, /\| 10,135\.12 \| 86,022\.11 \| 194\.59 \| 6\.40 \|/);
});

test("obtener_tarifa: lista, apartado ambiguo y tarifa inexistente", async () => {
  const lista = await c.callTool({ name: "obtener_tarifa", arguments: {} });
  assert.equal(lista.structuredContent.tarifas.length, 31);
  const amb = await c.callTool({ name: "obtener_tarifa", arguments: { tarifa: "B-VI" } });
  assert.match(txt(amb), /varias tarifas; usa el id exacto/);
  const no = await c.callTool({ name: "obtener_tarifa", arguments: { tarifa: "Z-9" } });
  assert.match(txt(no), /NO VERIFICADO/);
  assert.equal(no.structuredContent.encontrado, false);
});

test("los artículos 96 y 152 de la LISR remiten al Anexo 8", async () => {
  for (const art of ["96", "152"]) {
    const t = txt(await c.callTool({ name: "obtener_articulo", arguments: { ley: "LISR", articulo: art } }));
    assert.match(t, /Anexo 8 de la RMF 2026/);
  }
});

test("obtener_regla: texto, fundamento, remisiones y la advertencia de que no trae las modificaciones", async () => {
  const r = await c.callTool({ name: "obtener_regla", arguments: { regla: "2.7.1.1" } });
  const t = txt(r);
  assert.match(t, /regla 2\.7\.1\.1/);
  assert.match(t, /Almacenamiento de CFDI/);
  assert.match(t, /Fundamento \(tal como lo imprime la RMF\): CFF 28, 30/);
  assert.match(t, /NO tiene aplicadas las resoluciones de modificación/);
  assert.equal(r.structuredContent.encontrado, true);
  assert.deepEqual(r.structuredContent.referencias_leyes, { CFF: ["28", "30"] });
  assert.match(r.structuredContent.texto, /Para los efectos de los artículos 28/); // el texto viaja también en structuredContent (Claude Desktop lee solo eso)
  // también con la forma "regla 2.7.1.1." y con cinco niveles
  assert.equal((await c.callTool({ name: "obtener_regla", arguments: { regla: "regla 2.7.1.1." } })).structuredContent.regla, "2.7.1.1");
  assert.equal((await c.callTool({ name: "obtener_regla", arguments: { regla: "2.7.7.1.1" } })).structuredContent.encontrado, true);
});

test("obtener_regla: inexistente = no verificado; mal formada = error", async () => {
  const n = await c.callTool({ name: "obtener_regla", arguments: { regla: "99.9.9" } });
  assert.match(txt(n), /NO VERIFICADO/);
  assert.equal(n.structuredContent.encontrado, false);
  const e = await c.callTool({ name: "obtener_regla", arguments: { regla: "xyz" } });
  assert.equal(e.isError, true);
});

test("temas: lista, tema por id o nombre, filtro por ley y mínimo, y el que no existe", async () => {
  const l = await c.callTool({ name: "temas", arguments: {} });
  assert.match(txt(l), /hidrocarburos \| Hidrocarburos y combustibles/);
  assert.ok(l.structuredContent.temas.length >= 50);
  const h = await c.callTool({ name: "temas", arguments: { tema: "hidrocarburos", limite: 5 } });
  assert.match(txt(h), /Tema: Hidrocarburos y combustibles/);
  assert.equal(h.structuredContent.documentos.length, 5);
  assert.ok(h.structuredContent.total > 50);
  assert.match(txt(h), /RMF regla 2\.6\./);
  // por nombre, sin acentos, y acotado a una ley
  const s = await c.callTool({ name: "temas", arguments: { tema: "Subcontratacion", ley: "LFT" } });
  assert.equal(s.structuredContent.tema, "subcontratacion");
  assert.ok(s.structuredContent.documentos.every((x) => x.ley === "LFT"));
  // el puntaje mínimo deja solo lo más central
  const m = await c.callTool({ name: "temas", arguments: { tema: "cfdi", minimo: 20, limite: 100 } });
  assert.ok(m.structuredContent.documentos.every((x) => x.puntaje >= 20));
  const x = await c.callTool({ name: "temas", arguments: { tema: "zzz inexistente" } });
  assert.match(txt(x), /NO VERIFICADO/);
});

test("obtener_regla y temas llevan el texto completo en structuredContent.texto, igual que en content", async () => {
  for (const [name, args] of [["obtener_regla", { regla: "2.7.1.1" }], ["temas", { tema: "ptu" }], ["temas", {}]]) {
    const r = await c.callTool({ name, arguments: args });
    assert.equal(r.structuredContent.texto, r.content[0].text);
    assert.ok(r.structuredContent.texto.length > 100);
  }
});
