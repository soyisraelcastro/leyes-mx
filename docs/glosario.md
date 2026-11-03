# Glosario de sinónimos contables

La búsqueda de `leyes-mx` es léxica (BM25): encuentra las palabras que escribes, no lo que quieres decir. Una persona pregunta por "actualizaciones", "CFDI" o "PTU"; la ley dice "accesorios de las contribuciones", "comprobante fiscal digital por Internet" y "participación de los trabajadores en las utilidades de las empresas". El glosario cierra esa brecha antes de la búsqueda.

Ejemplo real: "fundamento para no deducir actualizaciones" dejaba la LISR 28 en la posición 43 (la fracción I dice "los accesorios de las contribuciones, a excepción de los recargos"; la palabra "actualización" no aparece ahí) y el CFF 17-A y 21 fuera de los primeros 50. Con el glosario quedan en las posiciones 2, 3 y 5.

## Qué hace

Al buscar, si la consulta contiene el disparador de una entrada:

1. **Agrega** términos a la consulta (peso 0.6 frente a las palabras del usuario, y nunca obligatorios: una consulta que ya tenía resultados no los pierde por ampliarse).
2. **Sustituye** siglas que el texto no usa (`ISR`, `PTU`, `CFDI`, `RESICO`...) cuando la entrada lo pide. Una sigla ausente del texto no aporta nada, y una sigla rara (`IVA` aparece en un solo artículo; `SAT` se expande por prefijo a "satelital") sube artículos sin relación.
3. **Relaciona** artículos: los que cita la entrada suben (bono de 0.8 veces el mejor puntaje léxico) y salen marcados `[glosario]`. Respetan los filtros de ley, año y proyectos.
4. **Lo declara.** La respuesta de `buscar` dice "Se amplió la consulta con: ...", qué se sustituyó, qué artículos relacionó y la nota de cada entrada. Con `glosario=false` (MCP) o `--sin-glosario` (CLI) se busca solo con las palabras dadas.

Otras mejoras de la búsqueda que van con él: se ignoran palabras vacías ("para", "de", "los"...) que se expandían por prefijo a "paraestatal"; el plural se reduce a su raíz ("actualizaciones" encuentra "actualización"); y en la búsqueda con todas las palabras, una palabra que no existe en ningún artículo (una sigla) ya no vuelve imposible la búsqueda.

## Dónde vive y cómo llega al usuario

`glosario.json` en la raíz del repo, versionado con git. `scripts/empaquetar_datos.py` lo mete en el paquete de datos (con su sha256 en `INTEGRIDAD.json` y un resumen en `manifest.json`), así que **se actualiza con `npx leyes-mx actualizar` sin publicar una versión nueva de npm**. El almacén lo carga si existe y es válido; si falta o está roto, la búsqueda funciona igual, sin ampliar. `npx leyes-mx estado` y `doctor` lo reportan.

El motor de búsqueda de Python (`scripts/buscar.py`, SQLite FTS5, el que usa Abacus) **no usa el glosario**: es una búsqueda distinta, sin estas mejoras. El glosario es solo del paquete Node. Python solo lo valida (`scripts/validar.py`).

## Formato

```json
{
  "esquema": 1,
  "version": "2026-11-02",
  "entradas": [
    {
      "id": "actualizacion",
      "disparadores": ["actualizacion", "actualizar"],
      "sustituir": ["isr"],
      "relacionar": false,
      "agregar": ["accesorios", "recargos", "no será deducible ni acreditable"],
      "articulos": [
        { "ley": "CFF", "articulo": "17-A", "evidencia": "no será deducible ni acreditable" }
      ],
      "nota": "Por qué la ley dice esto con otras palabras."
    }
  ]
}
```

- `id`: minúsculas, números y guiones; único.
- `disparadores`: frases que activan la entrada (basta una). Se comparan sin acentos ni mayúsculas. Una palabra de 5 o más letras también coincide con sus derivadas (`actualizacion` activa con "actualizaciones"). `"a + b"` exige ambas, en cualquier orden y no necesariamente juntas (`"declaracion anual + fisica"`). Evita disparadores genéricos: `renta` activaría con todo "impuesto sobre la renta".
- `agregar`: palabras o frases de la ley que se suman a la consulta.
- `sustituir` (opcional): palabras sueltas de la consulta que se quitan. Para siglas que el texto no usa.
- `relacionar` (opcional, `true` por omisión): con `false` los artículos no suben en el ranking y solo documentan la entrada. Útil en las siglas (`ISR` no debe subir la LISR 1 en cada consulta).
- `articulos`: al menos uno. `evidencia` es una frase **literal** del artículo (sin distinguir acentos ni mayúsculas) que justifica la entrada.
- `nota`: por qué existe, en una o dos frases, para quien mantiene el glosario y para el modelo que lee la respuesta. Si el dato exacto vive fuera de la base (la tarifa en el Anexo 8, el complemento de pago en la RMF), dilo ahí.

## Cómo aportar una entrada

1. Parte de un caso real: la pregunta que no encontró lo esperado. Agrégala primero a `npm/test/consultas.json` (pregunta, artículos esperados con su top y la frase de la ley en `por_que`) y comprueba que falla: `cd npm && node --test test/consultas.test.js`.
2. Busca en el texto de `leyes/2026/` el artículo correcto y copia una frase literal como `evidencia` (`grep -i` sirve). **No escribas de memoria**: si no está en el texto, no va.
3. Agrega la entrada a `glosario.json`. Cada artículo citado debe existir y estar vigente.
4. Comprueba: `python3 scripts/validar.py` (existencia y evidencia), `python3 -I tests/test_glosario.py` y `cd npm && npm test`. Si la entrada hace que otra consulta de `consultas.json` empeore, ajústala.
5. Texto en español de México, comillas dobles rectas, sin raya larga ni comillas angulares (la validación lo revisa).

## Qué NO va en el glosario

- Cifras, tasas o plazos como respuesta: el glosario solo lleva al artículo; el modelo lo lee completo. (Las notas pueden citar el dato que está en el artículo, como "7 % de la utilidad fiscal", porque la evidencia lo respalda.)
- Términos que la ley ya usa con las mismas palabras: la búsqueda literal ya los encuentra.
- Reglas de la RMF, criterios del SAT o jurisprudencia: no están en la base; la nota debe decir que son "no verificado".

## Limitaciones conocidas

- La búsqueda no indexa los títulos de capítulo y sección (`ubicacion` en el front matter). "Régimen Simplificado de Confianza" solo está ahí, no en el cuerpo de los artículos: por eso la entrada `resico` depende de los artículos que cita. Indexar los títulos mejoraría la búsqueda, pero cambia el puntaje de todos los artículos; queda como mejora aparte.
- Los pesos (0.6 y 0.8) se calibraron con los casos de `npm/test/consultas.json`; son un punto de partida, no una verdad.
- Las 40 entradas iniciales cubren los temas más frecuentes; faltan, por ejemplo, ISN, INFONAVIT, criptomonedas y todo lo de la Ley del Seguro Social (que no está en la base).
