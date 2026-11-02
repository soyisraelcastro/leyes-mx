// Servidor MCP por stdio. Solo sirve lo que está en los archivos de datos.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import * as z from "zod";
import { Almacen, SinDatos } from "./almacen.js";
import { Indice } from "./indice.js";
import { respuestaArticulo, respuestaBusqueda, respuestaEstado, respuestaLeyes, respuestaTarifa, respuestaTarifas, respuestaTransitorios } from "./respuestas.js";
import { VERSION } from "./version.js";

const INSTRUCCIONES = [
  "Base local de leyes fiscales y laborales de México (LISR, LIVA, CFF, LFT y reglamentos), un artículo por archivo, más las tarifas de ISR vigentes del Anexo 8 de la RMF.",
  "Los artículos 96 y 152 de la LISR traen la tarifa de la ley; para calcular retenciones o el anual del ejercicio usa obtener_tarifa (Anexo 8), que es la actualizada.",
  "Consúltala ANTES de buscar en internet. Para un artículo conocido usa obtener_articulo; para un tema usa buscar.",
  "Cita siempre ley, artículo, año de vigencia y fecha de última reforma que devuelve la herramienta.",
  "Si la herramienta dice que no existe, responde \"no verificado\"; no completes artículos de memoria.",
  "Respeta las líneas ADVERTENCIA. Un proyecto de reforma NO es ley vigente hasta su publicación en el DOF.",
].join(" ");

function texto(t, extra = {}) {
  return { content: [{ type: "text", text: t }], ...extra };
}
const error = (t) => ({ content: [{ type: "text", text: t }], isError: true });

