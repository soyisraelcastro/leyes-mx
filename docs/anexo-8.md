# Anexo 8 de la RMF (tarifas de ISR)

Código en `leyes_mx/anexos.py` (extracción, verificación, consulta), `leyes_mx/anexos_validar.py` (validación) y `scripts/extraer_anexo8.py`.

## Qué es y qué no

El Anexo 8 de la Resolución Miscelánea Fiscal para 2026 publica las tarifas de ISR de pagos provisionales, retenciones y cálculo anual. Las tarifas de los arts. 96 y 152 de la LISR (`leyes/`) son las **de la ley**; cada año se actualizan por inflación y para 2026 se aplican las del anexo. Un ejemplo: la mensual de la ley empieza 0.01 a 496.07; la mensual 2026 empieza 0.01 a 844.59.

Fuente única: PDF del SAT, publicado en el DOF el 2025-12-28 ("ANEXOS 4, 5, 6, 8, 15 y 25 de la Resolución Miscelánea Fiscal para 2026"), firmado el 2025-12-17.
`https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rmf/anexos/Anexo-8-RMF-2026_DOF-28122025.pdf` (19 páginas, 308287 bytes, sha256 `69ebaf8a78a3bde5d631ad2a994e81ec6d07e2d4e39085c8c948d138f782c1f4`). El PDF no se versiona (`fuentes/2026/RMF-2026-Anexo-8.pdf`, ignorado); queda su sha256 en `_meta.json`.

## Estructura

```
rmf/<año de vigencia>/anexo-8/<id>.md   una tarifa por archivo (31 en 2026)
rmf/<año>/anexo-8/_indice.md            lista de tarifas con lo que cita el anexo (artículos y reglas)
rmf/<año>/anexo-8/_meta.json            fuente, DOF, fecha de firma, sha256, tamaño, conteo por apartado
```

El año es el de vigencia. El Anexo 8 de 2027 se publicará aparte y va en `rmf/2027/anexo-8/` sin tocar lo de 2026.

Nombres estables (apartado del anexo, tarifa):

| Apartado | Archivos |
|---|---|
| A.I enajenación de inmuebles (art. 126) | `A-I-enajenacion-inmuebles` |
| B.I a B.IV retenciones por trabajo realizado, 7, 10 y 15 días | `B-I-trabajo-realizado`, `B-II-7-dias`, `B-III-10-dias`, `B-IV-15-dias` |
| B.V mensual 2026 (art. 96 LISR, 175 RLISR, regla 3.12.2) | `B-V-tarifa-mensual-2026` |
| B.VI art. 106 por mes | `B-VI-enero` ... `B-VI-diciembre` |
| B.VI arrendamiento (art. 116) y art. 74 opcional | `B-VI-arrendamiento-mensual`, `B-VI-arrendamiento-trimestral`, `B-VI-art-74-primer-semestre`, `B-VI-art-74-segundo-semestre` |
| B.VII RIF bimestral definitivo | `B-VII-rif-bimestral-definitivo` |
| B.VIII RIF por bimestre | `B-VIII-bimestre-enero-febrero` ... `B-VIII-bimestre-noviembre-diciembre` |
| C.I anual 2025, C.II anual 2026 (arts. 97 y 152, regla 3.17.1) | `C-I-tarifa-anual-2025`, `C-II-tarifa-anual-2026` |

Cada archivo: front matter (`documento`, `apartado`, `id`, `titulo`, `aplicable_a`, `vigencia_anio`, `publicado_dof`, `fecha_firma`, `fuente_url`, `fecha_descarga`, `sha256_fuente`, `estatus`, `filas`), el texto introductorio del apartado tal cual del PDF y la tabla (Límite inferior, Límite superior, Cuota fija, % sobre el excedente). Las cifras se copian como las imprime el PDF (por ejemplo la cuota "0" de la primera fila de A.I y C.II).

## Extracción y verificación

