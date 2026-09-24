from pathlib import Path
import re
import pandas as pd

IN = Path("recovery/processed/marc_recovered_normalized.parquet")
BACKUP = Path("recovery/processed/marc_recovered_normalized.before_authors_display_patch.parquet")
OUT = IN

OUT_DIR = Path("recovery/processed/name_audit_fast")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE = OUT_DIR / "marc_authors_display_patch_sample.csv"
FREQ = OUT_DIR / "marc_authors_count_frequency.csv"

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

print("Leyendo:", IN)
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

def clean_one_author(name):
    s = clean_str(name)

    if not s:
        return ""

    # Vacíos semánticos.
    if re.fullmatch(r"(?i)\s*(sin autor|registro en proceso|asesor)\s*", s):
        return ""

    # Quitar residuos muy conservadores.
    s = re.sub(r",?\s*\$e\s*(sustentante|autor|coautor|asesor|asesora)\b", "", s, flags=re.I)
    s = re.sub(r",?\s*\$e[a-záéíóúñ ]+", "", s, flags=re.I)

    # Quitar roles al final.
    s = re.sub(r",?\s*(sustentante|coautor|autor|asesor|asesora)\.?\s*$", "", s, flags=re.I)

    # Quitar fechas biográficas finales si existieran.
    s = re.sub(r",?\s*(18|19|20)\d{2}\s*-\s*((18|19|20)\d{2})?\s*$", "", s)

    # Puntuación y espacios.
    s = s.replace("\\", " ")
    s = re.sub(r"[<>]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*[,;:.]+$", "", s).strip()
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,+", ",", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s

def split_authors(value):
    value = clean_str(value)
    if not value:
        return []

    # Aceptamos | y ; por robustez, aunque MARC normalmente trae un solo autor.
    parts = re.split(r"\s*(?:\||;)\s*", value)

    out = []
    for p in parts:
        p = clean_one_author(p)
        if p and p not in out:
            out.append(p)

    return out

def pipe_authors(value):
    return " | ".join(split_authors(value))

def invert_name_for_display(name):
    name = clean_one_author(name).strip(" ,;")

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

def display_pipe_from_pipe(value):
    value = clean_str(value)
    if not value:
        return ""

    parts = [p.strip() for p in value.split("|") if p.strip()]
    out = []

    for p in parts:
        d = invert_name_for_display(p)
        if d and d not in out:
            out.append(d)

    return " | ".join(out)

def autor_ui_from_row(autor_display, num_autores):
    autor_display = clean_str(autor_display)

    try:
        n = int(num_autores)
    except Exception:
        n = 0

    if n == 0 or not autor_display:
        return "Autor no registrado"

    if n == 1:
        return autor_display

    return f"{autor_display} · +{n - 1} más"

# Crear raw si no existe.
if "autor_limpio_v2_raw" not in df.columns:
    df["autor_limpio_v2_raw"] = df["autor_limpio_v2"] if "autor_limpio_v2" in df.columns else ""

# Fuente: raw si existe; fallback autor_limpio_v2.
source = df["autor_limpio_v2_raw"].fillna("").astype(str)
fallback = df["autor_limpio_v2"].fillna("").astype(str) if "autor_limpio_v2" in df.columns else pd.Series([""] * len(df))

chosen = [
    clean_str(a) if clean_str(a) else clean_str(b)
    for a, b in zip(source, fallback)
]

# Lista técnica completa.
df["autores_limpios_v2"] = [pipe_authors(x) for x in chosen]

# Principal técnico.
df["autor_limpio_v2"] = df["autores_limpios_v2"].map(
    lambda x: next((p.strip() for p in str(x).split("|") if p.strip()), "")
)

# Conteo.
df["num_autores"] = df["autores_limpios_v2"].map(
    lambda x: len([p for p in str(x).split("|") if p.strip()])
)

# Display.
df["autor_display"] = df["autor_limpio_v2"].map(invert_name_for_display)
df["autores_display"] = df["autores_limpios_v2"].map(display_pipe_from_pipe)

# Flags.
df["flag_sin_autor"] = df["num_autores"] == 0
df["flag_multiples_autores"] = df["num_autores"] > 1
df["flag_autores_4plus"] = df["num_autores"] >= 4

# UI compacta.
df["autor_ui"] = [
    autor_ui_from_row(a, n)
    for a, n in zip(df["autor_display"], df["num_autores"])
]

# Guardar.
df.to_parquet(OUT, index=False)

freq = (
    df.groupby("num_autores")
      .size()
      .reset_index(name="n_tesis")
      .sort_values("num_autores")
)
freq["pct"] = freq["n_tesis"] / len(df) * 100
freq.to_csv(FREQ, index=False, encoding="utf-8")

sample_cols = [
    "biblionumber",
    "system_number",
    "Año",
    "título",
    "autor_limpio_v2_raw",
    "autores_limpios_v2",
    "autor_limpio_v2",
    "autores_display",
    "autor_display",
    "num_autores",
    "autor_ui",
]

sample_cols = [c for c in sample_cols if c in df.columns]
df[sample_cols].head(1000).to_csv(SAMPLE, index=False, encoding="utf-8")

print("\nLISTO patch autores MARC")
print("Archivo actualizado:", OUT)
print("Backup:", BACKUP)
print("Sample:", SAMPLE)
print("Freq:", FREQ)

print("\nDistribución num_autores:")
print(freq.to_string(index=False))

print("\nEjemplos:")
print(df[sample_cols].head(20).to_string(index=False))
