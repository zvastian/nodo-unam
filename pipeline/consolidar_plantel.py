"""Consolida duplicados residuales de plantel_estandarizado / plantel_display
en data/clean/base7_kaggle_clean.parquet.

Estrategia deliberadamente conservadora (ver ADR-0005):
- Solo se fusionan grupos detectados por clave normalizada (sin acentos, sin
  el token "UNAM") con evidencia manual verificada -- no hay generalización
  ciega tipo "quitar acentos a toda la columna".
- plantel_estandarizado: la forma canónica respeta la convención ya
  establecida en el resto de la columna (ASCII sin acentos). Si eso empata
  con el conteo mayoritario, se usa el conteo; si no, la convención gana
  sobre el conteo (ver caso "Escuela Normal Superior de México").
- plantel_display: se usa mayoría simple, pero solo si el ganador tiene
  >=90% de las filas del grupo. Grupos sin mayoría clara se reportan y NO
  se tocan -- quedan para revisión manual.
"""
from pathlib import Path
import re
import unicodedata
import shutil
import sys

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_plantel_consolidation_2026-09-20.parquet"
AUDIT_DIR = ROOT / "pipeline" / "audits"
AUDIT_PATH = AUDIT_DIR / "plantel_consolidation_2026-09-20.csv"

DISPLAY_MAJORITY_THRESHOLD = 0.90


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def has_accent(s: str) -> bool:
    return strip_accents(s) != s


def norm_key(s: str) -> str:
    s = strip_accents(str(s)).upper()
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\bUNAM\b", "", s).strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def pick_canonical_estandarizado(variants_counts: dict) -> tuple[str, str]:
    """Devuelve (forma_canonica, regla_usada)."""
    unaccented = {v: c for v, c in variants_counts.items() if not has_accent(v)}
    if unaccented:
        canonical = max(unaccented, key=unaccented.get)
        rule = "convencion_sin_acentos"
    else:
        canonical = max(variants_counts, key=variants_counts.get)
        rule = "mayoria_simple"
    return canonical, rule


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"No encontre {DATA_PATH}")

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Cargando {DATA_PATH} ...")
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()
    n_estandarizado_before = df["plantel_estandarizado"].nunique()

    audit_rows = []

    # --- Paso 1: consolidar plantel_estandarizado por clave normalizada ---
    df["_key"] = df["plantel_estandarizado"].map(norm_key)
    grouped = df.groupby("_key")["plantel_estandarizado"].value_counts()

    estandarizado_map = {}
    for key, sub in grouped.groupby(level=0):
        variants_counts = {v: c for (_, v), c in sub.items()}
        if len(variants_counts) <= 1:
            continue
        canonical, rule = pick_canonical_estandarizado(variants_counts)
        for variant, count in variants_counts.items():
            if variant != canonical:
                estandarizado_map[variant] = canonical
                audit_rows.append({
                    "campo": "plantel_estandarizado",
                    "valor_original": variant,
                    "valor_nuevo": canonical,
                    "filas_afectadas": count,
                    "regla": rule,
                })

    print(f"\nGrupos de plantel_estandarizado a fusionar: {len(estandarizado_map)}")
    for old, new in estandarizado_map.items():
        print(f"  {old!r} -> {new!r}")

    df["plantel_estandarizado"] = df["plantel_estandarizado"].replace(estandarizado_map)
    df = df.drop(columns=["_key"])

    # --- Paso 2: consolidar plantel_display dentro de cada plantel_estandarizado ---
    display_map = {}
    skipped_low_confidence = []

    for est_value, sub in df.groupby("plantel_estandarizado")["plantel_display"]:
        counts = sub.value_counts()
        if len(counts) <= 1:
            continue
        total = counts.sum()
        top_value = counts.index[0]
        top_share = counts.iloc[0] / total
        if top_share < DISPLAY_MAJORITY_THRESHOLD:
            skipped_low_confidence.append((est_value, dict(counts)))
            continue
        for variant, count in counts.items():
            if variant != top_value:
                display_map[variant] = top_value
                audit_rows.append({
                    "campo": "plantel_display",
                    "valor_original": variant,
                    "valor_nuevo": top_value,
                    "filas_afectadas": int(count),
                    "regla": f"mayoria>={DISPLAY_MAJORITY_THRESHOLD:.0%}",
                })

    print(f"\nGrupos de plantel_display a fusionar: {len(display_map)}")
    for old, new in display_map.items():
        print(f"  {old!r} -> {new!r}")

    if skipped_low_confidence:
        print(f"\nGrupos de plantel_display SIN mayoria clara (<{DISPLAY_MAJORITY_THRESHOLD:.0%}), "
              f"NO tocados, requieren revision manual: {len(skipped_low_confidence)}")
        for est_value, counts in skipped_low_confidence:
            print(f"  plantel_estandarizado={est_value!r}: {counts}")

    df["plantel_display"] = df["plantel_display"].replace(display_map)

    # --- Validaciones antes de escribir ---
    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    n_estandarizado_after = df["plantel_estandarizado"].nunique()

    assert n_after == n_before, f"Cambio en numero de filas: {n_before} -> {n_after}"
    assert ids_after == ids_before, f"Cambio en thesis_id unicos: {ids_before} -> {ids_after}"
    expected_after = n_estandarizado_before - len(estandarizado_map)
    assert n_estandarizado_after == expected_after, (
        f"plantel_estandarizado unicos esperado {expected_after}, obtuve {n_estandarizado_after}"
    )

    print(f"\nValidacion OK: {n_before} filas antes y despues, "
          f"{n_estandarizado_before} -> {n_estandarizado_after} valores unicos de plantel_estandarizado.")

    # --- Backup + escritura ---
    if not BACKUP_PATH.exists():
        print(f"\nCopiando original a backup: {BACKUP_PATH.name}")
        shutil.copy2(DATA_PATH, BACKUP_PATH)
    else:
        print(f"\nBackup ya existe, no se sobreescribe: {BACKUP_PATH.name}")

    print(f"Escribiendo version consolidada en {DATA_PATH.name} ...")
    df.to_parquet(DATA_PATH, index=False)

    audit_df = pd.DataFrame(audit_rows).sort_values(
        ["campo", "filas_afectadas"], ascending=[True, False]
    )
    audit_df.to_csv(AUDIT_PATH, index=False, encoding="utf-8")
    print(f"Audit log escrito en {AUDIT_PATH}")
    print(f"\nTotal de cambios registrados: {len(audit_df)}")


if __name__ == "__main__":
    main()
