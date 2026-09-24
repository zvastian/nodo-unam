from pathlib import Path
import re
import pandas as pd

IN = Path("recovery/processed/marc_recovered_normalized.parquet")
BACKUP = Path("recovery/processed/marc_recovered_normalized.before_names_patch.parquet")
OUT = IN
OUT_CHANGES = Path("recovery/processed/name_audit/name_cleaning_changes.csv")

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

def clean_one_name(name):
    original = clean_str(name)
    s = original

    if not s:
        return ""

    # Quitar etiquetas/roles residuales
    s = re.sub(r"\[(sustentante|asesor|director|tutor|colaborador|miembro del comité tutor|miembro del comite tutor)\]", "", s, flags=re.I)
    s = re.sub(r"\b(sustentante|asesor|director de tesis|director|tutor de tesis|tutor)\b\s*[:\-]?", "", s, flags=re.I)

    # Quitar residuos HTML o separadores extraños
    s = re.sub(r"[<>]", " ", s)
    s = s.replace("\\", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Quitar números basura al final.
    # Conservador: solo si son 1 a 8 dígitos al final y antes hay una letra.
    # Ej: "García López, Juan 123" -> "García López, Juan"
    s = re.sub(r"(?<=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])\s+\d{1,8}$", "", s)

    # Quitar puntuación final repetida
    s = re.sub(r"\s*[,;:.]+$", "", s).strip()

    # Arreglar comas dobles / espacios antes de coma
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,+", ",", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s

def clean_pipe_names(value):
    value = clean_str(value)
    if not value:
        return ""

    parts = [p.strip() for p in re.split(r"\s*\|\s*", value) if p.strip()]
    cleaned = []

    for p in parts:
        c = clean_one_name(p)
        if c and c not in cleaned:
            cleaned.append(c)

    return " | ".join(cleaned)

changes = []

def patch_col(col, pipe=False):
    if col not in df.columns:
        return

    old_vals = df[col].fillna("").astype(str)
    if pipe:
        new_vals = old_vals.map(clean_pipe_names)
    else:
        new_vals = old_vals.map(clean_one_name)

    mask = old_vals != new_vals

    for idx in df.index[mask]:
        changes.append({
            "row_index": idx,
            "column": col,
            "old": old_vals.loc[idx],
            "new": new_vals.loc[idx],
            "biblionumber": df.loc[idx].get("biblionumber", ""),
            "Año": df.loc[idx].get("Año", ""),
            "titulo": df.loc[idx].get("título", ""),
        })

    df[col] = new_vals

patch_col("autor_limpio_v2", pipe=False)
patch_col("asesor_limpio_v2", pipe=False)
patch_col("asesores_limpios_v2", pipe=True)

# Recalcular asesor principal desde lista, para consistencia
if "asesores_limpios_v2" in df.columns and "asesor_limpio_v2" in df.columns:
    def first_advisor(x):
        x = clean_str(x)
        if not x:
            return ""
        return x.split("|")[0].strip()

    old_vals = df["asesor_limpio_v2"].fillna("").astype(str)
    new_vals = df["asesores_limpios_v2"].map(first_advisor)
    mask = old_vals != new_vals

    for idx in df.index[mask]:
        changes.append({
            "row_index": idx,
            "column": "asesor_limpio_v2_recomputed",
            "old": old_vals.loc[idx],
            "new": new_vals.loc[idx],
            "biblionumber": df.loc[idx].get("biblionumber", ""),
            "Año": df.loc[idx].get("Año", ""),
            "titulo": df.loc[idx].get("título", ""),
        })

    df["asesor_limpio_v2"] = new_vals

# Recalcular num_asesores
if "asesores_limpios_v2" in df.columns:
    df["num_asesores"] = df["asesores_limpios_v2"].map(
        lambda x: len([p for p in str(x).split("|") if p.strip()])
    )

if "autor_limpio_v2" in df.columns:
    df["num_autores"] = df["autor_limpio_v2"].map(
        lambda x: 1 if clean_str(x) else 0
    )

df.to_parquet(OUT, index=False)

changes_df = pd.DataFrame(changes)
changes_df.to_csv(OUT_CHANGES, index=False, encoding="utf-8")

print("\nLISTO patch nombres")
print("Archivo actualizado:", OUT)
print("Backup:", BACKUP)
print("Cambios:", len(changes_df))
print("Log cambios:", OUT_CHANGES)

if len(changes_df):
    print("\nPrimeros cambios:")
    print(changes_df.head(50).to_string(index=False))
