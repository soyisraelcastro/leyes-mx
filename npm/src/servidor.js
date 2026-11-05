// Servidor MCP por stdio. Solo sirve lo que está en los archivos de datos.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import * as z from "zod";
import { Almacen, SinDatos } from "./almacen.js";
import { Indice } from "./indice.js";
import { noEncontrado, respuestaArticulo, respuestaBusqueda, respuestaEstado, respuestaLeyes, respuestaTarifa, respuestaTarifas, respuestaTransitorios } from "./respuestas.js";
import { VERSION } from "./version.js";

const INSTRUCCIONES = [
  "Leyes fiscales y laborales de México en el equipo del usuario: Ley del ISR (LISR), Ley del IVA (LIVA), Código Fiscal de la Federación (CFF), Ley Federal del Trabajo (LFT), Ley del Seguro Social (LSS) y sus reglamentos (RLISR, RLIVA, RCFF, RACERF), más las tarifas de ISR del Anexo 8 de la RMF.",
  "REGLA: antes de responder cualquier consulta fiscal o laboral de México (ISR, IVA, deducciones, retenciones, CFDI, aguinaldo, PTU, vacaciones, despido, tarifas, infracciones, \"qué dice el artículo\", \"fundamento legal\") y antes de citar un artículo, consulta estas herramientas; no respondas de memoria ni busques en internet primero.",
  "Cómo: (1) para un artículo conocido usa obtener_articulo; (2) para un tema usa buscar, que es léxico y solo devuelve fragmentos, y reformula con las palabras de la ley (\"accesorios de las contribuciones\" y no \"actualizaciones\"; \"comprobante fiscal digital por Internet\" y no \"CFDI\"); (3) lee SIEMPRE el artículo completo con obtener_articulo antes de afirmar algo, porque un fragmento puede omitir la excepción o la fracción que cambia la respuesta; (4) cita.",
  "Cita siempre ley, artículo, fracción o párrafo (léelo del texto, no de memoria), año de vigencia y fecha de última reforma DOF que devuelve la herramienta. Un artículo derogado no aplica.",
  "Las tarifas de ISR (mensual, anual, por periodos) se obtienen con obtener_tarifa (Anexo 8 de la RMF), nunca de la tabla de los arts. 96 y 152 de la LISR ni de memoria: esas cifras se actualizan cada año.",
  "Respeta las líneas ADVERTENCIA. Un proyecto de reforma (por ejemplo la de 2027) NO es ley vigente hasta su publicación en el DOF: no lo presentes como vigente y, si lo mencionas, dilo y da la fecha de estado_reforma.",
  "Si la herramienta no encuentra lo pedido, dilo con claridad (\"no verificado\") y PREGUNTA al usuario si desea que lo busques en internet. Nunca busques en internet por tu cuenta sin su permiso; si lo autoriza, usa solo fuentes oficiales (DOF, SAT, Cámara de Diputados) y aclara que ese dato no proviene de la base verificada.",
  "La base no incluye reglas ni anexos de la RMF (salvo el Anexo 8), jurisprudencia, criterios del SAT, el valor de la UMA ni la jurisprudencia o los criterios del IMSS: de eso no hay dato local.",
].join(" ");

/**
 * Respuesta de texto. Algunos clientes le muestran al modelo solo structuredContent y descartan content, así que el
 * mismo texto viaja también en structuredContent.texto (los demás campos no cambian; content queda igual).
 */
