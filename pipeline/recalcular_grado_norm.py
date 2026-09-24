"""Recalcula `grado_norm` desde cero para TODA la columna, usando la misma
funcion `normalize_key` que `normalizar_marc_recovered.py` ya usaba
correctamente para los registros MARC (linea 106-107 de ese script).

Motivo (ver ADR-0009): el lado de base6 tenia un bug de no determinismo
(el mismo valor de 'grado' producia dos 'grado_norm' distintos en 286
casos, por manejo inconsistente de "ñ" y parentesis) y no se encontro
codigo fuente que auditar -- probablemente vivia en un notebook que ya
no existe tal cual. La correccion es recalcular con una sola funcion
conocida-buena aplicada uniformemente, no parchear el bug original.
"""
from pathlib import Path
import re
import shutil
import unicodedata

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_grado_norm_recalculo_2026-09-20.parquet"
AUDIT_PATH = ROOT / "pipeline" / "audits" / "grado_norm_recalculo_2026-09-20.csv"


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize_key(s: str) -> str:
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()

    original = df["grado_norm"].copy()
    df["grado_norm"] = df["grado"].map(lambda x: normalize_key(x) if x and x.strip() else x)

    cambiadas = original != df["grado_norm"]
    print(f"Filas cuyo grado_norm cambio: {int(cambiadas.sum())} de {n_before}")

    # Verificacion de determinismo: cada 'grado' debe mapear a exactamente 1 grado_norm
    check = df.groupby("grado")["grado_norm"].nunique()
    no_deterministico = check[check > 1]
    print(f"Valores de 'grado' con >1 'grado_norm' tras el recalculo: {len(no_deterministico)} (deberia ser 0)")
    assert len(no_deterministico) == 0, "El recalculo sigue sin ser deterministico -- revisar normalize_key"

    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    assert n_after == n_before and ids_after == ids_before, "Cambio inesperado en filas/IDs"

    resumen = (
        pd.DataFrame({"antes": original[cambiadas], "despues": df.loc[cambiadas, "grado_norm"]})
        .groupby(["antes", "despues"]).size().reset_index(name="filas_afectadas")
    )
    resumen.to_csv(AUDIT_PATH, index=False, encoding="utf-8")

    if not BACKUP_PATH.exists():
        shutil.copy2(DATA_PATH, BACKUP_PATH)
        print(f"Backup: {BACKUP_PATH.name}")

    df.to_parquet(DATA_PATH, index=False)
    print(f"\ngrado_norm recalculado. Audit: {AUDIT_PATH}")
    print(f"grado_norm valores unicos: {original.nunique()} -> {df['grado_norm'].nunique()}")


if __name__ == "__main__":
    main()
