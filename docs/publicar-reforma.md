# Procedimiento: promover una reforma publicada a `leyes/`

Aplica cuando el DOF publique el decreto de una reforma que estaba como proyecto en `proyectos/<año>/` (por ejemplo la LISR 2027). Mientras no se publique en el DOF, **no se promueve nada**.

Una reforma no duplica la ley: se agrega una **capa** `leyes/<año>/<SIGLA>/` que guarda solo los artículos que cambian y hereda el resto de la capa anterior. Modelo y reglas completas en [criterio-anios.md](criterio-anios.md). `leyes/2026/` no se toca.

## 0. Confirmar la publicación

- Abrir el decreto en dof.gob.mx. Anotar: fecha de publicación, fecha de entrada en vigor (será el `vigente_desde` de la capa) y a qué leyes reforma.
- Comparar el decreto publicado con la minuta/iniciativa; el texto publicado es el único que cuenta.

## 1. Esperar o forzar el PDF actualizado de la Cámara

El texto consolidado sale del PDF de la Cámara de Diputados (no de lo que dice el proyecto). Cuando la Cámara lo actualice, su encabezado "Última Reforma DOF" cambia a la fecha de publicación.

```bash
python3 scripts/revisar_reformas.py --dry-run          # confirma el cambio de fecha en la(s) ley(es)
```

Si el PDF de la Cámara aún no refleja el decreto, esperar. No se arma el texto a mano con los proyectos.

## 2. Generar la capa del año nuevo

Si el decreto entra en vigor en `<año>` (p. ej. 2027) y `leyes/2026/` queda como está:

```bash
# tablas transcritas: si no cambian, copiar tablas/2026/<SIGLA>/ a tablas/2027/<SIGLA>/ antes (si no, 96 y 152 de la LISR salen como "modificados")
python3 scripts/diferenciar.py LISR CFF LIVA LFT RLISR RLIVA RCFF ... --anio 2027 --vigente-desde 2027-01-01 \
    --decreto "DOF 2026-12-DD" --nota "Decreto por el que se reforman..." --fecha-dof 2026-12-DD --dry-run   # primero solo reporta
python3 scripts/diferenciar.py ...  (lo mismo, sin --dry-run)
```

Por cada ley el script descarga el PDF, extrae el texto completo a un directorio **temporal**, compara cada artículo contra el texto heredado (cuerpo normalizado: espacios; no el front matter) y escribe en `leyes/2027/<SIGLA>/` solo los que difieren, más `_meta.json` (`hereda_de`, `vigente_desde`, `articulos_modificados`, `articulos_nuevos`, `fuente`), el `_indice.md` completo y, si cambiaron, `transitorios.md`. Una ley que no cambió queda solo con `_meta.json`. Reemplaza a `scripts/copiar_anio.py` (obsoleto).

Revisar el resumen: los artículos que lista deben ser los que dice el decreto. Si el script dice que un artículo del año anterior ya no está en el texto nuevo, se detiene (una derogación aparece en el PDF como "Se deroga", no como ausencia): revisar el extractor.

Cambiar `anio_vigencia_actual` en `fuentes.json` solo cuando corresponda (1 de enero del año nuevo, o la fecha de entrada en vigor). Una reforma de vigencia inmediata a mitad de año se reescribe con `scripts/revisar_reformas.py --aplicar` (reescribe el delta de la capa del año); una reforma con fecha posterior dentro del mismo año cabe como otra capa con `vigente_desde` de esa fecha (ver criterio-anios.md).

## 3. Etiquetar y validar

```bash
python3 scripts/etiquetar.py
python3 scripts/validar.py --pdf
python3 scripts/verificar_cobertura.py --anio 2027
```

`validar.py` comprueba las reglas de capas (herencia, fechas, `articulos_modificados`, nuevos contra heredados) y la secuencia sobre la vista completa. Revisar a mano 3 o 4 artículos de los que cambiaron contra el DOF.

## 4. Retirar los proyectos promovidos

- Borrar de `proyectos/2027/<SIGLA>/` los archivos de la ley ya promovida (o moverlos a `proyectos/2027/historico/<SIGLA>/` con el estado `publicado_dof`).
- Actualizar `proyectos/2027/estado.json`: hito `publicado_dof` con fecha y fuente (DOF), `es_ley_vigente: true` para lo ya publicado, y quitar la ley de `leyes_vigiladas`.
- Actualizar `proyectos/2027/README.md` (línea de tiempo).
- Si quedan leyes en trámite (por ejemplo la LIF se publica antes que la LISR), se promueve por ley, no en bloque.

## 5. Publicar

Un PR con: `leyes/2027/...`, `temas/2027/...`, estado actualizado, y en la descripción el enlace al decreto del DOF. Sin co-autorías ni firmas (ver CONTRIBUTING.md).

El Release de datos (`scripts/empaquetar_datos.py`, lo corre `.github/workflows/publicar-datos.yml`) materializa por omisión la vista completa de cada año, de modo que los clientes `npx leyes-mx` ya publicados siguen funcionando. No hace falta nada más.

## Estados válidos de un proyecto

`iniciativa` -> `aprobado_camara` -> `aprobado_senado` -> `publicado_dof`. Solo `publicado_dof` justifica mover algo a `leyes/`.
