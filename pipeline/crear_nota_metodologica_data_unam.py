"""Genera data/public/nota_metodologica_data_unam.md -- documentacion del
dataset publico/producto (distinto del maestro interno base7_kaggle_clean,
que tiene su propia nota en data/clean/nota_metodologica.md).
"""
from pathlib import Path
import duckdb

ROOT = Path(r"C:\Users\sebas\Desktop\UNAM Tesis")
PARQUET = ROOT / "data" / "public" / "data_unam.parquet"
OUT = ROOT / "data" / "public" / "nota_metodologica_data_unam.md"

if not PARQUET.exists():
    raise FileNotFoundError(f"No encontré {PARQUET}")

con = duckdb.connect()
p = PARQUET.as_posix()

n_rows = int(con.execute(f"SELECT count(*) AS n FROM read_parquet('{p}')").fetchdf()["n"].iloc[0])
n_cols = len(con.execute(f"DESCRIBE SELECT * FROM read_parquet('{p}')").fetchdf())
year_minmax = con.execute(f"SELECT min(anio) AS mn, max(anio) AS mx FROM read_parquet('{p}')").fetchdf().iloc[0]

area_counts = con.execute(f"""
SELECT area, count(*) AS n FROM read_parquet('{p}') GROUP BY 1 ORDER BY 2 DESC
""").fetchdf()

cov = con.execute(f"""
SELECT
    count(NULLIF(trim(asesor), '')) AS con_asesor,
    count(NULLIF(trim(programa), '')) AS con_programa,
    count(NULLIF(trim(materias), '')) AS con_materias,
    count(NULLIF(trim(area), '')) AS con_area
FROM read_parquet('{p}')
""").fetchdf().iloc[0]

COLUMNS_INFO = [
    ("thesis_id", "Identificador único global de la tesis (mismo que en el corpus interno, compatible para referencia cruzada)."),
    ("anio", "Año de la tesis o registro de titulación."),
    ("titulo_legible", "Título legible, con acentos y mayúsculas del registro bibliográfico, sin la mención de responsabilidad: se cortó todo lo que seguía al título (\"/ tesis que para obtener..., presenta ...\"), porque traía el nombre del autor."),
    ("titulo", "**Título normalizado** — sin acentos ni puntuación, en minúsculas. Pensado para búsqueda, comparación y deduplicación, no para lectura directa. Para el título legible, usar `titulo_legible`."),
    ("num_autores", "Número de autores detectados (sin exponer identidad, ver nota de privacidad)."),
    ("asesor", "Asesor principal, en formato legible (Nombre Apellido)."),
    ("asesores", "Lista completa de asesores/comité, separada por `|`, formato legible."),
    ("num_asesores", "Número de asesores detectados."),
    ("grado", "Grado o carrera registrada, forma original."),
    ("grado_busqueda", "Versión normalizada de `grado` (sin acentos, minúsculas) para búsqueda/agrupación."),
    ("nivel", "Nivel académico estandarizado (licenciatura, maestría, doctorado, especialidad)."),
    ("programa", "Programa académico o campo de formación, estandarizado (ver nota de normalización)."),
    ("area", "Área académica amplia: `area 1` (Ciencias Físico-Matemáticas e Ingenierías), `area 2` (Ciencias Biológicas, Químicas y de la Salud), `area 3` (Ciencias Sociales), `area 4` (Humanidades y Artes). Vacío cuando no hay información suficiente para clasificar."),
    ("origen", "Clasificación institucional del registro (UNAM / externa e incorporada / ambiguo)."),
    ("universidad", "Universidad extraída de la nota de tesis o del registro, cuando existe."),
    ("plantel", "Plantel (facultad/escuela) normalizado para análisis — minúsculas, sin acentos, para agrupar de forma confiable."),
    ("restricciones", "Información sobre disponibilidad o restricciones de acceso."),
    ("tipo_contenido", "Tipo de contenido bibliográfico. Baja variabilidad: ~90% del corpus comparte el mismo valor."),
    ("medio", "Medio del recurso bibliográfico. Baja variabilidad, ver nota."),
    ("soporte", "Soporte físico o digital del recurso. Baja variabilidad, ver nota."),
    ("descripcion_fisica", "Descripción física o extensión del recurso."),
    ("materias", "Materias o temas generales asociados, cuando existen. Cobertura parcial (~31%), usar con cautela."),
]

lines = []
lines.append("# Nota metodológica — data_unam.parquet")
lines.append("")
lines.append("## 1. Qué es este archivo")
lines.append("")
lines.append("`data_unam.parquet` es una versión pública y sanitizada del corpus de tesis de la UNAM procesado por NODO UNAM. Es distinto del dataset interno completo (`base7_kaggle_clean.parquet`): aquí se removieron o transformaron columnas por razones de privacidad, cobertura o vigencia (ver sección 3).")
lines.append("")
lines.append(f"- Filas: {n_rows:,}")
lines.append(f"- Columnas: {n_cols}")
lines.append(f"- Años cubiertos: {int(year_minmax['mn'])}–{int(year_minmax['mx'])}")
lines.append("")
lines.append("## 2. Columnas")
lines.append("")
lines.append("| Columna | Descripción |")
lines.append("|---|---|")
for col, desc in COLUMNS_INFO:
    lines.append(f"| `{col}` | {desc} |")
