import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { Almacen } from "../src/almacen.js";
import { Glosario, validarEstructura } from "../src/glosario.js";
import { plegar } from "../src/indice.js";
import { correr, REPO } from "./ayuda.js";

const datos = JSON.parse(fs.readFileSync(path.join(REPO, "glosario.json"), "utf8"));
const alm = new Almacen(REPO);
const g = Glosario.cargar(REPO);
const plano = (s) => plegar(s).replace(/\s+/g, " ").trim();

test("glosario.json: estructura válida, entre 25 y 60 entradas, sin raya larga ni comillas angulares", () => {
  assert.deepEqual(validarEstructura(datos), []);
  assert.ok(datos.entradas.length >= 25 && datos.entradas.length <= 60, `${datos.entradas.length} entradas`);
  const crudo = fs.readFileSync(path.join(REPO, "glosario.json"), "utf8");
  assert.ok(!crudo.includes("—") && !crudo.includes("«") && !crudo.includes("»"));
});

test("cada artículo que cita el glosario existe, está vigente y contiene su evidencia literal", () => {
  const fallos = [];
  for (const e of datos.entradas) {
    for (const a of e.articulos) {
      const f = alm.obtenerArticulo(a.ley, a.articulo, { anio: 2026 });
      if (!f) fallos.push(`${e.id}: ${a.ley} ${a.articulo} no existe`);
      else if (f.estatus !== "vigente") fallos.push(`${e.id}: ${a.ley} ${a.articulo} no está vigente`);
      else if (!plano(f.texto).includes(plano(a.evidencia))) fallos.push(`${e.id}: la evidencia no está en ${a.ley} ${a.articulo}: ${a.evidencia}`);
    }
  }
  assert.deepEqual(fallos, []);
});

test("validarEstructura rechaza entradas sin nota, sin artículos o con ids repetidos", () => {
  const base = { id: "x", disparadores: ["a"], agregar: ["b"], articulos: [{ ley: "LISR", articulo: "1", evidencia: "e" }], nota: "una nota suficientemente larga" };
  assert.deepEqual(validarEstructura({ esquema: 1, entradas: [base] }), []);
  assert.ok(validarEstructura({ esquema: 1, entradas: [{ ...base, nota: "corta" }] }).length);
  assert.ok(validarEstructura({ esquema: 1, entradas: [{ ...base, articulos: [] }] }).length);
  assert.ok(validarEstructura({ esquema: 1, entradas: [base, base] }).some((p) => /repetido/.test(p)));
  assert.ok(validarEstructura({ esquema: 2, entradas: [base] }).length);
  assert.ok(validarEstructura({ esquema: 1, entradas: [{ ...base, sustituir: ["dos palabras"] }] }).length);
});

test("expandir: coincide por frase, por derivada de 5 o más letras y con '+' en cualquier orden", () => {
  assert.ok(g.expandir("las actualizaciones").entradas.some((e) => e.id === "actualizacion"));
  assert.ok(g.expandir("no deducibles").entradas.some((e) => e.id === "gastos-no-deducibles"));
  assert.ok(!g.expandir("deducibles").entradas.some((e) => e.id === "gastos-no-deducibles"), "'deducibles' solo no es 'no deducibles'");
  assert.ok(g.expandir("declaración anual de personas físicas").entradas.some((e) => e.id === "declaracion-anual-personas-fisicas"));
  assert.ok(g.expandir("personas físicas: declaración anual").entradas.some((e) => e.id === "declaracion-anual-personas-fisicas"));
  assert.ok(!g.expandir("declaración anual").entradas.some((e) => e.id.startsWith("declaracion-anual-personas")));
  assert.deepEqual(g.expandir("hola mundo").entradas, []);
});

test("expandir: no repite lo que la consulta ya trae y las siglas se sustituyen", () => {
  const a = g.expandir("recargos de la actualización");
  assert.ok(!a.terminos.includes("recargos"));
  const s = g.expandir("PTU");
  assert.deepEqual(s.quitar, ["ptu"]);
  assert.ok(s.agregados.some((x) => /participación de los trabajadores/.test(x)));
});

