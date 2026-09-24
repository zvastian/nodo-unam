# Nota metodológica — construcción de base7_kaggle_clean.parquet

## 1. Propósito

El objetivo fue construir una base limpia, compacta y analíticamente útil de registros de tesis de TESIUNAM.

La base busca servir para análisis históricos, exploración institucional, visualización, redes de asesores/autores y prototipos de búsqueda académica.

## 2. Archivo resultante

- Archivo: `base7_kaggle_clean.parquet`
- Filas: 609,156
- Columnas: 43
- Años cubiertos: 1873–2026

## 3. Fuentes integradas

La versión final integra dos fuentes internas del pipeline:

- `base6`: 562,211 registros
- `marc_recovered`: 46,945 registros

`base6` corresponde a la base principal previamente procesada y normalizada.

`marc_recovered` corresponde a registros recuperados mediante extracción de vista MARC/Koha para años con faltantes significativos.

## 4. Recuperación de años con pérdida

Se detectaron años con pérdida elevada de registros en la extracción original. Para esos años se decidió reemplazar por completo el subconjunto de la base principal con registros recuperados vía MARC.

Años reemplazados:

`1905, 1913, 1960, 1980, 1985, 1987, 1989, 1995, 2026`

La decisión metodológica fue hacer reemplazo completo por año, no append de registros aparentemente faltantes. Esto evita ambigüedades de deduplicación por título, autor y año.

Distribución de los años recuperados en la versión final:

| Año | Fuente | Registros |
|---:|---|---:|
| 1905 | marc_recovered | 43 |
| 1913 | marc_recovered | 91 |
| 1960 | marc_recovered | 1,077 |
| 1980 | marc_recovered | 5,857 |
| 1985 | marc_recovered | 8,491 |
| 1987 | marc_recovered | 8,574 |
| 1989 | marc_recovered | 8,728 |
| 1995 | marc_recovered | 11,111 |
| 2026 | marc_recovered | 2,973 |

## 5. Identificadores

Se creó un nuevo identificador global:

- `thesis_id`: ID único de la versión base7.

También se conservó:

- `thesis_id_old`: ID de la base anterior, útil para compatibilidad con prototipos previos.
- `ID_Aleph`: identificador heredado de la extracción original.
- `biblionumber`: identificador de Koha, principalmente disponible en registros recuperados vía MARC.
- `system_number`: número de sistema bibliográfico, principalmente disponible en registros MARC.

Validación:

- Registros totales: 609,156
- `thesis_id` distintos: 609,156
- Rango `thesis_id`: TH_0000001–TH_0609156
- `thesis_id_old` no vacío: 562,211

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

Se aplicó una lógica equivalente a asesores:

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
- `entidad_clean`

Estas columnas permiten distinguir entre registros UNAM, instituciones incorporadas y otras entidades participantes cuando la información está disponible.

## 9. Columnas incluidas y excluidas

La versión limpia conserva 43 columnas centradas en análisis y visualización.

Se excluyeron columnas crudas, intermedias o de auditoría, como campos MARC completos, notas catalográficas extensas, columnas antiguas de limpieza y flags técnicos.

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

Ejemplo de regla de compatibilidad para prototipos:

- `stable_id = thesis_id_old if thesis_id_old else thesis_id`
