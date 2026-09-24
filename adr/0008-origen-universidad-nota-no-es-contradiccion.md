# ADR-0008: `origen` vs `universidad_nota` — no es una contradicción, no se toca

- **Estado**: Aceptado / cerrado sin acción (2026-09-20).

## Contexto

Se detectaron 12,658 filas donde `origen = "EXTERNAS E INCORPORADAS"` pero `universidad_nota = "unam"`, aparentando ser información contradictoria (¿es UNAM o es externa?).

## Investigación

- Las 12,658 filas son **100% `source_record = 'base6'`** — cero en `marc_recovered`. No hay código en `pipeline/` que calcule `origen` para registros base6 (el único cómputo de `origen` encontrado, en `normalizar_marc_recovered.py:351`, solo aplica a registros MARC). El valor de `origen` para base6 viene heredado sin modificación desde la extracción original — no fue introducido por este pipeline.
- El `plantel_estandarizado` de esas filas corresponde a instituciones privadas reales y reconocibles: Universidad Don Vasco, Universidad de Sotavento, Universidad Latina, Universidad Villa Rica, Universidad Iberoamericana, Universidad Lasallista Benavente, entre otras — el patrón clásico de **"escuelas incorporadas"** del sistema educativo mexicano: instituciones privadas autorizadas por la UNAM para otorgar títulos validados por ella, aunque el estudiante haya cursado en la escuela privada.

## Conclusión

`origen` (clasificación institucional: externa/incorporada) y `universidad_nota` (autoridad que otorga/valida el título: UNAM) capturan dos hechos **distintos y compatibles**, no contradictorios, para el caso de escuelas incorporadas. No es un error de captura ni un bug introducido por el pipeline.

## Decisión

No se modifica ningún dato. Coincide con el alcance del proyecto: limpiar solo lo que el producto necesita, no cada registro del dataset. Se documenta para que esta combinación no se vuelva a marcar como "contradicción" en una auditoría futura.
