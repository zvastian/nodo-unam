from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import duckdb

BASE = Path("base6_homogeneizada_stream_v4_1.parquet")
MARC = Path("recovery/processed/marc_recovered_normalized.parquet")
OUT = Path("base7_full_recovered.parquet")

OUT_DIR = Path("outputs/base7_merge")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY = OUT_DIR / "merge_summary.csv"
YEAR_COUNTS = OUT_DIR / "year_counts_base7.csv"
SAMPLE = OUT_DIR / "base7_sample_1000.csv"
LOG = OUT_DIR / "merge_log.csv"

RECOVERED_YEARS = {1905, 1913, 1960, 1980, 1985, 1987, 1989, 1995, 2026}

if not BASE.exists():
    raise FileNotFoundError(f"No encontré {BASE}")

if not MARC.exists():
    raise FileNotFoundError(f"No encontré {MARC}")

if OUT.exists():
    raise FileExistsError(f"Ya existe {OUT}. Borra o renombra el archivo antes de regenerarlo.")

CORE_FIRST = [
    "source_record",
    "thesis_id",
    "thesis_id_old",
    "biblionumber",
    "system_number",
    "Año",
    "ID_Aleph",
    "título",
    "titulo_limpio",
    "titulo_normalizado",

    "autor_limpio_v2_raw",
    "autores_limpios_v2",
    "autor_limpio_v2",
    "autores_display",
    "autor_display",
    "autor_ui",
    "num_autores",
    "flag_sin_autor",
    "flag_multiples_autores",
    "flag_autores_4plus",

    "asesor_limpio_v2_raw",
    "asesores_limpios_v2_raw",
    "asesores_source_used",
    "asesores_limpios_v2",
    "asesor_limpio_v2",
    "asesores_display",
    "asesor_display",
    "asesor_ui",
    "num_asesores",
    "flag_sin_asesor",
    "flag_multiples_asesores",
    "flag_asesores_4plus",

    "grado",
    "grado_norm",
    "nivel_estandar",
    "programa",
    "area",
    "origen",
    "universidad_nota",
    "entidad_clean",
    "plantel_estandarizado",
    "plantel_display",

    "link_extraido_regex",
    "texto_completo_url",
    "restricciones",
    "tipo de contenido",
    "medio",
    "soporte",
    "descr física",

    "materia general",
    "materia geográfico",
    "materia ent corp",
    "mat autor person",
    "materia tit unif",
    "materia conferencia",
    "palabras clave",
    "resumen",

    "marc_url",
    "detail_url",
    "download_status",
    "downloaded_at_unix",
]

INT_COLS = {
    "Año",
    "num_autores",
    "num_asesores",
}

FLOAT_COLS = {
    "downloaded_at_unix",
}

BOOL_COLS_EXTRA = {
    "es_unam_nota",
    "es_externa_explicit",
}

def parquet_cols(path):
    return pq.ParquetFile(path).schema.names

base_cols = parquet_cols(BASE)
marc_cols = parquet_cols(MARC)

all_cols = list(dict.fromkeys(CORE_FIRST + base_cols + marc_cols))

if "thesis_id_old" not in all_cols:
    all_cols.insert(2, "thesis_id_old")

def normalize_bool_series(s):
    if s.dtype == bool:
        return s.fillna(False).astype(bool)

    ss = s.fillna(False)

    if ss.dtype == object:
        return ss.astype(str).str.lower().isin(["true", "1", "yes", "si", "sí"])

    return ss.astype(bool)

def normalize_batch(df, dataset_label):
    df = df.copy()

    # Preservar ID original de base.
    if "thesis_id" in df.columns:
        df["thesis_id_old"] = df["thesis_id"].fillna("").astype(str)
    else:
        df["thesis_id_old"] = ""

    df["source_record"] = dataset_label

    # Agregar columnas faltantes.
    for col in all_cols:
        if col not in df.columns:
            if col in INT_COLS:
                df[col] = 0
            elif col in FLOAT_COLS:
                df[col] = float("nan")
            elif col.startswith("flag_") or col in BOOL_COLS_EXTRA:
                df[col] = False
            else:
                df[col] = ""

    # Forzar tipos consistentes.
    for col in all_cols:
        if col in INT_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

        elif col in FLOAT_COLS:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

        elif col.startswith("flag_") or col in BOOL_COLS_EXTRA:
            df[col] = normalize_bool_series(df[col])

        else:
            # Todo lo demás como string para evitar choques tipo ID_Aleph / ID_Limpio.
            df[col] = df[col].fillna("").astype(str)

    return df[all_cols]

writer = None
rows_written = 0
log_rows = []

print("BASE:", BASE)
print("MARC:", MARC)
print("OUT:", OUT)
print("Recovered years:", sorted(RECOVERED_YEARS))

# -------------------------------------------------------
# 1. BASE sin años recuperados
# -------------------------------------------------------

pf_base = pq.ParquetFile(BASE)

print("\nEscribiendo BASE sin años recuperados...")

