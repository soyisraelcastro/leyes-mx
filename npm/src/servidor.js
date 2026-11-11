// Servidor MCP por stdio. Solo sirve lo que está en los archivos de datos.
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import * as z from "zod";
import { Almacen, SinDatos } from "./almacen.js";
import { Indice } from "./indice.js";
import { noEncontrado, respuestaArticulo, respuestaBusqueda, respuestaEstado, respuestaLeyes, respuestaRegla, respuestaSubsidio, respuestaTarifa, respuestaTarifas, respuestaTema, respuestaTemas, respuestaTransitorios } from "./respuestas.js";
import { VERSION } from "./version.js";

const INSTRUCCIONES = [
  "Leyes fiscales y laborales de México en el equipo del usuario: Ley del ISR (LISR), Ley del IVA (LIVA), Código Fiscal de la Federación (CFF), Ley Federal del Trabajo (LFT), Ley del Seguro Social (LSS), Ley Federal de los Derechos del Contribuyente (LFDC), Ley de Coordinación Fiscal (LCF), Ley Orgánica de la Procuraduría de la Defensa del Contribuyente (LOPDC) y sus reglamentos (RLISR, RLIVA, RCFF, RACERF), más las tarifas de ISR del Anexo 8 de la RMF.",
  "REGLA: antes de responder cualquier consulta fiscal o laboral de México (ISR, IVA, deducciones, retenciones, CFDI, aguinaldo, PTU, vacaciones, despido, tarifas, infracciones, \"qué dice el artículo\", \"fundamento legal\") y antes de citar un artículo, consulta estas herramientas; no respondas de memoria ni busques en internet primero.",
  "Cómo: (1) para un artículo conocido usa obtener_articulo; (2) para un tema usa buscar, que es léxico y solo devuelve fragmentos, y reformula con las palabras de la ley (\"accesorios de las contribuciones\" y no \"actualizaciones\"; \"comprobante fiscal digital por Internet\" y no \"CFDI\"); (3) lee SIEMPRE el artículo completo con obtener_articulo antes de afirmar algo, porque un fragmento puede omitir la excepción o la fracción que cambia la respuesta; (4) cita.",
  "Cita siempre ley, artículo, fracción o párrafo (léelo del texto, no de memoria), año de vigencia y fecha de última reforma DOF que devuelve la herramienta. Un artículo derogado no aplica.",
  "Las tarifas de ISR (mensual, anual, por periodos) se obtienen con obtener_tarifa (Anexo 8 de la RMF), nunca de la tabla de los arts. 96 y 152 de la LISR ni de memoria: esas cifras se actualizan cada año.",
  "Respeta las líneas ADVERTENCIA. Un proyecto de reforma (por ejemplo la de 2027) NO es ley vigente hasta su publicación en el DOF: no lo presentes como vigente y, si lo mencionas, dilo y da la fecha de estado_reforma.",
  "Si la herramienta no encuentra lo pedido, dilo con claridad (\"no verificado\") y PREGUNTA al usuario si desea que lo busques en internet. Nunca busques en internet por tu cuenta sin su permiso; si lo autoriza, usa solo fuentes oficiales (DOF, SAT, Cámara de Diputados) y aclara que ese dato no proviene de la base verificada.",
  "Las reglas de la Resolución Miscelánea Fiscal 2026 se leen con obtener_regla: es el texto original del DOF del 28-12-2025, SIN las resoluciones de modificación de 2026, y la herramienta lo advierte. El subsidio para el empleo (decreto del DOF 01-05-2024 y su reforma del 31-12-2025, con la UMA de 2025 y 2026 que publica el INEGI) se consulta con obtener_subsidio_empleo; no lo calcules de memoria. La base no incluye otros anexos de la RMF (salvo el Anexo 8), jurisprudencia, criterios del SAT, el valor de la UMA de otros años ni la jurisprudencia o los criterios del IMSS: de eso no hay dato local.",
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

  const leyDesc = "Sigla del ordenamiento, por ejemplo LISR, LIVA, CFF, LFT, LSS, LFDC, LCF, LOPDC, LIEPS, LIF, RLISR, RLIVA, RCFF, RACERF (sin distinguir mayúsculas)";
  const anioDesc = "Año de vigencia (opcional). Por omisión, el vigente más reciente que tenga datos.";

  server.registerTool("obtener_articulo", {
    title: "Obtener artículo",
    description: "Muestra lo que dice un artículo de la LISR, LIVA, CFF, LFT, LSS, LFDC, LCF, LOPDC, LIEPS, LIF o de sus reglamentos (\"qué dice el artículo 28 de la LISR\", \"fundamento legal\", \"qué dice la ley sobre...\"). Úsala ANTES de responder cualquier consulta fiscal o laboral de México y antes de citar un artículo: devuelve el texto íntegro con año de vigencia, fecha de última reforma, estatus y advertencias. Es la fuente para CITAR; después de buscar, léelo completo porque buscar solo da fragmentos. Cita ley, artículo, fracción, vigencia y última reforma tal como salen. Acepta \"113 E\", \"113-e\", \"28 bis\", \"32-B-bis\". Si el texto es muy extenso se entrega por páginas (parámetro pagina). Si no existe, el resultado dice NO VERIFICADO y qué hacer: no inventes el artículo y pregunta al usuario antes de buscar en internet.",
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
    description: "Lista qué leyes y reglamentos fiscales y laborales hay en la base local (LISR, LIVA, CFF, LFT, LSS, LFDC, LCF, LOPDC, LIEPS, LIF y reglamentos), con año de vigencia, número de artículos y fecha de última reforma DOF. Úsala para saber qué cubre la base antes de decir que algo \"no está\" y para citar la fecha de última reforma.",
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

  server.registerTool("obtener_subsidio_empleo", {
    title: "Obtener el subsidio para el empleo (decreto del DOF)",
    description: "Subsidio para el empleo vigente en 2026: tope de ingresos mensuales, porcentaje de la UMA mensual (15.02%; 15.59% en enero de 2026), regla para periodos menores a un mes, valor de la UMA 2025 y 2026 (INEGI, DOF) y el texto de los decretos (01-05-2024, reformas del 31-12-2024 y 31-12-2025) y el texto consolidado. Úsala SIEMPRE para cualquier cálculo o cita del subsidio para el empleo: ya no es una tabla de montos variables ni está en el Anexo 8 ni en el art. 96 de la LISR. Cita el decreto y su fecha de publicación en el DOF. Los importes marcados como cálculo derivado no son texto del DOF. Sin parámetro `documento` da el resumen; con `documento` (por ejemplo \"vigente-2026\" o \"modificacion-2025-12-31\") devuelve también ese texto.",
    inputSchema: {
      documento: z.string().optional().describe("Id del documento: vigente-2026, decreto-2024-05-01, modificacion-2024-12-31, modificacion-2025-12-31, uma-2025 o uma-2026. Omitir para el resumen."),
      anio: z.number().int().optional().describe("Año de vigencia (por omisión, el más reciente)"),
    },
    annotations: RO,
  }, envolver(({ documento, anio }) => {
    const a = obtenerAlmacen();
    const f = a.obtenerSubsidioEmpleo({ anio: anio ?? null, documento: documento ?? null });
    if (!f) return texto(noEncontrado(documento ? `el documento ${documento} del subsidio para el empleo` : "el subsidio para el empleo",
      documento ? "Los ids válidos salen de llamar la herramienta sin `documento`." : "Estos datos no lo traen: ejecuta npx leyes-mx actualizar."), { structuredContent: { encontrado: false } });
    return texto(respuestaSubsidio(f), { structuredContent: { encontrado: true, anio: f.anio, parametros: f.parametros, uma: f.uma, documento: f.texto_documento?.id ?? null } });
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

  server.registerTool("obtener_regla", {
    title: "Obtener regla de la Resolución Miscelánea Fiscal",
    description: "Muestra lo que dice una regla de la RMF 2026 (por ejemplo 2.7.1.1, 3.17.2, 11.1.1) con su título, ubicación, fundamento y las leyes y reglas a las que remite. Úsala cuando el usuario cite una regla de la miscelánea o cuando un artículo o el fundamento de otra regla remita a ella. OJO: es el texto original publicado el 28-12-2025, sin las resoluciones de modificación de 2026; la respuesta lo advierte y debes repetirlo. Para buscar por materia usa temas.",
    inputSchema: {
      regla: z.string().describe("Número de regla, por ejemplo \"2.7.1.1\" o \"3.17.2\""),
      anio: z.number().int().optional().describe(anioDesc),
      pagina: z.number().int().min(1).optional().describe("Página (1 por omisión) cuando la regla es muy extensa"),
    },
    annotations: RO,
  }, envolver(({ regla, anio, pagina }) => {
    const a = obtenerAlmacen();
    let f;
    try { f = a.obtenerRegla(regla, { anio: anio ?? null }); } catch (e) { return error(e.message); }
    if (!f) {
      const hay = a.aniosReglas().length > 0;
      return texto(noEncontrado(`la regla ${regla} de la RMF`, hay ? "Esa regla no existe en la RMF 2026 de la base." : "Estos datos no traen las reglas de la RMF: ejecuta npx leyes-mx actualizar."),
        { structuredContent: { encontrado: false, regla: String(regla) } });
    }
    const r = respuestaRegla(f, pagina ?? 1);
    if (r.error) return error(r.texto);
    return texto(r.texto, { structuredContent: { encontrado: true, ley: f.ley, regla: f.regla, titulo: f.titulo, anio_vigencia: f.anio_vigencia, estatus: f.estatus,
      modificaciones_aplicadas: f.modificaciones_aplicadas, pagina: r.pagina, paginas: r.total, referencias_leyes: f.referencias_leyes, referencias_reglas: f.referencias_reglas } });
  }));

  server.registerTool("temas", {
    title: "Documentos de la base por tema",
    description: "Encuentra, en TODAS las leyes, reglamentos y reglas de la RMF a la vez, lo que trata o menciona una materia (\"todo lo de hidrocarburos\", \"CFDI\", \"subcontratación\", \"cuotas del IMSS\", \"donatarias\", \"PTU\"). Sin parámetros lista los temas. Con tema devuelve los artículos y reglas de ese tema ordenados por puntaje. Es un índice por palabras de la ley (no semántico) para saber DÓNDE mirar: después lee cada documento con obtener_articulo u obtener_regla antes de citarlo. Si el tema no está, usa buscar.",
    inputSchema: {
      tema: z.string().optional().describe("Id o nombre del tema, por ejemplo \"hidrocarburos\". Omitir para listar los temas."),
      ley: z.string().optional().describe(leyDesc + "; para la RMF usa RMF"),
      minimo: z.number().int().min(1).optional().describe("Puntaje mínimo (1 por omisión); súbelo para quedarte con lo más central"),
      limite: z.number().int().min(1).max(100).optional().describe("Máximo de documentos (25 por omisión)"),
      anio: z.number().int().optional().describe(anioDesc),
    },
    annotations: RO,
  }, envolver(({ tema, ley, minimo, limite, anio }) => {
    const a = obtenerAlmacen();
    const info = a.temas(anio ?? null);
    if (!info) return texto(noEncontrado("el índice de temas", "Estos datos no lo traen: ejecuta npx leyes-mx actualizar."), { structuredContent: { encontrado: false } });
    if (!tema) return texto(respuestaTemas(info), { structuredContent: { anio: info.anio, temas: info.temas.map((t) => ({ id: t.id, nombre: t.nombre, documentos: t.documentos })) } });
    const res = a.resolverTema(tema, anio ?? null);
    if (!res) return texto(noEncontrado(`el tema ${JSON.stringify(tema)}`, `Temas disponibles: ${info.temas.map((t) => t.id).join(", ")}. Si no es uno de ellos, usa buscar.`), { structuredContent: { encontrado: false } });
    if (res.ambiguo) return texto(`${JSON.stringify(tema)} corresponde a varios temas; usa el id exacto:\n` + res.ambiguo.map((x) => `- ${x.id}: ${x.nombre}`).join("\n"), { structuredContent: { encontrado: false, ambiguo: res.ambiguo } });
    const r = a.documentosDeTema(res.tema.id, { anio: res.anio, ley: ley ?? null, minimo: minimo ?? 1, limite: limite ?? 25 });
    return texto(respuestaTema(res.tema, r, { ley: ley ?? null, minimo: minimo ?? 1 }), { structuredContent: { encontrado: true, tema: res.tema.id, anio_vigencia: r.anio, total: r.total,
      documentos: r.lista.map((x) => ({ ley: x.ley, id: x.id, tipo: x.tipo, puntaje: x.puntaje, donde: x.donde, titulo: x.titulo })) } });
  }));

  return server;
}

export async function servir() {
  const server = crearServidor();
  await server.connect(new StdioServerTransport());
  process.stderr.write(`leyes-mx ${VERSION}: servidor MCP listo (stdio)\n`);
}
