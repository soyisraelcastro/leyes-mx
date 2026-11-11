# Criterio de años de vigencia

`<año>` en `leyes/<año>/` es el **año de vigencia** del texto (el año en que ese texto aplica), no la fecha de descarga. La fecha de descarga va en cada archivo (`fecha_descarga`).

## Reglas

1. Lo vigente hoy (2026-11-02) está en `leyes/2026/`. Cuando una reforma con vigencia 2027 se publique en el DOF, el texto nuevo se genera en `leyes/2027/` y `leyes/2026/` **queda congelado** (no se vuelve a regenerar para esas leyes).
2. Una ley reformada en 2026 con vigencia posterior (por ejemplo, la jornada laboral gradual de la LFT) sigue siendo un solo texto; la gradualidad se documenta con la advertencia de `fuentes.json` y en `transitorios.md`, no duplicando carpetas.
3. Si una ley **no cambió** para 2027, `leyes/2027/<SIGLA>/` se genera copiando 2026 con `scripts/copiar_anio.py`, que reescribe `vigencia_anio`, agrega `copiado_de_anio: 2026` y una nota en `_meta.json`. Cuándo se considera que no cambió: después del 1 de enero de 2027, `scripts/revisar_reformas.py` no reporta cambio en "Última Reforma DOF" ni en el sha256 del PDF de la Cámara, y el estado de `proyectos/2027/` no lista esa ley.
3-bis. **La Ley de Ingresos de la Federación (LIF) es anual**: la de 2026 rige solo en 2026. La de 2027 tendrá su propia carpeta y sigla/entrada en `fuentes.json` y **nunca** se genera con `copiar_anio.py`. Lo mismo para cualquier ordenamiento de vigencia de un solo ejercicio.
4. No se crea `leyes/2027/` por adelantado. Mientras no esté publicada la reforma, 2027 no existe como texto de ley; lo que hay es un proyecto en `proyectos/2027/`.
5. La consulta sin `--anio` usa el año más reciente con datos que **no sea posterior al año en curso**. Así, aunque `leyes/2027/` exista en diciembre de 2026, no se usa hasta enero de 2027.
6. Una ley que cambia a mitad de año (reforma con vigencia inmediata) se regenera dentro del mismo año. El historial queda en git; si hace falta distinguir antes y después, se usa el campo `ultima_reforma_dof` y el tag del commit.

## Qué guarda cada archivo para reconstruir la versión

`vigencia_anio`, `ultima_reforma_dof`, `fecha_descarga`, `sha256_fuente`, `fuente_url`.
