# ADR-0010: Corrección de nombres de asesor (typos, "?", años incrustados)

- **Estado**: Aceptado (2026-09-20).

## Contexto

Verificación pedida por el usuario sobre `asesor_display` (¿la inversión "Apellido, Nombre" → "Nombre Apellido" tenía bugs?): **no** — 535,079 de 535,079 casos verificables (formato con una sola coma) coinciden exactamente con lo esperado. 100% correcto.

Sí se encontraron problemas puntuales de fondo, no del algoritmo de inversión:

1. **Typos de OCR, dígito por letra** (7 casos): `Gustav0`→`Gustavo`, `B0llestas`→`Bollestas`, `Alf0nso`→`Alfonso`, `R0sales`→`Rosales`, `0lavarrieta`→`Olavarrieta`, `0lvera`→`Olvera`, `Marqu3z`→`Marquez`.
2. **"?" en vez de "ñ"** (23 casos): `Avenda?o`→`Avendaño`, `Zu?iga`→`Zúñiga`, `Mu?oz`→`Muñoz`, etc. — variante del mismo problema de codificación visto antes en `programa`/`grado_norm`, aquí con signo de interrogación en vez de espacio.
3. **Años de nacimiento de registro de autoridad bibliográfica incrustados en el nombre** (291 filas con más de una coma): ej. `Dallal, Alberto, 1936` — convención bibliotecaria real ("Apellido, Nombre, año de nacimiento") mal aislada del campo de nombre. Resuelto con una regla general: truncar a los primeros 2 segmentos separados por coma (apellidos, nombres), descartando cualquier fragmento adicional.
4. **Un caso de fecha incrustada a mitad de un apellido**: `Blanco D 2019mendieta, Julio Alejandro` → corregido a mano a `Blanco De Mendieta, Julio Alejandro` (decisión explícita del usuario: "De Mendieta" separado, no "Demendieta").

## Decisión

Aplicado en `pipeline/corregir_asesores.py`: correcciones puntuales (lista de 9 reemplazos de substring) + regla general de truncado a 2 segmentos, sobre `asesor_limpio_v2` y `asesores_limpios_v2`. `asesor_display`/`asesores_display` se **recalculan desde el técnico ya corregido** (no se parchean por separado) para garantizar consistencia.

## Resultado

- 314 filas de `asesor_limpio_v2` corregidas, 426 de `asesores_limpios_v2` (223 valores únicos).
- Verificación final: 0 dígitos, 0 "?", 0 casos con más de una coma restantes en `asesor_limpio_v2`.
- Backup: `data/clean/base7_kaggle_clean.before_corregir_asesores_2026-09-20.parquet`. Audit: `pipeline/audits/corregir_asesores_2026-09-20.csv`.

## Hallazgo adicional, NO resuelto (fuera de alcance de esta corrección)

El apellido "Blanco De Mendieta" tiene ~10 variantes de escritura distintas en el dataset (`Blanco de Mendieta`, `Blanco D'Mendieta`, `Blanco DMendieta`, `Blanco Mendieta`, etc.) — mismo tipo de problema de entidades duplicadas resuelto en `plantel` (ADR-0005), aplicado esta vez a un nombre de persona. No se tocó porque no formaba parte de lo solicitado. Si se decide aplicar el mismo criterio a nombres de asesores en el futuro, este es un buen caso de prueba.
