# ADR-0006: Estandarización de `programa` — minúscula sin acentos

- **Estado**: Aceptado (2026-09-20).

## Contexto

Análisis de `programa` (1,407 valores únicos) con las mismas dos técnicas usadas en `plantel` (ADR-0005) encontró un problema de naturaleza distinta y mucho mayor escala:

- **274 grupos de duplicados por mayúscula/acento**, afectando **497,296 filas (81.6% del corpus completo)**. Patrón dominante: la misma palabra exacta almacenada en minúscula-sin-acento (mayoría) y en Título-Con-Acentos (minoría, pero con miles de filas cada una) — ej. `derecho` (70,502) vs `Derecho` (8,473). A diferencia de `plantel`, el riesgo de fusionar por error dos programas reales distintos es bajo: dos strings que solo difieren en caja/acento son, con certeza práctica, el mismo programa.
- **36 valores con corrupción de "ñ" → espacio** (6,485 filas) — el mismo bug ya diagnosticado en `grado_norm`, pero presente en el dato *crudo* de `programa`, confirmando que es un bug de una función de limpieza compartida en el pipeline, no un accidente aislado de una columna derivada.
- **121 pares candidatos por similitud de texto**, de los cuales la mayoría son **falsos positivos**: especialidades médicas reales y distintas (ej. Neurología/Nefrología/Neumología pediátrica), idiomas distintos, ramas distintas de química (orgánica/inorgánica), y una categoría recurrente de **ambigüedad título-vs-materia** (ej. "Ingeniero Civil" vs "Ingeniería Civil", "Químico Industrial" vs "Química Industrial") que no se resuelve por similitud de texto sin más contexto.

## Decisión

1. `programa` se estandariza a un **único campo canónico en minúscula sin acentos** — no se crea una columna `programa_display` separada (a diferencia de `plantel`). La UI presentará el valor con una fuente de solo mayúsculas, por lo que la capa de presentación no depende de cómo se almacene el acento/caja en el dato.
2. Orden de operaciones (cada paso depende del anterior):
   - Reparar la corrupción de "ñ" en el dato crudo (debe hacerse antes de normalizar, o la "ñ" no se recupera).
   - Normalizar TODA la columna a minúscula sin acentos — función pura aplicada uniformemente, no un mapeo grupo por grupo.
   - Fusionar los typos genuinos confirmados a mano que la normalización de caja/acento no resuelve por sí sola (17 casos).
3. Casos de **ambigüedad título-vs-materia** (ingeniero/ingeniería, químico/química, físico/física) se dejan sin fusionar — es una distinción real y recurrente en el catálogo, no un error de captura, y fusionar por similitud de texto ahí sería sobre-generalizar.
4. Pares de doble titulación con orden de palabras invertido (ej. "Administración, Licenciatura en Contaduría" vs "Contaduría, Licenciatura en Administración") se preservan tal cual — invertir el orden podría cambiar cuál título es el principal.

## Resultado

- `programa`: 1,407 → 1,127 valores únicos.
- 53,431 filas normalizadas por el paso de minúscula/sin acento (incluye la reparación de "ñ" en 6,485 de ellas).
- 17 fusiones adicionales de typos confirmados (280 filas).
- 43 pares evaluados y explícitamente descartados — `pipeline/audits/programa_descartados_2026-09-20.csv`.
- Validado: 609,156 filas y `thesis_id` únicos intactos; 0 mayúsculas, 0 acentos y 0 corrupción de "ñ" residual verificado sobre la columna completa.
- Backup: `data/clean/base7_kaggle_clean.before_programa_estandarizacion_2026-09-20.parquet`. Script: `pipeline/estandarizar_programa.py`.

## Nota para el pipeline (Fase 1)

La corrupción de "ñ" confirmada en dos columnas independientes (`grado_norm`, `programa`) sugiere una función de limpieza de texto compartida con un bug — vale la pena localizarla en `pipeline/` y corregirla en la fuente antes de que aparezca en una tercera columna aún no auditada.
