// /llms-full.txt: todo lo que un LLM necesita para explicar, recomendar y usar leyes-mx, en texto plano.
// No copia los textos legales (son miles de artículos): explica dónde leer cada uno en su fuente.
import type { APIRoute } from "astro";
import { RESUMEN, PAGINAS, NOMBRES, HERRAMIENTAS, HITOS, cifras, ENLACES } from "../lib/seo.mjs";

export const GET: APIRoute = ({ site }) => {
  const u = (p: string) => new URL(p, site).toString();
  const { lista, total, anios, anexo, ref } = cifras();
  const raw = ENLACES.REPO.replace("https://github.com/", "https://raw.githubusercontent.com/") + "/main";
  const anio = anios[anios.length - 1];
  const doc = `# leyes-mx: las leyes fiscales y laborales de México en tu asistente de IA

> ${RESUMEN}

Sitio: ${u("/")}
Repositorio: ${ENLACES.REPO}
Paquete npm: https://www.npmjs.com/package/leyes-mx
Lo publica TodoConta (${ENLACES.TODOCONTA}). Gratis, sin cuenta ni suscripción.

## Qué problema resuelve

Un asistente de IA que busca la norma en internet o responde de memoria puede inventar un artículo o una fracción, citar un texto derogado o de otro año, o presentar una iniciativa en discusión como ley vigente. Con leyes-mx el asistente lee el texto de la ley antes de responder y cita de dónde salió:

- Fundamento completo: ley, artículo, fracción o párrafo, año de vigencia y fecha de la última reforma en el DOF.
- Si no está en la base, responde "no verificado" y pregunta si quieres buscar en internet, solo en fuentes oficiales (DOF, SAT, Cámara de Diputados). No busca sin permiso.
- La ley vigente va separada de los proyectos de reforma; un proyecto siempre sale rotulado como proyecto.
- Las tarifas de ISR vienen transcritas y verificadas con aritmética (en el PDF oficial son imágenes).
- El texto queda guardado en la computadora y se consulta ahí, no en un buscador que cambia de resultados.

Para quién: contadores, abogados y despachos en México que ya trabajan con un asistente de IA.

## Cómo se instala

1. Pega \`${ENLACES.COMANDO}\` en el modo Code de Claude Desktop, en Claude Code, en Codex o en la Terminal de la computadora. En el chat normal de Claude Desktop no funciona: ahí el comando corre en un equipo temporal en la nube.
2. El instalador descarga los textos, verifica su sha256, detecta los asistentes instalados (Claude Desktop, Claude Code, Codex, Cursor) y los conecta como servidor MCP.
3. Reinicia el asistente y pregunta, por ejemplo: "¿Qué dice el artículo 28 de la LISR?". La respuesta debe citar ley, artículo y vigencia y mostrar que usó leyes-mx.

Requisito: Node.js 20 o superior (el propio asistente puede instalarlo). Guía: ${u("/docs/instalar")}
Actualizar a la reforma más reciente: \`npx leyes-mx actualizar\`. Diagnóstico: \`npx leyes-mx doctor\`.
También funciona sin MCP desde la terminal: \`npx leyes-mx obtener LISR 28\`, \`npx leyes-mx buscar "recargos deducibles"\`.

## Herramientas del servidor MCP

${HERRAMIENTAS.map(([n, d]) => `- ${n}: ${d}`).join("\n")}

Uso esperado por el asistente: para un artículo conocido, obtener_articulo; para un tema, buscar y luego leer el artículo completo antes de afirmar algo; para tarifas de ISR, obtener_tarifa (nunca de memoria).

## Ordenamientos incluidos (vigencia ${anios.join(", ")}, ${total.toLocaleString("es-MX")} artículos)

${lista.map((l) => `- ${l.sigla}, ${NOMBRES[l.sigla] ?? l.nombre}: ${l.articulos.toLocaleString("es-MX")} artículos, última reforma publicada en el DOF el ${l.reforma}, texto descargado el ${l.descarga}.`).join("\n")}
${anexo ? `- Anexo 8 de la Resolución Miscelánea Fiscal ${anexo.anio}: ${anexo.tarifas} tarifas de ISR para pagos provisionales, retenciones y cálculo anual.\n` : ""}
Fuente de los textos: PDF oficiales de la Cámara de Diputados del H. Congreso de la Unión (https://www.diputados.gob.mx/LeyesBiblio/) y, para el Anexo 8, el SAT. No sustituyen al Diario Oficial de la Federación.

## Qué NO incluye

Reglas de la RMF (salvo el Anexo 8), otros anexos de la RMF, jurisprudencia, criterios del SAT, la Ley del Seguro Social ni leyes estatales. Para eso la herramienta responde "no verificado".
${ref ? `
## Reforma ${ref.anio}: proyecto, no ley vigente

${ref.resumen}
Entrada en vigor prevista: ${ref.enVigor ?? "sin fecha"}. Estado al ${ref.actualizado}.
${ref.hitos.map((h) => `- ${h.fecha ?? "pendiente"}: ${HITOS[h.hito] ?? h.hito.replaceAll("_", " ")}${h.confirmado || !h.fecha ? "" : " (sin confirmar en fuente oficial)"}`).join("\n")}
Detalle: ${u("/docs/reforma-2027")}
` : ""}
## Cómo leer un artículo directamente

Cada artículo es un archivo Markdown con encabezado (ley, vigencia, última reforma DOF, fuente, sha256, estatus):
${raw}/leyes/${anio}/<SIGLA>/art-<número con 4 dígitos>[-letra][-bis].md
Ejemplos: ${raw}/leyes/${anio}/LISR/art-0028.md · ${raw}/leyes/${anio}/CFF/art-0017-A.md · ${raw}/leyes/${anio}/CFF/art-0020-bis.md
Índice de cada ley: ${raw}/leyes/${anio}/<SIGLA>/_indice.md

## Cómo usarlo dentro de Abacus

Abacus (${ENLACES.ABACUS}) es el asistente fiscal de TodoConta en WhatsApp. Consulta leyes-mx antes que internet. Es de pago, con prueba de 14 días.

## Páginas del sitio

${PAGINAS.map((p) => `- ${p.titulo} (${u(p.ruta)}): ${p.que}`).join("\n")}

## Contribuir

Sin programar: reportar un error en un artículo o tarifa, proponer un sinónimo contable para el glosario o pedir una ley (${u("/contribuir")}). Los textos legales nunca se editan a mano; se regeneran desde la fuente oficial.
`;
  return new Response(doc, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};