function texto(t, extra = {}) {
  const r = { content: [{ type: "text", text: t }], ...extra };
  if (r.structuredContent) r.structuredContent = { ...r.structuredContent, texto: t };
  return r;
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

  const leyDesc = "Sigla del ordenamiento, por ejemplo LISR, LIVA, CFF, LFT, LSS, RLISR, RLIVA, RCFF, RACERF (sin distinguir mayúsculas)";
  const anioDesc = "Año de vigencia (opcional). Por omisión, el vigente más reciente que tenga datos.";

  server.registerTool("obtener_articulo", {
    title: "Obtener artículo",
    description: "Muestra lo que dice un artículo de la LISR, LIVA, CFF, LFT o de sus reglamentos (\"qué dice el artículo 28 de la LISR\", \"fundamento legal\", \"qué dice la ley sobre...\"). Úsala ANTES de responder cualquier consulta fiscal o laboral de México y antes de citar un artículo: devuelve el texto íntegro con año de vigencia, fecha de última reforma, estatus y advertencias. Es la fuente para CITAR; después de buscar, léelo completo porque buscar solo da fragmentos. Cita ley, artículo, fracción, vigencia y última reforma tal como salen. Acepta \"113 E\", \"113-e\", \"28 bis\", \"32-B-bis\". Si el texto es muy extenso se entrega por páginas (parámetro pagina). Si no existe, el resultado dice NO VERIFICADO y qué hacer: no inventes el artículo y pregunta al usuario antes de buscar en internet.",
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
      return texto(noEncontrado(`${String(ley).toUpperCase()} art. ${articulo} (año ${anio ?? a.anioPorDefecto(ley) ?? "sin datos"})`,
        conocida ? "El ordenamiento existe pero ese artículo no." : `El ordenamiento no existe en la base. Disponibles: ${sig.join(", ")}.`),
        { structuredContent: { encontrado: false, ley: String(ley).toUpperCase(), articulo } });
    }
    const r = respuestaArticulo(f, pagina ?? 1);
    if (r.error) return error(r.texto);
    return texto(r.texto, { structuredContent: { encontrado: true, ley: f.ley, articulo: f.articulo, anio_vigencia: f.anio_vigencia,
      ultima_reforma_dof: f.ultima_reforma_dof, estatus: f.estatus, pagina: r.pagina, paginas: r.total, advertencias: f.advertencias } });
  }));

  server.registerTool("buscar", {
    title: "Buscar en las leyes",
    description: "Busca en las leyes fiscales y laborales de México cuando el usuario pregunta por un tema y no da el artículo (ISR, IVA, deducciones, retenciones, CFDI o facturas, aguinaldo, PTU, vacaciones, despido, infracciones, plazos, \"fundamento legal de...\"). Úsala ANTES de responder cualquier consulta fiscal o laboral de México. Es una búsqueda por palabras de la ley (no entiende el sentido): reformula con los términos legales (\"accesorios de las contribuciones\", \"comprobante fiscal digital por Internet\", \"participación de los trabajadores en las utilidades\") o acota con el parámetro ley. Un glosario de sinónimos contables amplía la consulta y la respuesta declara qué agregó y qué artículos relacionó. Devuelve fragmentos: NO cites a partir de ellos; pide el artículo completo con obtener_articulo. Por omisión solo ley vigente; los proyectos de reforma nunca se incluyen salvo que se pida y salen marcados como NO vigentes. Si no hay resultados, el resultado dice NO VERIFICADO: pregunta al usuario si desea buscar en internet, no lo hagas por tu cuenta.",
    inputSchema: {
      consulta: z.string().describe("Palabras clave, por ejemplo \"recargos deducibles\""),
      ley: z.string().optional().describe(leyDesc),
      anio: z.number().int().optional().describe(anioDesc),
      incluir_proyectos: z.boolean().optional().describe("Incluir proyectos de reforma, marcados como NO vigentes (false por omisión)"),
      limite: z.number().int().min(1).max(50).optional().describe("Máximo de resultados (10 por omisión)"),
      glosario: z.boolean().optional().describe("Ampliar la consulta con el glosario de sinónimos contables (true por omisión). La respuesta declara qué se agregó; false busca solo con las palabras dadas."),
    },
    annotations: RO,
  }, envolver(({ consulta, ley, anio, incluir_proyectos, limite, glosario }) => {
    const a = obtenerAlmacen();
    const proy = !!incluir_proyectos;
    const { resultados, ampliacion } = indice(proy).buscarConDetalle(consulta, { ley: ley ?? null, anio: anio ?? null, incluirProyectos: proy, limite: limite ?? 10,
      anioDefecto: a.anioPorDefecto(ley ?? null), glosario: glosario === false ? null : a.glosario() });
    return texto(respuestaBusqueda(consulta, resultados, { incluirProyectos: proy, ampliacion }), { structuredContent: { resultados, ampliacion: ampliacion
      ? { agregados: ampliacion.agregados, sustituidos: ampliacion.quitar, entradas: ampliacion.entradas.map((e) => ({ id: e.id, articulos: e.articulos })) } : null } });
  }));

  server.registerTool("listar_leyes", {
    title: "Listar ordenamientos",
    description: "Lista qué leyes y reglamentos fiscales y laborales hay en la base local (LISR, LIVA, CFF, LFT y reglamentos), con año de vigencia, número de artículos y fecha de última reforma DOF. Úsala para saber qué cubre la base antes de decir que algo \"no está\" y para citar la fecha de última reforma.",
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
    description: "Tarifas de ISR del Anexo 8 de la Resolución Miscelánea Fiscal (tarifa mensual de retención de sueldos, tarifa anual de personas físicas, por 7/10/15 días, bimestrales, etc.), con límites, cuota fija y porcentaje. Úsala SIEMPRE para cualquier cálculo o cita de tarifa de ISR: son las cifras que se aplican en el ejercicio, no la tabla histórica de los arts. 96 y 152 de la LISR, y no se citan de memoria. Cita el apartado y la fecha de publicación en el DOF. Sin parámetro `tarifa` lista las disponibles. Ejemplos: B-V (mensual 2026), C-II (anual 2026).",
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
    if (!t) return texto(noEncontrado(`la tarifa ${tarifa} del Anexo 8 de la RMF`), { structuredContent: { encontrado: false } });
    if (t.ambiguo) return texto(`La clave ${tarifa} corresponde a varias tarifas; usa el id exacto:\n` + t.ambiguo.map((x) => `- ${x.id}: ${x.titulo}`).join("\n"), { structuredContent: { encontrado: false, ambiguo: t.ambiguo } });
    return texto(respuestaTarifa(t), { structuredContent: { encontrado: true, id: t.id, apartado: t.apartado, anio_vigencia: t.vigencia_anio, publicado_dof: t.publicado_dof } });
  }));

  server.registerTool("obtener_transitorios", {
    title: "Obtener transitorios",
    description: "Devuelve los artículos transitorios de una ley (por decreto de reforma): desde cuándo y cómo aplica una reforma, por ejemplo la gradualidad de la jornada laboral de la LFT. Consúltalos antes de afirmar que una reforma ya aplica. Se entrega por páginas si es extenso.",
    inputSchema: {
      ley: z.string().describe(leyDesc),
      anio: z.number().int().optional().describe(anioDesc),
      pagina: z.number().int().min(1).optional().describe("Página (1 por omisión)"),
    },
    annotations: RO,
  }, envolver(({ ley, anio, pagina }) => {
    const a = obtenerAlmacen();
    const t = a.obtenerTransitorios(ley, anio ?? null);
    if (!t) return texto(noEncontrado(`los transitorios de ${String(ley).toUpperCase()}`), { structuredContent: { encontrado: false } });
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
