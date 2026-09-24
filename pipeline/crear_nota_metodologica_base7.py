from pathlib import Path
import duckdb

PARQUET = Path("base7_kaggle_clean.parquet")
OUT = Path("nota_metodologica.md")

if not PARQUET.exists():
    raise FileNotFoundError(f"No encontré {PARQUET}")

con = duckdb.connect()

n_rows = int(con.execute(f"""
SELECT count(*) AS n FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf()["n"].iloc[0])

n_cols = len(con.execute(f"""
DESCRIBE SELECT * FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf())

year_minmax = con.execute(f"""
SELECT min("Año") AS min_year, max("Año") AS max_year
FROM read_parquet('{PARQUET.as_posix()}')
""").fetchdf().iloc[0]

source_counts = con.execute(f"""
SELECT source_record, count(*) AS n
FROM read_parquet('{PARQUET.as_posix()}')
GROUP BY 1
ORDER BY 1
""").fetchdf()

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

lines = []

lines.append("# Nota metodológica — construcción de base7_kaggle_clean.parquet")
lines.append("")
lines.append("## 1. Propósito")
lines.append("")
lines.append("El objetivo fue construir una base limpia, compacta y analíticamente útil de registros de tesis de TESIUNAM.")
lines.append("")
lines.append("La base busca servir para análisis históricos, exploración institucional, visualización, redes de asesores/autores y prototipos de búsqueda académica.")
lines.append("")
lines.append("## 2. Archivo resultante")
lines.append("")
lines.append("- Archivo: `base7_kaggle_clean.parquet`")
lines.append(f"- Filas: {n_rows:,}")
lines.append(f"- Columnas: {n_cols}")
lines.append(f"- Años cubiertos: {int(year_minmax['min_year'])}–{int(year_minmax['max_year'])}")
lines.append("")
lines.append("## 3. Fuentes integradas")
lines.append("")
lines.append("La versión final integra dos fuentes internas del pipeline:")
lines.append("")

for _, r in source_counts.iterrows():
    lines.append(f"- `{r.source_record}`: {int(r.n):,} registros")

lines.append("")
lines.append("`base6` corresponde a la base principal previamente procesada y normalizada.")
lines.append("")
lines.append("`marc_recovered` corresponde a registros recuperados mediante extracción de vista MARC/Koha para años con faltantes significativos.")
lines.append("")
lines.append("## 4. Recuperación de años con pérdida")
lines.append("")
lines.append("Se detectaron años con pérdida elevada de registros en la extracción original. Para esos años se decidió reemplazar por completo el subconjunto de la base principal con registros recuperados vía MARC.")
lines.append("")
lines.append("Años reemplazados:")
lines.append("")
lines.append("`" + ", ".join(map(str, recovered_years)) + "`")
lines.append("")
lines.append("La decisión metodológica fue hacer reemplazo completo por año, no append de registros aparentemente faltantes. Esto evita ambigüedades de deduplicación por título, autor y año.")
lines.append("")
lines.append("Distribución de los años recuperados en la versión final:")
lines.append("")
lines.append("| Año | Fuente | Registros |")
lines.append("|---:|---|---:|")

for _, r in recovered_counts.iterrows():
    lines.append(f"| {int(r['anio'])} | {r['source_record']} | {int(r['n']):,} |")

lines.append("")
lines.append("## 5. Identificadores")
lines.append("")
lines.append("Se creó un nuevo identificador global:")
lines.append("")
lines.append("- `thesis_id`: ID único de la versión base7.")
lines.append("")
lines.append("También se conservó:")
lines.append("")
lines.append("- `thesis_id_old`: ID de la base anterior, útil para compatibilidad con prototipos previos.")
lines.append("- `ID_Aleph`: identificador heredado de la extracción original.")
lines.append("- `biblionumber`: identificador de Koha, principalmente disponible en registros recuperados vía MARC.")
lines.append("- `system_number`: número de sistema bibliográfico, principalmente disponible en registros MARC.")
lines.append("")
lines.append("Validación:")
lines.append("")
lines.append(f"- Registros totales: {int(id_check['n']):,}")
lines.append(f"- `thesis_id` distintos: {int(id_check['distinct_thesis_id']):,}")
lines.append(f"- Rango `thesis_id`: {id_check['min_thesis_id']}–{id_check['max_thesis_id']}")
lines.append(f"- `thesis_id_old` no vacío: {int(id_check['thesis_id_old_no_vacio']):,}")
lines.append("")
lines.append("## 6. Normalización de autores")
lines.append("")
lines.append("Se construyó una arquitectura paralela para autores:")
lines.append("")
lines.append("- `autores_limpios_v2`: lista completa técnica, separada por `|`.")
lines.append("- `autor_limpio_v2`: primer autor técnico.")
lines.append("- `autores_display`: lista completa en formato legible.")
lines.append("- `autor_display`: primer autor en formato legible.")
lines.append("- `autor_ui`: texto compacto para interfaces.")
lines.append("- `num_autores`: número de autores detectados.")
lines.append("- `flag_sin_autor`: indicador de registros sin autor.")
lines.append("- `flag_multiples_autores`: indicador de coautoría.")
lines.append("")
lines.append("La capa técnica conserva el formato bibliográfico `Apellido(s), Nombre(s)`. La capa display invierte a `Nombre(s) Apellido(s)`.")
lines.append("")
lines.append("## 7. Normalización de asesores")
lines.append("")
lines.append("Se aplicó una lógica equivalente a asesores:")
lines.append("")
lines.append("- `asesores_limpios_v2`")
lines.append("- `asesor_limpio_v2`")
lines.append("- `asesores_display`")
lines.append("- `asesor_display`")
lines.append("- `asesor_ui`")
lines.append("- `num_asesores`")
lines.append("- `flag_sin_asesor`")
lines.append("- `flag_multiples_asesores`")
lines.append("")
lines.append("En registros con múltiples asesores o comité, los nombres se separan con `|`.")
lines.append("")
lines.append("## 8. Planteles e instituciones")
lines.append("")
lines.append("Se conservaron dos capas:")
lines.append("")
lines.append("- `plantel_estandarizado`: forma técnica normalizada, útil para análisis.")
lines.append("- `plantel_display`: forma legible, útil para visualización.")
lines.append("")
lines.append("También se conservaron:")
lines.append("")
lines.append("- `origen`")
lines.append("- `universidad_nota`")
lines.append("")
lines.append("Estas columnas permiten distinguir entre registros UNAM, instituciones incorporadas y otras entidades participantes cuando la información está disponible.")
lines.append("")
lines.append("Nota (2026-09-20): se removió `entidad_clean` de esta versión — era un campo de linaje interno del pipeline (82% redundante con `plantel_estandarizado`, sin consumidor en producción). Se archivó completa en `data/lineage/entidad_clean_archivado_2026-09-20.parquet`. Ver `adr/0007-archivar-entidad-clean.md`.")
lines.append("")
lines.append("## 9. Columnas incluidas y excluidas")
lines.append("")
lines.append(f"La versión limpia conserva {n_cols} columnas centradas en análisis y visualización.")
lines.append("")
lines.append("Se excluyeron columnas crudas, intermedias o de auditoría, como campos MARC completos, notas catalográficas extensas, columnas antiguas de limpieza y flags técnicos.")
lines.append("")
lines.append("La decisión busca reducir ruido para usuarios externos y mantener una estructura más clara.")
lines.append("")
lines.append("Para reproducibilidad interna, se recomienda conservar por separado una versión completa/auditable derivada de `base7_full_recovered.parquet`.")
lines.append("")
lines.append("## 10. Limitaciones")
lines.append("")
lines.append("1. La cobertura no es homogénea entre columnas. Algunas variables provienen de rutas distintas de extracción.")
lines.append("2. `ID_Aleph` está disponible principalmente para registros de la base original.")
lines.append("3. `biblionumber` y `system_number` están disponibles principalmente para registros recuperados vía MARC.")
lines.append("4. `thesis_id_old` solo existe para registros provenientes de la versión anterior.")
lines.append("5. Algunos años recientes, especialmente 2026, pueden estar incompletos por carga documental en curso.")
lines.append("6. La normalización de nombres busca ser conservadora; no pretende resolver todas las variantes nominales históricas.")
lines.append("7. El campo `materia general` tiene cobertura parcial y debe usarse con cautela para análisis temático.")
lines.append("")
lines.append("## 11. Recomendaciones de uso")
lines.append("")
lines.append("- Para conteos anuales: `Año`.")
lines.append("- Para análisis institucional: `plantel_estandarizado`.")
lines.append("- Para visualización institucional: `plantel_display`.")
lines.append("- Para autores: `autores_limpios_v2` o `autor_display`, según uso técnico o visual.")
lines.append("- Para asesores: `asesores_limpios_v2` o `asesor_display`.")
lines.append("- Para prototipos previos: usar `thesis_id_old` cuando exista; si está vacío, usar `thesis_id`.")
lines.append("")
lines.append("Ejemplo de regla de compatibilidad para prototipos:")
lines.append("")
lines.append("- `stable_id = thesis_id_old if thesis_id_old else thesis_id`")
lines.append("")

OUT.write_text("\n".join(lines), encoding="utf-8")

print("LISTO")
print("Archivo:", OUT)
print("Filas documentadas:", f"{n_rows:,}")
print("Columnas documentadas:", n_cols)
