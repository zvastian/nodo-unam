"""Resuelve manualmente los grupos de plantel_display que consolidar_plantel.py
dejo pendientes por no tener mayoria >=90%, mas la decision explicita del
usuario de expandir acronimos (ENAC, ENALLT, ENES+sede, ENCiT) a nombre
completo, y adoptar el formato "Universidad X, Campus Y" (coma) en vez de
parentesis para Universidad Latina -- ese formato coma+Campus ya es la
convencion dominante en el resto del archivo (ej. "Universidad de Sotavento,
Campus Orizaba"), confirmado por inspeccion antes de aplicar.

NO se tocan CCH ni ENTS (acronimos masivos, sin ambiguedad, no reportados
como duplicados) -- fuera de alcance de esta decision, pendiente de
confirmacion explicita del usuario.
"""
from pathlib import Path
import shutil

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_plantel_display_empates_2026-09-20.parquet"
AUDIT_PATH = ROOT / "pipeline" / "audits" / "plantel_display_empates_2026-09-20.csv"

# --- Decision: expandir acronimos a nombre completo ---
EXPANDIR_ACRONIMOS = {
    "ENAC": "Escuela Nacional de Artes Cinematográficas",
    "ENALLT": "Escuela Nacional de Lenguas, Lingüística y Traducción",
    "ENES León": "Escuela Nacional de Estudios Superiores, Unidad León",
    "ENES Morelia": "Escuela Nacional de Estudios Superiores, Unidad Morelia",
    "ENES Juriquilla": "Escuela Nacional de Estudios Superiores, Unidad Juriquilla",
    "ENCiT": "Escuela Nacional de Ciencias de la Tierra",
    "ENES Mérida": "Escuela Nacional de Estudios Superiores, Unidad Mérida",
}

# --- Decision: formato coma+Campus (no parentesis) para Universidad Latina ---
CAMPUS_FORMATO = {
    "Universidad Latina (Campus Cuautla)": "Universidad Latina, Campus Cuautla",
    "Universidad Latina (Campus Sur)": "Universidad Latina, Campus Sur",
}

# --- Empates restantes: se resuelve por ortografia correcta / convencion
#     "X, Y" ya usada en el resto del archivo. Explicito y auditable. ---
EMPATES_RESTANTES = {
    "Escuela de Trabajo social": "Escuela de Trabajo Social",
    "Escuela Nacional de Estudios Superiores Merida": "Escuela Nacional de Estudios Superiores Mérida",
    "Programa de Maestría y Doctorado en Trabajo social": "Programa de Maestría y Doctorado en Trabajo Social",
    "Programa único de especializaciones Odontológicas": "Programa Único de Especializaciones Odontológicas",
    "Universidad Autonoma de Guadalajara, Escuela de Ciencias Químicas": "Universidad Autónoma de Guadalajara, Escuela de Ciencias Químicas",
    "Universidad Autonoma de Guadalajara, Escuela de Pedagogía": "Universidad Autónoma de Guadalajara, Escuela de Pedagogía",
    "Universidad Autonóma de Guadalajara, Escuela de Pedagogía": "Universidad Autónoma de Guadalajara, Escuela de Pedagogía",
    "Universidad del Valle de Mexico, Escuela de Derecho": "Universidad del Valle de México, Escuela de Derecho",
    "Universidad Insurgentes Plantel León": "Universidad Insurgentes, Plantel León",
}

FULL_MAP = {**EXPANDIR_ACRONIMOS, **CAMPUS_FORMATO, **EMPATES_RESTANTES}


def main():
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()

    audit_rows = []
    for old, new in FULL_MAP.items():
        mask = df["plantel_display"] == old
        count = int(mask.sum())
        if count == 0:
            print(f"AVISO: no encontre filas con plantel_display == {old!r} (0 filas, se omite)")
            continue
        audit_rows.append({
            "campo": "plantel_display",
            "valor_original": old,
            "valor_nuevo": new,
            "filas_afectadas": count,
            "regla": "decision_manual_2026-09-20",
        })
        print(f"  {count:>5}  {old!r} -> {new!r}")

    df["plantel_display"] = df["plantel_display"].replace(FULL_MAP)

    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    assert n_after == n_before, f"Cambio en filas: {n_before} -> {n_after}"
    assert ids_after == ids_before, f"Cambio en thesis_id unicos: {ids_before} -> {ids_after}"

    if not BACKUP_PATH.exists():
        shutil.copy2(DATA_PATH, BACKUP_PATH)
        print(f"\nBackup escrito: {BACKUP_PATH.name}")

    df.to_parquet(DATA_PATH, index=False)

    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(AUDIT_PATH, index=False, encoding="utf-8")
    print(f"\nAudit log: {AUDIT_PATH}")
    print(f"Total cambios: {len(audit_df)}  |  filas afectadas: {audit_df['filas_afectadas'].sum()}")


if __name__ == "__main__":
    main()
