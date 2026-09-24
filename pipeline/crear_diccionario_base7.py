from pathlib import Path
import pandas as pd
import duckdb

PARQUET = Path("base7_kaggle_clean.parquet")
OUT = Path("base7_column_dictionary.csv")

if not PARQUET.exists():
    raise FileNotFoundError(f"No encontré {PARQUET}")

con = duckdb.connect()

desc = con.execute(f"""
DESCRIBE SELECT * FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf()

META = {
    "source_record": ("trazabilidad", "Fuente del registro", "Indica si el registro viene de base6 o de marc_recovered.", "base6 / marc_recovered"),
    "thesis_id": ("identificadores", "ID global de tesis", "Identificador único global generado para base7.", "TH_0000001"),
    "thesis_id_old": ("identificadores", "ID anterior de tesis", "ID previo conservado para compatibilidad con prototipos anteriores. Solo existe para registros base6.", "TH_0020003"),
    "ID_Aleph": ("identificadores", "ID Aleph", "Identificador heredado de la extracción original.", "7114"),
    "biblionumber": ("identificadores", "Biblionumber Koha", "Identificador bibliográfico de Koha/TESIUNAM, principalmente en registros MARC.", "222121"),
    "system_number": ("identificadores", "Número de sistema", "Número de control del sistema bibliográfico, principalmente en registros MARC.", "TES01000222119"),

    "Año": ("tiempo", "Año", "Año asociado a la tesis o registro de titulación.", "2024"),
    "título": ("título", "Título original", "Título en forma cercana al registro bibliográfico original.", "La pleurotomia"),
    "titulo_limpio": ("título", "Título limpio", "Versión limpiada del título para lectura y análisis.", "la pleurotomia"),
    "titulo_normalizado": ("título", "Título normalizado", "Versión normalizada para búsqueda, comparación y deduplicación.", "la pleurotomia"),

    "autores_limpios_v2": ("autores", "Autores limpios", "Lista completa de autores en formato Apellido(s), Nombre(s), separada por |.", "Alegría Rodríguez, Carolina | Alquicira Neri, Miguel Ángel"),
    "autor_limpio_v2": ("autores", "Autor principal limpio", "Primer autor en formato técnico bibliográfico.", "Alegría Rodríguez, Carolina"),
    "autores_display": ("autores", "Autores display", "Lista completa de autores en formato Nombre(s) Apellido(s), separada por |.", "Carolina Alegría Rodríguez | Miguel Ángel Alquicira Neri"),
    "autor_display": ("autores", "Autor display", "Autor principal en formato Nombre(s) Apellido(s).", "Carolina Alegría Rodríguez"),
    "autor_ui": ("autores", "Autor compacto UI", "Texto compacto para interfaces. Muestra autor principal y coautores si existen.", "Carolina Alegría Rodríguez · +2 más"),
    "num_autores": ("autores", "Número de autores", "Conteo de autores registrados.", "1"),
    "flag_sin_autor": ("autores", "Sin autor", "True si no se detectó autor.", "False"),
    "flag_multiples_autores": ("autores", "Múltiples autores", "True si hay más de un autor.", "False"),

    "asesores_limpios_v2": ("asesores", "Asesores limpios", "Lista completa de asesores en formato Apellido(s), Nombre(s), separada por |.", "Lira González, Julio César | Herrera Morales, Alma Rosa"),
    "asesor_limpio_v2": ("asesores", "Asesor principal limpio", "Primer asesor en formato técnico bibliográfico.", "Lira González, Julio César"),
    "asesores_display": ("asesores", "Asesores display", "Lista completa de asesores en formato Nombre(s) Apellido(s), separada por |.", "Julio César Lira González | Alma Rosa Herrera Morales"),
    "asesor_display": ("asesores", "Asesor display", "Asesor principal en formato Nombre(s) Apellido(s).", "Julio César Lira González"),
    "asesor_ui": ("asesores", "Asesor compacto UI", "Texto compacto para interfaces. Muestra asesor principal y adicionales si existen.", "Julio César Lira González · +3 más"),
    "num_asesores": ("asesores", "Número de asesores", "Conteo de asesores registrados.", "1"),
    "flag_sin_asesor": ("asesores", "Sin asesor", "True si no se detectó asesor.", "False"),
    "flag_multiples_asesores": ("asesores", "Múltiples asesores", "True si hay más de un asesor.", "False"),

    "grado": ("clasificación académica", "Grado", "Grado o carrera registrada.", "Licenciatura en Psicología"),
    "grado_norm": ("clasificación académica", "Grado normalizado", "Versión normalizada del grado o carrera.", "licenciatura en psicologia"),
    "nivel_estandar": ("clasificación académica", "Nivel estándar", "Nivel académico estandarizado.", "licenciatura"),
    "programa": ("clasificación académica", "Programa", "Programa académico o campo de formación.", "economia"),
    "area": ("clasificación académica", "Área", "Área académica o campo amplio de clasificación.", "Ciencias Sociales"),

    "origen": ("institución", "Origen institucional", "Clasificación del origen institucional del registro.", "UNAM"),
    "universidad_nota": ("institución", "Universidad nota", "Universidad extraída de la nota de tesis o del registro.", "unam"),
    "plantel_estandarizado": ("institución", "Plantel estandarizado", "Plantel normalizado para análisis.", "facultad de economia unam"),
    "plantel_display": ("institución", "Plantel display", "Nombre de plantel en formato legible.", "Facultad de Economía"),

    "texto_completo_url": ("acceso", "URL de texto completo", "URL extraída para acceder al texto completo cuando existe.", "https://tesiunamdocumentos.dgb.unam.mx/..."),
    "restricciones": ("acceso", "Restricciones", "Información sobre disponibilidad o restricciones de acceso.", "Acceso en línea sin restricciones"),
    "tipo de contenido": ("soporte", "Tipo de contenido", "Tipo de contenido bibliográfico.", "texto"),
    "medio": ("soporte", "Medio", "Medio del recurso bibliográfico.", "computadora"),
    "soporte": ("soporte", "Soporte", "Soporte físico o digital del recurso.", "recurso en línea"),
    "descr física": ("soporte", "Descripción física", "Descripción física o extensión del recurso.", "1 recurso en línea (117 páginas)"),
    "materia general": ("materias", "Materia general", "Materias o temas generales asociados al registro, cuando existen.", "Anestesiología | Anestesia"),
}

rows = []

for i, row in desc.iterrows():
    col = row["column_name"]
    category, label, description, example = META.get(col, ("", col, "", ""))

    cov = con.execute(f"""
    SELECT
        count(*) AS total,
        count(NULLIF(trim(cast("{col}" AS VARCHAR)), '')) AS non_empty,
        count(DISTINCT cast("{col}" AS VARCHAR)) AS distinct_count
    FROM read_parquet('{PARQUET.as_posix()}')
    """).fetchdf().iloc[0]

    total = int(cov["total"])
    non_empty = int(cov["non_empty"])
    pct = round(non_empty / total * 100, 4) if total else 0

    rows.append({
        "ordinal": i + 1,
        "column_name": col,
        "type": row["column_type"],
        "category": category,
        "label": label,
        "description": description,
        "methodological_note": "",
        "example": example,
        "non_empty": non_empty,
        "pct_non_empty": pct,
        "distinct_count": int(cov["distinct_count"]),
    })

pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8")

print("LISTO")
print("Archivo:", OUT)
print("Columnas:", len(rows))
