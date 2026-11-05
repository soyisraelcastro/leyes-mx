# Cómo contribuir

## Regla de commits y PRs: sin co-autoría ni firmas

Ningún commit ni PR lleva:

- líneas `Co-Authored-By` (de ninguna persona ni herramienta);
- pies tipo "Generated with ..." / "Generado con ...";
- menciones de herramientas de IA en trailers o pies.

Aplica también a PRs colaborativos de terceros: se pide reescribir el mensaje antes de integrar.

Se hace cumplir en tres puntos:

1. Hook local `.githooks/commit-msg`. Se activa con `sh scripts/instalar-hooks.sh`.
2. Plantilla de PR con casilla de confirmación.
3. CI (`.github/workflows/commits.yml`) que falla si algún commit del PR trae esos patrones.

## Mensajes de commit

En español, cortos y claros. Ejemplos: "Agrega LSS 2026", "Corrige corte del artículo 113-E", "Actualiza LISR por reforma DOF 2027-01-05".

## Reglas de contenido

- El texto legal sale siempre del texto oficial descargado (Cámara de Diputados / DOF). Nunca se escribe ni se corrige a mano un artículo.
- Un artículo con estatus distinto de "vigente" va en `proyectos/`, nunca en `leyes/`.
- Antes de abrir PR: `python3 scripts/validar.py`.
- Para agregar una ley: nueva entrada en `fuentes.json`, `python3 scripts/extraer.py SIGLA` y **`python3 scripts/etiquetar.py`**. Para una resolución de la RMF: `scripts/extraer_rmf.py` y lo mismo. No hace falta tocar código.
- **Todo ordenamiento se etiqueta por temas.** El índice `temas/` se genera de `temas.json` y de todo lo que hay en `leyes/` y `rmf/`; `scripts/validar.py` (y el CI) falla si no está al día. Al agregar un ordenamiento, además de regenerar: mira la cobertura que imprime `etiquetar.py` (un ordenamiento con muy pocos documentos etiquetados casi siempre es un hueco del vocabulario) y agrega a `temas.json` las palabras propias de esa materia. Ver [docs/temas.md](docs/temas.md).
- Texto plano en español, comillas dobles rectas, sin raya larga.

## Glosario de sinónimos contables

`glosario.json` amplía las consultas de `buscar` con los términos que usa la ley ("actualización" encuentra "accesorios de las contribuciones"). Para aportar una entrada (formato completo en [docs/glosario.md](docs/glosario.md)):

1. Parte de una pregunta real que no encontró lo esperado y agrégala a `npm/test/consultas.json` con los artículos esperados y la frase de la ley que los respalda.
2. La entrada lleva disparadores, términos a agregar, al menos un artículo con una `evidencia` **literal** copiada del texto de `leyes/` (nunca de memoria) y una `nota` de por qué existe.
3. Antes del PR: `python3 scripts/validar.py` (verifica que cada artículo exista y que su evidencia esté en el texto), `python3 -I tests/test_glosario.py` y `cd npm && npm test`.
4. Cambiar `glosario.json` no requiere publicar el paquete npm: sale con el siguiente Release de datos (`npx leyes-mx actualizar`).
