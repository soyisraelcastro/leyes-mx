# Integración con Abacus (OpenClaw)

Nada de esto se ejecuta desde este repo: son instrucciones para quien administra el VPS.

## Texto recomendado para `AGENTS.md` de Abacus

```markdown
## Consulta de leyes (leyes-mx)

Para citar leyes o reglamentos fiscales y laborales de México (LISR, LIVA, CFF, LFT, RLISR, RLIVA, RCFF):

1. PRIMERO consulta la base local en `knowledge/leyes-mx/`:
   - Artículo conocido: `python3 knowledge/leyes-mx/scripts/buscar.py obtener LEY ARTICULO`
     (ejemplo: `obtener LISR 113-E`).
   - Tema o palabras clave: `python3 knowledge/leyes-mx/scripts/buscar.py buscar "recargos deducibles" --ley LISR`.
   - Reforma 2027: `python3 knowledge/leyes-mx/scripts/buscar.py estado`.
2. Solo si el artículo o tema no está en la base, busca en la web, y solo en dominios oficiales
   (diputados.gob.mx, dof.gob.mx, sat.gob.mx, gob.mx, senado.gob.mx). Si tampoco ahí lo encuentras,
   responde "no verificado". No completes artículos de memoria.
3. Cita SIEMPRE: ley, artículo, año de vigencia y fecha de última reforma que imprime la base
   (por ejemplo: "LISR art. 28, vigencia 2026, última reforma DOF 2024-04-01").
4. Lee las líneas ">>> ADVERTENCIA" que imprime la base y respétalas (por ejemplo, la jornada laboral
   es gradual: el art. 59 de la LFT dice 40 horas pero en 2026 la jornada aplicable sigue siendo de 48).
5. NUNCA presentes un proyecto como ley. Lo que viene de `proyectos/` o marcado PROYECTO no es ley vigente
   hasta su publicación en el DOF. La reforma fiscal 2027 está en trámite: dilo así y da la fecha del
   estado que reporta `estado`.
6. Los textos son informativos, copiados de la Cámara de Diputados; si hay duda, prevalece el DOF.
```

Ajustar la ruta del script si se instala el paquete (`pip install .` crea el comando `leyes-mx`, equivalente a `buscar.py`).

## Sincronizar el repo al VPS (sugerido, no ejecutado)

Ruta destino sugerida: `/root/.openclaw/workspace-abacus/knowledge/leyes-mx/`.

Opción A, con git (repo público ya publicado):

```bash
ssh VPS 'git clone --depth 1 https://github.com/<usuario>/leyes-mx.git /root/.openclaw/workspace-abacus/knowledge/leyes-mx'
# actualizar:
ssh VPS 'git -C /root/.openclaw/workspace-abacus/knowledge/leyes-mx pull --ff-only'
```

Opción B, con rsync desde la Mac (antes de publicar):

```bash
rsync -a --delete --exclude '.git' --exclude 'build' --exclude 'fuentes' --exclude 'proyectos/*/documentos' \
  ./leyes-mx/ VPS:/root/.openclaw/workspace-abacus/knowledge/leyes-mx/
```

Requisitos en el VPS: `python3` (solo biblioteca estándar; SQLite con FTS5, que trae Python estándar). El índice `build/indice.sqlite` se crea solo la primera vez que se busca.

## Aviso mensual (cron en el VPS)

```cron
0 15 1 * * cd /root/.openclaw/workspace-abacus/knowledge/leyes-mx && python3 scripts/revisar_reformas.py --dry-run
```

Código de salida 0 sin cambios, 1 hay cambios, 2 error; la salida es una o dos líneas de texto, aptas para mandar por Telegram. Con `--dry-run` no escribe nada.
