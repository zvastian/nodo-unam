from pathlib import Path
import re
import pandas as pd

IN = Path("base6.parquet")
OUT_DIR = Path("outputs/base6_homologacion")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT = Path("base6_homogeneizada.parquet")
LOG = OUT_DIR / "base6_homogeneizacion_nombres_log.csv"
SAMPLE = OUT_DIR / "base6_homogeneizada_name_display_sample.csv"
FREQ = OUT_DIR / "base6_homogeneizada_asesores_por_tesis_frecuencia.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

print("Leyendo:", IN)
df = pd.read_parquet(IN)

def clean_str(x):
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def clean_one_name(name):
    original = clean_str(name)
    s = original

    if not s:
        return ""

    # Quitar subcampos MARC/Aleph residuales
    # Ej: "Sandoval Perez, Mario,$easesor"
    s = re.sub(r",?\s*\$e\s*(asesor|asesora|sustentante|tutor|tutora|director|directora)\b", "", s, flags=re.I)
    s = re.sub(r",?\s*\$e[a-záéíóúñ ]+", "", s, flags=re.I)

    # Quitar etiquetas textuales residuales
    s = re.sub(
        r"\b(asesor|asesora|director de tesis|directora de tesis|director|directora|tutor|tutora|sustentante)\b\s*[:\-]?",
        "",
        s,
        flags=re.I
    )

    # Quitar fechas biográficas al final:
    # "Apellido, Nombre, 1954-" -> "Apellido, Nombre"
    # "Apellido, Nombre, 1954-2010" -> "Apellido, Nombre"
    s = re.sub(r",?\s+\d{4}\s*-\s*(\d{4})?\s*$", "", s)

    # Algunos vienen como "Nombre 1942-" sin coma
    s = re.sub(r"\s+\d{4}\s*-\s*(\d{4})?\s*$", "", s)

    # Limpiar basura/puntuación
    s = s.replace("\\", " ")
    s = re.sub(r"[<>]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*[,;:.]+$", "", s).strip()
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,+", ",", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s

def split_asesores_base6(value):
    value = clean_str(value)
    if not value:
        return []

    # Base6 usa principalmente ; para múltiples asesores.
    # También aceptamos | por compatibilidad.
    parts = re.split(r"\s*(?:\||;)\s*", value)

    out = []
    for p in parts:
        p = clean_one_name(p)
        if p and p not in out:
            out.append(p)

    return out

def pipe_from_asesores(value):
    return " | ".join(split_asesores_base6(value))

def invert_name_for_display(name):
    name = clean_one_name(name).strip(" ,;")
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

def display_pipe(value):
    parts = split_asesores_base6(value)
    out = []
    for p in parts:
        d = invert_name_for_display(p)
        if d and d not in out:
            out.append(d)
    return " | ".join(out)

changes = []

def log_change(idx, col, old, new):
    if old != new and len(changes) < 200000:
        changes.append({
            "row_index": idx,
            "thesis_id": df.at[idx, "thesis_id"] if "thesis_id" in df.columns else "",
            "Año": df.at[idx, "Año"] if "Año" in df.columns else "",
            "título": df.at[idx, "título"] if "título" in df.columns else "",
            "column": col,
            "old": old,
            "new": new,
        })

# Guardar raw antes de tocar
if "autor_limpio_v2" in df.columns and "autor_limpio_v2_raw" not in df.columns:
    df["autor_limpio_v2_raw"] = df["autor_limpio_v2"]

if "asesor_limpio_v2" in df.columns and "asesor_limpio_v2_raw" not in df.columns:
    df["asesor_limpio_v2_raw"] = df["asesor_limpio_v2"]

if "asesores_limpios_v2" in df.columns and "asesores_limpios_v2_raw" not in df.columns:
    df["asesores_limpios_v2_raw"] = df["asesores_limpios_v2"]

# Autor limpio
if "autor_limpio_v2" in df.columns:
    old = df["autor_limpio_v2"].fillna("").astype(str)
    new = old.map(clean_one_name)
    for idx in df.index[old != new]:
        log_change(idx, "autor_limpio_v2", old.loc[idx], new.loc[idx])
    df["autor_limpio_v2"] = new
