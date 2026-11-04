// /llms.txt: índice corto para LLMs (formato llmstxt.org, mismo patrón que todoconta.com y soycontador.ai).
// Las cifras salen de los datos del repo en el build; nada se copia a mano.
import type { APIRoute } from "astro";
import { RESUMEN, PAGINAS, NOMBRES, cifras, ENLACES } from "../lib/seo.mjs";

export const GET: APIRoute = ({ site }) => {
  const u = (p: string) => new URL(p, site).toString();
  const { lista, total, anios, anexo, ref } = cifras();
  const doc = `# leyes-mx

> ${RESUMEN}

Idioma: español de México. Gratis, sin cuenta. Lo publica TodoConta (${ENLACES.TODOCONTA}).
Instalación: \`${ENLACES.COMANDO}\` (requiere Node.js 20 o superior; se ejecuta en la computadora, no en un chat en la nube).

## Páginas

${PAGINAS.map((p) => `- [${p.titulo}](${u(p.ruta)}): ${p.que}`).join("\n")}

## Qué incluye (vigencia ${anios.join(", ")}, ${total.toLocaleString("es-MX")} artículos)

${lista.map((l) => `- ${l.sigla}: ${NOMBRES[l.sigla] ?? l.nombre}, ${l.articulos.toLocaleString("es-MX")} artículos, última reforma DOF ${l.reforma}`).join("\n")}
${anexo ? `- Anexo 8 de la RMF ${anexo.anio}: ${anexo.tarifas} tarifas de ISR (pagos provisionales, retenciones y cálculo anual)\n` : ""}${ref ? `- Reforma ${ref.anio}: proyecto, no es ley vigente (estado al ${ref.actualizado}); va aparte y rotulado\n` : ""}
## Código y datos

- [Repositorio en GitHub](${ENLACES.REPO}): código, datos en Markdown (un archivo por artículo) y reglas para contribuir
- [Paquete npm](https://www.npmjs.com/package/leyes-mx): CLI y servidor MCP
- [Abacus](${ENLACES.ABACUS}): asistente fiscal de TodoConta en WhatsApp que consulta leyes-mx primero (de pago)

## Contenido completo

- [llms-full.txt](${u("/llms-full.txt")}): qué es, cómo se instala, herramientas MCP, cómo citar, límites, estado de la reforma y cómo leer cada artículo en texto plano
`;
  return new Response(doc, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};
