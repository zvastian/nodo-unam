from pathlib import Path
import pandas as pd

IN = Path("recovery/processed/marc_recovered_normalized.parquet")
BACKUP = Path("recovery/processed/marc_recovered_normalized.before_names_manual_patch.parquet")
OUT = IN
LOG = Path("recovery/processed/name_audit_fast/manual_name_patch_log.csv")

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

df = pd.read_parquet(IN)

if not BACKUP.exists():
    df.to_parquet(BACKUP, index=False)
    print("Backup creado:", BACKUP)
else:
    print("Backup ya existía:", BACKUP)

changes = []

def patch_value(mask, col, new_value):
    global df
    idxs = df.index[mask].tolist()
    for idx in idxs:
        old = df.at[idx, col]
        changes.append({
            "row_index": idx,
            "biblionumber": df.at[idx, "biblionumber"] if "biblionumber" in df.columns else "",
            "Año": df.at[idx, "Año"] if "Año" in df.columns else "",
            "titulo": df.at[idx, "título"] if "título" in df.columns else "",
            "column": col,
            "old": old,
            "new": new_value,
        })
        df.at[idx, col] = new_value

# 1. Campos Díaz, Delfin0 -> Campos Díaz, Delfino
mask_autor = (
    (df["biblionumber"].astype(str) == "228094")
    & (df["autor_limpio_v2"].astype(str) == "Campos Díaz, Delfin0")
)
patch_value(mask_autor, "autor_limpio_v2", "Campos Díaz, Delfino")

# 2. Navarro Morales, Luis A. ] -> Navarro Morales, Luis A.
mask_asesores_lista = (
    (df["biblionumber"].astype(str) == "25334")
    & (df["asesores_limpios_v2"].astype(str).str.contains("Navarro Morales, Luis A. ]", regex=False, na=False))
)

for idx in df.index[mask_asesores_lista]:
    old = df.at[idx, "asesores_limpios_v2"]
    new = str(old).replace("Navarro Morales, Luis A. ]", "Navarro Morales, Luis A.")
    changes.append({
        "row_index": idx,
        "biblionumber": df.at[idx, "biblionumber"],
        "Año": df.at[idx, "Año"],
        "titulo": df.at[idx, "título"],
        "column": "asesores_limpios_v2",
        "old": old,
        "new": new,
    })
    df.at[idx, "asesores_limpios_v2"] = new

# Recalcular asesor principal si ese registro dependía de la lista
if "asesor_limpio_v2" in df.columns and "asesores_limpios_v2" in df.columns:
    for idx in df.index[mask_asesores_lista]:
        old = df.at[idx, "asesor_limpio_v2"]
        new = str(df.at[idx, "asesores_limpios_v2"]).split("|")[0].strip()
        if old != new:
            changes.append({
                "row_index": idx,
                "biblionumber": df.at[idx, "biblionumber"],
                "Año": df.at[idx, "Año"],
                "titulo": df.at[idx, "título"],
                "column": "asesor_limpio_v2",
                "old": old,
                "new": new,
            })
            df.at[idx, "asesor_limpio_v2"] = new

# Recalcular conteos
if "num_autores" in df.columns:
    df["num_autores"] = df["autor_limpio_v2"].astype(str).str.strip().ne("").astype(int)

if "num_asesores" in df.columns:
    df["num_asesores"] = df["asesores_limpios_v2"].astype(str).apply(
        lambda x: len([p for p in x.split("|") if p.strip()])
    )

df.to_parquet(OUT, index=False)

changes_df = pd.DataFrame(changes)
changes_df.to_csv(LOG, index=False, encoding="utf-8")

print("\nLISTO patch manual nombres")
print("Cambios:", len(changes_df))
print("Log:", LOG)
print(changes_df.to_string(index=False))
