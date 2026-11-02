import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { normalizarId, nombreArchivo, idDesdeArchivo, compararIds } from "../src/ids.js";
import { pythonJson, REPO } from "./ayuda.js";

const VARIANTES = ["113 E", "113-e", "113E", "113 e", "28", "028", "28 bis", "28-Bis", "28 BIS", "28-bis", "Artículo 28", "articulo 28-A", "Art. 28 Bis",
  "Art 5", "1o.-A", "1º-A", "1°", "1o", "32-B Bis", "32-B-bis", "32 b bis", "18-H BIS", "353-ñ", "353 Ñ", "82 Quáter", "82 quater", "69 B", "69-b", "  113-E  ", "abc", "", "x28", "28-zz", "28 bis ter", "200 octies", "7-A-ter",
  "-5", "28.", "Artículo 1o.-A", "113-E-bis"];

test("30+ variantes de ids dan lo mismo que en Python (id y nombre de archivo)", () => {
  const py = pythonJson(
    "import sys,json\nfrom leyes_mx.ids import normalizar_id, nombre_archivo\nv=json.load(sys.stdin)\nr=[]\nfor x in v:\n  i=normalizar_id(x)\n  r.append([i, nombre_archivo(i) if i else None])\nprint(json.dumps(r))",
    VARIANTES);
  assert.ok(VARIANTES.length >= 30);
  VARIANTES.forEach((v, k) => {
    const id = normalizarId(v);
    assert.deepEqual([id, id ? nombreArchivo(id) : null], py[k], `variante ${JSON.stringify(v)}`);
  });
});

test("las variantes válidas apuntan al mismo archivo existente que Python", () => {
  const dir = path.join(REPO, "leyes", "2026");
  const casos = [["LISR", "113 E", "art-0113-E.md"], ["LISR", "113-e", "art-0113-E.md"], ["LISR", "113E", "art-0113-E.md"], ["CFF", "69 B", "art-0069-B.md"],
    ["LISR", "28", "art-0028.md"], ["LISR", "4 A", "art-0004-A.md"]];
  for (const [ley, v, esperado] of casos) {
    assert.equal(nombreArchivo(normalizarId(v)), esperado);
    assert.ok(fs.existsSync(path.join(dir, ley, esperado)), `${ley}/${esperado}`);
  }
});

test("la Ñ se escribe NN en el archivo y se recupera", () => {
  assert.equal(nombreArchivo("353-Ñ"), "art-0353-NN.md");
  assert.equal(idDesdeArchivo("art-0353-NN.md"), "353-Ñ");
});

test("todo nombre de archivo del repo vuelve a su id y el orden coincide con Python", () => {
  const ids = [];
  for (const ley of fs.readdirSync(path.join(REPO, "leyes", "2026"))) {
    for (const f of fs.readdirSync(path.join(REPO, "leyes", "2026", ley))) {
      const id = idDesdeArchivo(f);
      if (id) { assert.equal(nombreArchivo(id), f); ids.push(id); }
    }
  }
  const muestra = ids.slice(0, 3000);
  const py = pythonJson("import sys,json\nfrom leyes_mx.ids import clave_orden\nv=json.load(sys.stdin)\nprint(json.dumps(sorted(set(v), key=clave_orden)))", muestra);
  assert.deepEqual([...new Set(muestra)].sort(compararIds), py);
});
