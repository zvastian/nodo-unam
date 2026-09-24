# ADR-0009: Recalculo de `grado_norm`, fix de `origen`, y alcance del dataset público de Kaggle

- **Estado**: Aceptado (2026-09-20).

## `grado_norm` — recalculado desde cero

Investigación: la función correcta ya existía en el pipeline (`normalizar_marc_recovered.py:106-107`, usada solo para registros MARC — maneja bien acentos y "ñ" vía descomposición Unicode). El lado de `base6` tenía el bug de no-determinismo (mismo `grado` → dos `grado_norm` distintos, 286 casos) pero **no se encontró código fuente que lo calculara** — probablemente vivía en un notebook ya no disponible. No tiene caso perseguir un bug en código inexistente.

**Decisión**: recalcular `grado_norm` para las 609,156 filas con la misma función ya usada correctamente en la mitad MARC (`pipeline/recalcular_grado_norm.py`). Resultado: 1,728 → 1,437 valores únicos, determinismo verificado (0 valores de `grado` con más de un `grado_norm`), 120,815 filas afectadas. Backup: `base7_kaggle_clean.before_grado_norm_recalculo_2026-09-20.parquet`.

## `origen` — corregido

Mismo patrón de `programa`: `EXTERNAS E INCORPORADAS` (33,437) y `externa/incorporada` (6,650) eran la misma categoría en dos formatos. Fusionado a `EXTERNAS E INCORPORADAS`. `IPN` y 1 fila vacía (1 cada uno) se dejaron sin tocar — volumen insuficiente para inferir con confianza. Backup: `base7_kaggle_clean.before_origen_fix_2026-09-20.parquet`.

## Alcance del dataset público (Kaggle) — decisiones de esta sesión

- **`texto_completo_url` se excluye del release de Kaggle.** No es un problema de limpieza: el proveedor de origen cambió y las URLs scrapeadas ya no son válidas (no es que estén mal formateadas, es que apuntan a un sistema que ya no existe así). Arreglar el artefacto `\");` no serviría de nada porque el link de fondo también cambió. Queda pendiente como tarea futura: volver a scrapear URLs vigentes antes de considerar esta columna otra vez.
- **Nombres de autores/asesores se excluyen del dataset público**, decisión de privacidad del usuario — un CSV masivo descargable con 609,156 nombres reales es una superficie de exposición distinta a mostrarlos uno por uno en la app interactiva. Resuelve la pregunta abierta desde el PRD (§6, licenciamiento/PII).
- `autor_ui`/`asesor_ui` se excluyen por ser campos de conveniencia de UI, no analíticos (decisión ya tomada por el usuario).

## Pendiente

- Definir el script de export que derive el parquet/CSV de Kaggle desde `base7_kaggle_clean.parquet`, aplicando la exclusión de columnas de arriba.
- Actualizar `PRD.md` §6 para reflejar que la decisión de nombres ya está tomada (sin ellos en el dataset público).
