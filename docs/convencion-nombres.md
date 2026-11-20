# Convención de nombres

## Archivos

`leyes/<año>/<SIGLA>/art-<número a 4 dígitos>[-<sufijo>...].md`

- El número base va con ceros a la izquierda a 4 dígitos para que el orden alfabético coincida con el numérico (`art-0028.md`, `art-1010.md`).
- Cada sufijo se separa con guion. Hay dos tipos:
  - **Letra** en mayúscula (A, B, ... Z): `art-0113-E.md`.
  - **Palabra multiplicativa** en minúscula y sin acento: `bis`, `ter`, `quater`, `quinquies`, `sexies`, `septies`, `octies`, `nonies`, `decies` (y las latinas `quintus`, `sextus`, ...): `art-0028-bis.md`.
- **Número tras la palabra**: la Ley del INFONAVIT y la LSAR numeran artículos "Bis 1" a "Bis 6" ("Artículo 18 Bis 1", "Artículo 51 Bis 6", "Artículo 107 bis 1"). El número es otro sufijo, solo válido después de una palabra: `art-0018-bis-1.md`, id `18-bis-1`. "18 1" o "18-A-1" no son ids válidos.
- Se pueden combinar en el orden en que aparecen en el texto oficial: "Artículo 32-B Bis" es `art-0032-B-bis.md`; "Artículo 1o.-A Bis" es `art-0001-A-bis.md`.
- La letra Ñ (LFT 353-Ñ) se escribe `NN` en el nombre de archivo para mantenerlo en ASCII: `art-0353-NN.md`. En el front matter y en las consultas sigue siendo `353-Ñ`.
- Los ordinales "1o.", "3o." se descartan: `art-0003-bis.md` es "Artículo 3o. Bis".

Archivos especiales por ley: `_indice.md`, `_meta.json`, `transitorios.md`.

## Identificador de artículo (campo `articulo`)

Texto sin ceros: `"28"`, `"113-E"`, `"28-bis"`, `"32-B-bis"`, `"353-Ñ"`, `"18-bis-1"`. Es lo que se usa en las consultas.

El CLI y la biblioteca normalizan lo que escriba el usuario: `113 E`, `113-e`, `113E`, `28 bis`, `28-Bis`, `Artículo 1o.-A`, `82 Quáter` se resuelven al mismo identificador canónico.

## Orden

Dentro de un mismo número: letras (A, B, C, ...) y después palabras (bis, ter, ...); una palabra después de una letra va tras ella (`32-B` < `32-B-bis` < `32-C`), y el número tras la palabra va antes de la palabra siguiente (`18-bis` < `18-bis-1` < `18-bis-2` < `18-ter`).

Compatibilidad: el cliente npm hasta la 0.4.0 no reconoce el sufijo numérico; con un paquete de datos nuevo sigue funcionando para todo lo demás y simplemente no ve esos 10 artículos (`idDesdeArchivo` los descarta) hasta que se actualice el paquete npm.

## Carpetas

- `leyes/<año>/<SIGLA>/`: solo texto con estatus `vigente` o `derogado`.
- `proyectos/<año>/<SIGLA>/`: solo estatus `proyecto`. Mismo formato de nombres.
