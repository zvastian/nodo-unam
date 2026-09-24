# ADR-0011: `data_unam.parquet` — export público/producto, esquema final

- **Estado**: Aceptado (2026-09-20).

## Contexto

Decisiones acumuladas de la sesión 2026-09-20 sobre qué columnas expone el dataset "sanitizado" (para Kaggle y, más adelante, como fuente única para regenerar los artefactos de la app):

- Autores (estudiantes) fuera por privacidad — decisión de producto, no solo del dataset descargable.
- Asesores (docentes UNAM) se quedan — información valiosa, ya verificada sin bugs de inversión, y con la homogeneización de "Blanco De Mendieta" aplicada (ver ADR-0010).
- `plantel`: solo la versión técnica (`plantel_estandarizado`), sin `plantel_display` — decisión de simplificar a un solo campo.
- `flag_sin_asesor` y `flag_multiples_asesores`: fuera.
- `thesis_id_old`, `ID_Aleph`, `source_record` (fuente): fuera.
- `texto_completo_url`: fuera (URLs inválidas por cambio de proveedor, ver ADR-0009).
- `entidad_clean`: ya fuera desde ADR-0007.
- Renombrado general: se quitan sufijos de proceso interno (`_v2`, `_norm`, `_estandarizado`, `_display`) por nombres simples orientados a propósito (ej. `titulo_normalizado` → `titulo_busqueda`, `asesor_display` → `asesor`).

## Decisión

Nuevo archivo: **`data/public/data_unam.parquet`** — separado físicamente de `data/clean/base7_kaggle_clean.parquet` (que se queda como maestro completo, local, con nombres de autor, para uso interno futuro si se necesita). Generado por `pipeline/generar_data_unam.py`, con mapeo explícito columna-por-columna (no un `drop()` de lo que sobra, para que agregar una columna nueva al maestro en el futuro no se filtre por accidente al export público — hay que agregarla a `COLUMN_MAP` a propósito).

**Esquema final (25 columnas)**: `thesis_id`, `biblionumber`, `system_number`, `anio`, `titulo_original`, `titulo`, `titulo_busqueda`, `num_autores`, `asesor`, `asesores`, `num_asesores`, `grado`, `grado_busqueda`, `nivel`, `programa`, `area`, `origen`, `universidad`, `plantel`, `restricciones`, `tipo_contenido`, `medio`, `soporte`, `descripcion_fisica`, `materias`.

## Actualización 2026-09-20 (segunda pasada)

- **`biblionumber`/`system_number` removidas** — cobertura demasiado baja (solo poblados en registros MARC) para justificar su lugar en el export público.
- **`area` corregida en el maestro**: "Por Clasificar" (456 filas) rompía la convención de nulos del dataset (cadena vacía = sin dato, no un texto placeholder). Investigado: `programa` está vacío en el 100% de esas filas, por eso no se pudo clasificar — no es un error de clasificación, es ausencia de información de origen. Se reemplazó por cadena vacía, consistente con el resto del dataset.
- **`titulo`/`titulo_busqueda` colapsados en un solo campo `titulo`**: se descarta la versión intermedia (`titulo_limpio`, con acentos/puntuación) y se usa la versión normalizada (`titulo_normalizado`, sin acentos ni puntuación) bajo el nombre simple `titulo`. La nota metodológica debe aclarar que este campo está normalizado para búsqueda/comparación, no es el título con formato de lectura completo (para eso está `titulo_original`, la cadena bibliográfica cruda).
- Esquema final: **22 columnas** (era 25).

## Consecuencias

- (+) Separación física real entre el maestro (con PII) y lo público — no depende de que la UI "no muestre" un campo, el dato con nombres de autor ni siquiera llega a este archivo.
- (+) El script usa una lista explícita de inclusión (no exclusión), más seguro por defecto ante cambios futuros en el maestro.
- (-) Pendiente: apuntar `build_thesis_lookup.py` (y por tanto la app, ver ADR-0004) a este archivo en vez de al maestro directamente, para que el producto tampoco muestre autores — ese cambio de código todavía no se ha hecho.
- (-) Pendiente: exportar `data_unam.parquet` también a CSV si Kaggle lo requiere en ese formato (hoy solo existe en parquet).
