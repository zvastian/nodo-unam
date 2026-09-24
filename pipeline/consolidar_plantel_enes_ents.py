"""Corrige duplicados de ENES (Leon/Merida/Morelia) y ENTS que el detector
original (basado en acentos + sufijo UNAM) no capturo porque la diferencia
era una palabra completa faltante ("unidad", o "de" mal escrito como "e").

Encontrado a peticion del usuario al pedir el recuento final de ENES.
"""
from pathlib import Path
import shutil

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_enes_ents_fix_2026-09-20.parquet"
AUDIT_PATH = ROOT / "pipeline" / "audits" / "plantel_enes_ents_2026-09-20.csv"

# (plantel_estandarizado_viejo, plantel_estandarizado_nuevo, plantel_display_nuevo)
FIXES = [
    ("escuela nacional de estudios superiores leon",
     "escuela nacional de estudios superiores unidad leon unam",
     "Escuela Nacional de Estudios Superiores, Unidad León"),
    ("escuela nacional de estudios superiores merida",
     "escuela nacional de estudios superiores unidad merida unam",
     "Escuela Nacional de Estudios Superiores, Unidad Mérida"),
    ("escuela nacional de estudios superiores morelia",
     "escuela nacional de estudios superiores unidad morelia unam",
     "Escuela Nacional de Estudios Superiores, Unidad Morelia"),
    ("escuela nacional e trabajo social",
     "escuela nacional de trabajo social unam",
     "ENTS"),
]

# Stragglers de display dentro de un estandarizado que YA estaba correcto
# (se me escaparon en la pasada de empates anterior).
DISPLAY_STRAGGLERS = {
    "Escuela Nacional de Estudios Superiores Unidad Merida": "Escuela Nacional de Estudios Superiores, Unidad Mérida",
    "Escuela Nacional de Estudios Superiores Unidad Mérida": "Escuela Nacional de Estudios Superiores, Unidad Mérida",
    "Escuela Nacional de Estudios Superiores, Unidad Merida": "Escuela Nacional de Estudios Superiores, Unidad Mérida",
}


def main():
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()
    est_before = df["plantel_estandarizado"].nunique()

    audit_rows = []

    for old_est, new_est, new_disp in FIXES:
        mask = df["plantel_estandarizado"] == old_est
        count = int(mask.sum())
        if count == 0:
            print(f"AVISO: 0 filas para estandarizado={old_est!r}, se omite")
            continue
        old_disps = df.loc[mask, "plantel_display"].unique().tolist()
        df.loc[mask, "plantel_estandarizado"] = new_est
        df.loc[mask, "plantel_display"] = new_disp
        audit_rows.append({
            "campo": "plantel_estandarizado+display",
            "valor_original": f"{old_est} | displays={old_disps}",
            "valor_nuevo": f"{new_est} | {new_disp}",
            "filas_afectadas": count,
            "regla": "fix_palabra_faltante_2026-09-20",
        })
        print(f"  {count:>5}  est {old_est!r} -> {new_est!r}  (disp -> {new_disp!r})")

    for old_disp, new_disp in DISPLAY_STRAGGLERS.items():
        mask = df["plantel_display"] == old_disp
        count = int(mask.sum())
        if count == 0:
            continue
        df.loc[mask, "plantel_display"] = new_disp
        audit_rows.append({
            "campo": "plantel_display",
            "valor_original": old_disp,
            "valor_nuevo": new_disp,
            "filas_afectadas": count,
            "regla": "straggler_pasada_anterior",
        })
        print(f"  {count:>5}  disp {old_disp!r} -> {new_disp!r}")

    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    est_after = df["plantel_estandarizado"].nunique()
    assert n_after == n_before, f"Cambio en filas: {n_before} -> {n_after}"
    assert ids_after == ids_before, f"Cambio en thesis_id unicos: {ids_before} -> {ids_after}"

    if not BACKUP_PATH.exists():
        shutil.copy2(DATA_PATH, BACKUP_PATH)
        print(f"\nBackup escrito: {BACKUP_PATH.name}")

    df.to_parquet(DATA_PATH, index=False)

    pd.DataFrame(audit_rows).to_csv(AUDIT_PATH, index=False, encoding="utf-8")
    print(f"\nAudit log: {AUDIT_PATH}")
    print(f"plantel_estandarizado unicos: {est_before} -> {est_after}")


if __name__ == "__main__":
    main()
