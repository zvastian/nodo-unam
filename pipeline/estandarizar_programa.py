"""Estandarizacion general de `programa`: minuscula sin acentos.

Decision del usuario (2026-09-20): programa se normaliza a un solo campo
canonico en minusculas sin acentos -- no hay columna "display" separada
(la UI lo presentara con una fuente de solo mayusculas, que no depende de
como se guarde el acento/caja en el dato).

Orden de operaciones, cada una necesaria antes de la siguiente:
1. Reparar la corrupcion de "ñ" -> espacio (mismo bug ya visto en
   grado_norm, aqui esta en el dato crudo de `programa`). Debe hacerse
   ANTES de normalizar, si no la "ñ" nunca se recupera.
2. Normalizar TODA la columna a minuscula sin acentos -- esto colapsa
   automaticamente los 274 grupos de duplicados por mayuscula/acento
   encontrados en el analisis (no requiere mapeo manual, es una funcion
   pura aplicada uniformemente).
3. Fusionar los typos genuinos encontrados en el paso de similitud de
   texto (SequenceMatcher) que la normalizacion de paso 2 NO resuelve
   por si sola (son diferencias de letras, no de caja/acento).
4. Descartar explicitamente los pares evaluados que son programas
   academicos reales y distintos (especialidades medicas, idiomas,
   quimica organica/inorganica, etc.) o casos de ambiguedad genuina
   titulo-vs-materia (ingeniero/ingenieria, quimico/quimica) -- no se
   fusionan, se documentan.
"""
from pathlib import Path
import re
import shutil
import unicodedata

import pandas as pd

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
DATA_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.parquet"
BACKUP_PATH = ROOT / "data" / "clean" / "base7_kaggle_clean.before_programa_estandarizacion_2026-09-20.parquet"
AUDIT_PATH = ROOT / "pipeline" / "audits" / "programa_estandarizacion_2026-09-20.csv"
DESCARTADOS_PATH = ROOT / "pipeline" / "audits" / "programa_descartados_2026-09-20.csv"

# --- Paso 1: reparacion de "ñ" perdida (orden importa: mas largo primero) ---
NIÑ_FIXES = [
    ("dise o", "diseño"),
    ("ense anza", "enseñanza"),
    ("espa ola", "española"),
    ("espa olas", "españolas"),
    ("espa ol", "español"),
    ("ni os", "niños"),
    ("ni o", "niño"),
]

# --- Paso 3: typos genuinos confirmados a mano (misma entidad real) ---
TYPO_MERGES = {
    "insectologia": "infectologia",
    "flauta transversal": "flauta transversa",
    "micro finanzas": "microfinanzas",
    "ciencias e ingenieria de la computacion": "ciencia e ingenieria de la computacion",
    "ciencias e ingenieria de materiales": "ciencia e ingenieria de materiales",
    "ciencias de materiales": "ciencia de materiales",
    "ciencia de datos": "ciencias de datos",
    "lengua y literatura hispanicas": "lengua y literaturas hispanicas",
    "lengua y literatura modernas francesas": "lengua y literaturas modernas francesas",
    "estructura": "estructuras",
    "ingenieria (estructura)": "ingenieria (estructuras)",
    "aguas subterraneas": "agua subterranea",
    "ingenieria mecanico electricista": "ingenieria mecanica electricista",
    "radiooncologia": "radio oncologia",
    "medicina nuclear e imagenologia molecular": "medicina nuclear e imaginologia molecular",
    "medicina (medicina nuclear e imagenologia molecular)": "medicina (medicina nuclear e imaginologia molecular)",
    "quimica farmaceutico biologa": "quimica farmaceutico biologica",
}

