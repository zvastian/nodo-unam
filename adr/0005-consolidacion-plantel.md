# ADR-0005: Política de consolidación de entidades duplicadas — aplicada a `plantel`

- **Estado**: Aceptado (2026-09-20).

## Contexto

Auditoría de `data/clean/base7_kaggle_clean.parquet` (ver conversación 2026-09-20) encontró en `plantel_estandarizado` (591 valores únicos) 22 grupos de duplicados residuales — la misma institución partida en 2 formas por inconsistencia de sufijo "UNAM" o presencia/ausencia de acento — y en `plantel_display` 23 grupos con el mismo problema a nivel de etiqueta visible, afectando 6,640 filas (1.1% del corpus).

Riesgo explícito señalado por el usuario: un script de consolidación "generalizado" puede fusionar entidades que en realidad son distintas (falso positivo), o dejar de fusionar duplicados reales por ser demasiado conservador.

## Decisión — política de consolidación (reutilizable para futuros campos, no solo plantel)

1. **Solo se fusionan grupos con evidencia verificada manualmente** por clave normalizada (sin acentos, sin token "UNAM") — no se aplica una transformación ciega a toda la columna.
2. **`plantel_estandarizado`** (campo interno/técnico): la forma canónica respeta la convención ya establecida en el resto de la columna (ASCII sin acentos, confirmado en las 590 entradas no afectadas). Cuando la convención y la mayoría por conteo coinciden, se usa esa forma; cuando entran en conflicto (caso real: "Escuela Normal Superior de México", mayoría 11 filas con acento vs. 1 fila sin acento que sí respeta la convención), **gana la convención del archivo sobre el conteo mayoritario**.
3. **`plantel_display`** (campo de presentación): se usa mayoría simple, pero **solo si el valor ganador tiene ≥90% de las filas del grupo**. Grupos sin mayoría clara (ej. 40 vs 3 vs 1 vs 1 vs 1 — no cumple el umbral por count absoluto bajo y dispersión) se reportan mediante el audit log y **no se tocan** — quedan para decisión manual explícita.
4. Todo cambio queda auditado en un CSV (`pipeline/audits/plantel_consolidation_2026-09-20.csv`) con valor original, valor nuevo, filas afectadas y regla aplicada — nunca un reemplazo silencioso.
5. Se conserva un backup del archivo original antes de escribir (`data/clean/base7_kaggle_clean.before_plantel_consolidation_2026-09-20.parquet`).

## Resultado de esta ejecución

- `plantel_estandarizado`: 591 → 569 valores únicos (22 grupos fusionados, todos de baja frecuencia individual — el hallazgo no tocó ninguno de los 20 planteles grandes, que ya estaban limpios).
- `plantel_display`: 23 grupos fusionados automáticamente (cumplían el umbral de 90%); **13 grupos quedaron señalados para revisión manual** por no tener mayoría clara — ver salida del script o re-ejecutar `pipeline/consolidar_plantel.py` para verlos.
- Verificado que la fusión no fue un artefacto del algoritmo: en los casos donde el resultado es un acrónimo (ENAC, ENALLT, ENES + sede), ese acrónimo ya era la forma dominante preexistente en 31-946 filas — el script preservó la convención ya establecida, no la inventó.
- Validaciones automáticas pasaron: 609,156 filas antes y después, `thesis_id` sigue 100% único.

## Consecuencias

- (+) Política reutilizable para otros campos con el mismo problema (ej. `entidad_clean`, `programa`) sin tener que rediseñar el enfoque desde cero.
- (+) Nada se pierde: backup + audit log permiten revertir o inspeccionar cualquier cambio individual.

## Actualización 2026-09-20 (segunda pasada) — resolución de los 13 empates + decisión de acrónimos

Usuario decidió explícitamente:
- **Expandir acrónimos a nombre completo**: `ENAC`, `ENALLT`, `ENES León`, `ENES Morelia`, `ENES Juriquilla`, `ENCiT`, `ENES Mérida` (1,662 filas) — revierte la fusión automática por mayoría de la primera pasada para estos 7 casos.
- **Formato coma+"Campus" en vez de paréntesis** para Universidad Latina (Cuautla, Sur) — se adoptó el patrón ya dominante y no disputado en el resto del archivo (`"Universidad de Sotavento, Campus Orizaba"`), no una eliminación literal de la palabra "Campus".
- Los 9 empates restantes (case/acento puro, sin instrucción explícita) se resolvieron con la misma regla de "ortografía correcta + formato `X, Y`" ya establecida — extensión razonable de la política, marcada explícitamente para que el usuario la corrija si no era la intención.

Aplicado en `pipeline/consolidar_plantel_display_empates.py`. Backup adicional: `data/clean/base7_kaggle_clean.before_plantel_display_empates_2026-09-20.parquet`. Audit log: `pipeline/audits/plantel_display_empates_2026-09-20.csv` (18 cambios, 1,683 filas afectadas).

**Explícitamente NO tocado, pendiente de confirmación**: `CCH` (1,236 filas) y `ENTS` (2,226 filas) — acrónimos masivos, sin ambigüedad (no eran duplicados reportados), de uso universalmente reconocido incluso por la propia UNAM. No se incluyeron en "expandir" porque no formaban parte de los grupos disputados originalmente reportados — aplicar la misma regla ahí sería generalizar más allá de lo pedido.

## Actualización 2026-09-20 (tercera pasada) — gap en el detector original, encontrado al pedir recuento de ENES

