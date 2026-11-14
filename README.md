# leyes-mx

Base abierta de leyes y reglamentos fiscales y laborales de México en Markdown: **un archivo por artículo**, versionada por **año de vigencia**, con buscador local.

Sirve para que asistentes y herramientas con modelos de lenguaje (Claude Code, Codex, agentes propios, sistemas RAG) **consulten el texto local y verificable en lugar de ir a buscarlo a internet**: menos timeouts, menos citas inventadas, resultados reproducibles y citas completas (ley, artículo, año de vigencia y fecha de última reforma).

El texto sale de los PDF oficiales de la Cámara de Diputados, sin editar. Lo que es proyecto de reforma vive aparte y nunca se presenta como ley vigente.

> **Aviso.** Los textos son informativos y se copian de la Cámara de Diputados del H. Congreso de la Unión; pueden tener diferencias o errores de extracción y no sustituyen al Diario Oficial de la Federación. **La fuente oficial (Cámara de Diputados / DOF) prevalece.** Esto no es asesoría legal ni fiscal.

## Instalar con npx

Para usar estas leyes desde Claude Desktop, Codex (incluida la app de escritorio de ChatGPT), Claude Code, Cursor o cualquier cliente que hable MCP, en tu propio equipo y sin internet para consultar:

```bash
npx leyes-mx instalar
```

Descarga los datos (unos 3 MB, con verificación sha256), detecta tus clientes, registra el servidor y, donde aplica, copia la skill. Al terminar explica en español qué hacer: **reiniciar Claude Desktop por completo** (cerrarlo del todo y abrirlo) y pegar una pregunta de prueba ("¿Qué dice el artículo 28 de la LISR?"); si funcionó, la respuesta cita la ley, el artículo y la vigencia. Con `--cliente claude-desktop|claude-code|codex|cursor|todos` eliges uno y con `--dry-run` ves qué haría sin escribir nada.

```bash
npx leyes-mx actualizar     # cuando salga una ley, una reforma o un cambio del glosario; refresca también la skill
npx leyes-mx doctor         # verificar que quedó bien (y si Claude Desktop quedó listo, en una línea)
npx leyes-mx obtener LISR 28
npx leyes-mx buscar "fundamento para no deducir actualizaciones"
npx leyes-mx tarifa B-V     # tarifa mensual de ISR del Anexo 8
npx leyes-mx skill --zip    # skill para cargar a mano en Claude Desktop (opcional)
npx leyes-mx desinstalar
```

Necesita Node 20 o superior; si falta, pídele a tu asistente que lo instale (mensaje listo para pegar en [docs/clientes.md](docs/clientes.md)). Qué clientes sí y cuáles no (Claude web y ChatGPT web quedan fuera por ahora; la extensión `.mcpb` para quien no tiene Node): [docs/clientes.md](docs/clientes.md). Detalle, arquitectura de datos y cómo publicar: [docs/npx.md](docs/npx.md) y [npm/README.md](npm/README.md). La landing con instrucciones por cliente está en `sitio/` (Astro, para Vercel).

### Para que el asistente lo use solo

Las instrucciones del servidor y la descripción de cada herramienta le piden al modelo consultar la base **antes de responder cualquier consulta fiscal o laboral de México** (ISR, IVA, deducciones, CFDI, aguinaldo, "qué dice el artículo"...) y antes de citar un artículo; leer el artículo completo, citar ley, artículo, fracción, vigencia y última reforma; sacar las tarifas de ISR de `obtener_tarifa`; y nunca presentar el proyecto de 2027 como ley vigente. Si algo no está en la base, el **resultado** de la herramienta dice "No encontré esto en la base local" y manda **preguntar al usuario** si quiere que se busque en internet (nunca buscar sin su permiso; si lo autoriza, solo fuentes oficiales y aclarando que no viene de la base verificada). Eso funciona en cualquier cliente porque va en el resultado, no solo en las instrucciones.

