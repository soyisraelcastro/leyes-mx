# Skill `leyes-mx`

Una skill (formato [Agent Skills](https://agentskills.io/specification): una carpeta con `SKILL.md`) que le enseña al asistente el método de trabajo con la base: reformular con las palabras de la ley, buscar, leer el artículo completo, citar con ley, artículo, fracción, vigencia y última reforma, y no presentar nunca el proyecto de 2027 como ley vigente. Si algo no está en la base, manda **preguntar al usuario** si quiere buscarlo en internet (nunca buscar por cuenta propia) y, si lo autoriza, usar solo fuentes oficiales.

La skill es un **complemento**. Lo principal es el servidor MCP: sus `instructions` y las descripciones de las herramientas ya llevan la misma regla, y el resultado de las herramientas repite la indicación de "no encontrado". La skill se carga sola cuando la pregunta es fiscal o laboral de México y se invoca a mano como `/leyes-mx`.

Vive en `npm/skills/leyes-mx/SKILL.md` y viaja dentro del paquete npm (`files` de `npm/package.json`; `npm pack --dry-run` la lista).

## Cómo se instala

| Cliente | Ruta | Cómo |
|---|---|---|
| Claude Code | `~/.claude/skills/leyes-mx/SKILL.md` (con `CLAUDE_CONFIG_DIR`, esa carpeta) | `npx leyes-mx instalar` la copia |
| Codex (CLI, extensión de IDE y app de ChatGPT de escritorio) | `~/.agents/skills/leyes-mx/SKILL.md` | `npx leyes-mx instalar` la copia |
| Claude Desktop | no hay carpeta documentada | carga manual de un `.zip`: `npx leyes-mx skill --zip` |
| Claude web (claude.ai) | no hay carpeta | el mismo `.zip`, desde Personalizar > Skills |

- `instalar` copia la skill en Claude Code y Codex (`--sin-skill` la omite; `--dry-run` muestra qué haría). Es idempotente.
- `actualizar` la refresca donde este paquete ya la había puesto (no la agrega donde no estaba). Corre con el paquete npm que trae la versión nueva, por ejemplo `npx leyes-mx@latest actualizar`.
- `desinstalar` la quita. `doctor` la verifica (formato, estado por cliente) y `estado` la reporta. `revertir` solo vuelve los datos a la versión anterior, no toca la skill.
- Solo se toca lo propio: la carpeta lleva una marca `.leyes-mx-skill.json` con la huella del contenido. Si ya hay una carpeta `leyes-mx` sin esa marca, se omite y se avisa. Si la skill instalada se editó a mano o quedó vieja, `actualizar` la restaura **después de respaldarla** en `~/.leyes-mx/respaldos/` (fuera de la carpeta de skills: un respaldo dentro se cargaría como una segunda skill con el mismo nombre).
- `npx leyes-mx skill` muestra el estado por cliente. `npx leyes-mx skill --zip [--salida CARPETA]` escribe `leyes-mx-skill.zip` (por omisión en el directorio actual) con la carpeta `leyes-mx/` en la raíz, listo para cargar, y imprime los pasos.

### Cargar el .zip en Claude Desktop o Claude web

1. Abre Claude y entra a **Personalizar (Customize) > Skills**. En algunas versiones el menú es **Configuración > Capacidades** (la documentación de Anthropic usa los dos nombres según la fecha).
2. Pulsa **+**, elige **Subir una skill (Upload a skill)** y selecciona el `.zip`.
3. Activa `leyes-mx` en la lista.

La ejecución de código debe estar activada (Configuración > Capacidades) y en planes Team y Enterprise el administrador debe permitir skills. En Claude Desktop **es opcional**: el servidor MCP funciona sin ella.

## Fuentes y qué se verificó

Consultadas el 2026-11-02 y 2026-11-03:

- **Claude Code**: https://code.claude.com/docs/en/skills. Rutas `~/.claude/skills/<nombre>/SKILL.md` (personal) y `.claude/skills/<nombre>/SKILL.md` (proyecto); `name` y `description` en el front matter; invocación con `/<nombre>`; carga automática por la descripción (`description` y `when_to_use` juntos se truncan a 1,536 caracteres). Los campos `name`, `description`, `license`, `compatibility`, `metadata` y `allowed-tools` son los de la especificación; otros campos dan error al empaquetar para claude.ai.
- **Codex**: https://developers.openai.com/codex/skills (redirige a https://learn.chatgpt.com/docs/build-skills). Ruta de usuario `$HOME/.agents/skills`; `name` y `description` obligatorios; invocación con `/skills` o `$nombre`. Contraste con el código fuente de Codex (`codex-rs/ext/skills/src/host_roots.rs`, vía Context7): para el nivel usuario carga `~/.agents/skills` y también `$CODEX_HOME/skills`, que marca como ruta antigua "deprecated". Por eso se instala en `~/.agents/skills`.
- **Claude Desktop / claude.ai**: https://support.claude.com/en/articles/12512180-use-skills-in-claude (pasos Customize > Skills > + > Upload a skill, ZIP con la carpeta de la skill; el artículo no menciona ninguna carpeta local de skills en Claude Desktop) y https://support.claude.com/en/articles/12512198-how-to-create-custom-skills (el ZIP lleva la carpeta de la skill en la raíz, la carpeta se llama igual que la skill, nombre de hasta 64 caracteres y descripción de hasta 200).
- **Formato**: https://agentskills.io/specification (`name` en minúsculas, números y guiones, igual al nombre de la carpeta; descripción de hasta 1024 caracteres, pero claude.ai pide 200: se respeta el límite menor).

### Lo que NO se pudo verificar

- **Claude Desktop con una carpeta de archivos.** Ninguna fuente oficial documenta una carpeta local de skills en Claude Desktop; solo la carga del `.zip`. Si existe, no está documentada, y no se escribe en rutas no documentadas.
- **Los nombres exactos de los menús de la app** (Personalizar / Customize / Configuración > Capacidades): la documentación los llama de dos maneras. No se abrió la aplicación.
- **El tamaño máximo del .zip**: el artículo de soporte lo menciona sin dar la cifra. El `.zip` de esta skill pesa unos 3 kB.
- **`CLAUDE_CONFIG_DIR` y la carpeta de skills**: el instalador usa esa variable también para las skills de Claude Code (igual que para `CLAUDE.md`), pero la página de skills que se leyó no la menciona. Si el cliente no la respeta, la skill queda en la carpeta indicada y no se carga.
- **Cursor**: no se verificó si carga skills de esta forma ni en qué ruta; no se instala ahí.
- **Que cada cliente la cargue sola.** Se verificaron rutas y formato en documentación, no el comportamiento del modelo dentro de cada app.
