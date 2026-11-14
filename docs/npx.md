# Instalador npx (`leyes-mx`)

Cómo funciona el paquete npm, cómo se actualizan los datos y qué le toca a quien mantiene el proyecto.

## Piezas

```
npm/                         paquete npm "leyes-mx" (solo código, ESM, Node >= 20)
  bin/leyes-mx.js            punto de entrada
  src/                       ids, almacén, índice de búsqueda, glosario, servidor MCP, datos, clientes, skill, CLI
  skills/leyes-mx/SKILL.md   la skill (viaja en el paquete)
  test/                      pruebas (node --test); consultas.json: preguntas reales y artículos esperados
scripts/empaquetar_datos.py  construye leyes-mx-datos.tar.gz + manifest.json (determinista; materializa las capas, --sin-materializar para no hacerlo)
.github/workflows/publicar-datos.yml   publica el Release de datos
sitio/                       landing en Astro (Vercel)
```

El paquete npm **no lleva datos**: `npm pack --dry-run` lista 18 archivos (código, la skill, README y LICENSE; ~42 kB). Los datos viajan por un Release de GitHub, de modo que una reforma nueva no obliga a publicar otra versión del paquete.

## Datos y versiones

Cada Release `datos-AAAA.MM.DD` (con sufijo `.2`, `.3` si hay más de uno el mismo día) adjunta:

- `leyes-mx-datos.tar.gz`: `leyes/`, `proyectos/` sin PDF, `tablas/` (con imágenes), `rmf/`, `fuentes.json`, `glosario.json` e `INTEGRIDAD.json` (sha256 de cada archivo y hash del contenido). El tarball es determinista: mismo contenido, mismos bytes, mismo sha256.
- `manifest.json`: `version`, `publicado`, `contenido_sha256`, `tarball` (nombre, sha256, bytes), `anios`, `glosario` (versión, entradas y sha256) y por ley sigla, año, última reforma DOF y número de artículos.

La CLI consulta `https://github.com/soyisraelcastro/leyes-mx/releases/latest/download/manifest.json` (una URL de descarga, sin la API de GitHub y sin su límite de peticiones), compara la versión y baja el tarball que el manifest nombra, relativo a la misma URL.

En el equipo del usuario:

```
~/.leyes-mx/                 (LEYES_MX_HOME; en Windows %LOCALAPPDATA%\leyes-mx)
  datos/<version>/           datos descomprimidos + manifest.json
  actual                     archivo de texto con la versión activa
  anterior                   versión previa, para "npx leyes-mx revertir"
  config.json                {"anio": 2026} si se usó --anio
```

Activación atómica: se verifica el sha256 del tarball, se extrae a `datos/.tmp-*`, se verifica cada archivo contra `INTEGRIDAD.json`, se renombra la carpeta y al final se reescribe `actual` (archivo temporal + rename). Si algo falla no queda nada activo ni a medias. Se usa un archivo `actual` en lugar de un symlink para que funcione igual en Windows. Solo se conservan la versión actual y la anterior.

Varios años: el servidor lee `leyes/<año>/` de todos los años presentes (si un año es una capa, resuelve la herencia; el Release materializa por omisión cada año completo, ver [criterio-anios.md](criterio-anios.md)). Por defecto usa el más reciente que no sea posterior al año en curso (o el de `--anio`). Cuando exista `leyes/2027/`, el servidor lo usará solo a partir de 2027 y `anio=2026` seguirá disponible.

Modo "desde este repo", sin Release: `LEYES_MX_DATOS=/ruta/al/repo npx leyes-mx doctor`. Para probar una actualización local: `python3 scripts/empaquetar_datos.py --salida /tmp/pub --version 2026.12.01` y `LEYES_MX_MANIFEST=/tmp/pub/manifest.json npx leyes-mx actualizar`.

## Servidor MCP

Node, sin Python ni módulos nativos. Usa `@modelcontextprotocol/sdk` (1.x) y `zod`. La búsqueda es un índice invertido en memoria con BM25 (se arma en unos 300 ms al primer uso); no se usa minisearch porque son ~2500 documentos y así no hay otra dependencia. Antes de puntuar, la consulta pierde las palabras vacías, reduce plurales a su raíz y se amplía con el glosario de sinónimos ([glosario.md](glosario.md)); la respuesta declara la ampliación. Las instrucciones del servidor y las descripciones de las herramientas están escritas para que el modelo consulte la base antes de responder cualquier consulta fiscal o laboral, y el resultado "no encontrado" manda preguntar al usuario antes de buscar en internet. La normalización de artículos es un port de `leyes_mx/ids.py` con las mismas pruebas de paridad. Detalle de las herramientas en [npm/README.md](../npm/README.md).

## Qué escribe `instalar` en cada cliente

