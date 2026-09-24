from pathlib import Path
import pandas as pd
import re

IN = Path("recovery/processed/marc_recovered_normalized.parquet")
BACKUP = Path("recovery/processed/marc_recovered_normalized.before_name_display_patch.parquet")
OUT = IN
LOG = Path("recovery/processed/name_audit_fast/name_display_patch_sample.csv")

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

df = pd.read_parquet(IN)

if not BACKUP.exists():
    df.to_parquet(BACKUP, index=False)
    print("Backup creado:", BACKUP)
else:
    print("Backup ya existía:", BACKUP)

def clean_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def invert_name_for_display(name):
    """
    Convierte:
      'Márquez García, Antonio Zoilo'
    en:
      'Antonio Zoilo Márquez García'

    Conserva nombres sin coma tal como están.
    Solo usa la primera coma.
    """
    name = clean_str(name).strip(" ,;")

    if not name:
        return ""

    if "," not in name:
        return name

    left, right = name.split(",", 1)
    left = clean_str(left).strip(" ,;")
    right = clean_str(right).strip(" ,;")

    if not left or not right:
        return name

    return clean_str(f"{right} {left}")

def split_pipe(value):
    value = clean_str(value)
    if not value:
        return []
    return [p.strip() for p in re.split(r"\s*\|\s*", value) if p.strip()]

def display_pipe(value):
    parts = split_pipe(value)
    display = []
    for p in parts:
        d = invert_name_for_display(p)
        if d and d not in display:
            display.append(d)
    return " | ".join(display)

# Crear columnas display
df["autor_display"] = df["autor_limpio_v2"].map(invert_name_for_display) if "autor_limpio_v2" in df.columns else ""
df["asesor_display"] = df["asesor_limpio_v2"].map(invert_name_for_display) if "asesor_limpio_v2" in df.columns else ""
df["asesores_display"] = df["asesores_limpios_v2"].map(display_pipe) if "asesores_limpios_v2" in df.columns else ""

# Asegurar num_asesores y flags para UI
if "asesores_limpios_v2" in df.columns:
    df["num_asesores"] = df["asesores_limpios_v2"].map(lambda x: len(split_pipe(x)))
else:
    df["num_asesores"] = 0

df["flag_sin_asesor"] = df["num_asesores"] == 0
df["flag_multiples_asesores"] = df["num_asesores"] > 1
df["flag_asesores_4plus"] = df["num_asesores"] >= 4

# Texto compacto para hover/tarjeta
def asesor_ui(row):
    n = int(row.get("num_asesores", 0) or 0)
    principal = clean_str(row.get("asesor_display", ""))

    if n == 0 or not principal:
        return "Asesor no registrado"

    if n == 1:
        return principal

    return f"{principal} · +{n - 1} más"

df["asesor_ui"] = df.apply(asesor_ui, axis=1)

# Guardar
df.to_parquet(OUT, index=False)

# Muestra de cambios para revisar
cols = [
    "biblionumber",
    "Año",
    "título",
    "autor_limpio_v2",
    "autor_display",
    "asesor_limpio_v2",
    "asesor_display",
    "asesores_limpios_v2",
    "asesores_display",
    "num_asesores",
    "asesor_ui",
]

cols = [c for c in cols if c in df.columns]
sample = df[cols].head(1000)
sample.to_csv(LOG, index=False, encoding="utf-8")

print("\nLISTO")
print("Archivo actualizado:", OUT)
print("Backup:", BACKUP)
print("Sample:", LOG)

print("\nEjemplos:")
print(df[cols].head(20).to_string(index=False))

print("\nDistribución num_asesores:")
print(df["num_asesores"].value_counts().sort_index().to_string())
