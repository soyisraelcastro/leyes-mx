# Arquitectura y diseño para una futura API / MCP

## Capas

```
leyes/<año>/<SIGLA>/art-*.md   fuente de verdad (git)
proyectos/<año>/<SIGLA>/       proyectos, jamás mezclados con leyes/
        |
leyes_mx/store.py              biblioteca importable (sin dependencias)
        |
leyes_mx/cli.py                CLI (leyes-mx / scripts/buscar.py)
        |
npm/ (leyes-mx)                servidor MCP en Node (ya existe), mismo contrato; ver docs/npx.md
(futuro) API HTTP              envuelve las mismas funciones
build/indice.sqlite            índice FTS5, se regenera solo; ignorado por git
```

El árbol de archivos es el almacén. No hay base de datos que mantener: el índice de búsqueda es descartable.

## Contrato de la biblioteca (`leyes_mx`)

Todas las funciones son síncronas, puras respecto del árbol de archivos y devuelven diccionarios JSON-serializables.

### `obtener_articulo(ley, articulo, anio=None, incluir_proyectos=False) -> dict | None`

- `ley`: sigla ("LISR"), sin distinguir mayúsculas.
- `articulo`: cualquier forma normalizable ("113 E", "113-e", "28 bis").
- `anio`: año de vigencia; por omisión, el más reciente con datos que no sea posterior al año en curso.
- Devuelve `None` si no existe (nunca inventa texto). Con valor `ValueError` si el artículo no es reconocible.
- Campos: `ley`, `nombre_ley`, `articulo`, `anio_vigencia`, `ultima_reforma_dof`, `estatus` ("vigente" | "derogado" | "proyecto"), `fuente_url`, `fecha_descarga`, `texto`, `ruta`, `notas_reforma` (lista), `advertencias` (lista; p. ej. la gradualidad de la jornada laboral).
- Si `estatus` es "proyecto" (solo con `incluir_proyectos=True`): además `aviso`, `estado_proyecto` y `entrada_en_vigor`.

### `buscar(texto, ley=None, anio=None, incluir_proyectos=False, limite=10) -> list[dict]`

- Palabras clave, sin acentos, prefijos, ranking BM25 (SQLite FTS5). Primero exige todas las palabras (AND); si no hay resultados, acepta cualquiera (OR).
- Cada resultado: `ley`, `articulo`, `anio_vigencia`, `ultima_reforma_dof`, `estatus`, `fragmento`, `ruta`; y `aviso` si es proyecto.
- Por omisión **excluye** todo lo que no sea "vigente"/"derogado".
- Es búsqueda léxica: para citar un artículo conocido usar `obtener_articulo`.

### `listar_leyes(incluir_proyectos=False) -> list[dict]`

Una fila por ley y año: `sigla`, `nombre`, `anio_vigencia`, `ultima_reforma_dof`, `articulos`, `estatus`, `fecha_descarga`.

### `estado_reforma(anio=2027) -> dict`

Lee `proyectos/<año>/estado.json`: resumen, línea de tiempo con `confirmado` y `nivel` (oficial, prensa, pendiente) y fuente de cada hito; siempre trae `es_ley_vigente: false` mientras no se publique.

### `listar_anexo(anexo=8, anio=None) -> list[dict]` y `obtener_anexo(anexo, tarifa, anio=None) -> dict | None`

Anexo 8 de la RMF (`rmf/<año>/anexo-8/`). Solo existe el anexo 8 (otro número da `ValueError`).

- `listar_anexo`: una fila por tarifa (en el orden del PDF): `id`, `apartado`, `titulo`, `documento`, `anio_vigencia`, `publicado_dof`, `fuente_url`, `filas`, `ruta`. Lista vacía si no hay anexo.
- `obtener_anexo(8, "B-V")`: `tarifa` es un id exacto (`B-V-tarifa-mensual-2026`) o un apartado (`B-V`, `B.V`, `C-II`). Devuelve `documento`, `apartado`, `id`, `titulo`, `aplicable_a`, `vigencia_anio`, `publicado_dof`, `fecha_firma`, `fuente_url`, `fecha_descarga`, `sha256_fuente`, `estatus`, `columnas`, `filas` (lista de 4 cadenas tal cual el PDF), `texto`, `ruta`, `aviso`. `None` si no existe (nunca inventa). Si el apartado tiene varias tarifas (B.VI, B.VIII) devuelve `{"ambiguo": [{"id", "titulo"}, ...]}`.
- CLI: `obtener-anexo 8 [tarifa] [--anio N] [--json]`; sin tarifa lista. Código de salida 0 ok, 1 no verificado, 2 clave ambigua o anexo no soportado.
- Recurso futuro: `/v1/rmf/{año}/anexo-8/{tarifa}`.

### `normalizar_articulo(texto) -> str | None`

Identificador canónico ("113-E", "28-bis").

## Herramientas MCP

Implementadas en `npm/` (Node, sin Python), con la misma lógica de ids y los mismos campos; ver [npx.md](npx.md). Además de las cuatro de abajo hay `obtener_transitorios` y `obtener_tarifa` (tarifas de ISR del Anexo 8 de la RMF; en el CLI, `npx leyes-mx tarifa B-V`), y `obtener_articulo`/`obtener_transitorios` admiten `pagina` para textos muy extensos. `buscar` acepta `incluir_proyectos` como parámetro explícito y marca todo proyecto. Tabla original de diseño:

| Herramienta | Mapea a | Notas |
|---|---|---|
| `obtener_articulo(ley, articulo, anio?)` | `obtener_articulo` | Respuesta incluye ley, artículo, año, fecha de última reforma y el aviso de que la fuente oficial prevalece. |
| `buscar(consulta, ley?, anio?, limite?)` | `buscar` | Sin proyectos. |
| `listar_leyes()` | `listar_leyes` | Para que el agente sepa qué cubre la base. |
| `estado_reforma(anio?)` | `estado_reforma` | El agente debe consultarlo antes de afirmar algo sobre 2027. |

`incluir_proyectos` **no** se expone en la herramienta por defecto; si se expone, debe ser un parámetro explícito y la respuesta debe llevar el aviso en el cuerpo del texto, no solo en un campo.

## Versionado por año

- El año es parte de la dirección del recurso: `leyes/2026/LISR/art-0028.md`. Una API lo expondría como `/v1/leyes/{año}/{sigla}/{articulo}`.
- `leyes/<año>/` se congela al publicarse la reforma del año siguiente; se corrige solo un error de extracción.
- El estado de la reforma es un recurso aparte (`/v1/reformas/{año}`), no se mezcla con los artículos.
- Cada respuesta debe poder reconstruirse con (`ley`, `articulo`, `anio_vigencia`, `sha256_fuente`).

## Reglas duras

1. Nada con estatus distinto de "vigente"/"derogado" vive en `leyes/` (lo verifica `scripts/validar.py` y el CI).
2. Un proyecto jamás se presenta como vigente; el buscador lo excluye por omisión y lo marca.
3. Si no está en la base, se responde "no verificado"; nunca se completa de memoria.
