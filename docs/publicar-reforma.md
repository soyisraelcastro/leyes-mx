# Procedimiento: promover una reforma publicada a `leyes/`

Aplica cuando el DOF publique el decreto de una reforma que estaba como proyecto en `proyectos/<año>/` (por ejemplo la LISR 2027). Mientras no se publique en el DOF, **no se promueve nada**.

## 0. Confirmar la publicación

- Abrir el decreto en dof.gob.mx. Anotar: fecha de publicación, fecha de entrada en vigor y a qué leyes reforma.
- Comparar el decreto publicado con la minuta/iniciativa; el texto publicado es el único que cuenta.

## 1. Esperar o forzar el PDF actualizado de la Cámara

El texto consolidado sale del PDF de la Cámara de Diputados (no de lo que dice el proyecto). Cuando la Cámara lo actualice, su encabezado "Última Reforma DOF" cambia a la fecha de publicación.

```bash
python3 scripts/revisar_reformas.py --dry-run          # confirma el cambio de fecha en la(s) ley(es)
```

Si el PDF de la Cámara aún no refleja el decreto, esperar. No se arma el texto a mano con los proyectos.

## 2. Generar el año nuevo

Si el decreto entra en vigor en `<año>` (p. ej. 2027) y `leyes/2026/` queda congelado:

```bash
mkdir -p fuentes/2027
python3 scripts/extraer.py LISR --anio 2027        # descarga el PDF y genera leyes/2027/LISR/
python3 scripts/copiar_anio.py --desde 2026 --hasta 2027 LIVA CFF LFT RLISR RLIVA RCFF   # solo las que NO cambiaron
```

Para las que no cambiaron, verificar antes con `revisar_reformas.py` que el PDF y la fecha de reforma son los mismos. Después de generar el año, cambiar `anio_vigencia_actual` en `fuentes.json` solo cuando corresponda (1 de enero del año nuevo, o la fecha de entrada en vigor).

Si el decreto entra en vigor a mitad del año actual, regenerar en `leyes/<año actual>/` (`scripts/revisar_reformas.py --aplicar`).

## 3. Validar

```bash
python3 scripts/validar.py --pdf
python3 scripts/verificar_cobertura.py --anio 2027
```

Revisar a mano 3 o 4 artículos de los que cambiaron contra el DOF.

## 4. Retirar los proyectos promovidos

- Borrar de `proyectos/2027/<SIGLA>/` los archivos de la ley ya promovida (o moverlos a `proyectos/2027/historico/<SIGLA>/` con el estado `publicado_dof`).
- Actualizar `proyectos/2027/estado.json`: hito `publicado_dof` con fecha y fuente (DOF), `es_ley_vigente: true` para lo ya publicado, y quitar la ley de `leyes_vigiladas`.
- Actualizar `proyectos/2027/README.md` (línea de tiempo).
- Si quedan leyes en trámite (por ejemplo la LIF se publica antes que la LISR), se promueve por ley, no en bloque.

## 5. Publicar

Un PR con: `leyes/2027/...`, estado actualizado, y en la descripción el enlace al decreto del DOF. Sin co-autorías ni firmas (ver CONTRIBUTING.md).

## Estados válidos de un proyecto

`iniciativa` -> `aprobado_camara` -> `aprobado_senado` -> `publicado_dof`. Solo `publicado_dof` justifica mover algo a `leyes/`.
