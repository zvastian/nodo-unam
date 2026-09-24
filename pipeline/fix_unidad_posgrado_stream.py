import re
import csv
import unicodedata
from pathlib import Path
from collections import Counter, defaultdict

import pyarrow.parquet as pq
import pandas as pd

BASE = Path("base.parquet")
OUT_DIR = Path("outputs/plantel_fix_stream")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PATCH_CSV = OUT_DIR / "patch_unidad_posgrado.csv"
AUDIT_CSV = OUT_DIR / "audit_unidad_posgrado_modificados.csv"
COUNTS_BEFORE_CSV = OUT_DIR / "conteos_antes_por_anio_plantel.csv"
COUNTS_AFTER_CSV = OUT_DIR / "conteos_despues_por_anio_plantel.csv"
SUMMARY_CSV = OUT_DIR / "resumen_unidad_posgrado_fix.csv"

BATCH_SIZE = 25_000

if not BASE.exists():
    raise FileNotFoundError(f"No encontré {BASE.resolve()}")

pf = pq.ParquetFile(BASE)
cols = pf.schema_arrow.names
cols_set = set(cols)

def pick_col(*names):
    for name in names:
        if name in cols_set:
            return name
    return None

year_col = pick_col("Año", "AÃ±o")
if not year_col:
    raise ValueError("No encontré columna Año ni AÃ±o.")

required = ["plantel_estandarizado", "plantel_nota", "entidad_clean", "plantel_final"]
missing = [c for c in required if c not in cols_set]
if missing:
    raise ValueError(f"Faltan columnas requeridas: {missing}")

optional_cols = [
    "ID_Aleph",
    "titulo",
    "programa",
    "grado",
    "nivel_estandar",
    "entidad",
    "entidad_participante",
    "plantel_corregido",
    "clasificacion_final",
    "nota de tesis",
    "sec corporativo",
    "plantel_extraido",
    "universidad",
    "ejemplares",
]

read_cols = [year_col] + required + [c for c in optional_cols if c in cols_set]
read_cols = list(dict.fromkeys(read_cols))

def norm(x):
    if pd.isna(x):
        return ""
    x = str(x).lower().strip()
    x = unicodedata.normalize("NFKD", x)
    x = "".join(ch for ch in x if not unicodedata.combining(ch))
    x = re.sub(r"\s+", " ", x)
    x = re.sub(r"[,;:]+$", "", x)
    return x.strip()

def clean_plantel_unam(x):
    x = norm(x)
    if not x:
        return ""
    if re.search(r"\bunam\b", x):
        return x
    return f"{x} unam"

def is_programa_posgrado(x):
    x = norm(x)
    return bool(re.search(r"^programa de posgrado|^programa de maestria|^programa de doctorado|^programa de maestria y doctorado", x))

def is_bad_value(x):
    x = norm(x)
    return x in {
        "",
        "unidad de posgrado",
        "unidad de posgrado unam",
        "dependencia no especificada",
        "no especificado",
        "programa de posgrado",
        "programa de maestria y doctorado",
    }

entity_pattern = re.compile(
    r"\b("
    r"facultad de estudios superiores [a-z0-9 ]+|"
    r"facultad de [a-z0-9 ]+|"
    r"fes [a-z0-9 ]+|"
    r"enes [a-z0-9 ]+|"
    r"escuela nacional [a-z0-9 ]+|"
    r"escuela superior [a-z0-9 ]+|"
    r"instituto nacional [a-z0-9 ]+|"
    r"instituto de [a-z0-9 ]+|"
    r"centro regional [a-z0-9 ]+|"
    r"centro de [a-z0-9 ]+|"
    r"colegio de ciencias y humanidades"
    r")\b"
)

def extract_entity_from_plantel_final(x):
    x = norm(x)
    m = entity_pattern.search(x)
    if not m:
        return ""
    extracted = m.group(1).strip()

    # Corta frases largas típicas después de la entidad.
    cuts = [
        ". division",
        " division de",
        ". programa",
        " programa de",
        ". posgrado",
        " posgrado",
        ". departamento",
        " departamento de",
    ]

    for cut in cuts:
        idx = extracted.find(cut)
        if idx > 0:
            extracted = extracted[:idx].strip()

    return extracted

def contains_unidad_posgrado_explicit(row):
    fields = [
        "nota de tesis",
        "sec corporativo",
        "entidad_participante",
        "plantel_nota",
        "plantel_final",
        "plantel_extraido",
        "universidad",
        "ejemplares",
    ]
    text = " ".join(norm(row.get(c, "")) for c in fields)
    return bool(re.search(r"\bunidad de posgrado\b", text))