| Cliente | Archivo | Forma |
|---|---|---|
| Claude Desktop | macOS `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows `%APPDATA%\Claude\claude_desktop_config.json`; Linux `~/.config/Claude/claude_desktop_config.json` | `mcpServers["leyes-mx"]` = `{command, args, env}`. Respaldo previo del archivo. Hay que cerrar y reabrir la app. |
| Claude Code | `~/.claude.json` (o `$CLAUDE_CONFIG_DIR/.claude.json`), alcance de usuario | Con el binario: `claude mcp add --transport stdio --scope user leyes-mx -- npx -y leyes-mx servir`. Sin el binario (o con `--sin-binario`): `mcpServers["leyes-mx"]` = `{type: "stdio", command, args, env}`. |
| Codex | `~/.codex/config.toml` (o `$CODEX_HOME`) | Bloque delimitado por comentarios con la tabla `[mcp_servers.leyes-mx]` (`command`, `args`, `startup_timeout_sec = 60`). |
| Cursor | `~/.cursor/mcp.json` | `mcpServers["leyes-mx"]` = `{command, args}`. |
| Otro | (ninguno) | `instalar` imprime el bloque JSON genérico cuando no detecta ningún cliente. |

Siempre idempotente (si ya está igual, "sin cambios", sin respaldos nuevos), con `--dry-run` que muestra lo que escribiría, y `desinstalar` solo quita entradas llamadas `leyes-mx` cuyos argumentos son los de este paquete. Si ya existe una entrada `leyes-mx` ajena, no se toca. Un JSON inválido no se sobrescribe.

**Skill**: además del registro, `instalar` copia la skill `leyes-mx` donde el cliente la lee (Claude Code `~/.claude/skills/`, Codex `~/.agents/skills/`), con la misma disciplina: marca propia, respaldo (en `~/.leyes-mx/respaldos/`, fuera de la carpeta de skills), idempotencia y `--dry-run`. Claude Desktop no tiene carpeta documentada: `npx leyes-mx skill --zip`. Ver [skill.md](skill.md).

`--instrucciones` agrega un bloque (entre `<!-- leyes-mx:inicio -->` y `<!-- leyes-mx:fin -->`) a `~/.claude/CLAUDE.md` y `~/.codex/AGENTS.md`, solo con esa bandera y con confirmación (`--si` para no preguntar). `desinstalar` lo quita.

### PATH de npx en las apps de escritorio

Claude Desktop y Cursor se lanzan desde el sistema, no desde una terminal, y heredan un PATH reducido: no ven `npx` si Node está en una ruta de usuario (nvm, fnm, Volta) ni, en macOS, en `/opt/homebrew/bin`. Para esos dos clientes `instalar` escribe la ruta absoluta de `npx` y un `env.PATH` con su carpeta (en Windows deja `npx`, que es lo que documenta Claude Desktop). El costo: si cambias de versión de Node con nvm, hay que repetir `npx leyes-mx instalar`. `npx leyes-mx doctor` avisa. Claude Code y Codex arrancan desde la terminal y usan `npx` a secas.

## Agregar otro cliente

1. En `npm/src/clientes.js`: añadirlo a `CLIENTES`, a `rutaConfig`, a `detectar`, y decidir si es de escritorio (`GUI`, para ruta absoluta de npx).
2. Si su config es JSON con `mcpServers`, `instalarJson`/`desinstalarJson` ya lo cubren; si no, escribir su par `instalar*`/`desinstalar*` como el de Codex.
3. Añadirlo a `instalarCliente`, `desinstalarCliente` y `estadoCliente`.
4. Pruebas en `npm/test/e2e.test.js` (archivo de config falso en un HOME temporal) y, si aplica, una pestaña en `sitio/src/pages/index.astro`.
5. Verificar la sintaxis en la documentación oficial del cliente y anotar la fuente aquí.

Skills por cliente, fuentes y lo no verificado: [skill.md](skill.md). Qué cliente sí y cuál no: [clientes.md](clientes.md).

Fuentes consultadas el 2026-11-02: modelcontextprotocol.io (conectar servidores locales: rutas y JSON de Claude Desktop), code.claude.com/docs/en/mcp (`claude mcp add`, alcance de usuario, `~/.claude.json`), la documentación de Codex sobre MCP (`[mcp_servers.<nombre>]`, `codex mcp add`), cursor.com/docs (`~/.cursor/mcp.json`). No confirmado en documentación: la ruta de Linux de Claude Desktop viene de la guía de MCP, no de la app; y la variable `CODEX_HOME` no aparece en la página de MCP de Codex.

## Publicar datos (Release)

Lo hace `.github/workflows/publicar-datos.yml` en cada push a `main` que toque `leyes/**`, `proyectos/**` o `tablas/**`, y a mano (`workflow_dispatch`, con opción de forzar). Valida el árbol, calcula la versión, construye con `scripts/empaquetar_datos.py`, compara `contenido_sha256` con el del último Release (si es igual, no publica otro) y crea el Release marcado como latest con los dos archivos. El primer Release hay que dispararlo a mano (ver pasos abajo), porque hasta que exista ninguno la URL `releases/latest/download/manifest.json` da 404.

## Publicar el paquete npm (quien mantiene)

1. Revisar y probar: `cd npm && npm ci && npm test` (con el repo completo; la prueba de paridad corre `scripts/buscar.py` 2513 veces, tarda ~35 s) y `npm pack --dry-run` (solo `bin/`, `src/`, README, LICENSE, package.json).
2. Subir la versión en `npm/package.json` (semver). Cambia el comportamiento del servidor o de los clientes, no los datos.
3. `npm login` (cuenta con acceso al nombre `leyes-mx`; si la cuenta tiene 2FA, tener a mano el código).
4. `cd npm && npm publish --access public` (para paquetes sin scope `--access public` no hace falta, pero no estorba).
5. Probar desde cero en otra carpeta o equipo: `npx leyes-mx@latest doctor`.
6. Etiquetar en git (`git tag npm-v0.1.0`) si se quiere llevar el registro.

Una reforma nueva de las leyes no requiere publicar el paquete: basta el Release de datos, y los usuarios corren `npx leyes-mx actualizar`.

## Landing (`sitio/`) en Vercel

Proyecto Astro estático e independiente (`sitio/package.json`), sin adaptador: un sitio 100 % estático no necesita `@astrojs/vercel` (lo confirma la guía de Astro para Vercel). Vive en la raíz del dominio, sin `base`. La lista de leyes y el estado de la reforma salen en el build de `leyes/*/*/_meta.json`, `fuentes.json` y `proyectos/*/estado.json`, así que el build necesita ver el repo completo (en Vercel, "Include source files outside of the Root Directory" viene activado por defecto).

La URL pública es una sola variable: `SITE_URL` (en `sitio/astro.config.mjs` hay un valor por defecto provisional, `https://leyes-mx.example.com`). Solo se usa para canonical y og:url.

Pasos para desplegar (los hace quien mantiene; el proyecto de Vercel no está creado ni conectado):

1. En el dashboard de Vercel: Add New, Project, importar `soyisraelcastro/leyes-mx`. (O con la CLI, desde la raíz del repo: `vercel link` y elegir el repo.)
2. Root Directory: `sitio`. Framework Preset: Astro. Build Command: `npm run build`. Output Directory: `dist`. Install Command: `npm install`. Node 22 o superior.
3. Variable de entorno `SITE_URL` con la URL final (en Production y Preview), si ya se conoce.
4. Deploy. `sitio/vercel.json` añade cabeceras de seguridad y caché largo para `/_astro/*` (archivos con hash).
5. Dominio propio después: Project, Settings, Domains, Add. Configurar el DNS que indique Vercel, actualizar `SITE_URL` con ese dominio y volver a desplegar.

Probar en local: `cd sitio && npm install && npm run build && npm run preview`.

## Pruebas

`cd npm && npm test`:

- `ids.test.js`: más de 30 variantes de ids contra `leyes_mx.ids` de Python, ids y nombres de archivo.
- `paridad.test.js`: los 2513 artículos de `leyes/2026` contra el archivo y contra `python3 scripts/buscar.py obtener ... --json`.
- `mcp.test.js`: servidor real por stdio con el cliente del SDK (initialize, tools/list, las seis herramientas, inexistente con la indicación de preguntar antes de ir a internet, derogado, LFT 513 paginado, proyectos, glosario, textos para el modelo).
- `consultas.test.js` y `consultas.json`: preguntas reales (con la frase de la ley que las respalda) y los artículos que deben quedar en el top N, con y sin glosario.
- `glosario.test.js`: estructura, evidencia literal contra el texto de cada artículo citado, funcionamiento sin glosario y actualización del glosario por `actualizar`.
- `skill.test.js`: formato de la skill, `npm pack`, instalación por cliente, respaldo, ajena, desinstalación, `.zip` y mensajes del instalador.
- `e2e.test.js`: HOME temporal con configs falsas: dry-run, instalar en los cuatro clientes sin pisar nada, idempotencia, instrucciones, estado, doctor, actualizar con versión nueva, tarball alterado rechazado (dos formas), revertir, desinstalar.
- `sitio.test.js` (requiere `sitio/dist`): los comandos de la landing existen y coinciden con los del instalador.

## Riesgos conocidos

- PATH de npx en apps de escritorio (arriba).
- Primer arranque en frío: `npx -y leyes-mx servir` descarga el paquete y sus dependencias la primera vez; Claude Desktop puede tardar en mostrar el servidor. Codex tiene `startup_timeout_sec = 10` por defecto; el instalador lo sube a 60.
- Límites de salida de los clientes MCP: por eso las respuestas se paginan a 40 000 caracteres.
- Tamaño: tarball de ~3 MB; el índice de búsqueda ocupa memoria del proceso (unas decenas de MB).
- El paquete depende de `@modelcontextprotocol/sdk` (trae varias dependencias transitivas, entre ellas un servidor HTTP que este servidor no usa).
