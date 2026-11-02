import { defineConfig } from "astro/config";

// URL pública del sitio. PROVISIONAL: todavía no existe el proyecto ni el dominio.
// Se cambia en un solo lugar: variable de entorno SITE_URL (por ejemplo en Vercel) o este valor por defecto.
// Solo se usa para canonical y og:url.
const SITE_URL = process.env.SITE_URL || "https://leyes-mx.example.com";

// Sitio 100% estático, en la raíz del dominio (Vercel): sin "base" y sin adaptador.
export default defineConfig({
  site: SITE_URL,
  output: "static",
  trailingSlash: "ignore",
  devToolbar: { enabled: false },
});
