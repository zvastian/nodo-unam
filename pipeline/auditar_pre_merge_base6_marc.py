from pathlib import Path
import re
import unicodedata
import pandas as pd
import duckdb
import pyarrow.parquet as pq

BASE = Path("base6_homogeneizada_stream_v2.parquet")
MARC = Path("recovery/processed/marc_recovered_normalized.parquet")

OUT_DIR = Path("outputs/pre_merge_audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not BASE.exists():
    raise FileNotFoundError(f"No encontré {BASE}")

if not MARC.exists():
    raise FileNotFoundError(f"No encontré {MARC}")

con = duckdb.connect()

def clean_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def strip_accents(s):
    s = clean_str(s)
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

def norm_key(s):
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def describe_parquet(path):
    return con.execute(f"""
    DESCRIBE SELECT * FROM read_parquet('{path.as_posix()}')
    """).fetchdf()

def count_rows(path):
    return int(con.execute(f"""
    SELECT count(*) AS n FROM read_parquet('{path.as_posix()}')
    """).fetchdf()["n"].iloc[0])

print("BASE:", BASE)
print("MARC:", MARC)

base_desc = describe_parquet(BASE)
marc_desc = describe_parquet(MARC)

base_cols = base_desc["column_name"].tolist()
marc_cols = marc_desc["column_name"].tolist()

base_set = set(base_cols)
marc_set = set(marc_cols)

base_n = count_rows(BASE)
marc_n = count_rows(MARC)

print("\n=== Conteos ===")
print("base rows:", f"{base_n:,}")
print("marc rows:", f"{marc_n:,}")

# -------------------------
# 1. Schema comparison
# -------------------------

schema_rows = []

all_cols = sorted(base_set | marc_set)

for c in all_cols:
    base_type = ""
    marc_type = ""

    if c in base_set:
        base_type = base_desc.loc[base_desc["column_name"] == c, "column_type"].iloc[0]

    if c in marc_set:
        marc_type = marc_desc.loc[marc_desc["column_name"] == c, "column_type"].iloc[0]

    schema_rows.append({
        "column": c,
        "in_base": c in base_set,
        "in_marc": c in marc_set,
        "base_type": base_type,
        "marc_type": marc_type,
        "same_type": bool(base_type and marc_type and base_type == marc_type),
    })

schema = pd.DataFrame(schema_rows)
schema.to_csv(OUT_DIR / "schema_comparison.csv", index=False, encoding="utf-8")

base_only = schema[(schema["in_base"]) & (~schema["in_marc"])].copy()
marc_only = schema[(~schema["in_base"]) & (schema["in_marc"])].copy()
type_diff = schema[(schema["in_base"]) & (schema["in_marc"]) & (~schema["same_type"])].copy()

base_only.to_csv(OUT_DIR / "columns_only_in_base.csv", index=False, encoding="utf-8")
marc_only.to_csv(OUT_DIR / "columns_only_in_marc.csv", index=False, encoding="utf-8")
type_diff.to_csv(OUT_DIR / "columns_type_differences.csv", index=False, encoding="utf-8")

print("\n=== Schema ===")
print("columns base:", len(base_cols))
print("columns marc:", len(marc_cols))
print("common:", len(base_set & marc_set))
print("only base:", len(base_only))
print("only marc:", len(marc_only))
print("type differences:", len(type_diff))

# -------------------------
# 2. Coverage of merge-critical columns
# -------------------------

KEY_COLS = [
    "thesis_id",
    "biblionumber",
    "system_number",
    "Año",
    "ID_Aleph",
    "título",
    "titulo_limpio",
    "titulo_normalizado",
    "autor_limpio_v2",
    "autor_display",
    "asesor_limpio_v2",
    "asesor_display",
    "asesores_limpios_v2",
    "asesores_display",
    "asesor_ui",
    "num_autores",
    "num_asesores",
    "grado",
    "grado_norm",
    "nivel_estandar",
    "programa",
    "area",
    "plantel_estandarizado",
    "plantel_display",
    "link_extraido_regex",
    "texto_completo_url",
    "restricciones",
    "materia general",
    "palabras clave",
    "resumen",
    "source_record",
    "target_year",
    "asesores_source_used",
]

def coverage(path, label, cols):
    existing = set(describe_parquet(path)["column_name"].tolist())
    rows = []
    n = count_rows(path)

    for c in cols:
        if c not in existing:
            rows.append({
                "dataset": label,
                "column": c,
                "exists": False,
                "total": n,
                "non_empty": 0,
                "pct_non_empty": 0,
            })
            continue

        q = f"""
        SELECT
            count(*) AS total,
            count(NULLIF(trim(cast("{c}" AS VARCHAR)), '')) AS non_empty
        FROM read_parquet('{path.as_posix()}')
        """
        r = con.execute(q).fetchdf().iloc[0].to_dict()
        rows.append({
            "dataset": label,
            "column": c,
            "exists": True,
            "total": int(r["total"]),
            "non_empty": int(r["non_empty"]),
            "pct_non_empty": float(r["non_empty"]) / float(r["total"]) * 100 if r["total"] else 0,
        })

    return pd.DataFrame(rows)

cov = pd.concat([
    coverage(BASE, "base", KEY_COLS),
    coverage(MARC, "marc", KEY_COLS),
], ignore_index=True)

cov.to_csv(OUT_DIR / "critical_columns_coverage.csv", index=False, encoding="utf-8")

print("\n=== Cobertura columnas críticas ===")
print(cov.pivot(index="column", columns="dataset", values="pct_non_empty").fillna(0).round(2).to_string())

# -------------------------
# 3. Year counts
# -------------------------

def year_counts(path, label):
    cols = describe_parquet(path)["column_name"].tolist()
    if "Año" not in cols:
        return pd.DataFrame(columns=["dataset", "Año", "n"])

    df = con.execute(f"""
    SELECT
        '{label}' AS dataset,
        "Año" AS anio,
        count(*) AS n
    FROM read_parquet('{path.as_posix()}')
    GROUP BY 1, 2
    ORDER BY 2
    """).fetchdf()
    return df

years = pd.concat([
    year_counts(BASE, "base"),
    year_counts(MARC, "marc"),
], ignore_index=True)

years.to_csv(OUT_DIR / "year_counts_long.csv", index=False, encoding="utf-8")

year_pivot = (
    years.pivot(index="anio", columns="dataset", values="n")
         .fillna(0)
         .reset_index()
)

if "base" not in year_pivot.columns:
    year_pivot["base"] = 0
if "marc" not in year_pivot.columns:
    year_pivot["marc"] = 0

year_pivot["base"] = year_pivot["base"].astype(int)
year_pivot["marc"] = year_pivot["marc"].astype(int)
year_pivot["base_plus_marc_naive"] = year_pivot["base"] + year_pivot["marc"]

year_pivot.to_csv(OUT_DIR / "year_counts_comparison.csv", index=False, encoding="utf-8")

print("\n=== Años recuperados MARC ===")
print(year_pivot[year_pivot["marc"] > 0].to_string(index=False))

# -------------------------
# 4. Advisor distribution comparison
# -------------------------

def advisor_dist(path, label):
    cols = describe_parquet(path)["column_name"].tolist()
    if "num_asesores" not in cols:
        return pd.DataFrame(columns=["dataset", "num_asesores", "n"])

    return con.execute(f"""
    SELECT
        '{label}' AS dataset,
        num_asesores,
        count(*) AS n
    FROM read_parquet('{path.as_posix()}')
    GROUP BY 1, 2
    ORDER BY 2
    """).fetchdf()

adv = pd.concat([
    advisor_dist(BASE, "base"),
    advisor_dist(MARC, "marc"),
], ignore_index=True)

adv.to_csv(OUT_DIR / "advisor_count_distribution.csv", index=False, encoding="utf-8")

print("\n=== Distribución asesores ===")
print(adv.to_string(index=False))

# -------------------------
# 5. Dedup keys / overlap candidates
# -------------------------

# Cargamos solo columnas necesarias para crear claves. 583k + 46k está bien.
base_read_cols = [c for c in ["thesis_id", "Año", "título", "titulo_normalizado", "autor_limpio_v2", "autor_display", "link_extraido_regex", "texto_completo_url", "system_number", "biblionumber"] if c in base_cols]
marc_read_cols = [c for c in ["target_year", "biblionumber", "system_number", "Año", "título", "titulo_normalizado", "autor_limpio_v2", "autor_display", "texto_completo_url", "link_extraido_regex"] if c in marc_cols]

print("\nLeyendo columnas para overlap...")
base_small = pd.read_parquet(BASE, columns=base_read_cols)
marc_small = pd.read_parquet(MARC, columns=marc_read_cols)

def add_keys(df):
    if "Año" in df.columns:
        year = df["Año"].fillna("").astype(str)
    else:
        year = ""

    if "titulo_normalizado" in df.columns:
        title = df["titulo_normalizado"].fillna("").astype(str)
    elif "título" in df.columns:
        title = df["título"].fillna("").astype(str).map(norm_key)
    else:
        title = ""

    if "autor_limpio_v2" in df.columns:
        author = df["autor_limpio_v2"].fillna("").astype(str).map(norm_key)
    elif "autor_display" in df.columns:
        author = df["autor_display"].fillna("").astype(str).map(norm_key)
    else:
        author = ""

    df = df.copy()
    df["dedup_key_title_author_year"] = year + "||" + title.map(norm_key) + "||" + author

    # URL key
    url = pd.Series([""] * len(df), index=df.index)
    if "texto_completo_url" in df.columns:
        url = df["texto_completo_url"].fillna("").astype(str).map(clean_str)
    elif "link_extraido_regex" in df.columns:
        url = df["link_extraido_regex"].fillna("").astype(str).map(clean_str)

    df["dedup_key_url"] = url

    # system key
    sys = pd.Series([""] * len(df), index=df.index)
    if "system_number" in df.columns:
        sys = df["system_number"].fillna("").astype(str).map(clean_str)
    df["dedup_key_system_number"] = sys

    return df

base_small = add_keys(base_small)
marc_small = add_keys(marc_small)

# Sets
base_title_keys = set(base_small["dedup_key_title_author_year"].dropna().astype(str))
base_url_keys = set(base_small.loc[base_small["dedup_key_url"].astype(str).str.strip() != "", "dedup_key_url"].astype(str))
base_sys_keys = set(base_small.loc[base_small["dedup_key_system_number"].astype(str).str.strip() != "", "dedup_key_system_number"].astype(str))

marc_small["overlap_title_author_year"] = marc_small["dedup_key_title_author_year"].isin(base_title_keys)
marc_small["overlap_url"] = marc_small["dedup_key_url"].isin(base_url_keys) & marc_small["dedup_key_url"].astype(str).str.strip().ne("")
marc_small["overlap_system_number"] = marc_small["dedup_key_system_number"].isin(base_sys_keys) & marc_small["dedup_key_system_number"].astype(str).str.strip().ne("")

marc_small["any_overlap"] = (
    marc_small["overlap_title_author_year"]
    | marc_small["overlap_url"]
    | marc_small["overlap_system_number"]
)

overlap_summary = pd.DataFrame([
    {"metric": "marc_total", "n": len(marc_small)},
    {"metric": "overlap_title_author_year", "n": int(marc_small["overlap_title_author_year"].sum())},
    {"metric": "overlap_url", "n": int(marc_small["overlap_url"].sum())},
    {"metric": "overlap_system_number", "n": int(marc_small["overlap_system_number"].sum())},
    {"metric": "any_overlap", "n": int(marc_small["any_overlap"].sum())},
    {"metric": "insert_candidates_no_overlap", "n": int((~marc_small["any_overlap"]).sum())},
])

overlap_summary["pct_of_marc"] = overlap_summary["n"] / len(marc_small) * 100
overlap_summary.to_csv(OUT_DIR / "marc_overlap_summary.csv", index=False, encoding="utf-8")

marc_small.to_csv(OUT_DIR / "marc_overlap_flags_sample_all.csv", index=False, encoding="utf-8")

# sample useful
sample_cols = [c for c in [
    "target_year", "biblionumber", "system_number", "Año", "título",
    "autor_limpio_v2", "autor_display",
    "texto_completo_url", "dedup_key_title_author_year",
    "overlap_title_author_year", "overlap_url", "overlap_system_number", "any_overlap"
] if c in marc_small.columns]

marc_small[sample_cols].head(5000).to_csv(OUT_DIR / "marc_overlap_flags_sample_5000.csv", index=False, encoding="utf-8")

print("\n=== Overlap MARC vs base ===")
print(overlap_summary.to_string(index=False))

# -------------------------
# 6. Insert candidates by year
# -------------------------

candidates_by_year = (
    marc_small.assign(insert_candidate=~marc_small["any_overlap"])
              .groupby(["Año", "insert_candidate"], dropna=False)
              .size()
              .reset_index(name="n")
)

candidates_by_year.to_csv(OUT_DIR / "marc_insert_candidates_by_year.csv", index=False, encoding="utf-8")

print("\n=== Candidates by year ===")
print(candidates_by_year.to_string(index=False))

# -------------------------
# 7. Recommended common columns
# -------------------------

COMMON_DESIRED = [
    "source_record",
    "thesis_id",
    "biblionumber",
    "system_number",
    "Año",
    "ID_Aleph",
    "título",
    "titulo_limpio",
    "titulo_normalizado",
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
    "autor_limpio_v2",
    "autor_display",
    "asesor_limpio_v2",
    "asesor_display",
    "asesores_limpios_v2",
    "asesores_display",
    "asesor_ui",
    "num_autores",
    "num_asesores",
    "flag_sin_asesor",
    "flag_multiples_asesores",
    "flag_asesores_4plus",
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
    "asesores_source_used",
    "autor_limpio_v2_raw",
    "asesor_limpio_v2_raw",
    "asesores_limpios_v2_raw",
]

common_plan = pd.DataFrame([
    {
        "column": c,
        "in_base": c in base_set,
        "in_marc": c in marc_set,
        "action": (
            "keep_both" if c in base_set and c in marc_set
            else "add_empty_to_marc" if c in base_set and c not in marc_set
            else "add_empty_to_base" if c not in base_set and c in marc_set
            else "create_empty_both"
        )
    }
    for c in COMMON_DESIRED
])

common_plan.to_csv(OUT_DIR / "common_schema_plan.csv", index=False, encoding="utf-8")

print("\n=== Archivos creados ===")
for p in sorted(OUT_DIR.glob("*.csv")):
    print("-", p)

print("\nLISTO auditoría pre-merge.")
