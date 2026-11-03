# Qué cliente puede usar leyes-mx (y qué no)

Pensado para quien no es técnico (contadores, abogados). Verificado en documentación oficial el 2026-11-03; no se probó en las aplicaciones.

| Cliente | ¿Funciona? | Cómo | Fuente |
|---|---|---|---|
| Claude Desktop (Mac, Windows) | Sí, prioridad 1 | `npx leyes-mx instalar`; hay que reiniciar la app | https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp (Claude Desktop admite servidores locales por `claude_desktop_config.json`) |
| Codex CLI y extensión de IDE | Sí | `npx leyes-mx instalar` escribe `~/.codex/config.toml` | https://learn.chatgpt.com/docs/extend/mcp (`[mcp_servers.<nombre>]`, `command`, `args`) |
| App de escritorio de ChatGPT | Sí, según la documentación | Comparte `~/.codex/config.toml` con Codex: "ChatGPT desktop app, Codex CLI, and IDE extension share this configuration" | la misma página |
| Claude web (claude.ai) | No, por ahora | Solo conecta servidores MCP remotos (URL pública). Los servidores locales de `claude_desktop_config.json` "aren't available in Cowork or claude.ai" | la misma página de soporte de Claude |
| ChatGPT web | No, por ahora | Los conectores MCP personalizados son servidores remotos con URL HTTPS pública (SSE o streaming HTTP); un servidor por stdio en la máquina del usuario no funciona. Existe un "Secure MCP Tunnel" para servidores privados que alcanza un servidor stdio o HTTP, pero requiere ejecutar un cliente del túnel (`tunnel-client`) y administración del espacio de trabajo: no es para el usuario no técnico | https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt y https://developers.openai.com/plugins/deploy/connect-chatgpt |
| Claude Code | Sí | `npx leyes-mx instalar` (más la skill) | https://code.claude.com/docs/en/mcp |
| Cursor | Sí | `npx leyes-mx instalar` | documentación de Cursor |

**Claude web y ChatGPT web quedan fuera por ahora**, porque piden un servidor remoto. Lo habilitaría una futura API o servidor MCP hospedado sobre las mismas funciones (ya está en la hoja de ruta del README); implica operar un servicio y decidir autenticación y costos, y los textos siguen siendo públicos, así que el riesgo de privacidad es bajo.

## Quien no tiene Node: que lo resuelva el asistente

La vía principal para un usuario no técnico no es instalar Node a mano. Es pedirle a su asistente que lo haga, en una app donde el asistente pueda ejecutar comandos (por ejemplo Claude Code o Codex, o una app de escritorio con acceso a la terminal). Basta pegar este mensaje:

```text
Instala leyes-mx ejecutando "npx leyes-mx instalar". Si falta Node 20 o superior, instálalo primero con el método propio de mi sistema y vuelve a intentarlo. Al terminar, dime qué debo reiniciar y cómo comprobar que quedó listo.
```

Node queda como una nota ligera en la web, no como un paso del usuario. Lo que sí hay que tener claro:

- Sin Node el comando no llega a ejecutarse y `leyes-mx` no puede dar un mensaje propio: el intérprete responde que no encuentra `npx` (comprobado en macOS con un PATH sin Node: `zsh:1: command not found: npx`, código 127; en Windows el mensaje típico es "'npx' no se reconoce como un comando interno o externo", no se probó). Por eso el mensaje de arriba le dice al asistente qué hacer cuando eso pasa.
- Esto solo funciona donde el asistente puede ejecutar comandos. Un chat sin acceso a la terminal no puede correr `npx`; para ese caso sirve la extensión de escritorio de abajo.

## Extensión de escritorio (.mcpb) para Claude Desktop: viabilidad

Fuente: https://www.anthropic.com/engineering/desktop-extensions y la especificación https://github.com/anthropics/mcpb (`MANIFEST.md`).

Qué es: un `.mcpb` (antes `.dxt`) es un zip con el servidor MCP local y un `manifest.json`. El usuario hace doble clic, Claude Desktop pregunta "Instalar" y listo; sin terminal, sin editar JSON. **Claude Desktop trae su propio Node** ("We ship Node.js with Claude Desktop, eliminating external dependencies"), así que el usuario no necesita instalar nada. Soporta macOS y Windows.

Viabilidad para leyes-mx: **alta**. El servidor ya es Node puro (solo `@modelcontextprotocol/sdk` y `zod`, sin módulos nativos).

Lo que implica (esfuerzo estimado: 1 a 2 días, y un día más para probarlo en Mac y Windows):

1. `manifest.json` (`mcpb_version`, `name`, `version`, `description`, `author`, `server.type = "node"`, `server.entry_point`, `server.mcp_config.command = "node"` con `args` al entry point, `compatibility.runtimes.node >= 20`, y la lista de herramientas). Se empaqueta con `npx @anthropic-ai/mcpb pack`.
2. Las dependencias deben ir **dentro** del bundle (`node_modules`): hoy son unos 26 MB sin comprimir en el árbol de producción (se podría reducir con un empaquetador tipo esbuild a un solo archivo de pocos MB).
3. Los datos (unos 3 MB): o van dentro del bundle (se actualizan al instalar una versión nueva de la extensión) o el servidor los descarga al primer arranque con `datos.js`, que ya sabe verificar sha256. Lo segundo conserva la actualización sin reinstalar; hay que cuidar el arranque sin internet.
4. Un paso de CI que arme el `.mcpb` y lo adjunte al Release de datos (o a un Release del paquete), con la versión del manifest alineada.
5. Decidir si se firma (el formato lo permite) y si se envía al directorio de extensiones de Claude.

Riesgos: la ruta de datos y el `LEYES_MX_HOME` dentro del entorno de la extensión; la `skill` no viaja en la extensión (sigue siendo carga manual); y dos caminos de instalación que mantener (npx para Claude Code, Codex y Cursor; `.mcpb` para Desktop).

**No se implementó**: es trabajo de empaquetado y de pruebas en la aplicación real que no se pueden hacer desde aquí. Recomendación: es la mejora de mayor valor para el usuario objetivo, y conviene hacerla antes de promocionar la herramienta a contadores sin Node.

## Qué le dice al usuario el instalador

Al terminar `npx leyes-mx instalar` imprime, en español llano: qué quedó (leyes verificadas en el equipo, con qué apps quedó conectado), que hay que **reiniciar Claude Desktop por completo** (cerrarlo del todo y abrirlo; no basta cerrar la ventana), una pregunta de prueba para pegar ("¿Qué dice el artículo 28 de la LISR?") y la señal de que funcionó (la respuesta cita la ley, el artículo y la vigencia, y la app muestra que usó `leyes-mx`). `npx leyes-mx doctor` cierra con un "Resumen" de una línea: `Claude Desktop: LISTO` o `Claude Desktop: NO está listo (motivo)`.
