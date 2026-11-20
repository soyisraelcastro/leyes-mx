# Pipeline de extracción

Código en `leyes_mx/extraer.py` y `leyes_mx/pipeline.py`; scripts en `scripts/`.

1. **Descarga** (`scripts/extraer.py`): PDF de la Cámara de Diputados a `fuentes/<año>/<SIGLA>.pdf`. Los PDF (13 MB en total) **no se versionan**: están en `.gitignore` y lo que queda en git es el `sha256_pdf` de cada `_meta.json`. Se prefiere reproducir desde la fuente a inflar el historial.
2. **Texto**: `pdftotext -layout`. Se probó también sin `-layout`; se eligió `-layout` porque conserva la sangría (necesaria para separar fracciones, incisos y tablas) y deja las notas marginales de reforma en líneas propias. Sin `-layout` el orden de lectura mezcla notas y columnas de tablas (se usa solo como control independiente).
3. **Limpieza**: se quitan encabezados y pies por página (nombre de la ley, "CÁMARA DE DIPUTADOS DEL H. CONGRESO DE LA UNIÓN", "Secretaría General", "Secretaría de Servicios Parlamentarios", "Última Reforma DOF ...", "N de M"). Las notas marginales ("Párrafo reformado DOF ...", "Multa de ...") se separan del texto y se agregan al final de cada artículo en "Notas de reforma (margen del PDF)"; no forman parte del texto del artículo y la búsqueda no las indexa.
4. **Corte por artículo**: línea que empieza con "Artículo N[ordinal][-letra | Bis...]" seguida de punto. No cuenta "artículo 28 de esta Ley" (sin punto, en minúscula o a media línea). El cuerpo termina en el primer "TRANSITORIOS" / "DISPOSICIONES TRANSITORIAS" / "DISPOSICIONES DE VIGENCIA TEMPORAL". Los encabezados de Título/Capítulo/Sección que el PDF intercala se separan del artículo anterior y se guardan como `ubicacion` del siguiente (mejor esfuerzo).
5. **Formato**: los renglones partidos por el ancho del PDF se reúnen en párrafos; cada párrafo, fracción (I., II.) e inciso (a), b)) queda en su propio párrafo; los renglones partidos por salto de página se vuelven a unir. Las tablas (tarifas) se conservan tal cual en un bloque ```text.
6. **Escritura**: un `.md` por artículo con front matter, `_indice.md`, `_meta.json`, `transitorios.md` (separado por decreto de reforma, cada uno con su fecha de publicación).
7. **Validación**: `scripts/validar.py`. Ver README.

## Año nuevo: capas, no copias

`scripts/extraer.py` escribe una ley **completa** (la base, `leyes/2026/`). Un año posterior no se extrae ni se copia completo: `scripts/diferenciar.py` corre este mismo pipeline sobre el PDF nuevo en un directorio temporal, compara cada artículo contra el texto heredado y escribe en `leyes/<año>/<SIGLA>/` solo los que difieren (más `_meta.json` con `hereda_de`, `vigente_desde`, `articulos_modificados`). Reemplaza a `scripts/copiar_anio.py`, que quedó obsoleto: duplicaba ~18 MB por año y, al reescribir `vigencia_anio` en cada archivo, ni git deduplicaba. Modelo en [criterio-anios.md](criterio-anios.md); procedimiento en [publicar-reforma.md](publicar-reforma.md).

## Controles independientes

- `scripts/validar.py --pdf`: cuenta encabezados con una regex distinta y más simple, sobre el texto sin `-layout`.
- `scripts/verificar_cobertura.py`: porcentaje de secuencias de 6 palabras de cada artículo que existen en el texto del PDF extraído por otra vía.

## Particularidades del PDF fuente que el extractor tolera

- "Artículo 890-" (sin punto) en LFT: error tipográfico del PDF; se acepta el guion como terminador.
- "Artículo 3o. Bis.-", "Artículo 1o.-A BIS.-": ordinal y letra/palabra combinados.
- LSS: la letra va separada por un espacio, sin guion ("Artículo 15 A.", "Artículo 304 D."). El extractor la acepta; sin eso se perdían 48 artículos (entre ellos el 15-A, de subcontratación) y solo lo detectó el cruce con `validar.py --pdf` (385 encabezados contra 337 archivos).
- LFDC: no tiene reformas y su encabezado dice "Nueva Ley DOF 23-06-2005" en lugar de "Última Reforma DOF". El extractor acepta "Nueva Ley" igual que "Nuevo Reglamento" (RCFF): `ultima_reforma_dof` es entonces la fecha de publicación. Sin eso quedaba vacía.
- Títulos de decreto muy largos en los transitorios: el decreto de paridad de género del 11-05-2022 (LOPDC) y el del 15-01-2026 (LFT y LSS) reforman decenas de leyes y su título ocupa más de 12 renglones antes de "Publicado en el Diario Oficial". El extractor busca esa línea hasta 30 renglones abajo; con 12, sus transitorios quedaban pegados al decreto anterior. Regenerar las 12 leyes con los mismos PDF (mismo sha256) solo cambió esos tres encabezados.
- Ley del INFONAVIT y LSAR: artículos "Bis 1" a "Bis 6" ("Artículo 18 Bis 1.-", "Artículo 51 Bis 6.-", "Artículo 107 bis 1.-"). El número tras la palabra es otro sufijo del id (`18-bis-1`, ver [convencion-nombres.md](convencion-nombres.md)); sin eso se perdían 9 artículos de la LINFONAVIT y 1 de la LSAR, y solo lo detectó el cruce de `validar.py --pdf` (95 encabezados contra 86 archivos).
- LSAR: la letra separada por espacio termina en ".-" ("Artículo 37 A.-", "Artículo 100 B.-"); la LSS la trae con ". " y el extractor solo aceptaba esa forma (3 artículos perdidos, también los vio el cruce).
- RLSAR (y RIPAED): encabezados en mayúsculas, "ARTÍCULO 155.". El extractor y el cruce de `validar.py` aceptan las dos formas; las 15 leyes que ya estaban se regeneraron con los mismos PDF (mismo sha256) y no cambió un solo archivo.
- Artículos derogados: "Se deroga", "(Se deroga).", "(Derogado)." se marcan con `estatus: "derogado"`.
- LFT 513 (tabla de enfermedades de trabajo) mide ~360 mil caracteres: es un solo artículo con un catálogo completo. Un chunk por artículo es la regla, pero ese archivo es demasiado grande para meterlo entero en un contexto; usar `buscar` para ubicar el padecimiento y leer solo el tramo necesario.

## Tablas publicadas como imagen

pdftotext no ve las imágenes del PDF. En el art. 96 de la LISR la frase "la siguiente:" quedaba sin tabla (solo el texto, sin aviso). Solución:

1. `scripts/detectar_imagenes.py` lista las páginas con imágenes de contenido (ignora el logo del encabezado) y dice si están cubiertas. Es el control independiente: se corre antes de dar por buena una ley.
2. Cada tabla se transcribe en `tablas/<año>/<LEY>/tablas.json` (con el PNG original al lado) y `leyes_mx/tablas.py` la inyecta justo después del párrafo ancla al construir el artículo. Vive fuera de `leyes/` porque el pipeline borra y regenera esa carpeta.
3. Cada tabla se verifica en `validar.py` según su `tipo` en `tablas.json` (`leyes_mx/tablas.py`, `verificar`). `tarifa` (por omisión): cada límite inferior es el superior previo más 0.01 y cada cuota fija se recalcula desde la fila anterior (tolerancia 0.02). Otros: `lineal-por-fila` (porcentajes que crecen en línea recta por año), `matriz-pension` (lineal en semanas, creciente con edad y salario), `progresion` (paso fijo) y `monotona-decreciente` (con `escalon` opcional). Un tipo desconocido es error. Un error de transcripción rompe la validación. Las tablas de los transitorios llevan `"articulo": "transitorios"` y una `ancla`: se insertan en el decreto que las contiene.
4. `validar.py` además avisa si un párrafo termina en "la siguiente:" sin tabla ni lista debajo.
5. Las tablas sin verificación aritmética posible se dejan como imagen enlazada (`solo_imagen`), sin transcribir.
6. La LSAR trae como imagen las mismas tres tablas de los transitorios del decreto de 16-12-2020 que la LSS (cuota patronal 2023-2030, cuota social de 4.01 a 7.09 UMA, semanas y pensión garantizada): `pdfimages` da archivos idénticos byte por byte, así que `tablas/2026/LSAR/tablas.json` reutiliza la transcripción verificada de la LSS con las páginas de la LSAR.
7. Las fórmulas de distribución de la LCF (arts. 2, 2-A, 4, 4-A, 4-B, 31, 34 y 46) vienen como imágenes chicas (debajo del umbral de `detectar_imagenes.py`, que solo ve las de más de 200x100) o como notación matemática que pdftotext desordena o pierde (también los símbolos de las variables en las definiciones). Se transcriben a **LaTeX** (`$...$` en línea, `$$...$$` en bloque) en la clave `formulas` de `tablas/<año>/LCF/tablas.json`; cada entrada sustituye un texto exacto del artículo (`buscar`, o `desde`/`hasta` para quitar un bloque desordenado de varias líneas) y lleva la página del PDF de donde se transcribió. `leyes_mx/tablas.py` (`aplicar_formulas`) falla si el texto a sustituir no aparece una sola vez, así que un cambio en el PDF no pasa en silencio; `verificar_formulas` (en `validar.py`) revisa `$`, llaves y `\left`/`\right`. El front matter del artículo lista las entradas en `formulas_latex`. Las transcripciones son a mano contra la imagen; no hay verificación aritmética posible, así que cada artículo lleva una ADVERTENCIA (`fuentes.json`) que dice que ante la duda prevalece el PDF oficial.


## Ordenamientos sin texto compilado de la Cámara (RIPAED)

El pipeline lee el PDF "TEXTO VIGENTE" que compila la Cámara. El **Reglamento de Inscripción, Pago de Aportaciones y Entero de Descuentos al INFONAVIT (RIPAED)** no lo tiene: la Cámara lo lista entre sus normas (https://www.diputados.gob.mx/LeyesBiblio/norma/reglamento.htm) solo con el original (DOF 10-02-2012) y el decreto de reforma (DOF 28-09-2017), cada uno por separado y en Word. Armar el texto vigente a mano iría contra la regla de que ningún artículo se escribe a mano, así que se consolida con código a partir de las dos publicaciones del DOF:

1. `fuentes.json` lleva en la entrada una clave `consolidacion`: la nota del DOF original (`original`), los decretos (`reformas`, en orden, cada uno con `fecha_dof`, `fecha_texto` y `titulo`) y `vigilar` (la página y el texto del renglón de la Cámara que revisa `revisar_reformas.py`). `url` es la nota original del DOF.
2. `scripts/extraer.py RIPAED` descarga las notas de dof.gob.mx a `fuentes/<año>/RIPAED/DOF-<fecha>.html` (ignoradas por git, como los PDF) y `leyes_mx/consolidar.py` las lee: párrafo por párrafo, volviendo a unir los que el DOF parte por salto de página.
3. El decreto se aplica artículo por artículo. Un artículo que el decreto da completo (sin "...") sustituye al original; uno nuevo se inserta en su lugar con el encabezado de capítulo que lo precede; "Derogado." lo deroga. Cuando el decreto trae "..." (cada "..." conserva la unidad original que le toca: párrafo, fracción o inciso; "I. a III. ..." conserva un rango), el mapa `consolidacion/RIPAED.json` dice a qué unidad va cada texto nuevo (índice de la unidad original que sustituye, "+" si es una adición en ese punto o "+fin" si es una adición al final del artículo, como el último párrafo del art. 61, cuyas fracciones el decreto no repite). **El mapa no lleva texto**: solo posiciones. Lo que el decreto no menciona queda igual.
4. Controles: un texto nuevo con etiqueta (fracción o inciso) solo puede sustituir a una unidad con la misma etiqueta; el orden no retrocede; sobrar o faltar destinos es error; los artículos del decreto deben ser exactamente los que enumera su ARTÍCULO ÚNICO. Un mapa mal hecho falla en lugar de pasar en silencio (`tests/test_consolidar.py`).
5. Sale un texto con la misma forma que el de pdftotext (renglones en blanco entre párrafos, notas "Fracción reformada DOF 28-09-2017" en renglón propio, transitorios por decreto) y `pipeline.construir(..., consolidado=...)` lo procesa como cualquier ley. Las notas de reforma van bajo "## Notas de reforma (generadas al consolidar desde el DOF)". `_meta.json` trae `consolidado_desde_dof` (cada nota con su sha256) y `sha256_pdf` es el sha256 de esos sha256. Los artículos que tocó el decreto llevan una ADVERTENCIA (`fuentes.json`) con los dos enlaces del DOF.

Control independiente hecho al agregarlo (2026-11-19): los párrafos que salen del HTML del DOF coinciden uno a uno con los del Word de la Cámara (`regla/n327.doc` y `regla/n327_28sep17.doc`, convertidos con `textutil`); solo difieren el encabezado de la sección del DOF y el ARTÍCULO ÚNICO por un carácter de comillas. Además se revisaron a mano contra el decreto los 19 artículos con "..." (3, 8, 16, 20, 23, 27, 30, 43, 56 a 58, 60 a 63, 66, 71, 77 y 79).

Un decreto nuevo: `scripts/revisar_reformas.py` compara las fechas del renglón de la Cámara con las de `consolidacion` y avisa `reforma_nueva`. Se agrega el decreto a `reformas`, sus posiciones al mapa (clave = fecha del decreto) y se corre `scripts/extraer.py RIPAED`. `scripts/diferenciar.py` no lo procesa (no hay PDF): para un año nuevo se regenera así y, si el texto no cambió, la capa lleva solo `_meta.json`.

## Anexo 8 de la RMF

Las tarifas actualizadas de ISR (Anexo 8 de la RMF 2026) se extraen aparte con `scripts/extraer_anexo8.py` a `rmf/<año>/anexo-8/`. Ver [anexo-8.md](anexo-8.md).
