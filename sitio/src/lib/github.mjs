// Estrellas del repo, leídas una vez por build desde la API pública de GitHub.
// Se calcula en el build (no en el navegador) para no abrir la CSP a api.github.com; se actualiza en cada deploy.
// Si la API falla o tarda, devuelve null y el menú muestra solo "GitHub".
import { REPO } from "./constantes.mjs";

let cache;
export function estrellas() {
  cache ??= (async () => {
    try {
      const api = REPO.replace("https://github.com/", "https://api.github.com/repos/");
      const headers = { Accept: "application/vnd.github+json", "User-Agent": "leyes-mx-sitio" };
      if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
      const r = await fetch(api, { headers, signal: AbortSignal.timeout(4000) });
      if (!r.ok) return null;
      const n = (await r.json()).stargazers_count;
      return Number.isInteger(n) ? n : null;
    } catch {
      return null;
    }
  })();
  return cache;
}