El usuario pidió el recuento final de ENES para confirmar que no quedaba ambigüedad. Al verificar aparecieron **4 duplicados que el detector original no capturó**, porque ese detector solo normalizaba acentos y el sufijo "UNAM" — no palabras completas faltantes:

- `escuela nacional de estudios superiores leon` (1 fila, sin "unidad") — mismo que `...unidad leon unam` (946 filas).
- `escuela nacional de estudios superiores merida` (5 filas, sin "unidad") — mismo que `...unidad merida unam` (46 filas). Esta ya se había tocado en la pasada anterior (se le corrigió el acento del *display*) sin notar que el `plantel_estandarizado` en sí seguía siendo un bucket separado.
- `escuela nacional de estudios superiores morelia` (9 filas, sin "unidad") — mismo que `...unidad morelia unam` (531 filas).
- `escuela nacional e trabajo social` (1 fila, typo "e" en vez de "de") — mismo que `escuela nacional de trabajo social unam` / ENTS (2,225 filas).

Además, 3 filas sueltas de `plantel_display` dentro del grupo de Mérida (variantes sin coma o sin acento) se habían quedado fuera de la pasada de empates anterior.

Aplicado en `pipeline/consolidar_plantel_enes_ents.py`. Backup: `data/clean/base7_kaggle_clean.before_enes_ents_fix_2026-09-20.parquet`. Audit: `pipeline/audits/plantel_enes_ents_2026-09-20.csv`. `plantel_estandarizado`: 569 → 565.

**Resultado verificado**: León (947), Morelia (540), Mérida (51), Juriquilla (36) — cada uno con exactamente 1 `plantel_estandarizado` ↔ 1 `plantel_display`. Las 15 filas de `ENES` sin sede especificada se dejan intactas — son datos incompletos genuinos, no un duplicado (no hay base para asignarlas a una sede sin inventar información). ENTS: 2,226 filas, un solo valor.

**Lección para la política (ADR-0005)**: el detector de duplicados por clave normalizada debe ampliarse para tolerar palabras funcionales faltantes/de más (ej. "unidad", preposiciones), no solo acentos y un token fijo como "UNAM" — quedó pendiente para la próxima vez que se audite otro campo con el mismo método.

**Hallazgos adicionales, fuera de alcance de esta pregunta en su momento**:
- `centro de estudios superiores de martinez de la torre` vs `...martinez de la torre` sin "de" — confirmado y fusionado (ver cuarta actualización).
- `centro panamericano de estudios superiores` vs `universidad centro panamericano de estudios superiores` — confirmado y fusionado (ver cuarta actualización).

## Actualización 2026-09-20 (cuarta y última pasada) — cierre formal de `plantel`

Usuario pidió fusionar los 2 candidatos pendientes y **buscar sistemáticamente casos similares** para dar por terminado el trabajo en `plantel`. Se usaron dos técnicas nuevas sobre las 565 formas de `plantel_estandarizado` restantes:

1. **Clave laxa**: ignora acentos + palabras de relleno (de, la, unidad, universidad, campus, unam, y, en) — encontró 10 grupos candidatos.
2. **Similitud de texto** (`SequenceMatcher` ≥ 0.90) — encontró 97 pares candidatos.

**Hallazgo crítico de esta pasada**: la gran mayoría de los 97 pares de similitud de texto eran **falsos positivos** — instituciones y programas de posgrado reales y distintos que solo coinciden en texto (ej. "Instituto de Ecología" vs "Instituto de Geología", "Universidad Panamericana" vs "Universidad Latinoamericana", "Ciencias Bioquímicas" vs "Ciencias Químicas"). Cada uno de los 97 se revisó a mano. Resultado:

- **27 fusiones aplicadas** a `plantel_estandarizado` (typos, preposiciones faltantes, orden de palabras, abreviaturas de estado redundantes) — `pipeline/consolidar_plantel_final.py`.
- **16 ajustes adicionales de `plantel_display`** recalculados tras esas fusiones — mismo script.
- **14 grupos de `plantel_display` sin mayoría automática** tras las fusiones (empates cerrados, ej. 103 vs 100) resueltos a mano por corrección ortográfica/gramatical y consistencia con el resto del archivo — `pipeline/consolidar_plantel_display_final.py`.
- **1 grupo que se había quedado fuera de la segunda pasada** ("Escuela Nacional de Música" vs "...Musica") — detectado en la verificación final y corregido.
- **64 pares evaluados y explícitamente descartados** por ser instituciones/programas reales distintos — documentados en `pipeline/audits/plantel_descartados_2026-09-20.csv` para dejar constancia de que se revisaron, no que se pasaron por alto.

**Caso especial preservado, no fusionado a propósito**: `escuela nacional de estudios profesionales acatlan` (2 filas, típograficamente corregido) se mantiene **separado** de `facultad de estudios superiores acatlan unam` (22,213 filas) — es el nombre histórico anterior de la institución (ENEP Acatlán, antes de renombrarse a FES Acatlán). Fusionarlos habría borrado información histórica real (una tesis de esa época sí se presentó bajo el nombre antiguo).

**Resultado final verificado**: `plantel_estandarizado` (538) y `plantel_display` (538) en relación 1:1 perfecta — cero grupos con más de un valor de display por estandarizado. 609,156 filas y `thesis_id` únicos intactos en las 5 pasadas de fusión (verificado con `assert` en cada script). `plantel` se da por **cerrado**.
