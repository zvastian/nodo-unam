# ADR-0014: Vecindario semántico 100% precomputado — reemplaza el modelo híbrido de ADR-0003

- **Estado**: Aceptado (2026-09-22). **Reemplaza a [ADR-0003](0003-hibrido-precompute-on-demand.md)**, que queda como archivo histórico del debate (no se edita, por convención del proyecto).

## Contexto

ADR-0003 decidió un modelo híbrido para el vecindario semántico: precómputo solo para las ~50,000 tesis de la muestra del atlas viejo, y cómputo **en vivo** (embeber + buscar contra el índice completo) para cualquier tesis fuera de esa muestra o para un texto libre. La justificación explícita era que "precomputar vecindarios para las 609k excede el volumen razonable de precómputo".

Esa premisa nunca se verificó con números reales, y dos cosas cambiaron desde que se escribió:

1. **El atlas ya no vive sobre una muestra de 50k** — la Fase Explorar de esta semana reconstruyó todo sobre el corpus completo (609,154 tesis, HDBSCAN + Ward + e5-large). La distinción "dentro/fuera de la muestra" que motivaba el modelo híbrido ya no existe — todas las tesis del atlas están en el mismo corpus completo.
2. **El volumen real es mucho menor de lo que ADR-0003 asumía.** Precomputar top-K=100 vecinos por tesis (mismo `top_k` que usaba el endpoint viejo) para las 609,154 tesis pesa: `609,154 × 100 × (4 bytes id + 2 bytes similitud float16)` ≈ 365 MB sin comprimir, probablemente ~150 MB en parquet. Esto **no excede** el volumen que el propio [ADR-0001](0001-arquitectura-datos-produccion.md) ya aceptó como normal para R2 ("cientos de MB–unidades de GB", "sin límite práctico de objetos") — contradice directamente la premisa de ADR-0003. El cálculo en sí (equivalente a una búsqueda de vecinos más cercanos sobre 609,154 × 1024 embeddings) es del mismo orden de magnitud que pasos ya corridos en Kaggle esta semana (UMAP, HDBSCAN) — minutos con GPU, no una corrida inviable.

## Decisión

**El vecindario de cualquier tesis que ya está en el corpus (las 609,154) es 100% precomputado. No hay cómputo en vivo para este caso, nunca.**

- Se calcula una sola vez (offline, vía FAISS sobre los embeddings e5-large ya generados) una tabla de top-K vecinos por tesis (`thesis_id` → K vecinos + similitud), igual que ya se hizo para "Nobel más cercano" (`thesis_nobel_nearest.parquet`, mismo patrón de precómputo).
- Se sube a R2 como dato estático (mismo tratamiento que el resto de `atlas_data/`), servido por `thesis_id` bajo demanda desde el frontend (lazy, un fetch por tesis visitada — mismo patrón ya usado para `theses_by_micro/*.json`).
- FAISS **nunca se despliega como servicio**. Es una herramienta de build, corre en Kaggle o local una vez por regeneración del pipeline, igual que HDBSCAN/UMAP/PaCMAP.

**El caso que sí necesita cómputo en vivo es distinto y no es "vecindario del atlas":** un usuario que pega un texto libre que no está en el corpus (flujo de Laboratorio, `scripts/main.py` + `analyze()`, ya existente). Ese caso sigue necesitando embeber la consulta y buscar contra el índice en el momento — pero es un backend y un problema de producto aparte, con su propio gating de auth/cuota pendiente (ver Fase 3a en `development.md`), no algo que este ADR resuelva.

## Consecuencias

- (+) Sin la ambigüedad de "esta respuesta es instantánea vs. dispara cómputo en vivo" que ADR-0003 exigía comunicar en la UI — todo lo que el atlas muestra es siempre precomputado, siempre instantáneo.
- (+) Sin superficie de ataque de cómputo-por-request para el vecindario del atlas — el bug ya documentado en producción (`/api/explore/neighborhood/{id}` exponiendo detalles de FastAPI/uvicorn) deja de aplicar a este caso porque el endpoint deja de existir para tesis del corpus.
- (+) Consistente con el resto de la Fase Explorar de esta semana (Nobel más cercano, tesis representativas por micro-cluster): mismo patrón de precómputo + R2, nada nuevo que aprender operativamente.
- (-) Si en el futuro se agregan tesis al corpus (nueva cosecha anual), el vecindario de las tesis viejas no se actualiza solo — hay que re-correr el precómputo completo (o al menos recalcular contra las nuevas). Aceptado: el corpus no cambia con frecuencia (ver diagnóstico de madurez MLOps de la Fase -1, Nivel 0-1 aceptado conscientemente).
- (-) No resuelve "busca tu propio tema libremente" — ese caso sigue pendiente de su propio tratamiento de auth/cuota, sin cambios respecto a lo ya anotado en Fase 3a.

## Pendiente de esta decisión, no bloqueante para aceptarla

- Verificar *hubness* en el resultado real (mismo problema encontrado con Nobel: candidatos "genéricos" que acaparan el top-1 de una fracción desproporcionada de consultas) — a diferencia del caso Nobel, aquí es intra-corpus, mismo idioma, así que podría ser menos severo, pero se mide, no se asume.
- Revisar el efecto de los ~7,449 títulos duplicados/casi-duplicados ya documentados (ADR de limpieza de columnas, `development.md`) sobre el vecindario — una tesis con título idéntico a otras 291 (ej. "notas al programa") tendría un vecindario trivial y no útil si esos duplicados dominan su top-K.
- Elegir K final (100 sigue el precedente del endpoint viejo, pero no está reevaluado contra el tamaño real de payload que quiere el frontend).