def resolve_row(row):
    pe = norm(row.get("plantel_estandarizado", ""))

    flag_original = pe == "unidad de posgrado unam"

    if not flag_original:
        return {
            "plantel_estandarizado_corregido": row.get("plantel_estandarizado", ""),
            "metodo_correccion_plantel": "sin_cambio",
            "flag_unidad_posgrado_original": False,
            "flag_unidad_posgrado_explicita": False,
            "flag_rescatado_por_plantel_nota": False,
            "flag_rescatado_por_entidad_clean": False,
            "flag_rescatado_por_plantel_final": False,
            "flag_no_especificado_por_posgrado": False,
        }

    pn = norm(row.get("plantel_nota", ""))
    ec = norm(row.get("entidad_clean", ""))
    pfinal = norm(row.get("plantel_final", ""))

    flag_explicita = contains_unidad_posgrado_explicit(row)

    if flag_explicita:
        return {
            "plantel_estandarizado_corregido": "unidad de posgrado unam",
            "metodo_correccion_plantel": "conservado_unidad_posgrado_explicita",
            "flag_unidad_posgrado_original": True,
            "flag_unidad_posgrado_explicita": True,
            "flag_rescatado_por_plantel_nota": False,
            "flag_rescatado_por_entidad_clean": False,
            "flag_rescatado_por_plantel_final": False,
            "flag_no_especificado_por_posgrado": False,
        }

    if not is_bad_value(pn) and not is_programa_posgrado(pn):
        return {
            "plantel_estandarizado_corregido": clean_plantel_unam(pn),
            "metodo_correccion_plantel": "rescatado_por_plantel_nota",
            "flag_unidad_posgrado_original": True,
            "flag_unidad_posgrado_explicita": False,
            "flag_rescatado_por_plantel_nota": True,
            "flag_rescatado_por_entidad_clean": False,
            "flag_rescatado_por_plantel_final": False,
            "flag_no_especificado_por_posgrado": False,
        }

    if not is_bad_value(ec) and not is_programa_posgrado(ec):
        return {
            "plantel_estandarizado_corregido": clean_plantel_unam(ec),
            "metodo_correccion_plantel": "rescatado_por_entidad_clean",
            "flag_unidad_posgrado_original": True,
            "flag_unidad_posgrado_explicita": False,
            "flag_rescatado_por_plantel_nota": False,
            "flag_rescatado_por_entidad_clean": True,
            "flag_rescatado_por_plantel_final": False,
            "flag_no_especificado_por_posgrado": False,
        }

    extracted = extract_entity_from_plantel_final(pfinal)
    if extracted:
        return {
            "plantel_estandarizado_corregido": clean_plantel_unam(extracted),
            "metodo_correccion_plantel": "rescatado_por_plantel_final",
            "flag_unidad_posgrado_original": True,
            "flag_unidad_posgrado_explicita": False,
            "flag_rescatado_por_plantel_nota": False,
            "flag_rescatado_por_entidad_clean": False,
            "flag_rescatado_por_plantel_final": True,
            "flag_no_especificado_por_posgrado": False,
        }

    return {
        "plantel_estandarizado_corregido": "no especificado unam",
        "metodo_correccion_plantel": "no_especificado_por_ambiguedad_posgrado",
        "flag_unidad_posgrado_original": True,
        "flag_unidad_posgrado_explicita": False,
        "flag_rescatado_por_plantel_nota": False,
        "flag_rescatado_por_entidad_clean": False,
        "flag_rescatado_por_plantel_final": False,
        "flag_no_especificado_por_posgrado": True,
    }

patch_fields = [
    "anio",
    "ID_Aleph",
    "plantel_estandarizado",
    "plantel_estandarizado_corregido",
    "metodo_correccion_plantel",
    "flag_unidad_posgrado_original",
    "flag_unidad_posgrado_explicita",
    "flag_rescatado_por_plantel_nota",
    "flag_rescatado_por_entidad_clean",
    "flag_rescatado_por_plantel_final",
    "flag_no_especificado_por_posgrado",
]

audit_fields = [
    "anio",
    "ID_Aleph",
    "titulo",
    "programa",
    "grado",
    "nivel_estandar",
    "entidad",
    "entidad_clean",
    "entidad_participante",
    "plantel_nota",
    "plantel_final",
    "plantel_corregido",
    "clasificacion_final",
    "plantel_estandarizado",
    "plantel_estandarizado_corregido",
    "metodo_correccion_plantel",
    "flag_unidad_posgrado_original",
    "flag_unidad_posgrado_explicita",
    "flag_rescatado_por_plantel_nota",
    "flag_rescatado_por_entidad_clean",
    "flag_rescatado_por_plantel_final",
    "flag_no_especificado_por_posgrado",
    "nota de tesis",
    "sec corporativo",
]

