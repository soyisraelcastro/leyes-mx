// Lee, en tiempo de build, lo que hay en el repo: leyes/<año>/<SIGLA>/_meta.json (por versiones.js), fuentes.json y proyectos/<año>/estado.json.
// Nada se escribe a mano en la página. Requiere que el build vea la raíz del repo (carpeta superior a sitio/).
import fs from "node:fs";
import path from "node:path";
import * as versiones from "../../../npm/src/versiones.js";  // único punto que resuelve leyes/<año>/<SIGLA> (capas que heredan)

const RAIZ = path.resolve(process.cwd(), "..");

function leer(rel) {
  const p = path.join(RAIZ, rel);
  if (!fs.existsSync(p)) throw new Error(`No se encontró ${rel} en ${RAIZ}. El build de sitio/ necesita ver el repo completo (en Vercel: "Include source files outside of the Root Directory" activado, que es el valor por defecto).`);
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

export function leyes() {
  const fuentes = leer("fuentes.json").leyes;
  const res = [];
  for (const anio of versiones.anios(RAIZ)) {
    for (const sigla of versiones.siglas(RAIZ, anio)) {
      const meta = versiones.capa(RAIZ, sigla, anio).meta;
      const f = fuentes.find((x) => x.sigla === meta.sigla);
      res.push({ sigla: meta.sigla, nombre: meta.nombre_oficial, tipo: f?.tipo ?? meta.tipo, anio: meta.vigencia_anio, reforma: meta.ultima_reforma_dof,
        articulos: meta.articulos_extraidos, descarga: meta.fecha_descarga, advertencias: (meta.advertencias || []).length });
    }
  }
  return res;
}

export function reforma() {
  const base = path.join(RAIZ, "proyectos");
  if (!fs.existsSync(base)) return null;
  const anios = fs.readdirSync(base).filter((n) => /^\d+$/.test(n) && fs.existsSync(path.join(base, n, "estado.json"))).sort();
  if (!anios.length) return null;
  const e = leer(path.join("proyectos", anios[anios.length - 1], "estado.json"));
  return { anio: e.anio, actualizado: e.actualizado, resumen: e.resumen, esLey: e.es_ley_vigente, enVigor: e.entrada_en_vigor_prevista,
    hitos: (e.hitos || []).map((h) => ({ fecha: h.fecha, hito: h.hito, nivel: h.nivel, confirmado: h.confirmado, detalle: h.detalle })) };
}

// Cuenta las tarifas del Anexo 8 de la RMF (un archivo .md por tarifa; los que empiezan con "_" son índices).
export function anexo8() {
  const base = path.join(RAIZ, "rmf");
  if (!fs.existsSync(base)) return null;
  const anios = fs.readdirSync(base).filter((n) => /^\d+$/.test(n) && fs.existsSync(path.join(base, n, "anexo-8"))).sort();
  if (!anios.length) return null;
  const anio = anios[anios.length - 1];
  const tarifas = fs.readdirSync(path.join(base, anio, "anexo-8")).filter((n) => n.endsWith(".md") && !n.startsWith("_")).length;
  return { anio, tarifas };
}

// Primeras filas de una tarifa del Anexo 8 (para la demo de la portada), leídas del .md tal cual.
export function tarifa(id, n = 4) {
  const base = path.join(RAIZ, "rmf");
  const anio = fs.readdirSync(base).filter((x) => /^\d+$/.test(x)).sort().pop();
  const dir = path.join(base, anio, "anexo-8");
  const arch = fs.readdirSync(dir).find((f) => f.startsWith(id) && f.endsWith(".md"));
  if (!arch) return null;
  const txt = fs.readFileSync(path.join(dir, arch), "utf8");
  const campo = (k) => (txt.match(new RegExp(`^${k}: "?([^"\\n]+)"?$`, "m")) || [])[1];
  const filas = txt.split("\n").filter((l) => /^\|\s*[\d,]+\.\d+/.test(l)).slice(0, n)
    .map((l) => l.split("|").slice(1, -1).map((c) => c.trim()));
  return { anio, apartado: campo("apartado"), dof: campo("publicado_dof"), filas };
}

// Subsidio para el empleo: parámetros y UMA leídos de decretos/<año>/spe/_meta.json (nada se escribe a mano en el sitio).
export function subsidioEmpleo() {
  const base = path.join(RAIZ, "decretos");
  if (!fs.existsSync(base)) return null;
  const anios = fs.readdirSync(base).filter((n) => /^\d+$/.test(n) && fs.existsSync(path.join(base, n, "spe", "_meta.json"))).sort();
  if (!anios.length) return null;
  const anio = anios[anios.length - 1];
  const m = JSON.parse(fs.readFileSync(path.join(base, anio, "spe", "_meta.json"), "utf8"));
  return { anio, parametros: m.parametros_2026, uma: m.uma, derivado: m.calculo_derivado, noVerificado: m.no_verificado || [],
    documentos: (m.documentos || []).filter((d) => d.tipo === "decreto" || d.tipo === "modificacion").map((d) => ({ id: d.id, dof: d.publicado_dof, url: d.fuente_url, estatus: d.estatus })) };
}
