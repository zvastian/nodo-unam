"""Resuelve los 14 grupos de plantel_display que quedaron sin mayoria clara
(>=90%) despues de fusionar plantel_estandarizado en consolidar_plantel_final.py.
Criterio: correccion ortografica/gramatical y consistencia con decisiones ya
tomadas en pasadas anteriores (ej. preferir "Posgrado" sobre "Postgrado" en
todo el archivo, dado que ya es la forma dominante en otros grupos)."""
from pathlib import Path
import shutil

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_plantel_display_final_2026-09-20.parquet"
AUDIT_PATH = ROOT / "pipeline" / "audits" / "plantel_display_final_2026-09-20.csv"

FIXES = {
    "Universidad Autónoma de Guadalajara, Escuela de Odontología": "Universidad Autónoma de Guadalajara, Facultad de Odontología",
    "Instituto Nacional de Psiquiatría Ramón de la Fuente": "Instituto Nacional de Psiquiatría Ramón de la Fuente Muñiz",
    "Escuela Administración, Contabilidad y Economía": "Escuela de Administración, Contabilidad y Economía",
    "Centro de Estudios Superiores de Martinez de la Torre": "Centro de Estudios Superiores de Martínez de la Torre",
    "Centro de Estudios Superiores Martinez de la Torre": "Centro de Estudios Superiores de Martínez de la Torre",
    "Centro Panamericano de Estudios Superiores": "Universidad Centro Panamericano de Estudios Superiores",
    "Escuela de Administración y Contaduría": "Escuela de Contaduría y Administración",
    "Universidad Lasalle, Escuela de Ingeniería": "Universidad La Salle, Escuela de Ingeniería",
    "Programa de Posgrados en Ciencias del Mar y Limnología": "Programa de Posgrado en Ciencias del Mar y Limnología",
    "Facultad de Química, División de Estudios de Postgrado": "Facultad de Química, División de Estudios de Posgrado",
    "Universidad Autónoma de Guadalajara Guadalajara": "Universidad Autónoma de Guadalajara (Guadalajara, Jal.)",
    "Universidad Autonoma de Guadalajara (Guadalajara, Jal.).": "Universidad Autónoma de Guadalajara (Guadalajara, Jal.)",
    "Programa de Maestría yDoctorado en Estudios Mesoamericanos": "Programa de Maestría y Doctorado en Estudios Mesoamericanos",
    "Facultad de Filosofía y Letras, División de Estudios de Postgrado": "Facultad de Filosofía y Letras, División de Estudios de Posgrado",
    "Programa Único de Especializaciones en Ingeniería": "Programa Único de Especializaciones de Ingeniería",
    "Universidad del Valle de México, Facultad de Derecho": "Universidad del Valle de México, Escuela de Derecho",
}


def main():
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()

    audit_rows = []
    for old, new in FIXES.items():
        mask = df["plantel_display"] == old
        count = int(mask.sum())
        if count == 0:
            print(f"AVISO: 0 filas para display={old!r}, se omite")
            continue
        df.loc[mask, "plantel_display"] = new
        audit_rows.append({
            "campo": "plantel_display", "valor_original": old, "valor_nuevo": new,
            "filas_afectadas": count, "regla": "cierre_manual_2026-09-20",
        })
        print(f"  {count:>5}  {old!r} -> {new!r}")

    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    assert n_after == n_before and ids_after == ids_before, "Cambio inesperado en filas/IDs"

    if not BACKUP_PATH.exists():
        shutil.copy2(DATA_PATH, BACKUP_PATH)

    df.to_parquet(DATA_PATH, index=False)
    pd.DataFrame(audit_rows).to_csv(AUDIT_PATH, index=False, encoding="utf-8")

    # Verificacion final: cuantos grupos de display siguen sin mayoria unica
    check = df.groupby("plantel_estandarizado")["plantel_display"].nunique()
    restantes = check[check > 1]
    print(f"\nGrupos de plantel_display con >1 valor tras el cierre: {len(restantes)}")
    if len(restantes):
        for est in restantes.index:
            print(f"  {est!r}: {dict(df.loc[df['plantel_estandarizado']==est, 'plantel_display'].value_counts())}")

    print(f"\nplantel_estandarizado unicos: {df['plantel_estandarizado'].nunique()}")
    print(f"plantel_display unicos: {df['plantel_display'].nunique()}")


if __name__ == "__main__":
    main()
