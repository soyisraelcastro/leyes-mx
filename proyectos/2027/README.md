# Reforma fiscal 2027: estado y proyectos

> **Nada de esta carpeta es ley vigente.** Todo lo que está aquí tiene estatus "proyecto" y solo será ley si se publica en el DOF, a partir de la fecha que diga el decreto publicado. Lo vigente está en `leyes/`.

Estado al **2026-11-02**. Versión legible por máquina: [`estado.json`](estado.json) (el comando `leyes-mx estado` la imprime).

## Resumen

- El Paquete Económico 2027 **no está publicado en el DOF** (no se encontró publicación; el sitio del DOF no respondió a la consulta automática, verificar en dof.gob.mx).
- De las leyes de este repo, la iniciativa del Ejecutivo solo reforma la **LISR**. No hay iniciativa del Ejecutivo para CFF, LIVA ni LIEPS en la Gaceta 7121 (anexos A a N). Otras iniciativas de legisladores sobre CFF que aparecen en la Gaceta no son parte del paquete.
- La reforma a la LISR fue aprobada por la Cámara de Diputados, el Senado la aprobó **con una modificación** y la devolvió a la Cámara el 27 de octubre de 2026. La Cámara todavía debe votar ese cambio.
- La Ley de Ingresos 2027 y la Ley Federal de Derechos pasaron el Senado y esperan publicación (según prensa, sin verificar en fuente oficial del Senado).
- Entrada en vigor prevista de la LISR: 1 de enero de 2027 (transitorio de la iniciativa), si se publica antes.

## Línea de tiempo

Clave: **CONFIRMADO** = documento oficial leído. **PRENSA** = solo notas de prensa. **PENDIENTE** = no ocurrido o no verificable.

| Hito | Fecha | Estado | Fuente |
|---|---|---|---|
| Iniciativa del Ejecutivo (LIF, PEF, CGPE, Ley Federal de Derechos, LISR, Ley Aduanera, Ley de Economía Digital para Pagos Digitales y Electrónicos, Ley General Catastral y Registral) | 2026-09-08 | CONFIRMADO | Gaceta Parlamentaria 7121, anexos A a N: https://gaceta.diputados.gob.mx/Gaceta/66/2026/sep/pef2027.html |
| Dictámenes de la Comisión de Hacienda (LISR, LIF, Ley Federal de Derechos) publicados "para declaratoria de publicidad" | 2026-10-13 | CONFIRMADO | Gaceta 7145, anexos IV, IV-1, IV-2: https://gaceta.diputados.gob.mx/Gaceta/66/2026/oct/20261013.html |
| Aprobación en el pleno de la Cámara de Diputados | 2026-10-13 o 14 | PRENSA | Las notas discrepan en fecha y votos (LISR 349-118 o 322-115; LIF 331-118). No se halló el acta oficial de votación. Indicio oficial indirecto: el Senado devolvió el expediente (siguiente fila). |
| Turno en el Senado a Comisiones de Hacienda y Estudios Legislativos Primera | 2026-10-14 | PRENSA | Comunicado del Senado citado por buscador (no se pudo abrir directamente). |
| Senado aprueba LISR con modificaciones y la devuelve (fracción E del art. 72 constitucional) | 2026-10-27 | CONFIRMADO (el hecho); el contenido del cambio, PRENSA | Oficio DGPL-1P3A.-3160 de la Mesa Directiva del Senado, recibido en la Cámara el 27-oct a las 21:24 h: https://gaceta.diputados.gob.mx/PDF/66/2026/oct/20261028-I-2.pdf . La prensa ubica el cambio en el art. 78-E (excepción de armadoras y gasolineras al mecanismo de control de deducciones). |
| Senado aprueba LIF 2027 y Ley Federal de Derechos sin cambios | 2026-10-27 | PRENSA | Varias notas; votos reportados 79-34 o 74-33 (una nota dice 31-oct). |
| La Cámara dictamina y vota el cambio del Senado | convocada 2026-11-03 | PENDIENTE | Gaceta 7158 (30-oct) convoca a la Comisión de Hacienda a su segunda reunión extraordinaria el martes 3 de noviembre, 9:00 h (la prensa dijo 4 de noviembre; prevalece la Gaceta, verificar). Falta además el pleno. |
| Publicación en el DOF | sin fecha | PENDIENTE | No encontrada al 2026-11-02. |