`python3 scripts/extraer_anexo8.py` (o `--verificar` para no escribir): descarga si falta, `pdftotext -layout`, quita los encabezados "DIARIO OFICIAL ... Domingo 28 de diciembre de 2025", parte por tarifa (cada tabla termina en la fila "En adelante"; su título es el párrafo previo que empieza con "Tarifa"), y falla sin escribir si algo no cuadra:

1. Aritmética: primer límite inferior 0.01; cada inferior = superior previo + 0.01 (exacto); tasas = las 11 de la ley; cuota fija recalculada = cuota previa + (superior previo - inferior previo) x tasa previa, dentro de una tolerancia medida.
2. Conteo: renglones con 3 o más cifras en el texto crudo (otra regex) = filas parseadas; "En adelante" aparece 31 veces en el texto sin `-layout`; cada cifra de cada fila aparece en el texto sin `-layout`.
3. Corroboración cruzada: el anexo publica idénticas varias tarifas (mensual = enero = arrendamiento mensual; febrero = RIF definitivo = bimestre enero-febrero; etc.); deben coincidir fila por fila.
4. El título extraído de cada tabla debe contener lo esperado de su entrada en el catálogo.

Tolerancia de la cuota fija (por evidencia, ver `leyes_mx/anexos.py`): las tarifas "directas" tienen error máximo de 0.0084 a 0.0152 pesos, así que la tolerancia es 0.02; las "escaladas" (7, 10 y 15 días; febrero a noviembre; bimestres 1 a 5; trimestre; semestre 1) son K veces otra tarifa con cuotas multiplicadas desde valores ya redondeados, y el error crece con K (observado 0.0432 a 0.1000), así que la tolerancia es 0.02 x K. Límite conocido: un error de 0.01 en una cuota fija de una tarifa con K=1 no lo detecta la aritmética sola; lo detectan el cruce con el PDF y la corroboración cruzada.

`python3 scripts/validar.py --pdf` repite todo en cada corrida (verifica las 31 tarifas desde los `.md`; con el PDF local además re-extrae y compara) y comprueba las referencias cruzadas desde la LISR.

## Referencias desde la LISR

`fuentes.json` (LISR, `advertencias` con `en_archivo: true` y `rutas`) hace que `leyes/<año>/LISR/art-0096.md` y `art-0152.md` lleven, debajo del título, el aviso "La tabla de este artículo es la de la ley. Para 2026 se aplica la tarifa actualizada del Anexo 8 de la RMF 2026: ..." y que `_meta.json` lo registre (lo muestra también `obtener`). `tablas/2026/LISR/tablas.json` apunta a la tarifa del anexo con `anexo_8`. El validador comprueba que esas rutas existan. Si se cambian los textos, regenerar con `scripts/extraer.py LISR`.

## Vigilancia

`python3 scripts/revisar_reformas.py --dry-run` compara también el sha256 y el tamaño del PDF del anexo con `_meta.json` y avisa ("PDF distinto"). Nunca regenera solo: el SAT publica modificaciones de anexos durante el año (puede ser otro archivo con otro nombre); se revisa a mano y se corre `scripts/extraer_anexo8.py`. El workflow mensual abre un issue.

## Pendiente: subsidio para el empleo 2026

No está en el Anexo 8 (el PDF no contiene las palabras "subsidio" ni "empleo"). Fuente oficial encontrada: DECRETO por el que se modifica el diverso que otorga el subsidio para el empleo, DOF 2025-12-31 (firmado 2025-12-30), nota 5777649: `https://dof.gob.mx/nota_detalle.php?codigo=5777649&fecha=31/12/2025`. Según su texto ya no hay tabla de montos variables: hay un subsidio mensual como porcentaje del valor mensual de la UMA, con un tope de ingresos mensuales. Por eso no es una tarifa para este formato y **no se incorporan cifras** hasta definir cómo modelarlo (decreto con transitorios, UMA mensual vigente y el caso especial de enero de 2026). Pendiente.