- **Glosario de sinónimos contables** (`glosario.json`): la búsqueda es por palabras, así que "actualizaciones" no encontraba "accesorios de las contribuciones". El glosario amplía la consulta con los términos de la ley, la respuesta declara qué agregó y se actualiza con `npx leyes-mx actualizar`, sin versión nueva de npm. Formato y cómo aportar entradas: [docs/glosario.md](docs/glosario.md).
- **Skill `leyes-mx`** (`/leyes-mx`): el método de trabajo completo, por MCP o por terminal. Se instala sola en Claude Code y Codex; en Claude Desktop es opcional y se carga a mano. Rutas, fuentes y lo no verificado: [docs/skill.md](docs/skill.md).
- Para `AGENTS.md` o `CLAUDE.md`: `npx leyes-mx instalar --instrucciones` agrega un bloque delimitado, con confirmación.

## Qué contiene

Año de vigencia 2026 (texto vigente al 2026-11-02, descargado ese día):

| Sigla | Ordenamiento | Artículos | Vigentes | Derogados | Última reforma DOF (según la Cámara) |
|---|---|---|---|---|---|
| LISR | Ley del Impuesto sobre la Renta | 236 | 224 | 12 | 2024-04-01 |
| LIVA | Ley del Impuesto al Valor Agregado | 80 | 65 | 15 | 2021-11-12 |
| CFF | Código Fiscal de la Federación | 421 | 337 | 84 | 2026-04-09 |
| LFT | Ley Federal del Trabajo | 1266 | 1118 | 148 | 2026-05-14 |
| RLISR | Reglamento de la LISR | 313 | 312 | 1 | 2016-05-06 |
| RLIVA | Reglamento de la LIVA | 84 | 70 | 14 | 2014-09-25 |
| RCFF | Reglamento del CFF | 113 | 113 | 0 | 2014-04-02 (nuevo reglamento) |
| LSS | Ley del Seguro Social | 385 | 385 | 0 | 2026-01-15 |
| RACERF | Reglamento de la LSS en materia de afiliación, clasificación de empresas, recaudación y fiscalización | 196 | 196 | 0 | 2005-07-15 |
| LFDC | Ley Federal de los Derechos del Contribuyente | 24 | 24 | 0 | 2005-06-23 (sin reformas: fecha de publicación) |
| LCF | Ley de Coordinación Fiscal | 67 | 66 | 1 | 2024-01-03 |
| LOPDC | Ley Orgánica de la Procuraduría de la Defensa del Contribuyente | 28 | 28 | 0 | 2022-05-11 |
| LIEPS | Ley del Impuesto Especial sobre Producción y Servicios | 69 | 44 | 25 | 2025-11-07 |
| LIF | Ley de Ingresos de la Federación para el Ejercicio Fiscal de 2026 | 34 | 34 | 0 | 2025-11-07 (nueva ley, en vigor desde 2026-01-01) |

LFDC, LCF y LOPDC se descargaron el 2026-11-07; LIEPS y LIF el 2026-11-11. La LIF es una ley anual: solo rige en 2026 y la de 2027 tendrá su propia carpeta y no hereda de la de 2026 (ver [docs/criterio-anios.md](docs/criterio-anios.md)). El artículo 26-LL de la LIEPS (derogado) no tiene archivo propio, lleva su línea al final del 26-L. Las fórmulas de distribución de la LCF vienen en el PDF como imagen o notación matemática; se transcribieron a LaTeX (`$...$` y `$$...$$`) para que las lean los asistentes, y esos artículos llevan una advertencia: ante la duda prevalece el PDF oficial.

Además `proyectos/2027/`: seguimiento de la reforma fiscal 2027 (**no es ley vigente**).

## Cómo está organizado

```
leyes/<año>/<SIGLA>/art-0028.md          un archivo por artículo (art-0113-E.md, art-0028-bis.md)
leyes/<año>/<SIGLA>/transitorios.md      transitorios, separados por decreto de reforma
leyes/<año>/<SIGLA>/_indice.md           lista de artículos
leyes/<año>/<SIGLA>/_meta.json           sigla, nombre oficial, URL, última reforma DOF, fecha de descarga, sha256 del PDF, conteo
                                         (un año posterior a 2026 es una capa: solo los artículos que cambian y hereda_de, vigente_desde, articulos_modificados)
proyectos/<año>/                         proyectos de reforma (estatus "proyecto"), línea de tiempo y documentos
fuentes.json                             lista de leyes configuradas
leyes_mx/  scripts/  docs/               biblioteca, CLI y scripts, documentación
npm/                                     paquete npm "leyes-mx" (instalador y servidor MCP)
sitio/                                   landing en Astro
```

