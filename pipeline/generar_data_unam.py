"""Genera data/public/data_unam.parquet: version sanitizada y renombrada de
base7_kaggle_clean.parquet para uso publico/producto (Kaggle y, mas adelante,
como fuente para regenerar los artefactos que consume la app).

Decisiones de esta sesion (2026-09-20, ver ADR-0011):
- Fuera por privacidad: toda columna de identidad de AUTOR (estudiante).
- Se quedan las columnas de identidad de ASESOR (docente UNAM, informacion
  valiosa para Taller/redes de asesoria) -- version "display" (legible),
  ya verificada sin bugs y con "Blanco De Mendieta" homogeneizado.
- Fuera: texto_completo_url (URLs invalidas, proveedor cambio),
  thesis_id_old / ID_Aleph / source_record (no se usaran), flag_sin_asesor
  y flag_multiples_asesores (decision del usuario).
- Renombrado general: se quitan sufijos internos de proceso (_v2, _norm,
  _estandarizado, _display) por nombres simples orientados a proposito.
"""
from pathlib import Path

import pandas as pd

from titulo_sin_autor import titulo_legible

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
SOURCE_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
OUT_DIR = ROOT / "data" / "public"
OUT_PATH = OUT_DIR / "data_unam.parquet"

# (columna_origen, columna_nueva)
COLUMN_MAP = [
    ("thesis_id", "thesis_id"),
    ("Año", "anio"),
    ("título", "titulo_original"),
    ("titulo_normalizado", "titulo"),
    ("num_autores", "num_autores"),
    ("asesor_display", "asesor"),
    ("asesores_display", "asesores"),
    ("num_asesores", "num_asesores"),
    ("grado", "grado"),
    ("grado_norm", "grado_busqueda"),
    ("nivel_estandar", "nivel"),
    ("programa", "programa"),
    ("area", "area"),
    ("origen", "origen"),
    ("universidad_nota", "universidad"),
    ("plantel_estandarizado", "plantel"),
    ("restricciones", "restricciones"),
    ("tipo de contenido", "tipo_contenido"),
    ("medio", "medio"),
    ("soporte", "soporte"),
    ("descr física", "descripcion_fisica"),
    ("materia general", "materias"),
]


def main():
    df = pd.read_parquet(SOURCE_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()

    faltantes = [c for c, _ in COLUMN_MAP if c not in df.columns]
    if faltantes:
        raise KeyError(f"Columnas esperadas no encontradas en la fuente: {faltantes}")

    origen_cols = [c for c, _ in COLUMN_MAP]
    nuevo_nombres = {c: n for c, n in COLUMN_MAP}

    out = df[origen_cols].rename(columns=nuevo_nombres)

    # El título del catálogo trae pegado al autor ("... / tesis que ..., presenta
    # NOMBRE"): se publica solo el título, sin la mención de responsabilidad.
    out["titulo_original"] = out["titulo_original"].fillna("").map(titulo_legible)
    out = out.rename(columns={"titulo_original": "titulo_legible"})

    assert len(out) == n_before
    assert out["thesis_id"].nunique() == ids_before
    assert len(out.columns) == len(COLUMN_MAP)

    # Verificacion explicita: ninguna columna de identidad de autor presente
    prohibidas = ["autor", "autores"]
    for col in out.columns:
        assert col not in prohibidas, f"Columna de identidad de autor presente: {col}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)

    print(f"Generado: {OUT_PATH}")
    print(f"Filas: {len(out):,}  |  Columnas: {len(out.columns)}")
    print("\nColumnas finales:")
    for c in out.columns:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
