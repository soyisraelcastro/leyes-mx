# leyes-mx (paquete npm)

Leyes y reglamentos fiscales y laborales de México, en tu equipo, para tu asistente. Un servidor MCP (Claude Desktop, Claude Code, Codex, Cursor y cualquier cliente que hable MCP por stdio) y una consulta directa por terminal.

El paquete lleva solo código. Los textos se descargan aparte (unos 3 MB) desde un Release de GitHub, se verifican con sha256 y quedan en `~/.leyes-mx/`. Una vez instalados se consultan sin conexión.

## Uso

```bash
npx leyes-mx instalar                          # descarga los datos y registra el servidor en los clientes que detecte
npx leyes-mx instalar --cliente claude-code    # o elige: claude-desktop | claude-code | codex | cursor | todos
npx leyes-mx instalar --dry-run                # muestra qué escribiría, sin escribir
npx leyes-mx actualizar                        # trae la última versión de los datos
npx leyes-mx estado                            # versión instalada vs la última publicada, reforma por ley
npx leyes-mx doctor                            # diagnóstico
npx leyes-mx desinstalar                       # quita solo lo que puso este paquete

npx leyes-mx obtener LISR 28                   # consulta directa, sin MCP
npx leyes-mx buscar "recargos deducibles" --ley LISR
```

Requiere Node 20 o superior. Opciones de `instalar`: `--anio 2026` (año por defecto), `--instrucciones` (agrega un bloque a CLAUDE.md / AGENTS.md, con confirmación o `--si`), `--ruta-absoluta` (escribe la ruta completa de npx), `--sin-binario` (no usa `claude mcp add`), `--sin-datos`.

## Herramientas MCP

| Herramienta | Qué hace |
|---|---|
| `obtener_articulo(ley, articulo, anio?, pagina?)` | Texto íntegro con ley, artículo, año de vigencia, última reforma DOF, estatus y advertencias. |
| `buscar(consulta, ley?, anio?, incluir_proyectos?, limite?)` | Búsqueda por palabras clave. Por defecto excluye proyectos. |
| `listar_leyes(anio?)` | Qué hay en la base. |
| `estado_reforma(anio?)` | Seguimiento de la reforma en trámite y última reforma por ley. |
| `obtener_transitorios(ley, anio?, pagina?)` | Transitorios por decreto. |
| `obtener_tarifa(tarifa?, anio?)` | Tarifas de ISR vigentes del Anexo 8 de la RMF (mensual `B-V`, anual `C-II`, por 7/10/15 días, bimestrales...). Sin parámetro, las lista. Son las que se aplican en el ejercicio; las tablas de los arts. 96 y 152 de la LISR son las de la ley. |

Si no existe lo pedido, la respuesta dice "NO VERIFICADO" y no se inventa texto. Un proyecto de reforma nunca se presenta como ley vigente. Los textos muy extensos (por ejemplo el artículo 513 de la LFT) se entregan por páginas de hasta 40 000 caracteres, con aviso y parámetro `pagina`.

## Variables de entorno

- `LEYES_MX_HOME`: carpeta de datos (por defecto `~/.leyes-mx`, o `%LOCALAPPDATA%\leyes-mx` en Windows).
- `LEYES_MX_DATOS`: usar una carpeta de datos concreta, por ejemplo una copia del repositorio, sin descargar nada.
- `LEYES_MX_MANIFEST`: URL o ruta de otro `manifest.json`.

## Aviso

Los textos son informativos y se copian de la Cámara de Diputados; no sustituyen al Diario Oficial de la Federación. La fuente oficial prevalece. No es asesoría legal ni fiscal.

Repositorio, datos y cómo contribuir: https://github.com/soyisraelcastro/leyes-mx. Licencia MIT.