`<año>` es el **año de vigencia** del texto, no la fecha de descarga. `leyes/2026/` es la base y no se toca: lo de 2027 será una capa que guarda solo los artículos que cambian y hereda el resto, sin duplicar la ley (se genera con `scripts/diferenciar.py`, que reemplaza a `copiar_anio.py`; ver [docs/criterio-anios.md](docs/criterio-anios.md)). Convención de nombres: [docs/convencion-nombres.md](docs/convencion-nombres.md).

Cada artículo trae front matter YAML:

```yaml
---
ley: "LISR"
nombre_ley: "Ley del Impuesto sobre la Renta"
vigencia_anio: 2026
ultima_reforma_dof: "2024-04-01"
fuente_url: "https://www.diputados.gob.mx/LeyesBiblio/pdf/LISR.pdf"
fecha_descarga: "2026-11-02"
articulo: "113-E"
estatus: "vigente"        # vigente | derogado (en leyes/) ; proyecto (solo en proyectos/)
sha256_fuente: "..."
ubicacion: "TÍTULO IV ... > CAPÍTULO II ... > SECCIÓN IV ..."
---
```

## Consultar con el CLI de Python

Solo requiere Python 3.9+ (biblioteca estándar) y SQLite con FTS5.

```bash
# artículo exacto (acepta "113 E", "113-e", "28 bis", "Artículo 28-Bis")
python3 scripts/buscar.py obtener LISR 113-E
python3 scripts/buscar.py obtener CFF "69 B"
python3 scripts/buscar.py obtener LFT 61 --anio 2026

# por palabras clave (sin acentos, ranking por relevancia)
python3 scripts/buscar.py buscar "recargos deducibles" --ley LISR
python3 scripts/buscar.py buscar "retención 1.25%" --ley LISR --limite 5

# qué hay en la base y estado de la reforma 2027
python3 scripts/buscar.py listar
python3 scripts/buscar.py estado

# salida JSON, para otros programas
python3 scripts/buscar.py obtener LISR 28 --json

# instalado como paquete: pip install .  ->  comando `leyes-mx`
leyes-mx obtener LISR 113-E
```

Siempre imprime ley, artículo, año de vigencia y fecha de última reforma junto al texto. Sin `--anio` usa el año vigente más reciente con datos. Si el artículo no existe responde "NO VERIFICADO" (código de salida 1) y nunca inventa texto.

Como biblioteca:

```python
from leyes_mx import obtener_articulo, buscar
a = obtener_articulo("LISR", "113 E")
print(a["ley"], a["articulo"], a["anio_vigencia"], a["ultima_reforma_dof"])
print(a["texto"])
```

El contrato de las funciones está en [docs/arquitectura.md](docs/arquitectura.md).

## Reglas de la Resolución Miscelánea Fiscal 2026

`rmf/2026/rmf/reglas/regla-2.7.1.1.md`: una regla por archivo (1,208 reglas), con título, ubicación (Título > Capítulo > Sección), página del PDF, el fundamento tal como lo imprime la RMF (`CFF 29, 29-A, RMF 2.7.1.32.`) y ese mismo fundamento ya separado por ley y por regla (`referencias_leyes`, `referencias_reglas`) para cruzarlo con los artículos de `leyes/`. Además `glosario.md`, `preambulo.md`, `transitorios.md` y `_indice.md`. Cómo se extrae y qué controles tiene: [docs/rmf.md](docs/rmf.md).

**Estado, con cuidado:** es el texto de la RMF para 2026 publicado en el DOF el 28-12-2025. **Todavía no trae aplicadas** las resoluciones de modificación (09-07, 01-10 y 02-10-2026): una regla modificada o derogada después sigue apareciendo aquí con su texto original. El servidor MCP las sirve con `obtener_regla`, y cada respuesta repite esta advertencia.

## Temas: lo que una materia toca en todas las leyes

`temas.json` es un vocabulario controlado (hidrocarburos, CFDI, subcontratación, cuotas del IMSS, donatarias, PTU...) y `temas/2026/` el índice que resulta de aplicarlo a **todos** los artículos de `leyes/` y las reglas de `rmf/`: `temas/2026/hidrocarburos.md` lista, de lo más central a lo más tangencial, qué artículos y reglas de cualquier ley tocan ese tema. Desde el asistente: herramienta `temas`.