else:
    df["autor_limpio_v2"] = ""

# Asesores lista limpia
if "asesores_limpios_v2" in df.columns:
    old = df["asesores_limpios_v2"].fillna("").astype(str)
    new = old.map(pipe_from_asesores)
    for idx in df.index[old != new]:
        log_change(idx, "asesores_limpios_v2", old.loc[idx], new.loc[idx])
    df["asesores_limpios_v2"] = new
else:
    if "asesor_limpio_v2" in df.columns:
        df["asesores_limpios_v2"] = df["asesor_limpio_v2"].map(pipe_from_asesores)
    else:
        df["asesores_limpios_v2"] = ""

# Asesor principal desde lista
def first_advisor(x):
    parts = [p.strip() for p in str(x).split("|") if p.strip()]
    return parts[0] if parts else ""

if "asesor_limpio_v2" not in df.columns:
    df["asesor_limpio_v2"] = ""

old = df["asesor_limpio_v2"].fillna("").astype(str)
new = df["asesores_limpios_v2"].map(first_advisor)

for idx in df.index[old != new]:
    log_change(idx, "asesor_limpio_v2", old.loc[idx], new.loc[idx])

df["asesor_limpio_v2"] = new

# Conteos
df["num_asesores"] = df["asesores_limpios_v2"].map(
    lambda x: len([p for p in str(x).split("|") if p.strip()])
)

df["num_autores"] = df["autor_limpio_v2"].map(
    lambda x: 1 if clean_str(x) else 0
)

# Display
df["autor_display"] = df["autor_limpio_v2"].map(invert_name_for_display)
df["asesor_display"] = df["asesor_limpio_v2"].map(invert_name_for_display)
df["asesores_display"] = df["asesores_limpios_v2"].map(display_pipe)

df["flag_sin_asesor"] = df["num_asesores"] == 0
df["flag_multiples_asesores"] = df["num_asesores"] > 1
df["flag_asesores_4plus"] = df["num_asesores"] >= 4

def asesor_ui(row):
    n = int(row.get("num_asesores", 0) or 0)
    principal = clean_str(row.get("asesor_display", ""))
    if n == 0 or not principal:
        return "Asesor no registrado"
    if n == 1:
        return principal
    return f"{principal} · +{n - 1} más"

df["asesor_ui"] = df.apply(asesor_ui, axis=1)

# texto_completo_url homologado
if "texto_completo_url" not in df.columns:
    if "link_extraido_regex" in df.columns:
        df["texto_completo_url"] = df["link_extraido_regex"]
    else:
        df["texto_completo_url"] = ""

# Guardar
print("Guardando:", OUT)
df.to_parquet(OUT, index=False)

changes_df = pd.DataFrame(changes)
changes_df.to_csv(LOG, index=False, encoding="utf-8")

freq = (
    df.groupby("num_asesores")
      .size()
      .reset_index(name="n_tesis")
      .sort_values("num_asesores")
)
freq["pct"] = freq["n_tesis"] / len(df) * 100
freq.to_csv(FREQ, index=False, encoding="utf-8")

sample_cols = [
    "thesis_id",
    "Año",
    "título",
    "autor_limpio_v2_raw",
    "autor_limpio_v2",
    "autor_display",
    "asesor_limpio_v2_raw",
    "asesores_limpios_v2_raw",
    "asesor_limpio_v2",
    "asesor_display",
    "asesores_limpios_v2",
    "asesores_display",
    "num_asesores",
    "asesor_ui",
]
sample_cols = [c for c in sample_cols if c in df.columns]
df[sample_cols].head(1000).to_csv(SAMPLE, index=False, encoding="utf-8")

print("\nLISTO")
print("Output:", OUT)
print("Log:", LOG)
print("Sample:", SAMPLE)
print("Freq:", FREQ)
print("\nDistribución num_asesores:")
print(freq.to_string(index=False))
print("\nCambios registrados:", len(changes_df))