# --- Paso 4: pares evaluados y descartados (programas reales distintos, o
#     ambiguedad genuina titulo-vs-materia que no se resuelve por texto) ---
DESCARTADOS = [
    ("neurologia pediatrica", "nefrologia pediatrica", "especialidades medicas distintas"),
    ("neurologia pediatrica", "neumologia pediatrica", "especialidades medicas distintas"),
    ("neumologia pediatrica", "nefrologia pediatrica", "especialidades medicas distintas"),
    ("hematologia pediatrica", "dermatologia pediatrica", "especialidades medicas distintas"),
    ("hematologia pediatrica", "reumatologia pediatrica", "especialidades medicas distintas"),
    ("hematologia pediatrica", "patologia pediatrica", "especialidades medicas distintas"),
    ("hematologia pediatrica", "estomatologia pediatrica", "especialidades medicas distintas"),
    ("dermatologia pediatrica", "reumatologia pediatrica", "especialidades medicas distintas"),
    ("oncologia pediatrica", "odontologia pediatrica", "especialidades medicas distintas"),
    ("neurologia", "nefrologia", "especialidades medicas distintas"),
    ("neurologia", "neumologia", "especialidades medicas distintas"),
    ("nefrologia", "neumologia", "especialidades medicas distintas"),
    ("medicina (dermatologia)", "medicina (hematologia)", "especialidades distintas"),
    ("medicina (reumatologia)", "medicina (hematologia)", "especialidades distintas"),
    ("medicina (dermatologia)", "medicina (reumatologia)", "especialidades distintas"),
    ("medicina (urologia)", "medicina (neurologia)", "especialidades distintas"),
    ("medicina (urologia)", "medicina (nefrologia)", "especialidades distintas"),
    ("medicina (neumologia)", "medicina (nefrologia)", "especialidades distintas"),
    ("quimica organica", "quimica inorganica", "ramas distintas de quimica"),
    ("produccion animal", "reproduccion animal", "programas distintos"),
    ("ingenieria (electrica)", "ingenieria (electronica)", "especialidades de ingenieria distintas"),
    ("electrica", "electronica", "programas distintos"),
    ("enseñanza de aleman como lengua extranjera", "enseñanza de italiano como lengua extranjera", "idiomas distintos"),
    ("enseñanza de ingles como lengua extranjera", "enseñanza de frances como lengua extranjera", "idiomas distintos"),
    ("enseñanza de ingles como lengua extranjera", "enseñanza de aleman como lengua extranjera", "idiomas distintos"),
    ("lengua y literaturas modernas inglesas", "lengua y literaturas modernas francesas", "idiomas distintos"),
    ("lengua y literaturas modernas alemanas", "lengua y literaturas modernas italianas", "idiomas distintos"),
    ("ciencias de la comunicacion", "ciencias de la computacion", "programas distintos, coincidencia de texto"),
    ("ciencias biologicas", "ciencias fisiologicas", "programas distintos"),
    ("ciencias biomedicas", "ciencias sociomedicas", "programas distintos"),
    ("ciencias biomedicas", "ciencias medicas", "programas distintos"),
    ("ciencias economicas", "ciencias genomicas", "programas distintos, coincidencia de texto"),
    ("ingenieria mecanica", "ingenieria mecatronica", "programas distintos"),
    ("ingenieria en sistemas biomedicos", "ingeniero en sistemas biomedicos", "ambiguedad titulo-vs-materia, no se resuelve por texto"),
    ("ingenieria en telecomunicaciones sistemas y electronica", "ingeniero en telecomunicaciones sistemas y electronica", "ambiguedad titulo-vs-materia"),
    ("fisico biomedico", "fisica biomedica", "ambiguedad titulo-vs-materia"),
    ("ingenieria civil", "ingeniero civil", "ambiguedad titulo-vs-materia"),
    ("quimico industrial", "quimica industrial", "ambiguedad titulo-vs-materia"),
    ("quimico farmaceutico biologo", "quimica farmaceutico biologica", "ambiguedad titulo-vs-materia/genero"),
    ("estomatologia pediatrica", "odontologia pediatrica", "posible distincion real, no se asume duplicado"),
    ("econometria aplicada", "economia aplicada", "programas distintos"),
    ("odontologia (parodoncia)", "odontologia (ortodoncia)", "especialidades odontologicas distintas"),
    # Pares de doble titulacion con orden invertido -- se preservan tal cual,
    # invertir el orden podria cambiar cual programa es el "principal".
    ("administracion licenciatura en contaduria", "contaduria licenciatura en administracion", "doble titulacion, orden puede ser semanticamente relevante"),
]

STRIP_TABLE = None


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def normalizar(valor: str) -> str:
    if not valor or not valor.strip():
        return valor
    s = valor
    for buscado, reemplazo in NIÑ_FIXES:
        s = s.replace(buscado, reemplazo)
    s = strip_accents(s).lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    df = pd.read_parquet(DATA_PATH)
    n_before = len(df)
    ids_before = df["thesis_id"].nunique()
    programas_before = df["programa"].nunique()

    print("Aplicando reparacion de \u00f1 + normalizacion minuscula/sin acento a toda la columna...")
    original = df["programa"].copy()
    df["programa"] = df["programa"].map(normalizar)

    cambiadas = (df["programa"] != original) & (original.str.strip() != "")
    print(f"Filas cuyo valor de 'programa' cambio por la normalizacion: {int(cambiadas.sum())}")

    audit_rows = []
    resumen = (
        pd.DataFrame({"antes": original[cambiadas], "despues": df.loc[cambiadas, "programa"]})
        .groupby(["antes", "despues"]).size().reset_index(name="filas_afectadas")
    )
    for _, row in resumen.iterrows():
        audit_rows.append({
            "campo": "programa", "valor_original": row["antes"], "valor_nuevo": row["despues"],
            "filas_afectadas": int(row["filas_afectadas"]), "regla": "normalizacion_minuscula_sin_acento_2026-09-20",
        })

    print(f"\nAplicando {len(TYPO_MERGES)} fusiones de typos confirmados manualmente...")
    for old, new in TYPO_MERGES.items():
        mask = df["programa"] == old
        count = int(mask.sum())
        if count == 0:
            print(f"  AVISO: 0 filas para {old!r}, se omite")
            continue
        df.loc[mask, "programa"] = new
        audit_rows.append({
            "campo": "programa", "valor_original": old, "valor_nuevo": new,
            "filas_afectadas": count, "regla": "typo_confirmado_manual_2026-09-20",
        })
        print(f"  {count:>5}  {old!r} -> {new!r}")

    n_after = len(df)
    ids_after = df["thesis_id"].nunique()
    programas_after = df["programa"].nunique()
    assert n_after == n_before, f"Cambio en filas: {n_before} -> {n_after}"
    assert ids_after == ids_before, f"Cambio en thesis_id unicos: {ids_before} -> {ids_after}"

    if not BACKUP_PATH.exists():
        shutil.copy2(DATA_PATH, BACKUP_PATH)
        print(f"\nBackup escrito: {BACKUP_PATH.name}")

    df.to_parquet(DATA_PATH, index=False)

    pd.DataFrame(audit_rows).to_csv(AUDIT_PATH, index=False, encoding="utf-8")
    pd.DataFrame(DESCARTADOS, columns=["valor_a", "valor_b", "motivo_no_fusion"]).to_csv(
        DESCARTADOS_PATH, index=False, encoding="utf-8"
    )

    print(f"\nAudit log: {AUDIT_PATH}")
    print(f"Descartados documentados: {DESCARTADOS_PATH}  ({len(DESCARTADOS)} pares)")
    print(f"\nprograma valores unicos: {programas_before} -> {programas_after}")


if __name__ == "__main__":
    main()