## Contenido de la LISR proyectada (según la iniciativa)

Entre otros: nuevo Capítulo X del Título II "Del Mecanismo de Control de las Deducciones Autorizadas y de las Pérdidas Fiscales" (arts. 78-A a 78-F), derogación del Capítulo VI del Título II (arts. 59 a 71), cambios al RESICO (art. 113-E: el límite de ingresos pasa de 3.5 a 5 millones de pesos, y 113-F, 113-H), y cambios a los arts. 22, 25, 27, 28, 77, 78, 153, 206, 209 y 214. La minuta del Senado menciona además reformas al art. 147 y derogaciones en los arts. 36 y 74 que la iniciativa no traía. Consultar los archivos, no este resumen.

## Qué hay en esta carpeta

| Ruta | Qué es |
|---|---|
| `LISR/art-*.md` | Un archivo por artículo con el texto de la **iniciativa** (PDF con texto, Anexo E). `estatus: "proyecto"`, `estado_proyecto: "iniciativa"`. Los "..." del decreto significan texto sin cambio. |
| `LISR/transitorios.md` | Artículos Segundo y Tercero (vigencia transitoria) y transitorio único de la iniciativa. |
| `LISR/_comparacion_minuta.md` | Índice por página de la minuta del Senado y similitud OCR frente a la iniciativa (orientativo). |
| `documentos.json` | Lista de PDF oficiales con URL y sha256. |
| `documentos/` | Los PDF (ignorados por git por tamaño, ~110 MB; `python3 scripts/descargar_proyectos.py` los baja y verifica). |
| `estado.json` | Línea de tiempo legible por máquina. |

## Limitaciones declaradas

1. **El texto por artículo es el de la iniciativa, no el de la minuta final.** La Cámara y el Senado lo modificaron. Los dictámenes (13-oct) y la minuta (27-oct) son PDF **escaneados sin capa de texto**; no hay herramienta de OCR en el repo y un OCR no es fiable para texto legal, así que no se trocearon. Para cada artículo, la fuente de verdad del trámite actual es la minuta (`documentos/minuta-Senado-LISR-devuelta-gaceta-7156-I-2.pdf`, 74 páginas; el índice por página está en `LISR/_comparacion_minuta.md`).
2. Los artículos 36 (fracción III, párrafo cuarto), 74 (párrafo segundo) y 147 (fracción VII) aparecen en la minuta pero no en la iniciativa; no tienen archivo aquí.
3. Los dictámenes de LIF y Ley Federal de Derechos no se trocean (la LIF es anual y la Ley Federal de Derechos queda fuera del alcance inicial). Están descargados como PDF.
4. Los votos y fechas de la Cámara y el Senado marcados como PRENSA no están confirmados en fuente oficial.

## Reforma laboral de las 40 horas (no es proyecto)

Ya es **ley publicada**: el decreto que reforma la Ley Federal del Trabajo se publicó en el DOF el **1 de mayo de 2026** y está en vigor desde esa fecha (consta en el PDF de la Cámara, en los transitorios de ese decreto: `leyes/2026/LFT/transitorios.md`). La reducción es **gradual**: jornada semanal de 48 horas en 2026, 46 en 2027, 44 en 2028, 42 en 2029 y 40 en 2030, a partir del 1 de enero de cada año; horas extra de 9 (2026 y 2027), 10, 11 y 12. Por eso el artículo 59 ya dice "cuarenta horas semanales" pero la jornada aplicable en 2026 sigue siendo de 48. La reforma constitucional al artículo 123 se publicó el 3 de marzo de 2026 según prensa (no verificado en el DOF).

## Cuando se publique

Seguir [`docs/publicar-reforma.md`](../../docs/publicar-reforma.md).
