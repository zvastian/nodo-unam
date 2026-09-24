from pathlib import Path
import re
import unicodedata
import pandas as pd
import duckdb
import pyarrow.parquet as pq

BASE = Path("base6_homogeneizada_stream_v4_1.parquet")
MARC = Path("recovery/processed/marc_recovered_normalized.parquet")

OUT_DIR = Path("outputs/pre_merge_audit_final")
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not BASE.exists():
    raise FileNotFoundError(f"No encontré {BASE}")

if not MARC.exists():
    raise FileNotFoundError(f"No encontré {MARC}")

con = duckdb.connect()

RECOVERED_YEARS = [1905, 1913, 1960, 1980, 1985, 1987, 1989, 1995, 2026]

FINAL_CORE_COLUMNS = [
    "source_record",
    "thesis_id",
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

def describe(path):
    return con.execute(f"""
    DESCRIBE SELECT * FROM read_parquet('{path.as_posix()}')
    """).fetchdf()

def count_rows(path):
    return int(con.execute(f"""
    SELECT count(*) AS n
    FROM read_parquet('{path.as_posix()}')
    """).fetchdf()["n"].iloc[0])

def save(df, name):
    p = OUT_DIR / name
    df.to_csv(p, index=False, encoding="utf-8")
    return p

base_desc = describe(BASE)
marc_desc = describe(MARC)

base_cols = base_desc["column_name"].tolist()
marc_cols = marc_desc["column_name"].tolist()

base_set = set(base_cols)
marc_set = set(marc_cols)

base_n = count_rows(BASE)
marc_n = count_rows(MARC)

print("=== ARCHIVOS ===")
print("BASE:", BASE)
print("MARC:", MARC)
print("BASE rows:", f"{base_n:,}")
print("MARC rows:", f"{marc_n:,}")

# ------------------------------------------------------------
# 1. Schema comparison
# ------------------------------------------------------------

schema_rows = []
for c in sorted(base_set | marc_set):
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
save(schema, "01_schema_comparison.csv")
save(schema[(schema["in_base"]) & (~schema["in_marc"])], "02_columns_only_in_base.csv")
save(schema[(~schema["in_base"]) & (schema["in_marc"])], "03_columns_only_in_marc.csv")
save(schema[(schema["in_base"]) & (schema["in_marc"]) & (~schema["same_type"])], "04_columns_type_differences.csv")

print("\n=== SCHEMA ===")
print("base cols:", len(base_cols))
print("marc cols:", len(marc_cols))
print("common cols:", len(base_set & marc_set))
print("only base:", int(((schema["in_base"]) & (~schema["in_marc"])).sum()))
print("only marc:", int(((~schema["in_base"]) & (schema["in_marc"])).sum()))
print("type differences:", int(((schema["in_base"]) & (schema["in_marc"]) & (~schema["same_type"])).sum()))

# ------------------------------------------------------------
# 2. Coverage final columns
# ------------------------------------------------------------

def coverage(path, label, columns):
    available = set(describe(path)["column_name"].tolist())
    n = count_rows(path)
    rows = []

    for c in columns:
        if c not in available:
            rows.append({
                "dataset": label,
                "column": c,
                "exists": False,
                "total": n,
                "non_empty": 0,
                "pct_non_empty": 0.0,
            })
            continue

        r = con.execute(f"""
        SELECT
            count(*) AS total,
            count(NULLIF(trim(cast("{c}" AS VARCHAR)), '')) AS non_empty
        FROM read_parquet('{path.as_posix()}')
        """).fetchdf().iloc[0]

        rows.append({
            "dataset": label,
            "column": c,
            "exists": True,
            "total": int(r["total"]),
            "non_empty": int(r["non_empty"]),
            "pct_non_empty": float(r["non_empty"]) / float(r["total"]) * 100 if r["total"] else 0.0,
        })

    return pd.DataFrame(rows)

cov = pd.concat([
    coverage(BASE, "base", FINAL_CORE_COLUMNS),
    coverage(MARC, "marc", FINAL_CORE_COLUMNS),
], ignore_index=True)

save(cov, "05_final_core_columns_coverage.csv")

cov_pivot = (
    cov.pivot(index="column", columns="dataset", values="pct_non_empty")
       .fillna(0)
       .reset_index()
)
save(cov_pivot, "06_final_core_columns_coverage_pivot.csv")

print("\n=== COBERTURA COLUMNAS FINALES ===")
print(cov_pivot.to_string(index=False))

# ------------------------------------------------------------
# 3. Year counts and replacement plan
# ------------------------------------------------------------

years_base = con.execute(f"""
SELECT "Año" AS anio, count(*) AS base_n
FROM read_parquet('{BASE.as_posix()}')
GROUP BY 1
ORDER BY 1
""").fetchdf()

years_marc = con.execute(f"""
SELECT "Año" AS anio, count(*) AS marc_n
FROM read_parquet('{MARC.as_posix()}')
GROUP BY 1
ORDER BY 1
""").fetchdf()

year_cmp = years_base.merge(years_marc, on="anio", how="outer").fillna(0)
year_cmp["base_n"] = year_cmp["base_n"].astype(int)
year_cmp["marc_n"] = year_cmp["marc_n"].astype(int)
year_cmp["is_recovered_year"] = year_cmp["anio"].isin(RECOVERED_YEARS)
year_cmp["merge_strategy"] = year_cmp["is_recovered_year"].map(
    lambda x: "replace_base_year_with_marc" if x else "keep_base"
)
year_cmp["final_n_if_replace_years"] = year_cmp.apply(
    lambda r: int(r["marc_n"]) if r["is_recovered_year"] else int(r["base_n"]),
    axis=1
)
year_cmp["delta_vs_base"] = year_cmp["final_n_if_replace_years"] - year_cmp["base_n"]
year_cmp = year_cmp.sort_values("anio")

save(year_cmp, "07_year_counts_replacement_plan.csv")

print("\n=== AÑOS RECUPERADOS ===")
print(year_cmp[year_cmp["is_recovered_year"]].to_string(index=False))

print("\n=== TOTAL SI REEMPLAZAMOS AÑOS ===")
base_keep = int(year_cmp.loc[~year_cmp["is_recovered_year"], "base_n"].sum())
marc_recovered = int(year_cmp.loc[year_cmp["is_recovered_year"], "marc_n"].sum())
final_total = base_keep + marc_recovered
print("base_keep_non_recovered:", f"{base_keep:,}")
print("marc_recovered_years:", f"{marc_recovered:,}")
print("final_total:", f"{final_total:,}")
print("delta_vs_base:", f"{final_total - base_n:,}")

summary_counts = pd.DataFrame([
    {"metric": "base_rows", "n": base_n},
    {"metric": "marc_rows", "n": marc_n},
    {"metric": "base_keep_non_recovered_years", "n": base_keep},
    {"metric": "marc_rows_recovered_years", "n": marc_recovered},
    {"metric": "final_total_if_replace_years", "n": final_total},
    {"metric": "delta_vs_base", "n": final_total - base_n},
])
save(summary_counts, "08_final_total_summary.csv")

# ------------------------------------------------------------
# 4. Author/advisor distributions
# ------------------------------------------------------------

def dist(path, label, col):
    available = set(describe(path)["column_name"].tolist())
    if col not in available:
        return pd.DataFrame(columns=["dataset", col, "n"])

    return con.execute(f"""
    SELECT
        '{label}' AS dataset,
        "{col}" AS "{col}",
        count(*) AS n
    FROM read_parquet('{path.as_posix()}')
    GROUP BY 1, 2
    ORDER BY 2
    """).fetchdf()

author_dist = pd.concat([
    dist(BASE, "base", "num_autores"),
    dist(MARC, "marc", "num_autores"),
], ignore_index=True)

advisor_dist = pd.concat([
    dist(BASE, "base", "num_asesores"),
    dist(MARC, "marc", "num_asesores"),
], ignore_index=True)

save(author_dist, "09_author_count_distribution.csv")
save(advisor_dist, "10_advisor_count_distribution.csv")

print("\n=== DISTRIBUCIÓN AUTORES ===")
print(author_dist.to_string(index=False))

print("\n=== DISTRIBUCIÓN ASESORES ===")
print(advisor_dist.to_string(index=False))

# ------------------------------------------------------------
# 5. Check suspicious authors/advisors after final cleaning
# ------------------------------------------------------------

def flags_for_name(s):
    s0 = clean_str(s)
    k = norm_key(s0)
    return {
        "flag_empty": s0 == "",
        "flag_any_digit": bool(re.search(r"\d", s0)),
        "flag_trailing_number": bool(re.search(r"\b\d{1,8}$", s0)),
        "flag_biographical_year": bool(re.search(r"\b(18|19|20)\d{2}\s*-\s*((18|19|20)\d{2})?\s*$", s0)),
        "flag_subfield_e": bool(re.search(r"\$e", s0, flags=re.I)),
        "flag_role_residue": any(x in k for x in [
            "sustentante", "asesor", "autor", "coautor",
            "presenta", "tesis", "para obtener",
            "universidad nacional autonoma de mexico",
        ]),
        "flag_bad_chars": bool(re.search(r"[\[\]\{\}<>=_*#@\\]", s0)),
        "flag_mojibake": bool(re.search(r"Ã|Â|�", s0)),
        "flag_too_short": 0 < len(k) <= 2,
        "flag_too_long": len(s0) > 120,
        "flag_separator": bool(re.search(r"\s[;|]\s", s0)),
        "flag_ends_comma": s0.endswith(","),
        "flag_starts_comma": s0.startswith(","),
    }

def audit_names(path, label, name_cols):
    pf = pq.ParquetFile(path)
    available = set(pf.schema.names)
    use_cols = [c for c in ["thesis_id", "biblionumber", "system_number", "Año", "título"] + name_cols if c in available]

    df = pd.read_parquet(path, columns=use_cols)

    rows = []
    summary = {}

    for col in name_cols:
        if col not in df.columns:
            continue

        for i, val in enumerate(df[col].fillna("").astype(str)):
            val = clean_str(val)
            parts = [val]

            # Para listas técnicas completas, auditar cada elemento.
            if col in ["autores_limpios_v2", "asesores_limpios_v2"]:
                parts = [p.strip() for p in val.split("|") if p.strip()]

            for p in parts:
                flags = flags_for_name(p)
                for f, yes in flags.items():
                    if yes:
                        summary[(col, f)] = summary.get((col, f), 0) + 1

                if any(flags.values()) and len(rows) < 20000:
                    row = {
                        "dataset": label,
                        "source_col": col,
                        "row_index": i,
                        "name": p,
                    }
                    for c in ["thesis_id", "biblionumber", "system_number", "Año", "título"]:
                        if c in df.columns:
                            row[c] = df.iloc[i][c]
                    row.update(flags)
                    rows.append(row)

    summary_df = pd.DataFrame([
        {"dataset": label, "source_col": col, "flag": flag, "n": n}
        for (col, flag), n in summary.items()
    ]).sort_values(["source_col", "n"], ascending=[True, False]) if summary else pd.DataFrame(columns=["dataset", "source_col", "flag", "n"])

    rows_df = pd.DataFrame(rows)
    return summary_df, rows_df

base_name_summary, base_name_sus = audit_names(
    BASE,
    "base",
    ["autor_limpio_v2", "autores_limpios_v2", "asesor_limpio_v2", "asesores_limpios_v2"]
)

marc_name_summary, marc_name_sus = audit_names(
    MARC,
    "marc",
    ["autor_limpio_v2", "autores_limpios_v2", "asesor_limpio_v2", "asesores_limpios_v2"]
)

name_summary = pd.concat([base_name_summary, marc_name_summary], ignore_index=True)
name_sus = pd.concat([base_name_sus, marc_name_sus], ignore_index=True)

save(name_summary, "11_name_flags_summary.csv")
save(name_sus, "12_suspicious_names_sample.csv")

print("\n=== FLAGS NOMBRES ===")
print(name_summary.to_string(index=False) if len(name_summary) else "Sin flags.")

# ------------------------------------------------------------
# 6. Overlap diagnostics, still useful but not merge strategy
# ------------------------------------------------------------

def read_small_for_keys(path):
    pf = pq.ParquetFile(path)
    available = set(pf.schema.names)
    cols = [c for c in [
        "thesis_id",
        "biblionumber",
        "system_number",
        "Año",
        "título",
        "titulo_normalizado",
        "autor_limpio_v2",
        "autores_limpios_v2",
        "autor_display",
        "texto_completo_url",
        "link_extraido_regex",
    ] if c in available]
    return pd.read_parquet(path, columns=cols)

def add_dedup_keys(df):
    df = df.copy()

    year = df["Año"].fillna("").astype(str) if "Año" in df.columns else pd.Series([""] * len(df), index=df.index)

    if "titulo_normalizado" in df.columns:
        title = df["titulo_normalizado"].fillna("").astype(str).map(norm_key)
    elif "título" in df.columns:
        title = df["título"].fillna("").astype(str).map(norm_key)
    else:
        title = pd.Series([""] * len(df), index=df.index)

    if "autor_limpio_v2" in df.columns:
        author = df["autor_limpio_v2"].fillna("").astype(str).map(norm_key)
    elif "autor_display" in df.columns:
        author = df["autor_display"].fillna("").astype(str).map(norm_key)
    else:
        author = pd.Series([""] * len(df), index=df.index)

    df["dedup_key_title_author_year"] = year + "||" + title + "||" + author

    if "texto_completo_url" in df.columns:
        df["dedup_key_url"] = df["texto_completo_url"].fillna("").astype(str).map(clean_str)
    elif "link_extraido_regex" in df.columns:
        df["dedup_key_url"] = df["link_extraido_regex"].fillna("").astype(str).map(clean_str)
    else:
        df["dedup_key_url"] = ""

    if "system_number" in df.columns:
        df["dedup_key_system_number"] = df["system_number"].fillna("").astype(str).map(clean_str)
    else:
        df["dedup_key_system_number"] = ""

    return df

base_small = add_dedup_keys(read_small_for_keys(BASE))
marc_small = add_dedup_keys(read_small_for_keys(MARC))

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
save(overlap_summary, "13_overlap_summary_diagnostic_only.csv")

overlap_by_year = (
    marc_small.assign(insert_candidate=~marc_small["any_overlap"])
              .groupby(["Año", "insert_candidate"], dropna=False)
              .size()
              .reset_index(name="n")
              .sort_values(["Año", "insert_candidate"])
)
save(overlap_by_year, "14_overlap_by_year_diagnostic_only.csv")

print("\n=== OVERLAP DIAGNÓSTICO ===")
print(overlap_summary.to_string(index=False))

# ------------------------------------------------------------
# 7. Common schema merge plan
# ------------------------------------------------------------

common_schema_plan = pd.DataFrame([
    {
        "column": c,
        "in_base": c in base_set,
        "in_marc": c in marc_set,
        "base_type": base_desc.loc[base_desc["column_name"] == c, "column_type"].iloc[0] if c in base_set else "",
        "marc_type": marc_desc.loc[marc_desc["column_name"] == c, "column_type"].iloc[0] if c in marc_set else "",
        "action": (
            "keep_both" if c in base_set and c in marc_set
            else "add_empty_to_marc" if c in base_set and c not in marc_set
            else "add_empty_to_base" if c not in base_set and c in marc_set
            else "create_empty_both"
        )
    }
    for c in FINAL_CORE_COLUMNS
])
save(common_schema_plan, "15_common_schema_plan_final_core.csv")

# ------------------------------------------------------------
# 8. Final recommendation text file
# ------------------------------------------------------------

recommendation = f"""
PRE-MERGE FINAL AUDIT

Recommended base file:
{BASE}

Recommended MARC file:
{MARC}

Recommended merge strategy:
1. Keep base rows EXCLUDING recovered years:
   {RECOVERED_YEARS}

2. Append all MARC rows for recovered years.

Expected final total:
{final_total:,}

Base rows:
{base_n:,}

MARC rows:
{marc_n:,}

Base rows kept outside recovered years:
{base_keep:,}

MARC recovered rows used:
{marc_recovered:,}

Delta vs base:
{final_total - base_n:,}

Reason:
The recovered years were precisely the years with known extraction loss.
Replacing those years entirely with normalized MARC avoids duplicate ambiguity
from title/author/year matching and preserves a cleaner methodology.

Do not use overlap-only append as main merge strategy.
Overlap files are diagnostic only.
"""

(OUT_DIR / "16_merge_recommendation.txt").write_text(recommendation, encoding="utf-8")

print("\n=== RECOMENDACIÓN ===")
print(recommendation)

print("\n=== ARCHIVOS CREADOS ===")
for p in sorted(OUT_DIR.glob("*")):
    print("-", p)

print("\nLISTO auditoría final pre-merge.")
