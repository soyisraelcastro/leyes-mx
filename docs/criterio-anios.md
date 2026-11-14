# Criterio de años de vigencia y versiones por capas

`<año>` en `leyes/<año>/` es el **año de vigencia** del texto (el año en que ese texto aplica), no la fecha de descarga. La fecha de descarga va en cada archivo (`fecha_descarga`).

## El modelo: capas que heredan

Un año no es una copia de la ley: es una **capa**.

- `leyes/2026/` es la **base**. Está completa (cada ley, todos sus artículos) y no lleva marcas de herencia. No se toca al llegar un año nuevo.
- `leyes/<año>/<SIGLA>/` de un año posterior guarda **solo los artículos que cambian** respecto de la capa que hereda: los modificados, los nuevos y los que pasan a derogado (un derogado es un archivo `art-XXXX.md` con `estatus: "derogado"`, nunca una ausencia). El resto no se copia.
- La capa lleva un `_meta.json` con los campos de siempre (sigla, nombre, fuente, `ultima_reforma_dof`, `fecha_descarga`, `sha256_pdf`...) y además:

| Campo | Qué es |
|---|---|
| `hereda_de` | año de la capa que hereda (p. ej. `2026`) |
| `vigente_desde` | fecha ISO desde la que rige la capa (p. ej. `"2027-01-01"`) |
| `articulos_modificados` | ids de los archivos de la capa (modificados, nuevos y derogados); debe coincidir con los archivos |
| `articulos_nuevos` | subconjunto de los anteriores que no existían en la capa heredada (p. ej. `78-G`) |
| `fuente` | de dónde sale: `decreto` (DOF), `nota` y `fecha_dof` |
| `articulos_extraidos` | total de artículos de la **vista** completa de ese año, no del delta |

- `vigente_hasta` **no se guarda**: se deriva. Es el `vigente_desde` de la capa siguiente que contiene ese artículo (`versiones.vigente_hasta()`).
- `_indice.md` se regenera **completo** en cada capa con cambios (es chico) y enlaza cada artículo a su archivo real, incluso si vive en una capa anterior. `transitorios.md` solo está en la capa si los transitorios cambiaron; si no, se hereda el anterior.
- Una ley que no cambia en un año nuevo queda como una capa que solo trae `_meta.json`: deja constancia de que se revisó (fecha, sha256 del PDF) y su vista es idéntica a la anterior.

### Resolución

La vista de una ley en el año `Y` es: para cada artículo, el archivo de la capa **más reciente** de la cadena `hereda_de` hasta `Y` que lo contenga. Las capas se ordenan por `vigente_desde` (no por el nombre de la carpeta), de modo que más adelante una capa pueda ser una fecha y no un año.

Hay un solo punto de resolución por lenguaje, y todo lo demás lo usa: `leyes_mx/versiones.py` (Python) y `npm/src/versiones.js` + `npm/src/almacen.js` (Node, también el build del sitio). Nada más debe leer `leyes/<año>/<SIGLA>/` directamente.

Un artículo heredado se presenta con el año de vigencia y la última reforma de la vista pedida (el archivo conserva los de su capa de origen; el campo `ruta` de las respuestas es el archivo real). El id del artículo, el estatus, las advertencias y la salida de las herramientas MCP no cambian; una ley sin capas se ve byte a byte como antes.

### Qué significa "vigente desde" en la base

La base (2026) **no tiene `vigente_desde`**. Su inicio implícito es el "inicio de cobertura" del repo (1 de enero de 2026), no la fecha histórica en que cada artículo entró en vigor: esa fecha no la tenemos por artículo, solo existe `ultima_reforma_dof` por ley. Por eso el `vigente_desde` de una capa se compara solo contra el de la capa anterior (o contra el 1 de enero del año base), y nunca debe leerse como "este artículo rige desde la fecha X" para lo que viene de 2026.

### Reformas a mitad de año

