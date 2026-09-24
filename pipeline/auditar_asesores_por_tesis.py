from pathlib import Path
import pandas as pd
import re

IN = Path("recovery/processed/marc_recovered_normalized.parquet")
OUT_DIR = Path("recovery/processed/name_audit_fast")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FREQ = OUT_DIR / "asesores_por_tesis_frecuencia.csv"
OUT_EDGE = OUT_DIR / "asesores_por_tesis_edge_cases.csv"
OUT_SAMPLE_MULTI = OUT_DIR / "asesores_multiples_sample.csv"
OUT_NO_ASESOR = OUT_DIR / "tesis_sin_asesor_sample.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

df = pd.read_parquet(IN)

def clean_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def split_asesores(x):
    x = clean_str(x)
    if not x:
        return []
    parts = [p.strip() for p in re.split(r"\s*\|\s*", x) if p.strip()]
    # dedupe conservador preservando orden
    out = []
    for p in parts:
        if p not in out:
            out.append(p)
    return out

df["asesores_lista_audit"] = df["asesores_limpios_v2"].map(split_asesores)
df["num_asesores_audit"] = df["asesores_lista_audit"].map(len)

# Frecuencia principal
freq = (
    df.groupby("num_asesores_audit", dropna=False)
      .size()
      .reset_index(name="n_tesis")
      .sort_values("num_asesores_audit")
)

freq["pct"] = freq["n_tesis"] / len(df) * 100
freq.to_csv(OUT_FREQ, index=False, encoding="utf-8")

# Casos edge: sin asesor o demasiados asesores
edge = df[
    (df["num_asesores_audit"] == 0)
    | (df["num_asesores_audit"] >= 4)
].copy()

edge_cols = [
    "target_year",
    "biblionumber",
    "system_number",
    "Año",
    "título",
    "autor_limpio_v2",
    "asesores_limpios_v2",
    "asesor_limpio_v2",
    "num_asesores",
    "num_asesores_audit",
    "grado",
    "nivel_estandar",
    "plantel_display",
    "texto_completo_url",
]

edge_cols = [c for c in edge_cols if c in edge.columns]
edge[edge_cols].to_csv(OUT_EDGE, index=False, encoding="utf-8")

# Muestra de tesis con múltiples asesores
multi = df[df["num_asesores_audit"] >= 2].copy()
multi[edge_cols].head(500).to_csv(OUT_SAMPLE_MULTI, index=False, encoding="utf-8")

# Muestra sin asesor
noasesor = df[df["num_asesores_audit"] == 0].copy()
noasesor[edge_cols].head(500).to_csv(OUT_NO_ASESOR, index=False, encoding="utf-8")

print("\nLISTO auditoría asesores por tesis")
print("Total tesis:", len(df))
print("\nFrecuencia:")
print(freq.to_string(index=False))

print("\nEdge cases:")
print("Sin asesor:", int((df["num_asesores_audit"] == 0).sum()))
print("Con 2+ asesores:", int((df["num_asesores_audit"] >= 2).sum()))
print("Con 3+ asesores:", int((df["num_asesores_audit"] >= 3).sum()))
print("Con 4+ asesores:", int((df["num_asesores_audit"] >= 4).sum()))
print("Máximo asesores en una tesis:", int(df["num_asesores_audit"].max()))

print("\nArchivos:")
print("-", OUT_FREQ)
print("-", OUT_EDGE)
print("-", OUT_SAMPLE_MULTI)
print("-", OUT_NO_ASESOR)

print("\nTop 20 casos con más asesores:")
top = df.sort_values("num_asesores_audit", ascending=False).head(20)
print(top[edge_cols].to_string(index=False))
