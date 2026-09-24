from pathlib import Path
import re
import json
import pandas as pd
import duckdb
import pyarrow.parquet as pq

IN = Path("base7_full_recovered.parquet")
OUT_DIR = Path("outputs/base7_column_audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not IN.exists():
    raise FileNotFoundError(f"No encontré {IN}")

con = duckdb.connect()

pf = pq.ParquetFile(IN)
cols = pf.schema.names

total_rows = con.execute(f"""
SELECT count(*) AS n
FROM read_parquet('{IN.as_posix()}')
""").fetchdf()["n"].iloc[0]

print("Archivo:", IN)
print("Filas:", f"{total_rows:,}")
print("Columnas:", len(cols))

# ------------------------------------------------------------
# Clasificación editorial inicial por nombre de columna
# ------------------------------------------------------------

KEEP_CLEAN_EXACT = {
    "thesis_id",
    "source_record",
    "Año",
    "título",
    "titulo_limpio",
    "titulo_normalizado",

    "autores_limpios_v2",
    "autor_limpio_v2",
    "autores_display",
    "autor_display",
    "autor_ui",
    "num_autores",
    "flag_sin_autor",
    "flag_multiples_autores",

    "asesores_limpios_v2",
    "asesor_limpio_v2",
    "asesores_display",
    "asesor_display",
    "asesor_ui",
    "num_asesores",
    "flag_sin_asesor",
    "flag_multiples_asesores",

    "grado",
    "grado_norm",
    "nivel_estandar",
    "programa",
    "area",
    "origen",
    "universidad_nota",
    "entidad_clean",
    "plantel_estandarizado",
    "plantel_display",

    "link_extraido_regex",
    "texto_completo_url",
    "restricciones",
    "tipo de contenido",
    "medio",
    "soporte",
    "descr física",

    "materia general",
    "materia geográfico",
    "materia ent corp",
    "mat autor person",
    "materia tit unif",
    "materia conferencia",
    "palabras clave",
    "resumen",

    "biblionumber",
    "system_number",
    "ID_Aleph",
}

AUDIT_EXACT = {
    "thesis_id_old",
    "target_year",
    "detail_url",
    "marc_url",
    "download_status",
    "downloaded_at_unix",

    "autor_limpio_v2_raw",
    "asesor_limpio_v2_raw",
    "asesores_limpios_v2_raw",
    "asesores_source_used",

    "plantel_marc_original",
    "flag_correccion_manual",
    "flag_auditoria_historica",
}

DROP_EXACT = {
    "element",
    "sin_etiqueta",
}

# Columnas heredadas que suenan a crudo/Aleph intermedio
RAW_OR_LEGACY_PATTERNS = [
    r"^sustentante$",
    r"^sustentante/asesor$",
    r"^sec corporativo$",
    r"^recurso electronico$",
    r"^ejemplares$",
    r"^nota general$",
    r"^nota de tesis$",
    r"^nota de idioma$",
    r"^datos de publicac$",
    r"^formato adicional$",
    r"^tít analítico$",
    r"^variantes del tít$",
    r"^nota con$",
    r"^materia$",
    r"^clasificación$",
    r"^clasificacion_final$",
    r"^autor_limpio$",
    r"^asesor_limpio$",
    r"^asesores_limpios$",
    r"^autor\(es\)$",
    r"^equipo_completo$",
    r"^plantel_",
    r"^nota_norm$",
    r"^es_unam_nota$",
    r"^es_externa_explicit$",
    r"^entidad_participante$",
    r"^entidad$",
    r"^tipo$",
    r"^ID_Limpio$",
]

DISPLAY_PATTERNS = [
    r"_display$",
    r"_ui$",
]

FLAG_PATTERNS = [
    r"^flag_",
]

def group_column(col):
    c = col.lower()

    if col in ["thesis_id", "thesis_id_old", "ID_Aleph", "ID_Limpio", "biblionumber", "system_number"]:
        return "identificadores"

    if col in ["Año", "datos de publicac", "downloaded_at_unix"]:
        return "tiempo_publicacion"

    if "titulo" in c or "tít" in c or col == "título":
        return "titulo"

    if "autor" in c or "sustentante" in c:
        return "autores"

    if "asesor" in c or "tutor" in c:
        return "asesores"

    if "plantel" in c or "universidad" in c or "entidad" in c or "unam" in c:
        return "institucion_plantel"

    if col in ["grado", "grado_norm", "nivel_estandar", "programa", "area", "clasificación", "clasificacion_final", "tipo"]:
        return "clasificacion_academica"

    if "materia" in c or "palabras clave" in c or "resumen" in c:
        return "materias_resumen"

    if "link" in c or "url" in c or "recurso" in c or "electronico" in c or "marc" in c or "detail" in c:
        return "links_origen_digital"

    if "nota" in c:
        return "notas_catalogo"

    if col.startswith("flag_") or c.startswith("es_"):
        return "flags_auditoria"

    return "otros"

def suggest_decision(col, pct_non_empty, distinct_count, examples):
    # keep_clean = dataset público limpio
    # audit_only = conservar solo en full/auditable
    # drop = eliminar de clean y posiblemente de full si no aporta
    # review = revisar manualmente

    if col in KEEP_CLEAN_EXACT:
        return "keep_clean", "columna central limpia o útil para análisis/UX"

    if col in AUDIT_EXACT:
        return "audit_only", "columna útil para trazabilidad, no necesaria en versión Kaggle limpia"

    if col in DROP_EXACT:
        return "drop", "columna residual/intermedia con bajo valor analítico"

    if col.startswith("flag_"):
        if col in ["flag_sin_autor", "flag_multiples_autores", "flag_sin_asesor", "flag_multiples_asesores"]:
            return "keep_clean", "flag simple útil para filtros y control de calidad"
        return "audit_only", "flag más técnico; útil para auditoría, no imprescindible en clean"

    for pat in RAW_OR_LEGACY_PATTERNS:
        if re.search(pat, col, flags=re.I):
            return "audit_only", "columna cruda/heredada útil para trazabilidad pero redundante frente a columnas normalizadas"

    if pct_non_empty == 0:
        return "drop", "columna completamente vacía"

    if pct_non_empty < 0.01:
        return "drop_or_audit", "cobertura casi nula; revisar si tiene valor documental excepcional"

    if pct_non_empty < 1:
        return "audit_only", "cobertura muy baja; mejor conservar solo en versión full/auditable"

    if col.endswith("_raw"):
        return "audit_only", "valor crudo; conservar para auditoría, no para clean"

    if any(re.search(p, col, flags=re.I) for p in DISPLAY_PATTERNS):
        return "keep_clean", "columna de presentación útil para UI"

    return "review", "requiere revisión: no clasificada automáticamente"

def safe_example_sql(col, limit=5):
    return f"""
    SELECT DISTINCT cast("{col}" AS VARCHAR) AS example
    FROM read_parquet('{IN.as_posix()}')
    WHERE NULLIF(trim(cast("{col}" AS VARCHAR)), '') IS NOT NULL
    LIMIT {limit}
    """

profiles = []
examples_rows = []

for i, col in enumerate(cols, start=1):
    print(f"[{i}/{len(cols)}] {col}", flush=True)

    # Tipo
    col_type = con.execute(f"""
    DESCRIBE SELECT "{col}"
    FROM read_parquet('{IN.as_posix()}')
    """).fetchdf()["column_type"].iloc[0]

    # Cobertura básica
    stats = con.execute(f"""
    SELECT
        count(*) AS total,
        count(NULLIF(trim(cast("{col}" AS VARCHAR)), '')) AS non_empty
    FROM read_parquet('{IN.as_posix()}')
    """).fetchdf().iloc[0]

    total = int(stats["total"])
    non_empty = int(stats["non_empty"])
    pct_non_empty = non_empty / total * 100 if total else 0

    # distinct aproximado/real
    try:
        distinct_count = int(con.execute(f"""
        SELECT count(DISTINCT cast("{col}" AS VARCHAR)) AS n
        FROM read_parquet('{IN.as_posix()}')
        """).fetchdf()["n"].iloc[0])
    except Exception:
        distinct_count = None

    # ejemplos
    try:
        exdf = con.execute(safe_example_sql(col, 5)).fetchdf()
        examples = [str(x) for x in exdf["example"].tolist()]
    except Exception as e:
        examples = [f"ERROR_EXAMPLE: {e}"]

    for j, ex in enumerate(examples, start=1):
        examples_rows.append({
            "column": col,
            "example_n": j,
            "example": ex,
        })

    decision, reason = suggest_decision(col, pct_non_empty, distinct_count, examples)

    profiles.append({
        "ordinal": i,
        "column": col,
        "group": group_column(col),
        "type": col_type,
        "total_rows": total,
        "non_empty": non_empty,
        "pct_non_empty": pct_non_empty,
        "empty": total - non_empty,
        "distinct_count": distinct_count,
        "decision_suggestion": decision,
        "reason": reason,
        "examples_joined": " || ".join(examples[:3]),
    })

profile = pd.DataFrame(profiles)
examples_df = pd.DataFrame(examples_rows)

profile.to_csv(OUT_DIR / "01_column_profile.csv", index=False, encoding="utf-8")
examples_df.to_csv(OUT_DIR / "03_column_examples.csv", index=False, encoding="utf-8")

decision = profile[[
    "ordinal",
    "column",
    "group",
    "type",
    "pct_non_empty",
    "distinct_count",
    "decision_suggestion",
    "reason",
    "examples_joined",
]].copy()

decision.to_csv(OUT_DIR / "02_column_decision_suggestion.csv", index=False, encoding="utf-8")

by_group = (
    profile.groupby(["group", "decision_suggestion"])
           .size()
           .reset_index(name="n_columns")
           .sort_values(["group", "decision_suggestion"])
)
by_group.to_csv(OUT_DIR / "04_columns_by_group.csv", index=False, encoding="utf-8")

clean_cols = profile.loc[
    profile["decision_suggestion"].isin(["keep_clean"]),
    "column"
].tolist()

full_cols = profile.loc[
    profile["decision_suggestion"].isin(["keep_clean", "audit_only", "review", "drop_or_audit"]),
    "column"
].tolist()

drop_cols = profile.loc[
    profile["decision_suggestion"].isin(["drop"]),
    "column"
].tolist()

(OUT_DIR / "05_kaggle_clean_candidate_columns.txt").write_text(
    "\n".join(clean_cols),
    encoding="utf-8"
)

(OUT_DIR / "06_full_auditable_candidate_columns.txt").write_text(
    "\n".join(full_cols),
    encoding="utf-8"
)

(OUT_DIR / "07_drop_candidate_columns.txt").write_text(
    "\n".join(drop_cols),
    encoding="utf-8"
)

# ------------------------------------------------------------
# Nota metodológica preliminar
# ------------------------------------------------------------

n_cols = len(profile)
n_keep = (profile["decision_suggestion"] == "keep_clean").sum()
n_audit = (profile["decision_suggestion"] == "audit_only").sum()
n_drop = (profile["decision_suggestion"] == "drop").sum()
n_review = (profile["decision_suggestion"] == "review").sum()
n_drop_or_audit = (profile["decision_suggestion"] == "drop_or_audit").sum()

method_note = f"""# Nota metodológica preliminar — auditoría de columnas base7

## Archivo auditado

- Archivo: `{IN}`
- Filas: {total_rows:,}
- Columnas totales: {n_cols}

## Objetivo

Esta auditoría clasifica las columnas del parquet final en función de su utilidad para una versión pública limpia tipo Kaggle y una versión completa/auditable. La separación propuesta evita perder trazabilidad metodológica, pero reduce ruido para usuarios que solo necesitan analizar la base final de tesis.

## Resultado de clasificación automática

- Columnas sugeridas para versión limpia: {n_keep}
- Columnas sugeridas solo para versión auditable/full: {n_audit}
- Columnas sugeridas para eliminar: {n_drop}
- Columnas por revisar manualmente: {n_review}
- Columnas de cobertura muy baja a decidir entre eliminar o conservar en auditoría: {n_drop_or_audit}

## Criterios usados

1. Se conservaron en la versión limpia las columnas normalizadas y de mayor valor analítico: título, año, autores, asesores, grado, nivel, programa, área, plantel, enlaces y materias.
2. Se conservaron en la versión limpia las columnas de interfaz derivadas: `autor_display`, `autor_ui`, `asesor_display`, `asesor_ui`, `plantel_display`.
3. Se propuso mover a versión auditable las columnas crudas o intermedias: campos `_raw`, campos de extracción MARC, flags técnicos, columnas heredadas del pipeline y columnas de corrección.
4. Se propuso eliminar columnas completamente vacías o residuales sin valor analítico claro.
5. Las columnas de cobertura menor a 1% se marcaron como auditable o revisión, salvo que tuvieran una función metodológica evidente.

## Recomendación preliminar

Publicar dos versiones:

### 1. Versión limpia / Kaggle

Contiene columnas normalizadas, útiles para análisis y visualización. Evita exponer columnas intermedias del pipeline que podrían confundir a usuarios externos.

Archivo sugerido futuro:

`base7_kaggle_clean.parquet`

### 2. Versión completa / auditable

Contiene las columnas limpias más columnas crudas, flags de auditoría, URLs MARC, campos de origen y columnas intermedias necesarias para reproducibilidad.

Archivo sugerido futuro:

`base7_full_auditable.parquet`

## Archivos generados por esta auditoría

- `01_column_profile.csv`: perfil completo por columna.
- `02_column_decision_suggestion.csv`: recomendación preliminar por columna.
- `03_column_examples.csv`: ejemplos de valores por columna.
- `04_columns_by_group.csv`: conteo de columnas por grupo y decisión.
- `05_kaggle_clean_candidate_columns.txt`: columnas candidatas para versión limpia.
- `06_full_auditable_candidate_columns.txt`: columnas candidatas para versión auditable.
- `07_drop_candidate_columns.txt`: columnas candidatas a eliminar.
"""

(OUT_DIR / "08_methodological_notes_draft.md").write_text(method_note, encoding="utf-8")

print("\nLISTO auditoría de columnas")
print("Carpeta:", OUT_DIR)
print("\nResumen decisiones:")
print(profile["decision_suggestion"].value_counts().to_string())

print("\nPor grupo:")
print(by_group.to_string(index=False))

print("\nArchivos:")
for p in sorted(OUT_DIR.glob("*")):
    print("-", p)
