from pathlib import Path
import re
import unicodedata
import pandas as pd

IN = Path("recovery/processed/marc_recovered_normalized.parquet")
OUT_DIR = Path("recovery/processed/name_audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

df = pd.read_parquet(IN)

NAME_COLS = [
    "autor_limpio_v2",
    "asesor_limpio_v2",
    "asesores_limpios_v2",
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

def split_pipe(s):
    s = clean_str(s)
    if not s:
        return []
    return [x.strip() for x in re.split(r"\s*\|\s*", s) if x.strip()]

def explode_names(df, col, role):
    rows = []
    for i, v in enumerate(df[col].fillna("").astype(str)):
        parts = split_pipe(v) if col == "asesores_limpios_v2" else [clean_str(v)]
        for p in parts:
            p = clean_str(p)
            if not p:
                continue
            rows.append({
                "row_id": i,
                "role": role,
                "source_col": col,
                "name": p,
                "name_key": norm_key(p),
                "target_year": df.iloc[i].get("target_year", ""),
                "biblionumber": df.iloc[i].get("biblionumber", ""),
                "titulo": df.iloc[i].get("título", ""),
            })
    return pd.DataFrame(rows)

all_names = []

if "autor_limpio_v2" in df.columns:
    all_names.append(explode_names(df, "autor_limpio_v2", "autor"))

if "asesor_limpio_v2" in df.columns:
    all_names.append(explode_names(df, "asesor_limpio_v2", "asesor_principal"))

if "asesores_limpios_v2" in df.columns:
    all_names.append(explode_names(df, "asesores_limpios_v2", "asesor_lista"))

names = pd.concat(all_names, ignore_index=True) if all_names else pd.DataFrame()

print("Total nombres expandidos:", len(names))

# -------------------------
# Flags sospechosos
# -------------------------

def flag_trailing_number(s):
    # Ej: "García López, Juan 123", "Pérez, Ana 1"
    return bool(re.search(r"\b\d{1,8}$", clean_str(s)))

def flag_any_digit(s):
    return bool(re.search(r"\d", clean_str(s)))

def flag_role_residue(s):
    k = norm_key(s)
    residues = [
        "sustentante", "asesor", "director", "tutor",
        "colaborador", "institucion", "entidad participante",
        "universidad nacional autonoma de mexico",
        "tesis", "presenta", "para obtener",
    ]
    return any(r in k for r in residues)

def flag_bad_chars(s):
    # Caracteres raros frecuentes por parser/HTML.
    return bool(re.search(r"[\[\]\{\}<>=_*#@\\]", clean_str(s)))

def flag_mojibake(s):
    return bool(re.search(r"Ã|Â|�", clean_str(s)))

def flag_too_short(s):
    k = norm_key(s)
    return len(k) <= 2

def flag_too_long(s):
    return len(clean_str(s)) > 120

def flag_repeated_pipe_or_sep(s):
    return bool(re.search(r"\|\s*\||;;|,,", clean_str(s)))

def flag_inverted_empty(s):
    s = clean_str(s)
    return s.startswith(",") or s.endswith(",")

names["flag_trailing_number"] = names["name"].map(flag_trailing_number)
names["flag_any_digit"] = names["name"].map(flag_any_digit)
names["flag_role_residue"] = names["name"].map(flag_role_residue)
names["flag_bad_chars"] = names["name"].map(flag_bad_chars)
names["flag_mojibake"] = names["name"].map(flag_mojibake)
names["flag_too_short"] = names["name"].map(flag_too_short)
names["flag_too_long"] = names["name"].map(flag_too_long)
names["flag_bad_sep"] = names["name"].map(flag_repeated_pipe_or_sep)
names["flag_inverted_empty"] = names["name"].map(flag_inverted_empty)

flag_cols = [c for c in names.columns if c.startswith("flag_")]
names["any_flag"] = names[flag_cols].any(axis=1)

# -------------------------
# Outputs
# -------------------------

names.to_csv(OUT_DIR / "all_names_expanded.csv", index=False, encoding="utf-8")

sus = names[names["any_flag"]].copy()
sus.to_csv(OUT_DIR / "suspicious_names_all.csv", index=False, encoding="utf-8")

# Resumen por flag
flag_summary = []
for c in flag_cols:
    flag_summary.append({
        "flag": c,
        "n": int(names[c].sum()),
    })

flag_summary = pd.DataFrame(flag_summary).sort_values("n", ascending=False)
flag_summary.to_csv(OUT_DIR / "suspicious_flags_summary.csv", index=False, encoding="utf-8")

# Frecuencias de nombres
freq = (
    names.groupby(["role", "source_col", "name", "name_key"], dropna=False)
         .size()
         .reset_index(name="n")
         .sort_values("n", ascending=False)
)

freq.to_csv(OUT_DIR / "names_frequency.csv", index=False, encoding="utf-8")

# Nombres con dígitos
names[names["flag_any_digit"]].to_csv(
    OUT_DIR / "names_with_digits.csv",
    index=False,
    encoding="utf-8"
)

# Nombres con números al final
names[names["flag_trailing_number"]].to_csv(
    OUT_DIR / "names_trailing_numbers.csv",
    index=False,
    encoding="utf-8"
)

# Potenciales variantes: mismo key normalizado con varias formas visibles
variants = (
    freq.groupby(["role", "name_key"], dropna=False)
        .agg(
            variants=("name", "nunique"),
            total=("n", "sum"),
            examples=("name", lambda x: " | ".join(list(dict.fromkeys(x))[:10]))
        )
        .reset_index()
)

variants = variants[variants["variants"] > 1].sort_values(
    ["variants", "total"],
    ascending=False
)

variants.to_csv(OUT_DIR / "name_variants_same_key.csv", index=False, encoding="utf-8")

print("\nLISTO auditoría nombres")
print("Carpeta:", OUT_DIR)

print("\nResumen flags:")
print(flag_summary.to_string(index=False))

print("\nTop sospechosos:")
cols = ["role", "source_col", "name", "target_year", "biblionumber"] + flag_cols
print(sus[cols].head(50).to_string(index=False))

print("\nArchivos creados:")
for p in sorted(OUT_DIR.glob("*.csv")):
    print("-", p)
