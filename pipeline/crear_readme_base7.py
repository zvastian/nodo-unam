from pathlib import Path
import duckdb

PARQUET = Path("base7_kaggle_clean.parquet")
OUT = Path("README.md")

if not PARQUET.exists():
    raise FileNotFoundError(f"No encontré {PARQUET}")

con = duckdb.connect()

n_rows = int(con.execute(f"""
SELECT count(*) AS n FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf()["n"].iloc[0])

n_cols = len(con.execute(f"""
DESCRIBE SELECT * FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf())

year_minmax = con.execute(f"""
SELECT min("Año") AS min_year, max("Año") AS max_year
FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf().iloc[0]

source_counts = con.execute(f"""
SELECT source_record, count(*) AS n
FROM read_parquet('{PARQUET.as_posix()}')
GROUP BY 1
ORDER BY 1
""").fetchdf()

id_check = con.execute(f"""
SELECT
    count(*) AS n,
    count(DISTINCT thesis_id) AS distinct_thesis_id,
    min(thesis_id) AS min_thesis_id,
    max(thesis_id) AS max_thesis_id,
    count(NULLIF(trim(thesis_id_old), '')) AS thesis_id_old_no_vacio
FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf().iloc[0]

source_lines = "\n".join(
    f"- `{r.source_record}`: {int(r.n):,} registros"
    for _, r in source_counts.iterrows()
)

text = f"""# TESIUNAM — base7 clean

Dataset limpio y normalizado de registros de tesis de TESIUNAM.

Esta versión integra una base principal previamente procesada y una recuperación complementaria vía registros MARC para años con pérdida elevada de registros.

## Archivo principal

- `base7_kaggle_clean.parquet`
- Filas: {n_rows:,}
- Columnas: {n_cols}
- Años cubiertos: {int(year_minmax['min_year'])}–{int(year_minmax['max_year'])}

## Distribución por fuente

{source_lines}

## Identificadores

- `thesis_id`: identificador global nuevo de la versión base7.
- `thesis_id_old`: identificador anterior, conservado para compatibilidad con prototipos previos. Solo existe para registros provenientes de `base6`.
- `ID_Aleph`: identificador heredado de la extracción original.
- `biblionumber` y `system_number`: identificadores principalmente disponibles en registros recuperados vía MARC/Koha.

Validación:

- Registros totales: {int(id_check['n']):,}
- `thesis_id` distintos: {int(id_check['distinct_thesis_id']):,}
- Rango `thesis_id`: {id_check['min_thesis_id']}–{id_check['max_thesis_id']}
- `thesis_id_old` no vacío: {int(id_check['thesis_id_old_no_vacio']):,}

## Años recuperados

Los siguientes años fueron reemplazados por registros recuperados vía MARC:

`1905, 1913, 1960, 1980, 1985, 1987, 1989, 1995, 2026`

La estrategia fue excluir de la base principal los registros de esos años y reemplazarlos por la recuperación MARC completa.

## Columnas principales

El dataset limpio conserva columnas de alto valor analítico:

- identificación y trazabilidad;
- año y título;
- autores y asesores en formato técnico y de visualización;
- grado, nivel, programa y área;
- origen institucional y plantel;
- acceso, soporte y restricciones;
- materia general.

Para conocer cada columna, revisar:

- `base7_column_dictionary.csv`

## Formatos de nombres

El dataset conserva dos capas para autores y asesores.

Columnas técnicas:

- `autor_limpio_v2`
- `autores_limpios_v2`
- `asesor_limpio_v2`
- `asesores_limpios_v2`

Estas usan el formato bibliográfico `Apellido(s), Nombre(s)`.

Columnas de visualización:

- `autor_display`
- `autores_display`
- `asesor_display`
- `asesores_display`
- `autor_ui`
- `asesor_ui`

Estas usan el formato `Nombre(s) Apellido(s)`.

## Notas de uso

- Para análisis temporal, usar `Año`.
- Para agrupación institucional, usar `plantel_estandarizado`.
- Para visualización institucional, usar `plantel_display`.
- Para redes de asesores, usar `asesores_limpios_v2`.
- Para redes de autores, usar `autores_limpios_v2`.
- Para interfaces, usar `autor_ui` y `asesor_ui`.
- Para compatibilidad con prototipos anteriores, usar `thesis_id_old` cuando exista; si está vacío, usar `thesis_id`.

## Archivos recomendados

- `base7_kaggle_clean.parquet`
- `base7_column_dictionary.csv`
- `nota_metodologica.md`
"""

OUT.write_text(text, encoding="utf-8")

print("LISTO")
print("Archivo:", OUT)