Una reforma con vigencia a mitad de año cabe como una capa con fecha: `vigente_desde: "2027-07-01"`, `hereda_de` apunta a la capa vigente antes de esa fecha. Hoy las capas viven en carpetas por año y el resolvedor trabaja por año, así que la consulta por año devuelve la capa más reciente de ese año; consultar "a una fecha" (la vista antes y después del 1 de julio) quedaría para cuando una capa pueda ser una fecha y no un año. El orden por `vigente_desde` y `vigente_hasta` derivado ya lo permiten. Mientras tanto, una reforma de vigencia inmediata en el mismo año se regenera con `scripts/revisar_reformas.py --aplicar`, que reescribe el delta de la capa del año.

## Reglas

1. Lo vigente hoy está en `leyes/2026/`. Cuando una reforma con vigencia 2027 se publique en el DOF, se genera `leyes/2027/` con `scripts/diferenciar.py` (solo lo que cambia) y `leyes/2026/` **no se toca**.
2. Una ley reformada en 2026 con vigencia posterior (por ejemplo, la jornada laboral gradual de la LFT) sigue siendo un solo texto; la gradualidad se documenta con la advertencia de `fuentes.json` y en `transitorios.md`, no con otra capa.
3. Una ley que **no cambió** para 2027 igualmente recibe su capa (solo `_meta.json`). Cuándo se considera que no cambió: después del 1 de enero de 2027, `scripts/revisar_reformas.py` no reporta cambio en "Última Reforma DOF" ni en el sha256 del PDF de la Cámara, y el estado de `proyectos/2027/` no lista esa ley. `scripts/diferenciar.py` lo comprueba además comparando artículo por artículo contra el texto heredado.
3-bis. **La Ley de Ingresos de la Federación (LIF) es anual**: la de 2026 rige solo en 2026. La de 2027 tendrá su propia carpeta y sigla/entrada en `fuentes.json` y **no hereda** de la de 2026 (una capa sin `hereda_de` es completa). Lo mismo para cualquier ordenamiento de vigencia de un solo ejercicio.
4. No se crea `leyes/2027/` por adelantado. Mientras no esté publicada la reforma, 2027 no existe como texto de ley; lo que hay es un proyecto en `proyectos/2027/`.
5. La consulta sin `--anio` usa el año más reciente con datos que **no sea posterior al año en curso**. Así, aunque `leyes/2027/` exista en diciembre de 2026, no se usa hasta enero de 2027.
6. `scripts/validar.py` comprueba las capas: `hereda_de` existe y es anterior; `vigente_desde` es una fecha válida y posterior a la de la capa heredada (o al 1 de enero de su año si es la base); `articulos_modificados` coincide con los archivos; cada artículo de la capa difiere del heredado (salvo los nuevos); un artículo declarado nuevo no puede existir en la capa heredada ni uno no declarado puede faltar en ella; no se guarda `vigente_hasta`. La secuencia de artículos y el conteo se verifican sobre la vista completa.

## Paquete de datos (Release)

El repo guarda las capas, pero el Release que descarga `npx leyes-mx` **materializa** por omisión la vista completa de cada año (`scripts/empaquetar_datos.py`): así los clientes publicados antes de las capas, que leen `leyes/<año>/` completo, no se rompen en 2027, y gzip hace barato lo repetido. Los artículos heredados llevan en el paquete `vigencia_anio` y `ultima_reforma_dof` de la vista y `heredado_de_anio`. `manifest.json` trae `"materializado": true` y `"capas": <n>`. Con `--sin-materializar` el paquete lleva las capas tal cual y el manifest sube a `esquema: 2`, para que un cliente que no entiende capas lo rechace en lugar de leerlo mal. El cliente nuevo lee los dos formatos.

## Qué guarda cada archivo para reconstruir la versión

`vigencia_anio`, `ultima_reforma_dof`, `fecha_descarga`, `sha256_fuente`, `fuente_url`. Para saber de qué capa sale un artículo basta su ruta: `leyes/2026/LISR/art-0001.md` visto en 2027 es el texto de 2026 que sigue vigente.
