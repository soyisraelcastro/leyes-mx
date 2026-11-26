# Integración con Abacus (OpenClaw)

Nada de esto se ejecuta desde este repo: describe cómo está instalado leyes-mx en el VPS de Abacus y cómo se mantiene. Estado verificado el 2026-11-26 (paquete 0.5.0, datos 2026.11.26).

## Cómo está instalado

Abacus usa el **paquete npm** (`leyes-mx`) como servidor MCP. El motor de Python (`scripts/buscar.py`) ya no se usa en el VPS.

- Paquete global: `npm install -g leyes-mx` deja el comando en `/usr/bin/leyes-mx`.
- Datos: en `/root/.leyes-mx/` (`actual` y `anterior` son la versión instalada y la previa; `datos/` guarda cada versión). Los baja `leyes-mx actualizar` del último Release de datos de GitHub y verifica su sha256.
- Servidor MCP, en `/root/.openclaw/openclaw.json`:

  ```json
  "mcp": {
    "servers": {
      "leyes-mx": { "command": "/usr/bin/leyes-mx", "args": ["servir"] }
    }
  }
  ```

- Dentro de `exec`, Abacus llama las herramientas en camelCase: `MCP.leyesMx.buscar(...)`, `obtenerArticulo`, `obtenerRegla`, `temas`, `obtenerTarifa`, `obtenerTransitorios`, `obtenerSubsidioEmpleo`, `listarLeyes`, `estadoReforma`.

## Actualización semanal

Cron de root, domingo 4:00 am hora de México (10:00 UTC):

```cron
0 10 * * 0 /root/bin/leyes-mx-semanal.sh >> /var/log/leyes-mx-semanal.log 2>&1
```

`/root/bin/leyes-mx-semanal.sh`:

1. `npm install -g leyes-mx@latest` y `leyes-mx actualizar`.
2. Si no cambió ni el paquete ni los datos, termina.
3. Corre `leyes-mx doctor`. Si falla, revierte los datos (`leyes-mx revertir`) y reinstala la versión anterior del paquete.
4. Reinicia el gateway: `systemctl --user restart openclaw-gateway.service` (con `XDG_RUNTIME_DIR=/run/user/0`).

Para no esperar al domingo (por ejemplo, tras publicar una versión), se corre el mismo script a mano:

```bash
ssh VPS '/root/bin/leyes-mx-semanal.sh 2>&1 | tee -a /var/log/leyes-mx-semanal.log'
```

Qué llega por cada vía:

- **Release de datos** (sale solo al hacer merge a `main` de cambios en leyes, RMF, tablas, `glosario.json` o temas): textos, glosario e índice de temas.
- **Paquete npm** (se publica a mano, ver [npx.md](npx.md)): el código del servidor, incluida la búsqueda. Un cambio en cómo busca `buscar` no llega a Abacus hasta publicar una versión nueva del paquete.

## Texto recomendado para `AGENTS.md` de Abacus

El `AGENTS.md` vive en `/root/.openclaw/workspace-abacus/`. Lo esencial sobre leyes-mx:

```markdown
1. *leyes-mx* — base local verificada (leyes, reglamentos, reglas de la RMF 2026 y tarifas de ISR del Anexo 8). Si no sabes si un ordenamiento está, consulta `listarLeyes` antes de decir que no lo tienes.
   - `buscar` para encontrar el tema, con las palabras de la ley ("accesorios de las contribuciones", no "actualizaciones"). Devuelve artículos y, aparte, reglas de la RMF; con `ley: "RMF"` busca solo en las reglas.
   - `temas` para ver todo lo que una materia toca en leyes, reglamentos y reglas. Es un índice: después lee cada artículo o regla.
   - `obtenerArticulo` y `obtenerRegla` para leer el texto completo antes de citar. La RMF es el texto del DOF del 28-12-2025, SIN las modificaciones de 2026: repite el aviso que trae la herramienta.
   - Las tarifas de ISR salen de `obtenerTarifa` (Anexo 8), nunca de memoria.
2. Cita SIEMPRE ley, artículo (o regla), fracción o párrafo, año de vigencia y fecha de última reforma DOF que devuelve la herramienta.
3. Respeta las líneas ADVERTENCIA. Un proyecto de reforma no es ley vigente hasta su publicación en el DOF.
4. Solo si leyes-mx responde NO VERIFICADO, busca en fuentes oficiales (DOF, SAT, Cámara de Diputados) y aclara que ese dato no viene de la base verificada.
```

## Búsqueda web de Abacus (fuera de leyes-mx)

Cuando leyes-mx no encuentra algo, Abacus busca en internet con Gemini: `tools.web.search.provider: "gemini"` en `openclaw.json`, con la llave `GEMINI_API_KEY` de `/root/.openclaw/.env`. Un `HTTP 402` en esa búsqueda es falta de saldo o de facturación en el proyecto de Google de esa llave, no un problema de leyes-mx (pasó en noviembre de 2026).
