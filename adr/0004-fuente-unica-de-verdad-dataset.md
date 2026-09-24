# ADR-0004: `data/clean/base7_kaggle_clean.parquet` es la única fuente de verdad del corpus

- **Estado**: Aceptado (2026-09-20).

## Contexto

Auditoría de datasets (2026-09-20) encontró ~30 archivos parquet representando el corpus de tesis en distintos puntos de un pipeline sin orquestación (ver Fase 1). Se verificó, contando registros año por año para los 9 años marcados como "recuperados vía MARC" en el README raíz (1905, 1913, 1960, 1980, 1985, 1987, 1989, 1995, 2026):

- **Linaje "base6" (583,470 filas)** — `base.parquet`, `v5.parquet`, `base6.parquet`, `base6_homogeneizada_stream*`, `base_with_ids.parquet`, `t*.parquet`, `plantel_fix_stream/base_plantel_corregido_stream.parquet`, prácticamente todo `data/archive/Old/*.parquet`, y `app/AI Pipeline/Base.parquet` — **todos con el mismo conteo bajo para esos 9 años** (el hueco de scraping original, sin corregir), a pesar de que varios llevan "corregido" en el nombre (esas correcciones fueron de otros problemas — typos, planteles — nunca del hueco de años).
- **Linaje "base7" (609,156 filas)** — `data/archive/base7_full_recovered.parquet` y `data/clean/base7_kaggle_clean.parquet` — coinciden exacto, año por año, con `pipeline/recovery/processed/marc_recovered_normalized.parquet` (la recuperación MARC aislada). El fix está correctamente aplicado aquí.

**Hallazgo crítico**: `app/MI-TESIS-UNAM_github/data/thesis_lookup.parquet` — el archivo que `workshop_service.py` usa como motor SQL (DuckDB) para *todas* las queries de Taller, y el archivo modificado más recientemente de todo el proyecto (2026-09-19) — se construyó a partir de la línea **rota**, no de `base7_kaggle_clean.parquet`. Causa raíz: `scripts/build_thesis_lookup.py` busca su input en rutas hardcodeadas (`base.parquet` dentro del propio repo de la app), sin ninguna referencia a la ubicación real del dataset canónico. Ese `base.parquet` de origen ya ni siquiera existe hoy en el repo — el build no es reproducible.

**Consecuencia funcional**: Taller (Ranking, Burbujas, Heatmap, Series) y probablemente los JSON estáticos pre-generados en `deploy/static/data/workshop/` subcuentan esos 9 años, porque todos dependen de `thesis_lookup.parquet`.

## Decisión

1. `data/clean/base7_kaggle_clean.parquet` es la única fuente de verdad del corpus de tesis, de aquí en adelante. Ningún script de la app o del pipeline debe leer de `base.parquet`, `base6*`, `t*.parquet`, ni de ninguna copia en `data/archive/`.
2. `scripts/build_thesis_lookup.py` debe apuntar su input a `data/clean/base7_kaggle_clean.parquet` (ruta absoluta o parametrizada, no una búsqueda heurística de nombre de archivo) — pendiente de implementar.
3. Regenerar `thesis_lookup.parquet` y, en consecuencia, todos los JSON de `deploy/static/data/workshop/` desde cero contra la fuente corregida — pendiente de ejecutar.

## Consecuencias

- (+) Cierra el hallazgo de que la app en producción sirve datos con el hueco de scraping sin que nadie lo supiera.
- (+) Da un punto de referencia único para cualquier regeneración futura (`build_thesis_lookup.py`, el pipeline semántico, futuros exports).
- (-) Requiere regenerar y volver a desplegar todos los artefactos derivados (`thesis_lookup.parquet`, JSON de Taller, y verificar si el atlas semántico de 50k también necesita reconstruirse — ver nota abajo).
- **Nota abierta**: `app/Nodos/sample_50k_final_15d.parquet` (la muestra que alimenta el atlas semántico de Explorar) está fechada 2026-05-16, antes de que existiera `base7_kaggle_clean.parquet` (2026-06-05). Su distribución de los 9 años, escalada al tamaño de muestra, coincide con la línea rota — pendiente de confirmar con un join directo por `thesis_id` antes de decidir si también se regenera.