export function crearServidor(almacen = null) {
  let alm = almacen;
  const indices = {};
  const obtenerAlmacen = () => (alm ||= Almacen.abrir());
  const indice = (proy) => (indices[proy ? "con" : "sin"] ||= new Indice(obtenerAlmacen(), { proyectos: proy }));

  const server = new McpServer({ name: "leyes-mx", version: VERSION }, { instructions: INSTRUCCIONES });
  const envolver = (fn) => async (args) => {
    try { return await fn(args); }
    catch (e) { return error(e instanceof SinDatos ? e.message : `Error: ${e.message}`); }
  };
  const RO = { readOnlyHint: true, idempotentHint: true, openWorldHint: false };

  const leyDesc = "Sigla del ordenamiento, por ejemplo LISR, LIVA, CFF, LFT, RLISR, RLIVA, RCFF (sin distinguir mayúsculas)";
  const anioDesc = "Año de vigencia (opcional). Por omisión, el vigente más reciente que tenga datos.";

  server.registerTool("obtener_articulo", {
    title: "Obtener artículo",
    description: "Devuelve el texto íntegro de un artículo de una ley o reglamento fiscal/laboral mexicano, con año de vigencia, fecha de última reforma, estatus y advertencias. Acepta \"113 E\", \"113-e\", \"28 bis\", \"32-B-bis\". Si el texto es muy extenso se entrega por páginas (parámetro pagina).",
    inputSchema: {
      ley: z.string().describe(leyDesc),
      articulo: z.string().describe("Número de artículo, por ejemplo \"28\", \"113-E\", \"28 bis\""),
      anio: z.number().int().optional().describe(anioDesc),
      pagina: z.number().int().min(1).optional().describe("Página (1 por omisión) cuando el artículo es muy extenso"),
    },
    annotations: RO,
  }, envolver(({ ley, articulo, anio, pagina }) => {
    const a = obtenerAlmacen();
    let f;
    try { f = a.obtenerArticulo(ley, articulo, { anio: anio ?? null }); } catch (e) { return error(e.message); }
    if (!f) {
      const sig = a.siglasDisponibles(anio ?? a.anioPorDefecto(ley) ?? a.anioPorDefecto());
      const conocida = a.anios().some((y) => a.dirLey(`${a.raiz}/leyes/${y}`, ley));
      return texto(`NO VERIFICADO: ${String(ley).toUpperCase()} art. ${articulo} no está en la base local (año ${anio ?? a.anioPorDefecto(ley) ?? "sin datos"}). ` +
        (conocida ? "El ordenamiento existe pero ese artículo no. " : `El ordenamiento no existe en la base. Disponibles: ${sig.join(", ")}. `) +
        "No se inventa texto: consultar la fuente oficial (DOF, diputados.gob.mx).", { structuredContent: { encontrado: false, ley: String(ley).toUpperCase(), articulo } });
    }
    const r = respuestaArticulo(f, pagina ?? 1);
    if (r.error) return error(r.texto);
    return texto(r.texto, { structuredContent: { encontrado: true, ley: f.ley, articulo: f.articulo, anio_vigencia: f.anio_vigencia,
      ultima_reforma_dof: f.ultima_reforma_dof, estatus: f.estatus, pagina: r.pagina, paginas: r.total, advertencias: f.advertencias } });
  }));

  server.registerTool("buscar", {
    title: "Buscar en las leyes",
    description: "Búsqueda por palabras clave (sin acentos, por relevancia) en el texto de los artículos. Devuelve fragmentos; para citar pide el artículo completo con obtener_articulo. Por omisión solo ley vigente; los proyectos de reforma nunca se incluyen salvo que se pida.",
    inputSchema: {
      consulta: z.string().describe("Palabras clave, por ejemplo \"recargos deducibles\""),
      ley: z.string().optional().describe(leyDesc),
      anio: z.number().int().optional().describe(anioDesc),
      incluir_proyectos: z.boolean().optional().describe("Incluir proyectos de reforma, marcados como NO vigentes (false por omisión)"),
      limite: z.number().int().min(1).max(50).optional().describe("Máximo de resultados (10 por omisión)"),
    },
    annotations: RO,
  }, envolver(({ consulta, ley, anio, incluir_proyectos, limite }) => {
    const a = obtenerAlmacen();
    const proy = !!incluir_proyectos;
    const res = indice(proy).buscar(consulta, { ley: ley ?? null, anio: anio ?? null, incluirProyectos: proy, limite: limite ?? 10, anioDefecto: a.anioPorDefecto(ley ?? null) });
    return texto(respuestaBusqueda(consulta, res, { incluirProyectos: proy }), { structuredContent: { resultados: res } });
  }));

  server.registerTool("listar_leyes", {
    title: "Listar ordenamientos",
    description: "Lista las leyes y reglamentos que hay en la base local, con año de vigencia, número de artículos y fecha de última reforma DOF. Sirve para saber qué cubre la base antes de afirmar que algo no existe.",
    inputSchema: { anio: z.number().int().optional().describe("Filtrar por año de vigencia (opcional)") },
    annotations: RO,
  }, envolver(({ anio }) => {
    const a = obtenerAlmacen();
    const leyes = a.listarLeyes().filter((x) => !anio || x.anio_vigencia === anio);
    return texto(respuestaLeyes(leyes, a.version), { structuredContent: { leyes } });
  }));

  server.registerTool("estado_reforma", {
    title: "Estado de la reforma",
    description: "Estado del seguimiento de la reforma fiscal en trámite (por ejemplo 2027), con línea de tiempo y fuentes, y la última reforma DOF de cada ley en la base. Consúltalo antes de afirmar algo sobre una reforma futura: un proyecto no es ley hasta publicarse en el DOF.",
    inputSchema: { anio: z.number().int().optional().describe("Año del proyecto de reforma (por omisión, el más reciente)") },
    annotations: RO,
  }, envolver(({ anio }) => {
    const a = obtenerAlmacen();
    const e = a.estadoReforma(anio ?? null);
    const leyes = a.listarLeyes().map((x) => ({ sigla: x.sigla, anio_vigencia: x.anio_vigencia, ultima_reforma_dof: x.ultima_reforma_dof }));
    return texto(respuestaEstado(e, leyes, a.version), { structuredContent: { reforma: e, leyes } });
  }));

  server.registerTool("obtener_tarifa", {
    title: "Obtener tarifa de ISR (Anexo 8 de la RMF)",
    description: "Tarifas de ISR vigentes del Anexo 8 de la Resolución Miscelánea Fiscal (mensual, anual, por 7/10/15 días, bimestrales, etc.), con límites, cuota fija y porcentaje. Son las que se aplican en el ejercicio, no la tabla histórica de la ley. Sin parámetro `tarifa` lista las disponibles. Ejemplos: B-V (mensual 2026), C-II (anual 2026).",
    inputSchema: {
      tarifa: z.string().optional().describe("Id exacto o apartado, por ejemplo \"B-V\", \"C-II\", \"B-IV-15-dias\". Omitir para listar."),
      anio: z.number().int().optional().describe("Año de vigencia del anexo (por omisión, el más reciente)"),
    },
    annotations: RO,
  }, envolver(({ tarifa, anio }) => {
    const a = obtenerAlmacen();
    if (!tarifa) {
      const lista = a.listarTarifas(anio ?? null);
      return texto(respuestaTarifas(lista), { structuredContent: { tarifas: lista } });
    }
    const t = a.obtenerTarifa(tarifa, anio ?? null);
    if (!t) return texto(`NO VERIFICADO: la tarifa ${tarifa} del Anexo 8 no está en la base local. No se inventan cifras: consultar el DOF o sat.gob.mx.`, { structuredContent: { encontrado: false } });
    if (t.ambiguo) return texto(`La clave ${tarifa} corresponde a varias tarifas; usa el id exacto:\n` + t.ambiguo.map((x) => `- ${x.id}: ${x.titulo}`).join("\n"), { structuredContent: { encontrado: false, ambiguo: t.ambiguo } });
    return texto(respuestaTarifa(t), { structuredContent: { encontrado: true, id: t.id, apartado: t.apartado, anio_vigencia: t.vigencia_anio, publicado_dof: t.publicado_dof } });
  }));

  server.registerTool("obtener_transitorios", {
    title: "Obtener transitorios",
    description: "Devuelve los artículos transitorios de una ley (por decreto de reforma). Necesario, por ejemplo, para la gradualidad de la jornada laboral de la LFT. Se entrega por páginas si es extenso.",
    inputSchema: {
      ley: z.string().describe(leyDesc),
      anio: z.number().int().optional().describe(anioDesc),
      pagina: z.number().int().min(1).optional().describe("Página (1 por omisión)"),
    },
    annotations: RO,
  }, envolver(({ ley, anio, pagina }) => {
    const a = obtenerAlmacen();
    const t = a.obtenerTransitorios(ley, anio ?? null);
    if (!t) return texto(`NO VERIFICADO: no hay transitorios de ${String(ley).toUpperCase()} en la base local. No se inventa texto: consultar la fuente oficial.`, { structuredContent: { encontrado: false } });
    const r = respuestaTransitorios(t, pagina ?? 1);
    if (r.error) return error(r.texto);
    return texto(r.texto, { structuredContent: { encontrado: true, ley: t.ley, pagina: r.pagina, paginas: r.total } });
  }));

  return server;
}

export async function servir() {
  const server = crearServidor();
  await server.connect(new StdioServerTransport());
  process.stderr.write(`leyes-mx ${VERSION}: servidor MCP listo (stdio)\n`);
}
