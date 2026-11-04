// robots.txt: todos bienvenidos, incluidos los crawlers de IA (mismo patrón que todoconta.com).
import type { APIRoute } from "astro";

const BOTS_IA = ["GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-Web", "Claude-User", "Claude-SearchBot", "anthropic-ai",
  "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "CCBot", "meta-externalagent", "DuckAssistBot", "MistralAI-User"];

export const GET: APIRoute = ({ site }) => {
  const u = (p: string) => new URL(p, site).toString();
  const txt = `# leyes-mx: todos bienvenidos, incluidos los crawlers de IA.
# Índice para LLMs: ${u("/llms.txt")}
# Contenido completo en texto plano: ${u("/llms-full.txt")}

User-agent: *
Allow: /

# Crawlers de IA: mismas reglas, explícitas.
${BOTS_IA.map((b) => `User-agent: ${b}`).join("\n")}
Allow: /

Sitemap: ${u("/sitemap.xml")}
`;
  return new Response(txt, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
};
