from pathlib import Path
import re
import unicodedata
from collections import Counter
import pandas as pd
import pyarrow.parquet as pq

FILES = {
    "base": Path("base6_homogeneizada_stream_v2.parquet"),
    "marc": Path("recovery/processed/marc_recovered_normalized.parquet"),
}

OUT_DIR = Path("outputs/pre_merge_audit/autores")
OUT_DIR.mkdir(parents=True, exist_ok=True)

for label, path in FILES.items():
    if not path.exists():
        raise FileNotFoundError(f"No encontré {label}: {path}")

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

def flags_for_author(s):
    s0 = clean_str(s)
    k = norm_key(s0)

    return {
        "flag_empty": s0 == "",
        "flag_any_digit": bool(re.search(r"\d", s0)),
        "flag_trailing_number": bool(re.search(r"\b\d{1,8}$", s0)),
        "flag_biographical_year": bool(re.search(r"\b(18|19|20)\d{2}\s*-\s*((18|19|20)\d{2})?\s*$", s0)),
        "flag_subfield_e": bool(re.search(r"\$e", s0, flags=re.I)),
        "flag_role_residue": any(x in k for x in [
            "sustentante",
            "asesor",
            "autor",
            "presenta",
            "tesis",
            "para obtener",
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

def read_existing_cols(path, wanted):
    pf = pq.ParquetFile(path)
    available = set(pf.schema.names)
    cols = [c for c in wanted if c in available]
    return pd.read_parquet(path, columns=cols), available

wanted = [
    "source_record",
    "thesis_id",
    "target_year",
    "biblionumber",
    "system_number",
    "Año",
    "título",
    "autor_limpio_v2_raw",
    "autor_limpio_v2",
    "autor_display",
    "titulo_normalizado",
]

all_summaries = []

for label, path in FILES.items():
    print(f"\n=== AUDITANDO {label}: {path} ===")

    df, available = read_existing_cols(path, wanted)
    n = len(df)

    for c in wanted:
        if c not in df.columns:
            df[c] = ""

    flag_counter = Counter()
    suspicious = []
    freq_counter = Counter()
    variants = {}

    for i, row in df.iterrows():
        if i % 50000 == 0:
            print(f"{label}: {i:,}/{n:,}", flush=True)

        author = clean_str(row["autor_limpio_v2"])
        display = clean_str(row["autor_display"])
        raw = clean_str(row["autor_limpio_v2_raw"])

        flags = flags_for_author(author)

        for k, v in flags.items():
            if v:
                flag_counter[k] += 1

        key = norm_key(author)
        if author:
            freq_counter[(author, key)] += 1
            variants.setdefault(key, set()).add(author)

        any_flag = any(flags.values())

        raw_key = norm_key(raw)
        author_key = norm_key(author)

        raw_diff_suspicious = (
            raw != ""
            and author != ""
            and raw_key != author_key
            and len(raw) > len(author) + 8
            and (
                "$e" in raw.lower()
                or re.search(r"\b(18|19|20)\d{2}\s*-", raw)
                or ";" in raw
                or "|" in raw
            )
        )

        if (any_flag or raw_diff_suspicious) and len(suspicious) < 20000:
            out = {
                "dataset": label,
                "row_index": i,
                "thesis_id": row.get("thesis_id", ""),
                "target_year": row.get("target_year", ""),
                "biblionumber": row.get("biblionumber", ""),
                "system_number": row.get("system_number", ""),
                "Año": row.get("Año", ""),
                "título": row.get("título", ""),
                "autor_limpio_v2_raw": raw,
                "autor_limpio_v2": author,
                "autor_display": display,
                "raw_diff_suspicious": raw_diff_suspicious,
            }
            out.update(flags)
            suspicious.append(out)

    if flag_counter:
        summary = pd.DataFrame([
            {"dataset": label, "flag": k, "n": v, "pct": v / n * 100}
            for k, v in flag_counter.items()
        ]).sort_values("n", ascending=False)
    else:
        summary = pd.DataFrame(columns=["dataset", "flag", "n", "pct"])

    summary.to_csv(OUT_DIR / f"{label}_author_flags_summary.csv", index=False, encoding="utf-8")

    pd.DataFrame(suspicious).to_csv(
        OUT_DIR / f"{label}_suspicious_authors_sample.csv",
        index=False,
        encoding="utf-8"
    )

    freq = pd.DataFrame([
        {"autor_limpio_v2": a, "author_key": k, "n": count}
        for (a, k), count in freq_counter.most_common(10000)
    ])
    freq.to_csv(OUT_DIR / f"{label}_author_frequency_top10000.csv", index=False, encoding="utf-8")

    variant_rows = []
    for key, forms in variants.items():
        if len(forms) > 1:
            variant_rows.append({
                "author_key": key,
                "variants": len(forms),
                "examples": " | ".join(list(forms)[:10]),
            })

    if variant_rows:
        variant_df = pd.DataFrame(variant_rows).sort_values(
            ["variants", "author_key"],
            ascending=[False, True]
        )
    else:
        variant_df = pd.DataFrame(columns=["author_key", "variants", "examples"])

    variant_df.to_csv(
        OUT_DIR / f"{label}_author_variants_same_key.csv",
        index=False,
        encoding="utf-8"
    )

    print(f"\nResumen {label}:")
    print(summary.to_string(index=False) if len(summary) else "Sin flags.")

    all_summaries.append(summary)

combined = pd.concat(all_summaries, ignore_index=True) if all_summaries else pd.DataFrame(columns=["dataset", "flag", "n", "pct"])
combined.to_csv(OUT_DIR / "combined_author_flags_summary.csv", index=False, encoding="utf-8")

print("\nLISTO auditoría autores.")
print("Carpeta:", OUT_DIR)
for p in sorted(OUT_DIR.glob("*.csv")):
    print("-", p)
