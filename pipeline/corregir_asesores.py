"""Corrige nombres de asesor: typos de OCR (digito por letra), "?" en vez
de "ñ", un caso de fecha incrustada a mano, y trunca segmentos extra tras
la 2a coma (que en la practica son anos de nacimiento de registros de
autoridad bibliografica pegados al nombre, o basura de titulos/sufijos).
Luego recalcula asesor_display / asesores_display desde el tecnico ya
corregido, para que ambos queden consistentes.

Ver hallazgo en la conversacion 2026-09-20: 100% de coincidencia en la
inversion Apellido,Nombre -> Nombre Apellido para el caso simple (535,079
de 535,079 verificables) -- este script solo corrige los casos raros
encontrados (28 con digitos, 23 con "?", 291 con mas de una coma).
"""
from pathlib import Path
import re
import shutil

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_corregir_asesores_2026-09-20.parquet"
AUDIT_PATH = ROOT / "pipeline" / "audits" / "corregir_asesores_2026-09-20.csv"

SUBSTRING_FIXES = [
    ("?", "ñ"),
    ("Blanco D 2019mendieta", "Blanco De Mendieta"),
    ("Gustav0", "Gustavo"),
    ("B0llestas", "Bollestas"),
    ("Alf0nso", "Alfonso"),
    ("R0sales", "Rosales"),
    ("0lavarrieta", "Olavarrieta"),
    ("0lvera", "Olvera"),
    ("Marqu3z", "Marquez"),
]


def fix_person(s: str) -> str:
    if not s or not s.strip():
        return s
    for old, new in SUBSTRING_FIXES:
        s = s.replace(old, new)
    parts = s.split(",")
    if len(parts) > 2:
        s = ",".join(parts[:2])
    return s.strip()


def fix_list(s: str) -> str:
    if not s or not s.strip():
        return s
    people = [fix_person(p.strip()) for p in s.split("|")]
    return " | ".join(p for p in people if p)


def invert(tecnico: str) -> str:
    if not tecnico or not tecnico.strip() or "," not in tecnico:
        return tecnico
    apellidos, nombres = tecnico.split(",", 1)
    return f"{nombres.strip()} {apellidos.strip()}"


def invert_list(s: str) -> str:
    if not s or not s.strip():
        return s
    return " | ".join(invert(p.strip()) for p in s.split("|"))


def main():
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()

    orig_asesor = df["asesor_limpio_v2"].copy()
    orig_asesores = df["asesores_limpios_v2"].copy()

    df["asesor_limpio_v2"] = df["asesor_limpio_v2"].map(fix_person)
    df["asesores_limpios_v2"] = df["asesores_limpios_v2"].map(fix_list)

    cambiadas_asesor = orig_asesor != df["asesor_limpio_v2"]
    cambiadas_asesores = orig_asesores != df["asesores_limpios_v2"]
    print(f"asesor_limpio_v2 cambiado: {int(cambiadas_asesor.sum())} filas")
    print(f"asesores_limpios_v2 cambiado: {int(cambiadas_asesores.sum())} filas")

    audit_rows = []
    resumen = (
        pd.DataFrame({"antes": orig_asesor[cambiadas_asesor], "despues": df.loc[cambiadas_asesor, "asesor_limpio_v2"]})
        .drop_duplicates()
    )
    for _, r in resumen.iterrows():
        audit_rows.append({"campo": "asesor_limpio_v2", "valor_original": r["antes"], "valor_nuevo": r["despues"]})

    # Recalcular display desde el tecnico ya corregido
    df["asesor_display"] = df["asesor_limpio_v2"].map(invert)
    df["asesores_display"] = df["asesores_limpios_v2"].map(invert_list)

    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    assert n_after == n_before and ids_after == ids_before, "Cambio inesperado en filas/IDs"

    if not BACKUP_PATH.exists():
        shutil.copy2(DATA_PATH, BACKUP_PATH)
        print(f"Backup: {BACKUP_PATH.name}")

    df.to_parquet(DATA_PATH, index=False)
    pd.DataFrame(audit_rows).to_csv(AUDIT_PATH, index=False, encoding="utf-8")
    print(f"\nAudit: {AUDIT_PATH}  ({len(audit_rows)} valores unicos corregidos)")

    # Verificacion final: ya no deberia haber digitos ni "?" ni >1 coma
    quedan_digito = df["asesor_limpio_v2"].str.contains(r"\d", regex=True, na=False).sum()
    quedan_signo = df["asesor_limpio_v2"].str.contains(r"\?", regex=True, na=False).sum()
    quedan_comas = df["asesor_limpio_v2"].str.count(",").gt(1).sum()
    print(f"\nVerificacion: digitos restantes={quedan_digito}, '?' restantes={quedan_signo}, >1 coma restantes={quedan_comas}")


if __name__ == "__main__":
    main()
