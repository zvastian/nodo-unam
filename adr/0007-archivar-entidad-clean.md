# ADR-0007: Remover `entidad_clean` del dataset limpio principal, archivarla aparte

- **Estado**: Aceptado (2026-09-20).

## Contexto

`entidad_clean` (86.51% poblado) resultó ser, al investigarla, un campo de **linaje interno del pipeline** — no un duplicado descuidado de `plantel_estandarizado` como se sospechó inicialmente:

- **Origen**: para registros MARC, se llena desde `entidades_participantes_marc` (`pipeline/normalizar_marc_recovered.py:349`) — un concepto distinto de "plantel" (instituciones participantes/coasesoras, no necesariamente la escuela de inscripción).
- **Uso histórico real**: `pipeline/fix_unidad_posgrado_stream.py` la usó como fuente de rescate para corregir `plantel_estandarizado` en un subconjunto de filas (flag `flag_rescatado_por_entidad_clean`).
- **Uso en producción**: cero referencias en `app/MI-TESIS-UNAM_github`. No la usa nada desplegado.

**Análisis cuantitativo** (2026-09-20): de las 526,953 filas pobladas, **82% (432,078) es literalmente la misma información que `plantel_estandarizado`** (solo peor normalizada — mayúsculas mixtas, puntuación suelta como "Universidad Autónoma de Guadalajara."). El **18% restante (94,875 filas)** trae información potencialmente distinta — casi siempre una universidad "padre" sin la facultad específica, o una institución externa distinta a la del plantel, con algo de ruido real mezclado (typos como "facultad de esconomia").

## Decisión

- Se remueve `entidad_clean` de `data/clean/base7_kaggle_clean.parquet` (43 → 42 columnas).
- Se archiva completa (sin limpiar, tal cual) en `data/lineage/entidad_clean_archivado_2026-09-20.parquet`, con `thesis_id` y el `plantel_estandarizado` de esa fila para poder comparar sin volver a unir con el dataset principal.
- No se invierte esfuerzo de limpieza (a diferencia de `plantel`/`programa`, ver ADR-0005/0006) porque no hay consumidor actual que lo justifique.

## Consecuencias

- (+) El dataset "producto" (`base7_kaggle_clean.parquet`) queda más limpio y sin una columna de bajo valor informativo (82% redundante) que podía confundirse con `plantel_estandarizado`.
- (+) Nada se pierde: el 18% de información potencialmente útil queda accesible en `data/lineage/` si en el futuro se justifica investigarlo (ej. mapear coinstituciones/programas conjuntos).
- (-) Cualquier reprocesamiento futuro de `plantel_estandarizado` que quisiera usar `entidad_clean` como fuente de rescate (como hizo `fix_unidad_posgrado_stream.py` en su momento) debe ahora leer de `data/lineage/`, no del archivo principal.
- Actualizar `data/clean/base7_column_dictionary.csv` y `nota_metodologica.md` para reflejar las 42 columnas y explicar dónde quedó `entidad_clean`.
