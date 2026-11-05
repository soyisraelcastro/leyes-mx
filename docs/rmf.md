# Resolución Miscelánea Fiscal (RMF): una regla por archivo

Código en `leyes_mx/rmf.py` (extracción) y `leyes_mx/rmf_validar.py` (validación); script `scripts/extraer_rmf.py`; configuración en `fuentes.json`, clave `rmf`.

## Alcance

- Solo el texto **publicado en el DOF** y alojado por el SAT en su página de normatividad (RMF y resoluciones de modificación). No se usan versiones anticipadas ni compiladas.
- Hoy: la RMF para 2026 (DOF 28-12-2025). Faltan, y se agregan una por una, la 1a (09-07-2026), la 2a (01-10-2026) y la 3a (02-10-2026) resoluciones de modificación. **Mientras no estén aplicadas, una regla modificada o derogada sigue con su texto original.**
- Los anexos no están (salvo el Anexo 8, ver [anexo-8.md](anexo-8.md)).

## Salida

```
rmf/2026/rmf/reglas/regla-2.7.1.1.md   una regla por archivo (el nombre lleva el número sin ceros)
rmf/2026/rmf/_indice.md                  índice con título de cada regla
rmf/2026/rmf/_meta.json                  sha256 del PDF, conteo, primera y última regla
rmf/2026/rmf/glosario.md               glosario y "Objeto de la Resolución"
rmf/2026/rmf/preambulo.md              considerandos
rmf/2026/rmf/transitorios.md           transitorios finales y firmas
```

Front matter de cada regla: `regla`, `titulo`, `ubicacion`, `estatus`, `pagina_pdf`, `fundamento` (texto exacto de la línea en cursiva), `referencias_leyes` (por ejemplo `{"CFF": ["29", "29-A"]}`), `referencias_reglas` y, si algún fragmento del fundamento no se pudo interpretar (por ejemplo "Decretos región fronteriza norte 30/12/2020 Segundo"), `referencias_parcial: true`. **El texto de `fundamento` es el que manda;** las referencias separadas son un apoyo.

## Cómo se lee el PDF

La RMF no se corta por "Artículo N.". Distingue cada parte por **tipografía**, así que se lee con `pdftohtml -xml` (negrita, cursiva y posición) y no con `pdftotext`:

- Número de regla: negrita en el margen izquierdo (a la izquierda de x=200; las menciones a otras reglas dentro del texto caen en x>=230). Hasta cinco niveles: hay 19 reglas como 2.7.7.1.1 bajo una "Subsección".
- Título: negrita, justo arriba del número. Fundamento: cursiva, al final de la regla.
- Encabezados Título/Capítulo/Sección: negrita y centrados. Se parten entre líneas y entre páginas, y quedan pegados al título de la regla siguiente; se separan con el texto exacto del **índice ("Contenido") del propio PDF**.
- Párrafos: por espacio vertical (23 px o más entre párrafos, 16 a 18 dentro de uno). Fracciones e incisos, cada uno en su párrafo.
- Tablas: un bloque ```text. Son de mejor esfuerzo: el texto no se pierde, pero una celda con varias líneas puede quedar intercalada (p. ej. regla 2.14.10). Texto justificado con huecos anchos no se toma por tabla.

## Controles

`scripts/validar.py` (y el CI) revisa: nombres vs front matter, sin reglas repetidas ni huecos de numeración dentro de cada capítulo, título y texto no vacíos, sha256 consistente, y que **cada artículo citado en el fundamento exista** en `leyes/` (para las leyes que ya están en la base). Con `--pdf` y el PDF en `fuentes/2026/RMF.pdf`, cuenta las reglas con una ruta distinta (`pdftotext -layout`, sin tipografía) y exige el mismo número.

Medidas al construirla (2026-11-05): 1,208 reglas sin huecos ni repetidas; cruce independiente 1,208 = 1,208; 2,852 referencias a artículos de las leyes que ya están en la base y ninguna apunta a un artículo inexistente; comparando palabra por palabra el texto del PDF contra lo escrito, falta solo una palabra que el PDF parte en dos fragmentos ("denomina" + "da") y que aquí queda unida.

## Casos que se vieron y por qué el extractor es como es

- Un encabezado de capítulo y el título de la regla pueden quedar separados por un salto de página, así que la separación por espacio vertical no basta; por eso se usa el índice del PDF.
- En varias reglas, a veces un fragmento (p. ej. `RMF 5.2.28.`) queda sin cursiva. Se toma la línea como fundamento si tiene algún fragmento en cursiva.
- Dos reglas no traen fundamento (1.3 y 9.1.10): es como las imprime el PDF.
- La regla 2.4.17 trae el número en negrita y el punto en otro fragmento sin negrita.
- Las 19 reglas de cinco niveles (2.7.7.1.1 a 2.7.7.2.6) se perdieron en la primera versión: quedaban pegadas dentro de la 2.7.6.4, y el cruce con `pdftotext` coincidía porque usaba el mismo patrón de número. Ahora el cruce acepta hasta siete niveles, de modo que un nivel desconocido para el extractor hace que los conteos difieran.