No es semántico ni lo asigna un modelo: cada tema es una lista de palabras en el idioma de la ley y un documento lo recibe si la palabra está en su encabezado, se repite en el texto o lo cita el fundamento de la regla. El mismo vocabulario sobre los mismos textos da siempre el mismo índice. **Es obligatorio:** al agregar o actualizar cualquier ordenamiento se corre `python3 scripts/etiquetar.py` y el CI falla si `temas/` no está al día. Reglas, límites y cómo agregar un tema: [docs/temas.md](docs/temas.md).

## Anexo 8 de la RMF 2026 (tarifas de ISR)

`rmf/2026/anexo-8/` trae las tarifas del Anexo 8 de la Resolución Miscelánea Fiscal para 2026 (DOF 2025-12-28, firmado 2025-12-17): 31 tarifas, una por archivo, copiadas del PDF del SAT y verificadas con aritmética. Las tarifas de los arts. 96 y 152 de la LISR son las **de la ley**; para 2026 se aplican las del anexo (mensual 2026: `B-V-tarifa-mensual-2026.md`; anual 2026: `C-II-tarifa-anual-2026.md`). Los arts. 96 y 152 de `leyes/` traen un aviso que lo dice.

```bash
python3 scripts/buscar.py obtener-anexo 8            # lista las 31 tarifas
python3 scripts/buscar.py obtener-anexo 8 B-V        # tarifa mensual 2026
python3 scripts/buscar.py obtener-anexo 8 C-II --json
```

Detalle y verificación: [docs/anexo-8.md](docs/anexo-8.md).

**Subsidio para el empleo 2026:** no es tarifa (desde 2024 es un porcentaje de la UMA mensual con tope de ingresos). Los decretos del DOF (01-05-2024 y reformas), el valor de la UMA 2025 y 2026 que publica el INEGI y un texto consolidado están en `decretos/2026/spe/`; herramienta `obtener_subsidio_empleo`, en terminal `npx leyes-mx subsidio`. Detalle, cifras y qué no está verificado: [docs/spe.md](docs/spe.md).

## Conectarlo a un asistente

La idea es una regla simple en las instrucciones del asistente (`AGENTS.md`, `CLAUDE.md` o el prompt del sistema):

1. Primero consultar esta base (`obtener` para un artículo conocido, `buscar` para un tema).
2. Solo si no está, buscar en la web y únicamente en dominios oficiales (diputados.gob.mx, dof.gob.mx, sat.gob.mx). Si tampoco, responder "no verificado".
3. Citar siempre ley, artículo, año de vigencia y fecha de última reforma.
4. Nunca presentar un proyecto como ley.

Funciona igual con un agente que ejecuta comandos (Claude Code, Codex), con un RAG sobre los archivos `.md` (un artículo es un chunk natural) o, más adelante, con un servidor MCP. Texto de ejemplo listo para pegar y notas de sincronización a un servidor: [docs/integracion-abacus.md](docs/integracion-abacus.md).

## Vigente vs. proyecto

- `leyes/` contiene **solo** texto vigente (o derogado). Lo verifica `scripts/validar.py` y el CI.
- `proyectos/` contiene propuestas con `estatus: "proyecto"` y `estado_proyecto` (iniciativa, aprobado_camara, aprobado_senado, publicado_dof), con una nota visible de que no es ley.
- El buscador **excluye los proyectos por defecto**; con `--incluir-proyectos` los incluye marcados.
- **La reforma fiscal 2027 no es ley hasta que se publique en el DOF.** Estado al 2026-11-02 y fuentes en [proyectos/2027/README.md](proyectos/2027/README.md). La reforma de la jornada laboral de 40 horas, en cambio, ya está publicada (DOF 2026-05-01) y es gradual; los artículos afectados de la LFT traen una advertencia.
- Cuando algo se publique en el DOF, [docs/publicar-reforma.md](docs/publicar-reforma.md) describe cómo promoverlo como una capa de `leyes/<año>/` (solo lo que cambia).

## Cómo se actualiza

- `.github/workflows/actualizar.yml` corre el día 1 de cada mes (14:00 UTC) y a demanda: compara "Última Reforma DOF" y el sha256 de cada PDF con lo guardado; si cambió, regenera lo afectado y abre un PR con el diff, o un issue si la regeneración no pasa la validación o si hay señal de que se publicó la reforma 2027.
- `scripts/revisar_reformas.py --dry-run` hace la misma revisión sin escribir nada y sirve para cron en un servidor (código de salida 0 sin cambios, 1 cambios, 2 error).
- Agregar una ley: nueva entrada en `fuentes.json` y `python3 scripts/extraer.py SIGLA`. No hace falta tocar código.