for rg in range(pf_base.num_row_groups):
    df = pf_base.read_row_group(rg).to_pandas()

    before = len(df)
    df = df[~df["Año"].isin(RECOVERED_YEARS)].copy()
    kept = len(df)
    dropped = before - kept

    if kept == 0:
        log_rows.append({
            "phase": "base",
            "row_group": rg + 1,
            "input_rows": before,
            "kept_rows": kept,
            "dropped_rows": dropped,
            "rows_written_total": rows_written,
        })
        print(f"base rg={rg+1}/{pf_base.num_row_groups} kept=0 dropped={dropped:,}")
        continue

    df = normalize_batch(df, "base6")

    start = rows_written + 1
    end = rows_written + kept
    df["thesis_id"] = [f"TH_{i:07d}" for i in range(start, end + 1)]

    table = pa.Table.from_pandas(df, preserve_index=False)

    if writer is None:
        writer = pq.ParquetWriter(
            OUT,
            table.schema,
            compression="zstd",
            use_dictionary=True
        )

    writer.write_table(table)
    rows_written += kept

    log_rows.append({
        "phase": "base",
        "row_group": rg + 1,
        "input_rows": before,
        "kept_rows": kept,
        "dropped_rows": dropped,
        "rows_written_total": rows_written,
    })

    print(
        f"base rg={rg+1}/{pf_base.num_row_groups} "
        f"input={before:,} kept={kept:,} dropped={dropped:,} "
        f"written={rows_written:,}",
        flush=True
    )

# -------------------------------------------------------
# 2. MARC completo para años recuperados
# -------------------------------------------------------

pf_marc = pq.ParquetFile(MARC)

print("\nEscribiendo MARC recuperado completo...")

for rg in range(pf_marc.num_row_groups):
    df = pf_marc.read_row_group(rg).to_pandas()

    before = len(df)
    df = df[df["Año"].isin(RECOVERED_YEARS)].copy()
    kept = len(df)
    dropped = before - kept

    if kept == 0:
        log_rows.append({
            "phase": "marc",
            "row_group": rg + 1,
            "input_rows": before,
            "kept_rows": kept,
            "dropped_rows": dropped,
            "rows_written_total": rows_written,
        })
        print(f"marc rg={rg+1}/{pf_marc.num_row_groups} kept=0 dropped={dropped:,}")
        continue

    df = normalize_batch(df, "marc_recovered")

    start = rows_written + 1
    end = rows_written + kept
    df["thesis_id"] = [f"TH_{i:07d}" for i in range(start, end + 1)]

    table = pa.Table.from_pandas(df, preserve_index=False)

    writer.write_table(table)
    rows_written += kept

    log_rows.append({
        "phase": "marc",
        "row_group": rg + 1,
        "input_rows": before,
        "kept_rows": kept,
        "dropped_rows": dropped,
        "rows_written_total": rows_written,
    })

    print(
        f"marc rg={rg+1}/{pf_marc.num_row_groups} "
        f"input={before:,} kept={kept:,} dropped={dropped:,} "
        f"written={rows_written:,}",
        flush=True
    )

if writer:
    writer.close()

pd.DataFrame(log_rows).to_csv(LOG, index=False, encoding="utf-8")

# -------------------------------------------------------
# 3. Validación rápida
# -------------------------------------------------------

con = duckdb.connect()

n = con.execute(f"""
SELECT count(*) AS n
FROM read_parquet('{OUT.as_posix()}')
""").fetchdf()["n"].iloc[0]

years = con.execute(f"""
SELECT "Año" AS anio, count(*) AS n
FROM read_parquet('{OUT.as_posix()}')
GROUP BY 1
ORDER BY 1
""").fetchdf()
years.to_csv(YEAR_COUNTS, index=False, encoding="utf-8")

source_counts = con.execute(f"""
SELECT source_record, count(*) AS n
FROM read_parquet('{OUT.as_posix()}')
GROUP BY 1
ORDER BY 1
""").fetchdf()

summary = pd.DataFrame([
    {"metric": "rows_written", "value": rows_written},
    {"metric": "rows_count_duckdb", "value": int(n)},
    {"metric": "expected_rows", "value": 609156},
    {"metric": "matches_expected", "value": str(int(n) == 609156)},
])

summary.to_csv(SUMMARY, index=False, encoding="utf-8")

sample = con.execute(f"""
SELECT *
FROM read_parquet('{OUT.as_posix()}')
LIMIT 1000
""").fetchdf()
sample.to_csv(SAMPLE, index=False, encoding="utf-8")

print("\nLISTO MERGE BASE7")
print("Output:", OUT)
print("Rows written:", f"{rows_written:,}")
print("DuckDB count:", f"{int(n):,}")
print("Expected:", "609,156")
print("\nSource counts:")
print(source_counts.to_string(index=False))
print("\nSummary:", SUMMARY)
print("Year counts:", YEAR_COUNTS)
print("Sample:", SAMPLE)
print("Log:", LOG)
