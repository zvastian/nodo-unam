from pathlib import Path
import pandas as pd
import re
import unicodedata

IN = Path("recovery/processed/marc_recovered_normalized.parquet")
BACKUP = Path("recovery/processed/marc_recovered_normalized.before_unam_patch.parquet")
OUT = IN

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

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

print("Leyendo:", IN)
df = pd.read_parquet(IN)

print("Filas:", len(df))

# Backup
if not BACKUP.exists():
    df.to_parquet(BACKUP, index=False)
    print("Backup creado:", BACKUP)
else:
    print("Backup ya existía:", BACKUP)

# Detectar UNAM genérica usada indebidamente como plantel
plantel_display_key = df["plantel_display"].map(norm_key)
plantel_std_key = df["plantel_estandarizado"].map(norm_key)
plantel_original_key = df["plantel_marc_original"].map(norm_key)

unam_generic = {
    "universidad nacional autonoma de mexico",
    "universidad nacional autonoma de mexico unam",
    "unam",
}

mask = (
    plantel_display_key.isin(unam_generic)
    | plantel_std_key.isin(unam_generic)
    | plantel_original_key.isin(unam_generic)
)

print("\nCasos detectados para corregir:", int(mask.sum()))

if mask.sum() > 0:
    print("\nAntes:")
    print(
        df.loc[mask, ["plantel_marc_original", "plantel_estandarizado", "plantel_display"]]
          .value_counts()
          .reset_index(name="n")
          .to_string(index=False)
    )

df.loc[mask, "plantel_estandarizado"] = "no especificado unam"
df.loc[mask, "plantel_display"] = "No especificado"

df.to_parquet(OUT, index=False)

print("\nPatch aplicado:", OUT)

# Auditoría post
print("\nDespués: casos sospechosos")
post_display_key = df["plantel_display"].map(norm_key)
post_std_key = df["plantel_estandarizado"].map(norm_key)

post_mask = (
    post_display_key.isin(unam_generic)
    | post_std_key.isin(unam_generic)
)

print("Sospechosos restantes:", int(post_mask.sum()))

print("\nTop plantel_display después:")
print(
    df["plantel_display"]
    .value_counts()
    .head(30)
    .to_string()
)

print("\nNo especificado total:")
print((df["plantel_display"] == "No especificado").sum())
