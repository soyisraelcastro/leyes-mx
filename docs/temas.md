# Temas: un índice por materia sobre toda la base

Código en `leyes_mx/temas.py`; vocabulario en `temas.json` (raíz); salida en `temas/<año>/`; script `scripts/etiquetar.py`; herramienta MCP `temas`.

## Para qué sirve

`buscar` encuentra palabras. Los temas responden otra pregunta: **qué toca una materia en todos los ordenamientos a la vez**. "Todo lo de hidrocarburos" cruza la RMF (controles volumétricos, Título 10 sobre la Ley de Ingresos sobre Hidrocarburos), la LISR, el CFF y sus reglamentos, y cuando se agreguen la LIF, la LISH o la LFD, entran solas al mismo índice.

## Cómo se etiqueta (una sola regla, sin criterio de nadie en medio)

Cada tema de `temas.json` trae `id`, `nombre`, `descripcion`, `palabras` (en el idioma de la ley), opcionalmente `umbral` y `citas`. Un documento (artículo de `leyes/` o regla de `rmf/`) recibe el tema si:

1. una palabra del tema está en su **encabezado** (la ubicación Título/Capítulo/Sección de un artículo; el título y la ubicación de una regla), o
2. una palabra aparece en el **texto** al menos `umbral` veces (2 por omisión; 1 si el texto tiene menos de 1,500 caracteres, porque un artículo corto que nombra el tema una vez trata de él; el vocabulario baja a 1 el umbral de las frases muy específicas, como "régimen simplificado de confianza"), o
3. es una regla cuyo **fundamento** cita una de las leyes de `citas` (por ejemplo, las reglas que citan la LISH entran al tema de hidrocarburos).

Puntaje para ordenar: 5 por cada coincidencia en el encabezado, 1 por cada una en el texto (máximo 20) y 3 por la cita. Los términos se comparan sin acentos ni mayúsculas, admiten plural, y no coinciden dentro de otra palabra.

Es **léxico, no semántico**: "menciona o trata". Un puntaje de 1 o 2 suele ser una mención de pasada; para quedarse con lo central, filtrar con `minimo`. No reemplaza leer el artículo: el índice dice dónde mirar.

No hay etiquetas a mano ni asignadas por un modelo. El mismo `temas.json` sobre los mismos textos da siempre el mismo resultado, por eso se puede regenerar, auditar y exigir.

## Salida (derivada: no se edita)

```
temas.json                       vocabulario (a mano, es la única fuente)
temas/2026/_indice.json         tema -> [ley, artículo o regla, puntaje, dónde]; cobertura por ordenamiento; hashes
temas/2026/_resumen.md          todos los temas, con conteos y cobertura
temas/2026/<tema>.md            los documentos del tema, de mayor a menor puntaje, con enlace al archivo
```

## La regla: todo ordenamiento se etiqueta

- `python3 scripts/etiquetar.py` regenera `temas/` y se corre **cada vez** que cambia `temas.json` o entra, sale o se actualiza un ordenamiento (ley, reglamento o resolución de la RMF).
- `scripts/validar.py`, y con él el CI, **falla** si `temas/` no es idéntico a lo que daría regenerarlo ahora. No se puede agregar una ley sin que quede etiquetada.
- `etiquetar.py` imprime la cobertura (qué parte de cada ordenamiento recibió al menos un tema). Un ordenamiento nuevo con poca cobertura casi siempre es un hueco del vocabulario: agregar las palabras propias de esa materia a `temas.json` y regenerar. Así se detectaron y cerraron, por ejemplo, el derecho procesal del trabajo, la organización del IMSS y los derechos federales.
- Cada tema debe etiquetar algo: un tema sin documentos sale como aviso en `validar.py` y se quita (así se quitaron "activos virtuales" y "régimen de incorporación fiscal", que ningún texto vigente de la base menciona).

## Agregar o ajustar un tema

1. Editar `temas.json`: id en minúsculas y guiones, nombre, descripción y las palabras como las escribe la ley (no como las dice la gente: "comprobante fiscal digital por internet" y también "CFDI").
2. `python3 scripts/etiquetar.py` y revisar `temas/<año>/<tema>.md`: los de puntaje alto deben ser lo central; si entran artículos que no tienen que ver, quitar la palabra ambigua o subir el `umbral`.
3. `python3 scripts/validar.py` y `python3 -m unittest discover -s tests`.
4. El índice sale con el siguiente Release de datos (`npx leyes-mx actualizar`); no requiere publicar el paquete npm.

## Lo que se midió al construirlo (2026-11-05)

4,224 documentos (3,016 artículos no derogados de 14 leyes y reglamentos y 1,208 reglas de la RMF) y 66 temas. Cobertura por ordenamiento, de menor a mayor: RLIVA 73%, RACERF 80%, LFT 86%, LIEPS 91%, LFDC 92%, LIVA 92%, LOPDC 93%, RLISR 93%, LSS 94%, CFF 96%, RMF 96%, RCFF 96%, LIF 97%, LISR 98%, LCF 98%. La cobertura baja por ordenamiento se revisó por ubicación (qué capítulos quedaban sin tema) y de ahí salieron los temas que faltaban; lo que sigue sin tema son sobre todo disposiciones generales o de forma. Se regenera en menos de 10 segundos.