before_counts = Counter()
after_counts = Counter()
summary_counts = Counter()

total_rows = 0
total_unidad = 0
total_modified = 0

with open(PATCH_CSV, "w", newline="", encoding="utf-8") as f_patch, \
     open(AUDIT_CSV, "w", newline="", encoding="utf-8") as f_audit:

    patch_writer = csv.DictWriter(f_patch, fieldnames=patch_fields)
    audit_writer = csv.DictWriter(f_audit, fieldnames=audit_fields)

    patch_writer.writeheader()
    audit_writer.writeheader()

    for batch_i, batch in enumerate(pf.iter_batches(batch_size=BATCH_SIZE, columns=read_cols), start=1):
        df = batch.to_pandas()
        df = df.where(pd.notnull(df), "")

        for _, row in df.iterrows():
            r = row.to_dict()
            anio = r.get(year_col, "")
            old_plantel = r.get("plantel_estandarizado", "")
            old_norm = norm(old_plantel)

            result = resolve_row(r)
            new_plantel = result["plantel_estandarizado_corregido"]

            before_counts[(anio, old_plantel)] += 1
            after_counts[(anio, new_plantel)] += 1

            total_rows += 1

            if old_norm == "unidad de posgrado unam":
                total_unidad += 1
                summary_counts[result["metodo_correccion_plantel"]] += 1

                patch_row = {
                    "anio": anio,
                    "ID_Aleph": r.get("ID_Aleph", ""),
                    "plantel_estandarizado": old_plantel,
                    **result,
                }
                patch_writer.writerow({k: patch_row.get(k, "") for k in patch_fields})

                if new_plantel != old_plantel:
                    total_modified += 1
                    audit_row = {
                        "anio": anio,
                        "ID_Aleph": r.get("ID_Aleph", ""),
                        "titulo": r.get("titulo", ""),
                        "programa": r.get("programa", ""),
                        "grado": r.get("grado", ""),
                        "nivel_estandar": r.get("nivel_estandar", ""),
                        "entidad": r.get("entidad", ""),
                        "entidad_clean": r.get("entidad_clean", ""),
                        "entidad_participante": r.get("entidad_participante", ""),
                        "plantel_nota": r.get("plantel_nota", ""),
                        "plantel_final": r.get("plantel_final", ""),
                        "plantel_corregido": r.get("plantel_corregido", ""),
                        "clasificacion_final": r.get("clasificacion_final", ""),
                        "plantel_estandarizado": old_plantel,
                        **result,
                        "nota de tesis": r.get("nota de tesis", ""),
                        "sec corporativo": r.get("sec corporativo", ""),
                    }
                    audit_writer.writerow({k: audit_row.get(k, "") for k in audit_fields})

        print(
            f"batch={batch_i} rows={total_rows:,} "
            f"unidad={total_unidad:,} modificados={total_modified:,}",
            flush=True
        )

with open(COUNTS_BEFORE_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["anio", "plantel", "n"])
    for (anio, plantel), n in sorted(before_counts.items(), key=lambda x: (str(x[0][0]), -x[1], str(x[0][1]))):
        w.writerow([anio, plantel, n])

with open(COUNTS_AFTER_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["anio", "plantel", "n"])
    for (anio, plantel), n in sorted(after_counts.items(), key=lambda x: (str(x[0][0]), -x[1], str(x[0][1]))):
        w.writerow([anio, plantel, n])

with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["metodo_correccion_plantel", "n"])
    for metodo, n in summary_counts.most_common():
        w.writerow([metodo, n])

print("\nLISTO")
print(f"Filas totales leídas: {total_rows:,}")
print(f"Casos unidad de posgrado originales: {total_unidad:,}")
print(f"Casos modificados: {total_modified:,}")
print(f"Patch: {PATCH_CSV}")
print(f"Auditoría: {AUDIT_CSV}")
print(f"Conteos antes: {COUNTS_BEFORE_CSV}")
print(f"Conteos después: {COUNTS_AFTER_CSV}")
print(f"Resumen: {SUMMARY_CSV}")

print("\nResumen:")
for metodo, n in summary_counts.most_common():
    print(f"{metodo}: {n:,}")
