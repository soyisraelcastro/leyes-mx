# Subsidio para el empleo (SPE) 2026

Código en `leyes_mx/spe.py` (extracción, controles y validación); script `scripts/extraer_spe.py`; datos en `decretos/2026/spe/`. Servidor: herramienta `obtener_subsidio_empleo`; terminal: `npx leyes-mx subsidio [DOCUMENTO]`.

## Por qué no es una tarifa

Desde el "Decreto que otorga el subsidio para el empleo" (DOF 01-05-2024) la tabla de montos variables se sustituyó por una cuota mensual igual a un porcentaje del valor mensual de la UMA, para quien tenga ingresos mensuales de hasta un tope. Por eso no está en el Anexo 8 de la RMF ni en el art. 96 de la LISR, y no cabe en `rmf/<año>/anexo-8/` (que es de tarifas con filas). Se guarda como decretos del DOF.

## Qué hay

```
decretos/2026/spe/decreto-2024-05-01.md        DOF 01-05-2024, nota 5725287, completo
decretos/2026/spe/modificacion-2024-12-31.md   DOF 31-12-2024, nota 5746529 (rigió 2025; superada)
decretos/2026/spe/modificacion-2025-12-31.md   DOF 31-12-2025, nota 5777649 (rige desde 01-01-2026)
decretos/2026/spe/uma-2025.md                  INEGI, DOF 10-01-2025, nota 5746930
decretos/2026/spe/uma-2026.md                  INEGI, DOF 09-01-2026, nota 5778072
decretos/2026/spe/vigente-2026.md              consolidado (ver abajo)
decretos/2026/spe/_meta.json, _indice.md       parámetros, sha256 de cada texto, avisos
```

Cada decreto es el texto del DOF sin parafrasear (considerandos, artículos, transitorios, firma y notas), con front matter: `publicado_dof`, `nota_dof`, `fuente_url`, `fecha_descarga`, `sha256_texto` y `estatus`.

## Cifras 2026 (decreto del 31-12-2025, verificadas contra el texto)

| Concepto | Valor |
|---|---|
| Tope de ingresos mensuales | $11,492.66 |
| Subsidio mensual máximo | valor mensual de la UMA x 15.02% |
| Enero de 2026 (transitorio segundo) | valor mensual de la UMA x 15.59% |
| Pagos por periodos menores a un mes | (UMA mensual x porcentaje) / 30.4 x días del periodo; sin exceder el máximo mensual |
| Pago único de varios meses | (UMA mensual x porcentaje) x número de meses |

La UMA mensual es la que publica el INEGI en el DOF y se cita del DOF, no se inventa: 2025, diario $113.14, mensual $3,439.46, anual $41,273.52 (vigente del 01-02-2025 al 31-01-2026, es la que aplica a enero de 2026); 2026, diario $117.31, mensual $3,566.22, anual $42,794.64 (desde el 01-02-2026). `leyes_mx/spe.py` comprueba que el mensual sea el diario por 30.4 y el anual el mensual por 12.

## Lo que NO es texto del DOF

- `calculo_derivado` en `_meta.json`: UMA mensual x porcentaje, redondeado a centavos (enero $536.21; febrero a diciembre $535.65). El decreto no fija redondeo, y su considerando cita $536.22 para 15.02% (no coincide con 15.02% de la UMA mensual publicada: $535.65). Se muestra marcado como cálculo derivado; para un monto exacto, el usuario debe cotejar con el SAT.
- `vigente-2026.md`: el decreto de 2024 con los párrafos 1, 3, 4 y 5 del Artículo Segundo sustituidos mecánicamente por los del decreto de 2025 (los párrafos 2, 6 y 7 los conserva la reforma con "..."). Lo arma el script, lo marca como no oficial y la validación regenera y compara. Para citar, usar cada decreto.
- Modificaciones posteriores al 31-12-2025: no se encontraron al 2026-11-11, pero la búsqueda no es exhaustiva (`no_verificado` en `_meta.json`, y la herramienta lo repite).

## Verificación

`python3 scripts/extraer_spe.py` descarga las cinco notas del DOF y falla sin escribir si algo no cuadra: el título y la fecha de cada nota, 15.02% en los cuatro párrafos y el transitorio, 15.59%, $11,492.66 en cifra y letra, la entrada en vigor, los valores de la UMA en el texto del INEGI y la aritmética diario/mensual/anual, y que el Artículo Segundo consolidado ya no conserve cifras de 2024 ni de 2025. `--verificar` no escribe; `--validar` revisa lo escrito sin red (sha256 del texto, consolidado regenerado, parámetros). `scripts/validar.py` (y el CI) corre esa validación.

## Año siguiente

Cada diciembre se publica una reforma del Artículo Segundo y en enero el INEGI publica la UMA: agregar sus notas a `FUENTES` en `leyes_mx/spe.py` y los nuevos parámetros, y crear `decretos/<año>/spe/`.
