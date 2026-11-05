---
name: leyes-mx
description: Consulta las leyes fiscales y laborales de México (LISR, LIVA, CFF, LFT y reglamentos) en la base local leyes-mx. Úsala ante dudas de ISR, IVA, deducciones, nómina o "qué dice el artículo".
license: MIT
---

# Leyes fiscales y laborales de México (leyes-mx)

Responde consultas fiscales y laborales de México con el texto de la ley, no de memoria. La base está en el equipo del usuario: LISR, LIVA, CFF, LFT, LSS, RLISR, RLIVA, RCFF, RACERF y las tarifas de ISR del Anexo 8 de la RMF, con año de vigencia y fecha de última reforma.

## Cuándo usarla

Antes de responder cualquier consulta fiscal o laboral de México y antes de citar un artículo: ISR, IVA, deducciones, retenciones, CFDI y facturas, aguinaldo, PTU, vacaciones, despido, finiquito, tarifas, multas, plazos de declaraciones, "qué dice el artículo", "fundamento legal". También si el usuario escribe "/leyes-mx".

## Flujo

1. **Reformula con las palabras de la ley.** La búsqueda es léxica: encuentra palabras, no ideas. "Actualizaciones" no encuentra "accesorios de las contribuciones"; "CFDI" no aparece en la ley, que dice "comprobante fiscal digital por Internet"; "PTU" es "participación de los trabajadores en las utilidades de las empresas". Un glosario de sinónimos ayuda y la respuesta declara qué agregó, pero no sustituye este paso.
2. **Busca.** Con el servidor MCP `leyes-mx`: herramienta `buscar` (parámetro `ley` para acotar a LISR, LIVA, CFF, LFT, LSS, RLISR, RLIVA, RCFF o RACERF). Si el artículo ya se conoce, ve directo a `obtener_articulo`.
3. **Lee el artículo completo** con `obtener_articulo`. Los resultados de `buscar` son fragmentos y pueden omitir la excepción o la fracción que cambia la respuesta. Si el texto viene por páginas, lee todas.
4. **Cita.** Ley, artículo, fracción o párrafo (tómalos del texto leído), año de vigencia y fecha de última reforma DOF, tal como los devuelve la herramienta. Ejemplo: "LISR art. 28, fracción I, vigencia 2026, última reforma DOF 2024-04-01". Un artículo derogado no aplica; si se menciona, dilo.
5. **Cuida las advertencias.** Respeta las líneas ADVERTENCIA del artículo (por ejemplo, la jornada laboral de la LFT se reduce de forma gradual) y consulta `obtener_transitorios` antes de afirmar desde cuándo aplica una reforma.

## Herramientas MCP

| Herramienta | Para qué |
|---|---|
| `obtener_articulo(ley, articulo)` | Texto íntegro de un artículo: la fuente para citar. |
| `buscar(consulta, ley?)` | Encontrar artículos por tema. Devuelve fragmentos. `glosario=false` busca solo con las palabras dadas. |
| `obtener_tarifa(tarifa?)` | Tarifas de ISR del Anexo 8 (mensual `B-V`, anual `C-II`, por periodos). Sin argumento, las lista. |
| `obtener_transitorios(ley)` | Transitorios por decreto de reforma. |
| `estado_reforma()` | Seguimiento de la reforma 2027 (proyecto) y última reforma por ley. |
| `listar_leyes()` | Qué cubre la base. |

## Sin el servidor MCP: por terminal

Si las herramientas MCP no están disponibles pero hay terminal, el equivalente es:

```bash
npx leyes-mx buscar "accesorios de las contribuciones recargos" --ley LISR
npx leyes-mx obtener LISR 28
npx leyes-mx tarifa B-V          # mensual; C-II es la anual; sin argumento lista todas
npx leyes-mx reforma             # estado de la reforma en trámite
```

Agrega `--json` para salida estructurada y `--sin-glosario` para no ampliar la consulta. Si el comando no existe o no hay datos, ofrece ejecutar `npx leyes-mx instalar` (necesita Node 20 o superior; si falta Node, instálalo tú con el método propio del sistema del usuario) y avisa que mientras tanto el dato es "no verificado".

## Tarifas de ISR

Las tablas de los artículos 96 y 152 de la LISR son las de la ley: no son las que se aplican en el ejercicio. Para retenciones, pagos provisionales o la declaración anual usa `obtener_tarifa` (Anexo 8 de la RMF), cita el apartado y la fecha de publicación en el DOF, y nunca recites cifras de memoria.

## 2026 contra 2027

- La base trae la ley vigente (año de vigencia 2026 al momento de escribir esto) y, aparte, el seguimiento de la reforma fiscal 2027.
- La reforma 2027 es un **proyecto**: no es ley vigente hasta que se publique en el DOF y solo desde la fecha que indique el decreto. Nunca la presentes como vigente.
- `buscar` y `obtener_articulo` no devuelven proyectos por defecto (`obtener_articulo` solo da ley vigente). Si el usuario pregunta por 2027, usa `estado_reforma`, di que es un proyecto y da la fecha del estado que reporta. Para ver artículos del proyecto, `buscar` con `incluir_proyectos` (por terminal, `obtener --incluir-proyectos`) y marca cada cita como "proyecto, no vigente".
- Si el usuario pide un año concreto, pasa `anio`. Si no hay datos de ese año, dilo.

## Lo que NO está en la base

Reglas y anexos de la Resolución Miscelánea Fiscal (salvo el Anexo 8), jurisprudencia, criterios del SAT o del IMSS y el valor de la UMA. De eso no hay dato local: dilo.

## Si no encuentras algo

1. Prueba una vez más: otra redacción con términos de la ley, otra ley, `obtener_articulo` si sabes el número.
2. Si sigue sin aparecer, di con claridad que **no está verificado en la base local** y **pregunta al usuario si desea que lo busques en internet**. Nunca busques en internet por tu cuenta sin su permiso.
3. Si lo autoriza, usa solo fuentes oficiales (DOF, SAT, Cámara de Diputados) y aclara que ese dato no proviene de la base verificada.
4. No completes artículos, porcentajes ni montos de memoria.

## Aviso

Los textos son informativos, copiados de la Cámara de Diputados; la fuente oficial (DOF) prevalece. No es asesoría legal ni fiscal: presenta la ley y su cita, y deja el criterio profesional a quien consulta.
