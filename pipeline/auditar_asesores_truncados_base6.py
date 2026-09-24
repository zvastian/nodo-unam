from pathlib import Path
import pandas as pd
import re

IN = Path("base6_homogeneizada_stream.parquet")
OUT_DIR = Path("outputs/base6_homologacion")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT = OUT_DIR / "base6_posibles_asesores_truncados.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

# Leer solo columnas necesarias
all_cols = pd.read_parquet(IN, columns=[]).columns.tolist() if False else None

cols = [
    "thesis_id",
    "Año",
    "título",
    "asesor_limpio_v2_raw",
    "asesores_limpios_v2_raw",
    "asesor_limpio_v2",
    "asesores_limpios_v2",
    "asesor_display",
    "asesores_display",
    "num_asesores",
]

# Si alguna columna no existiera, hacemos lectura robusta con pyarrow metadata
import pyarrow.parquet as pq
pf = pq.ParquetFile(IN)
available = set(pf.schema.names)
use_cols = [c for c in cols if c in available]

df = pd.read_parquet(IN, columns=use_cols)

def clean(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

a = df["asesor_limpio_v2_raw"].map(clean) if "asesor_limpio_v2_raw" in df.columns else pd.Series([""] * len(df), index=df.index)
b = df["asesores_limpios_v2_raw"].map(clean) if "asesores_limpios_v2_raw" in df.columns else pd.Series([""] * len(df), index=df.index)

# Sospecha base:
# lista cruda más corta que principal crudo, y ambos no vacíos.
mask = (
    a.ne("")
    & b.ne("")
    & (b.str.len() + 5 < a.str.len())
)

# Condición adicional convertida a Series
contains_or_suffix = pd.Series(
    [
        (bb.lower() in aa.lower()) or aa.lower().endswith(bb.lower())
        for aa, bb in zip(a, b)
    ],
    index=df.index
)

mask2 = mask & contains_or_suffix

sus = df[mask2].copy()
sus["len_asesor_raw"] = a[mask2].str.len().values
sus["len_asesores_raw"] = b[mask2].str.len().values

# Diferencia de longitud para priorizar
sus["len_diff"] = sus["len_asesor_raw"] - sus["len_asesores_raw"]

sus = sus.sort_values("len_diff", ascending=False)

sus.to_csv(OUT, index=False, encoding="utf-8")

print("Casos sospechosos:", len(sus))
print("Output:", OUT)

if len(sus):
    print(sus.head(80).to_string(index=False))
else:
    print("No se detectaron truncamientos obvios.")