lines.append("")
lines.append("## 3. Diferencias respecto al dataset interno completo")
lines.append("")
lines.append("Columnas **removidas** respecto al corpus interno, y por qué:")
lines.append("")
lines.append("- **Identidad de autor** (nombre de la persona que escribió la tesis): removida por privacidad. Los autores son estudiantes, individuos privados — a diferencia de los asesores, que son personal académico de la UNAM en su rol público. Se conserva `num_autores` (el conteo, sin identidad).")
lines.append("- **`texto_completo_url`**: removida. El proveedor de origen cambió y las URLs scrapeadas ya no son válidas — no es un problema de formato, el sistema al que apuntaban ya no existe así. Pendiente para una futura versión, una vez que se vuelva a extraer con URLs vigentes.")
lines.append("- **`biblionumber`, `system_number`**: removidas por cobertura muy baja (solo disponibles para un subconjunto de registros recuperados vía MARC).")
lines.append("- **`entidad_clean`**: removida del corpus interno desde antes de este export — era un campo de linaje interno del pipeline, 82% redundante con `plantel`, sin uso en producto.")
lines.append("- **`thesis_id_old`, `ID_Aleph`, `source_record`**: removidas, uso interno de trazabilidad del pipeline, sin valor para un uso externo del dataset.")
lines.append("")
lines.append("Columnas **renombradas** para quitar sufijos de proceso interno (`_v2`, `_norm`, `_estandarizado`, `_display`) por nombres simples orientados al propósito del campo (ej. `asesor_display` → `asesor`, `plantel_estandarizado` → `plantel`).")
lines.append("")
lines.append("## 4. Normalización y limpieza aplicada")
lines.append("")
lines.append("- **`plantel`**: se consolidaron duplicados por variaciones de acento, sufijo institucional y errores tipográficos (institución con múltiples formas encontradas y fusionadas en una sola forma canónica).")
lines.append("- **`programa`**: se normalizó a minúsculas sin acentos en todo el campo, y se corrigió una corrupción de codificación puntual (la letra \"ñ\" convertida en espacio en blanco en un subconjunto de registros).")
lines.append("- **`grado_busqueda`**: recalculado de forma determinista a partir de `grado` — una versión anterior de este campo producía resultados distintos para el mismo valor de entrada en algunos casos; fue recalculado con una sola función de normalización aplicada de manera uniforme.")
lines.append("- **`area`**: el corpus original representaba las mismas 4 áreas académicas de dos formas distintas (numerada y con nombre descriptivo) para distintos subconjuntos de registros; se unificaron en una sola forma. Los registros sin información suficiente para clasificar (ausencia de `programa` de origen) quedan con `area` vacío — no se inventó una clasificación donde no hay evidencia para sostenerla.")
lines.append("- **`asesor`/`asesores`**: se verificó que la conversión de formato bibliográfico (Apellido, Nombre) a formato legible (Nombre Apellido) no tuviera errores — no los tenía, coincidencia exacta en el 100% de los casos verificables. Se corrigieron casos puntuales de typos de digitalización (letras confundidas con dígitos, \"ñ\" corrompida) y fragmentos de años de nacimiento de registros de autoridad bibliográfica que habían quedado incrustados en el nombre.")
lines.append("")
lines.append("## 5. Limitaciones conocidas")
lines.append("")
lines.append(f"1. `materias` tiene cobertura parcial (~{cov['con_materias']/n_rows*100:.0f}% de los registros) — no usar como si fuera exhaustivo para análisis temático.")
lines.append(f"2. `tipo_contenido`, `medio` y `soporte` tienen muy baja variabilidad — la gran mayoría del corpus comparte el mismo valor en las tres columnas (tesis en texto, formato digital, recurso en línea). Son informativas solo para el subconjunto no digital (microfilm, volumen físico).")
lines.append(f"3. `area` queda vacía en {n_rows - int(cov['con_area']):,} registros donde no hubo información de origen suficiente para clasificar — no representa un error, representa ausencia real de dato.")
lines.append("4. `texto_completo_url` no está disponible en esta versión (ver sección 3) — no es posible enlazar directamente al PDF original desde este dataset todavía.")
lines.append("5. La normalización de nombres (`asesor`) es conservadora — no pretende resolver todas las variantes históricas de un mismo nombre; puede haber duplicados residuales de la misma persona escrita de forma distinta.")
lines.append("")
lines.append("## 6. Recomendaciones de uso")
lines.append("")
lines.append("- Para búsqueda o comparación de títulos: usar `titulo` (ya normalizado). Para mostrar el título a un lector: usar `titulo_legible`.")
lines.append("- Para agrupar/contar por institución: usar `plantel` (forma consistente). No existe una versión \"legible\" de plantel en este export — para presentación, capitalizar/formatear en el momento de mostrarlo.")
lines.append("- Para análisis de redes de asesoría: usar `asesor`/`asesores`. No hay campo equivalente para autores (ver sección 3).")
lines.append("- Este archivo se deriva de `base7_kaggle_clean.parquet` (dataset interno) mediante `pipeline/generar_data_unam.py` — cualquier corrección futura al corpus interno debe re-ejecutar ese script para propagarse aquí.")
lines.append("")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("LISTO")
print("Archivo:", OUT)
print("Filas:", f"{n_rows:,}", "| Columnas:", n_cols)
