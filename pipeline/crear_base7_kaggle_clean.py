from pathlib import Path
import pandas as pd
import duckdb
import pyarrow.parquet as pq
import pyarrow as pa

IN = Path("base7_full_recovered.parquet")
OUT = Path("base7_kaggle_clean.parquet")

OUT_DIR = Path("outputs/base7_clean")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY = OUT_DIR / "base7_kaggle_clean_summary.csv"
COLUMNS_CSV = OUT_DIR / "base7_kaggle_clean_columns.csv"
SAMPLE = OUT_DIR / "base7_kaggle_clean_sample_1000.csv"
LOG = OUT_DIR / "base7_kaggle_clean_log.csv"
YEAR_COUNTS = OUT_DIR / "base7_kaggle_clean_year_counts.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

if OUT.exists():
    raise FileExistsError(f"Ya existe {OUT}. Renómbralo o bórralo si quieres regenerarlo.")

# Versión limpia, pero conservando thesis_id_old por compatibilidad con prototipo.
CLEAN_COLUMNS = [
    # Trazabilidad mínima / IDs
    "source_record",
    "thesis_id",
    "thesis_id_old",
    "ID_Aleph",
    "biblionumber",
    "system_number",

    # Tiempo y título
    "Año",
    "título",
    "titulo_limpio",
    "titulo_normalizado",

    # Autores
    "autores_limpios_v2",
    "autor_limpio_v2",
    "autores_display",
    "autor_display",
    "autor_ui",
    "num_autores",
    "flag_sin_autor",
    "flag_multiples_autores",

    # Asesores
    "asesores_limpios_v2",
    "asesor_limpio_v2",
    "asesores_display",
    "asesor_display",
    "asesor_ui",
    "num_asesores",
    "flag_sin_asesor",
    "flag_multiples_asesores",

    # Clasificación académica
    "grado",
    "grado_norm",
    "nivel_estandar",
    "programa",
    "area",

    # Institución / plantel
    "origen",
    "universidad_nota",
    "entidad_clean",
    "plantel_estandarizado",
    "plantel_display",

    # Acceso / soporte
    "texto_completo_url",
    "restricciones",
    "tipo de contenido",
    "medio",
    "soporte",
    "descr física",

    # Materias principales
    "materia general",
]

# Algunas columnas pueden no existir si cambiaste algo; usamos solo las disponibles.
available = set(pq.ParquetFile(IN).schema.names)
missing = [c for c in CLEAN_COLUMNS if c not in available]
use_cols = [c for c in CLEAN_COLUMNS if c in available]

if missing:
    print("Columnas solicitadas que no existen y se omitirán:")
    for c in missing:
        print("-", c)

pf = pq.ParquetFile(IN)

print("Input:", IN)
print("Output:", OUT)
print("Input rows:", f"{pf.metadata.num_rows:,}")
print("Input row groups:", pf.num_row_groups)
print("Clean columns:", len(use_cols))

writer = None
rows_written = 0
log_rows = []

for rg in range(pf.num_row_groups):
    table = pf.read_row_group(rg, columns=use_cols)
    df = table.to_pandas()

    # Reordenar columnas exactas.
    df = df[use_cols]

    out_table = pa.Table.from_pandas(df, preserve_index=False)

    if writer is None:
        writer = pq.ParquetWriter(
            OUT,
            out_table.schema,
            compression="zstd",
            use_dictionary=True
        )

    writer.write_table(out_table)

    rows_written += len(df)

    log_rows.append({
        "row_group": rg + 1,
        "rows_batch": len(df),
        "rows_written": rows_written,
    })

    print(
        f"row_group={rg+1}/{pf.num_row_groups} "
        f"batch_rows={len(df):,} rows_written={rows_written:,}",
        flush=True
    )

if writer:
    writer.close()

pd.DataFrame(log_rows).to_csv(LOG, index=False, encoding="utf-8")

# Validaciones con DuckDB
con = duckdb.connect()

n = con.execute(f"""
SELECT count(*) AS n
FROM read_parquet('{OUT.as_posix()}')
""").fetchdf()["n"].iloc[0]

source_counts = con.execute(f"""
SELECT source_record, count(*) AS n
FROM read_parquet('{OUT.as_posix()}')
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
FROM read_parquet('{OUT.as_posix()}')
""").fetchdf()

year_counts = con.execute(f"""
SELECT "Año" AS anio, count(*) AS n
FROM read_parquet('{OUT.as_posix()}')
GROUP BY 1
ORDER BY 1
""").fetchdf()
year_counts.to_csv(YEAR_COUNTS, index=False, encoding="utf-8")

columns_report = pd.DataFrame({
    "ordinal": range(1, len(use_cols) + 1),
    "column": use_cols,
    "included_in_clean": True,
    "note": [
        "ID anterior conservado para compatibilidad con prototipo" if c == "thesis_id_old"
        else "columna limpia normalizada"
        for c in use_cols
    ]
})
columns_report.to_csv(COLUMNS_CSV, index=False, encoding="utf-8")

summary = pd.DataFrame([
    {"metric": "input_file", "value": str(IN)},
    {"metric": "output_file", "value": str(OUT)},
    {"metric": "rows_written", "value": int(rows_written)},
    {"metric": "rows_count_duckdb", "value": int(n)},
    {"metric": "columns", "value": len(use_cols)},
    {"metric": "matches_expected_609156", "value": str(int(n) == 609156)},
    {"metric": "thesis_id_old_included", "value": str("thesis_id_old" in use_cols)},
    {"metric": "missing_requested_columns", "value": " | ".join(missing)},
])
summary.to_csv(SUMMARY, index=False, encoding="utf-8")

sample = con.execute(f"""
SELECT *
FROM read_parquet('{OUT.as_posix()}')
LIMIT 1000
""").fetchdf()
sample.to_csv(SAMPLE, index=False, encoding="utf-8")

print("\nLISTO CLEAN PARQUET")
print("Output:", OUT)
print("Rows:", f"{int(n):,}")
print("Columns:", len(use_cols))
print("\nSource counts:")
print(source_counts.to_string(index=False))
print("\nID check:")
print(id_check.to_string(index=False))
print("\nSummary:", SUMMARY)
print("Columns:", COLUMNS_CSV)
print("Sample:", SAMPLE)
print("Year counts:", YEAR_COUNTS)
print("Log:", LOG)
