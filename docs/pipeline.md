# Pipeline de extracción

Código en `leyes_mx/extraer.py` y `leyes_mx/pipeline.py`; scripts en `scripts/`.

1. **Descarga** (`scripts/extraer.py`): PDF de la Cámara de Diputados a `fuentes/<año>/<SIGLA>.pdf`. Los PDF (13 MB en total) **no se versionan**: están en `.gitignore` y lo que queda en git es el `sha256_pdf` de cada `_meta.json`. Se prefiere reproducir desde la fuente a inflar el historial.
2. **Texto**: `pdftotext -layout`. Se probó también sin `-layout`; se eligió `-layout` porque conserva la sangría (necesaria para separar fracciones, incisos y tablas) y deja las notas marginales de reforma en líneas propias. Sin `-layout` el orden de lectura mezcla notas y columnas de tablas (se usa solo como control independiente).
3. **Limpieza**: se quitan encabezados y pies por página (nombre de la ley, "CÁMARA DE DIPUTADOS DEL H. CONGRESO DE LA UNIÓN", "Secretaría General", "Secretaría de Servicios Parlamentarios", "Última Reforma DOF ...", "N de M"). Las notas marginales ("Párrafo reformado DOF ...", "Multa de ...") se separan del texto y se agregan al final de cada artículo en "Notas de reforma (margen del PDF)"; no forman parte del texto del artículo y la búsqueda no las indexa.
4. **Corte por artículo**: línea que empieza con "Artículo N[ordinal][-letra | Bis...]" seguida de punto. No cuenta "artículo 28 de esta Ley" (sin punto, en minúscula o a media línea). El cuerpo termina en el primer "TRANSITORIOS" / "DISPOSICIONES TRANSITORIAS" / "DISPOSICIONES DE VIGENCIA TEMPORAL". Los encabezados de Título/Capítulo/Sección que el PDF intercala se separan del artículo anterior y se guardan como `ubicacion` del siguiente (mejor esfuerzo).
5. **Formato**: los renglones partidos por el ancho del PDF se reúnen en párrafos; cada párrafo, fracción (I., II.) e inciso (a), b)) queda en su propio párrafo; los renglones partidos por salto de página se vuelven a unir. Las tablas (tarifas) se conservan tal cual en un bloque ```text.
6. **Escritura**: un `.md` por artículo con front matter, `_indice.md`, `_meta.json`, `transitorios.md` (separado por decreto de reforma, cada uno con su fecha de publicación).
7. **Validación**: `scripts/validar.py`. Ver README.

## Controles independientes

- `scripts/validar.py --pdf`: cuenta encabezados con una regex distinta y más simple, sobre el texto sin `-layout`.
- `scripts/verificar_cobertura.py`: porcentaje de secuencias de 6 palabras de cada artículo que existen en el texto del PDF extraído por otra vía.

## Particularidades del PDF fuente que el extractor tolera

- "Artículo 890-" (sin punto) en LFT: error tipográfico del PDF; se acepta el guion como terminador.
- "Artículo 3o. Bis.-", "Artículo 1o.-A BIS.-": ordinal y letra/palabra combinados.
- LSS: la letra va separada por un espacio, sin guion ("Artículo 15 A.", "Artículo 304 D."). El extractor la acepta; sin eso se perdían 48 artículos (entre ellos el 15-A, de subcontratación) y solo lo detectó el cruce con `validar.py --pdf` (385 encabezados contra 337 archivos).
- Artículos derogados: "Se deroga", "(Se deroga).", "(Derogado)." se marcan con `estatus: "derogado"`.
- LFT 513 (tabla de enfermedades de trabajo) mide ~360 mil caracteres: es un solo artículo con un catálogo completo. Un chunk por artículo es la regla, pero ese archivo es demasiado grande para meterlo entero en un contexto; usar `buscar` para ubicar el padecimiento y leer solo el tramo necesario.

## Tablas publicadas como imagen

pdftotext no ve las imágenes del PDF. En el art. 96 de la LISR la frase "la siguiente:" quedaba sin tabla (solo el texto, sin aviso). Solución:

1. `scripts/detectar_imagenes.py` lista las páginas con imágenes de contenido (ignora el logo del encabezado) y dice si están cubiertas. Es el control independiente: se corre antes de dar por buena una ley.
2. Cada tabla se transcribe en `tablas/<año>/<LEY>/tablas.json` (con el PNG original al lado) y `leyes_mx/tablas.py` la inyecta justo después del párrafo ancla al construir el artículo. Vive fuera de `leyes/` porque el pipeline borra y regenera esa carpeta.
3. Cada tabla se verifica en `validar.py` según su `tipo` en `tablas.json` (`leyes_mx/tablas.py`, `verificar`). `tarifa` (por omisión): cada límite inferior es el superior previo más 0.01 y cada cuota fija se recalcula desde la fila anterior (tolerancia 0.02). Otros: `lineal-por-fila` (porcentajes que crecen en línea recta por año), `matriz-pension` (lineal en semanas, creciente con edad y salario), `progresion` (paso fijo) y `monotona-decreciente` (con `escalon` opcional). Un tipo desconocido es error. Un error de transcripción rompe la validación. Las tablas de los transitorios llevan `"articulo": "transitorios"` y una `ancla`: se insertan en el decreto que las contiene.
4. `validar.py` además avisa si un párrafo termina en "la siguiente:" sin tabla ni lista debajo.
5. Las tablas sin verificación aritmética posible se dejan como imagen enlazada (`solo_imagen`), sin transcribir.


## Anexo 8 de la RMF

Las tarifas actualizadas de ISR (Anexo 8 de la RMF 2026) se extraen aparte con `scripts/extraer_anexo8.py` a `rmf/<año>/anexo-8/`. Ver [anexo-8.md](anexo-8.md).