test("sin glosario.json el almacén funciona: glosario() es null y buscar no falla", () => {
  const vacio = fs.mkdtempSync(path.join(os.tmpdir(), "leyes-mx-sin-glosario-"));
  try {
    fs.cpSync(path.join(REPO, "leyes", "2026", "CFF"), path.join(vacio, "leyes", "2026", "CFF"), { recursive: true });
    const a = new Almacen(vacio);
    assert.equal(a.glosario(), null);
    assert.deepEqual(Glosario.diagnosticar(vacio), { existe: false });
    fs.writeFileSync(path.join(vacio, "glosario.json"), "{ roto");
    assert.equal(new Almacen(vacio).glosario(), null, "un glosario ilegible se ignora, no tumba la búsqueda");
    assert.equal(Glosario.diagnosticar(vacio).valido, false);
  } finally { fs.rmSync(vacio, { recursive: true, force: true }); }
});

test("el glosario viaja en el paquete de datos y se actualiza con `actualizar`, sin nueva versión de npm", () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "leyes-mx-glos-"));
  try {
    const empaquetar = (dir, version, raiz) => {
      const r = spawnSync("python3", ["-I", path.join(REPO, "scripts", "empaquetar_datos.py"), "--salida", dir, "--version", version, "--raiz", raiz], { encoding: "utf8" });
      assert.equal(r.status, 0, r.stderr);
      return JSON.parse(fs.readFileSync(path.join(dir, "manifest.json"), "utf8"));
    };
    // datos mínimos: una sola ley y el glosario del repo
    const raiz1 = path.join(tmp, "r1");
    fs.cpSync(path.join(REPO, "leyes", "2026", "LISR"), path.join(raiz1, "leyes", "2026", "LISR"), { recursive: true });
    fs.copyFileSync(path.join(REPO, "glosario.json"), path.join(raiz1, "glosario.json"));
    const m1 = empaquetar(path.join(tmp, "p1"), "2026.11.02", raiz1);
    assert.equal(m1.glosario.entradas, datos.entradas.length);
    assert.equal(m1.glosario.version, datos.version);
    assert.match(m1.glosario.sha256, /^[0-9a-f]{64}$/);

    const LM = path.join(tmp, "lm");
    const env = { HOME: path.join(tmp, "home"), LEYES_MX_HOME: LM, LEYES_MX_DATOS: "", LEYES_MX_MANIFEST: path.join(tmp, "p1", "manifest.json") };
    let r = correr(["actualizar"], env);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    assert.ok(fs.existsSync(path.join(LM, "datos", "2026.11.02", "glosario.json")));
    r = correr(["estado"], env);
    assert.match(r.stdout, new RegExp(`Glosario de sinónimos: ${datos.entradas.length} entradas, versión ${datos.version}`));
    r = correr(["buscar", "zzcomodin"], env);
    assert.doesNotMatch(r.stdout, /Se amplió/);

    // versión nueva solo con el glosario cambiado: una entrada nueva
    const raiz2 = path.join(tmp, "r2");
    fs.cpSync(raiz1, raiz2, { recursive: true });
    const nuevo = JSON.parse(JSON.stringify(datos));
    nuevo.version = "2026-11-03";
    nuevo.entradas.push({ id: "comodin", disparadores: ["zzcomodin"], sustituir: ["zzcomodin"], agregar: ["tarifa"], articulos: [{ ley: "LISR", articulo: "96", evidencia: "tarifa actualizada del Anexo 8 de la RMF" }],
      nota: "Entrada de prueba para verificar que el glosario se actualiza solo." });
    fs.writeFileSync(path.join(raiz2, "glosario.json"), JSON.stringify(nuevo, null, 2));
    empaquetar(path.join(tmp, "p2"), "2026.11.03", raiz2);
    const env2 = { ...env, LEYES_MX_MANIFEST: path.join(tmp, "p2", "manifest.json") };
    r = correr(["estado"], env2);
    assert.match(r.stdout, /publicado: versión 2026-11-03/);
    r = correr(["actualizar"], env2);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    r = correr(["buscar", "zzcomodin", "--limite", "3"], env2);
    assert.match(r.stdout, /Se amplió la consulta con: tarifa \(glosario: comodin\)/);
    assert.match(r.stdout, /LISR art\. 96/);
    r = correr(["buscar", "zzcomodin", "--sin-glosario"], env2);
    assert.doesNotMatch(r.stdout, /Se amplió/);
    assert.equal(r.status, 1, "sin glosario esa palabra no existe en la ley");
    r = correr(["doctor"], env2);
    assert.match(r.stdout, /glosario de sinónimos: 41 entradas \(versión 2026-11-03\)/);
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
});
