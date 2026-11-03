// Lee, en tiempo de build, lo que hay en el repo: leyes/<año>/<SIGLA>/_meta.json, fuentes.json y proyectos/<año>/estado.json.
// Nada se escribe a mano en la página. Requiere que el build vea la raíz del repo (carpeta superior a sitio/).
import fs from "node:fs";
import path from "node:path";

const RAIZ = path.resolve(process.cwd(), "..");

function leer(rel) {
  const p = path.join(RAIZ, rel);
  if (!fs.existsSync(p)) throw new Error(`No se encontró ${rel} en ${RAIZ}. El build de sitio/ necesita ver el repo completo (en Vercel: "Include source files outside of the Root Directory" activado, que es el valor por defecto).`);
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

export function leyes() {
  const fuentes = leer("fuentes.json").leyes;
  const base = path.join(RAIZ, "leyes");
  const res = [];
  for (const anio of fs.readdirSync(base).filter((n) => /^\d+$/.test(n)).sort()) {
    for (const sigla of fs.readdirSync(path.join(base, anio)).sort()) {
      const m = path.join("leyes", anio, sigla, "_meta.json");
      if (!fs.existsSync(path.join(RAIZ, m))) continue;
      const meta = leer(m);
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
