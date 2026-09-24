from pathlib import Path
import pandas as pd
import duckdb

PARQUET = Path("base7_kaggle_clean.parquet")

COLUMN_DICTIONARY = Path("base7_column_dictionary.csv")
README = Path("README.md")
METHODOLOGY = Path("nota_metodologica.md")

if not PARQUET.exists():
    raise FileNotFoundError(f"No encontré {PARQUET}")

con = duckdb.connect()

desc = con.execute(f"""
DESCRIBE SELECT * FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf()

n_rows = int(con.execute(f"""
SELECT count(*) AS n
FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf()["n"].iloc[0])

source_counts = con.execute(f"""
SELECT source_record, count(*) AS n
FROM read_parquet('{PARQUET.as_posix()}')
GROUP BY 1
ORDER BY 1
""").fetchdf()

year_minmax = con.execute(f"""
SELECT min("Año") AS anio_min, max("Año") AS anio_max
FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf().iloc[0]

id_check = con.execute(f"""
SELECT
    count(*) AS n,
    count(DISTINCT thesis_id) AS distinct_thesis_id,
    min(thesis_id) AS min_thesis_id,
    max(thesis_id) AS max_thesis_id,
    count(NULLIF(trim(thesis_id_old), '')) AS thesis_id_old_no_vacio
FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf().iloc[0]

recovered_years = [1905, 1913, 1960, 1980, 1985, 1987, 1989, 1995, 2026]

recovered_counts = con.execute(f"""
SELECT "Año" AS anio, source_record, count(*) AS n
FROM read_parquet('{PARQUET.as_posix()}')
WHERE "Año" IN ({",".join(map(str, recovered_years))})
GROUP BY 1, 2
ORDER BY 1, 2
""").fetchdf()

# ------------------------------------------------------------
# Descripciones de columnas
# ------------------------------------------------------------

column_meta = {
    "source_record": {
        "category": "trazabilidad",
        "label": "Fuente del registro",
        "description": "Indica si el registro proviene de la base principal original normalizada o de la recuperación MARC.",
        "methodological_note": "Valores esperados: base6 o marc_recovered.",
        "example": "base6",
    },
    "thesis_id": {
        "category": "identificadores",
        "label": "ID global de tesis",
        "description": "Identificador único global generado después del merge final.",
        "methodological_note": "Renumerado de forma consecutiva para el dataset base7.",
        "example": "TH_0000001",
    },
    "thesis_id_old": {
        "category": "identificadores",
        "label": "ID anterior de tesis",
        "description": "Identificador previo conservado para compatibilidad con prototipos o versiones anteriores.",
        "methodological_note": "Solo existe para registros provenientes de base6. Los registros recuperados vía MARC no tienen thesis_id_old.",
        "example": "TH_0020003",
    },
    "ID_Aleph": {
        "category": "identificadores",
        "label": "ID Aleph",
        "description": "Identificador proveniente de la extracción original del catálogo Aleph/TESIUNAM.",
        "methodological_note": "Principalmente disponible en registros base6.",
        "example": "7114",
    },
    "biblionumber": {
        "category": "identificadores",
        "label": "Biblionumber Koha",
        "description": "Identificador bibliográfico utilizado por el sistema Koha/TESIUNAM.",
        "methodological_note": "Principalmente disponible en registros recuperados vía MARC.",
        "example": "222121",
    },
    "system_number": {
        "category": "identificadores",
        "label": "Número de sistema",
        "description": "Número de control del sistema bibliográfico, cuando está disponible.",
        "methodological_note": "Principalmente disponible en registros recuperados vía MARC.",
        "example": "TES01000222119",
    },
    "Año": {
        "category": "tiempo",
        "label": "Año",
        "description": "Año asociado a la tesis o al registro de titulación.",
        "methodological_note": "Campo central para análisis temporal.",
        "example": "2024",
    },
    "título": {
        "category": "titulo",
        "label": "Título original",
        "description": "Título de la tesis en su forma más cercana al registro bibliográfico original.",
        "methodological_note": "Puede incluir menciones de responsabilidad en algunos registros antiguos.",
        "example": "La pleurotomia",
    },
    "titulo_limpio": {
        "category": "titulo",
        "label": "Título limpio",
        "description": "Versión limpiada del título.",
        "methodological_note": "Se usa para visualización y análisis textual básico.",
        "example": "la pleurotomia",
    },
    "titulo_normalizado": {
        "category": "titulo",
        "label": "Título normalizado",
        "description": "Versión normalizada del título para comparación, búsqueda y deduplicación.",
        "methodological_note": "Puede remover acentos, puntuación o variaciones de formato.",
        "example": "la pleurotomia",
    },

    "autores_limpios_v2": {
        "category": "autores",
        "label": "Autores limpios",
        "description": "Lista técnica completa de autores/sustentantes, separada por '|'.",
        "methodological_note": "Conserva formato bibliográfico Apellido(s), Nombre(s).",
        "example": "Alegría Rodríguez, Carolina | Alquicira Neri, Miguel Ángel",
    },
    "autor_limpio_v2": {
        "category": "autores",
        "label": "Autor principal limpio",
        "description": "Primer autor/sustentante en formato técnico bibliográfico.",
        "methodological_note": "Derivado de autores_limpios_v2.",
        "example": "Alegría Rodríguez, Carolina",
    },
    "autores_display": {
        "category": "autores",
        "label": "Autores para visualización",
        "description": "Lista de autores en formato Nombre(s) Apellido(s), separada por '|'.",
        "methodological_note": "Pensada para interfaces, tablas y visualización.",
        "example": "Carolina Alegría Rodríguez | Miguel Ángel Alquicira Neri",
    },
    "autor_display": {
        "category": "autores",
        "label": "Autor principal para visualización",
        "description": "Autor principal en formato Nombre(s) Apellido(s).",
        "methodological_note": "Derivado de autor_limpio_v2.",
        "example": "Carolina Alegría Rodríguez",
    },
    "autor_ui": {
        "category": "autores",
        "label": "Autor compacto para UI",
        "description": "Texto compacto para mostrar autor principal y número de coautores.",
        "methodological_note": "Ejemplo: 'Carolina Alegría Rodríguez · +2 más'.",
        "example": "Carolina Alegría Rodríguez · +2 más",
    },
    "num_autores": {
        "category": "autores",
        "label": "Número de autores",
        "description": "Conteo de autores/sustentantes registrados.",
        "methodological_note": "Calculado a partir de autores_limpios_v2.",
        "example": "1",
    },
    "flag_sin_autor": {
        "category": "autores",
        "label": "Sin autor",
        "description": "Indicador booleano de ausencia de autor/sustentante.",
        "methodological_note": "True cuando num_autores = 0.",
        "example": "False",
    },
    "flag_multiples_autores": {
        "category": "autores",
        "label": "Múltiples autores",
        "description": "Indicador booleano de tesis con más de un autor/sustentante.",
        "methodological_note": "True cuando num_autores > 1.",
        "example": "False",
    },

    "asesores_limpios_v2": {
        "category": "asesores",
        "label": "Asesores limpios",
        "description": "Lista técnica completa de asesores, tutores o miembros del comité, separada por '|'.",
        "methodological_note": "Conserva formato bibliográfico Apellido(s), Nombre(s).",
        "example": "Lira González, Julio César | Herrera Morales, Alma Rosa",
    },
    "asesor_limpio_v2": {
        "category": "asesores",
        "label": "Asesor principal limpio",
        "description": "Primer asesor registrado en formato técnico bibliográfico.",
        "methodological_note": "Derivado de asesores_limpios_v2.",
        "example": "Lira González, Julio César",
    },
    "asesores_display": {
        "category": "asesores",
        "label": "Asesores para visualización",
        "description": "Lista de asesores en formato Nombre(s) Apellido(s), separada por '|'.",
        "methodological_note": "Pensada para interfaces y lectura humana.",
        "example": "Julio César Lira González | Alma Rosa Herrera Morales",
    },
    "asesor_display": {
        "category": "asesores",
        "label": "Asesor principal para visualización",
        "description": "Asesor principal en formato Nombre(s) Apellido(s).",
        "methodological_note": "Derivado de asesor_limpio_v2.",
        "example": "Julio César Lira González",
    },
    "asesor_ui": {
        "category": "asesores",
        "label": "Asesor compacto para UI",
        "description": "Texto compacto para mostrar asesor principal y número de asesores adicionales.",
        "methodological_note": "Ejemplo: 'Julio César Lira González · +3 más'.",
        "example": "Julio César Lira González · +3 más",
    },
    "num_asesores": {
        "category": "asesores",
        "label": "Número de asesores",
        "description": "Conteo de asesores registrados.",
        "methodological_note": "Calculado a partir de asesores_limpios_v2.",
        "example": "1",
    },
    "flag_sin_asesor": {
        "category": "asesores",
        "label": "Sin asesor",
        "description": "Indicador booleano de ausencia de asesor registrado.",
        "methodological_note": "True cuando num_asesores = 0.",
        "example": "False",
    },
    "flag_multiples_asesores": {
        "category": "asesores",
        "label": "Múltiples asesores",
        "description": "Indicador booleano de tesis con más de un asesor o miembro de comité.",
        "methodological_note": "True cuando num_asesores > 1.",
        "example": "False",
    },

    "grado": {
        "category": "clasificacion_academica",
        "label": "Grado",
        "description": "Grado o carrera registrada en el catálogo.",
        "methodological_note": "Campo relativamente cercano al registro bibliográfico original.",
        "example": "Licenciatura en Psicología",
    },
    "grado_norm": {
        "category": "clasificacion_academica",
        "label": "Grado normalizado",
        "description": "Versión normalizada del grado o carrera.",
        "methodological_note": "Útil para agrupaciones y análisis.",
        "example": "licenciatura en psicologia",
    },
    "nivel_estandar": {
        "category": "clasificacion_academica",
        "label": "Nivel estándar",
        "description": "Nivel académico estandarizado.",
        "methodological_note": "Valores esperados: licenciatura, especialidad, maestría, doctorado u otros.",
        "example": "licenciatura",
    },
    "programa": {
        "category": "clasificacion_academica",
        "label": "Programa",
        "description": "Programa académico o campo de formación asociado.",
        "methodological_note": "Normalizado a partir del grado/carrera cuando fue posible.",
        "example": "economia",
    },
    "area": {
        "category": "clasificacion_academica",
        "label": "Área",
        "description": "Área académica o campo amplio de clasificación.",
        "methodological_note": "Puede contener áreas UNAM o agrupaciones normalizadas.",
        "example": "Ciencias Sociales",
    },

    "origen": {
        "category": "institucion",
        "label": "Origen institucional",
        "description": "Clasificación del origen institucional del registro.",
        "methodological_note": "Distingue UNAM, externa/incorporada, IPN u otros casos según extracción.",
        "example": "UNAM",
    },
    "universidad_nota": {
        "category": "institucion",
        "label": "Universidad nota",
        "description": "Universidad extraída de la nota de tesis o del registro.",
        "methodological_note": "Campo auxiliar para clasificar institución y plantel.",
        "example": "unam",
    },
    "plantel_estandarizado": {
        "category": "institucion",
        "label": "Plantel estandarizado",
        "description": "Plantel normalizado en formato técnico.",
        "methodological_note": "Pensado para agrupación y análisis.",
        "example": "facultad de economia unam",
    },
    "plantel_display": {
        "category": "institucion",
        "label": "Plantel para visualización",
        "description": "Nombre de plantel en formato legible.",
        "methodological_note": "Pensado para interfaces y reportes.",
        "example": "Facultad de Economía",
    },

    "texto_completo_url": {
        "category": "acceso",
        "label": "URL de texto completo",
        "description": "URL extraída para acceder al texto completo cuando existe.",
        "methodological_note": "Puede apuntar a distintos sistemas o rutas históricas de TESIUNAM.",
        "example": "https://tesiunamdocumentos.dgb.unam.mx/...",
    },
    "restricciones": {
        "category": "acceso",
        "label": "Restricciones de acceso",
        "description": "Información sobre disponibilidad o restricciones de acceso.",
        "methodological_note": "Puede indicar acceso abierto, restringido u otras condiciones.",
        "example": "Acceso en línea sin restricciones",
    },

    "tipo de contenido": {
        "category": "soporte",
        "label": "Tipo de contenido",
        "description": "Tipo de contenido bibliográfico.",
        "methodological_note": "Campo derivado del registro bibliográfico.",
        "example": "texto",
    },
    "medio": {
        "category": "soporte",
        "label": "Medio",
        "description": "Medio del recurso bibliográfico.",
        "methodological_note": "Campo catalográfico.",
        "example": "computadora",
    },
    "soporte": {
        "category": "soporte",
        "label": "Soporte",
        "description": "Soporte físico o digital del recurso.",
        "methodological_note": "Campo catalográfico.",
        "example": "recurso en línea",
    },
    "descr física": {
        "category": "soporte",
        "label": "Descripción física",
        "description": "Descripción física o extensión del recurso.",
        "methodological_note": "Puede incluir páginas, ilustraciones o tipo de recurso.",
        "example": "1 recurso en línea (117 páginas)",
    },
    "materia general": {
        "category": "materias",
        "label": "Materia general",
        "description": "Materias o temas generales asociados al registro.",
        "methodological_note": "Campo de cobertura parcial, útil para análisis temático cuando está disponible.",
        "example": "Anestesiología | Anestesia",
    },
}

rows = []

for i, row in desc.iterrows():
    col = row["column_name"]
    meta = column_meta.get(col, {})

    coverage = con.execute(f"""
    SELECT
        count(*) AS total,
        count(NULLIF(trim(cast("{col}" AS VARCHAR)), '')) AS non_empty,
        count(DISTINCT cast("{col}" AS VARCHAR)) AS distinct_count
    FROM read_parquet('{PARQUET.as_posix()}')
    """).fetchdf().iloc[0]

    total = int(coverage["total"])
    non_empty = int(coverage["non_empty"])
    pct = non_empty / total * 100 if total else 0

    rows.append({
        "ordinal": i + 1,
        "column_name": col,
        "type": row["column_type"],
        "category": meta.get("category", ""),
        "label": meta.get("label", col),
        "description": meta.get("description", ""),
        "methodological_note": meta.get("methodological_note", ""),
        "example": meta.get("example", ""),
        "non_empty": non_empty,
        "pct_non_empty": round(pct, 4),
        "distinct_count": int(coverage["distinct_count"]),
    })

dictionary = pd.DataFrame(rows)
dictionary.to_csv(COLUMN_DICTIONARY, index=False, encoding="utf-8")

source_txt = "\n".join(
    f"- `{r.source_record}`: {int(r.n):,} registros"
    for _, r in source_counts.iterrows()
)

README_TEXT = f"""# TESIUNAM — base7 clean

Dataset limpio y normalizado de registros de tesis de TESIUNAM, construido a partir de una base principal previamente extraída y una recuperación complementaria vía registros MARC para años con pérdida elevada de registros.

## Archivo principal

- `base7_kaggle_clean.parquet`
- Filas: {n_rows:,}
- Columnas: {len(desc)}
- Años cubiertos: {int(year_minmax['anio_min'])}–{int(year_minmax['anio_max'])}

## Distribución por fuente

{source_txt}

## Identificadores

- `thesis_id`: identificador global nuevo de la versión base7.
- `thesis_id_old`: identificador de la versión anterior, conservado para compatibilidad con prototipos previos. Solo está disponible en registros provenientes de `base6`.
- `ID_Aleph`: identificador heredado de la extracción original, cuando está disponible.
- `biblionumber` y `system_number`: identificadores disponibles principalmente en registros recuperados vía MARC/Koha.

Validación de IDs:

- Registros totales: {int(id_check['n']):,}
- `thesis_id` distintos: {int(id_check['distinct_thesis_id']):,}
- Rango `thesis_id`: {id_check['min_thesis_id']}–{id_check['max_thesis_id']}
- `thesis_id_old` no vacío: {int(id_check['thesis_id_old_no_vacio']):,}

## Años recuperados

Los siguientes años fueron reemplazados por registros recuperados vía MARC debido a pérdidas elevadas o actualización posterior:

`{", ".join(map(str, recovered_years))}`

La estrategia usada fue excluir de la base principal los registros de esos años y reemplazarlos por la recuperación MARC completa.

## Columnas principales

El dataset limpio conserva columnas de alto valor analítico:

- identificación y trazabilidad;
- año y título;
- autores y asesores en formato técnico y de visualización;
- grado, nivel, programa y área;
- origen institucional y plantel;
- acceso, soporte y restricciones;
- materia general.

Para conocer cada columna, revisar:

- `base7_column_dictionary.csv`

## Formatos de nombres

El dataset conserva dos capas para autores y asesores:

1. Columnas técnicas:
   - `autor_limpio_v2`
   - `autores_limpios_v2`
   - `asesor_limpio_v2`
   - `asesores_limpios_v2`

   Estas usan el formato bibliográfico `Apellido(s), Nombre(s)`.

2. Columnas de visualización:
   - `autor_display`
   - `autores_display`
   - `asesor_display`
   - `asesores_display`
   - `autor_ui`
   - `asesor_ui`

   Estas usan el formato `Nombre(s) Apellido(s)` y están pensadas para interfaces, tarjetas o dashboards.

## Notas de uso

- Para análisis temporal, usar `Año`.
- Para agrupación institucional, usar preferentemente `plantel_estandarizado`.
- Para visualización institucional, usar `plantel_display`.
- Para redes de asesores, usar `asesores_limpios_v2`.
- Para redes de autores, usar `autores_limpios_v2`.
- Para interfaces, usar `autor_ui` y `asesor_ui`.

## Archivos recomendados

- `base7_kaggle_clean.parquet`: versión limpia.
- `base7_column_dictionary.csv`: diccionario de columnas.
- `nota_metodologica.md`: descripción metodológica del proceso.
"""

README.write_text(README_TEXT, encoding="utf-8")

recovered_table = recovered_counts.to_markdown(index=False)

METHODOLOGY_TEXT = f"""# Nota metodológica — construcción de `base7_kaggle_clean.parquet`

## 1. Propósito

El objetivo de esta versión fue construir una base limpia, compacta y analíticamente útil de registros de tesis de TESIUNAM. La base busca servir para análisis históricos, exploración institucional, visualización, redes de asesores/autores y prototipos de búsqueda académica.

## 2. Archivo resultante

- Archivo: `base7_kaggle_clean.parquet`
- Filas: {n_rows:,}
- Columnas: {len(desc)}
- Años cubiertos: {int(year_minmax['anio_min'])}–{int(year_minmax['anio_max'])}

## 3. Fuentes integradas

La versión final integra dos fuentes internas del pipeline:

{source_txt}

`base6` corresponde a la base principal previamente procesada y normalizada.  
`marc_recovered` corresponde a registros recuperados mediante extracción de vista MARC/Koha para años con faltantes significativos.

## 4. Recuperación de años con pérdida

Se detectaron años con pérdida elevada de registros en la extracción original. Para esos años se decidió reemplazar por completo el subconjunto de la base principal con los registros recuperados vía MARC.

Años reemplazados:

`{", ".join(map(str, recovered_years))}`

La decisión metodológica fue hacer reemplazo completo por año, no solo append de registros aparentemente faltantes. Esto evita ambigüedades de deduplicación por título, autor y año, especialmente en años donde la extracción original estaba incompleta.

Distribución de los años recuperados en la versión final:

{recovered_table}

## 5. Identificadores

Se creó un nuevo identificador global:

- `thesis_id`: ID único de la versión base7.

También se conservó:

- `thesis_id_old`: ID de la base anterior, útil para compatibilidad con prototipos previos. Está disponible solo para registros provenientes de `base6`.
- `ID_Aleph`: identificador heredado de la extracción original.
- `biblionumber`: identificador de Koha, principalmente disponible en registros recuperados vía MARC.
- `system_number`: número de sistema bibliográfico, principalmente disponible en registros MARC.

Validación:

- Registros totales: {int(id_check['n']):,}
- `thesis_id` distintos: {int(id_check['distinct_thesis_id']):,}
- Rango `thesis_id`: {id_check['min_thesis_id']}–{id_check['max_thesis_id']}
- `thesis_id_old` no vacío: {int(id_check['thesis_id_old_no_vacio']):,}

## 6. Normalización de autores

Se construyó una arquitectura paralela para autores:

- `autores_limpios_v2`: lista completa técnica, separada por `|`.
- `autor_limpio_v2`: primer autor técnico.
- `autores_display`: lista completa en formato legible.
- `autor_display`: primer autor en formato legible.
- `autor_ui`: texto compacto para interfaces.
- `num_autores`: número de autores detectados.
- `flag_sin_autor`: indicador de registros sin autor.
- `flag_multiples_autores`: indicador de coautoría.

La capa técnica conserva el formato bibliográfico `Apellido(s), Nombre(s)`. La capa display invierte a `Nombre(s) Apellido(s)`.

## 7. Normalización de asesores

Se aplicó la misma lógica a asesores:

- `asesores_limpios_v2`
- `asesor_limpio_v2`
- `asesores_display`
- `asesor_display`
- `asesor_ui`
- `num_asesores`
- `flag_sin_asesor`
- `flag_multiples_asesores`

En registros con múltiples asesores o comité, los nombres se separan con `|`.

## 8. Planteles e instituciones

Se conservaron dos capas:

- `plantel_estandarizado`: forma técnica normalizada, útil para análisis.
- `plantel_display`: forma legible, útil para visualización.

También se conservaron:

- `origen`
- `universidad_nota`

Estas columnas permiten distinguir entre registros UNAM, instituciones incorporadas y otras entidades participantes cuando la información está disponible.

Nota (2026-09-20): se removió `entidad_clean` de esta versión — era un campo de linaje interno del pipeline (82% redundante con `plantel_estandarizado`, sin consumidor en producción). Se archivó completa en `data/lineage/entidad_clean_archivado_2026-09-20.parquet`. Ver `adr/0007-archivar-entidad-clean.md`.

## 9. Columnas incluidas y excluidas

La versión limpia conserva {len(desc)} columnas centradas en análisis y visualización. Se excluyeron columnas crudas, intermedias o de auditoría, como campos MARC completos, notas catalográficas extensas, columnas antiguas de limpieza y flags técnicos.

La decisión busca reducir ruido para usuarios externos y mantener una estructura más clara.

Para reproducibilidad interna, se recomienda conservar por separado una versión completa/auditable derivada de `base7_full_recovered.parquet`.

## 10. Limitaciones

1. La cobertura no es homogénea entre columnas. Algunas variables provienen de rutas distintas de extracción.
2. `ID_Aleph` está disponible principalmente para registros de la base original.
3. `biblionumber` y `system_number` están disponibles principalmente para registros recuperados vía MARC.
4. `thesis_id_old` solo existe para registros provenientes de la versión anterior.
5. Algunos años recientes, especialmente 2026, pueden estar incompletos por carga documental en curso.
6. La normalización de nombres busca ser conservadora; no pretende resolver todas las variantes nominales históricas.
7. El campo `materia general` tiene cobertura parcial y debe usarse con cautela para análisis temático.

## 11. Recomendaciones de uso

- Para conteos anuales: `Año`.
- Para análisis institucional: `plantel_estandarizado`.
- Para visualización institucional: `plantel_display`.
- Para autores: `autores_limpios_v2` o `autor_display`, según uso técnico o visual.
- Para asesores: `asesores_limpios_v2` o `asesor_display`.
- Para prototipos previos: usar `thesis_id_old` cuando exista; si está vacío, usar `thesis_id`.

Ejemplo de ID estable para prototipo:

```python
stable_id = thesis_id_old if thesis_id_old else thesis_id METHODOLOGY.write_text(METHODOLOGY_TEXT, encoding="utf-8")

print("LISTO")
print("Diccionario:", COLUMN_DICTIONARY)
print("README:", README)
print("Nota metodológica:", METHODOLOGY)
print("Filas:", f"{n_rows:,}")
print("Columnas:", len(desc))
