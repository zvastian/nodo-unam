from pathlib import Path
import re
import unicodedata
from collections import Counter, defaultdict
import pandas as pd

IN = Path("recovery/processed/marc_recovered_normalized.parquet")
OUT_DIR = Path("recovery/processed/name_audit_fast")
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

print("Leyendo columnas necesarias:", IN)

cols = [
    "target_year",
    "biblionumber",
    "título",
    "autor_limpio_v2",
    "asesor_limpio_v2",
    "asesores_limpios_v2",
]

df = pd.read_parquet(IN, columns=[c for c in cols if c in pd.read_parquet(IN).columns])

print("Filas:", len(df))

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

def split_pipe(s):
    s = clean_str(s)
    if not s:
        return []
    return [x.strip() for x in re.split(r"\s*\|\s*", s) if x.strip()]

def flags_for_name(s):
    s0 = clean_str(s)
    k = norm_key(s0)

    flags = {}

    flags["flag_trailing_number"] = bool(re.search(r"\b\d{1,8}$", s0))
    flags["flag_any_digit"] = bool(re.search(r"\d", s0))
    flags["flag_role_residue"] = any(r in k for r in [
        "sustentante", "asesor", "director", "tutor",
        "colaborador", "institucion", "entidad participante",
        "universidad nacional autonoma de mexico",
        "tesis", "presenta", "para obtener",
    ])
    flags["flag_bad_chars"] = bool(re.search(r"[\[\]\{\}<>=_*#@\\]", s0))
    flags["flag_mojibake"] = bool(re.search(r"Ã|Â|�", s0))
    flags["flag_too_short"] = len(k) <= 2
    flags["flag_too_long"] = len(s0) > 120
    flags["flag_bad_sep"] = bool(re.search(r"\|\s*\||;;|,,", s0))
    flags["flag_inverted_empty"] = s0.startswith(",") or s0.endswith(",")

    return flags

flag_counter = Counter()
freq_counter = Counter()
variant_names = defaultdict(set)
suspicious_rows = []
digit_rows = []
trailing_rows = []

MAX_SUSPICIOUS_ROWS = 5000
MAX_DIGIT_ROWS = 2000
MAX_TRAILING_ROWS = 2000

def add_name(row_idx, role, source_col, name):
    name = clean_str(name)
    if not name:
        return

    k = norm_key(name)
    freq_counter[(role, source_col, name, k)] += 1
    variant_names[(role, k)].add(name)

    flags = flags_for_name(name)

    any_flag = any(flags.values())

    for f, val in flags.items():
        if val:
            flag_counter[f] += 1

    if any_flag and len(suspicious_rows) < MAX_SUSPICIOUS_ROWS:
        base = {
            "row_index": row_idx,
            "role": role,
            "source_col": source_col,
            "name": name,
            "name_key": k,
            "target_year": df.at[row_idx, "target_year"] if "target_year" in df.columns else "",
            "biblionumber": df.at[row_idx, "biblionumber"] if "biblionumber" in df.columns else "",
            "titulo": df.at[row_idx, "título"] if "título" in df.columns else "",
        }
        base.update(flags)
        suspicious_rows.append(base)

    if flags["flag_any_digit"] and len(digit_rows) < MAX_DIGIT_ROWS:
        digit_rows.append({
            "row_index": row_idx,
            "role": role,
            "source_col": source_col,
            "name": name,
            "target_year": df.at[row_idx, "target_year"] if "target_year" in df.columns else "",
            "biblionumber": df.at[row_idx, "biblionumber"] if "biblionumber" in df.columns else "",
        })

    if flags["flag_trailing_number"] and len(trailing_rows) < MAX_TRAILING_ROWS:
        trailing_rows.append({
            "row_index": row_idx,
            "role": role,
            "source_col": source_col,
            "name": name,
            "target_year": df.at[row_idx, "target_year"] if "target_year" in df.columns else "",
            "biblionumber": df.at[row_idx, "biblionumber"] if "biblionumber" in df.columns else "",
        })

n = len(df)

for i in range(n):
    if i % 5000 == 0:
        print(f"Procesadas filas: {i:,}/{n:,}", flush=True)

    if "autor_limpio_v2" in df.columns:
        add_name(i, "autor", "autor_limpio_v2", df.at[i, "autor_limpio_v2"])

    if "asesor_limpio_v2" in df.columns:
        add_name(i, "asesor_principal", "asesor_limpio_v2", df.at[i, "asesor_limpio_v2"])

    if "asesores_limpios_v2" in df.columns:
        for p in split_pipe(df.at[i, "asesores_limpios_v2"]):
            add_name(i, "asesor_lista", "asesores_limpios_v2", p)

print(f"Procesadas filas: {n:,}/{n:,}")

# Resumen flags
flag_summary = pd.DataFrame([
    {"flag": k, "n": v}
    for k, v in flag_counter.items()
]).sort_values("n", ascending=False)

flag_summary.to_csv(OUT_DIR / "suspicious_flags_summary.csv", index=False, encoding="utf-8")

# Sospechosos sample
pd.DataFrame(suspicious_rows).to_csv(
    OUT_DIR / "suspicious_names_sample.csv",
    index=False,
    encoding="utf-8"
)

pd.DataFrame(digit_rows).to_csv(
    OUT_DIR / "names_with_digits_sample.csv",
    index=False,
    encoding="utf-8"
)

pd.DataFrame(trailing_rows).to_csv(
    OUT_DIR / "names_trailing_numbers_sample.csv",
    index=False,
    encoding="utf-8"
)

# Frecuencias top únicamente
top_freq = pd.DataFrame([
    {
        "role": role,
        "source_col": source_col,
        "name": name,
        "name_key": key,
        "n": count
    }
    for (role, source_col, name, key), count in freq_counter.most_common(5000)
])

top_freq.to_csv(OUT_DIR / "names_frequency_top5000.csv", index=False, encoding="utf-8")

# Variantes sospechosas: mismo key, varias formas
variant_rows = []
for (role, key), names_set in variant_names.items():
    if len(names_set) > 1:
        variant_rows.append({
            "role": role,
            "name_key": key,
            "variants": len(names_set),
            "examples": " | ".join(list(names_set)[:10]),
        })

variants = pd.DataFrame(variant_rows)
if len(variants):
    variants = variants.sort_values(["variants", "name_key"], ascending=[False, True])
variants.to_csv(OUT_DIR / "name_variants_same_key_sample.csv", index=False, encoding="utf-8")

print("\nLISTO auditoría rápida")
print("Carpeta:", OUT_DIR)

print("\nResumen flags:")
if len(flag_summary):
    print(flag_summary.to_string(index=False))
else:
    print("Sin flags.")

print("\nArchivos:")
for p in sorted(OUT_DIR.glob("*.csv")):
    print("-", p)
