# TESIUNAM — base7 clean

Dataset limpio y normalizado de registros de tesis de TESIUNAM.

Esta versión integra una base principal previamente procesada y una recuperación complementaria vía registros MARC para años con pérdida elevada de registros.

## Archivo principal

- `base7_kaggle_clean.parquet`
- Filas: 609,156
- Columnas: 43
- Años cubiertos: 1873–2026

## Distribución por fuente

- `base6`: 562,211 registros
- `marc_recovered`: 46,945 registros

## Identificadores

- `thesis_id`: identificador global nuevo de la versión base7.
- `thesis_id_old`: identificador anterior, conservado para compatibilidad con prototipos previos. Solo existe para registros provenientes de `base6`.
- `ID_Aleph`: identificador heredado de la extracción original.
- `biblionumber` y `system_number`: identificadores principalmente disponibles en registros recuperados vía MARC/Koha.

Validación:

- Registros totales: 609,156
- `thesis_id` distintos: 609,156
- Rango `thesis_id`: TH_0000001–TH_0609156
- `thesis_id_old` no vacío: 562,211

## Años recuperados

Los siguientes años fueron reemplazados por registros recuperados vía MARC:

`1905, 1913, 1960, 1980, 1985, 1987, 1989, 1995, 2026`

La estrategia fue excluir de la base principal los registros de esos años y reemplazarlos por la recuperación MARC completa.

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

El dataset conserva dos capas para autores y asesores.

Columnas técnicas:

- `autor_limpio_v2`
- `autores_limpios_v2`
- `asesor_limpio_v2`
- `asesores_limpios_v2`

Estas usan el formato bibliográfico `Apellido(s), Nombre(s)`.

Columnas de visualización:

- `autor_display`
- `autores_display`
- `asesor_display`
- `asesores_display`
- `autor_ui`
- `asesor_ui`

Estas usan el formato `Nombre(s) Apellido(s)`.

## Notas de uso

- Para análisis temporal, usar `Año`.
- Para agrupación institucional, usar `plantel_estandarizado`.
- Para visualización institucional, usar `plantel_display`.
- Para redes de asesores, usar `asesores_limpios_v2`.
- Para redes de autores, usar `autores_limpios_v2`.
- Para interfaces, usar `autor_ui` y `asesor_ui`.
- Para compatibilidad con prototipos anteriores, usar `thesis_id_old` cuando exista; si está vacío, usar `thesis_id`.

## Archivos recomendados

- `base7_kaggle_clean.parquet`
- `base7_column_dictionary.csv`
- `nota_metodologica.md`
