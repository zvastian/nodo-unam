"""Saca `entidad_clean` de data/clean/base7_kaggle_clean.parquet y la
archiva por separado.

Justificacion (ver ADR-0007): 86.51% poblado, pero 82% de eso es
informacion redundante con plantel_estandarizado (ya normalizada y mejor
mantenida). El 18% restante (94,875 filas) trae informacion potencialmente
distinta -- no se descarta, se archiva con el thesis_id como llave por si
se necesita despues (investigacion de coinstituciones, auditoria futura).

No se usa en la app desplegada (0 referencias en app/MI-TESIS-UNAM_github)
ni en el flujo actual de build_thesis_lookup.py -- seguro de remover del
producto principal.
"""
from pathlib import Path
import shutil

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_quitar_entidad_clean_2026-09-20.parquet"
ARCHIVE_DIR = ROOT / "data" / "lineage"
ARCHIVE_PATH = ARCHIVE_DIR / "entidad_clean_archivado_2026-09-20.parquet"


def main():
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()
    cols_before = len(df.columns)

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    archivo = df.loc[df["entidad_clean"].str.strip() != "", ["thesis_id", "entidad_clean", "plantel_estandarizado"]].copy()
    archivo.to_parquet(ARCHIVE_PATH, index=False)
    print(f"Archivado: {len(archivo)} filas -> {ARCHIVE_PATH}")
    print("(se guarda junto a plantel_estandarizado de esa fila, para comparar despues sin tener que re-unir con el dataset principal)")

    if not BACKUP_PATH.exists():
        shutil.copy2(DATA_PATH, BACKUP_PATH)
        print(f"Backup del dataset completo (con la columna todavia adentro): {BACKUP_PATH.name}")

    df = df.drop(columns=["entidad_clean"])

    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    cols_after = len(df.columns)
    assert n_after == n_before, f"Cambio en filas: {n_before} -> {n_after}"
    assert ids_after == ids_before, f"Cambio en thesis_id unicos: {ids_before} -> {ids_after}"
    assert cols_after == cols_before - 1, f"Se esperaba quitar exactamente 1 columna, quedaron {cols_after} de {cols_before}"

    df.to_parquet(DATA_PATH, index=False)
    print(f"\nbase7_kaggle_clean.parquet: {cols_before} -> {cols_after} columnas, {n_after} filas (sin cambio), thesis_id intacto.")


if __name__ == "__main__":
    main()