## Validación

```bash
python3 scripts/validar.py --pdf          # estructura, secuencia, front matter, conteos; --pdf cruza con una extracción independiente
python3 scripts/verificar_cobertura.py    # cobertura de cada artículo contra el texto del PDF
python3 -I tests/test_ids.py
```

## Limitaciones

- Los textos son tan buenos como el PDF de la Cámara y la extracción. Las tablas que el PDF publica como TEXTO se conservan como bloque de texto; las que publica como IMAGEN (hoy solo en la LISR: tarifa mensual del art. 96, tarifa anual del art. 152 y dos tablas de un transitorio) no las ve la extracción, así que se transcriben aparte en `tablas/<año>/<LEY>/tablas.json`, se verifican con aritmética (rangos contiguos y cuota fija recalculada) y conservan la imagen original. `python3 scripts/detectar_imagenes.py` avisa si aparece otra imagen sin cubrir. Las dos tablas del transitorio (deducción de inversiones 2016 y 2017) solo tienen la imagen, sin transcribir.
- Las tarifas de los arts. 96 y 152 de `leyes/` son las de la ley. Cada año se actualizan por inflación y se publican en el Anexo 8 de la RMF (art. 152, último párrafo). El Anexo 8 de la RMF 2026 sí está en el repo (`rmf/2026/anexo-8/`, ver sección "Anexo 8 de la RMF"): para calcular retenciones o el anual 2026 se usa esa tarifa. Los demás anexos no están; las reglas de la RMF están en `rmf/2026/rmf/` (ver abajo), sin las modificaciones posteriores.
- La Cámara puede tardar en reflejar una reforma; la fecha "última reforma" es la que imprime su PDF, no una verificación contra el DOF.
- Los reglamentos son los que publica la Cámara en su sitio (RLISR con última reforma de 2016, RLIVA de 2014, RCFF de 2014, RACERF de 2005); verificar si existen versiones posteriores en el DOF. Las reglas de la RMF 2026 están en `rmf/2026/rmf/` en su texto original (sin las resoluciones de modificación) y sus anexos, salvo el Anexo 8, **no** están en la base.
- El artículo 513 de la LFT (tabla de enfermedades) es un archivo de ~360 mil caracteres.
- Búsqueda léxica (no semántica). El paquete npm la complementa con un glosario de sinónimos contables ([docs/glosario.md](docs/glosario.md)); el motor de Python (`scripts/buscar.py`) no lo usa. Para un artículo conocido usar `obtener`.
- Los dictámenes y minutas de la reforma 2027 están escaneados; los archivos por artículo de `proyectos/2027/` reflejan la iniciativa, no el texto final del trámite. Detalle en su README.

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md). Resumen: el texto legal siempre sale del texto oficial descargado, nunca se escribe a mano; correr `scripts/validar.py` antes del PR; mensajes de commit en español, cortos y claros; **ningún commit ni PR lleva `Co-Authored-By` ni firmas de herramientas** (hook en `.githooks/`, se activa con `sh scripts/instalar-hooks.sh`, y CI que lo revisa).

## Hoja de ruta

- Más ordenamientos: Ley del INFONAVIT, LIEPS, Ley de Ingresos, Ley Federal de Derechos y otros (solo configuración en `fuentes.json`).
- Resolución Miscelánea Fiscal y sus anexos.
- Jurisprudencia y criterios.
- API HTTP o servidor MCP hospedado sobre las mismas funciones (habilitaría Claude web y ChatGPT web, que solo conectan servidores remotos; ver [docs/clientes.md](docs/clientes.md)). El servidor MCP local ya existe: ver [docs/npx.md](docs/npx.md).
- Extensión de escritorio `.mcpb` para Claude Desktop (instalación de un clic, sin Node): viabilidad en [docs/clientes.md](docs/clientes.md).
- Año 2027 cuando se publique la reforma.

## Licencia

Código y documentación: MIT (ver [LICENSE](LICENSE)). Los textos legales provienen de la Cámara de Diputados y del DOF; son textos oficiales de dominio público, informativos y sin garantía; la fuente oficial prevalece.
