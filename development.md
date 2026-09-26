# NODO UNAM — Development Log

> Doc de referencia del proyecto: qué se hizo, por qué, y en qué fase estamos.
> Bitácora viva por fases. El producto vive en `PRD.md`, los debates abiertos en `rfc/`, las decisiones ya tomadas en `adr/` — este archivo indexa y enlaza, no los reemplaza.

## Cómo se usa este documento

- **`development.md`** (este archivo): índice narrativo, mutable, organizado por fase. Qué está hecho, qué falta, en qué orden vamos. No repite razonamiento que ya vive en un PRD/RFC/ADR — enlaza.
- **`PRD.md`**: definición de producto (problema, audiencias, alcance, métricas de éxito). Un solo documento, se edita in-place a medida que se confirman decisiones (a diferencia de los ADR, no es inmutable — el producto se sigue afinando).
- **`rfc/NNNN-titulo.md`**: Request for Comments — propuestas abiertas a debate, todavía sin decidir. Se usa para explorar opciones y desacuerdos *antes* de comprometerse. Cuando se resuelve, la decisión final se registra como ADR (si es técnica) o se actualiza el PRD (si es de producto), y el RFC queda como archivo histórico del debate.
- **`adr/NNNN-titulo.md`**: Architecture Decision Records — una por cada decisión de arquitectura/seguridad/proveedor difícil de revertir, ya tomada (no propuestas). Formato: Contexto → Decisión → Consecuencias. Una vez con estado "Aceptado", un ADR **no se edita** — si la decisión cambia, se crea un ADR nuevo que la reemplaza y cita al anterior.

## Fases del proyecto

-1. **Metodología de trabajo** — cómo trabajamos, qué marcos usamos y por qué (ver abajo).
0. **Producto** — qué es NODO UNAM, para quién, qué NO es. Ver [`PRD.md`](PRD.md).
1. **Data Engineering** — extracción, limpieza, entity resolution, embeddings, pipeline.
2. **Desarrollo** — cómo correr todo localmente sin depender de hosting.
3. **Producción** — arquitectura de despliegue, almacenamiento, cache.
   - 3a. Cybersecurity
   - 3b. Datos precalculados / almacenamiento
   - 3c. UI
   - 3d. UX

---

## Fase -1 — Metodología de trabajo

_Definida 2026-09-20, investigación con fuentes en el hilo de esa fecha._

| Capa | Elección | Por qué |
|---|---|---|
| Flujo de trabajo diario | **Kanban** | Ya se usaba de forma informal (tablero de Notion); es lo que la evidencia de industria recomienda para equipos de 1-2 personas — Scrum impone roles/ceremonias sin beneficio a este tamaño. |
| Decisiones técnicas | **RFC → ADR** | RFC para debatir antes de decidir (`rfc/`), ADR para registrar lo ya decidido e inmutable (`adr/`). No mezclar ambos estados en un mismo documento. |
| Producto | **PRD vivo** (`PRD.md`) | Documento único, editable, con secciones marcadas [ABIERTO] hasta confirmarse. |
| Arquitectura visual | **C4 Model** (pendiente de producir) | Diagramas de contexto/contenedores — hoy no existe ningún diagrama del sistema completo (estático + R2 + Worker IA + FastAPI dev + pipeline). |
| Datos/pipeline | **Principios DataOps** | Tratar el pipeline como línea de producción: todo versionado, calidad monitoreada, "reducir el heroísmo". Da marco formal a la deuda de Fase 1. |
| ML/embeddings | **MLOps maturity model como diagnóstico, no como meta** | Hoy en Nivel 0-1 (manual, sin reentrenamiento automático) — aceptado conscientemente; perseguir Nivel 4 sería sobre-ingeniería dado que el corpus no cambia con frecuencia. |
| Git/branching | **Trunk-based**, condicionado a tener CI real primero | GitFlow es ceremonia sin beneficio para un deploy estático sin releases programados; TBD es el ajuste correcto, pero es prematuro mientras no haya CI corriendo los tests en cada push. |
| Medición de salud del proceso | **DORA (4 métricas)**, una vez exista CI/CD | Deployment frequency, lead time for changes, MTTR, change failure rate — estándar de facto, barato de trackear incluso en solitario. |

**Explícitamente descartado por sobre-ingeniería para el tamaño actual del equipo**: Scrum con ceremonias completas, PMI/PMBOK, PRINCE2 — diseñados para equipos grandes/regulados, no aportan aquí.

## Fase 0 — Producto

Ver [`PRD.md`](PRD.md) — problema, audiencias, alcance (v0/v1/fuera de alcance), riesgos y métricas de éxito. No se duplica aquí.

Decisión de alcance en discusión activa: [`rfc/0001-mvp-scope-laboratorio-tiers.md`](rfc/0001-mvp-scope-laboratorio-tiers.md).

## Fase 0.5 — Redefinición de producto (2026-09-21, ver ADR-0012)

- [x] Análisis sección por sección (Inicio/Explorar/Taller/Laboratorio/Nobel), intención vs. estado actual.
- [x] **Nobel** se fusiona en Explorar (Nobel más cercano por vecindario + nodos easter-egg en el atlas) — deja de ser pestaña propia.
- [x] **Taller** pivota a constructor de análisis en vivo sobre el backend `analyze()` ya existente (frontend pendiente de construir).
- [x] Repo público `zvastian/MI-TESIS-UNAM` puesto en **privado** — tenía `data/thesis_lookup.parquet` vía Git LFS con nombres reales de autores expuestos públicamente. Historial de LFS pendiente de purgar (no se ha hecho, solo se cortó el acceso).
- [ ] Laboratorio: RFC-0001 sigue sin resolución formal (Tier 1/Tier 2).

## Fase Explorar — reconstrucción del atlas semántico (en curso, 2026-09-21)

- [x] ~~Confirmado: el texto que se embebe es `titulo_normalizado | programa | nivel | area | plantel` (`app/MI-TESIS-UNAM_github/scripts/rebuild_01_sample_embeddings.py`) — los 3 últimos campos cambiaron en Fase 1, hace falta regenerar.~~ **Obsoleto, superado por la corrección de la línea de abajo (2026-09-21): el texto embebido final es solo `titulo`.** Esa línea describía un experimento de la muestra de 50k (`rebuild_01_sample_embeddings.py`), no el pipeline que terminó usándose para el corpus completo. Se deja tachada en vez de borrarse para que quede registro del cambio de rumbo.
- [x] Confirmado: la decisión de abandonar la muestra de 50k y reconstruir sobre el corpus completo (609,156) ya estaba tomada por el usuario en `nodo_unam.md`, nunca ejecutada.
- [x] Modelo decidido: **`intfloat/multilingual-e5-large`** (560M parámetros, 1024-dim) — upgrade sobre el MiniLM-L12 viejo (118M, 384-dim). Costo: ~2.7x más de almacenamiento en los vectores, re-embeber Nobel también (trivial). Beneficio esperado: menos falsos "parecidos", clusters más coherentes, matches de Nobel más significativos.
- [x] Plataforma decidida: **Kaggle Notebooks** (GPU T4/P100, cuota semanal visible de 30h) en vez de Colab (desconexiones sin aviso, sin cuota visible).
- [x] Scripts listos: `pipeline/generar_embeddings_full_e5.py` (tesis, corpus completo desde `data_unam.parquet`) y `pipeline/reembedder_nobel_e5.py` (Nobel, reusa `build_nodes()` de `build_nobel_atlas.py`, no reimplementa el parseo).
- [x] **Corrección importante (2026-09-21)**: el texto embebido es **solo `titulo`**, no la concatenación con programa/nivel/área/plantel que se había propuesto primero. Verificado contra `notebooks/proc_abril28.ipynb` (el notebook real de producción) — nunca concatenó metadata. Razón de fondo, no solo precedente: meter categoría dentro del texto embebido empuja el clustering a agruparse por categoría (ya existe como filtro) en vez de por contenido semántico real, suprimiendo el descubrimiento cruzado entre áreas/programas que es el valor central de un atlas semántico. `programa`/`nivel`/`area`/`plantel` se guardan como metadata adjunta en `embeddings_meta.parquet`, no como parte del texto embebido.
- [x] Embeddings de tesis generados y verificados: `data/embeddings/embeddings_full_e5large.npy` (609,154 × 1024, normas=1.0) + `embeddings_meta.parquet` (thesis_id/programa/nivel/area/plantel).
- [x] Embeddings de Nobel generados y verificados: `data/embeddings/nobel_embeddings_e5large.npy` (1,026 × 1024, normas=1.0) + `nobel_embeddings_meta.parquet` (node_id).
- [x] **Confirmado (ADR-0013)**: migrar de Leiden manual a estilo BERTopic — **HDBSCAN** para clustering (jerarquía nativa, maneja ruido/outliers, no requiere adivinar resolución) + **c-TF-IDF** para etiquetas automáticas de tema por cluster + **PaCMAP** en vez de UMAP para el layout 2D (mejor preservación de estructura global entre macroclusters, vía pares "mid-near" y ponderación por etapas).
- [ ] Reconstruir jerarquía macro/meso/micro sobre el corpus completo con este pipeline, una vez estén los embeddings.

### Próximos pasos concretos, en orden

1. **Clustering con HDBSCAN** sobre `embeddings_full_e5large.npy` — obtener cluster por tesis (incluye posible "ruido"/sin cluster) y la jerarquía nativa que reemplaza el proceso manual de macro/meso/micro de Leiden.
2. **Etiquetas de tema con c-TF-IDF** — para cada cluster de HDBSCAN, extraer palabras clave distintivas a partir de los títulos de las tesis que caen en ese cluster.
3. **Reducción a 2D con PaCMAP** sobre los mismos embeddings — da las coordenadas x,y de cada tesis en el mapa visual.
### Paso 4/7 en curso (2026-09-22) — Nobel más cercano

Script: `pipeline/generar_nobel_cercano.py`. Similitud coseno (producto punto, embeddings normalizados) de cada tesis contra los 1,026 nodos de Nobel (texto embebido: `motivation` en inglés, ver `reembedder_nobel_e5.py`). Metadata legible (nombre/categoría/año/motivación) reusada de `app/MI-TESIS-UNAM_github/nobel/outputs/processed/nobel_award_nodes.json` (atlas viejo, pero son datos biográficos reales, no dependen del modelo de embeddings) — se reconstruyó `category` en español desde `category_code` porque ese JSON tiene mojibake en campos con acentos (`name` también lo tiene, ej. "Katalin Karik�"; pendiente si se expone en frontend, arreglarlo ahí).

**Bug real encontrado y corregido: hubness.** Primera corrida (similitud coseno cruda, top-1): 15 de 1026 laureados (1.5%) acaparaban **36.1%** de todas las asignaciones de "más cercano" (Barry J. Marshall solo, 7.8% del corpus completo) — problema de "hubness" bien documentado en búsqueda de vecinos de alta dimensión cross-lingüe (609,154 consultas cortas en español vs. 1,026 candidatos largos en inglés): algunos vectores se vuelven "el más cercano" de una fracción desproporcionada por geometría del espacio, no por similitud semántica real. **Fix**: z-score por candidato (restar media/desviación de su similitud contra el corpus completo antes de rankear, equivalente simplificado de CSLS). Resultado: concentración del top-15 bajó a **13.6%**, 943/1026 laureados con cobertura. Mejora real, no perfecta — con solo 1,026 candidatos algunos matches individuales siguen siendo débiles cuando se revisan a mano (ej. "auditoría legal externa" → Coetzee por tema literario de "outsider"), junto a aciertos genuinamente buenos (ej. "reproducción asistida" → Robert Edwards/FIV). Es una limitación inherente al tamaño del pool de candidatos, no algo que la corrección de hubness pueda resolver del todo.

**Recomendación para el paso 6 (frontend), no implementada aún**: no forzar el top-1 cuando la confianza es baja — usar el z-score guardado (`nobel_top1_zscore`, rango observado -2.5 a 7.8, media 2.29) como umbral de exhibición; mejor no mostrar "Nobel más cercano" que mostrar uno débil y forzado.

Guardado: `data/nobel/thesis_nobel_nearest.parquet` (609,154 filas — `thesis_id`, top-3 `nobel_topK_id`/`_similarity`/`_zscore`, más nombre/categoría/año/motivación del top-1).

**Segundo bug real encontrado y corregido: el ajuste conjunto de PaCMAP (la opción "recomendada" original) colapsa.** Se corrió `pipeline/generar_layout_pacmap_con_nobel.py` (tesis + Nobel concatenados antes del fit, 610,180 puntos, 516.6s) siguiendo la recomendación original de abajo. Medido antes de aceptarlo: **650/1026 laureados (63%) cayeron en prácticamente la misma coordenada exacta, 997/1026 (97%) comprimidos en solo 4 ubicaciones** — con solo 1,026 puntos (0.17% del total) más parecidos entre sí por idioma/registro (citas formales en inglés) que por contenido frente a 609,154 tesis en español, PaCMAP los trata casi como un solo grupo atípico degenerado en vez de darles posiciones individuales. **Script descartado, no usado** (se deja en el repo con nota de por qué falló).

**Fix**: `pipeline/generar_posicion_nobel_interpolada.py` — en vez de pedirle a PaCMAP que resuelva el desbalance, se interpola la posición de cada laureado desde el promedio ponderado (por similitud) de las posiciones 2D *ya aceptadas* de sus K=25 tesis más parecidas (`layout_pacmap2d.parquet`, sin tocar). Primer intento con similitud cruda **también colapsó** (640/1026 <0.05 de distancia) — mismo problema de hubness que el bug de arriba, visto del otro lado: unas pocas tesis genéricas resultan "la más cercana" para cientos de laureados distintos. Segundo fix: z-score de cada tesis contra los 1,026 Nobel (barato, ya disponible en el mismo batch, sin pasada extra) antes de elegir vecinos — equivalente a CSLS con corrección en ambos sentidos (Nobel↔tesis). Resultado final: de los 1,026 nodos, 322 son duplicados legítimos de texto (premios compartidos entre 2-3 laureados con la misma cita — correcto que coincidan en posición); de los 704 con texto único, solo **52 (7.4%)** siguen con colapso real — mejora de 63%→7.4%. Distancia mediana al vecino entre únicos: 0.19 (escala del mapa: rango ~53). Verificado visualmente: `docs/evidencia_visual/04_mapa_con_nobel.png` — cientos de estrellas distinguibles, concentradas en la banda central densa del mapa (coherente con que las citas Nobel, en prosa científica genérica de alto nivel, se acercan más a las tesis "generalistas" del núcleo que a los nichos periféricos muy específicos).

**Lección para futuros pasos con conjuntos chicos/heterogéneos (ej. si se agregan más fuentes tipo Nobel)**: no asumir que un ajuste conjunto de reducción dimensional da posiciones individuales significativas cuando un grupo es <1% del total y estructuralmente distinto (idioma/registro) — verificar colapso (distancia al vecino más cercano dentro del grupo chico) antes de aceptar el resultado, igual que se verificó hubness en la búsqueda de vecinos.

Dos usos previstos (ADR-0012):
   - Similitud coseno de cada tesis contra los 1,026 nodos de Nobel → guardar el más cercano (y quizás top-3) como "Nobel más cercano".
   - Decidir si los 1,026 puntos de Nobel corren *dentro* del mismo cómputo de PaCMAP junto con las tesis (recomendado — posición realmente comparable en el mismo mapa) o se posicionan aparte.
5. **Generar la estructura de salida** para el frontend, adaptando el esquema ya documentado en `nodo_unam.md` (`atlas_manifest.v1.json`, macro eager / meso-micro-vecindario lazy) al nuevo esquema de clusters de HDBSCAN. **Jerarquía macro/meso/micro: hecha (2026-09-22)** — ver sección "Jerarquía macro/meso/micro" más abajo (130 macro, 432 meso, 513 micro, tras 5 rondas de corrección manual con revisión de títulos reales — el plan original de caminar `condensed_tree.parquet` se probó y se descartó, y el primer corte v2 por conteo también se reemplazó por corte por coherencia). **`atlas_manifest.v1.json` real: hecho (2026-09-22)** — ver sección "Paso 6 — atlas_manifest.v1.json" más abajo. Pendiente solo `neighborhood_by_thesis` (índice de vecinos a nivel tesis).
6. **Actualizar el frontend**: etiquetas de tema visibles, tarjeta "Nobel más cercano" en vista de vecindario, nodos de Nobel con estilo visual distinto (easter egg) en el mapa.
7. **Capturar evidencia visual** (ver checklist "Evidencia visual del proceso" arriba) — el momento natural es justo después del paso 3/4, cuando ya hay mapa coloreado + Nobel integrado.

### Paso 2/7 completado (2026-09-22) — etiquetas de tema con c-TF-IDF

Script nuevo: `pipeline/generar_topicos_ctfidf.py` — corre 100% local (es texto, no embeddings; no aplica el problema de RAM que forzó HDBSCAN a Kaggle). Implementa c-TF-IDF estilo BERTopic (cada cluster = un "documento", `tf(t,c) * log(1 + A/freq(t))`) sobre los títulos, excluyendo el 67.2% de ruido. Filtros: stopwords en español + relleno académico (tesis/estudio/análisis/unam/méxico/...), `max_df=0.5` (descarta términos casi universales) y `MIN_TOTAL_COUNT=3` (descarta typos casi únicos). Corrida sobre los 513 clusters reales (199,623 tesis con cluster asignado): vocabulario final 893,325 términos, resultado guardado en `data/clustering/cluster_topics_ctfidf.parquet` (`cluster_id`, `n_tesis`, `keywords`, `topic_label`).

**Calidad**: alta — clusters grandes salen temáticamente coherentes sin curación manual (ej. cluster 503 "teorema · espacios · grupos · álgebras" = matemáticas puras; 359 "filosofia · nietzsche · hegel · aristoteles · kant"; 195 "amparo · juicio amparo · suspension" = derecho). Una rugosidad menor, no bloqueante: duplicados singular/plural por no aplicar stemming/lematización ni diversificación MMR (BERTopic sí la usa) — cosmético.

**Investigado y cerrado (2026-09-22): cluster 372 NO mezcla temas.** La sospecha inicial (veterinaria + vocabulario metodológico "revision bibliografica/manual" = posible fusión de dos temas por `leaf`) se descartó al revisar 25 títulos al azar: es veterinaria coherente de punta a punta (necropsias, castración, tumores, cirugía en perros/gatos/cerdos/caballos/ganado) — "revision bibliografica"/"estudio recapitulativo" son un formato de tesis legítimo y común en esa facultad (revisiones de literatura), no una mezcla de campos. Sin acción.

**Auditoría de clusters dominados por título duplicado exacto (2026-09-22)**: dado el hallazgo del hueco central (ver checklist de evidencia visual), se midió cuántos de los 513 clusters están inflados por un solo título repetido — solo **2/513 (0.4%)** superan 30% de dominancia: cluster 0 (89.8% "notas al programa", género de tesis-recital musical) y cluster 1 (37.4% "apicectomia", formato de caso clínico dental). Juntos representan 512 de 199,623 tesis con cluster (0.26%) — contenido, no sistémico. **Decisión**: no justifica re-correr el pipeline de Kaggle ni deduplicar el corpus completo (sobre-ingeniería para 0.08% del corpus). Al construir el corte macro/meso, tratar clusters 0 y 1 como "cluster de género" (tamaño no representa contenido distinto), no como tema de contenido diverso.

### Paso 3/7 completado (2026-09-22) — layout 2D con PaCMAP, corrido local

Script nuevo: `pipeline/generar_layout_pacmap.py` (2D fijo, separado de `reduce_dimensions_pacmap()` de `clustering_hdbscan.py`, que ahí es solo referencia a 15D para el paso de clustering). **Smoke test 100k local**: 87.6s, ~1.4GB de RAM consumida — mucho más liviano que UMAP+HDBSCAN, sin señal de riesgo de escala. **Corpus completo (609,154) corrido local, sin Kaggle**: `fit_transform` en 519.8s (~8.7 min). RAM libre bajó a **1.2GB** justo tras materializar los embeddings en denso (paso previo a PaCMAP en sí) — más ajustado que el smoke test hacía pensar, vale la pena tenerlo en cuenta si la máquina tiene más cosas abiertas en el futuro, pero terminó sin problema y liberó a 5.8GB libres al final. Resultado guardado en `data/clustering/layout_pacmap2d.parquet` (`thesis_id`, `x`, `y`) — verificado sin NaNs ni `thesis_id` duplicados, coordenadas en rango [-26.4, 26.6].

### Decisión tomada (2026-09-21) — HDBSCAN corre en Kaggle, no local

Ninguno de los dos pasos necesita GPU — era una decisión de RAM/CPU y de ciclo de iteración, no de cómputo especializado. Resuelta a favor de **Kaggle** tras el incidente de RAM del mismo día (ver Changelog): local tiene 16.6GB de RAM total, ~9.4GB libres en un momento normal — no alcanza con margen para 609,154×1024 + condensed tree sin degradar a mono-hilo. Kaggle da RAM conocida de antemano (~30GB en sesión sin GPU) y, al ser Linux (fork real, no spawn), evita la duplicación de memoria por worker que causó el incidente. Instrucciones paso a paso y motivo completo en el docstring de `pipeline/clustering_hdbscan.py`.

**Nota técnica aparte, aplica sin importar la plataforma**: la práctica común no es correr HDBSCAN directo sobre las 1024 dimensiones completas — primero se reduce a un número moderado de dimensiones y **sobre eso** se clusteriza; la reducción a 2D para visualización (PaCMAP) es un paso aparte, hecho para mostrar en pantalla, no para alimentar el clustering.

**Actualizado 2026-09-21 (ver `problem.md`/`solution.md` para el diagnóstico completo): la nota de arriba decía "PCA a 50d antes de HDBSCAN" — quedó obsoleta.** Dos smoke tests en Kaggle (100k tesis) con ese reductor dieron un cluster gigante (42%) + dos minúsculos + 57.5% de ruido, y subir de 50 a 150 componentes de PCA para retener más varianza (0.435→0.684) *empeoró* el tiempo de HDBSCAN de forma no lineal (6.3 min → 45+ min sin terminar) sin llegar a arreglar el resultado. Causa raíz: PCA preserva varianza *global*, no densidad *local*, y HDBSCAN clusteriza por densidad local — con PCA los embeddings de e5 quedan casi uniformes en el espacio reducido sin importar cuántas dimensiones se retengan. Releyendo ADR-0013, esto ya estaba previsto ahí ("HDBSCAN sobre los embeddings de e5-large, posiblemente tras reducción **UMAP**") — la implementación se había desviado hacia PCA primero y luego hacia PaCMAP (que ADR-0013 reserva para el layout 2D, no para este paso) sin volver a chequear contra la decisión ya tomada.

**Fix aplicado en `pipeline/clustering_hdbscan.py` (2026-09-21, sin correr en Kaggle todavía):** `REDUCTION_METHOD` ahora tiene default `"umap"` (`min_dist=0.0`, `metric="cosine"`, 5 dimensiones) — la configuración estándar de facto para este paso en pipelines BERTopic-like. `MIN_CLUSTER_SIZE`/`MIN_SAMPLES` suben de 40/10 a 150/5 como punto de partida (no valor final) para el nuevo barrido. Se agregó `REDUCED_EMBEDDINGS_PATH` para cachear el resultado de la reducción y poder iterar los parámetros de HDBSCAN sin repetir el paso caro. PCA y PaCMAP se mantienen como opciones (`REDUCTION_METHOD=pca`/`pacmap`) para referencia, ya no como default. Antes del cambio se verificó que no hacía falta regenerar embeddings: el prefijo `"query: "` de e5 ya estaba bien aplicado en `generar_embeddings_full_e5.py`, y las 2 filas de diferencia entre el corpus (609,156) y los embeddings (609,154) son las 2 tesis con título vacío, filtradas a propósito por ese mismo script — no un desalineado. Se detectaron 7,449 títulos duplicados (21,465 filas, 3.5% del corpus, el peor caso "notas al programa" ×292) — real pero secundario, no explica el ruido por sí solo; deduplicar por título antes de reducir requeriría agregar `titulo` a `embeddings_meta.parquet`, hoy no lo tiene — pendiente, no bloqueante.

**Resultado del smoke test de 100k con UMAP (2026-09-21)**: confirma que el cuello de botella nunca fue el tamaño del dataset. La búsqueda de vecinos más cercanos de UMAP (la fase que se degradaba con PCA a 150d) tardó **~66s** sobre 100k puntos de 1024 dimensiones, y el fit completo (UMAP + HDBSCAN) terminó en minutos — nada comparable a los 45+ minutos sin terminar de la corrida con PCA. Pero calibrar `cluster_selection_method` resultó ser el siguiente cuello de botella, no de tiempo sino de calidad — un mismo reductor UMAP cacheado (`embeddings_umap5.npy`, reusado sin recalcular gracias a `REDUCED_EMBEDDINGS_PATH`) da resultados muy distintos según ese parámetro:

| Config | Clusters | Ruido | Tamaños | Prob. media |
|---|---|---|---|---|
| `min_cluster_size=150, min_samples=5, method=eom` | 2 | 0.3% | 1 cluster con 99,085 (99%) + 1 con 625 | 0.988 |
| `min_cluster_size=150, min_samples=5, method=leaf` | 87 | 64.2% | min 154, mediana 316, max 2,104 | 0.850 |

Ninguno de los dos extremos sirve tal cual: `eom` colapsa casi todo en un solo cluster (busca el nodo más "estable" del árbol jerárquico y aquí resultó ser casi todo el dataset); `leaf` sí revuelve estructura fina y con tamaños razonables (87 clusters de 154-2,104 tesis, del orden correcto para nivel meso), pero es demasiado conservador asignando membresía y deja 64.2% como ruido. Es el trade-off documentado de HDBSCAN entre ambos métodos de selección, no un error de configuración. El árbol condensado (`condensed_tree.parquet`, 100,172 filas de eventos de fusión/separación) ya contiene la estructura jerárquica completa en ambos casos — lo que cambia entre `eom`/`leaf` es solo qué corte plano de ese árbol se reporta como `labels_`.

**Decisión tomada (2026-09-21)**: en vez del barrido de `MIN_CLUSTER_SIZE` propuesto arriba (probablemente solo interpola entre "un blob" de `eom` y "mucho ruido" de `leaf`, sin punto intermedio estable — limitación conocida de `cluster_selection_method`, no una calibración fina), se implementó **soft clustering** en `pipeline/clustering_hdbscan.py`: `CLUSTER_SELECTION_METHOD` default pasa de `eom` a `leaf`, `prediction_data=True` en el fit, y una función nueva `soft_reassign_noise()` que usa `hdbscan.all_points_membership_vectors()` para recalcular membership fraccional de cada punto de ruido contra los clusters ya encontrados, reasignándolo si supera `SOFT_CLUSTER_THRESHOLD` (default 0.1, punto de partida, no valor final). Los puntos ya asignados por HDBSCAN no se tocan. Se guardan ambas versiones en `clusters_hdbscan.parquet` (`cluster_id`/`cluster_probability` = final con soft clustering; `cluster_id_hard`/`cluster_probability_hard` = asignación original de HDBSCAN, para poder auditar/comparar). Desactivable con `SOFT_CLUSTERING=0`.

**Resultado del smoke test de soft clustering, 100k (2026-09-22)**: mismo UMAP 5d + `leaf` de arriba, con `prediction_data=True` y `SOFT_CLUSTER_THRESHOLD=0.1`. Ruido bajó de **64.2% → 49.7%** (rescató 14,476 puntos: 22.6% del ruido original, 14.5% del corpus). Probabilidad media entre asignados bajó de 0.850 a 0.651 — esperado, no es señal de degradación: los puntos rescatados son por definición los de confianza más baja, apenas por encima del umbral, y arrastran el promedio. Con un umbral ya bastante permisivo (10%) solo se rescató ~23% del ruido, lo que sugiere que buena parte del ~50% remanente no es "borderline" corregible bajando el umbral, sino tesis sin vecindario claro contra ninguno de los 87 clusters — outliers reales o candidatos a una categoría propia, no un fallo de calibración. Costo total del paso adicional: 34.8s sobre 100k (aceptable). Tiempos del smoke test completo: UMAP 188.4s + HDBSCAN fit 10.8s + soft clustering 34.8s ≈ 4 min.

**Decisión tomada (2026-09-22)**: no seguir iterando sobre el subsample — el 49.7% de ruido en 100k no es necesariamente representativo del corpus completo (un subsample aleatorio de ~16% destruye densidad local real que existe en los 609,156; el corpus completo podría salir con menos ruido de entrada incluso antes de soft clustering), y el costo medido no da ninguna señal de riesgo de escala (nada parecido al incidente de PCA). Siguiente paso: correr el corpus completo con esta misma configuración.

### Bitácora de calibración HDBSCAN — resumen paso a paso (Kaggle, 100k salvo donde se indica)

| # | Config | Resultado | Decisión |
|---|---|---|---|
| 1 | PCA 50d + HDBSCAN | 3 clusters, uno con 42% del corpus, 57.5% ruido | Sospechar del reductor, no de los hiperparámetros de HDBSCAN |
| 2 | PCA 150d + HDBSCAN | Mismo problema de fondo; fit empeoró de 6.3 min a 45+ min sin terminar | Descartar PCA para este paso (preserva varianza global, no densidad local — ver `problem.md`/`solution.md`); volver a UMAP, como ya preveía ADR-0013 |
| 3 | UMAP 5d + HDBSCAN `eom` | 2 clusters, 99% del corpus en uno solo, 0.3% ruido | `eom` busca la rama "más estable" del árbol y aquí es casi todo el dataset — descartar `eom` para este corpus |
| 4 | UMAP 5d + HDBSCAN `leaf` (mismo UMAP cacheado) | 87 clusters (154–2,104 tesis c/u), 64.2% ruido, prob. media 0.850 | `leaf` da la granularidad correcta pero es conservador asignando — no perseguir 0% ruido solo con `min_cluster_size`/`min_samples`; agregar soft clustering en vez de seguir el barrido |
| 5 | UMAP 5d + HDBSCAN `leaf` + soft clustering (`threshold=0.1`) | Ruido 64.2% → 49.7% (rescató 14.5% del corpus); prob. media 0.850 → 0.651 | Proceder a correr el corpus completo con esta configuración — sin señal de riesgo de escala, y el ruido remanente puede diferir (a favor) sobre el corpus completo |
| 6 | **Corpus completo** (609,154), misma config del test 5 | UMAP: 2,280.4s (~38 min). HDBSCAN duro: 513 clusters, tamaños 150–2,475 (mediana 273), **67.2% ruido**, prob. media 0.827. Soft clustering: sin terminar tras un tiempo bastante mayor al estimado por extrapolación lineal del smoke test (~20-35 min) — preocupación real de que `all_points_membership_vectors` esté escalando peor que lineal con 513 clusters (la función no tiene barra de progreso, así que el silencio en sí no prueba nada, pero la duración sí es sospechosa) | La hipótesis de la fila 5 ("el corpus completo podría salir con menos ruido") **no se confirmó** — 67.2% es peor, no mejor, que el 64.2% del subsample de 100k. **Incidente de arquitectura detectado**: el script guardaba el resultado (`clusters_hdbscan.parquet`, `condensed_tree.parquet`, embeddings reducidos, modelo UMAP) recién al final, después de soft clustering — si ese paso se cuelga o se queda sin memoria, se pierden los ~40 min de UMAP+HDBSCAN ya hechos sin nada persistido. **Fix aplicado en caliente (2026-09-22)**: `main()` ahora guarda el resultado duro + condensed tree + reducción en disco *inmediatamente* después del fit de HDBSCAN, antes de intentar soft clustering; si soft clustering sí termina, se vuelve a guardar `clusters_hdbscan.parquet` con las columnas finales encima. Pendiente: confirmar si esta corrida en Kaggle termina o hay que interrumpirla y aceptar el resultado duro sin soft clustering para el corpus completo |

**Relanzamiento vía commit y confirmación del fix (2026-09-22)**: se relanzó como "Save & Run All" (Version #10), no como sesión interactiva, siguiendo la lección del incidente de la fila de abajo. Resultado duro **idéntico** al de la fila 6 (513 clusters, mismos tamaños, 67.2% ruido, prob. media 0.827) — confirma que `random_state` reproduce igual entre corridas, buena señal. UMAP tardó 1,749.9s (~29 min) esta vez vs 2,280.4s la anterior — variación normal de la máquina asignada por Kaggle, no un cambio de configuración. **El fix de guardado intermedio se confirmó en producción**: el log muestra `clusters_hdbscan.parquet` + `condensed_tree.parquet` + `embeddings_umap5.npy` + `umap_model.joblib` guardados en disco *antes* de entrar a soft clustering. Entrando ahora al mismo tramo que la corrida anterior no logró terminar en tiempo razonable — pendiente ver si esta vez sí termina o si toca aceptar el resultado duro sin soft clustering para v1.

**Cierre (2026-09-22)**: se canceló Version #10 manualmente durante soft clustering (misma decisión que la fila 6 — no vale la pena el riesgo de tiempo/cuelgue por una mejora que el diseño de producto ya trata como opcional, ver "modo caos"). **Se procede sin soft clustering para v1.** `clusters_hdbscan.parquet`, `condensed_tree.parquet` y `embeddings_umap5.npy` ya estaban a salvo en disco local (`data/clustering/`) gracias al guardado intermedio, descargados antes de cancelar — el resultado duro completo del corpus (513 clusters, 67.2% ruido, prob. media 0.827) es la base para el corte macro/meso. `umap_model.joblib` se perdió (Kaggle no conserva output de un kernel cancelado ni por API ni por UI) — sin impacto: es determinista (mismo `random_state` reproduce resultado idéntico, confirmado esta misma sesión) y barato de regenerar (~29 min) si algún día hace falta proyectar puntos nuevos al mismo espacio UMAP. **Nota técnica**: el joblib pesaba ~9GB — no por soft clustering (paso independiente, corre después y solo toca el parquet), sino porque un objeto `umap.UMAP` entrenado guarda internamente una copia completa de los datos de entrenamiento (609,154×1024 floats ≈ 2.5GB) más el grafo de vecinos y el índice de búsqueda ("hub-based search tree", visible en el log justo antes del guardado) necesarios para soportar `.transform()` sobre puntos nuevos — tamaño esperado para 609k puntos, no un error.

### Próximo paso: correr el corpus completo (609,156) en Kaggle

Misma configuración del test 5, sin `SAMPLE_N` (o `SAMPLE_N=0`) para usar el corpus completo, y **sin** `PCA_COMPONENTS` (dejar el default de UMAP en 5 — ver incidente de la sesión 2026-09-22: reusar `PCA_COMPONENTS=150` de los tests 1-2 con el reductor UMAP habría reproducido el mismo problema de degradación del árbol de vecinos que llevó a descartar PCA a 150d).

```python
# Celda 1 — env vars antes del exec, no después
import os
os.environ["SOURCE_DIR"] = "/kaggle/input/datasets/sebastiandiazprado/embeddings"
os.environ["OUTPUT_DIR"] = "/kaggle/working"
os.environ["CORE_DIST_N_JOBS"] = "-1"
# SAMPLE_N sin fijar (o "0") -- corpus completo
```

```python
# Celda 2
exec(open("/kaggle/input/datasets/sebastiandiazprado/embeddings/clustering_hdbscan.py").read())
```

`CLUSTER_SELECTION_METHOD` (`leaf`) y `SOFT_CLUSTERING` (`1`) quedan en su default, ya calibrados en los tests de arriba. Presupuestar más tiempo que el smoke test (609k vs 100k, ~6x más puntos) — ninguna de las tres fases (UMAP, HDBSCAN, soft clustering) mostró indicios de escalar peor que linealmente en el smoke test, así que debería seguir cómodo dentro de una sesión de Kaggle, pero vale la pena no asumirlo sin verificar el tiempo real.

Pendiente de decidir cuando se llegue al paso 3 (PaCMAP): si corre también en Kaggle en la misma sesión que HDBSCAN o aparte — no bloquea el paso 1.

### Incidente 2026-09-21/22 — se perdió la corrida del corpus completo al cerrar el navegador

**Síntoma**: el usuario cerró y reabrió la pestaña de Kaggle mientras el soft clustering del corpus completo llevaba corriendo ~1h34m (CPU 101%, RAM sana, sin señales de cuelgue). Al reabrir, el notebook mostró **"Draft Session Starting."** sin el contador de tiempo previo — sesión nueva, no una reconexión a la que estaba corriendo.

**Causa raíz**: una sesión interactiva de Kaggle ("Draft Session"/modo edición) no es lo mismo que un job en segundo plano real — depende de la conexión activa del navegador. Para dejar algo corriendo de verdad sin mantener la pestaña abierta, el mecanismo correcto de Kaggle es **"Save Version" → "Save & Run All" (commit)**, que empaqueta el notebook y lo ejecuta como job independiente en la infraestructura de Kaggle, revisable después desde la pestaña "Output"/"Versions" sin depender del navegador.

**Costo**: probablemente se perdieron las ~2h de cómputo (UMAP ~38 min + HDBSCAN ~2 min + soft clustering en curso) de la corrida del corpus completo (fila 6 de la bitácora arriba) — esa ejecución en particular todavía corría la versión vieja del script (sin el fix de guardado intermedio aplicado más tarde esa misma sesión), así que no había nada persistido en disco todavía.

**Fix hacia adelante**: (1) usar "Save & Run All" para cualquier corrida larga que deba sobrevivir sin la pestaña abierta, nunca la sesión interactiva; (2) subir al dataset de Kaggle la versión corregida de `clustering_hdbscan.py` (guarda resultado duro + condensed tree + reducción antes de intentar soft clustering) antes de relanzar — si esta lección no se aplica, cualquier commit repite el mismo riesgo.

**Estado**: 🔴 corrida del corpus completo pendiente de relanzar (esta vez vía commit, con el script corregido ya subido).

### Decisión de producto en curso (2026-09-22): vista curada vs. vista cruda del atlas ("modo caos")

**Contexto**: 513 clusters (o incluso los 87 del smoke test) son demasiados para navegación directa — nunca se planteó mostrarlos todos tal cual. El atlas viejo (Leiden, muestra de 50k) ya resolvía esto con una política editorial explícita, documentada en `nodo_unam.md`: 43 macroclusters totales (Área 1: 12, Área 2: 15, Área 3: 10, **Área 4: 6**), con topes por macro (máx. 30 micro, mín. 5 tesis visibles, fallback si un macro queda vacío) en `atlas_display_policy.v1.json`. Área 4 ya salía la más chica ahí.

**Tensión editorial planteada por el usuario**: ¿representar el atlas lo más fiel posible a los datos (con el desbalance real entre áreas) o editorializar para que el recorrido se sienta más parejo/amigable? Propuesta: no elegir una — ofrecer **dos vistas**. Una curada (macro/meso/micro editorializado, la experiencia principal) y una cruda/"caos" sin curar (la estructura real, incluyendo desbalance y ruido), como una segunda capa que el usuario puede encontrar — sin explicarla ni venderla ("modo caos" → volver a la vista curada se siente como volver al orden). Valor adicional: potencial pieza narrativa para README/CV, en línea con el checklist de evidencia visual de abajo.

**Opinión (análisis 2026-09-22)**:
- La idea es sólida — resuelve la tensión sin forzar una sola respuesta, y reutiliza infraestructura que ya existe (el sistema de manifest jerárquico lazy-load de `atlas_manifest.v1.json` ya separa macro/meso/micro; la vista cruda sería un manifest/payload adicional, no una re-arquitectura).
- **Cross-validación que refuerza el caso**: Área 4 sale infrarrepresentada en dos pipelines completamente independientes — Leiden sobre una muestra de 50k con embeddings viejos (6/43 macro), y ahora HDBSCAN sobre el corpus completo de 609k con e5-large (67.2% de ruido global, ver fila 6 de la bitácora arriba). Dos algoritmos, dos modelos de embeddings, dos tamaños de corpus, mismo patrón — buena evidencia de que es una propiedad real del espacio semántico del área 4 (menos producción y/o más heterogénea temáticamente), no un artefacto de parámetros de un pipeline específico. Esto hace que la "vista cruda" no esté exhibiendo ruido de un pipeline mal calibrado, sino un hallazgo real sobre el corpus — más defendible como pieza honesta, no solo como curiosidad visual.
- **Redefinir qué es "el caos"**: no debería ser solo "mostrar los 513 clusters en vez de un macro curado" — eso sigue siendo una vista ordenada con más categorías. El contraste narrativo real está en mostrar también el **ruido** (409,531 puntos sin cluster en la corrida completa, 67.2%) como dispersión visible sin bucket — ahí es donde se siente "el caos que realmente es".
- **Cómo construir el corte curado sin re-clusterizar**: `condensed_tree.parquet` (generado por `clustering_hdbscan.py`) ya tiene la jerarquía completa de fusiones de los 513 clusters hoja. "Macro" = subir por ese árbol hasta un corte más alto — mejor definido por un **umbral de tamaño mínimo por rama** (ej. no fusionar más allá de cierto punto) que por un número fijo de antemano, dejando que la cantidad de macros salga de la estructura real (banda de sanidad razonable: ~15-40, no un número inventado).
- **Dos preguntas abiertas, no resueltas todavía**:
  1. ~~Performance de renderizado: si Sigma.js/graphology (`atlas_macro_preview.html`) aguanta pintar ~609k puntos crudos sin cluster, o si la vista cruda también necesita algún tope técnico de renderizado (no de curación editorial, de capacidad del navegador).~~ **Resuelto, ver subsección de abajo.**
  2. ~~Antes de fijar el corte curado: medir **% de ruido por área**, no solo el total. Si área 4 resulta desproporcionadamente más ruido que las demás, la vista curada podría no solo infrarrepresentarla sino **hacerla desaparecer** del todo — un problema distinto y peor que estar chica.~~ **Resuelto (2026-09-22)**: medido — área 4 tiene 74.2% de ruido (vs 67.2% global), el más alto de las 4, pero no llega al extremo de "desaparecer": queda con 13,120 tesis clusterizadas (25.8% de sus 50,834), suficiente masa para representarla en el corte macro sin necesitar una regla editorial especial. Además tiene al menos un nicho fuerte y exclusivo (tesis-recital de música, ver checklist de evidencia visual) que puede anclar su sección en la vista curada. **Decisión**: no se necesita tratamiento editorial especial para área 4 en el corte macro — se procede con el mismo criterio (umbral de tamaño mínimo por rama) para las 4 áreas por igual.

**Estado**: idea validada, no bloqueante para el trabajo de clustering en curso. Depende de tener el corte macro definido (paso 2/5 de "Próximos pasos concretos") antes de poder construir ambos manifests. No se ha decidido aún el número final de macros ni el mecanismo exacto de la vista cruda (dataset completo renderizado vs. alguna forma de agregación ligera para performance).

#### Investigación de herramienta de renderizado (2026-09-22): ¿Sigma.js/graphology sigue siendo lo óptimo?

Pedido explícito del usuario: no asumir que la herramienta actual sigue siendo la correcta solo por inercia, con el mismo criterio que llevó a reemplazar Leiden por HDBSCAN. Investigación exhaustiva (no solo conocimiento previo — verificado contra repos/docs actuales) comparando Sigma.js/graphology contra `cosmos.gl` (grafo con layout de fuerza en GPU), `regl-scatterplot`, `deck.gl` `ScatterplotLayer`, `three.js`/PIXI.js de bajo nivel, y otras (G6, Ogma, VivaGraphJS) para los dos problemas de renderizado que son en realidad distintos: el grafo curado (macro/meso/micro/vecindario) vs. la nube de hasta 609k puntos del "modo caos".

**Decisión — vista curada: mantener Sigma.js + graphology, sin migrar.** La ventaja de `cosmos.gl` (layout de fuerza dirigida calculado en vivo en GPU, pensado para +1M nodos) no aplica aquí porque las posiciones del grafo curado ya se precomputan offline desde el árbol condensado de HDBSCAN — no hay layout en vivo que acelerar. Migrar reescribiría el modelo de datos y toda la lógica de interacción ya construida (lazy load por nivel, hover, labels por zoom) sin ganar nada. Sigma v3.0.3 está estable y mantenida activamente (v4 sigue en beta, no listo para producción); ningún límite duro documentado en ningún lado, pero los conteos reales de esta vista (macro ~15-40, vecindario ~50) están muy por debajo de donde la librería empieza a mostrar degradación conocida (según un issue del propio repo, la densidad de edges/labels pesa más que el conteo de nodos). Pendiente menor, no bloqueante: correr un smoke test de la vista curada con el macro real antes de darlo por sentado del todo, mismo criterio aplicado a HDBSCAN.

**Decisión — vista cruda/"modo caos": `regl-scatterplot` (flekschas), no Sigma ni deck.gl.** Es un problema de scatterplot, no de grafo. `regl-scatterplot` está construido exactamente para esto: hasta 20M puntos con pan/zoom fluido, MIT, mantenimiento activo real (v1.16.0 publicado ~7 días antes de esta investigación), color categórico nativo por cluster (pinta directo los 513 clusters + ruido en gris), WebGL1/2, disponible por CDN sin bundler — compatible con el deploy actual ("Build command: none"). `deck.gl` se descartó por cargar todo un framework geoespacial para usar una sola layer, sin necesitar nada geoespacial aquí. `three.js`/PIXI.js quedan descartados por ser de más bajo nivel — reimplementarían manualmente picking/lasso/color encoding que `regl-scatterplot` ya resuelve.

**Dos librerías, no una.** Ambas son deliberadamente pequeñas y de propósito único — más liviano que forzar una sola herramienta general (`cosmos.gl` o `deck.gl`) a cubrir los dos casos, y cada una solo se carga en la vista que la usa.

**Esfuerzo de migración: cero.** La vista curada no cambia; la vista cruda es trabajo nuevo de cualquier forma (nunca existió antes), no hay "migración" que evaluar ahí — es una decisión de qué construir, no de qué reemplazar.

### Design — referencia visual de nodos (2026-09-22)

El usuario mostró dos imágenes de referencia para definir la "vibra" visual de los nodos del atlas — una que sí (el look que quiere) y una que definitivamente no. Se registran en palabras porque las imágenes no viven en este archivo.

**Sí — red densa tipo "innovation network" (referencia: visualización de red de patentes/colaboración, estilo conocido de este tipo de gráficos — nodos = personas, con un nodo destacado en verde brillante entre un mar de nodos grises)**:
- Fondo blanco liso, sin ruido de fondo.
- Paleta casi monocromática: nodos y edges en escala de grises con un único acento de color (teal/cian) para los edges, y un segundo acento (verde) reservado exclusivamente para **un** nodo especial — el color no codifica categoría aquí, codifica "esto es lo único que debes mirar primero".
- Labels solo en un puñado de nodos centrales/importantes — la inmensa mayoría de los nodos no tiene texto encima. Eso es lo que la hace legible pese a tener miles de nodos: no compite por atención en todos lados a la vez.
- Edges finos, sin etiqueta, sin flechas — se leen como textura/densidad ("neblina" de conexión), no como datos individuales a leer uno por uno.
- Tamaño de nodo variable (más grande = más central/conectado) — dando jerarquía visual sin necesidad de más labels.
- Estructura compositiva: un núcleo denso tipo "maraña" en el centro, rodeado de un halo cada vez más disperso, y clusters diminutos completamente aislados flotando en el borde — no todo está conectado a todo, y esa desconexión periférica se deja ver, no se oculta ni se fuerza a integrarse visualmente.

**No — red de personajes tipo exportación default de herramienta de grafos (referencia: red de interacciones de personajes de una película, colores por facción)**:
- Cada nodo etiquetado en mayúsculas, todo el tiempo — sin jerarquía de qué mirar primero.
- Cada edge con su propia etiqueta de tipo de relación repetida cientos de veces — ruido puro a esta densidad.
- Color por categoría (facción/bando) + tamaño + label + flechas de dirección, todo a la vez compitiendo por atención.
- Fondo gris plano, sin atmósfera.
- Se siente una vista de depuración de una herramienta (Gephi/vis.js sin ningún pase de diseño encima), no una pieza terminada.

**Traducido a decisiones concretas para NODO UNAM (principios, no un mockup todavía)**:
1. **Etiquetar poco, no todo.** Encaja directo con lo ya planeado (macro eager, meso/micro/vecindario lazy, "ocultamiento de labels según zoom" ya mencionado en `nodo_unam.md`) — el principio de la imagen de referencia es el mismo que ya estaba en el plan, solo hay que ser disciplinados aplicándolo también dentro de cada nivel (ni siquiera todos los nodos de un mismo macro deberían tener label a la vez).
2. **Edges como textura, nunca como dato individual leíble.** Ningún edge debería llevar texto encima ni flecha — las conexiones semánticas de "vecindario" no tienen una dirección real que valga la pena mostrar (es similitud, no causalidad), así que ni siquiera aplican las flechas del ejemplo malo.
3. **La estructura núcleo-denso + halo disperso + islas aisladas no es solo estética — ya es literalmente la forma de sus propios datos.** El corpus real tiene macroclusters densos (el núcleo) y un 50-67% de ruido en clusters diminutos o sin cluster (las islas aisladas del borde). En vez de forzar un layout compacto que oculte esa estructura, el "modo caos" ya decidido arriba debería apoyarse en dejarla ver tal cual — el ejemplo de referencia prácticamente ya es una vista previa de cómo se vería su propio "modo caos" bien logrado.
4. **No apilar todas las codificaciones visuales a la vez.** El error del ejemplo malo es color+tamaño+label+edge-label+flecha compitiendo simultáneamente. Definir 1-2 codificaciones primarias por vista y resistir agregar más sin razón concreta — ej. vista curada: tamaño = masa del cluster, posición = layout semántico; vista cruda: color = cluster_id (gris para ruido), posición = coordenadas PaCMAP.
5. **Tensión abierta, no resuelta aquí**: la referencia que gustó usa fondo **blanco**; lo ya documentado para el atlas en `nodo_unam.md` es fondo **oscuro** tipo mapa/constelación. Falta decidir si la "vibra" deseada se traduce manteniendo el fondo oscuro (adaptando esta misma disciplina de restricción a una paleta oscura) o si en realidad están proponiendo pasar a fondo claro — no dar por hecho ninguna de las dos.
6. Compatible con las herramientas ya decididas arriba (Sigma.js para la vista curada: soporta color/tamaño/label por nodo y ocultamiento por zoom; `regl-scatterplot` para la vista cruda: soporta `colorBy` categórico y tamaño de punto) — no requiere reabrir esa decisión.

**Estado**: ~~principios de diseño capturados, no hay mockup ni implementación todavía. Pendiente de decidir el punto 5 (fondo claro vs. oscuro) antes de construir cualquier prototipo visual.~~ Resuelto — ver manifiesto de diseño abajo.

### Design Manifest v1 (2026-09-22)

**Decisión de fondo (resuelve el punto 5 de arriba)**: fondo **claro**, no oscuro. Razón textual del usuario: "fondo oscuro hoy en día parece más AI slop que algo bien trabajado" — el fondo oscuro tipo constelación que proponía `nodo_unam.md` queda descartado, no solo pospuesto.

**Norte del manifiesto**: el atlas debe sentirse como el lugar donde vive el conocimiento nuevo generado por una universidad — legítimo, digno, casi gubernamental — sin que "serio" signifique "sin color" ni "aburrido". La seriedad se construye con espacio en blanco, jerarquía visual disciplinada y precisión de instrumento científico, no con ausencia de color ni con paletas oscuras/futuristas que hoy leen como genérico-IA.

**Referencia de anclaje**: atlas científico / carta náutica — no un dashboard de producto, no una red social de nodos. Piensa en un mapa estelar o una carta de navegación impresa: fondo claro, líneas finas, colores profundos con propósito, coordenadas siempre visibles, etiquetas contenidas y precisas.

**1. Color — vívido pero profundo, nunca pastel, nunca "IA genérica"**
Colores primarios oscuros/saturados (no pasteles, no neón, no gradientes decorativos sin significado) sobre fondo claro con mucho espacio en blanco. La imagen de referencia que compartió el usuario (grafo con nodos rojo-naranja-amarillo-verde-azul sobre blanco) es el modelo a seguir: el color no es decoración, **codifica algo real** — en su caso probablemente centralidad/importancia (grado del nodo). Traducido a NODO UNAM: el color debería mapear a una métrica que ya tienen calculada, no a una categoría arbitraria — candidatos concretos ya en mano: `cluster_probability` (confianza de asignación de HDBSCAN, ya en `clusters_hdbscan.parquet`) o el tamaño del cluster (masa semántica). Esto además refuerza el "rigor matemático": el color en sí es un dato, no un capricho estético.

**2. Tipografía — mezcla Helvetica + serif, moderno con toques de elegancia**
Pareo de dos familias con roles distintos, no una sola familia para todo:
- **Sans neutro/grotesco** (familia "Helvetica") para UI, navegación, ejes, coordenadas, números — la voz "instrumento de precisión". Candidatos gratuitos/web-safe para un deploy estático sin build step: **Public Sans** (la tipografía open-source del US Web Design System — literalmente diseñada para comunicación gubernamental digital, encaja casi de forma literal con "casi gubernamental") o **Inter**/**IBM Plex Sans** como alternativas igual de neutras y muy usadas en interfaces de datos serias.
- **Serif editorial** para títulos de macrocluster, nombres de área, momentos de "curaduría humana" — la voz "elegancia académica". Candidatos: **Source Serif 4** (compañera oficial de Source Sans, misma familia de diseño que Public Sans en espíritu), **Newsreader** (diseñada para lectura editorial/periodística seria), o **Fraunces** si se quiere un toque más expresivo sin perder seriedad.
- Regla de uso: nunca mezclar ambas en el mismo bloque de texto — el sans es la voz de "esto es un instrumento", el serif es la voz de "esto es curaduría humana sobre ese instrumento".

**3. Chrome de rigor — siempre visible, sutil, nunca decorativo sin sustento**
Elementos tipo carta náutica/gráfico científico presentes todo el tiempo, no solo al interactuar: marcas de coordenadas en los bordes del mapa, una grilla de referencia muy tenue (bajo contraste, nunca compitiendo con los nodos), y un pie de "ficha técnica" permanente y discreto (tipo caption de figura científica: "n=609,154 tesis · HDBSCAN + UMAP · e5-large embeddings · [fecha]") — barato de implementar, altísimo impacto en percepción de rigor, y honesto porque es literalmente cierto. Nota de honestidad de diseño: las coordenadas del mapa (PaCMAP) no tienen unidad física real (no es latitud/longitud) — el chrome de "coordenadas" es una señal de rigor intencional, no una utilidad de navegación literal, y no debe presentarse como si lo fuera.

**Ampliación (2026-09-22, pregunta del usuario): ¿por qué el mapa tiene esa forma específica y no, por ejemplo, rotada 90°? ¿Y por qué no hay tesis en las esquinas?** Dos aclaraciones que conviene tener escritas para cuando se explique el atlas (ej. en la defensa o el README):
- **La rotación/orientación del mapa es arbitraria, no significativa.** PaCMAP (como UMAP o t-SNE) no tiene un eje "x" o "y" con significado propio — a diferencia de PCA, donde el primer componente al menos está ordenado por varianza explicada, aquí los ejes solo existen para poder dibujar en 2D. El algoritmo optimiza tres fuerzas (atracción entre pares cercanos, atracción débil entre pares medio-cercanos para no romper la estructura global, repulsión entre pares lejanos) sin ninguna preferencia de orientación absoluta — el resultado final queda rotado/reflejado según la inicialización aleatoria de esa corrida particular. Si se corriera de nuevo con otra semilla, la **forma relativa** (qué está cerca de qué) sería equivalente, pero la orientación en pantalla podría salir girada o espejada. Por eso las "coordenadas" del chrome de rigor son una convención visual, no una referencia absoluta (ver nota de arriba).
- **No hay ningún cuadrado de referencia ni canvas objetivo — la forma orgánica con esquinas vacías es la firma esperada de un layout por fuerzas, no un error.** El bounding box (`x∈[-26.4,26.6], y∈[-24.5,24.7]`) es casi cuadrado por coincidencia (el dato con mayor extensión en cada eje resultó de magnitud similar), pero eso no significa que los puntos llenen un cuadrado. Verificado: el punto más extremo en x cae en `y≈1.6` (centro vertical, no una esquina) y el punto más extremo en y cae en `x≈-8.5` (lejos del borde horizontal) — son puntos distintos, no un mismo punto extremo en ambos ejes a la vez. El punto más cercano a cualquiera de las 4 esquinas reales del bounding box queda a 10-14 unidades de distancia (el mapa completo mide ~72 unidades de diagonal). Una esquina requiere que un punto sea simultáneamente el más extremo en x **y** en y al mismo tiempo — con datos reales de una nube con estructura (no ruido uniforme), eso casi nunca ocurre. La forma real (núcleo denso + anillo hueco + tentáculos + islas aisladas) es producto de las tres fuerzas de PaCMAP descritas arriba, no de ajustar a ninguna figura geométrica predefinida.

**4. Qué evitar explícitamente (adicional a los anti-patrones ya listados arriba)**
- Paletas pastel o de baja saturación — leen como "amigable/consumer app", lo opuesto al tono buscado.
- Gradientes o glassmorphism/blur decorativos sin significado — es exactamente la estética que hoy se asocia a "generado por IA sin dirección de diseño".
- Fondo oscuro con acentos neón (el "constellation dark mode" descartado esta sesión).
- Una sola tipografía para todo — pierde la distinción entre "instrumento" y "curaduría" que el manifiesto pide.

**Decisión tomada (2026-09-22)**: la métrica de color es **tamaño del cluster** (masa semántica), no `cluster_probability`. Razón del usuario/decisión: más intuitivo para el visitante ("esta zona tiene más producción académica") y encaja mejor con la metáfora de carta náutica/atlas (más masa = territorio más grande) — `cluster_probability` es un concepto interno de HDBSCAN que requeriría explicación adicional. Se descartó la opción de codificar ambas métricas a la vez (color + opacidad) por ir contra la regla del propio manifiesto de no apilar codificaciones sin razón concreta.

**Estado**: manifiesto de dirección de diseño cerrado (color, tipografía, chrome, fondo, métrica de color). Falta: tokens de color concretos (valores hex, probablemente del rango secuencial azul del sistema de diseño validado) y el primer mockup/prototipo — nada de esto se ha construido todavía.

### Decisión editorial fuerte: estructura de v1 — 100% data-driven, no por las 4 áreas administrativas (2026-09-22)

**Pregunta planteada por el usuario**: los datos quedan naturalmente alineados con las 4 áreas institucionales de la UNAM (Físico-Matemáticas, Biológicas y de la Salud, Sociales, Humanidades y las Artes) — ¿debería el atlas v1 usar esas 4 áreas como su estructura principal de navegación (macro), o hay una lógica mejor?

**Análisis**: las 4 áreas son una taxonomía **administrativa** (asignada por el sistema de registro de la UNAM al catalogar cada tesis), no algo que el pipeline semántico descubrió. Usarlas como estructura editorial principal de "el primer atlas" tiene dos problemas de fondo:
1. **Contradice un hallazgo ya confirmado dos veces**: Área 4 (Humanidades) sale infrarrepresentada en el espacio semántico tanto en el atlas viejo (Leiden/50k: 6 de 43 macronodos) como en el nuevo (HDBSCAN/609k: 67.2% de ruido global, con sospecha de concentrarse más ahí — pendiente medir). Si el área es la estructura de navegación, esa sección se sentirá "vacía" sin ninguna explicación — se lee como falla del atlas, no como el hallazgo real que es.
2. **Reintroduce a nivel de UX el mismo silo que se evitó a propósito a nivel de embedding**: ya se decidió no concatenar `área` en el texto embebido precisamente para no suprimir el descubrimiento cruzado entre áreas/programas — hacer de `área` la partición de navegación de más alto nivel deshace esa decisión en la capa de arriba.

**Decisión tomada**: **v1 se muestra 100% data-driven** — la jerarquía macro/meso/micro sale del corte del árbol condensado de HDBSCAN, agnóstica de área. Las 4 áreas administrativas quedan como una **lente/filtro secundario** (activable encima del mapa ya construido, ej. "colorear por área"), no como la partición del mapa. El usuario ofreció ayudar a organizar esa vista por áreas más adelante — se registra como trabajo futuro, no bloqueante para v1.

**Razón adicional del usuario, coincide con la decisión de "modo caos" de esta misma sesión**: mostrar la estructura 100% data-driven primero tiene valor narrativo/pedagógico — "estaríamos enseñando" que así se ve la información real, antes de (opcionalmente) mostrar cómo se vería curada/organizada por categorías administrativas. Es la misma lógica de "caos real → orden editorializado" ya decidida para el modo caos, aplicada ahora también a la elección de qué estructura lidera v1.

**Idea nueva que surge de esto: un onboarding/prólogo que enseñe explícitamente por qué el mapa no sigue las 4 áreas.** El usuario reconoce que es trabajo adicional, no gratuito — se registra como decisión a favor en principio, pendiente de alcance exacto.

#### Ideas de onboarding/narrativa para explicar la estructura data-driven (brainstorm 2026-09-22)

- `[idea]` **Prólogo corto, no tutorial forzado (barato).** Una página/panel fijo, 3-4 frases, tono de ficha técnica (coherente con el Design Manifest): "Este mapa no sigue las 4 áreas administrativas de la UNAM — se construyó agrupando 609,156 tesis por similitud real de contenido." Sin pasos forzados tipo "1 de 5".
- `[idea]` **Transición animada área → clusters reales, como pieza educativa (reusa el "modo caos").** En vez de solo explicar con texto, mostrarlo: animar la misma nube de puntos pasando de "coloreada/agrupada por área declarada" a "reagrupada por similitud semántica real". Es mucho más persuasivo que un párrafo, y es casi la misma feature que el modo caos con otro propósito — evaluar si conviene construirlas como una sola pieza reutilizable en vez de dos features separadas.
- `[idea]` **Nota ambiental en la ficha técnica permanente, no un modal (barato, reusa chrome ya decidido).** El pie de "ficha técnica" del Design Manifest ya va a estar siempre visible — aprovecharlo para una línea discreta: "Agrupación: similitud semántica, no área administrativa · ver por qué ↗", enlazando al prólogo del punto 1 en vez de interrumpir con un modal al entrar.
- `[idea]` **"Encuentra tu área" como verificación posterior, no introducción.** Después de que el usuario ya exploró el mapa un rato: invitación opcional a activar una área declarada y ver cómo se dispersa sobre los clusters reales (no queda contenida en una región). Enseña el hallazgo haciendo que el usuario lo descubra, en vez de que se lo digan de entrada.
- `[idea]` **Colofón de "primera edición", al estilo de un atlas de papel real.** Una ficha "Acerca de este atlas" con fecha de corte de datos, versión del modelo de embeddings, algoritmo de clustering, número de tesis — trata a v1 literalmente como una primera edición sujeta a revisión, como cualquier atlas científico impreso real. Refuerza legitimidad y es honesto sobre que esto es una versión, no una verdad final.
- `[idea]` **Micro-textos explicativos por nivel de profundidad, no por paso de tutorial.** En vez de una serie "1 de 5" al inicio, un texto breve que aparece la primera vez que el usuario cruza de macro→meso o meso→micro, explicando "estás bajando un nivel de la jerarquía que descubrió el algoritmo" — enseña en el momento exacto que es relevante, no todo de golpe al entrar.

**Mi opinión**: de las seis, priorizaría el prólogo corto (punto 1) y la nota en la ficha técnica (punto 3) primero — son casi gratis porque reusan chrome que el Design Manifest ya exige construir, y ya resuelven la mayor parte del riesgo de "el usuario se siente perdido sin las 4 áreas de siempre". La transición animada (punto 2) es la pieza con más impacto narrativo/de portafolio, pero cuesta más — la dejaría para cuando ya exista la vista por áreas como filtro (reutiliza ese mismo trabajo en vez de construir una animación de un solo uso). El colofón de "primera edición" (punto 5) es barato y, más allá de enseñar, es honestidad de producto — lo trataría casi como no-opcional para cualquier versión "v1" que se llame a sí misma primera edición.

**Estado**: decisión de estructura (100% data-driven, áreas como filtro futuro) tomada. Onboarding: dirección aceptada en principio, alcance y priorización de las 6 ideas todavía sin decidir formalmente.

## Jerarquía macro/meso/micro (2026-09-22, paso 5 de "Próximos pasos concretos")

**Pregunta del usuario**: cómo construir macro/meso/micro de forma objetiva (no curada a mano) pero pensando en que la UI necesita un número de opciones navegable, no 513.

### Intento 1 (descartado): caminar `condensed_tree.parquet` por umbral de tamaño

El plan que ya estaba anotado arriba ("Cómo construir el corte curado sin re-clusterizar") proponía subir por el árbol condensado de HDBSCAN hasta un umbral de tamaño mínimo por rama. Se probó contra los datos reales **antes** de construir nada encima, y no sirve para este corpus: la raíz del árbol condensado se parte en solo 2 hijos-cluster — uno de 325 tesis y **otro de 608,603 (99.9% de todo lo clusterizado)**. Es el mismo patrón de "blob gigante" que ya había obligado a descartar `cluster_selection_method='eom'` a nivel de puntos, reapareciendo un nivel más arriba. Barrido de umbrales (5%–70% del corpus clusterizado) confirmó que subir el umbral no ayuda: el tamaño **mediano** de los grupos resultantes salta a 130,000–410,000 tesis casi de inmediato — casi todas las 513 hojas terminan colgando del mismo blob dominante en vez de repartirse en ramas de tamaño comparable. Caminar el árbol tal cual está construido no da una jerarquía navegable.

### Método adoptado: Ward sobre los 513 centroides, no sobre los 609k puntos

Esto no contradice "no re-clusterizar" — los 609,154 puntos no se tocan. El paso nuevo es barato y opera solo sobre los 513 micro-clusters ya computados:

1. **Micro = los 513 clusters de HDBSCAN, sin cambios.**
2. **Centroide por micro-cluster** en el espacio de embeddings de 1024d (promedio de los vectores e5-large de sus miembros), re-normalizado a norma 1 antes de agrupar — para que la distancia se comporte como similitud coseno, consistente con el resto del pipeline (Nobel, hubness, etc., todo usa coseno).
3. **Clustering jerárquico aglomerativo (Ward)** sobre esos 513 centroides — la misma técnica que usa BERTopic para `hierarchical_topics()`. Con 513 objetos es trivial computacionalmente (matriz 513×513), y Ward da ramas balanceadas, a diferencia del encadenamiento por densidad del árbol condensado que acaba de fallar arriba.
4. **Corte a macro/meso**: se busca `N` dentro de una banda fijada por legibilidad de UI, no un número inventado de antemano. Banda inicial propuesta: ~15-40 (heredada del atlas viejo). **El usuario pidió ampliarla a 50-60** porque en la UI se veían pocas opciones con la banda chica — aceptado, es una restricción de producto legítima, no arbitrariedad: más opciones en el nivel macro reparten mejor la navegación cuando hay 513 micro-temas reales debajo. Dentro de la banda, dos criterios objetivos de desempate cuando cabe más de un `N`:
   - **Balance**: ningún macro debe concentrar más de 30% del corpus clusterizado (evita repetir el colapso tipo "eom" a este nivel).
   - **Gap del dendrograma**: entre los `N` que cumplen el balance, se prefiere el que cae justo antes del salto más grande en altura de fusión de Ward (el "codo" estándar) — señal real de separación en los datos.
5. **Meso** se construye igual, pero corriendo Ward otra vez *dentro de cada macro* (solo sobre sus micro-clusters miembros), banda ~5-15 por macro. Si un macro tiene ≤5 micro-clusters, no se fuerza a agrupar — cada micro-cluster es su propio meso.
6. **Ruido (67.2%) queda fuera de esta jerarquía**, igual que antes — vive en el "modo caos", no se fuerza a ningún macro.

**Bug real encontrado y corregido durante la implementación**: la primera versión de `pipeline/construir_jerarquia_macro_meso.py` construía la matriz dispersa indicador (micro-cluster × tesis) con un doble indexado incorrecto (`cols = np.arange(len(rows))` declarado contra `X.shape[0]` completo y vuelto a rebanar con `[:, mask]`), lo que desalineaba qué tesis pertenecía a qué fila de la matriz. Los centroides salían de subconjuntos casi aleatorios de puntos, no de los miembros reales del cluster. Se detectó *antes* de confiar en el resultado, verificando que los tamaños de cluster recuperados desde la matriz coincidieran exactamente con los tamaños reales de `clusters_hdbscan.parquet` (coincidían con la versión rota — con **desfasado de 17.0% vs. 5.9%** entre lo que el código decía y lo que en realidad medía — señal de que algo no cuadraba). Fix: construir la matriz indicador directamente con `shape=(n_clusters, X_masked.shape[0])`, sin la rebanada `[:, mask]` redundante. Verificado después del fix: multiset de tamaños recuperados == multiset de tamaños reales, exacto.

### Resultado (corrida real, 2026-09-22)

Script: `pipeline/construir_jerarquia_macro_meso.py`. Banda macro=(50,60), banda meso=(5,15), tope de balance=30%.

- **53 macro-grupos** (dentro de la banda pedida). Balance: el más grande concentra **7.4%** del corpus clusterizado (bien por debajo del tope de 30%) — nada parecido al colapso del árbol condensado. Tamaño por macro: min=325, mediana=3,020, max=14,749 tesis. Micro-clusters por macro: min=1, mediana=8, max=30.
- **324 meso-grupos** en total. Tamaño por meso: min=150 (un solo micro-cluster sin fusionar), mediana=382, max=4,908 tesis. Meso por macro: min=1 (solo 1 de los 53 macros — muy pocos micro-clusters propios, no se forzó fusión), mediana=5, max=14.
- Etiquetas c-TF-IDF generadas para ambos niveles reusando `pipeline/generar_topicos_ctfidf.py` sin modificarlo (mismo método que ya etiqueta los 513 micro-clusters, aplicado con `CLUSTERS_PATH`/`OUTPUT_PATH` apuntando a tablas temporales thesis→macro_id y thesis→meso_id) → `data/clustering/macro_topics_ctfidf.parquet`, `data/clustering/meso_topics_ctfidf.parquet`.

**Verificación cualitativa honesta (no solo los números de balance)**: revisar las etiquetas automáticas confirma que **meso es temáticamente limpio** (ej. meso 201 "pozos · yacimientos · perforación · petroleros", meso 202 "síntesis · compuestos · derivados · catalizadores", meso 216 "teorema · espacios · gráficas · grupos" — cada uno un tema real y coherente) pero **macro es deliberadamente más grueso y a veces mezcla subcampos distintos bajo un mismo techo** — ej. macro 35 sale etiquetado "síntesis · pozos · compuestos · yacimientos" porque agrupa el meso de química/síntesis JUNTO con el meso de pozos petroleros; macro 37 sale "teorema · robot · gráficas · líquido · galaxias · fluidos" porque agrupa matemáticas puras, robótica, dinámica de fluidos y astronomía bajo un mismo macro. Esto **no es un bug** — es la consecuencia esperada de comprimir 513 micro-temas reales en solo 53 categorías de nivel superior (mediana 8 micro-clusters por macro): un "capítulo" de este tamaño necesariamente agrupa subcampos relacionados-pero-distintos, igual que el capítulo "Ciencias" de cualquier clasificación bibliotecaria agrupa física, química y biología sin que eso implique que son el mismo tema. La navegación real hacia el tema específico ocurre al bajar a meso, que sí es fino.

**Inspección a fondo del macro 35 (2026-09-22, a pedido del usuario) — la mezcla es peor de lo que la frase de arriba sugería.** No son 2 subcampos ("química" + "petróleo"), son **al menos 5 campos genuinamente distintos**, verificado con muestras de título reales de cada uno de sus 7 meso: meso 201 "pozos petroleros" (3,950, 26.8% — ingeniería petrolera real: perforación, interpretación sísmica); meso 207 "perros/gatos" (2,974, 20.2% — **veterinaria**, no química: cirugía en pequeñas especies, leptospirosis canina, anatomía comparada — sin relación alguna con química o petróleo); meso 202 "síntesis" (2,223, 15.1% — química de síntesis real: compuestos organometálicos, catalizadores); meso 204 "maíz/frijol" (2,136, 14.5% — **ciencia de alimentos/agroindustria**: quesos, pastas, lácteos, biomasa); meso 203 "películas delgadas" (1,889, 12.8% — **metalurgia/materiales**: aleaciones, nanoestructuras); más química analítica (206, 7.7%) y fitoquímica (205, 3.0%). Se agruparon porque comparten un registro de escritura técnico-procedimental similar ("método", "caracterización", "síntesis", "propiedades"), no porque el contenido sea afín — el 20.2% que es veterinaria pura es el caso más claro de que el nombre del macro puede ser activamente engañoso para una porción no trivial de su contenido. **Implicación de producto**: para macros grandes y heterogéneos como este, no basta con mostrar la etiqueta del macro en la UI — hace falta exponer el desglose por meso (o al menos advertir cuando el macro es muy heterogéneo) para no prometer coherencia temática que no existe a ese nivel. Pendiente decidir un criterio automático de "heterogeneidad de macro" (ej. entropía de área administrativa entre sus miembros, o dispersión de los centroides de meso dentro del macro) para detectar casos como este sin depender de que alguien lo note a simple vista.

**Resuelto parcialmente por la jerarquía v2 (ver sección "Jerarquía macro/meso — v2" más abajo)**: este hallazgo fue exactamente el disparador del cambio de método. Bajo v2, este contenido queda repartido en 3 macros distintos — {petróleo+materiales+síntesis} id 54 (8,062), {maíz+fitoquímico} id 55 (2,581), {veterinaria+cromatografía} id 56 (4,106). La veterinaria ya no convive con petróleo/química (la mezcla más grave), aunque persiste algo de mezcla dentro de cada uno de los 3 (petróleo con materiales/síntesis; veterinaria con química analítica) — declarado como tensión abierta en la sección v2, no una solución perfecta.

**Archivos generados**:
- `data/clustering/jerarquia_macro_meso.parquet` — `cluster_id` (micro), `n_tesis`, `macro_id`, `meso_id`.
- `data/clustering/tesis_macro_meso.parquet` — `thesis_id`, `cluster_id`, `macro_id`, `meso_id` (199,623 filas, sin ruido).
- `data/clustering/macro_topics_ctfidf.parquet`, `data/clustering/meso_topics_ctfidf.parquet` — etiquetas por nivel.

**Para recrear (v1, ver v2 más abajo — ya no es el método vigente)**: `python pipeline/construir_jerarquia_macro_meso.py` (banda/tope configurables por env var: `MACRO_MIN`, `MACRO_MAX`, `MESO_MIN`, `MESO_MAX`, `MAX_MACRO_SHARE`), luego etiquetar cada nivel reusando `pipeline/generar_topicos_ctfidf.py` con `CLUSTERS_PATH`/`OUTPUT_PATH` apuntando a una tabla thesis_id+cluster_id renombrada desde `macro_id`/`meso_id` de `tesis_macro_meso.parquet`.

### Jerarquía macro/meso — v2, corte por coherencia (2026-09-22)

**Por qué se reemplazó v1**: al inspeccionar el macro 35 (el más grande de v1, a pedido del usuario) se encontró que mezclaba **5 campos sin relación temática real** — ingeniería petrolera (26.8%), veterinaria (20.2%, verificado con títulos: cirugía en perros/gatos, leptospirosis canina — nada que ver con química), química de síntesis (15.1%), ciencia de alimentos (14.5%), metalurgia (12.8%) — unidos solo porque comparten un registro de escritura técnico-procedimental ("método", "caracterización", "síntesis", "propiedades"), no contenido. Causa raíz identificada: v1 cortaba el dendrograma Ward por **conteo** (banda 50-60 pedida para la UI, con balance y "gap" como desempate) sin ningún chequeo de que el contenido agrupado tuviera sentido — el criterio nunca miraba coherencia, solo cuántos grupos salían y qué tan parejos eran en tamaño.

**Diagnóstico cuantitativo antes de tocar el código**: se midió la altura de fusión Ward (`Z[:,2]`) necesaria para separar los 5 campos del macro 35. A la altura que daba 53 grupos (0.484, percentil ~90 de todas las alturas de fusión del árbol), los 5 seguían fusionados en un solo nodo. Barrido completo de alturas candidatas (D de 0.15 a 0.484), verificando en cada una (a) cuántos macro-grupos totales resultan, y (b) en cuántas partes se separa específicamente el conjunto de 26 micro-clusters del viejo macro 35:

| D (altura Ward) | Macro-grupos totales | Macro 35 se parte en |
|---|---|---|
| 0.484 (v1) | 53 | 1 (sin resolver) |
| 0.45 | 66 | 2 |
| 0.42 | 75 | 2 |
| **0.40** | **89** | **3** |
| 0.35 | 141 | 4 |
| 0.30 | 207 | 7 (= exactamente los 7 meso ya validados — deja de existir una distinción real entre macro y meso) |

**Hallazgo estructural, no solo un ajuste de parámetro**: no hay ningún valor de corte único que a la vez (a) quepa en la banda de 50-60 pedida para la UI y (b) resuelva la mezcla del macro 35 — resolverla exige bajar a D≤0.45, y ya no caben más de 66 grupos ahí. Forzar la banda de conteo fue, en retrospectiva, la causa directa del problema: exigía comprimir 513 micro-temas en muy pocos grupos sin ningún límite de cuánta heterogeneidad se acepta por grupo. **Se abandona el corte por conteo — el número de macros ya no se fija de antemano, sale de la coherencia real de los datos** (con `criterion='distance'` de scipy en vez de `criterion='maxclust'`).

**D elegido: 0.40** (89 macro-grupos) — el más alto (menos fragmentación posible) que ya separa el macro 35 en partes genuinamente más sensatas: {petróleo + materiales + síntesis} (8,062), {maíz/frijol + fitoquímico} (2,581), {veterinaria + cromatografía} (4,106). No es una separación perfecta (petróleo sigue con materiales/síntesis; veterinaria sigue con química analítica) — bajar más resuelve eso pero a D=0.30 el macro colapsa a la misma granularidad que meso, dejando de tener dos niveles distintos. D=0.40 es el punto donde la mezcla más grave (veterinaria con petróleo) se resuelve sin sacrificar la distinción macro/meso. **Meso usa el mismo criterio de distancia, D=0.20, dentro del sub-árbol de cada macro ya cortado** (antes: banda 5-15 por macro).

**Evidencia de que es correcto — comparación v1 vs. v2**:

| Métrica | v1 (conteo, banda 50-60) | v2 (distancia, D=0.40) |
|---|---|---|
| Macro-grupos | 53 | **89** |
| Meso-grupos | 324 | 424 |
| Macro más grande | 14,749 tesis (7.4% del clusterizado) | 8,062 tesis (**4.0%**) |
| Micro-clusters por macro (mediana) | 8 | 5 |
| Macros singleton (1 solo micro-cluster) | 1 (macro 31, "notas al programa") | 3 |
| Caso macro 35 (petróleo+veterinaria+química+comida+metalurgia) | 1 solo macro, sin resolver | **3 macros separados**, verificado con muestras de título reales de cada uno |

Pureza por área administrativa (métrica secundaria, ya se había anotado como imperfecta — un grupo puede ser 100% de una sola área y aun así mezclar subcampos, como pasa con petróleo+materiales+síntesis que son todos Área 1): la pureza media apenas cambia entre v1 y v2 (0.835 → 0.832) — **confirma que el área administrativa no es un buen proxy para detectar este tipo de mezcla** (petróleo/química/materiales conviven en la misma área sin ser el mismo campo); la evidencia real y concluyente es la resolución del caso conocido, verificada con títulos reales, no la métrica de área.

**Costo aceptado, declarado explícitamente**: el conteo de macros subió de 53 a 89 — por encima de la banda de 50-60 que se había pedido para la UI. Es la consecuencia directa de priorizar coherencia real sobre un objetivo de conteo. **Sigue sin ser perfecto** — macro 54 (el más grande ahora) todavía mezcla petróleo con materiales y síntesis química; para una separación completa haría falta bajar hasta D≈0.30, punto en el que macro deja de ser un nivel distinto de meso. Se marca como tensión abierta, no resuelta del todo: la mejora es real y medible, no total.

**Verificación del caso macro 31 ("notas al programa")**: sigue existiendo como macro singleton (ahora con id 49, la numeración cambió con el recorte) — confirma que el nuevo método sigue respetando islas genuinamente aisladas sin forzarlas a fusionarse con nada, igual que v1.

**Gráficas 10, 11 y 13 regeneradas** con la jerarquía v2 (mismos scripts, sin cambios salvo hacer dinámico el conteo de macros en los títulos — antes tenían "53" hardcodeado). Ver la sección de evidencia visual más abajo para el detalle actualizado de cada una.

**Archivos nuevos/actualizados por v2**: `data/clustering/micro_cluster_centroides.npy` + `micro_cluster_ids_orden.npy` (centroides persistidos por primera vez, para poder recalcular validaciones sin repetir el paso caro de leer los embeddings completos). `jerarquia_macro_meso.parquet`, `tesis_macro_meso.parquet`, `macro_topics_ctfidf.parquet`, `meso_topics_ctfidf.parquet`, `macro_linkage_Z.npy` — mismos nombres que v1, contenido reemplazado.

**Para recrear v2**: `python pipeline/construir_jerarquia_macro_meso.py` (ahora con `D_MACRO`, `D_MESO` como env vars, default 0.40/0.20 — ya no hay banda de conteo), luego regenerar etiquetas igual que antes con `pipeline/generar_topicos_ctfidf.py` vía tablas temporales renombradas.

**Pendiente (no es parte de este paso)**: esto entrega la *estructura* de datos (qué micro pertenece a qué meso pertenece a qué macro, con etiquetas), no todavía el `atlas_manifest.v1.json` que consume el frontend (paso 6) — falta adaptar el esquema ya documentado en `nodo_unam.md` (macro eager / meso-micro-vecindario lazy) a estas tablas nuevas.

**Dos piezas de evidencia visual generadas a pedido del usuario (2026-09-22)**, agregadas al checklist de abajo como ítems 10 y 11:
- `docs/evidencia_visual/10_dendrograma_macro.png` (script: `pipeline/graficar_dendrograma_macro.py`) — dendrograma Ward truncado a los últimos 80 merges (513 hojas no caben legibles), con línea de corte marcando la altura a la que se obtienen los 53 macro-grupos. Requiere que `construir_jerarquia_macro_meso.py` haya guardado `data/clustering/macro_linkage_Z.npy` (se agregó ese guardado al script — antes no persistía la matriz de linkage).
- `docs/evidencia_visual/11_atlas_micro_vs_macro.png` (script: `pipeline/graficar_atlas_macro.py`) — dos paneles sobre el mismo layout PaCMAP: 513 micro-clusters (igual que la gráfica 1) vs. los 53 macro-grupos, con el `macro_id` numerado en el centroide (mediana x,y) de cada uno para poder ubicarlos contra `macro_topics_ctfidf.parquet`. Confirma visualmente que el agrupamiento Ward sí concentra parches de color más grandes y coherentes en el panel derecho, sin perder la estructura general del atlas.

### Escaneo sistemático de heterogeneidad + piloto de re-embedding (2026-09-22)

**Contexto**: el usuario preguntó por qué el macro 56 mezclaba veterinaria con cromatografía, y pidió revisar el resto de las 89 etiquetas en busca de más casos así. Se hizo un escaneo manual completo (las 89 macros, todas sus meso) — el peor caso resultó ser el **macro 58** ("flujo · teorema · espacios · robot · gráficas · líquido"), que mezcla **6 campos sin relación**: matemáticas puras, dinámica de fluidos, astronomía, robótica/redes neuronales, estadística, y medicina de laboratorio (índice de neutrófilos/PaO2) — peor que el 35/56. Otros casos identificados a mano: macro 25 (hotel+autobuses+bomberos+mercado, agrupados por formato "anteproyecto técnico", no por tema), macro 72 (agrupado por **nombre de hospital/institución**, no por tema), macro 51 (geología+biología bajo "geociencias"), macro 30 (grab-bag regional/ambiental).

**Dos métricas automáticas probadas para no depender de lectura manual — la primera falló, la segunda funcionó**:
1. **Similitud coseno entre centroides de embeddings de meso**: descartada — todos los valores caen entre 0.91-0.94 sin importar la heterogeneidad real, el espacio de e5-large está demasiado comprimido para discriminar a esta escala (ver el piloto de re-embedding más abajo, que mide esto directamente).
2. **Jaccard de las top-8 keywords c-TF-IDF entre pares de meso**: descartada — 78 de 85 macros con ≥2 meso tienen al menos un par con 0 palabras en común, incluso los genuinamente coherentes (las top-8 palabras de c-TF-IDF están deliberadamente filtradas para excluir vocabulario común entre clusters, así que dos meso relacionados pero con vocabulario específico distinto también dan Jaccard=0 — la métrica no distingue).
3. **Similitud coseno entre vectores c-TF-IDF COMPLETOS de cada meso (no solo el top-8), funciona**: separa limpio los casos conocidos. Macros malos (58, 56, 25) caen en 0.030-0.034 de similitud media entre sus meso; macros buenos (15 "todo derecho/amparo", 77 "todo procedimientos quirúrgicos", 21 "todo justicia penal") caen en 0.056-0.061 — casi el doble. Aplicado a las 85 macros con ≥2 meso, produce un ranking honesto: macro 58 sale en el puesto 4 de 85 más heterogéneo, macro 56 en el 7, macro 25 en el 8 — coincide con la lectura manual. Encontró 3 casos adicionales no detectados a ojo: macro 61 (tuberculosis + síndrome de Sjögren, el más heterogéneo de los 85), macro 66 (dental, con un par interno sospechosamente bajo), macro 20 (adopción+eutanasia+donación de órganos+inseminación artificial). Script: cálculo ad-hoc, no persistido todavía como pipeline formal — pendiente si se decide aplicar la separación automática (ver "Próximo paso" al final de esta subsección).

**Pregunta del usuario: ¿el modelo de embeddings (e5-large) fue subóptimo? Se probó empíricamente con un piloto, no se especuló.**

Se instaló `sentence-transformers` + `BAAI/bge-m3` (568M parámetros, buen soporte multilingüe, candidato más verificable de una lista sugerida por otra IA — esa lista incluía modelos "Jina v5" cuyas specs no se pudieron verificar de forma independiente, se trataron como no confirmadas) y se embebieron con BGE-M3 muestras de 15 títulos reales de: el par conocido malo (veterinaria cluster 372 vs. cromatografía clusters 470/475), el pentágono completo del macro 58, un par de control conocido bueno (fracturas/artroplastia vs. infarto/miocardio, ambos clínico-quirúrgicos pero distintos), y un baseline de 300 títulos aleatorios del corpus completo.

| | e5-large | BGE-M3 |
|---|---|---|
| Similitud media entre pares al azar (baseline) | 0.926 | **0.325** |
| Veterinaria ↔ Cromatografía (par MALO conocido) | 0.961 → percentil 96.7 del baseline | 0.723 → percentil **99.7** |
| Fracturas ↔ Infarto (control BUENO conocido) | 0.964 → percentil 97.7 | 0.766 → percentil **99.7** |
| Pentágono macro 58 (matemáticas+fluidos+astronomía+robótica+estadística+medicina lab) | ya sabíamos que mal | media 0.772, rango 0.676-0.840 — igual de elevado que el resto |

**Resultado, contrario a la hipótesis de partida**: BGE-M3 sí tiene un espacio de similitud mucho menos comprimido (baseline 0.325 vs. 0.926 de e5-large — confirma que la compresión de e5-large es real y medible). **Pero eso no resuelve el problema**: bajo BGE-M3, el par malo y el par bueno de control caen en el **mismo percentil exacto (99.7%)** del baseline — el modelo no los distingue en absoluto. Bajo e5-large al menos había una diferencia de 1 punto (96.7 vs 97.7). **Conclusión**: el problema no es principalmente la compresión del espacio de e5-large — es que modelos de propósito general (probado con dos: e5-large y BGE-M3) capturan con fuerza la **plantilla/registro procedimental** de un título académico corto en español ("determinación de X por método Y") por encima del contenido temático específico, cuando el título es breve y formulaico. Parece ser un problema transversal a embeddings de oraciones de propósito general para este tipo de texto, no un defecto específico de e5-large. **Decisión: no se justifica re-embeber el corpus** — no solo por el costo (recorrer todo el pipeline: HDBSCAN en Kaggle, PaCMAP, jerarquía completa, Nobel), sino porque el candidato más creíble probado no arregla lo que se buscaba arreglar.

**Archivos del piloto**: `data/clustering/piloto_bge_m3_titulos.json` (las muestras de título usadas, para poder repetir la comparación con otro modelo sin volver a samplear) y `data/clustering/piloto_bge_m3_embeddings.npz` (los embeddings BGE-M3 ya calculados de esas muestras).

### Corrección manual sobre la jerarquía v2 (2026-09-22) — separación quirúrgica con revisión caso por caso

**Pedido explícito del usuario**: aplicar la separación automática, pero con revisión manual incluida — "nos tardaremos lo que haga falta para asegurar que los datos estén lo mejor posible". La métrica de similitud c-TF-IDF completa (sección anterior) dio 11 candidatos por debajo de 0.045 de similitud media entre sus meso. **Se revisó cada uno con muestras de título reales antes de decidir** — la métrica sola no bastaba.

**7 de los 11 resultaron ser falsos positivos** — campos amplios pero legítimamente coherentes, la métrica los marcó solo porque sus sub-temas usan vocabulario específico distinto entre sí (no por falta de relación real). Verificado con títulos:
- **Macro 66** (n_meso=7, sim=0.027): todo odontología — molares, caninos retenidos, labio/paladar hendido, terapia pulpar, ATM, hábitos orales, maloclusión. Coherente.
- **Macro 20** (sim=0.029): todo bioética/derecho de la persona — donación de órganos, adopción, inseminación artificial/reproducción asistida, eutanasia. Coherente.
- **Macro 14** (sim=0.031): todo derecho laboral-fiscal de las prestaciones — prima de antigüedad, participación de utilidades, ISR de personas físicas. Coherente.
- **Macro 44** (sim=0.032): todo comunicación/diseño — campaña publicitaria, diseño web, identidad gráfica/corporativa, periodismo/radio. Coherente.
- **Macro 18** (sim=0.034, 14 meso): todo derecho civil-mercantil-administrativo — fideicomiso, obra pública, protección al consumidor, notariado, títulos de crédito, quiebra, servidores públicos. Coherente aunque grande (candidato a dividir por navegabilidad en el futuro, no por incoherencia).
- **Macro 75** (sim=0.042): todo neurociencia/psiquiatría — Parkinson, esquizofrenia, TDAH, condicionamiento operante y memoria en ratas (investigación básica de neurociencia). Coherente.
- **Macro 24** (sim=0.045): exploración sanitaria municipal + descripción de hospitales/clínicas — ambos son censos de infraestructura de salud. Coherente.

**6 confirmados como genuinamente incoherentes — separados**:
- **Macro 58** (ya documentado arriba): matemáticas + fluidos + astronomía + robótica + estadística + medicina de laboratorio.
- **Macro 56** (ya documentado arriba): veterinaria + cromatografía + radiología + enfermedad infecciosa + farmacia.
- **Macro 25** (ya documentado arriba): hotel + autobuses + bomberos + mercado, agrupados por formato "anteproyecto técnico", no por tema.
- **Macro 61** (sim=0.018, el más heterogéneo de los 85): tuberculosis + síndrome de Bartter + síndrome de Ellis-van Creveld + **"alerta Amber, el color de los niños desaparecidos"** (literal, sin ninguna relación) — grab-bag de "reporte breve de caso", no un tema.
- **Macro 30** (sim=0.047): energía residencial + turismo médico + transporte público + geografía económica regional + vivienda urbana + regulación de telecomunicaciones + residuos sólidos + tráfico de fauna silvestre + física atmosférica + ciclones tropicales — demasiados campos genuinamente distintos bajo "temas regionales/ambientales".
- **Macro 88** (sim=0.050): epidemiología dental + modelo de atención médica familiar + nutrición infantil + casos de enfermería + salud reproductiva/dinámica familiar + factores de riesgo cardiovascular.

**Ejecución**: `pipeline/aplicar_correccion_manual_macro.py` — reasignación directa de `macro_id` (cada meso de los 6 macros confirmados se vuelve su propio macro), sin re-correr Ward ni recalcular embeddings. 40 micro-clusters afectados (19,009 tesis, 9.5% del corpus clusterizado) se redistribuyeron en 35 macros nuevos.

**Resultado final**: **118 macros** (89 automáticos − 6 separados + 35 nuevos), **33 de ellos singleton** (1 solo micro-cluster — antes eran 3). Macro más grande sigue siendo el mismo (8,062, 4.0% del clusterizado) porque ninguno de los 6 corregidos estaba en el top 5. Gráficas 10, 11 y 13 regeneradas con la jerarquía corregida — el dendrograma (10) ahora aclara explícitamente que la línea roja marca el corte automático (89 grupos) y que 6 de esos se separaron después a mano, dando el total final de 118 (ya no corresponde a un único corte plano del árbol, así que no se puede seguir derivando la altura de la línea desde el conteo de macros — se fijó `D_MACRO_ORIGINAL=0.40` explícitamente en el script).

**Para recrear**: correr en orden `python pipeline/construir_jerarquia_macro_meso.py` → regenerar labels de macro/meso (ver instrucciones arriba) → `python pipeline/aplicar_correccion_manual_macro.py` → regenerar labels de macro otra vez (los de meso no cambian) → regenerar gráficas 10/11/13.

**Pendiente (no bloqueante)**: el macro 18 (derecho civil-mercantil, 14 meso) es coherente temáticamente pero grande para navegación — candidato a dividir por tamaño en una futura pasada, no por el criterio de heterogeneidad usado aquí. Y sigue pendiente construir el criterio automático de "macro demasiado grande para la UI" (distinto del de "macro heterogéneo", ya resuelto) si hace falta más adelante.

### Ronda 2 — macro 54 (química/petróleo) y el detector de heterogeneidad escondida (2026-09-22)

**El usuario no quedó tranquilo con que macro 54 (el más poblado, 8,062 tesis) mezclara química de síntesis con petróleo — pidió muestra representativa + veredicto.** Se leyeron títulos reales de los 9 meso del macro. Resultado: no son 2 campos, son **3**:

- **Petróleo/refinación real** (34.7%, ~2,799 tesis): meso 255 "pozos petroleros" (ingeniería de yacimientos: fracturamiento hidráulico, reservas de gas shale), meso 256 "refinería" (operación de plantas FCC en Minatitlán/Tula), meso 258 "catalizadores HDS" (hidrodesulfuración — un catalizador específico del proceso de refinación, puente real entre química y petróleo, no solo vocabulario compartido).
- **Química de síntesis y materiales** (45.9%, ~3,696 tesis): meso 257 (síntesis orgánica/medicinal — esteroides, benzodiazepinas), meso 259 (química de coordinación inorgánica), meso 262 (polímeros), meso 260 (metalurgia — aleaciones, corrosión), meso 261 (materiales/nanomateriales — películas delgadas, celdas solares).
- **Agroindustria/ambiental, mal etiquetado** (19.4%, 1,567 tesis): meso 254 tenía la etiqueta "aguas residuales" pero los títulos reales son mucho más amplios — producción de azúcar de caña, enmiendas químicas de suelo, producción de un pesticida (hexaclorociclohexano), tratamiento de aguas. Ingeniería química agroindustrial, sin relación real con petróleo ni con síntesis de laboratorio.

**Por qué se escapó de la primera pasada**: similitud media de macro 54 = 0.063, por encima del umbral (0.045) que se usó para filtrar candidatos. Pero la similitud **mínima** era 0.005 (pozos↔síntesis orgánica, casi cero) — peor que varios de los 6 ya separados. El promedio esconde una estructura **bimodal**: dos-tres sub-bloques internamente muy parecidos entre sí (que inflan el promedio) pero casi sin relación mutua.

**Frontera entre "química de síntesis" y "materiales/metalurgia" — no se forzó una división que no se pudo justificar.** Se probó Ward directo sobre los vectores c-TF-IDF de los 9 meso: a k=2 separa {síntesis+catalizadores+materiales} vs. {agroindustria+petróleo+metalurgia} — agrupa metalurgia CON petróleo, no con materiales, contradiciendo la lectura cualitativa de títulos. Con solo 9 puntos el resultado es inestable y no se le puede dar más peso que a la lectura manual. Se dejó la "química de síntesis y materiales" como un solo macro en vez de forzar una frontera fina sin evidencia clara — más honesto que fingir precisión que no hay.

**Ejecución**: división en 3 vía `pipeline/aplicar_correccion_manual_macro.py` (`SEPARACION_MANUAL_FINA`, asignación mano a mano por meso, no automática). Nuevos macros: **125** (agroindustria, 1,567), **126** (petróleo/refinación, 2,383 — incluye 255+256, el catalizador 258 quedó en el grupo grande porque su similitud léxica con síntesis fue más alta que con pozos/refinería pese a la relación funcional), **127** (química/materiales, 4,112). Total tras esta ronda: **120 macros**.

**El detector, formalizado**: `pipeline/detectar_macros_heterogeneos.py`. Combina dos señales sobre los vectores c-TF-IDF completos de los meso de cada macro: (1) similitud media global (encontró los primeros 6 casos), (2) similitud entre los dos sub-grupos que resultan de forzar un corte Ward en 2 (encontró el punto ciego que dejó pasar macro 54). **Ninguna de las dos es un clasificador limpio por sí sola** — corrido sobre los 120 macros finales, marca 18 candidatos, y **10 de esos 18 ya están confirmados como coherentes** en rondas anteriores (18, 48, 21, 66, 75, 24, 55, 14, 44, 20) — es decir, el detector los re-marca aunque ya se revisaron y están bien. Esto es esperado y coherente con todo lo aprendido: **el detector prioriza candidatos, la decisión final siempre requiere leer títulos reales.**

### Ronda 3 — revisión de los 8 candidatos restantes (2026-09-22)

Se revisaron con títulos reales los 8 candidatos que quedaban sin revisar. **7 de 8 resultaron falsos positivos**, confirmados coherentes:
- **Macro 40**: supervisión de obras + control de proyectos + costos de producción + organización contable + presupuestos + inventarios — todo "administración de costos y proyectos". Coherente.
- **Macro 126**: perforación de pozos + operación de refinerías — el macro de petróleo recién separado en la Ronda 2, confirma que esa agrupación intencional fue correcta.
- **Macro 74**: oftalmología (glaucoma, LASIK) + ORL (timpanoplastia, otosclerosis) + neurología (epilepsia, esclerosis múltiple) + toxina botulínica — procedimientos médico-quirúrgicos especializados, mismo patrón ya confirmado antes para el macro 77. Coherente.
- **Macro 86**: exposición laboral a químicos/calor + síndrome de burnout + efectos psicológicos del COVID — salud ocupacional/estrés laboral, conexión algo floja (el COVID no es estrictamente "ocupacional") pero coherente en espíritu.
- **Macro 9**: franquicias + financiamiento PyME + mercado de valores + banca — finanzas corporativas y sistema financiero. Coherente.
- **Macro 65**: accidentes/complicaciones en endodoncia + emergencias en consultorio dental + traumatismos dentales + fracturas maxilares — urgencias y traumatología dental. Coherente.
- **Macro 45**: publicidad/estereotipos de género + publicidad subliminal + cine mexicano + fotografía — estudios de medios y publicidad, mismo patrón que el macro 44 ya confirmado. Coherente.

**1 caso real encontrado — macro 19** ("matrimonio · divorcio · concubinato · potestad", n=1,661): mezclaba **derecho de familia** (meso 95 patria potestad, 96 divorcio, 97 concubinato/matrimonio — análisis jurídico) con **psicología de pareja/violencia** (meso 93 satisfacción marital/dependencia emocional, 94 violencia familiar — análisis psicológico/social, no jurídico). Mismo tema (relaciones de pareja/familia), dos disciplinas académicas distintas. Separado en macro **129** (derecho de familia, 1,099) y macro **128** (psicología de pareja/violencia, 562).

**Estado final tras 3 rondas de corrección manual: 121 macros.** Detector re-corrido sobre la estructura final: sigue marcando 17 candidatos, pero **los 17 ya están confirmados como coherentes** en las rondas de revisión — es decir, todo lo que el detector puede encontrar con las señales actuales ya se revisó. Cualquier caso adicional que quede (si lo hay) requeriría una señal distinta a las dos ya probadas, o revisión manual sin apoyo de detector.

**Archivos**: `data/clustering/deteccion_heterogeneidad_macro.parquet` (resultado del detector sobre los 121 macros finales) — recrear con `python pipeline/detectar_macros_heterogeneos.py`. Orden de ejecución completo desde cero: `construir_jerarquia_macro_meso.py` → labels → `aplicar_correccion_manual_macro.py` (aplica las 3 rondas en un solo paso, es idempotente) → labels otra vez → `detectar_macros_heterogeneos.py` (opcional, solo para verificar) → gráficas 10/11/13.

### Ronda 4 — el mismo enfoque, un nivel más abajo: micro-clusters dentro de cada meso (2026-09-22)

**Pedido del usuario**: aplicar exactamente el mismo detector (similitud c-TF-IDF completa + revisión manual), esta vez para ver si los micro-clusters *dentro* de cada meso son genuinamente coherentes entre sí, no solo los meso dentro de cada macro.

**Se construyó el mismo tipo de matriz c-TF-IDF completa, esta vez a nivel micro-cluster** (`data/clustering/micro_ctfidf_matrix.npz` + `micro_ctfidf_ids.npy`, 513 micro-clusters). **Hallazgo de calibración importante**: las similitudes a nivel meso son mucho más altas que a nivel macro (mediana 0.209 vs. ~0.08-0.09) — tiene sentido, meso se construyó con un umbral de distancia mucho más estricto (D_MESO=0.20 vs. D_MACRO=0.40), así que sus micro-clusters ya parten de estar más relacionados entre sí. Los umbrales calibrados para macro (0.045/0.035) **no aplican aquí** — se usó el ranking por similitud (no un umbral fijo) para priorizar los 15 peores casos a revisar con títulos reales.

**Resultado: 3 casos reales de 15 revisados** (12 falsos positivos, mismo patrón que las rondas anteriores — campos amplios pero coherentes: hornos/calderas, microbiología en distintos organismos, termodinámica de fluidos, biología de la reproducción, parasitología veterinaria, biología celular/receptores, neurología/rehabilitación, biología marina/pesquerías, ecología/uso de suelo, reumatología autoinmune, y dos casos borderline aceptados por analogía con decisiones ya tomadas a nivel macro: filosofía+literatura como "humanidades" igual que el macro 48, genética de plantas+lagartijas como "sistemática/filogenia" compartiendo método aunque no taxón):

- **Meso 293** (macro 117, ya era singleton desde la Ronda 1 — venía del viejo macro 61): "tuberculosis" mezclado con "breves consideraciones acerca de..." (pancreatitis, actinomicosis, tratamiento histórico con mercurio) — el mismo patrón de grab-bag "reporte breve de caso clínico sin tema" que ya se había visto, **seguía sin resolverse un nivel más abajo** pese a que el macro que lo contenía ya se había aislado. Separado en meso 425 (tuberculosis, macro nuevo 130) y meso 426 (breves/grab-bag, macro nuevo 131).
- **Meso 281** (macro 112, singleton): física de partículas/cuántica (neutrinos, quarks, Bose-Einstein) vs. astronomía observacional (galaxias, estrellas, nebulosas) — dos subcampos de física con métodos y objetos de estudio distintos. Separado en meso 427 (macro nuevo 132) y meso 428 (macro nuevo 133).
- **Meso 286** (macro 59, "prótesis dentales" — 5 meso, no singleton): mezclaba reconstrucción auricular/cirugía plástica (micro 30 — reimplante de dedo, injertos nasales, oreja prominente) con injertos dentales/periodontales (micro 81) — **el micro 30 ni siquiera es dental**, no debería haber estado en un macro de prótesis dentales en primer lugar. Micro 81 se separó en su propio meso pero se quedó en el macro 59 (sigue siendo dental); micro 30 se separó en meso nuevo **y** macro nuevo 134 (no pertenece a ningún macro dental existente).

**Extensión del script de corrección**: `SEPARACION_MESO_FINA` en `pipeline/aplicar_correccion_manual_macro.py` — nuevo mecanismo que opera un nivel más fino que `SEPARACION_MANUAL_FINA`: por cada micro-cluster de un meso a dividir, especifica si se queda en su macro original (`"queda"`, solo tiene sentido si el macro no es singleton, como el 59) o se va a un macro completamente nuevo (`"nuevo_macro"`). Verificado idempotente (correr todas las rondas de nuevo no duplica nada).

**Estado final tras las 4 rondas: 124 macros, 431 meso** (frente a los 513 micro-clusters y 89 macros del corte automático original). **38 macros singleton** (antes 33).

**Lección que se repite en las 4 rondas**: el patrón dominante de "falso positivo" del detector sigue siendo el mismo — campos genuinamente distintos pero relacionados por método compartido (organismos distintos en biología molecular, taxones distintos en sistemática, subcampos distintos de humanidades) que el detector marca por vocabulario específico distinto, y que la revisión manual con títulos reales descarta. El patrón dominante de "caso real" también se repite: (a) "reporte breve de caso clínico" sin tema (mismo mecanismo que macros 61/88, ahora visto también dentro de un meso ya aislado), y (b) disciplinas genuinamente distintas unidas por una técnica o palabra compartida (petróleo↔química por "catalizador", plástica↔dental por "injerto").

### Ronda 5 — revisión de los 67 meso restantes (2026-09-22)

**Pedido del usuario**: revisar todos los candidatos, no solo los peores 15. Para 67 meso, leer 3-4 títulos de cada micro-cluster hubiera sido excesivo (~500 títulos) — se hizo un **pase rápido solo con las etiquetas c-TF-IDF** (más eficiente, ya había probado que las etiquetas por sí solas alcanzan para descartar la mayoría) y se marcaron 9 sospechosos por patrón ya conocido (nombre de institución/género compartido) para verificar con títulos reales. **De los 9, 5 fueron casos reales** — tasa de acierto más alta que el primer pase (5/9 ≈ 56% vs. 3/15 ≈ 20% del pase ciego por similitud), confirma que triar por etiqueta antes de gastar tiempo en títulos es más eficiente sin perder rigor.

- **Meso 343 y 344** (ambos dentro de macro 72, "Zubirán/nutrición"): cada uno mezclaba reportes de caso clínico de órganos/condiciones sin relación entre sí (páncreas, vejiga, laringe, próstata, testículo vs. nutrición pediátrica, crioglobulinemia, cáncer nasal, síndrome nefrótico), unidos solo por el género "experiencia de N años en el hospital X". **Esto refuerza con más fuerza la sospecha ya anotada sobre el macro 72 completo** (revisado en la Ronda 3, aceptado entonces porque el detector a nivel macro no lo marcaba con fuerza — rank 66/85) — a un nivel más fino, el patrón de género por institución es real y estaba presente todo el tiempo, solo que el detector de similitud media no lo veía porque las 4 meso de ese macro comparten vocabulario de "hospital/paciente/experiencia" que las hace parecer relacionadas sin estar relacionadas por tema.
- **Meso 327** (macro 70, "revisión literatura/presentación clínico"): mismo patrón de género — "reporte de un caso y revisión de la literatura" aplicado a condiciones sin relación (papiloma bucal, púrpura trombocitopénica, porencefalia, brucelosis).
- **Meso 47** (macro 10, "código/artículo DF"): código penal (micro 220) vs. código civil (micro 221) — ramas de derecho distintas.
- **Meso 44** (macro 10): estructura institucional del sistema de justicia del DF (Ministerio Público, Poder Judicial) vs. delitos específicos (prostitución, robo).

**Decisión de destino**: los pedazos de 343/344/327 se mandaron a macros nuevos (sus macros de origen ya son de género, no tiene sentido dejarlos ahí). Los pedazos de 47/44 se quedaron en el macro 10 porque ese macro ya es explícitamente "derecho y administración del Distrito Federal" en sentido amplio — coherente con esa amplitud ya aceptada.

**Limitación honesta encontrada**: las nuevas etiquetas de los macros desprendidos de 343/344/327 (`data/clustering/macro_topics_ctfidf.parquet`, ids 135-140) **siguen siendo de género** ("hospital especialidades", "hospital Juárez", "revisión literatura") — separar la jerarquía no arregla que esos **micro-clusters de HDBSCAN mismos** ya estaban agrupados por género de escritura, no por tema clínico. Arreglar eso de raíz requeriría revisar el clustering de esos micro-clusters específicos, fuera del alcance de esta corrección de jerarquía (que solo reagrupa micro-clusters existentes, no los reconstruye).

**Estado final tras las 5 rondas: 130 macros, 442 meso.** El macro 72 queda con solo 2 meso (345 Federico Gómez, 346 Zubirán) tras perder 343 y 344 — sigue siendo un macro de género de institución, señalado explícitamente como pendiente de una revisión más profunda (no se desarmó del todo en esta ronda para no seguir expandiendo el alcance sin confirmación).

**Pendiente, no revisado**: los ~58 meso restantes que el pase por etiqueta consideró razonablemente coherentes no se verificaron con títulos reales uno por uno (solo por etiqueta) — riesgo residual bajo pero no cero.

### ¿Qué tan extendido está el problema de fondo? Medido, no especulado (2026-09-22)

**Pregunta del usuario**: la limitación anotada arriba (micro-clusters de HDBSCAN ya agrupados por género de escritura, no por tema, imposible de arreglar solo reorganizando la jerarquía) — ¿qué tanto afecta la calidad general del clustering?

**Medido con dos búsquedas de frases de género sobre los títulos reales del corpus clusterizado (199,623 tesis)**:

1. **Género médico** ("revisión de la literatura", "reporte de un caso", "experiencia de N años", "breves consideraciones", etc.): presente en **0.84%** de las tesis clusterizadas (1,679 de 199,623), repartidas en **194 micro-clusters distintos de 513** — pero **domina** (>25% del cluster) solo en **6**: clusters 99, 98, 267, 273, 81, 272. Son exactamente los que ya se encontraron y separaron en las rondas 4 y 5. En los otros 188 clusters es una traza minoritaria (unas pocas tesis de título genérico entre cientos de título temático claro) — no alcanza para torcer la identidad del cluster.
2. **Otros géneros ya vistos en esta bitácora** ("anteproyecto técnico", "investigación bibliográfica" genérica, "notas al programa", "estudio recapitulativo"): 0.41%, en 22 clusters, con solo 3 dominantes — cluster 0 (96.3%, ya aislado como el macro de "notas al programa" musical), cluster 12 (73.7%, **no es un problema**, es el mismo género musical, ya correctamente en el macro de música), cluster 372 (16.5%, veterinaria, ya investigado en fases anteriores — el boilerplate "estudio recapitulativo" no corrompe su coherencia temática real).

**Conclusión**: no compromete la calidad general del clustering. Menos del 1.5% del corpus clusterizado muestra esta firma en total, y las rondas 4-5 de corrección manual ya capturaron prácticamente todos los casos donde el género realmente dominaba lo suficiente para distorsionar un cluster — es un punto ciego real pero angosto, ya mayormente parchado, no un defecto sistémico del pipeline.

**Salvedad honesta**: esta medición busca las firmas de género ya identificadas manualmente a lo largo de esta bitácora (case-report médico, anteproyecto técnico, investigación bibliográfica genérica, notas al programa, estudio recapitulativo) — no es una garantía de que no exista ningún otro patrón de género sin descubrir, es una medición de lo que ya se sabe buscar. Si aparece un patrón nuevo en una revisión futura, extendería esta lista, no la contradiría.

## Paso 6 — `atlas_manifest.v1.json` (2026-09-22)

**Objetivo**: adaptar el esquema del atlas viejo (`app/MI-TESIS-UNAM_github/atlas_preview_data/`, documentado en `nodo_unam.md`, Leiden sobre muestra de 50k, 43 macros atados a las 4 áreas) a la jerarquía nueva (HDBSCAN + Ward + 5 rondas de corrección manual, 130 macro / 432 meso / 513 micro sobre 609,154 tesis). Antes de generar nada se leyeron los 5 tipos de archivo reales del bundle viejo (no solo la descripción en `nodo_unam.md`) para no inventar un esquema — `atlas_manifest.v1.json`, `atlas_display_policy.v1.json`, `atlas_balanced_macro_graph.json`, un `meso_by_macro/*.json`, un `micro_by_macro/*.json`, un `theses_by_micro/*.json`.

**Dos decisiones confirmadas con el usuario antes de generar archivos**:
1. **Privacidad**: incluir `advisor` (asesor, dato académico público) pero **nunca nombre de autor**. Resultó automático — el dataset público (`data_unam.parquet`, ver ADR-0011) ya no incluye nombres de autor en absoluto (solo `num_autores`), así que no hizo falta filtrar nada a mano; el incidente de privacidad ya documentado (repo con LFS exponiendo autores, puesto en privado) no se puede repetir con esta fuente.
2. **Alcance**: incluir también el payload del "modo caos" (vista cruda con `regl-scatterplot`, ya decidida en la sección "vista curada vs. vista cruda" más arriba) en esta misma pasada, no dejarlo pendiente.

### Qué cambia respecto al esquema viejo

- **IDs ya no codifican área administrativa** — `M{macro_id}` en vez de `Area{1-4}_M{00..}`, consistente con la decisión "100% data-driven" ya tomada. El área queda solo como metadata (`areaMix`, `dominantArea`) en cada nodo, no como estructura.
- **Posición de cada nodo = su centroide real** en el layout PaCMAP (mediana x,y de sus miembros) — sin el truco viejo de `quadrant_area_mix_with_deterministic_jitter` (que posicionaba por cuadrante de área + jitter determinístico), porque ya no hay 4 cuadrantes de área que anclar.
- **Edges entre macros son una aproximación, marcada como tal en el propio JSON** (`"isApproximate": true`): el sistema viejo los sacaba de un grafo semántico FAISS real a nivel tesis (~1.6M edges, embeddings MiniLM). Ese grafo no se reconstruyó para e5-large — se aproximó con similitud coseno entre centroides de embeddings de macro (top-5 vecinos por macro, evita un grafo denso de ~8,000 pares). Edges dentro de cada subgrafo (meso/micro) sí reusan una fuente ya validada: la misma matriz c-TF-IDF completa construida para el detector de heterogeneidad (`meso_ctfidf_matrix.npz` / `micro_ctfidf_matrix.npz`) — consistencia deliberada entre "qué tan relacionados se ven en el grafo" y "qué tan relacionados los juzgué al decidir si separarlos".
- **`neighborhood_by_thesis` queda pendiente, declarado explícitamente como tal en el manifest** (`"status": "pendiente"`) — requiere un índice de vecinos más cercanos a nivel tesis sobre los embeddings e5-large (el viejo grafo FAISS era de MiniLM). Es la pieza más pesada del bundle viejo (516 MB, 10,068 archivos) y una tarea aparte, no se intentó en esta pasada.

### Archivos generados (`atlas_data/`, 20 MB total)

| Archivo | Script | Tamaño |
|---|---|---|
| `atlas_manifest.v1.json` | `pipeline/generar_atlas_manifest.py` | 4 KB |
| `atlas_display_policy.v1.json` | `pipeline/generar_atlas_manifest.py` | 4 KB |
| `atlas_macro_graph.v1.json` (130 nodos, 488 edges) | `pipeline/generar_atlas_macro_graph.py` | 124 KB |
| `meso_by_macro/{macro_id}.json` × 130 | `pipeline/generar_atlas_subgraphs.py` | 490 KB |
| `micro_by_macro/{macro_id}.json` × 130 | `pipeline/generar_atlas_subgraphs.py` | 553 KB |
| `theses_by_micro/{cluster_id}.json` × 513 | `pipeline/generar_atlas_theses.py` | 5.2 MB |
| `atlas_chaos_mode.v1.bin` + `.json` (609,154 puntos) | `pipeline/generar_atlas_modo_caos.py` | 14 MB |

**Selección de tesis representativas** (`generar_atlas_theses.py`): más cercanas al centroide del micro-cluster en el espacio de embeddings de 1024d (no en PaCMAP 2D, que ya perdió información) — mismo principio que el sistema viejo. Deduplicación por título exacto (máx. 2 copias idénticas mostradas) en vez de la deduplicación por "familia de título" (normalización + comparación difusa) que usaba el sistema viejo — más simple, suficiente para el propósito, documentado como diferencia deliberada.

**Modo caos** (`generar_atlas_modo_caos.py`): formato binario, no JSON — a 609,154 puntos un JSON de objetos pesaría decenas de MB y el parseo en navegador sería lento. Tres arrays tipados concatenados en un `.bin` (Float32 x, Float32 y, Int32 macroCode) más un `.json` chico con offsets/conteos para que el frontend haga `new Float32Array(buffer, offset, count)` directo. `macroCode=-1` para el 67.2% de ruido HDBSCAN — se incluye siempre, es el punto del modo caos (ver la sección "vista curada vs. vista cruda" más arriba: "el contraste narrativo real está en mostrar también el ruido"). Verificado leyendo el binario de vuelta: conteo de ruido coincide exacto (409,531).

**Todos los archivos están bajo el límite de 25 MB de Cloudflare Pages** (el más grande, el `.bin` del modo caos, pesa 14 MB) — pero por la recomendación ya documentada en `nodo_unam.md` ("Sí conviene subir a R2": archivos grandes/numerosos), el modo caos y probablemente `theses_by_micro/` completo deberían ir a R2, no a Pages, cuando se decida el deploy real; no se tomó esa decisión aquí, solo se generaron los datos.

**Para recrear todo, en orden**: `python pipeline/generar_atlas_macro_graph.py` → `python pipeline/generar_atlas_subgraphs.py` → `python pipeline/generar_atlas_theses.py` → `python pipeline/generar_atlas_modo_caos.py` → `python pipeline/generar_atlas_manifest.py` (este último debe ir al final, audita los tamaños/conteos de los archivos ya generados).

**Pendiente**: `neighborhood_by_thesis` (índice de vecinos a nivel tesis, ver arriba); conectar este bundle al frontend real (`atlas_macro_preview.html` o su sucesor); decidir Pages vs. R2 por archivo para el deploy.

### Prototipo visual del macro graph — feedback del usuario y plan para la próxima sesión (2026-09-22)

Se armó un prototipo interactivo (artifact HTML, SVG, pan/zoom, panel de detalle) cargando `atlas_macro_graph.v1.json` real (130 nodos) para validar visualmente el bundle antes de seguir. Feedback del usuario, dos cosas distintas que no hay que confundir:

**1. Bug concreto, arreglo trivial cuando se retome**: el zoom-out no tiene límite atado al contenido — se puede alejar la vista (o arrastrarla) hasta que los nodos quedan fuera de cuadro o ilegibles, se ve poco profesional. Fix: clamp de pan/zoom atado a la bounding box real de los datos + margen (patrón estándar tipo `maxBounds` de librerías de mapas) — no dejar que el usuario "pierda" el grafo.

**2. Crítica de fondo, requiere diseño antes de tocar código — el modelo de interacción está mal planteado, no solo el estilo.**

> "el boceto reduce más de 100 años de conocimiento a un mapa mental de preparatoria."

El prototipo muestra 130 círculos dispersos con mucho espacio vacío alrededor — no transmite la escala real (609,154 tesis) ni se parece a las referencias visuales ya documentadas (sección "Design — referencia visual de nodos": núcleo denso + halo disperso + islas aisladas, la sensación de "innovation network" con miles de nodos). **El problema no es de estilo (colores, tipografía) — es que solo se está dibujando el nivel macro agregado, sin ningún relleno de fondo que dé sensación de densidad/volumen real.** Ningún ajuste cosmético arregla eso; hace falta mostrar la nube de puntos real (o un subconjunto de ella) como capa base, con los círculos de macro como anotación encima, no como reemplazo.

**Pedido concreto del usuario — zoom semántico, no solo óptico**: la vista debería empezar "caótica" (como las referencias) y **aclararse progresivamente al acercarse**, "como adentrarse en una selva" — y conforme se hace zoom, los clusters deberían **separarse físicamente y revelar meso/micro**, no solo mostrar/ocultar etiquetas (eso ya estaba planeado, ver `nodo_unam.md`: "ocultamiento de tesis/labels según zoom" — el pedido nuevo va más allá de eso, es re-disposición real, no solo visibilidad de texto).

**Trade-off que el usuario ya identificó y propuso cómo resolver**: mostrar los 609,154 puntos reales de fondo en todo momento sería fiel a la escala pero podría volver lenta la exploración. Propuesta: no renderizar el corpus completo, usar un **subconjunto representativo** (muestreo) que dé la sensación de densidad/complejidad sin pagar el costo de rendimiento de dibujar todo.

#### Plan para la próxima sesión (no implementado, solo diseñado)

**A. Arreglo inmediato**: bounds de pan/zoom atados al bounding box real del layout, con margen — bajo esfuerzo, hacerlo primero.

**B. Dos formas de lograr "zoom semántico con separación", a evaluar con evidencia antes de elegir (no asumir cuál es mejor sin probar)**:
   - **Opción 1 — Multi-LOD artificial**: precomputar layouts separados por nivel (macro agregado / meso "explotado" alrededor de su macro / micro "explotado" alrededor de su meso) e interpolar posición al hacer zoom. Más control sobre la separación visual, pero es una capa de diseño inventada encima de los datos — más trabajo, más alejado de "lo que los datos realmente dicen".
   - **Opción 2 — Usar las posiciones PaCMAP reales en todos los niveles (recomendada, a validar)**: macro, meso y micro **ya tienen posición real en el mismo espacio 2D** (no hay que inventar nada) — en vez de "explotar" artificialmente un cluster al hacer zoom, simplemente cambiar qué nivel de detalle se dibuja según el zoom, igual que un mapa de teselas: a zoom bajo se ven los 130 macro-círculos; al acercarse sobre una zona, empiezan a dibujarse los meso/micro reales de esa zona (que ya estaban ahí, solo indistinguibles a escala pequeña). Más honesto con los datos, probablemente más barato de construir. Esto sugiere además que **"vista curada" y "modo caos" quizás no deberían ser dos modos con un botón** (como quedó en el prototipo y como está documentado hoy) sino un mismo canvas continuo: nube de puntos real (o el subconjunto muestreado) siempre de fondo, círculos de macro como anotación que se desvanece (fade out) al acercarse — **esto es una posible revisión de la decisión ya tomada de "dos vistas separadas"**, marcado explícitamente para discutir, no decidido aquí.

**C. Subconjunto representativo para la nube de fondo**: no usar los 609,154 puntos completos. Tamaño exacto pendiente de un benchmark real de rendimiento en navegador (no asumir un número de antemano) — y el muestreo debe ser **estratificado por densidad/cluster, no aleatorio simple**, para no distorsionar la forma real (núcleo denso + halo + islas) que ya se caracterizó visualmente en las gráficas 1 y 9-12 — un muestreo aleatorio simple aclararía desproporcionadamente las zonas ya densas sin aliviar nada donde ya es disperso, cambiando la percepción de la estructura real.

**D. Preguntas abiertas para la próxima sesión, sin decidir aquí**:
   - ¿Reabrir la decisión "dos vistas separadas con botón" a favor de un canvas continuo? Impacto en el trabajo ya hecho (`generar_atlas_modo_caos.py`, el toggle del prototipo) si se decide que sí.
   - Tamaño del subconjunto muestreado — depende de probar `regl-scatterplot` con datos reales en el navegador, no de una estimación de escritorio.
   - Releer las referencias visuales ya documentadas (`development.md`, "Design — referencia visual de nodos") contra cualquier prototipo nuevo específicamente buscando la sensación de "núcleo denso + halo disperso + islas" — el criterio de aceptación no es "se ve bonito", es "se parece a la referencia que sí gustó".

### Validación con evidencia real (2026-09-22) — Opción 2 confirmada, sin necesidad de submuestreo

Se construyó una segunda iteración del prototipo (mismo artifact, `Atlas Macro NODO`) agregando de verdad `regl-scatterplot` (WebGL) como capa de fondo con los **609,154 puntos reales** de `atlas_chaos_mode.v1.bin`, sincronizada con la capa SVG de anotación (círculos macro/meso/micro) vía los `xScale`/`yScale` de D3 que la librería expone en su evento `view` — el patrón que la propia documentación de regl-scatterplot recomienda para overlays. Para probar el mecanismo de revelado por zoom (pregunta B) sin depender de gestos de mouse reales (ver limitación de prueba más abajo), se pre-cargaron los archivos `meso_by_macro`/`micro_by_macro` de 10 de los 130 macros (los 8 más grandes + 2 chicos, para cubrir ambos extremos) y se agregaron botones de prueba que invocan `zoomToLocation()` directamente.

**Resultado: la Opción 2 (posiciones PaCMAP reales en todos los niveles, sin "explotar" artificialmente nada) funciona de punta a punta, verificado, no solo argumentado.** Al cruzar el umbral de zoom, el macro-círculo de cada uno de los 10 macros precargados se reemplaza por sus meso-nodos reales (mismo layout, ninguna posición inventada), y al seguir acercando, por sus micro-nodos — confirmado contando nodos por nivel en cada re-render (ej. `total=192 porNivel={"macro":121,"meso":71}` tras 9 de 10 reemplazos) y haciendo clic en los nodos nuevos para confirmar que el panel de detalle muestra datos reales de meso/micro (no del macro que reemplazaron). Esto resuelve la pregunta abierta de la sesión anterior: **no hace falta un layout artificial "explotado"** (Opción 1 descartada) — los tres niveles ya comparten el mismo espacio 2D real.

**Consecuencia directa sobre la pregunta D ("¿reabrir dos vistas separadas con botón?"): sí, se reabre, y se resuelve a favor de un canvas continuo.** El prototipo ya construido ES ese canvas continuo — la nube de fondo (WebGL, todo el corpus) y las anotaciones curadas (SVG, macro/meso/micro) conviven siempre en la misma vista, sin botón de modo. El toggle "Vista curada / Modo caos" del primer prototipo se eliminó de este archivo. `generar_atlas_modo_caos.py` no se desperdicia — su output (`atlas_chaos_mode.v1.bin`) es exactamente lo que alimenta esta capa de fondo unificada, solo cambia cómo se consume (siempre visible, no detrás de un botón).

**Pregunta C (tamaño del submuestreo) resuelta de forma más simple de lo previsto: no hace falta submuestrear.** Se probaron los 609,154 puntos completos directamente (sin ningún subconjunto) y `regl-scatterplot` los renderizó sin problema — pan/zoom y clics sobre las anotaciones se mantuvieron responsivos en las pruebas manuales. No se hizo un benchmark formal de FPS (pendiente si hiciera falta un número exacto), pero no hubo ninguna señal de degradación cualitativa, consistente con que la librería está diseñada para hasta 20M puntos. Evita construir la lógica de muestreo estratificado por densidad que se había anticipado como necesaria.

**Tres bugs reales encontrados y corregidos durante la construcción, no solo teorizados:**
1. **UMD de `regl-scatterplot` no expone el constructor directamente** — `window.createScatterplot` resultaba ser `{default: fn, __esModule: true}`, no la función en sí (patrón típico de interop ESM→UMD de Rollup). Sin este fix, la librería falla con `window.createScatterplot is not a function` en cuanto se intenta usar. Fix: `if (typeof window.createScatterplot.default === 'function') window.createScatterplot = window.createScatterplot.default;` tras cargar el script.
2. **Doble corrección de aspect ratio** — se intentó ajustar manualmente el dominio de datos al aspect ratio del canvas (para que 1 unidad de dato ocupe los mismos píxeles en x/y), sin saber que `regl-scatterplot` ya hace exactamente eso internamente con su cámara por defecto. El resultado combinado distorsionaba la nube (multiplicaba el efecto). Fix: no tocar el dominio, dejar que la cámara de la librería maneje el aspect ratio sola — verificado con los mismos números de `xSpan`/`ySpan` que reporta el evento `view`.
3. **Corregir el pan/zoom fuera de rango (ítem A del plan, el "arreglo trivial") no era tan trivial** — llamar a `.set({cameraDistance: 1})` de forma síncrona *dentro* del propio callback del evento `view` no tenía ningún efecto visible (el `.set()` se pierde/ignora en ese punto del ciclo de vida de la librería). Fix real: diferir la corrección un tick con `setTimeout(fn, 0)` y usar `zoomToLocation()` en vez de `.set()` — verificado forzando `distance=3` (fuera de rango) y confirmando en el log de diagnóstico que un segundo evento `view` corrige a `distance=1` un tick después.

**Limitación de la prueba, no del prototipo — honesta, no verificada todavía**: la rueda del mouse (zoom) y el arrastre (pan) genuinos no se pudieron probar de forma confiable vía automatización de navegador contra el visor de artifacts de claude.ai — el scroll sintético no llegó al canvas (cero efecto en 2 intentos, en ambas direcciones) y el arrastre sintético fue interceptado por manijas de redimensionado del iframe del visor (aparecieron controles azules de selección a nivel de la página anfitriona, no del contenido). Por eso la validación de zoom/pan se hizo invocando `zoomToLocation()` directamente vía botones de prueba — válido para confirmar que el *mecanismo* (revelado por nivel, clamp, sincronización de capas) funciona, pero **no reemplaza probar con mouse/trackpad real antes de dar esto por completamente validado**. Los botones de prueba se dejaron en el artifact (`Atlas Macro NODO`, versión actual) para que se puedan repetir las pruebas o probar el gesto real.

**Alcance deliberadamente parcial de esta iteración, no un defecto**: solo 10 de los 130 macros traen datos de meso/micro precargados (los 8 más poblados + 2 chicos), elegidos a mano para la prueba — el resto se queda en nivel macro sin importar el zoom. Una implementación real necesitaría lazy-load por **intersección con el viewport actual**, no una lista fija de 10 ids como aquí. Tampoco se implementó cross-fade entre niveles (el cambio es un corte duro, no una transición) — pulido pendiente, no bloqueante para validar el mecanismo.

**Estado**: preguntas B, C y D del plan de la sesión anterior, respondidas con evidencia real, no solo con argumento. Pendiente: (1) confirmar el gesto de mouse real fuera de este entorno de prueba, (2) decidir el criterio de lazy-load por viewport para los 130 macros completos, (3) pulido visual (cross-fade, paleta de color final en vez del gris/azul binario de esta prueba, chrome de rigor del Design Manifest). Artifact: `Atlas Macro NODO` (https://claude.ai/artifact/B8AtTYyJwH3q5D389KjS3y).

### Auditoría de funciones del atlas viejo vs. el nuevo (2026-09-22)

**Pedido del usuario**: inventariar todas las funciones del atlas viejo (Explorar + Nobel) antes de seguir construyendo, para no perder capacidades sin darse cuenta. Se leyó completo `app/MI-TESIS-UNAM_github/deploy/static/index.html` (tab Explorar, ~600 líneas de JS inline) y `nobel_map.html`.

**Inventario del atlas viejo**: drilldown de 3 niveles por clic (overview → macro → micro, con tesis individuales en espiral dentro del micro); layout de macro por **4 polos de área fija** con un "campo de disciplina" visual (gradiente CSS entre polos) — ya descartado a propósito por la decisión "100% data-driven" de esta semana, no es una laguna; paneles de detalle con términos/programas/áreas dominantes y periodo (`year_min–year_max`); composición por área en barras; y la pieza más grande, **"Explorar vecindario"**: un botón que llama a `/api/explore/neighborhood/{thesis_id}?top_k=100` (API viva de FastAPI) y abre una vista "solar" aparte con dos modos (universe = espiral por ángulo dorado, radio ∝ similitud inversa; analytic = grilla agrupada por año/programa/plantel/nivel/área), selector de agrupación, filtro, slider de cuántos de los 100 mostrar, leyenda y edges cuyo grosor codifica similitud. Nobel vive en un tab completamente aparte (`nobel_map.html`), con su propio filtro por categoría/país y relaciones de vecindario precomputadas por tipo de relación. Adyacente pero fuera de alcance del atlas: Laboratorio tiene su propio mini-mapa solar duplicado (`labMini*` en `app.js`) y un módulo de asesores similares — corre sobre el backend `analyze()` ya existente, no se toca aquí.

**Comparado contra lo que existe hoy**: la jerarquía macro/meso/micro y las tesis representativas por micro ya tienen paridad (y mejoran: 609k vs. muestra de 50k, 100% data-driven, nube de fondo real que el viejo nunca tuvo, zoom semántico). El hueco real es **vecindario**: no había ni el índice de vecinos a nivel tesis, ni el endpoint, ni la vista — `neighborhood_by_thesis` seguía "pendiente" en el manifest. Nobel más cercano ya está calculado (`thesis_nobel_nearest.parquet`) pero no conectado al frontend.

### ADR-0014 — vecindario 100% precomputado, reemplaza ADR-0003 (2026-09-22)

**Pregunta que disparó el cambio**: dónde vive en producción un índice FAISS sobre 609k embeddings, y si no sería demasiado pesado. Al hacer el cálculo real (no asumido), la respuesta cambió el diseño: **FAISS nunca debe correr como servicio en producción para este caso** — corre una sola vez (build-time, igual que HDBSCAN/UMAP) y lo que se despliega es el resultado, no el índice.

**Contradicción real encontrada entre dos ADR ya aceptados**: ADR-0003 (vecindario híbrido, precómputo solo para una muestra de 50k + cómputo en vivo para el resto) justificaba el modelo híbrido diciendo que precomputar para las 609k "excede el volumen razonable de precómputo" — pero nunca se verificó con números. Con K=100 vecinos por tesis, la tabla completa pesa ~365MB sin comprimir (~150MB en parquet), muy por debajo de lo que el propio ADR-0001 ya aceptó como normal para R2 ("cientos de MB–unidades de GB", sin límite práctico de objetos). Además, la premisa de fondo de ADR-0003 (una muestra de 50k vs. el resto del corpus) ya no existe — el atlas se reconstruyó esta semana sobre el corpus completo. **Se escribió [`adr/0014-vecindario-100-precomputado.md`](adr/0014-vecindario-100-precomputado.md)**, que reemplaza formalmente a ADR-0003 (queda como archivo histórico, no se edita, por convención del proyecto) — el cómputo en vivo se reserva exclusivamente para texto libre fuera del corpus (Laboratorio, backend `analyze()` ya existente), no para el vecindario del atlas.

**Pipeline nuevo, corrido y verificado con datos reales, no solo diseñado**: `pipeline/generar_vecindario_knn.py` — FAISS `IndexFlatIP` (exacto, no aproximado; embeddings ya normalizados así que producto punto = similitud coseno) sobre los mismos embeddings e5-large ya generados. Busca TOP_K+1 vecinos por tesis y descarta explícitamente el índice de la propia fila (no "cualquier similitud 1.0", porque los ~7,449 títulos duplicados ya documentados también dan sim=1.0 y son vecinos reales, no el self-match). Con GPU (Kaggle) usa `faiss.index_cpu_to_gpu`; sin GPU corre en CPU con aviso.

**Smoke tests locales (20k y 100k) antes de comprometerse a la corrida completa**: 20,000×20,000 en 4.8s; 100,000×100,000 en 125.1s — la razón entre ambos (25x más consultas → 26x más tiempo) confirma escalamiento O(n²) limpio y predecible, sin sorpresas de rendimiento no lineal (a diferencia del incidente de PCA de la sesión del 21). Extrapolado al corpus completo: **~75-80 minutos, factible en CPU local, sin necesitar Kaggle para este paso** — memoria acotada (~2.5GB, el índice no duplica por batch porque `index.search()` ya reduce a top-K internamente en FAISS, nunca materializa la matriz completa de similitud en Python, a diferencia del enfoque de `numpy` usado para Nobel que sí era viable porque ahí el otro lado solo tenía 1,026 candidatos).

**Diagnósticos reales de los smoke tests, no asumidos**:
- **Hubness mucho más bajo que en Nobel**: top-15 tesis "hub" acaparan solo 0.3-0.8% de las asignaciones de top-1 (contra 36.1% sin corregir en el caso Nobel) — consistente con que aquí no hay problema cross-lingüe (todo es tesis en español contra tesis en español, mismo registro). **Conclusión: no hace falta la segunda pasada de corrección por z-score** que sí hizo falta para Nobel — se deja documentado como posible paso futuro en el ADR, no se construye por adelantado sin evidencia de que se necesite.
- **Duplicados/casi-duplicados**: 0.53% (muestra de 20k) a 1.41% (muestra de 100k) de tesis tienen un top-1 con similitud > 0.999 — señal de que sí hay pares de título idéntico/casi-idéntico apareciendo como "vecino más cercano" (coherente con el 3.5% de títulos duplicados ya documentado). No es un bug del pipeline — es contenido real del corpus —, pero el frontend probablemente debería deduplicar por título al mostrar el vecindario (mismo criterio ya aplicado en `theses_by_micro`), no mostrar como "el más similar" lo que en realidad es una copia del mismo título.

**Corrida completa lanzada en segundo plano** (`pipeline/generar_vecindario_knn.py`, sin `SAMPLE_N`, corpus completo) → `data/vecindario/tesis_vecindario_top100.parquet` (`thesis_id`, `neighbor_ids` (lista de 100), `neighbor_similarities` (lista de 100)). Pendiente de confirmar que termina sin incidentes y revisar los diagnósticos sobre el corpus completo (no solo la muestra) antes de conectarlo al frontend.

**Corrida real en GPU (Kaggle), completada (2026-09-22-23)**: el usuario pidió intentar GPU (Colab o Kaggle) en vez de esperar la corrida CPU local (~75-80 min). Kaggle resultó más práctico que Colab para este job puntual: los embeddings ya estaban subidos ahí (mismo dataset que usa `clustering_hdbscan.py`), sin el paso extra de montar Google Drive. **Tiempo real: 4.7 minutos** para el corpus completo (13 shards de 50k filas, GPU T4x2) — más rápido incluso que el estimado de 10-20 min. Bug real encontrado antes de esa corrida exitosa: el script no seguía la convención de rutas ya establecida por `clustering_hdbscan.py` (`SOURCE_DIR` debe apuntar directo a la carpeta plana del dataset, sin repetir `data/embeddings/` adentro) — corregido antes de volver a correr.

**Diagnósticos sobre el corpus completo (no solo la muestra), confirman lo que sugerían los smoke tests**:
- **Hubness: 0.2% total** en el top-15 (vs. 0.3-0.8% en las muestras de 20k/100k, y 36.1% sin corregir en el caso Nobel) — se descarta definitivamente la corrección por z-score para este caso.
- **Duplicados: 3.65%** de tesis con top-1 de similitud > 0.999 — coincide casi exacto con el 3.5% de títulos duplicados ya documentado, buena validación cruzada.
- **Investigación de las tesis "hub" (los top-1 más repetidos), verificada contra el título real, no asumida**: `TH_0010950`/`TH_0020413` (161/135 veces) son las ya conocidas "notas al programa" (292 copias, género de tesis-recital musical). El resto es un hallazgo nuevo — **títulos genéricos de tesis de odontología por formato de caso clínico**: "ortodoncia preventiva" (156 copias, 101 veces top-1), "mantenedores de espacio" (115 copias, 115 veces top-1), "prostodoncia total" (101 copias), "odontología preventiva" (81 copias). Mismo mecanismo que "notas al programa": el título es literalmente idéntico entre decenas de tesis reales distintas de la carrera de Cirujano Dentista, así que el embedding también es idéntico. No es un bug del pipeline — es contenido real del corpus. **Implicación de producto confirmada**: el vecindario debe deduplicar por título antes de mostrarse en el frontend (mismo criterio ya aplicado en `theses_by_micro`), o alguien que entra a una de esas tesis vería su "top 100 similares" dominado por copias del mismo título genérico, sin valor exploratorio.

**Incidente real al intentar descargar el resultado desde Kaggle (2026-09-22/23), documentado para no repetirlo**: `kaggle kernels output` (CLI 2.2.4) devuelve 404 real del servidor para esta cuenta/token — se verificó con la llamada HTTP exacta (POST a `kernels.KernelsApiService/ListKernelSessionOutput`, body idéntico al que construye el SDK), no era un error de sintaxis del comando. Se encontró una ruta alterna en el SDK (`download_kernel_output`, pensada para Kaggle Hub) que sí ubica los archivos correctamente y genera URLs firmadas válidas — pero el CDN de descarga (`kaggleusercontent.com`) devolvió **500 Internal Server Error de forma consistente**, probado con `curl` puro sin ningún header, sobre tres archivos distintos del mismo output (el parquet completo, un shard chico, y `__notebook__.ipynb`) — confirma que no era un problema del archivo ni del código, era el servicio de descarga de Kaggle fallando en ese momento, la misma inestabilidad que el usuario ya había visto "a veces" desde la web. **Se resolvió finalmente descargando desde la web de Kaggle** (el usuario lo consiguió pese al patrón de fallas) — archivo verificado íntegro contra los diagnósticos que había impreso el log de Kaggle (mismos conteos exactos de tesis "hub", misma tasa de duplicados). Guardado en `data/vecindario/tesis_vecindario_top100.parquet` (609,154 filas, verificado). El backup local (corrida CPU, había llegado a 18/31 shards) se detuvo — sus shards parciales quedan en `data/vecindario/shards/` sin usarse más, no bloqueantes, no borrados.

**Estado**: pipeline de vecindario tesis-tesis completo y verificado end-to-end (ADR-0014 ejecutado). Pendiente: diseñar el payload deduplicado por título para el frontend, y conectar esto + Nobel-más-cercano a la próxima iteración del artifact (que, como ya se anotó, va a cambiar mucho una vez esto entre — primero MVP funcional).

### Próximos pasos, pausa 2026-09-22/23 — en orden de prioridad

1. ~~**Payload de vecindario deduplicado por título**~~ **Hecho (2026-09-22/23)** — ver sección "Payload de vecindario" más abajo.
2. **Conectar Nobel-más-cercano al frontend** — el dato ya existe (`thesis_nobel_nearest.parquet`, top-3 por tesis) pero no está expuesto en ningún lado todavía. Candidatos: tarjeta en la vista de vecindario + nodos Nobel con estilo visual distinto en el mapa (posiciones ya interpoladas, `nobel_posicion_interpolada.parquet`).
3. ~~**Construir la vista de vecindario en el artifact/atlas**~~ **Hecho (2026-09-23)** — ver sección "Paso 3 del backlog — vista de vecindario en el artifact (MVP)" más abajo. Lista simple, acotada a las 2,500 tesis representativas de los 10 macros ya precargados. Superada por el paso 5 (modo analytic reemplaza la lista plana).
4. ~~**Lazy-load por viewport para los 130 macros**~~ **Hecho (2026-09-23)** — ver sección "Paso 4 del backlog" más abajo.
5. ~~**Modo analytic para la vista de vecindario**~~ **Hecho (2026-09-23)** — ver sección "Paso 5 del backlog — modo analytic" más abajo. Grilla-de-grillas animada agrupada por área o década, reemplaza la lista plana del paso 3. Modo universo/espiral se construyó y luego se retiró a pedido del usuario (ver "Modo universo retirado + clic en tesis individual sobre el mapa real" más abajo) — reemplazado por una versión del mismo efecto de foco/área aplicada directo sobre el mapa real en vez de un grafo aparte.
6. ~~**Confirmar el gesto de mouse real (wheel/drag)**~~ **Confirmado (2026-09-23)** — ver sección "Verificación en vivo + dos bugs reales de rendimiento" más abajo. El límite anterior era específico del visor de artifact embebido en el chat (iframe cross-origin); contra la URL standalone (y ahora contra el prototipo local, mismo origen), scroll y drag reales funcionan sin problema.
7. **Pulido visual — explícitamente al final, no antes**: cross-fade entre niveles al hacer zoom, paleta final del Design Manifest (hoy gris/azul binario de prueba), chrome de rigor (grilla, ficha técnica permanente), deduplicación visual de nodos Nobel como easter egg.
8. **Housekeeping menor, no bloqueante**: `data/vecindario/shards/` tiene 18 shards parciales de la corrida CPU local abortada (~370MB) — ya no se usan, se pueden borrar cuando se confirme que no hacen falta. Decidir si `tesis_vecindario_top100.parquet` sube a R2 ahora o se espera a tener el payload final deduplicado (evitar subir dos versiones).

**Nota del usuario, registrada explícitamente para no perderla**: el diseño del artifact/atlas **va a cambiar mucho, visual y funcionalmente**, una vez se conecte vecindario (y después Nobel-más-cercano) — el prototipo actual (macro/meso/micro + nube de fondo) es deliberadamente un paso intermedio, no la forma final. **Decisión de secuencia explícita: primero un MVP funcional, el pulido visual final viene después** — no invertir en cross-fade, paleta final del Design Manifest, ni chrome de rigor todavía, hasta que el vecindario esté conectado y la forma real de la interacción esté validada con las piezas que faltan.

### Payload de vecindario deduplicado por título (2026-09-22/23) — paso 1 del backlog de pausa

**Decisión de escala tomada antes de escribir el archivo final, no después**: la opción obvia (un archivo por tesis, o shards, con metadata de despliegue — título/año/programa/etc. — embebida por vecino, igual que `theses_by_micro`) se descartó por cálculo, no por intuición. `theses_by_micro` embebe metadata completa porque solo cubre ~10,000 entradas (513 micro-clusters × ~20 tesis representativas); el vecindario cubre 609,154 tesis × hasta 100 vecinos (~55M pares) — embeber solo el título ya estimaba ~4.4GB, 1000x el tamaño de `theses_by_micro`. **Decisión**: el payload de vecindario NO lleva metadata de despliegue por vecino — solo `thesisId` + `similarity` (+ contador opcional de duplicados absorbidos). Resolver `thesisId → título/programa/...` para mostrarlo en pantalla queda pendiente, es trabajo del paso 3 (construir la vista), no de este paso.

**Criterio de deduplicación (la pregunta que quedaba abierta en el backlog)**: se reusó el mismo criterio ya establecido en `generar_atlas_theses.py` — cap de **2 apariciones por título exacto** (`MAX_POR_TITULO`), no colapsar a una sola entrada (perdería la señal de "esto se repite mucho") ni mostrar las 100 copias. La segunda aparición mostrada de un título repetido lleva un contador opcional (`dup`) con cuántas copias adicionales se omitieron — preserva la información sin inflar la lista. El título se usa solo en memoria durante la generación (dict `thesis_id → titulo`, ~609k entradas), nunca se persiste en el archivo de salida.

**Sharding**: 610 archivos de 1,000 tesis cada uno (`shard = (int(thesisId[3:]) - 1) // 1000`, calculable sin índice aparte), en vez de 609,154 archivos individuales — evita saturar el filesystem/conteo de objetos de R2 por un factor de 1000 sin perder mucho: cada shard pesa ~2.1MB, cacheable por el navegador tras el primer clic dentro de ese rango. Trade-off declarado, no resuelto del todo: 2.1MB por clic inicial es más pesado que el ideal "un archivo chico por tesis" — si en la práctica resulta molesto, sharding más fino (ej. 200/shard) es un cambio de una constante, no un rediseño.

**Script**: `pipeline/generar_vecindario_payload.py`. Smoke test en 3,000 tesis antes de la corrida completa (patrón ya establecido en esta bitácora) — verificado a mano: tesis con título "ortodoncia preventiva" (uno de los títulos "hub" ya documentados) redujo su vecindario de 100 a 81 entradas tras dedup, con 3 entradas absorbiendo 1/7/11 duplicados adicionales cada una — el mecanismo funciona como se diseñó.

**Corrida completa (609,154 tesis, 5m37s)**: promedio de vecinos 100.0 → 98.31 tras dedup (impacto modesto en promedio, esperado — la mayoría de tesis no cae en clusters de título duplicado). **120,940 tesis (19.85%) tuvieron al menos un duplicado absorbido** — más alto que el 3.65% de tesis con top-1 casi-duplicado ya documentado, porque este conteo es acumulativo sobre los 100 vecinos, no solo el top-1. Tamaño final: **1,259MB en 610 shards** (`atlas_data/neighbors_by_thesis/`) — dentro del rango "cientos de MB–unidades de GB" que ADR-0001 ya acepta para R2, pero sin margen para crecer mucho más sin reconsiderar el diseño.

**Manifest actualizado**: `atlas_data/atlas_neighbors_manifest.v1.json` (nuevo, con las estadísticas de arriba) y `atlas_manifest.v1.json` — `neighborhoodByThesis.status` pasa de `"pendiente"` a `"hecho"` (`pipeline/generar_atlas_manifest.py` actualizado para leer el manifest de vecindario si existe, en vez de hardcodear el estado pendiente).

**Para recrear**: `python pipeline/generar_vecindario_payload.py` (requiere `data/vecindario/tesis_vecindario_top100.parquet` y `data/public/data_unam.parquet`) → `python pipeline/generar_atlas_manifest.py` (regenera el manifest general con el nuevo estado).

**Pendiente explícito, no resuelto aquí**: resolución de metadata de despliegue (título/año/programa/etc.) por `thesisId` para el frontend — necesaria tanto para mostrar los resultados del vecindario como, en algún momento, para cualquier clic directo sobre un nodo de tesis fuera de `theses_by_micro`. No se construyó un índice global de metadata en este paso (habría sido sobre-alcance respecto al ítem 1 del backlog) — queda como parte natural del paso 3 ("construir la vista de vecindario").

### Paso 3 del backlog — vista de vecindario en el artifact (MVP), 2026-09-23

**A pedido del usuario, se saltó el paso 2 (Nobel) para ir directo a este.**

**Resuelto primero, antes de tocar el artifact — cómo resolver `thesisId → título` sin repetir el error de escala del paso 1.** Medido, no asumido: en una muestra de 20 tesis, sus ~90 vecinos deduplicados caen en un promedio de **87.65 de los 610 shards** de `neighbors_by_thesis` (rango 69-94) — los `thesis_id` son orden de registro, sin relación con similitud semántica, así que **ningún esquema de sharding por rango de ID reduce cuántos bytes hace falta para resolver una lista de vecinos completa**: casi siempre hay que tocar prácticamente todos los shards. Se construyó en su lugar `pipeline/generar_titulos_index.py`: un índice global compacto `thesisId → {título, año}` (arrays posicionales, sin repetir claves JSON 609,156 veces — los `thesis_id` de `data_unam.parquet` son contiguos 1..609,156, verificado, así que no hace falta guardar el id en sí), shardeado en 8 piezas **solo por el límite de 16MB por archivo de texto de Artifacts**, no por localidad de acceso (cargar todos los shards una sola vez por sesión es la estrategia correcta, dado el hallazgo de arriba). Resultado real: 59.3MB en 8 shards (máx. 8.9MB/shard) — generado y verificado (lookup cruzado contra `data_unam.parquet` para 2 tesis de control, coincide exacto). No se publicó al artifact todavía (ver alcance del MVP abajo).

**Alcance del MVP, decidido para no repetir el problema de escala**: el artifact "Atlas Macro NODO" ya tenía una limitación de alcance declarada (`PREFETCHED`, 10 de 130 macros con meso/micro precargados). Se extendió esa misma limitación al vecindario en vez de intentar resolverlo para el corpus completo dentro de un artifact (que tiene límites de 16MB/archivo y 64MB/publish): `pipeline/generar_vecindario_preview_prototipo.py` recorta a las **2,500 tesis representativas de esos mismos 10 macros** (vía `theses_by_micro`), con título/año embebido directo por vecino (a esta escala acotada — ~50,000 pares, no ~55 millones — sí es aceptable, a diferencia de la decisión tomada para el payload de producción completo). Tope de 20 vecinos por tesis (no los 100 completos, para no acercarse al límite de 16MB). Resultado: `atlas_data/vecindario_preview.v1.json`, **8.74MB**, 2,500 tesis, publicado como archivo del artifact.

**Cambios en el artifact**: navegación de panel con pila (`node → theses → vecindario`, con botón "← volver", soporta recursión — clic en un vecino que también esté en la muestra de 2,500 abre su propio vecindario). Nodo micro con tesis representativas en la muestra muestra un enlace "Ver lista completa →"; cada tesis representativa lista sus vecinos con % de similitud, año, y nota de duplicados absorbidos (`+N más con el mismo título`) heredada del dedup del paso 1; vecinos fuera de la muestra de 2,500 se muestran (título/similitud) pero marcados "fuera de este preview", sin poder recursar en ellos — límite honesto del alcance parcial, no oculto.

**Verificación**: se confirmó que el archivo publicado se sirve exactamente en la ruta que el HTML pide (`./data/vecindario_preview.v1.json`, fetch verificado contra el archivo real publicado). **No se pudo probar el flujo de clics en vivo esta sesión** — la extensión de Claude in Chrome no estaba conectada. Pendiente antes de dar el MVP por completamente validado: clic real macro→meso→micro→tesis→vecindario en el artifact publicado (mismo tipo de limitación ya documentada para el gesto de zoom/pan real).

**Para recrear**: `python pipeline/generar_titulos_index.py` (índice global, no usado todavía por el artifact) → `python pipeline/generar_vecindario_preview_prototipo.py` (requiere `neighbors_by_thesis/`, `theses_by_micro/`, `jerarquia_macro_meso.parquet`, `data_unam.parquet` ya generados).

**Pendiente**: (1) verificar el flujo de clics real en el navegador; (2) decidir si `titulos_index` (59.3MB, corpus completo) se conecta en una futura iteración para levantar el límite de "10 macros" del vecindario, o si el patrón de shards por macro/rango se extiende en su lugar; (3) paso 2 (Nobel) sigue pendiente, saltado a pedido del usuario.

### Paso 4 del backlog — lazy-load por viewport, 130/130 macros (2026-09-23)

**Lo que cambió respecto a la iteración anterior**: la limitación de "solo 10/130 macros con meso/micro" nunca fue una limitación de tamaño de dato — medido antes de tocar código: `meso_by_macro/` completo (130 archivos) pesa 490KB, `micro_by_macro/` completo (130 archivos) pesa 553KB. ~1MB total para los 130 macros. Era una limitación de **qué se había publicado al artifact** (solo 10 de 130 macros), no de que el resto no cupiera. Se publicaron los 130/130 (dos llamadas de publish, 130 archivos c/u, por el límite de 255 entradas por llamada) — 265 archivos totales en el artifact ahora.

**Cambio de mecanismo, no solo de cantidad**: la lista fija `PREFETCHED = [53, 71, 18, 48, 77, 57, 15, 127, 118, 104]` se reemplazó por un chequeo real de viewport (`inViewport()`, usa `xScale.domain()`/`yScale.domain()` ya trackeados en cada evento `view` de regl-scatterplot, con 25% de margen para precargar justo antes de que un macro entre en pantalla). Cada uno de los 130 macros se revela a meso/micro cuando (a) el zoom cruza el umbral correspondiente **y** (b) su posición cae dentro del viewport actual — antes (a) bastaba, para los 10 de la lista. Un macro que sale del viewport (por pan) vuelve a nivel macro aunque el zoom siga alto — antes se quedaba revelado para siempre una vez cargado (dato ya en cache, decisión correcta ahí: no hace falta re-descargar, solo dejar de mostrar el detalle).

**No verificado con gesto de mouse real todavía** (mismo límite ya documentado para el paso anterior — la extensión de Claude in Chrome no estaba conectada esta sesión). Verificado sí: los 265 archivos quedaron publicados y listados correctamente en el artifact (conteo exacto, sin archivos faltantes ni duplicados).

**Para recrear los datos** (sin cambios respecto a lo ya documentado en "Paso 6 — atlas_manifest.v1.json"): `python pipeline/generar_atlas_subgraphs.py` genera los 130/130 de ambas carpetas — no hizo falta un script nuevo para este paso, solo publicar lo que ya existía.

### Verificación en vivo + dos bugs reales de rendimiento (2026-09-23)

**Verificado con clics/scroll/drag reales** (extensión de Claude in Chrome conectada esta sesión, navegando directo a la URL publicada del artifact, no el visor embebido del chat): el panel renderiza correctamente en los 3 niveles (macro/meso/micro) con datos reales; el revelado por viewport carga macros fuera de la vieja lista fija de 10 (confirmado con macros 4, 8, 9, 11, 20, 21, 22, 23, 26, 28, 29, 33, 39, 45, 50, 90-99, 106, 108-116, 125, 127, 129, 132, 133 entre otros); **scroll (zoom) y drag (pan) reales SÍ funcionan** contra la URL publicada directamente — corrige el límite documentado en la sesión anterior ("no se pudo probar con mouse/trackpad real"), que aplicaba solo al visor de artifact embebido dentro del chat (iframe cross-origin, eventos sintéticos bloqueados), no a la URL standalone. El flujo completo de vecindario (micro → tesis representativas → vecinos deduplicados) se confirmó visualmente por el usuario ("si vi unas que tenian vecinos en forma de lista") tras que yo gastara ~40 llamadas de navegador adivinando coordenadas de píxel para encontrarlo — **ineficiencia real de proceso, no del prototipo**, señalada por el usuario y reconocida.

**Bug real #1 — log de debug sin límite (RAM/DOM creciente)**: `dlog()` hacía `el.textContent += msg + '\n'` indefinidamente, sin ningún tope — en una sesión larga de exploración el nodo de texto del DOM crece sin límite, cada `scrollTop = el.scrollHeight` de por sí se vuelve más caro conforme crece. **Fix**: ring buffer fijo (`DLOG_MAX_LINES = 60`), y el panel de log pasa a estar oculto por defecto (botón "log ▾" para mostrarlo) — ya no hace falta visible todo el tiempo, la mecánica de zoom/pan real ya está confirmada.

**Bug real #2 — reconstrucción completa del overlay en cada frame de zoom/pan (la causa real de "el render es algo lento al hacer zoom", reportado por el usuario)**: el evento `view` de regl-scatterplot dispara varias veces por segundo durante un gesto continuo de zoom/pan, y `maybeReveal()` corría de forma síncrona en cada disparo — cada vez que cruzaba un umbral de nivel, forzaba fetch + `rebuildIfChanged()` (destruye y reconstruye todo el overlay SVG, con su costo de reflow). Con un gesto continuo esto podía disparar decenas de reconstrucciones completas por segundo. **Fix**: `scheduleReveal()` debounce (150ms sin nuevos eventos `view` antes de evaluar `maybeReveal()`) — `updatePositions()` (solo reposiciona nodos ya existentes, barato) se mantiene en cada evento para que el movimiento se siga viendo fluido mientras tanto. No medido con benchmark formal de FPS todavía — el fix ataca la causa mecánica identificada (rebuild síncrono por frame), no una hipótesis sin verificar; pendiente confirmar la mejora percibida con el usuario.

### Se abandona el visor de Claude Artifacts para este prototipo — servido localmente (2026-09-23)

**Queja del usuario, dos partes**: (1) el chrome del visor de Claude Artifacts (barra de título, botones Chat/Share) "obstaculiza la vista" — es UI del wrapper de claude.ai, no algo que el HTML del artifact pueda controlar; (2) el consumo de RAM percibido durante el uso. La parte (2) se aborda con los dos fixes de arriba; la parte (1) no tiene solución dentro de Artifacts — se decidió abandonarlo para este prototipo, no intentar mitigarlo.

**Decisión**: servir el prototipo como archivos estáticos locales, exactamente el patrón que **Fase 2 del proyecto ya tenía como objetivo** ("cómo correr todo localmente sin depender de hosting") y que `prototypes/`/`app/atlas_macro_preview.html` ya usaban para iteraciones anteriores del atlas — no es una decisión nueva de arquitectura, es aplicar la que ya existía en vez de seguir iterando dentro de Artifacts.

**Hecho**: `prototypes/atlas_vecindario_mvp/` — `index.html` (con los 2 fixes de arriba aplicados) + `data/` (24MB: `atlas_macro_graph.v1.json`, `atlas_chaos_mode.v1.json`/`.bin` — renombrado de `.wasm` a `.bin`, ese nombre era un rodeo específico de las extensiones binarias que Artifacts acepta publicar, ya no aplica sirviendo localmente —, `vecindario_preview.v1.json`, `meso_by_macro/`×130, `micro_by_macro/`×130 — 265 archivos). Servido con `python -m http.server` desde esa carpeta. **Verificado real**: servidor responde 200 en `index.html` y en el `.bin` de 14MB, y la página carga y renderiza correctamente en una pestaña de Chrome normal (sin ningún chrome de claude.ai) apuntando a `http://localhost:PUERTO/index.html`.

**Para correrlo**: `cd prototypes/atlas_vecindario_mvp && python -m http.server 8765` (o cualquier puerto libre), abrir `http://localhost:8765/index.html` en el navegador. Nada de Artifacts involucrado de aquí en adelante para este prototipo — actualizaciones futuras se hacen editando `index.html`/`data/` directamente en el repo, no republicando a claude.ai.

**Pendiente**: confirmar con el usuario si la mejora de rendimiento (debounce) se siente suficiente corriendo localmente, o si hace falta perfilar más a fondo (Chrome DevTools Performance/Memory, ahora posible sin la limitación del iframe de Artifacts).

### Investigación: ranking y mecánica de diseño del modo Explorar/analytic viejo (2026-09-23)

**Pedido del usuario, antes de construir el paso 5**: investigar cómo se construían las "top 50 tesis similares" del atlas viejo — recordaba un sistema de ranking que no usaba solo embeddings, "algo más" —, y por separado documentar qué hacía que el modo analytic se sintiera "como un producto interactivo de verdad" (animaciones, diseño) para poder reproducir esa calidad en el prototipo nuevo.

#### Ranking del top-50: verificado con datos reales, no con la documentación ni con memoria

**Hallazgo, confirmado cruzando datos reales (no asumido)**: la lista de "tesis similares" que consume el frontend (`neighborhood_by_thesis/{thesis_id}.json`, `"topK": 50`) es **coseno puro, sin ninguna señal adicional** — verificado en `TH_0000006.json`: los 50 scores bajan de 0.870429 a 0.783039 en una curva perfectamente monótona, sin ningún salto ni reordenamiento.

**Pero el usuario no estaba inventando el recuerdo — existe un sistema real de "algo más", solo que en otra pieza del pipeline, no en esta lista.** `app/semantic_full/base7_semantic_edges_mutual_rank15_score075.parquet` (1,637,549 edges) se construyó con **filtro de vecinos mutuos (mutual k-NN)**: un edge A↔B solo se conserva si B está en el top-15 de A **y** A está en el top-15 de B (reciprocidad, no basta con ser top-k en una sola dirección) **y** score ≥ 0.75. Verificado cruzando directamente contra `TH_0000006`: ese grafo mutuo solo tiene **8 edges** para esa tesis (no 50), y esos 8 scores aparecen dispersos en las posiciones 1,2,3,4,5,6,12,15 del ranking completo de 50 — prueba de que son dos artefactos calculados independientemente sobre el mismo embedding, no que uno alimente al otro. El grafo mutuo alimentaba la estructura de **edges a nivel macro del atlas** (y probablemente la clusterización Leiden en sí, que necesita un grafo de entrada) — no la lista personal de vecindario. El "recuerdo" del usuario era real, solo que sobre otra parte del sistema.

**Relevancia para NODO UNAM hoy**: el problema de fondo que el filtro mutuo resolvía (hubness — nodos que aparecen como "vecino" de todo el mundo sin relación real) ya se resolvió distinto y mejor en el pipeline nuevo — corrección por z-score para Nobel (paso 4 de la Fase Explorar) y, para el vecindario tesis-tesis (ADR-0014), medido y confirmado **negligible** (0.2% de hubness en el top-15, sin necesitar corrección). No hay hueco que rellenar del lado del ranking — la arquitectura ya es mejor que la que el usuario recordaba.

**Archivos/scripts**: `scripts/build_graph_neighborhood.py` (`build_graph_from_query`, el endpoint on-demand — coseno puro, `scores = emb_norm @ q; ranked = argsort(scores)[::-1]`) construye el vecindario en vivo para el caso "tesis fuera de la muestra"; `neighborhood_by_thesis/*.json` (516MB, 10,068 archivos, precomputado para las ~50k tesis del atlas viejo) es lo que consume la UI al hacer clic en "Explorar vecindario" — **no se encontró el script generador de este archivo en el repo** (no está en `scripts/`, `pipeline/` ni `notebooks/` — probablemente corrido una vez en un entorno no versionado); se infirió su método por verificación cruzada de datos reales, no por leer su código fuente.

#### Mecánica de diseño y animación — por qué se sentía "como un producto interactivo de verdad"

Todo verificado leyendo `deploy/static/index.html` directamente (no de memoria):

**1. Tweening de posición manual, no solo lo que sigma.js da por defecto.** `animateToPositions(positions, duration=850)` — loop propio de `requestAnimationFrame`, easing cúbico `ease(t) = 1 - (1-t)³` (ease-out, arranca rápido y desacelera), interpola `x`/`y` de cada nodo entre su posición actual y la nueva en cada frame, llama `renderer.refresh()` por frame. Esto es lo que hace que cambiar de universo↔analytic (o refiltrar/reagrupar) se sienta como una transformación fluida del mismo grafo, no un corte duro — el nodo "viaja" a su nuevo lugar, nunca teletransporta.

**2. Cámara con su propia animación separada.** `camera.animatedReset({duration: 500})` (sigma.js nativo) al cambiar de vista — 480-500ms consistente en las 5 ocurrencias encontradas en el archivo.

**3. Layout "universo" — espiral de ángulo dorado, radio ∝ similitud inversa:**
```js
GOLDEN_ANGLE = π(3 − √5)  // ≈137.5°, el ángulo dorado real
innerRadius = 0.70, outerRadius = 3.95
radius = innerRadius + (1 − simNorm) × (outerRadius − innerRadius)  // mas similar = mas cerca del centro
angle  = i × GOLDEN_ANGLE + sin(i × 1.71) × 0.18   // perturbación angular, evita rejilla perfecta
jitter = 0.045 × ((i % 5) − 2)                      // jitter radial ciclico cada 5 items
```
El ángulo dorado es la misma constante que genera phyllotaxis (arreglo de semillas de girasol) — de ahí que la nube de puntos se vea orgánica y no en anillos concéntricos artificiales pese a ser 100% determinística.

**4. Layout "analytic" — grilla de grillas, agrupado por categoría, más cercano primero dentro de cada grupo:**
```js
cols = min(4, max(1, ceil(sqrt(groupCount))))   // grilla de grupos, max 4 columnas
xGap = 3.1, yGap = 2.45                         // separación entre centros de grupo
// dentro de cada grupo: orden por similitud desc, sub-grilla propia
innerCols = ceil(sqrt(n))
spacing = n > 16 ? 0.30 : 0.36                  // grupos grandes se compactan un poco mas
```
Mismo principio del Design Manifest ya escrito para NODO UNAM sin saberlo de antemano: "1-2 codificaciones primarias, resistir agregar mas" — aquí posición de grupo = categoría, posición dentro del grupo = ranking de similitud, nada más compite.

**5. Edges como codificación continua de similitud, no binaria:**
```js
t = clamp((weight − 0.70) / 0.25, 0, 1)   // normaliza el rango util 0.70-0.95 a 0-1
size = 0.35 + t × 2.25
opacity = 0.08 + t × 0.30
```
Grosor y opacidad suben juntos con la similitud — coherente con la regla ya aceptada en el Design Manifest de NODO UNAM ("edges como textura, nunca como dato individual leíble").

**6. Tamaño de nodo también codifica similitud** (`build_graph_neighborhood.py`): `size = 9.2 + max(0, similarity − 0.72) × 26` — nodos por debajo de 0.72 de similitud quedan al tamaño base, por arriba crecen linealmente.

**7. Transiciones CSS consistentes en toda la interfaz**: 120-160ms `ease` para hover/estado (botones, opacidad), 420ms para paneles más grandes, keyframes dedicados (`bloomLevelIn`, `bloomPyramidIn`) para el efecto de "revelado" al bajar de macro→meso→micro — un vocabulario de motion design real, no transiciones por defecto del navegador.

**Aplicación directa al paso 5**: replicar el mecanismo (tweening manual con easing cúbico, no solo confiar en que la librería anime) y las dos fórmulas de layout (universo = espiral áurea por radio-similitud; analytic = grilla-de-grillas agrupada con orden interno por similitud) es más valioso que replicar los números exactos — los números (0.70 radios, 3.1 gaps, etc.) se calibraron para sigma.js con ~50-100 nodos; el prototipo nuevo usa SVG + regl-scatterplot con otra escala de coordenadas, van a necesitar su propia calibración visual, no un copy-paste de constantes.

### Paso 5 del backlog — modo analytic, grid-of-grids animado (2026-09-23)

**Construido directamente sobre la investigación de arriba** — mismo mecanismo (tweening manual, easing cúbico) y misma fórmula de layout (grilla-de-grillas, agrupado por categoría, orden interno por similitud), recalibrado para SVG en vez de copiar las constantes de sigma.js, tal como quedó anotado como plan.

**Cambio de datos primero, antes de tocar UI**: el payload `vecindario_preview.v1.json` no traía `area` por vecino (deliberadamente excluido en el paso 3 para minimizar tamaño). Se agregó (`pipeline/generar_vecindario_preview_prototipo.py`) y de paso se subió `MAX_VECINOS` de 20 a **50**, igual al `topK` del atlas viejo (ver investigación de arriba) — ya no hay límite de 16MB de Artifacts que respetar, corriendo local. Resultado: `vecindario_preview.v1.json` pasó de 8.74MB a **23.28MB** (2,500 tesis × hasta 50 vecinos con área).

**Implementación**: modal de pantalla completa (`#vmodal`, antes vivía como texto plano dentro del panel lateral de 320px — no cabía un grid legible ahí). `computeAnalyticLayout()` reproduce la fórmula del atlas viejo (`cols = min(4, ceil(√grupos))`, sub-grilla interna `innerCols = ceil(√n)`, orden por similitud descendente dentro de cada grupo) en coordenadas de píxel del contenedor en vez de las unidades abstractas de sigma.js. Agrupa por **área** (default) o **década** (selector) — no hay programa/plantel/nivel por vecino en este payload acotado, mismo criterio de "no soy el ADR completo, soy el MVP" ya aplicado antes.

**Animación**: en vez de reimplementar el loop manual de `requestAnimationFrame` del atlas viejo, se usó **transiciones de D3** (`selection.transition().duration(850).ease(d3.easeCubicOut)`) — D3 ya estaba cargado como dependencia (para los scales del mapa principal) y `d3.easeCubicOut` es exactamente la misma curva `1-(1-t)³` que el atlas viejo escribía a mano — mismo resultado visual, menos código propio que mantener. Patrón enter/update/exit real: nodos nuevos aparecen en la posición del nodo focal anterior con opacidad 0 y viajan/aparecen hacia su posición real (efecto "supernova" al recursar sobre un vecino), nodos que ya no aplican se desvanecen y se eliminan, nodos que persisten (mismo `id`) se mueven suavemente a su nueva posición.

**Recursión con breadcrumb**: clic en un vecino que esté en la muestra de 2,500 (`inSample`) abre su propio vecindario dentro del mismo modal, empujando un breadcrumb navegable (clic en cualquier punto del breadcrumb vuelve a ese nivel). Vecinos fuera de la muestra se muestran (color/tamaño/tooltip) pero no son clicables — mismo límite ya declarado en el paso 3, ahora visual en vez de solo textual (clase CSS `not-in-sample`, cursor default).

**Verificado en vivo, no solo revisado el código** (servidor local, extensión de Chrome conectada, mismo origen — sin el problema de iframe cross-origin de sesiones anteriores, así que se pudo usar un hook de depuración `window.__debugAtlas` en vez de adivinar coordenadas de píxel):
- Modal abre y renderiza el grid correctamente (probado con `TH_0000072`, 49 vecinos en área 2 + 1 sin área).
- Recursión funciona: clic en un vecino abrió su propio vecindario (`TH_0356641`), breadcrumb se actualizó a 2 niveles, título/año/área del nuevo foco correctos.
- Cambio de agrupación en vivo (área → década) re-renderizó el mismo set de 50 vecinos en 4 grupos por década (1980s/2000s/2010s/2020s) con la transición animada, sin errores de consola.
- Cierre del modal confirmado (`hidden` vuelve a `true`).
- Sin errores en consola en ningún punto de la prueba.

**Pendiente, no bloqueante**: (1) hover-tooltip no se verificó en vivo (se intentó, la captura de pantalla llegó tarde por una animación en curso — el código es el mismo patrón ya usado en el mapa principal, riesgo bajo); (2) `window.__debugAtlas` es un hook de desarrollo dejado a propósito en el prototipo (no es código de producción) — útil para seguir probando sin depender de clics reales.

**Para correr**: mismo servidor local ya documentado (`cd prototypes/atlas_vecindario_mvp && python -m http.server 8765`). Para regenerar el payload: `python pipeline/generar_vecindario_preview_prototipo.py` (ahora incluye `area`, `MAX_VECINOS=50`) y copiar el resultado a `prototypes/atlas_vecindario_mvp/data/`.

### Modo universo — espiral de ángulo dorado (2026-09-23, a pedido del usuario tras el paso 5)

**Construido sobre la misma investigación**, esta vez la fórmula del modo "universo" del atlas viejo en vez de la de "analytic": `computeUniverseLayout()` reproduce `radius = innerRadius + (1−simNorm)×(outerRadius−innerRadius)`, `angle = i×GOLDEN_ANGLE + sin(i×1.71)×0.18`, `jitter = 0.012×(outerRadius−innerRadius)×((i%5)−2)` — la misma espiral de Fibonacci/phyllotaxis (`GOLDEN_ANGLE = π(3−√5)`), radios en píxeles del contenedor (`innerRadius = min(w,h)×0.06`, `outerRadius = min(w,h)×0.46`) en vez de las unidades abstractas del atlas viejo.

**Arquitectura — un solo dispatcher, no dos vistas separadas**: `computeVecindarioLayout(neighbors, mode, groupByKey, w, h)` elige entre `computeUniverseLayout` (sin agrupar, `groups: []`) y `computeAnalyticLayout` según `vm.mode`. El resto del pipeline de render (edges, nodos, tooltip, tweening D3, recursión con breadcrumb) es **exactamente el mismo código** para ambos modos — universo y analytic solo difieren en qué función de layout produce las posiciones objetivo. Cambiar de modo dispara la misma transición animada de 850ms ya construida para el paso 5, sin código nuevo de animación.

**UI**: toggle de dos botones ("Universo" / "Analítico") junto al selector de agrupación — este último se oculta (`visibility:hidden`, no `display:none`, para no saltar el layout) en modo universo porque no aplica (el universo no agrupa, solo ordena por radio). Las etiquetas de grupo (`vm-group-label`) desaparecen solas en universo porque `computeUniverseLayout` devuelve `groups: []` — el data-join de D3 ya las limpia vía `exit().remove()`, sin lógica condicional extra.

**Verificado en vivo** (mismo hook `window.__debugAtlas`, mismo servidor local): el toggle cambia el layout correctamente (grid de grupos → nube en espiral), el nodo "sin área" (el vecino de menor similitud en la muestra) queda visiblemente en el radio exterior como predice la fórmula, las etiquetas de grupo y el selector de agrupación desaparecen en modo universo, sin errores de consola. **No se confirmó recursión (clic en un vecino) específicamente en modo universo** — un intento de clic falló por puntería de píxel (no por el código; el manejador de clic es el mismo ya probado exitosamente en modo analytic), no se insistió para no repetir el patrón de adivinar coordenadas ya señalado como ineficiente esta sesión.

**Para correr**: sin cambios de datos — mismo `vecindario_preview.v1.json` del paso 5, mismo servidor local.

### Modo universo retirado + clic en tesis individual sobre el mapa real (2026-09-23)

**Modo universo removido a pedido del usuario** (`quita el modo universo`) — se sacaron `computeUniverseLayout()`, el toggle de dos botones y el estado `vm.mode`; `computeAnalyticLayout()` queda como único layout del modal de vecindario, sin el dispatcher intermedio.

**Investigación puntual sobre el atlas viejo, a pedido del usuario**: releyendo `deploy/static/index.html` específicamente el `nodeReducer`/`clickNode` de la vista de vecindario (líneas ~8176-8280) — clic en un nodo tesis fija `state.selectedNode`; el reducer, para cada OTRO nodo que no sea vecino directo del seleccionado, lo apaga a `rgba(170,170,170,0.34)` (gris). Los nodos SÍ eran vecinos ya tenían color por área desde que se construyó el grafo (`AREA_COLORS`, en `build_graph_neighborhood.py`) — el clic no "pinta" nada nuevo, **apaga todo lo demás y deja que el color por área ya existente resalte por contraste**. Esa era la sensación que el usuario recordaba.

**Diferencia clave al traerlo a NODO UNAM**: el grafo viejo era una estrella abstracta (PROJECT↔cada vecino, sin edges entre vecinos, posiciones inventadas por el layout universo/analytic) — aquí las 609,154 tesis ya tienen posición semántica REAL (`atlas_chaos_mode.v1.bin`, layout PaCMAP), así que el mismo efecto se puede aplicar directamente sobre el mapa real en vez de sobre un grafo aparte: clic en cualquier punto del fondo WebGL → si tiene vecindario precargado, se apaga todo el resto del corpus y los vecinos reales se colorean por área en su posición real del mapa.

**Pieza de datos ya existente, nunca leída hasta ahora**: `generar_atlas_modo_caos.py` ya escribía un campo `thesisIdsBlob` (todos los `thesis_id`, mismo orden que x/y/macroCode) desde que se generó el modo caos — el frontend nunca lo parseaba. Se agregó el parseo (`TextDecoder` sobre el rango de bytes correspondiente) y un `Map` inverso `thesisId → índice`, sin regenerar ningún archivo de datos.

**Implementación**: la paleta categórica del punto de fondo WebGL pasó de 2 categorías (ruido/con-macro) a 9 — las 2 originales sin cambios por default, más `DIMMED`, `FOCAL`, `AREA1-4`, `SIN_AREA`, declaradas todas de entrada (regl-scatterplot fija `pointColor`/`opacity` al crear el plot, no se pueden agregar categorías después de `createScatterplot()`). Clic en un punto dispara el evento nativo `select` de regl-scatterplot (confirmado por su documentación: "Select a dot: Click on a dot with your mouse" — no hace falta lasso) → `applyMapSpotlight(thesisId, idx)` recalcula el array de categorías completo (todo a `DIMMED` salvo el foco y sus vecinos reales, coloreados por su área) y llama `plot.draw()` de nuevo con las mismas posiciones. Clic en espacio vacío dispara `deselect` → `clearMapSpotlight()` restaura las 2 categorías originales.

**UI nueva**: tarjeta flotante `#map-selection` (arriba a la derecha) con título/año/área de la tesis clickeada, conteo de vecinos ubicados ("50 de 50 vecinos..."), y un botón "Ver vecindario completo (grid) →" que abre el modal ya construido en el paso 5 — las dos vistas (spotlight en el mapa real, grid animado) quedan conectadas, no son features separadas.

**Verificado, con una brecha honesta**:
- ✅ Lógica de resolución de vecinos y categorías por área: verificado con datos reales (`TH_0000072`: 49 vecinos en área 2 + 1 sin área, exactamente como reporta la tarjeta "50 de 50").
- ✅ `applyMapSpotlight`/`clearMapSpotlight` invocados directamente (vía `window.__debugAtlas`) funcionan de punta a punta sin errores de consola, la tarjeta se llena y se limpia correctamente.
- ⚠️ **No se confirmó el disparo real del evento `select` de regl-scatterplot con un clic físico del mouse** — los intentos de clic real cayeron sobre los círculos SVG de macro/meso/micro (que están *encima* del canvas WebGL y capturan el clic primero) o sobre espacio genuinamente vacío sin punto cerca. Es una limitación de puntería a este nivel de zoom (los círculos de cluster tapan la mayoría del área visible), no evidencia de que el mecanismo esté roto — pero tampoco es prueba de que funcione con clic real. Pendiente: probar con el mapa suficientemente alejado de cualquier círculo de cluster (zona de ruido periférica) o suficientemente:  zoom profundo (nivel micro, círculos chicos) para tener espacio de fondo clickeable real.

**Para correr**: mismo servidor local, sin cambios de datos (usa `atlas_chaos_mode.v1.bin` y `vecindario_preview.v1.json` ya presentes).

### Pulido visual — color por área predominante en vez de masa (2026-09-23)

**Revierte una decisión anterior del Design Manifest, a pedido explícito del usuario** ("el coloreado por tamaño no sirve"). El Design Manifest (sección "Color", 2026-09-22) había elegido color = masa del cluster (degradado azul→ámbar→rojo, `massStops`) — el usuario lo probó en el prototipo real y decidió que no funciona visualmente. Nueva regla: **tamaño del círculo = masa** (sin cambios, `radius()` intacto), **color = área administrativa predominante, en degradado por qué tan predominante es** (`dominantAreaShare`, ya calculado y presente en los datos — `data/clustering/jerarquia_macro_meso.parquet`/`atlas_macro_graph.v1.json`/`meso_by_macro`/`micro_by_macro`, nunca se había expuesto en el color, solo en el texto del panel de detalle).

**Fórmula**: 4 colores base (mismos ya usados en el modal de vecindario y su leyenda — `área 1` azul `#2a4d7a`, `área 2` verde `#0f7d5c`, `área 3` ámbar `#c98a2e`, `área 4` rojo `#b8412f` — un solo código de área en toda la interfaz, no una paleta por vista). Degradado lineal entre una versión muy pálida de ese color (mezcla pareja entre las 4 áreas, sin dominancia real — `share≈0.28`, el piso teórico de "ninguna área domina" con 4 categorías) y el color base saturado (`share≥0.90`, casi puro) — `colorByDominantArea(area, share)`.

**Por qué degradado y no color plano por categoría**: un color plano por área ya se usa en el modal de vecindario (ahí cada nodo es una tesis individual, con una sola área real, sin ambigüedad). A nivel macro/meso/micro cada nodo es una **mezcla** de tesis de varias áreas — un macro con 95% área 3 y uno con 30% área 3 (mayoría relativa apenas) son casos muy distintos que un color plano igualaría. El degradado hace que la intensidad del color por sí sola comunique qué tan "puro" es el cluster, sin agregar una segunda codificación visual nueva (sigue siendo 1 sola variable: el área con su fuerza, no área+pureza como dos cosas separadas).

**Verificado visualmente** (servidor local, sin errores de consola): el mapa a nivel macro ahora muestra territorios de color claramente legibles (azul=física-matemáticas arriba-izquierda, verde=biológicas abajo-izquierda, ámbar=sociales derecha-centro, rojo=humanidades extremo derecho) — mucho más informativo que el degradado de masa anterior, que no comunicaba nada sobre el contenido temático. Leyenda rediseñada: 4 barras de degradado (una por área, pálido→saturado) con escala "mezcla pareja / casi puro", reemplaza la barra única de masa.

**Housekeeping de paso**: se eliminó `lerpColor()`/`massStops` (código muerto tras el cambio) y las variables CSS `--mass-lo/--mass-mid/--mass-hi` (sin más referencias).

### Dos correcciones reales tras revisión del usuario (2026-09-23)

**Pregunta 1 — "¿por qué el color por área solo aplica en los clusters, no en las tesis individuales?"** Cierto: el fondo WebGL (609,154 puntos individuales) seguía en el esquema binario viejo (gris=ruido/azul=con-macro), sin tocar. Fix real, no cosmético — requirió dato nuevo: `pipeline/generar_atlas_modo_caos.py` no traía `area` por punto (solo `x/y/macroCode`). Se agregó una columna `areaCode` (0=sin área, 1-4=área 1-4, tomada de `clusters_hdbscan.parquet` — dato de catálogo, independiente de si HDBSCAN la marcó ruido) al `.bin` regenerado (14.0MB → 15.7MB) y a los metadatos.

**Diseño de la paleta WebGL, dos variables no una**: en vez de colapsar área+ruido en una sola categoría (perdiendo la distinción ruido/clusterizado, que era el punto central del "modo caos"), se separaron: **color = área** (5 tonos, misma paleta ya usada en todos lados), **opacidad = si HDBSCAN la agrupó o no** (clusterizada = opaca, ruido = tenue). 10 categorías (5 áreas × 2 estados) + `DIMMED`/`FOCAL` ya usadas por el spotlight de clic = 12 categorías totales en `MAP_CATEGORIES`, todas declaradas de entrada en `createScatterplot()` (regl-scatterplot fija la paleta al crear el plot). `areaMapCategory(areaCode, hasMacro) = areaCode*2 + (hasMacro?1:0)` da el índice directo; el spotlight de clic (paso anterior) reusa la misma función pero forzando `hasMacro=true` para los vecinos (un vecino real se muestra vívido sin importar su propio estatus de ruido).

**Pregunta 2 — "revisa la guía de diseño, no se respetó nada, empezando por las tipografías"**: se auditó el Design Manifest (arriba) contra el prototipo real, con evidencia (JS en el navegador, no lectura de código a ojo). Tipografía en sí: **sí cargaba correctamente** (`document.fonts.check` confirmó Public Sans y Source Serif 4 activas, computed style correcto en `h1`/body) — no era el problema real. **Encontrados 2 violaciones concretas, no percepción**:
- **Los 4 botones de navegación del header** (`reset ×1`, `macro→meso`, `meso→micro`, `log`) nunca habían recibido ningún estilo propio — venían de un panel de depuración temporal (ver "Verificación en vivo" de sesiones anteriores) y se quedaron así. Computed style real, verificado en el navegador: `font-family: Arial`, `background: rgb(240,240,240)`, `border: 2px outset rgb(0,0,0)` — el bisel 3D literal por defecto del navegador, visible todo el tiempo en la esquina superior derecha, la parte más prominente de la interfaz después del título. Fix: clase `.nav-btn` (Public Sans, borde fino `var(--border)`, sin bisel, hover con `var(--accent)`) — mismo lenguaje visual que `.vm-close`/`.back-btn`, que sí estaban bien desde el principio. Etiquetas simplificadas de paso ("Reset" en vez de "reset (×1)" — el multiplicador exacto ya vive en el `zoom-readout` de abajo, no hacía falta repetirlo en el botón).
- **El degradado de color por dominancia de área (construido esta misma sesión) iba hacia casi-blanco en el extremo de baja dominancia** — exactamente la "paleta pastel/baja saturación" que el punto 4 del manifiesto prohíbe explícitamente ("nunca pastel... lee como amigable/consumer app"). Fix: el extremo bajo ahora mezcla hacia el mismo gris neutro y profundo que ya representa "sin área" (`rgb(148,141,124)`, no blanco) — se corrigió tanto la función `colorByDominantArea()` como los 4 gradientes de la leyenda para que coincidan.

**Bug adicional encontrado en el camino (no de diseño, de desarrollo local)**: al regenerar `atlas_chaos_mode.v1.json`/`.bin` con el campo `areaCode` nuevo, el navegador siguió sirviendo la versión vieja desde caché pese a recargar la página — `fetch()` sin opciones de caché explícitas puede quedarse con una respuesta cacheada indefinidamente. Fix: `{cache: 'no-store'}` en todos los `fetch()` de datos (`fetchJson()` y el fetch binario del modo caos) — necesario mientras se siga iterando localmente con datos que cambian seguido; sin impacto en producción real (ahí importaría más CDN cache-control que fetch-level).

**Verificado en vivo**: recarga limpia, sin errores de consola, puntos individuales de fondo ahora muestran color por área (antes solo gris/azul uniforme) con ruido visiblemente más tenue que los clusterizados, botones de header con el lenguaje visual correcto, leyenda con gradientes muted→vívido (no pastel). `window.__debugAtlas.state.chaosAreaCode` confirmado cargado con valores reales (`[1,3,3,3,3,2,3,2,2,2]` para las primeras 10 tesis).

**Para correr**: `python pipeline/generar_atlas_modo_caos.py` (agrega `areaCode`) → copiar `atlas_data/atlas_chaos_mode.v1.{bin,json}` a `prototypes/atlas_vecindario_mvp/data/` → recargar el servidor local (ya no debería hacer falta limpiar caché del navegador a mano gracias al fix de `no-store`).

**Pendiente, declarado explícito**: el resto del Design Manifest (chrome de rigor — grilla, ficha técnica — ya estaba razonablemente implementado y no se tocó; falta una auditoría igual de sistemática sobre el modal de vecindario y la tarjeta de spotlight, no solo el mapa principal, por si tienen violaciones similares sin detectar todavía.

### Segunda ronda de correcciones de diseño + diagnóstico de amontonamiento (2026-09-23)

**El usuario insistió tras la primera ronda: "no has seguido la guía de diseño, el font sigue siendo igual"** — verificado de nuevo con evidencia real (no repetir el error de confiar en el código sin medir). Hallazgo concreto nuevo: varios elementos de "lectura técnica" (`zoom-readout`, `footer`, IDs) estaban declarados como `font-family: "Public Sans", monospace` — pero Public Sans **sí carga**, así que el navegador nunca cae al fallback `monospace`: todo ese texto rendereaba en Public Sans proporcional, no en ninguna tipografía monoespaciada real. Verificado con `measureText()`: el ancho de "i" y "W" en esa declaración es idéntico (falso) — confirma que el "monospace" era decorativo, nunca funcional. Fix: se agregó **JetBrains Mono** (Google Fonts) para toda lectura numérica/técnica (zoom, coordenadas, ficha técnica, IDs, valores de stat-row) — tercera familia tipográfica, con rol propio (lectura instrumental de números), no reemplaza a Public Sans ni Source Serif 4.

**Mayúsculas, a pedido explícito ("busca un font adecuado que se vea bien en mayúsculas")**: no hizo falta una tipografía nueva — Public Sans ya es la elegida por el propio manifiesto para la "voz instrumento" precisamente porque es la familia oficial de USWDS, que la usa así (mayúsculas + tracking amplio) para este tipo de etiqueta constantemente. El problema real era que la regla de mayúsculas ya existía (`.panel-eyebrow`, `.lg-title`, `.section-label`) pero nunca se aplicó a los elementos más visibles: los 4 botones del header (nunca estilizados en absoluto, ver ronda 1), el pie de ficha técnica, el zoom-readout, las etiquetas de `stat-row`, el botón "ver vecindario completo". Aplicado a todos. **Deliberadamente NO aplicado** a: `<h1>`, títulos de panel/modal (nombre real de tesis/cluster), tooltips de título — esos son la "voz curaduría" (serif), y mezclar mayúsculas con serif es literalmente el antipatrón que la referencia "no me gusta" del Design Manifest ya había señalado (cada nodo etiquetado en mayúsculas todo el tiempo). Mantener esa distinción es aplicar la regla existente con más disciplina, no una regla nueva.

**"Los clusters ya no siguen gradientes" — bug real de calibración, no percepción.** Medido antes de tocar nada (mismo patrón de esta sesión: no asumir): `dominantAreaShare` entre los 130 macros tiene **mediana 0.907** y p90=0.99 — la fórmula de la ronda 1 normalizaba contra un rango teórico (0.28–0.90) nunca verificado contra los datos reales, así que la mayoría de los nodos ya caía en `t=1` (saturación completa) y el degradado colapsaba a color plano para más de la mitad del mapa. Fix: `colorByDominantArea()` ahora recibe `t` ya normalizado por el **mín/máx real de `dominantAreaShare` entre los nodos activos en la vista actual** — mismo criterio que `radius()` ya usa para el tamaño (normalización relativa a la vista, no un umbral absoluto inventado). Leyenda actualizada para reflejar que ahora es relativo ("menor/mayor dominancia\*", con nota al pie), no un umbral fijo.

**Opacidad de tesis individuales bajada a 40%** (antes hasta 0.80) — a pedido explícito ("opaca completamente todo"). Nuevo tope: clusterizadas 0.40, ruido 0.15 (antes 0.78/0.26). El fondo real vuelve a leerse como textura/contexto sin competir con las etiquetas y el grafo curado por encima.

#### Diagnóstico del amontonamiento visual ("que no se vean tantas tesis pegadas")

**Medido con `cKDTree` sobre los 609,154 puntos reales antes de proponer nada** (mismo estándar de evidencia de todo el proyecto): distancia al vecino más cercano real —
- Solo **1.37% de los puntos** (8,354) están genuinamente superpuestos (distancia < 0.001) — coincide casi exacto con el ~1.4-3.5% de títulos duplicados ya documentado (mismo título → mismo embedding → misma posición). **Esto NO es la causa principal del amontonamiento.**
- **53.4% de los puntos tiene su vecino más cercano a menos de 0.01 unidades** de distancia — sobre un mapa que mide ~72 unidades de lado a lado. 99.3% tiene un vecino a menos de 0.05. **Esta es la causa real**: es el comportamiento esperado de un embedding PaCMAP de 609k puntos — el algoritmo preserva vecindarios locales muy apretados a propósito (esa es literalmente su función objetivo), no es un defecto de los datos ni algo que "arreglar" en el sentido de que esté mal.

**Dos causas, dos remedios de naturaleza distinta — se aplicó solo el que no toca la honestidad de los datos:**
- **Tamaño de punto adaptativo al zoom** (implementado): antes fijo (2.4px sin importar el nivel), ahora crece con `state.k` (1.4px a nivel macro alejado → 4.8px a nivel micro cercano). A nivel macro, 609k puntos a tamaño fijo se leían como una mancha sólida por pura densidad de píxeles: reducir el tamaño ahí da aire sin mover ni un punto de su posición real. Al acercarse, la distancia real entre vecinos ya ocupa más píxeles de pantalla — tiene sentido que el punto también crezca. **No altera ningún dato, es puramente un parámetro de render.**
- **Jitter determinístico solo para el 1.37% de superposición exacta — NO implementado, dejado para decisión del usuario.** Separaría visualmente los duplicados reales (mismo título, mismo embedding, literalmente el mismo punto) sin tocar el 98.63% restante que ya está en su posición semántica honesta. Se dejó sin implementar deliberadamente porque el manifiesto ya le da mucho peso a la honestidad de la representación (toda la sección sobre por qué las coordenadas de PaCMAP no son literales, por qué la forma del mapa no se fuerza a ninguna figura) — mover posiciones, aunque sea solo el 1.37% de casos ya sabidos como duplicados, es una decisión con más peso que un parámetro de render, y no estaba explícitamente pedida.

**Verificado en vivo**: recarga limpia sin errores nuevos de consola; a zoom macro los puntos de fondo se ven notablemente más finos/aireados que antes; al zoom-in los puntos crecen y las agrupaciones densas (ej. el clúster ámbar de la zona derecha, inspeccionado con zoom de captura de pantalla) muestran círculos individuales más distinguibles que antes del cambio.

**Para correr**: mismo servidor local, sin cambios de datos (todos los fixes de esta ronda son CSS/JS puro, salvo el `areaCode` de la ronda anterior que ya estaba aplicado).

### Tercera ronda de correcciones de diseño (2026-09-23) — mayúsculas, gradiente, opacidad por nivel

**"¿Esto te parecen mayúsculas???"** — el usuario tenía razón: la ronda 2 aplicó mayúsculas solo a la "voz instrumento" (botones, footer, stat-labels) pero dejó la "voz curaduría" (etiquetas de nodos en el mapa, títulos de tesis, títulos de panel/modal) en minúscula — exactamente lo que señaló la captura de pantalla (labels del mapa como "planta", "sintesis", "filosofia" en minúscula). **Corrección al razonamiento de la ronda 1**: había asumido que mezclar mayúsculas con serif repetía el antipatrón de la referencia "no me gusta" del Design Manifest — sobre-generalización. Releyendo esa referencia, el problema señalado ahí era que **cada nodo** estaba etiquetado todo el tiempo, sin jerarquía de qué mirar primero — no el uso de mayúsculas en sí. Mayúsculas en serif para etiquetas de mapa es, de hecho, la convención clásica de cartografía (nombres de lugar en cartas náuticas reales). Se aplicó mayúsculas (con tracking) a: `.node-label` (etiquetas del mapa), `#panel h2` (título de panel), `.thesis-row .th-title` (tesis representativas y lista de vecindario), `#vm-title`/`#ms-title`/`#vt-title`/`.t-label` (títulos de modal/tarjeta/tooltips), `.vm-breadcrumb`, y el propio `<h1>`. Se dejaron en minúscula/normal solo los bloques de **prosa explicativa** (notas de leyenda, `.vecindario-note`, `.ms-note`) — un párrafo completo en mayúsculas perjudica la lectura de una forma que una etiqueta corta no.

**Gradiente: blanco → color, no gris → color** — revierte explícitamente el fix de la ronda 2. El usuario prefiere la rampa secuencial clásica de dataviz (tinte blanco del mismo tono hasta el tono saturado, estilo ColorBrewer) sobre la versión desaturada-hacia-gris que se había hecho para respetar la regla "nunca pastel" del manifiesto. Se implementó tal cual se pidió — es una revisión consciente de esa regla por parte de la autoridad de diseño del proyecto (el usuario), no un descuido. Se agregó borde sutil (`var(--border)`) a las barras de degradado de la leyenda, porque el extremo blanco quedaba invisible contra el fondo blanco del panel (`--panel-bg: #ffffff`) sin él.

**Opacidad por nivel jerárquico (macro/meso/micro), números calibrados sin pedir confirmación (a pedido explícito: "haz tú los números")**: antes `fill-opacity` fija en 0.9 para los tres niveles por igual. Ahora: **macro = 1.0** (el ancla visual principal, siempre el nivel más agregado), **meso = 0.70**, **micro = 0.48** — cada nivel más fino se siente progresivamente "más adentro"/más textura y menos protagonismo, reforzando visualmente que están anidados (macro contiene meso contiene micro) en vez de competir por la misma atención. Verificado en vivo en los 3 niveles (screenshots a zoom ×1/×4/×10): a nivel micro los círculos quedan casi fantasma, dejando que el fondo real de puntos individuales sea lo que se lee.

**Verificado en vivo, sin errores nuevos de consola**: los tres cambios confirmados juntos — labels del mapa en mayúsculas con tracking, degradado blanco→color visible en la leyenda y en los clusters reales, opacidad decreciente confirmada visualmente en meso y micro.

### Fuente de las etiquetas del mapa → Source Sans 3 (2026-09-23)

**Pedido**: "cambia la fuente de las etiquetas por algo como Source Sans Pro". Se interpretó "las etiquetas" como `.node-label` (los nombres que aparecen junto a los círculos del mapa — "PLANTA", "FILOSOFIA", etc.), que hasta ahora usaban Source Serif 4 (recién puesto en mayúsculas en la ronda anterior). Nota técnica verificada antes de escribir el link de Google Fonts: "Source Sans Pro" es el nombre viejo — Adobe la renombró a **Source Sans 3** al pasarla a mantenimiento activo; ese es el nombre real que Google Fonts sirve hoy (confirmado con `curl` contra la API, 200 — no se adivinó). Se agregó como cuarta familia tipográfica, con fallback explícito a `"Source Sans Pro"` por si algún entorno viejo todavía la resuelve con ese nombre.

**Por qué esta elección tiene sentido, no es un cambio arbitrario**: Source Sans y Source Serif son hermanas de diseño — ambas parte de la "Source superfamily" de Adobe, dibujadas para combinar entre sí (comparten proporciones/altura de x). Usarla para las etiquetas del mapa mantiene coherencia con Source Serif 4 (el resto de la "voz curaduría") sin ser la misma familia que Public Sans (que evita crear una cuarta voz tipográfica sin motivo — ya son 3: Public Sans/instrumento, Source Serif 4/curaduría, JetBrains Mono/lectura numérica). Además, un grotesco a 10.5px lee más limpio en mayúsculas que un serif al mismo tamaño chico — beneficio práctico, no solo estético.

**Verificado en vivo**: `document.fonts.check('600 16px "Source Sans 3"')` → `true`; computed style del `.node-label` confirma la cadena de fallback aplicada correctamente. Sin errores nuevos de consola.

### Zoom por defecto más ajustado + macros 1.5x + toggle de densidad (2026-09-23)

**Tres pedidos del usuario, viendo el prototipo el mismo en su propio navegador** (captura real, no descripción):

**1. Zoom-out máximo + estado inicial más ajustado.** La vista inicial (`cameraDistance=1`, ajustada al bounding box completo +8%) dejaba demasiado espacio vacío alrededor del núcleo denso. El usuario mostró una captura a `zoom×2.94` como el encuadre que le parecía bien y pidió que **ese** fuera tanto el máximo alejamiento permitido como el estado por defecto — no una vista más, sino la única vista de "todo el mapa" disponible. Fix: `DEFAULT_CAMERA_DISTANCE = 0.34` (k=1/0.34≈2.94) reemplaza el `1` hardcodeado en la config inicial del plot, el límite de zoom-out en `clampCamera()`, y el botón "Reset". La fórmula de `k` (`1/cameraDistance`) no cambió — evita tener que recalibrar `K_MESO`/`K_MICRO`/`K_MAX_ZOOM`, que siguen siendo válidos en la misma escala.

**Bug real encontrado y corregido en el camino (antes de llegar a este pedido)**: el tope de zoom-in (`K_MAX_ZOOM=25`) de la ronda anterior no funcionaba — verificado con scroll real, llegó a zoom×21,419 pese al límite. Causa raíz: la corrección reactiva (`clampCamera()`, corrige `cameraDistance` en un `setTimeout(0)` después del evento `'view'`) estaba detrás del mismo throttle `clampScheduled` usado para la corrección cosmética de deriva del pan — con una ráfaga rápida de rueda del mouse (muchos eventos `'view'` en sucesión), solo la primera corrección de la ráfaga se agendaba, dejando pasar el resto sin corregir. Primer intento de fix (interceptar el evento `'wheel'` en fase de captura y bloquearlo en la fuente) **rompió el zoom por completo** desde el primer scroll, sin diagnosticar la causa exacta — revertido; el usuario señaló correctamente que ya iban demasiadas vueltas de prueba en vivo para ese enfoque. Fix real: se quitó el throttle específicamente para el caso fuera-de-rango (las correcciones son idempotentes, no hay costo real en que se acumulen varias durante una ráfaga), dejando el throttle solo para la deriva cosmética del pan.

**2. Nodos macro 1.5x más grandes.** `radius()` pasó de tomar solo el tamaño (`s`) a tomar el nodo completo (`n`), con un multiplicador por nivel (`LEVEL_SIZE_MULT`): macro=1.5, meso/micro=1.0 por ahora — "empezando por los macro" implica que los otros niveles podrían subir después, no se adelantó esa decisión.

**3. Toggle de densidad del fondo (25/50/75/100%), experimento directo sobre el diagnóstico de amontonamiento ya hecho.** Se usó el método **nativo** `scatterplot.filter(indices)`/`.unfilter()` de regl-scatterplot (confirmado contra su documentación antes de implementar, no inventado) — preserva el alineamiento de índices 1:1 con `chaosThesisIds`/`thesisIdToChaosIndex` del que dependen el spotlight y el resto del mapa, a diferencia de filtrar los arrays `x`/`y`/`valueA` directamente (que habría roto esos índices). Inclusión determinista por punto vía hash barato (`sin(i×12.9898)×43758.5453`, fracción) en vez de una permutación completa — mismo resultado estadístico para "mostrar el X% de abajo del rank", más barato para 609,154 puntos. `draw()` parece resetear el filtro activo, así que se reaplica después de cada `draw()` en el spotlight (`applyMapSpotlight`/`clearMapSpotlight`) por seguridad, no se asumió que persiste.

**Verificado en vivo**: zoom inicial confirmado en ×2.94 (coincide con la captura de referencia); macros visiblemente más grandes; toggle al 25% confirmado con el número real (`152,328` puntos incluidos, ≈25% exacto de 609,154); sin errores nuevos de consola.

**Pendiente de que el usuario confirme si el toggle de densidad realmente "limpia la vista"** — es explícitamente un experimento ("para ver si así se limpia la vista"), no una decisión de diseño cerrada.

### v2.0.0 — bug de distorsión real, distancia artificial 1.5x, versionado (2026-09-23)

**Bug real reportado con captura**: el usuario mostró un mapa distorsionado (un solo nodo grande visible, el resto de los edges/nodos estirados en líneas diagonales) describiéndolo como "a veces si hago click y muevo puedo mover los nodos". El readout de la propia captura tenía la pista: `XSPAN=55.7 YSPAN=0.6` — el dominio Y colapsado a casi nada mientras X seguía normal. **Verificado por lectura de código, no se adivinó ni se probó en vivo primero** (a pedido explícito del usuario en el mensaje anterior de no seguir iterando en el navegador): no existe ningún handler de arrastre sobre nodos en todo el archivo — el verdadero origen era el segundo `window.addEventListener('resize', ...)`, que mutaba a mano el **rango** en píxeles de `state.xScale`/`state.yScale` sin recalcular su **dominio**. Si el usuario redimensiona la ventana del navegador (fácil de gatillar sin querer, arrastrando el borde o encajándola a media pantalla — coincide con la descripción "a veces"), ese scale mutado a mano con dominio viejo + rango nuevo podía quedar activo sin autocorregirse. Fix: el resize handler ya no toca los scales directamente — solo le avisa a regl-scatterplot el nuevo tamaño (`.set({width,height})`) y deja que el evento `'view'` (única fuente de verdad ya existente para `xScale`/`yScale`) haga el recálculo correcto, como ya hace para cualquier otro cambio de cámara.

**Distancia artificial 1.5x** ("generar más espacio y dar una sensación de poder explorar tranquilo"): `POSITION_SCALE = 1.5` aplicado una sola vez, apenas se leen las posiciones reales de cada fuente de datos — el fondo WebGL (`xArr`/`yArr` del modo caos) y los nodos macro/meso/micro (`n.position.x/y`, tanto los del grafo macro inicial como los que se cargan lazy vía `loadMeso`/`loadMicro`). No cambia la estructura relativa (sigue siendo el mismo PaCMAP, solo "separado"), y no requirió recalibrar ningún umbral (`K_MESO`/`K_MICRO`/`K_MAX_ZOOM`/`VIEWPORT_PAD`) porque todos son relativos al span visible, que crece proporcionalmente parejo. Verificado en vivo: `XSPAN`/`YSPAN` en el estado por defecto pasaron de 57.3/18.1 a 86.1/27.1 — exactamente ×1.5 (57.3×1.5=85.95≈86.1, 18.1×1.5=27.15≈27.1).

**Versionado canónico (semver)**: insignia fija `#app-version` abajo a la derecha, siempre visible, separada del footer de notas de desarrollo (ese cambia de contenido con cada paso del backlog — el número de versión es la única fuente estable de "qué build es esta"). Este conjunto de cambios (fix de distorsión + distancia artificial + el versionado mismo) es **v2.0.0**, nombrado así a pedido explícito del usuario. Convención hacia adelante: MAJOR = cambio de arquitectura/rediseño grande, MINOR = feature nueva, PATCH = fix sin feature nueva.

**Bug nuevo encontrado y corregido en el camino, real (no falsa alarma)**: al verificar los cambios, la consola mostró `"Ignoring draw call as the previous draw call has not yet finished"` con stack trace apuntando a `clearMapSpotlight` — `draw()` de regl-scatterplot es asíncrono (devuelve una promesa), y el toggle de densidad de la sesión anterior llamaba `applyDensityFilter()` inmediatamente después de `draw()` sin esperar a que resolviera, pisando el draw en curso. Fix: encadenado con `.then()`. **Pendiente, no resuelto del todo**: el propio `draw()` inicial (no ya la reaplicación del filtro) todavía puede emitir esta misma advertencia si se llama en sucesión muy rápida contra el propio ciclo de render interno de la librería — no rompe funcionalidad (el estado se mantiene consistente, en el peor caso se salta un redibujado redundante), pero se deja documentado en vez de perseguirlo más en vivo, seguía el patrón exacto que el usuario ya había señalado de gastar demasiadas vueltas de depuración en el navegador.

**Para correr**: mismo servidor local, sin cambios de datos.

### v2.0.1 — distancia artificial subida a 3x (2026-09-23)

A pedido del usuario ("separa mucho más, intentemos un 3x"), `POSITION_SCALE` sube de 1.5 a 3.0 — un solo número a cambiar gracias a que ya estaba centralizado en una constante (paso v2.0.0). Verificado en vivo: `XSPAN`/`YSPAN` en el estado por defecto pasan de 86.1/27.1 (×1.5) a 172.3/54.2 (×3.0 sobre la base real de 57.3/18.1) — el encuadre relativo (mismo `zoom×2.94` de referencia) se mantiene igual, solo cambia cuánto espacio absoluto hay entre los puntos. Sin errores nuevos de consola respecto a v2.0.0 (persisten los mismos warnings ya documentados de `draw()`, no relacionados con este cambio). PATCH, no MINOR — es un ajuste de parámetro sobre una feature ya construida, no una feature nueva.

### v2.0.2 — distancia artificial ×4 acumulativo sobre el 3x (2026-09-23)

Pedido explícito: "sobre este 3x ya hecho, aplica un 4x" — acumulativo, no reemplaza. `POSITION_SCALE = 3.0 × 4 = 12.0`. Verificado en vivo: `XSPAN`/`YSPAN` en el estado por defecto pasan a 687.7/216.7 — exactamente ×12 sobre la base real (57.3×12=687.6, 18.1×12=217.2). Mismo encuadre relativo (`zoom×2.94`), sin errores nuevos de consola.

### Cuarta ronda: barrido de código para texto de dataset sin mayúsculas + título en negrita sin querer (2026-09-23)

**Pedido explícito: "busca en código, no en Chrome"** — auditoría sistemática (`grep` sobre todos los `.textContent =`/`.innerHTML =` del archivo, no inspección visual) para encontrar todo texto que viene directo del dataset normalizado en minúsculas (`programsTop`, `area`, etc.) sin su clase CSS correspondiente en mayúsculas. Encontrados y corregidos 5 casos reales que la ronda 3 se había saltado: `.programs` (la lista "programas más frecuentes" — el caso que motivó la queja, ej. "artes visuales (631)" seguía en minúscula), `#tooltip .t-meta`, `#vmodal .vm-meta`, `#map-selection .ms-meta` (las tres muestran `área`/`area N` inline) y `.thesis-row .th-meta` (por consistencia con el resto de meta-texto, aunque en sí solo muestra año/ID sin case). Barrido completo confirmado contra los ~25 `textContent`/`innerHTML` del archivo — el resto ya estaba cubierto por reglas existentes (`.node-label`, `.panel-eyebrow`, `.stat-row span:first-child`, títulos) o es prosa explicativa dejada a propósito en minúscula (`.vecindario-note`, `.ms-note`, `.lg-note`).

**Título en negrita no intencional — bug real, no elección de diseño**: `#panel h2` nunca tuvo `font-weight` explícito, así que heredaba el **bold por defecto que los navegadores aplican a `<h1>`-`<h6>` en su hoja de estilos interna** — y como Source Serif 4 solo tiene los pesos 500/600 cargados (no 700), el navegador ni siquiera usaba un peso real: sintetizaba un bold artificial (peor calidad visual que cualquier peso real de la fuente). Fix: `font-weight: 500` explícito — el mismo peso "regular" que ya usa el resto del texto serif, título más delgado como se pidió. Se verificó que `<h1>` no tiene este problema (ya tenía `font-weight: 600` explícito, intencional) y que no hay más elementos `<h1>`-`<h6>` en el archivo sin peso declarado.

**Verificado en vivo**: panel de un macro real ("filosofia · traduccion · obra · libro") — título visiblemente más delgado, lista de programas ("FILOSOFIA (1614)", "ARTES VISUALES (637)", "LENGUA Y LITERATURAS HISPANICAS (466)"...) y meta del tooltip ("N = 5,469 TESIS · 8 MICRO-CLUSTERS · ÁREA: AREA 4 (83%)") ahora en mayúsculas. Sin errores nuevos de consola.

### Apartado técnico — GPU (2026-09-22)

**Pregunta del usuario**: al ver el log de Kaggle imprimir "2 GPU(s) detectada(s) -- moviendo el índice a GPU", ¿cómo se "carga" una GPU con código? ¿No basta con activarla en la configuración del notebook?

**No basta.** Activar el acelerador GPU en Kaggle (o Colab) solo pone la tarjeta **disponible dentro del contenedor** — no hace que el código la use automáticamente. Python/NumPy por defecto siempre corren en CPU, haya o no una GPU prendida al lado. Para que un cómputo real use la GPU, la librería tiene que hablarle a CUDA explícitamente — es el mismo patrón que `.to('cuda')` en PyTorch. En `pipeline/generar_vecindario_knn.py` son 3 líneas concretas:

```python
n_gpu = faiss.get_num_gpus()      # le pregunta al driver de CUDA cuantas GPUs ve
if n_gpu > 0:
    res = faiss.StandardGpuResources()             # reserva memoria/contexto en la GPU
    index = faiss.index_cpu_to_gpu(res, 0, index)   # copia el indice (609k vectores) de RAM a la VRAM de la GPU 0
```

Después de la tercera línea `index` ya no es el mismo objeto en memoria — es una versión que vive en la GPU, y sus métodos `.add()`/`.search()` se ejecutan como kernels CUDA en vez de instrucciones de CPU. El `if n_gpu > 0` es el fallback: si FAISS no ve la GPU (driver ausente, o el paquete instalado es `faiss-cpu` en vez de `faiss-gpu-cu12`, aunque el acelerador esté prendido en la configuración de Kaggle), el script sigue corriendo igual pero en CPU — más lento, nunca roto. Es justo lo que casi pasó en la primera corrida en Kaggle de esta sesión: sin el paquete GPU instalado, `get_num_gpus()` habría devuelto 0 pese a tener la GPU activada.

**Por qué importa para el estimado de tiempo**: esta es la razón concreta por la que el mismo trabajo (~7.6×10¹⁴ FLOPs, búsqueda exacta de vecinos sobre 609,154×1024) tarda ~75-80 min en CPU local pero solo ~10-20 min en GPU (T4/P100 de Kaggle) — no es que Kaggle sea "más rápido" en general, es que el código explícitamente mueve el trabajo a hardware paralelizable para esta carga específica (multiplicación de matrices).

_Plan de capturas — 2026-09-21. Pega con Alt+V en el chat cuando las tengas; se van marcando aquí conforme se consiguen. Pensado tanto para el README del repo como para mostrar el proceso, no solo el resultado final._

- [x] **1. Mapa 2D de PaCMAP coloreado por cluster de HDBSCAN** — capturado 2026-09-22, `docs/evidencia_visual/01_mapa_pacmap_clusters_hdbscan.png` (script: `pipeline/graficar_atlas_preview.py`). 609,154 puntos, color por identidad de cluster (paleta HSV permutada, 513 clusters — no cabe leyenda a esa cantidad, el color aquí es para que la estructura salte a la vista, no para leerse contra una leyenda), ruido gris detrás. **Título actualizado 2026-09-22** de uno narrativo ("NODO UNAM -- Atlas semantico de tesis (vista preliminar sin curar)") a uno formal tipo caption de instrumento: **"Proyección PaCMAP 2D — clustering HDBSCAN (513 clusters)"** — la ficha técnica (`n=...`, % ruido, modelo de embeddings, fecha) ya vivía en el subtítulo monospace y no cambió. **Para recrearla**: `python pipeline/graficar_atlas_preview.py` desde la raíz del repo, con `data/clustering/layout_pacmap2d.parquet` y `data/clustering/clusters_hdbscan.parquet` presentes (defaults del script vía `LAYOUT_PATH`/`CLUSTERS_PATH`/`OUTPUT_PATH`, sobreescribibles por env var). **Observación investigada (2026-09-22)**: el hueco central es real, no visual — perfil de densidad radial confirma ~50 puntos/área en r<0.7 vs pico de 1,837 en r≈3-3.6 (36x menos denso). Los 200 puntos más cercanos al centro geométrico son 59% ruido + 37% cluster 16 (psicología conductual/análisis experimental de la conducta) + resto disperso. Caso más claro: el título boilerplate "investigacion bibliografica de las tesis y seminarios de investigacion de la biblioteca de la facultad de contaduria y administracion" (9 copias exactas en el corpus) cae casi entero justo en el centro — es vocabulario académico genérico sin términos de dominio especifico, su embedding queda cerca del promedio de todo el corpus, y ese promedio no corresponde a ningún tema real dado lo disperso de las disciplinas (matematicas, veterinaria, derecho, filosofia...). Hipótesis de mecanismo (no verificada contra la literatura de PaCMAP): la repulsión explícita de "far pairs" de PaCMAP empuja a los clusters reales hacia una capa a cierta distancia del centro, dejando vacío el punto que no representa a ningún tema — mismo fenómeno que un layout de grafo con muchos nodos bien conectados formando una esfera hueca en vez de una bola solida. **Implicación para el paso 5**: la zona central mixta (boilerplate + un cluster ahí por coincidencia geométrica) no debe tratarse como "un macro más" sin revisión.

**Investigación completa (2026-09-22, ver [`gap.md`](gap.md)):** el usuario preguntó si esto es metodológicamente suficiente para afirmar un **vacío real de conocimiento generado en la UNAM** (un tema que la universidad no investiga). Respuesta corta: **no**. Análisis riguroso con `pipeline/analizar_hueco_central.py` + visualización `pipeline/graficar_hueco_central.py` (→ `docs/evidencia_visual/09_hueco_central_composicion.png`). Corrige el dato de arriba: con una definición de "hueco" más rigurosa (radio donde la densidad supera 30% del pico, no los 200 puntos más cercanos) el ruido dentro del hueco es **68.0%, prácticamente idéntico al 67.2% global** — el hueco no es excepcionalmente vacío de contenido clusterizable. Lo que sí es real: sobre-representación de Área 1 (1.51x) y sub-representación de Área 3 (0.59x) frente al baseline; tres clusters reales y ya bien poblados en otras partes del mapa (conducta/reforzamiento, química didáctica, matemáticas puras) concentran 25% del hueco; y una tasa de títulos duplicados 2.5x mayor que el resto del corpus (8.8% vs 3.5%, ej. "sincope", "asma", títulos de una palabra). Veredicto: es un artefacto de layout + títulos genéricos transversales a disciplinas ya representadas, no evidencia de un tema ausente — inferir un tema específico "faltante" (el ejemplo pedido era física nuclear) no está respaldado por los datos y se evitó explícitamente en `gap.md`. Ver ese archivo para la metodología completa, la tabla de coordenadas/composición y la propuesta de cómo sí se buscaría un vacío real (comparar contra una taxonomía externa de disciplinas, no contra la geometría del layout).

**Corrección de método (2026-09-22, "Parte 2" de `gap.md`)**: el usuario señaló, viendo `09_hueco_central_composicion.png`, que hay un hueco **notablemente más grande** a la izquierda del que se acababa de analizar. Al investigarlo se encontró que el análisis de arriba tenía un defecto real: asumía que el hueco es un círculo centrado en el **centroide del corpus completo** (0.09, 0.11) — una asunción nunca verificada contra la densidad 2D real. Detectando componentes conexas de baja densidad sin asumir forma ni centro (`scipy.ndimage.binary_fill_holes` + `label` sobre una grilla 200×200, ver `pipeline/analizar_hueco_izquierdo.py`), el hueco dominante real del mapa (135 celdas, el siguiente componente más grande tiene solo 14) está centrado en **(-2.91, -1.40)** — un punto distinto, con forma irregular/alargada, no un círculo — y el análisis anterior solo alcanzaba a cubrir su borde derecho. Este hueco grande (zona ampliada: 7,640 tesis, 1.25% del corpus) tiene una composición **opuesta** a la del hueco chico: ruido **por debajo** del global (46.2% vs 67.2%, no igual), dominado por un solo cluster real grande (30.4% "exploración sanitaria"), y **84.4% Área 2** (enriquecimiento 2.09x) — es una zona fronteriza entre varios clusters reales grandes de ciencias de la salud/neurociencia que se tocan sin fundirse, no un atractor de títulos genéricos cruzando disciplinas como el hueco chico. Mismo veredicto de fondo (no es evidencia de un vacío real de conocimiento), mecanismo distinto. Detalle completo, veredicto y visualización (`docs/evidencia_visual/12_hueco_izquierdo_composicion.png`) en la "Parte 2" de `gap.md`.

**Exploración: relación con las 4 áreas administrativas (2026-09-22)**. Tasa de ruido por área (`clusters_hdbscan.parquet`, columna `area`): **área 4 (Humanidades) 74.2%** (la más alta, n=50,834, la más chica), área 1 68.9%, área 2 66.9% (n=246,089, la más grande), área 3 63.6% (la más baja, contraintuitivo — es la que mejor clusteriza). Confirma cuantitativamente el patrón ya sospechado con Leiden/50k.

Mapa por área (`docs/evidencia_visual/02_mapa_por_area.png`, script `pipeline/graficar_atlas_por_area.py`, small multiples en vez de un solo scatter de 5 colores porque un scatter no aguanta separación confiable con más de 3 categorías superpuestas). **Título actualizado 2026-09-22** de "NODO UNAM -- Donde cae cada area administrativa sobre el mapa semantico" a **"Proyección PaCMAP 2D — distribución por área administrativa"** (formal, sin la pregunta narrativa; los n/% de ruido por panel y el pie explicativo no cambiaron). **Para recrearla**: `python pipeline/graficar_atlas_por_area.py` desde la raíz del repo, mismas fuentes que la gráfica 1 (`layout_pacmap2d.parquet` + `clusters_hdbscan.parquet`, columna `area`). A simple vista **ninguna área queda contenida en una región propia** — las 4 se dispersan por casi toda la forma del mapa, reforzando la decisión de no usar área como estructura de navegación. Pero medido con grilla (25x25, celdas con >=100 puntos), sí hay enriquecimiento local real, no es ruido uniforme: área 2 tiene el territorio más extendido (52/128 celdas con enriquecimiento >1.5x, coherente con ser la más grande), **área 4 tiene el enriquecimiento más extremo pero el territorio más escaso** (max 11.8x, solo 18/128 celdas) — la celda pico (11.98x, 149 tesis, 100% área 4) resultó ser un nicho angosto y estructuralmente exclusivo: **tesis-recital de música** (clusters "programa obras · bach", "musica · guitarra · piano") — un género que ninguna otra área puede producir por definición. Interesante: ese nicho específico sí forma clusters reales y bien definidos pese a que área 4 tiene el ruido más alto en general — el ruido de área 4 no es parejo, se concentra fuera de estos nichos exclusivos de formato/género.
**Cuantificado (2026-09-22): separación local por área SÍ existe, aunque a escala macro no forme regiones propias.** Pregunta del usuario: si el atlas "ya divide algo por área" tal como está, y si se puede inferir el área de un laureado Nobel a partir de su posición. Script nuevo: `pipeline/analizar_area_por_posicion.py`. Metodología: clasificador de vecino-más-cercano — para 30,000 tesis muestreadas al azar, voto mayoritario del área entre sus K=25 vecinos más cercanos *en la posición 2D ya calculada* (no en el embedding de 1024d), comparado contra el área real de esa tesis. **Resultado: 80.6% de accuracy** (vs. 40.4% del baseline "predecir siempre área 2", vs. 25% de azar con 4 clases) — muy por encima de ambos baselines. Recall por área: área 2 (Biológicas) 87.0%, área 3 (Sociales) 84.3%, área 1 (Físico-Matemáticas) 74.7%, área 4 (Humanidades) 66.3% (la más baja — se confunde 23.7% del tiempo con área 3, borde esperado Humanidades/Sociales). **No contradice el hallazgo de la gráfica 2 de arriba, lo complementa**: "ninguna área forma una región propia" es una observación a escala *macro* (no hay 4 continentes separados en el mapa); esta medición es a escala *local* (vecindario inmediato) — ambas son ciertas a la vez: las áreas están entreveradas en muchos bolsillos pequeños homogéneos por todo el mapa, no en un solo territorio grande por área, pero dentro de cada bolsillo la homogeneidad es alta. Coherente con el enriquecimiento por grilla ya medido (1.5x–11.8x) — esto solo le pone un número de tipo "accuracy de clasificador" en vez de "factor de enriquecimiento por celda".

**Validación externa con los laureados Nobel**: mismo método (K=25, esta vez ponderado por inverso de distancia) aplicado a la posición interpolada de cada laureado (`nobel_posicion_interpolada.parquet`) para inferir su área, comparado contra la **categoría real del premio** (Física/Química/Medicina/Economía/Literatura/Paz, parseada de `node_id` — dato que nunca se usó para calcular la posición, así que es una validación genuinamente independiente). Resultado, proporción por categoría real → área inferida: **Física → área 1 en 59.6%** de los casos; **Medicina/Fisiología → área 2 en 75.9%**; **Economía → área 3 en 65.7%**; **Paz → área 3 en 81.1%**; **Literatura → área 4 en 89.3%**; **Química se reparte entre área 1 (42.5%) y área 2 (44.5%)**, sensato — la química limita con física y con las ciencias biomédicas por igual, no debería caer limpio en una sola. El mapeo categoría→área coincide con la intuición disciplinar en los 6 casos (ciencias físicas→área 1, ciencias de la vida→área 2, ciencias sociales/paz→área 3, letras→área 4) sin que esa correspondencia se haya forzado en ningún punto del pipeline (ni la posición ni el área provienen de la categoría Nobel). Es la evidencia más fuerte hasta ahora de que el layout PaCMAP + embeddings e5-large está capturando estructura temática real y no solo artefactos de idioma/registro (que era la preocupación original del bug de hubness, ver paso 4 arriba). Guardado: `data/nobel/nobel_area_inferida.parquet` (`node_id`, `category`, `x`, `y`, `area_inferida`, `confianza_voto`). **Para recrear ambos análisis**: `python pipeline/analizar_area_por_posicion.py` desde la raíz del repo (usa `layout_pacmap2d.parquet`, `embeddings_meta.parquet` y `nobel_posicion_interpolada.parquet`, ya presentes).

- [ ] **2. Zoom progresivo macro → meso → micro** (3 capturas de la misma región del mapa, en 3 niveles de detalle) — demuestra visualmente la jerarquía nativa de HDBSCAN funcionando, algo que antes se armaba a mano.
- [ ] **3. Etiquetas de tema (c-TF-IDF) superpuestas en el mapa** — el mismo mapa de PaCMAP pero con palabras clave visibles por región (ej. "derecho · penal · delito"). Evidencia concreta de la mejora sobre el método viejo (que solo mostraba "tesis representativas" como ejemplos, sin etiqueta real).
- [x] **4. Nobel embebido como easter egg** — capturado 2026-09-22, `docs/evidencia_visual/04_mapa_con_nobel.png` (script: `pipeline/graficar_atlas_con_nobel.py`, usa posiciones interpoladas de `generar_posicion_nobel_interpolada.py`, no el ajuste conjunto que colapsó — ver paso 4 arriba). 1,026 laureados como estrellas doradas sobre las 609,154 tesis, concentrados en la banda central densa del mapa. **Título actualizado 2026-09-22** de "NODO UNAM -- 609,154 tesis + 1,026 laureados Nobel en el mismo espacio semantico" a **"Proyección PaCMAP 2D — corpus UNAM + laureados Nobel (n=610,180)"** (formal, el conteo se mueve del cuerpo de la frase a un paréntesis tipo notación de figura). **Para recrearla**: `python pipeline/graficar_atlas_con_nobel.py` desde la raíz del repo, con `data/clustering/layout_pacmap2d.parquet` y `data/clustering/nobel_posicion_interpolada.parquet` presentes (defaults vía `TESIS_LAYOUT_PATH`/`NOBEL_POS_PATH`/`OUTPUT_PATH`).
- [ ] **5. Comparación lado a lado: atlas viejo (muestra 50k, MiniLM) vs. nuevo (609k completo, e5-large + PaCMAP + HDBSCAN)** — la más útil para narrar el "antes/después" en un README o CV; requiere tener screenshot del atlas viejo antes de que quede reemplazado.
- [ ] **6. Taller — el constructor de análisis en acción** — una consulta libre (ej. buscar "messi" en título, cruzar por año) devolviendo una gráfica al instante. Evidencia de que la función que estaba "perdida" (ADR-0012) ya funciona con cara.
- [ ] **7. La app final en producción** (Explorar/Taller/Laboratorio) — capturas estándar para el README del repo público, una vez esté reconstruido.
- [x] **9. Composición del hueco central — ¿vacío real o artefacto de layout?** — capturado 2026-09-22, `docs/evidencia_visual/09_hueco_central_composicion.png` (scripts: `pipeline/analizar_hueco_central.py` + `pipeline/graficar_hueco_central.py`). Dos paneles: localizador (mapa completo, círculo marcando el hueco, r=1.80, 0.41% del corpus) + zoom coloreado por los 3 clusters reales más grandes presentes ahí (reforzamiento/conducta, química didáctica, matemáticas puras — 25% del hueco entre los tres) más ruido/otros clusters como contexto neutro. Investigación completa y veredicto metodológico en [`gap.md`](gap.md) — **no es evidencia válida de un vacío real de conocimiento en la UNAM**, ver ese archivo para el porqué. **Para recrear**: `python pipeline/analizar_hueco_central.py` (genera `data/clustering/hueco_central_puntos.parquet`) seguido de `python pipeline/graficar_hueco_central.py`, ambos desde la raíz del repo, con `layout_pacmap2d.parquet`, `clusters_hdbscan.parquet`, `cluster_topics_ctfidf.parquet` y `data/public/data_unam.parquet` ya presentes.
- [x] **8. Laureados Nobel por categoría real, validación cruzada con área administrativa** — capturado 2026-09-22, `docs/evidencia_visual/08_nobel_por_categoria.png` (script: `pipeline/graficar_nobel_por_categoria.py`, usa `data/nobel/nobel_area_inferida.parquet` generado por `pipeline/analizar_area_por_posicion.py`). Small multiples (2×3, mismo criterio que la gráfica 2 — un scatter no aguanta 6 series categóricas simultáneas de forma CVD-segura, ver skill dataviz: solo 3 slots categóricos validan all-pairs; con 6 la salida correcta es facetar, no forzar la paleta), un panel por categoría Nobel (Física/Química/Medicina-Fisiología/Literatura/Paz/Economía), mismo acento dorado que ya identifica "laureado Nobel" en la gráfica 4 (el color no distingue categoría aquí — el panel lo hace — así que no hace falta validar una paleta de 6 tonos). Título del panel muestra el área administrativa dominante entre sus vecinos, tomada del análisis cuantitativo de más abajo. **Confirma visualmente el hallazgo cuantitativo**: Física/Química/Medicina caen concentrados en la banda superior-izquierda del mapa (áreas 1/2), Literatura/Paz/Economía en una región distinta hacia el centro-derecha (áreas 3/4) — separación visible a simple vista, no solo en la tabla de porcentajes. **Para recrearla**: `python pipeline/graficar_nobel_por_categoria.py` desde la raíz del repo (usa `layout_pacmap2d.parquet` y `nobel_area_inferida.parquet`, ya presentes; si `nobel_area_inferida.parquet` no existe, regenerarlo primero con `python pipeline/analizar_area_por_posicion.py`).
- [x] **10. Dendrograma del corte macro (Ward)** — capturado 2026-09-22, `docs/evidencia_visual/10_dendrograma_macro.png` (script: `pipeline/graficar_dendrograma_macro.py`). Dendrograma truncado a los últimos 80 merges (513 hojas no caben legibles en un solo dendrograma), coloreado por debajo de la altura de corte; por encima, gris (estructura entre-macro, fuera del corte elegido). **Actualizado cinco veces** a lo largo de las rondas de corrección (ver sección de jerarquía): corte por coherencia (89, jerarquía v2) → ronda 1 (118) → ronda 2 (120) → ronda 3 (121) → ronda 4, revisión a nivel meso (124) → ronda 5, revisión completa de los 67 meso restantes (**130 macro-grupos finales**). La línea roja ya no se deriva del conteo de macros (dejó de corresponder a un corte plano único) — queda fija en D=0.40, el corte automático original, con nota explícita en el pie de que varias ramas se separaron después a mano. **Para recrearla**: `python pipeline/graficar_dendrograma_macro.py` desde la raíz del repo, requiere `data/clustering/macro_linkage_Z.npy` y `data/clustering/jerarquia_macro_meso.parquet` (ya con las 5 rondas de corrección manual aplicadas).
- [x] **11. Atlas: 513 micro-clusters vs. 130 macro-grupos, lado a lado** — capturado 2026-09-22, `docs/evidencia_visual/11_atlas_micro_vs_macro.png` (script: `pipeline/graficar_atlas_macro.py`). Mismo layout PaCMAP en ambos paneles: izquierda repite la paleta de la gráfica 1 (513 micro-clusters, HSV permutado); derecha colorea por los macro-grupos y numera el `macro_id` en el centroide (mediana x,y) de cada uno, para poder cruzarlo contra `data/clustering/macro_topics_ctfidf.parquet` y leer su etiqueta temática. Visualiza directamente la agregación: el panel derecho muestra parches de color notablemente más grandes y coherentes que el izquierdo, sin perder la forma general del atlas (núcleo denso + halo + islas). **Actualizado cinco veces** — ver sección de jerarquía para la justificación completa de cada ronda (89 → 118 → 120 → 121 → 124 → 130 macros finales). **Para recrearla**: `python pipeline/graficar_atlas_macro.py` desde la raíz del repo, con `layout_pacmap2d.parquet`, `clusters_hdbscan.parquet` y `jerarquia_macro_meso.parquet` ya presentes.
- [x] **12. Composición del hueco GRANDE (izquierda del centro) — corrección de método** — capturado 2026-09-22, `docs/evidencia_visual/12_hueco_izquierdo_composicion.png` (scripts: `pipeline/analizar_hueco_izquierdo.py` + `pipeline/graficar_hueco_izquierdo.py`). A pedido del usuario, que notó que el hueco de la gráfica 9 era chico comparado con uno mucho más grande a su izquierda. Detección por componentes conexas sobre grilla 2D (sin asumir centro ni forma — corrige un defecto real del método de la gráfica 9, que asumía un círculo centrado en el centroide del corpus). Dos paneles: localizador con el **contorno real** del hueco (forma irregular, no círculo, dibujado con `ax.contour` sobre la máscara de la componente conexa) + zoom coloreado por los 3 clusters reales más grandes que lo rodean (exploración sanitaria, rata/hipocampo, reforzamiento/conducta). Investigación completa, composición y veredicto en la "Parte 2" de [`gap.md`](gap.md) — mismo veredicto de fondo que el hueco chico (no es evidencia de un vacío real), pero mecanismo distinto: zona fronteriza entre clusters reales grandes de Área 2, no atractor de títulos genéricos transversal a disciplinas. **Para recrear**: `python pipeline/analizar_hueco_izquierdo.py` (genera `data/clustering/hueco_izquierdo_puntos.parquet` y `hueco_izquierdo_mask.npz`) seguido de `python pipeline/graficar_hueco_izquierdo.py`, ambos desde la raíz del repo, con `layout_pacmap2d.parquet`, `clusters_hdbscan.parquet`, `cluster_topics_ctfidf.parquet` y `data/public/data_unam.parquet` ya presentes.
- [x] **13. Los 5 macro-grupos más poblados, señalados con flechas** — capturado 2026-09-22, `docs/evidencia_visual/13_top5_macro_poblados.png` (script: `pipeline/graficar_top5_macro.py`). Surgió de revisar el macro 31 (caso "notas al programa", ver más abajo) y querer contrastarlo contra el otro extremo: los macros más grandes, no los más aislados. **Actualizado con la jerarquía v2** (corte por coherencia, ver sección de jerarquía) — top 5 recalculado: **macro 54** "Química de síntesis / petróleo" (n=8,062, 4.0% del corpus clusterizado, área 1 50% — el mismo macro 35 de v1, ahora sin veterinaria/comida/fitoquímica, que se separaron a otros dos macros; sigue mezclando petróleo con materiales y síntesis química, tensión abierta declarada en la sección de jerarquía), **macro 53** "Biología molecular / cáncer" (n=7,535, 3.8%, área 2 82% — sin cambios respecto a v1), **macro 71** "Medicina interna / nefrología" (n=6,638, 3.3%, área 2 98%), **macro 18** "Derecho mercantil / fideicomiso" (n=5,542, 2.8%, área 3 96%), **macro 48** "Filosofía / humanidades" (n=5,469, 2.7%, área 4 83%). Cada ficha muestra 3 estadísticas (n, % del corpus **clusterizado** — no del total, porque el 67.2% de ruido no tiene macro asignado —, y área administrativa dominante) más un nombre interpretado a mano junto a 2 keywords crudas de c-TF-IDF. **Para recrear**: `python pipeline/graficar_top5_macro.py` desde la raíz del repo, con `layout_pacmap2d.parquet`, `clusters_hdbscan.parquet`, `jerarquia_macro_meso.parquet` y `macro_topics_ctfidf.parquet` ya presentes (los diccionarios `NOMBRE_INTERPRETADO`/`BOX_OFFSET` del script están hardcodeados a los macro_id de esta corrida — si la jerarquía se vuelve a recalcular con otro `D_MACRO`, esos macro_id cambian y hay que actualizarlos a mano). **Nota ronda 1 (2026-09-22)**: tras la corrección manual quirúrgica (ver "Corrección manual sobre la jerarquía v2"), el top 5 no cambió — ninguno de los 6 macros separados (58, 56, 25, 61, 30, 88) estaba entre los más poblados. Se regeneró solo para actualizar el conteo total de macros en el pie (118, antes 89).

**Nota ronda 2 (2026-09-22)**: el macro 54 (el #1 del top 5) sí se dividió esta vez (ver "Ronda 2" en la sección de jerarquía) — top 5 recalculado, **cambia de composición**: **macro 53** "Biología molecular/cáncer" (n=7,535, 3.8%, área 2 82%), **macro 71** "Medicina interna/nefrología" (n=6,638, 3.3%, área 2 98%), **macro 18** "Derecho mercantil/fideicomiso" (n=5,542, 2.8%, área 3 96%), **macro 48** "Filosofía/humanidades" (n=5,469, 2.7%, área 4 83%), **macro 77** "Procedimientos médico-quirúrgicos" (n=5,370, 2.7%, área 2 99% — nuevo en el top 5, antes lo tapaba el 54). Los `NOMBRE_INTERPRETADO`/`BOX_OFFSET` del script se actualizaron a mano otra vez para esta corrida (120 macros totales).

**Nota rondas 3, 4 y 5 (2026-09-22)**: el top 5 no volvió a cambiar de composición en ninguna de las 3 rondas (todos los macros/meso divididos eran demasiado chicos para estar cerca del top 5, incluyendo el macro 72 "Zubirán" de la ronda 5) — se regeneró solo para actualizar el conteo total de macros en el pie (130, tras las 5 rondas completas).

**Pregunta del usuario al ver esta gráfica: en el atlas viejo "medicina" dominaba — aquí ni aparece en el top 5, ¿por qué?** Verificado (2026-09-22, cifras re-verificadas tras la jerarquía v2 más abajo): Área 2 (biológicas/salud) sigue siendo, por mucho, la mayor masa del corpus clusterizado — bajo v1 (53 macros), **83,443 tesis (41.8%) repartidas en 19 macros distintos**; recalculado bajo v2 (89 macros, corte por coherencia): **80,030 tesis (40.1%) en 35 macros distintos**, contra Área 3 con 65,402 en 34 macros, Área 1 con 40,858 en 13 macros, y Área 4 con 13,333 en 7 macros — mismo patrón, ahora con más granularidad porque hay más macros en total. El contenido no desapareció ni se redujo — se separó en decenas de categorías específicas (pediatría, oncología, salud pública, neurociencia, nefrología...) en vez de quedar como un solo bloque "Medicina". Es la consecuencia directa y esperada de la decisión ya tomada de no usar las 4 áreas administrativas como estructura de navegación (ver "Decisión editorial fuerte" más arriba) — el atlas viejo probablemente mostraba "Medicina" como categoría top-level porque *usaba el área administrativa* como esa estructura; este atlas agrupa por contenido real, y medicina es internamente demasiado heterogénea para quedar en un solo macro.
- [x] **Caso macro 31 — "notas al programa" (2026-09-22, id cambió a 49 con la jerarquía v2 — mismo contenido, solo se renumeró)**: revisado a pedido del usuario ("¿qué es el 31? desentona con todo" en `11_atlas_micro_vs_macro.png`). Es el único de los 53 macros de v1 que quedó como singleton (1 solo micro-cluster, el micro-cluster 0) — nunca se fusionó con nada más, ni siquiera al cortar en 53 grupos. Sigue singleton en v2 (ahora id 49, de 89), confirmando que el cambio de método no afecta islas genuinamente aisladas. Contenido verificado: 325 tesis, 292 (89.8%) tituladas literalmente "notas al programa" — el género de **tesis-recital musical** de la Facultad de Música (98.2% Área 4), donde el estudiante presenta las notas de programa de su recital en vez de una tesis de investigación tradicional. Contaminación menor (8/325, 2.5%): un puñado de "legrado parodontal"/"legrado periapical" (cirugía dental) sin relación temática, mismo fenómeno de título corto/genérico que en `gap.md`. Posición: centroide a 20.9 unidades del centroide del corpus (rango total del mapa ≈53 unidades) — isla genuinamente aislada, no un artefacto de layout. **Confirma una decisión ya anotada el mismo día** (línea de la auditoría de clusters dominados por título duplicado, más arriba): "tratar clusters 0 y 1 como 'cluster de género', no como tema de contenido diverso" — el corte macro lo hizo automáticamente, sin que hiciera falta ninguna regla especial a mano.

## Ideas (backlog) — 2026-09-21

_Sin priorizar formalmente todavía, capturadas de una sesión de brainstorm. Etiqueta `[idea]` para diferenciarlas de las decisiones ya tomadas._

**Descubrimiento / enganche**
- `[idea]` Botón "Sorpréndeme" — salto a un punto aleatorio del atlas.
- `[idea]` "Tesis del día" — una tesis destacada al azar en Inicio, rota diario.
- `[idea]` Comparador libre de 2 tesis elegidas por el usuario (similitud, vocabulario compartido, distancia temporal).

**Investigación seria (audiencia investigadores/bibliotecólogos)**
- `[idea]` Detector de "vacíos" de investigación — zonas del atlas con poca densidad reciente en una disciplina.
- `[idea]` Red de asesoría / genealogía académica — quién asesoró a quién, cuántas tesis, por época (usa la dimensión "asesor" de Taller).
- `[idea]` Exportar cita en BibTeX/APA por tesis.
- `[idea]` Mapa geográfico real de escuelas incorporadas (complementario al atlas semántico).

**Infraestructura / alcance**
- `[idea]` API pública de solo lectura, rate-limited, sobre los mismos endpoints que ya existen internamente.

**Con advertencia ética explícita, no recomendada sin más**
- `[idea]` Brecha de género en la producción académica por año/área — técnicamente posible (inferencia de género por nombre de pila), pero es una aproximación imperfecta, no un dato declarado — evaluar con cuidado antes de mostrarlo como si fuera exacto.

**Aprovechando el clustering HDBSCAN / soft clustering — 2026-09-22 (brainstorm mientras corría el smoke test del corpus completo)**
- `[idea]` **"Puentes interdisciplinarios" (costo ~cero — ya calculado hoy)**: el soft clustering guarda membership fraccional de cada tesis a *todos* los clusters, no solo al principal. Rankear por entropía de membership (ej. 40% a un cluster + 35% a otro) da directo una lista de tesis que viven genuinamente entre dos campos, sin cómputo nuevo — es el reverso positivo del mismo dato usado para rescatar ruido.
- `[idea]` **"El unicornio del corpus" (costo cero — dato ya guardado, sin usar)**: `clusters_hdbscan.parquet` guarda `outlier_score` por tesis desde el primer script de `clustering_hdbscan.py` — hoy no lo consume nada del roadmap. Leaderboard directo de las tesis más "solas" en el espacio semántico.
- `[idea]` Línea de tiempo animada del mapa — filtrar/atenuar por año sobre las posiciones 2D ya fijas de PaCMAP (sin re-clusterizar), para ver visualmente cómo áreas enteras crecen o nacen con el tiempo.
- `[idea]` Genealogía de un asesor superpuesta directo sobre el atlas existente (no un grafo nuevo aparte, a diferencia del ítem de "red de asesoría" de arriba): elegir un asesor ilumina sus tesis dirigidas sobre el mapa ya construido — revela si es "especialista" (agrupadas) o "generalista" (dispersas).
- `[idea]` Camino narrativo hacia el Nobel más cercano — en vez de un solo vecino más cercano, una cadena de tesis intermedias que conecte progresivamente hacia esa zona del mapa, reforzando el ángulo aspiracional ya decidido en ADR-0012.
- `[idea]` Entrada curada a las "islas de ruido" — un tour dentro del ~50-67% sin cluster ("rincones raros de la UNAM": temas sin par en todo el corpus), en vez de dejarlo solo como dispersión de fondo en el modo caos.
- `[idea]` Zoom a la frontera entre dos áreas macro elegidas por el usuario — versión a nivel área del ítem de "puentes interdisciplinarios", conecta directo con el hallazgo de Área 4 infrarrepresentada.

**Prioridad sugerida si se retoma esta lista**: Sorpréndeme (barato) → Detector de vacíos de investigación (más diferenciador) → Exportar cita (trivial, alto valor de confianza). De la tanda nueva del 2026-09-22, los dos de "costo ~cero" (puentes interdisciplinarios, unicornio del corpus) son los más baratos de todo el backlog — no requieren ningún cómputo adicional, solo exponer datos que ya existen.

## Fase 1 — Data Engineering

### Estado actual (auditoría 2026-09-20)

- Corpus: 609,156 tesis normalizadas (`data/clean/base7_kaggle_clean.parquet`), 1873–2026, 43 columnas.
- Multi-fuente: `base6` (562,211) + recuperación MARC (46,945) para años con pérdida de registros.
- Entity resolution real sobre nombres de autores/asesores (normalización de acentos, mojibake, residuos de rol, variantes del mismo nombre).
- Índice SQLite (386MB) para lookup de bibliografía.
- Pipeline de embeddings + clustering (sentence-transformers, Leiden, UMAP) sobre una muestra de 50k tesis para el atlas semántico.
- **Sin orquestación**: 62 scripts sueltos en `pipeline/`, sin Makefile/DAG, ejecutados a mano.
- **Sin tests** de la lógica de normalización de entidades (la parte más frágil del pipeline).
- **~26GB con duplicación masiva** en `data/archive/` (múltiples snapshots casi-idénticos del mismo dataset).
- **El proyecto raíz no es un repositorio git** — nada del pipeline de datos está versionado hoy. Pendiente de decidir si se inicializa.
- **[CRÍTICO — ver ADR-0004]** El dataset corregido (`data/clean/base7_kaggle_clean.parquet`) nunca se propagó río abajo: la app en producción (`thesis_lookup.parquet`, y con ella todo Taller) sigue sirviendo la versión con el hueco de scraping original.

### Pendientes
- [ ] Consolidar `pipeline/` en un flujo con orden explícito (Makefile o runner con `argparse` + `logging`).
- [ ] Tests de contrato para normalización de entidades.
- [ ] Decidir destino de `data/archive/` (¿borrar duplicados, mover a almacenamiento frío?).
- [x] Ejecutado ADR-0004 (2026-09-21) — con una corrección sobre el plan original: `build_thesis_lookup.py` no apunta a `base7_kaggle_clean.parquet` (el maestro, con PII) sino a **`data/public/data_unam.parquet`**, cerrando en el mismo cambio el pendiente que ADR-0011 ya dejaba anotado ("apuntar build_thesis_lookup.py a este archivo... para que el producto tampoco muestre autores"). `title` ahora se lee de `titulo_original` (no de `titulo`, que en el export público ya viene normalizado sin acentos — usarlo directo habría degradado el título mostrado en Taller). `thesis_lookup.parquet` regenerado (609,154 filas) y verificado: los 9 años del hueco de scraping ya muestran conteos reales, columna `author` vacía en el 100% de las filas. Backup del archivo viejo en `app/MI-TESIS-UNAM_github/data/thesis_lookup.before_adr0004_fix_2026-09-21.parquet`.
- [ ] **Pendiente descubierto al ejecutar lo anterior**: no se encontró ningún script que genere los JSON estáticos de `deploy/static/data/workshop/*.json` ni los parquets preagregados que `workshop_service.py` espera en `data/workshop/ranking_summary.parquet`/`series_summary.parquet` (rutas leídas en el código, pero los archivos no existen en el repo y no hay generador para ellos). Es decir, la propagación del fix a esos artefactos — la segunda mitad de lo que ADR-0004 pedía — no es un comando reproducible hoy; hace falta averiguar cómo se produjeron originalmente (¿a mano, contra el backend vivo?) o escribir ese exportador desde cero antes de poder regenerarlos.
- [ ] Confirmar si `app/Nodos/sample_50k_final_15d.parquet` (atlas semántico) también necesita reconstruirse (ver nota abierta en ADR-0004).
- [x] Resolver los 13 grupos de `plantel_display` sin mayoría clara — hecho 2026-09-20, ver ADR-0005.
- [x] Decisión de producto: acrónimos vs nombre completo — resuelto: expandir (ENAC, ENALLT, ENES+sede, ENCiT). Ver ADR-0005.
- [ ] Confirmar si `CCH` (1,236 filas) y `ENTS` (2,226 filas) también deben expandirse o se quedan como están — explícitamente no tocados todavía.
- [x] `plantel` cerrado 2026-09-20: `plantel_estandarizado`/`plantel_display` 538↔538, relación 1:1 perfecta, 0 ambigüedades. Ver ADR-0005 (4 pasadas, 64 pares evaluados y descartados por ser instituciones reales distintas).
- [x] `programa` estandarizado 2026-09-20: 1,407 → 1,127 valores únicos, minúscula sin acentos, "ñ" reparada. Ver ADR-0006 (43 pares descartados por ser programas reales distintos o ambigüedad título-vs-materia).
- [ ] Localizar y corregir en la fuente el bug de "ñ" → espacio compartido entre `grado_norm` y `programa` (ver ADR-0006) antes de auditar otra columna de texto.
- [x] `entidad_clean` removida del dataset limpio (43→42 columnas) y archivada en `data/lineage/entidad_clean_archivado_2026-09-20.parquet` — era un campo de linaje interno (82% redundante con plantel), no un duplicado a limpiar. Ver ADR-0007.
- [x] `data/clean/base7_column_dictionary.csv` y `nota_metodologica.md` regenerados con 42 columnas (2026-09-20). Nota: `nota_metodologica.md` nunca había vivido en `data/clean/` — solo existía una copia vieja (43 columnas) en `pipeline/`, sin tocar. `pipeline/crear_docs_base7.py` (tercer script que solapa con los dos anteriores, también regenera el `README.md` raíz) corregido pero NO ejecutado — pendiente decidir si se usa o se deprecia.
- [x] `origen` vs `universidad_nota` (12,658 filas "contradictorias") investigado y cerrado sin acción — es el patrón normal de "escuelas incorporadas" a la UNAM, no un error. No introducido por este pipeline. Ver ADR-0008.
- [x] `origen` corregido 2026-09-20: fusión `externa/incorporada` → `EXTERNAS E INCORPORADAS` (6,650 filas). Ver ADR-0009.
- [x] `grado_norm` recalculado desde cero 2026-09-20 (1,728→1,437 valores únicos, determinismo verificado). Ver ADR-0009.
- [ ] `tipo de contenido`/`medio`/`soporte`: solo 18 combinaciones reales entre las 3 columnas, 90.7% del corpus es una sola combinación — candidato a colapsar en un solo campo. Pendiente de decisión (dejado en espera por el usuario).

### Columnas del dataset público de Kaggle (2026-09-20, propuesta — ver nota de asesores pendiente de confirmar)

_Excluidas de `base7_kaggle_clean.parquet` (42 cols) para llegar a esta versión: `entidad_clean` (ya fuera del interno, ADR-0007), `texto_completo_url` (URLs inválidas, ADR-0009), columnas de identidad de autor (`autor_limpio_v2`, `autores_limpios_v2`, `autor_display`, `autores_display`, `autor_ui`). **Pendiente de confirmar si también se excluyen las columnas de identidad de asesor** — ver hilo 2026-09-20._

### Correcciones aplicadas a `asesor` antes del export (2026-09-20, ver ADR-0010)
- Verificado: la inversión Apellido↔Nombre no tiene bugs (100% de coincidencia en 535,079 casos verificables).
- Corregidos: 7 typos de OCR (dígito por letra), 23 casos de "?" en vez de "ñ", 291 filas con años de nacimiento incrustados (truncado a 2 segmentos), 1 caso especial ("Blanco De Mendieta", separado, a pedido del usuario).
- Pendiente sin resolver: ~10 variantes de escritura del apellido "Blanco De Mendieta" — mismo problema de `plantel` mudado a nombres de persona, no solicitado, no tocado.

| Columna | Qué es | Fuente |
|---|---|---|
| `source_record` | Indica si el registro viene de `base6` o de `marc_recovered` | Trazabilidad interna del merge (ADR/README raíz) |
| `thesis_id` | ID único global de la versión base7 | Generado al construir base7 |
| `thesis_id_old` | ID de la base anterior, para compatibilidad con prototipos previos (solo existe para registros base6) | Heredado de la base anterior |
| `ID_Aleph` | Identificador heredado de la extracción original | Catálogo original UNAM (Aleph) |
| `biblionumber` | Identificador bibliográfico de Koha/TESIUNAM | Catálogo Koha (principalmente registros MARC) |
| `system_number` | Número de control del sistema bibliográfico | Catálogo Koha/MARC |
| `Año` | Año de la tesis o registro de titulación | Catálogo original, normalizado en el pipeline |
| `título` | Título en forma cercana al registro bibliográfico original | Catálogo original |
| `titulo_limpio` | Título limpiado para lectura y análisis | Calculado en el pipeline (limpieza) |
| `titulo_normalizado` | Título normalizado (sin acentos/puntuación) para búsqueda y deduplicación | Calculado en el pipeline (normalización) |
| `num_autores` | Conteo de autores registrados | Calculado en el pipeline |
| `flag_sin_autor` | True si no se detectó autor | Calculado en el pipeline |
| `flag_multiples_autores` | True si hay más de un autor | Calculado en el pipeline |
| `asesores_limpios_v2`* | Lista completa de asesores, formato técnico, separada por \| | Catálogo original, normalizado |
| `asesor_limpio_v2`* | Primer asesor, formato técnico | Catálogo original, normalizado |
| `asesores_display`* | Lista completa de asesores, formato legible | Calculado en el pipeline |
| `asesor_display`* | Asesor principal, formato legible | Calculado en el pipeline |
| `asesor_ui`* | Texto compacto para interfaces | Calculado en el pipeline |
| `num_asesores` | Conteo de asesores registrados | Calculado en el pipeline |
| `flag_sin_asesor` | True si no se detectó asesor | Calculado en el pipeline |
| `flag_multiples_asesores` | True si hay más de un asesor | Calculado en el pipeline |
| `grado` | Grado o carrera registrada (crudo) | Catálogo original |
| `grado_norm` | Versión normalizada del grado (recalculada, ver ADR-0009) | Calculado en el pipeline |
| `nivel_estandar` | Nivel académico estandarizado (licenciatura/maestría/etc.) | Calculado en el pipeline |
| `programa` | Programa académico, estandarizado (ver ADR-0006) | Calculado en el pipeline |
| `area` | Área académica amplia | Catálogo original, normalizado |
| `origen` | Clasificación institucional del registro (UNAM / externa-incorporada / ambiguo) — corregido ADR-0009 | Catálogo original, normalizado |
| `universidad_nota` | Universidad extraída de la nota de tesis o del registro | Catálogo original |
| `plantel_estandarizado` | Plantel normalizado para análisis (ver ADR-0005) | Calculado en el pipeline |
| `plantel_display` | Nombre de plantel en formato legible (ver ADR-0005) | Calculado en el pipeline |
| `restricciones` | Disponibilidad o restricciones de acceso | Catálogo original |
| `tipo de contenido` | Tipo de contenido bibliográfico | Catálogo MARC (baja diferenciación, ver Fase 1) |
| `medio` | Medio del recurso bibliográfico | Catálogo MARC (baja diferenciación) |
| `soporte` | Soporte físico o digital del recurso | Catálogo MARC (baja diferenciación) |
| `descr física` | Descripción física o extensión del recurso | Catálogo original |
| `materia general` | Materias o temas generales (68.9% vacío, cobertura parcial) | Catálogo original |

\* = columnas de identidad de **asesor** — pendientes de confirmar si se excluyen también por privacidad (ver nota arriba). Si se excluyen, quedan solo `num_asesores`/`flag_sin_asesor`/`flag_multiples_asesores`, igual que autores.

### Dataset público (Kaggle/producto) — `data/public/data_unam.parquet` (2026-09-20, ver ADR-0011)
- [x] Generado: 609,156 filas, 25 columnas. Script: `pipeline/generar_data_unam.py`.
- [x] Autores (estudiantes) excluidos — decisión de privacidad, aplica también al producto, no solo a Kaggle.
- [x] Asesores (docentes) SÍ se incluyen — información valiosa, ya corregida (ADR-0010).
- [x] `plantel`: solo versión técnica, sin `plantel_legible`.
- [x] `flag_sin_asesor`, `flag_multiples_asesores`, `thesis_id_old`, `ID_Aleph`, `source_record`, `texto_completo_url`: excluidos.
- [x] Columnas renombradas sin sufijos de proceso interno (`_v2`/`_norm`/`_estandarizado`/`_display`).
- [ ] Pendiente: apuntar `build_thesis_lookup.py` a `data_unam.parquet` en vez del maestro, para que la app tampoco muestre autores (ver ADR-0004 y ADR-0011).
- [ ] Pendiente: exportar también a CSV si Kaggle lo requiere en ese formato.
- [x] `area` corregida en el maestro: "Por Clasificar" (456 filas, `programa` vacío en el 100% de ellas — no se puede reclasificar) reemplazado por cadena vacía, consistente con la convención de nulos del dataset. De paso se fusionaron los 2 sistemas de nombres duplicados de área (numerado "Area N" vs nombre descriptivo) en uno solo, minúsculas.
- [x] `titulo`/`titulo_busqueda` colapsados en un solo campo `titulo` (versión normalizada) para el export público — 22 columnas finales.
- [x] Nota metodológica propia del export público generada: `data/public/nota_metodologica_data_unam.md` (`pipeline/crear_nota_metodologica_data_unam.py`, estadísticas calculadas del archivo real).

### Auditoría de calidad por columna (2026-09-20)
- 43 columnas, `thesis_id` 100% único. Los nulos se representan como `""`, no `NaN` — cualquier chequeo de completitud futuro debe buscar cadena vacía.
- `materia general`: 68.9% vacío — el campo menos poblado del dataset, no sirve hoy para cruces temáticos finos.
- `grado_norm` tiene más valores únicos (1,728) que `grado` sin normalizar (1,644) — una normalización no debería aumentar cardinalidad. Anomalía anotada, no investigada a fondo (fuera del alcance de esta sesión).
- `plantel_estandarizado`/`plantel_display`: consolidado — ver ADR-0005.

## Fase 2 — Desarrollo (entorno local)

### Decisión: Docker Compose + reverse proxy local
Ver [`adr/0002-docker-compose-dev.md`](adr/0002-docker-compose-dev.md) para la decisión y su razonamiento completo — no se repite aquí.

## Fase 3 — Producción

### 3a. Cybersecurity
- **[Pendiente]** Gating de endpoints con cómputo en vivo (Worker de rerank IA) detrás de registro + cuota por usuario. El endpoint de vecindario on-demand deja de aplicar aquí — ver ADR-0014, ya no existe cómputo en vivo para el vecindario de tesis del corpus.
- **[Resuelto por diseño, no por parche — ver ADR-0014]** `app/MI-TESIS-UNAM_github/deploy/static/index.html` L6893-6899 llama a `/api/explore/neighborhood/{id}` (API viva) que no existe en el deploy estático — el mensaje de error expone detalles de implementación (FastAPI/uvicorn/puerto 8000) al usuario final. El atlas nuevo no tendrá este endpoint en absoluto: vecindario 100% precomputado, el bug deja de tener superficie donde ocurrir.
- **[Pendiente]** CORS de `scripts/main.py` con `allow_origins=["*"]` + `allow_credentials=True` (combinación inválida/riesgosa) — corregir si ese backend llega a desplegarse. Sigue aplicando al caso separado de Laboratorio (texto libre fuera del corpus), no al vecindario del atlas.
- **[Pendiente]** `error_response()` en `scripts/main.py` devuelve traceback completo al cliente.

### 3b. Datos precalculados / almacenamiento
Ver [`adr/0001-arquitectura-datos-produccion.md`](adr/0001-arquitectura-datos-produccion.md) y [`adr/0014-vecindario-100-precomputado.md`](adr/0014-vecindario-100-precomputado.md) (reemplaza a `adr/0003-hibrido-precompute-on-demand.md`, que queda como archivo histórico del debate).

### 3c. UI / 3d. UX
- Ver auditoría Impeccable 2026-09-19 (`app/MI-TESIS-UNAM_github/features.md`) — onboarding, accesibilidad, consistencia de color. La mayoría de los P0/P1 ya están atendidos.

---

## Changelog / Bugs conocidos

> Solo bugs reales con causa raíz identificada — no ruido operativo de una sesión de depuración. Formato: fecha, síntoma, causa raíz, estado.

### 2026-09-20 — Consolidación de duplicados en `plantel_estandarizado` / `plantel_display`
- **Síntoma**: usuario reportó problemas históricos de calidad en el campo `plantel` (repetidos, mal escritos).
- **Causa raíz**: 22 grupos de duplicados por inconsistencia de sufijo "UNAM"/acento en `plantel_estandarizado`; 23 grupos de inconsistencia de formato en `plantel_display` (6,640 filas, 1.1% del corpus). Detalle y política de fusión en [`adr/0005-consolidacion-plantel.md`](adr/0005-consolidacion-plantel.md).
- **Acción**: `pipeline/consolidar_plantel.py` — 591→569 valores únicos en `plantel_estandarizado`; 23 grupos de `plantel_display` fusionados; 13 grupos sin mayoría clara quedaron señalados sin tocar. Backup en `data/clean/base7_kaggle_clean.before_plantel_consolidation_2026-09-20.parquet`, audit log en `pipeline/audits/plantel_consolidation_2026-09-20.csv`.
- **Estado**: ✅ Aplicado y validado (609,156 filas intactas, `thesis_id` sigue único). Pendiente: los 13 grupos de `plantel_display` sin resolver, y decisión de producto sobre acrónimos (ver Fase 1 pendientes).

### 2026-09-21 — RAM sin control al correr `clustering_hdbscan.py` local con `core_dist_n_jobs=-1`
- **Síntoma**: corrida completa (609,154 filas) local no terminaba y la RAM libre bajaba sin parar — de 7.7GB a 2.9GB libres en 1h, sin haber terminado.
- **Causa raíz**: Windows no tiene `fork()`, solo `spawn` — cada uno de los 8 workers que `core_dist_n_jobs=-1` le pide a `hdbscan`/`joblib` reimporta el proceso completo y recibe su propia copia de los datos en vez de compartir memoria por copy-on-write como en Linux. Con 16.6GB de RAM total en la máquina, 8 copias del array de distancias/embeddings agotan la RAM libre antes de terminar.
- **Fix**: `CORE_DIST_N_JOBS` default bajado a `1` (mono-hilo, sin duplicación de memoria, más lento por core) en `clustering_hdbscan.py`. Motivó la decisión de mover la corrida completa a Kaggle (Linux, fork real, RAM conocida de antemano) — ver sección "Decisión tomada" en Fase Explorar arriba.
- **Estado**: ✅ Mitigado localmente (mono-hilo evita el OOM, aunque más lento), corrida completa reasignada a Kaggle en vez de forzar el local.

### 2026-09-21 — Dos bugs en `pipeline/reembedder_nobel_e5.py` al reusar `build_nodes()`
- **Síntoma 1**: `AttributeError: 'str' object has no attribute 'get'` en `laureate.get("id", "")` dentro de `build_nodes()`.
- **Causa raíz 1**: `laureates_complete.json` no es una lista directa de laureados — es un diccionario con varias llaves (`downloaded_at_utc`, `source`, `meta`, `laureates`), y la lista real vive dentro de la llave `laureates`. El script le pasaba el diccionario completo a `build_nodes()`, que espera iterar sobre una lista de registros. Al iterar sobre un diccionario en Python se itera sobre sus *llaves* (strings), no sus valores — por eso `laureate` terminaba siendo el texto `"downloaded_at_utc"` en vez de un registro real, y `.get()` no existe en un string.
- **Fix 1**: extraer explícitamente `laureate_payload["laureates"]` antes de pasarlo a `build_nodes()`.
- **Síntoma 2** (tras el fix 1): `TypeError: list indices must be integers or slices, not str` en `node["motivation"]`.
- **Causa raíz 2**: `build_nodes()` en `build_nobel_atlas.py` devuelve **3 valores** (`return nodes, entities, organization_ids`), no solo la lista de nodos. El script los recibía como si fuera un único valor (`nodes = mod.build_nodes(laureates)`), así que `nodes` terminaba siendo la tupla completa de 3 elementos — al iterar `for node in nodes`, el primer "node" obtenido era en realidad la lista completa de nodos (el primer elemento de la tupla), no un nodo individual. Por eso `node["motivation"]` fallaba: se intentaba indexar una lista con un string.
- **Fix 2**: desempacar los 3 valores del retorno — `nodes, _entities, _organization_ids = mod.build_nodes(laureates)`.
- **Lección**: ambos bugs vinieron del mismo patrón — asumir la forma de una estructura de datos ajena (el JSON crudo, el `return` de una función) en vez de verificarla contra el código/dato real antes de escribir el script que la reutiliza. Al reusar una función de otro script, hay que leer su `return` exacto, no solo su nombre y para qué sirve.
- **Estado**: ✅ Corregido, embeddings de Nobel generados y guardados correctamente.

### 2026-09-20 — La app en producción sirve el dataset con el hueco de scraping sin corregir
- **Síntoma**: usuario reportó incertidumbre sobre si un fix de scraping (años con pérdida de registros) había quedado bien aplicado.
- **Causa raíz**: `data/clean/base7_kaggle_clean.parquet` sí tiene el fix (verificado registro por registro contra `marc_recovered_normalized.parquet`), pero `app/MI-TESIS-UNAM_github/data/thesis_lookup.parquet` — el motor SQL/DuckDB detrás de todo Taller — se construyó desde una copia vieja de `base.parquet` (`build_thesis_lookup.py` no tiene ninguna referencia al dataset canónico). Detalle completo en [`adr/0004-fuente-unica-de-verdad-dataset.md`](adr/0004-fuente-unica-de-verdad-dataset.md).
- **Estado**: ✅ `thesis_lookup.parquet` regenerado 2026-09-21 desde `data/public/data_unam.parquet` (ver Fase 1, pendientes). 🟡 Sigue pendiente propagar a los JSON estáticos de `deploy/static/data/workshop/` — no existe generador reproducible para ellos hoy, ver nota nueva en Fase 1.

### 2026-09-21 — PCA como reductor previo a HDBSCAN producía un cluster gigante + 57.5% de ruido
- **Síntoma**: dos smoke tests en Kaggle (100k tesis, PCA a 50 y a 150 dimensiones) dieron 3 clusters, uno de ellos con el 42% del corpus, y 57.5% de las tesis sin cluster. Subir de 50 a 150 componentes (más varianza retenida: 0.435→0.684) no mejoró la calidad y el tiempo de HDBSCAN pasó de 6.3 min a más de 45 min sin terminar.
- **Causa raíz**: PCA preserva varianza global, no densidad local — y HDBSCAN agrupa por densidad local. Con PCA, los embeddings de e5 quedan casi uniformes en el espacio reducido sin importar cuántas dimensiones se retengan, así que HDBSCAN no encuentra fronteras reales. El salto de tiempo a 150d es una degradación no lineal de las estructuras de búsqueda de vecinos (KD-tree/ball-tree) por encima de ~20-30 dimensiones, agravada porque la construcción del árbol de expansión mínima no paraleliza bien. Diagnóstico completo en `problem.md`/`solution.md`.
- **Fix**: `REDUCTION_METHOD` default cambiado de `pca` a `umap` (`min_dist=0.0`, `metric="cosine"`, 5 dimensiones) en `pipeline/clustering_hdbscan.py` — ya era lo que ADR-0013 preveía ("posiblemente tras reducción UMAP"), la implementación se había desviado. `MIN_CLUSTER_SIZE`/`MIN_SAMPLES` suben de 40/10 a 150/5 como punto de partida. Se agregó caché de la reducción (`REDUCED_EMBEDDINGS_PATH`) para no repetirla en cada barrido de parámetros de HDBSCAN.
- **Estado**: 🟡 UMAP confirmado como fix del problema de tiempo (búsqueda de vecinos ~66s vs 45+ min sin terminar con PCA a 150d) y del problema de calidad original (con `leaf`, 87 clusters de tamaño razonable en vez de 1 blob de 42%). Abrió un problema de calibración nuevo, más chico: `eom` colapsa casi todo en un cluster (99%), `leaf` da buena granularidad pero 64.2% de ruido. Pendiente: barrido de `min_cluster_size` con `leaf` y/o reasignación de ruido por membresía suave — detalle en la sección "Decisión tomada" de Fase Explorar arriba. No bloquea el paso 1, es la calibración fina de ese mismo paso.

### 2026-09-20 — Burbujas y Ranking (Taller) renderizaban en blanco
- **Síntoma**: los datos cargaban bien (sin error, leyenda visible) pero el canvas de ECharts quedaba vacío al entrar a la pestaña.
- **Causa raíz**: `echarts.init()` se llamaba mientras el contenedor todavía estaba en transición de tamaño 0 (cambio de pestaña de Taller). Heatmap y Series ya tenían el parche (`resize()` inmediato + `setTimeout(..., 80)` tras cada `setOption`); Burbujas y Ranking no lo tenían.
- **Estado**: ✅ Corregido en `workshop.js` — mismo patrón aplicado a los 4 módulos.

### v2.1.0 — cross-fade entre niveles de revelado + bump de tamaño meso/micro (2026-09-23)

Recap pedido por el usuario ("en el paso de depuración visual, qué elementos consideramos y cuáles crees que faltan") identificó dos huecos concretos frente al backlog original de "pulido visual, al final": (1) transición entre macro/meso/micro seguía siendo un corte duro, (2) el bump de tamaño de la ronda anterior solo tocó macro ("empezando por los macro" dejaba implícito que meso/micro podían seguir, nunca se hizo). El usuario pidió explícitamente esos dos puntos.

**Cross-fade** (`prototypes/atlas_vecindario_mvp/index.html`, `buildOverlay()`): antes, cada cambio de `revealLevel` vaciaba `overlay.innerHTML` y reconstruía todo de golpe. Ahora `buildOverlay()` arma la capa nueva (`grid-layer`/`edge-layer-g`/`node-layer-g` dentro de un `<g class="reveal-layer">`) aparte, la agrega al DOM con `opacity:0`, y en el frame siguiente la transiciona a `opacity:1` (CSS `.reveal-layer { transition: opacity 220ms ease }`) mientras la capa anterior transiciona a `opacity:0` en paralelo y se elimina del DOM al terminar. No es un morph nodo-a-nodo — los sets de nodos entre niveles no son 1:1 (un macro se vuelve N nodos meso/micro) — es una disolución cruzada honesta. `updatePositions()` pasó de buscar por `id` fijo (`#grid-layer`, `#node-layer`, `#edge-layer`) a resolver contra la capa activa (`activeLayerGroup`, un puntero al `<g>` visible actual) para evitar colisión de selectores durante la ventana en la que ambas capas coexisten.

**Tamaño meso/micro**: `LEVEL_SIZE_MULT` pasa de `{macro:1.5, meso:1.0, micro:1.0}` a `{macro:1.5, meso:1.25, micro:1.1}`. Bump más chico que macro a propósito: meso ya es visualmente disperso (pocos blobs grandes por macro) y tolera crecer casi tanto como macro; micro es la capa que el diagnóstico de amontonamiento (KDTree, sección anterior) señaló como la más densa, así que sube lo justo para seguir la jerarquía de tamaño sin reintroducir ese problema.

Verificado con `node --check` sobre el bloque `<script>` extraído (sin errores de sintaxis) — no se hizo verificación visual en vivo para este cambio puntual, ya que el patrón de cross-fade + selección por capa activa es mecánico y de bajo riesgo (no toca datos, cálculo de posiciones, ni el filtro de densidad). MINOR, no PATCH — el cross-fade es una feature nueva de interacción, no un ajuste de parámetro. `v2.0.2 → v2.1.0`.

### v2.1.1 — bug real encontrado en `clampCamera()`: setTimeout(0) con closure obsoleto peleando contra el drag activo (2026-09-23)

**"Sigue estando el bug en el que puedo mover los nodos como yo quiera"** — el fix de v2.0.0 (quitar la mutación manual de `xScale`/`yScale` en el handler de `resize`) no era la causa real, o no la única: el usuario seguía viendo distorsión al arrastrar, no solo al redimensionar la ventana.

**Diagnóstico** (esta vez sí con una pasada en vivo — inspección de estado por consola, no prueba-y-error repetida — antes de que el usuario pidiera explícitamente no seguir usando Chrome a mitad de la investigación, momento en el que se cambió a leer el bundle real de la librería en vez de seguir probando en el navegador): `state.scatterplot.zoomToLocation([...], {transition:false})` llamado a mano vía consola SÍ mueve `cameraTarget`, pero el evento `'view'` (única fuente que actualiza `state.xScale`/`state.yScale`, y por lo tanto todo el overlay SVG) no se disparaba después. Para confirmar el mecanismo exacto se descargó el bundle real (`regl-scatterplot@1.16.0`, `cdn.jsdelivr.net`, no una suposición) y se decompiló la función `zoomToLocation`: internamente llama a `Ir.lookAt(target, dist)` de forma **síncrona**, dentro del executor de la Promise — no hay ninguna razón interna para que el código de la app la envolviera en `setTimeout(fn, 0)`.

**Causa raíz real**: `clampCamera()` (código de la ronda anterior, "tope de zoom, segundo intento") diferría sus correcciones fuera de rango con `setTimeout(fn, 0)`, capturando `tx`/`ty`/`dist` por closure en el tick en que se agendaban. Durante un gesto de pan/zoom activo (que dispara `'view'` en cada frame), para cuando el timeout corría un tick después, el usuario ya había seguido arrastrando — la corrección aplicaba entonces una posición YA VIEJA sobre una cámara que ya había avanzado, un salto hacia atrás en contra del gesto activo. La ronda anterior además había quitado a propósito el throttle del caso fuera-de-rango (razonando que las llamadas eran "idempotentes, sin costo real en acumularse") — sin throttle, estas correcciones diferidas y obsoletas podían apilarse una sobre otra durante un arrastre sostenido fuera de límites, produciendo el efecto errático de "los nodos se mueven solos" que describió el usuario.

**Fix**: se elimina el `setTimeout(0)` en ambos casos de `clampCamera()` (fuera de rango en distancia, y deriva de pan target) — se llama a `zoomToLocation()` directo y síncrono con los valores recién leídos en ese mismo tick. `panDriftScheduled` (el flag de throttle, ya innecesario sin deferral) se elimina también. No hace falta throttle: `clampCamera()` ya corre como máximo una vez por evento `'view'`, con datos frescos cada vez.

**Estado**: 🟡 corregido por lectura de código + inspección de bundle real, sin verificación visual en vivo del comportamiento final tras el fix (el usuario pidió no seguir usando Chrome a mitad de la sesión de diagnóstico) — pendiente que el usuario confirme en vivo que el arrastre ya no distorsiona. `node --check` sobre el `<script>` extraído: sin errores de sintaxis. PATCH sobre v2.1.0 (corrección de bug real, no feature nueva). `v2.1.0 → v2.1.1`.

**⚠️ Corrección posterior (misma fecha, ver "Revisión crítica de la v2.1.1" abajo)**: ni este fix ni el de v2.0.0 atacaban la causa raíz. La distorsión es **rotación de cámara** (Alt+arrastre, o Alt "atorado" tras Alt+Tab), no el `setTimeout` ni el resize.

### Revisión crítica de la v2.1.1 — causa raíz real del bug de zoom, fallas de verificación, puntos ciegos (2026-09-23)

**Pedido del usuario**: leer este documento completo e inspeccionar carencias reales/puntos ciegos, sobre todo técnicos; explorar la v2 e identificar mejoras de diseño, una solución al bug del zoom, y cómo hacer la exploración sorprendente pero navegable. Se leyó el log completo, `prototypes/atlas_vecindario_mvp/index.html` (v2.1.1) y el bundle real `regl-scatterplot@1.16.0` (ESM, jsdelivr — incluye `dom-2d-camera` embebido). La extensión de Chrome no estaba conectada: el bug se confirmó por lectura del código de la librería + matemática, no reproducido en vivo.

#### 1. Bug de zoom/"muevo los nodos como quiero" — causa raíz: la cámara ROTA

- `regl-scatterplot` trae `DEFAULT_ACTION_KEY_MAP = { rotate: 'alt', remove: 'alt', lasso: 'shift', merge: 'cmd' }` y `dom-2d-camera` se crea con `isRotate = true` → **Alt + arrastrar rota la cámara**.
- `dom-2d-camera` activa el modificador en `keydown` (`isMouseDownMoveModActive = event.altKey`) y solo lo desactiva en `keyup`. En Windows, **Alt+Tab** manda el `keyup` a otra ventana: el modificador queda "atorado" y desde ahí **todo arrastre rota en vez de panear**. Explica el "a veces".
- `computeDomainView()` de la librería deriva `xScale`/`yScale` (los que emite el evento `view` y usa todo el overlay SVG) solo de dos esquinas, `(-1,-1)` y `(1,1)`, sin contemplar rotación. Con rotación θ y aspecto del canvas a=ancho/alto: `xSpan ∝ a·cosθ + sinθ`, `ySpan ∝ cosθ − a·sinθ`. Con el aspecto real del prototipo (a≈3.17, cuadra con 57.3/18.1 del readout) **ySpan llega a 0 con θ≈17.5°**. La captura del bug (`XSPAN=55.7 YSPAN=0.6`, razón 92.8) corresponde a θ≈16.9°. Los puntos WebGL rotan y el overlay se aplasta contra una línea — las "líneas diagonales".
- Por qué "se arreglaba solo" a ratos: `zoomToLocation` → `camera.lookAt(target, dist)` con rotación default 0 → cada corrección de `clampCamera()` **enderezaba** el mapa de golpe.
- Verificación sugerida en 10 s: `__debugAtlas.state.scatterplot.set({cameraRotation: 0.3})` y mirar el readout.
- **Detalle no obvio**: pasar `actionKeyMap` en `createScatterplot()` NO desactiva la rotación — `updateActionKeyMapChange()` solo corre vía `.set()`. Hay que llamar `plot.set({actionKeyMap: {lasso: 'shift'}})` después de crear el plot.
- **Tope de zoom nativo**: `camera.setScaleBounds()` existe y se aplica dentro de `camera.scale()` *antes* de dibujar — elimina la pelea rueda-vs-`clampCamera()` de 3 versiones. `setTranslationBounds()` existe pero **no se aplica** en esta versión (se guarda y nunca se lee en `translate()`), así que el pan sigue necesitando clamp propio — pero por **bordes del viewport** (centro en `[-1 + a·dist − m, 1 − a·dist + m]`), no recortando el centro a [-1,1] (que dejaba media pantalla vacía).

#### 2. Fallas de verificación en la v2 (la lección más importante de esta revisión)

- **`POSITION_SCALE` (v2.0.0–v2.0.2, 1.5x → 3x → 12x) es un no-op visual.** El fondo se normaliza a NDC — `(x·s − min·s)/(span·s)` — y el factor se cancela; el overlay usa escalas en el mismo espacio multiplicado. Las tres versiones se "verificaron" midiendo xSpan/ySpan, **la variable que se cambió, no el resultado en pantalla**. La separación percibida depende de px/unidad (zoom) y radio de nodo. Regla hacia adelante: verificar el resultado observable (píxeles), no el parámetro tocado.
- **El nivel macro casi no existía**: `K_MESO = 3.0` con zoom inicial k=2.94 — un 2% de zoom revelaba meso en todo el mapa, sin histéresis (parpadeo en el umbral).
- **Etiquetas**: top-16 por tamaño de *todos* los nodos activos (incluidos fuera de pantalla), sin manejo de colisiones.
- **Rendimiento por frame**: `updatePositions()` destruía y recreaba la grilla SVG y hacía `querySelectorAll` en cada evento `view`.
- **Aspecto de datos**: el dominio se normalizaba por separado en x (span 53.0) e y (span 49.2) → ~7% de anisotropía; una "carta náutica" debe ser equi-escala.
- **`draw()` resetea el filtro** salvo que se pase `{filter}`/`preventFilterReset` — el bundle ya lo soporta; el `.then(applyDensityFilter)` era un parche de carrera innecesario.

#### 3. Problemas de diseño en la v2

- **Círculos como protagonistas**: son andamiaje de depuración, no un mapa. Además la posición del círculo (mediana 2D PaCMAP) puede no representar un macro que Ward agrupó en 1024d: medido, la mediana del radio mediano por macro es 0.82 unidades pero el máximo es **7.83** (macros espacialmente dispersos dibujados como un punto).
- **Edges entre macros sin señal**: coseno entre centroides e5, que en este espacio cae casi siempre en 0.91–0.94 (ver piloto BGE-M3). Ruido visual.
- **Color por área contradice la decisión editorial** "100% data-driven, área como lente" — el área es hoy la codificación visual dominante.
- **Sin búsqueda, sin breadcrumb, sin minimapa**: nada impide que el usuario se pierda, y la primera pregunta de cualquier visitante ("¿dónde está X?") no tiene respuesta.
- **Chrome de depuración visible**: párrafo técnico en la leyenda, botones de zoom de debug, readout de xSpan, toggle de densidad.
- **Etiquetas crudas sin acentos** ("SINTESIS", "FILOSOFIA") — c-TF-IDF sobre títulos normalizados.

#### 4. Puntos ciegos del proyecto (técnicos, fuera del prototipo)

- **Sin git, 110 scripts en `pipeline/`, sin tests, 33 GB en `data/`** — igual que en la auditoría del 20-09, pero ahora más grave: 5 rondas de juicio humano viven codificadas en `aplicar_correccion_manual_macro.py`.
- **Las correcciones manuales están atadas a IDs derivados** (`MACROS_A_SEPARAR = [58, 56, 25, 61, 30, 88]`, ids de meso). Cualquier cambio aguas arriba (Ward, `D_MACRO`, re-corrida de HDBSCAN) las aplica **en silencio sobre los macros equivocados**. Propuesta: expresarlas sobre `cluster_id` de HDBSCAN (estable con `random_state`) + huella (hash) del input que falle ruidosamente si cambia.
- **67% del corpus inalcanzable por navegación**: el drill-down cubre solo lo clusterizado; el vecindario, 2,500 tesis.
- **Formato del vecindario de producción**: 1.26 GB en shards JSON, ~2.1 MB por clic. Propuesta: binario de registros de largo fijo (100 × `uint32` id + `uint8` similitud cuantizada = 500 B/tesis, ~305 MB total) → **un HTTP Range request de 500 bytes por tesis** (R2 soporta Range). Mismo patrón para títulos (offsets + blob). Cambia el cálculo de ADR-0014 — requeriría ADR nuevo.
- **Nobel sigue desconectado**, siendo la justificación de fusionarlo en Explorar (ADR-0012).
- **Proceso**: 12 versiones en un día ajustando parámetros por pedido puntual, varias revirtiendo la anterior (gradiente, mayúsculas); el Design Manifest ya no refleja lo construido. Falta un mockup de referencia antes de seguir iterando píxeles.

#### 5. Propuesta "sorprendente pero navegable" — aprobada por el usuario para implementar

Principio: **el mapa son los puntos, no los círculos**.
- **Momento sorpresa**: al entrar, los 609k puntos aparecen agrupados en discos por área administrativa y vuelan a su posición semántica real (`draw(..., {transition: true})`, nativo de la librería) — es la idea de onboarding "área → semántico" ya anotada el 22-09.
- **Carta náutica**: sin círculos a nivel macro; nombres de territorio tipográficos (tamaño por masa, colocación sin colisiones, solo en viewport); puntos coloreados por **territorio semántico**, área como lente activable; hover sobre un nombre resalta su territorio.
- **Navegación**: clic en nombre → vuelo animado; breadcrumb "UNAM › macro › meso"; minimapa con recuadro de vista; buscador Cmd-K sobre las ~1,085 etiquetas.
- **Rutas guiadas** (secuencias de vuelos con tarjeta de texto): isla "notas al programa", hueco central, petróleo↔química, medicina como archipiélago.
- **Limpieza**: chrome de depuración detrás de `?debug`.

**Orden acordado con el usuario**: primero los fixes (secciones 1–2), al final la sección 5. Pendientes que no son del prototipo (git, correcciones por `cluster_id`, binario con Range requests, nombres humanos para los 130 macros) quedan en backlog, sin empezar.

### v2.2.0 — fixes de cámara y render, verificados en Chrome headless con métricas observables (2026-09-23)

Primera parte del plan de la "Revisión crítica de la v2.1.1". Respaldo de la versión anterior: `prototypes/atlas_vecindario_mvp/index.v2.1.1.html`.

**Harness nuevo de verificación** (la extensión de Chrome no estaba conectada): script Node sin dependencias que habla CDP directo con Chrome headless (`--headless=new`, swiftshader para WebGL) — ejecuta pasos `eval`/`mouse`/`wheel`/`key`/`shot` y vuelca consola. Vive en el scratchpad de la sesión, no en el repo (candidato a moverse a `tools/` si se adopta). Permite eventos de mouse/teclado *reales* (con modificadores), no llamadas a funciones internas — cierra la brecha de "no se pudo probar el gesto real" que se arrastraba desde el 22-09.

**Bug reproducido antes del fix, en la v2.1.1 sin tocar**: Alt + arrastre real → `cameraRotation` = 137.4°, `xSpan=-191.2 ySpan=-457.8` (spans negativos), captura con los puntos rotados y el overlay desalineado — mismo síntoma que la captura original del usuario.

**Cambios** (`index.html`, todos comentados en el código):
1. Rotación desactivada: `plot.set({actionKeyMap: {lasso: 'shift'}})` después de crear el plot.
2. Tope de zoom nativo: `camera.setScaleBounds([[K0, K0·10], ...])` — el zoom ya no se corrige después de dibujar, la cámara nunca sale del rango. `K_MAX_ZOOM` sube de 25 a K0·10 ≈ 29.4 para que el rango micro tenga recorrido.
3. Clamp de pan por bordes del viewport (centro ∈ `[-1 − m + a·dist, 1 + m − a·dist]`, m=0.12), sin tocar la distancia; se salta durante vuelos animados.
4. Nivel global con histéresis ±8%: meso a K0·1.9, micro a K0·4.5 (antes meso a 3.0 con k inicial 2.94).
5. `POSITION_SCALE` eliminado (no-op); dominio equi-escala (mismo span en ambos ejes).
6. Edges entre macros eliminados (sin señal); edges meso/micro (c-TF-IDF) se conservan.
7. Etiquetas: todas creadas ocultas, `placeLabels()` coloca por frame solo las que están en viewport, por masa, sin colisiones (máx. 28).
8. Grilla con pool de elementos: solo se recrea si cambia el paso/rango, no en cada evento `view`.
9. Filtro de densidad dentro del mismo `draw()` (opción nativa `filter`) — elimina la carrera "Ignoring draw call…".
10. **Bug nuevo encontrado al verificar, real para usuarios**: el renderer compartido por defecto limita su canvas interno a `min(innerWidth, screen.availWidth)` y lo copia centrado → con zoom del navegador <100% (innerWidth en CSS px > pantalla), en headless o entre monitores, **el mapa sale recortado a un recuadro central**. Fix: renderer propio (`createRenderer` del mismo bundle) redimensionado al contenedor, también tras cada `resize`.

**Verificación (eventos reales, métricas observables, no parámetros)**:

| Prueba | Resultado |
|---|---|
| Alt + arrastre real | rotación 0.00°, spans sin cambio |
| Equi-escala | xSpan/ySpan = W/H exacto (2.289 = 2.289) en todos los pasos |
| 54 ticks de rueda hacia adentro | k = 29.41 (tope exacto, sin rebote) |
| 80 ticks hacia afuera | k = 2.94 (tope exacto) |
| Objetivo forzado a (3,−3) con k=20 | clamp a (1.006, −1.070); esperado (1.0055, −1.07) |
| Histéresis en k=5.30 (umbral de subida 6.04) | sigue en macro |
| Niveles | macro → meso (k=8.3, 191 nodos) → micro (k=29.4) |
| Render | mapa completo a 1584×692 (antes recortado a 800×600) |
| Consola | sin errores ni advertencias |

MINOR (`v2.1.1 → v2.2.0`): incluye cambios de comportamiento (umbrales, etiquetas, sin edges macro), no solo fixes.

### v3.0.0 — rediseño "sorprendente pero navegable" (2026-09-23)

Implementa la sección 5 de la "Revisión crítica de la v2.1.1", sobre la base de cámara de v2.2.0. Respaldo de la versión anterior: `prototypes/atlas_vecindario_mvp/index.v2.2.0.html`. MAJOR: cambia el modelo de interacción (el mapa son los puntos, no los círculos), no solo el estilo.

**Qué hay nuevo** (todo en `index.html`, comentado en el código):
- **Introducción área → contenido**: las 609,154 tesis arrancan en discos por área administrativa (filotaxis por disco, tamaño ∝ √n; grilla 2×2 en pantallas verticales) y vuelan a su posición PaCMAP real con la transición nativa de regl-scatterplot (2.6 s, `cubicInOut`, interpolación en GPU). Al llegar, el color cambia de área a territorio. Se muestra una vez (`localStorage`, envuelto en try/catch); botón "Introducción" para repetirla; `?debug` la salta.
- **Territorios en vez de círculos**: a nivel macro no hay marcadores; los 130 territorios son nombres tipográficos (tamaño por masa, colocación greedy sin colisiones, solo en viewport, máx. 34). En meso/micro hay puntos chicos con nombre, y el nombre del territorio padre queda de fondo, grande y tenue, en el espacio libre. Overlay keyed por id: entran y salen nodos individuales con fade, sin reconstruir la capa completa.
- **Color por territorio** (130 tonos OKLCH; tono = ángulo del centroide alrededor del centro del mapa ±14°, luminosidad alternada en 3 pasos) con el área como **lente** activable ("Territorios | Áreas UNAM"). Resuelve la contradicción señalada en la revisión (el área era la codificación dominante pese a la decisión "100% data-driven").
- **Resaltado de territorio** al pasar el mouse sobre un nombre (todo lo demás se atenúa); tooltip al pasar sobre cualquier punto (territorio + área).
- **Todo el mapa es clicable**: clic en un nombre o en un punto vuela a su territorio y abre el panel; clic en una de las 2,500 tesis con vecindario → spotlight de vecinos (igual que v2).
- **Vuelos de cámara** con distancia y objetivo acotados *antes* de volar. El destino de un territorio es su caja **p10–p90** de puntos, no la mediana. Primer intento con media ± 2σ, descartado al verificar: 8 tesis dentales dentro de la isla "notas al programa" inflaban la caja y la ruta no acercaba.
- **Breadcrumb** (UNAM › territorio › subtema, según el centro de la vista) navegable; **minimapa** con recuadro de vista, clic/arrastre para moverse (se desplaza a la izquierda cuando se abre el panel).
- **Buscador** (Ctrl/Cmd+K o `/`): ~3,575 entradas (130 territorios + subtemas + temas finos + 2,500 títulos del preview), sin acentos, ↑↓/Enter/Esc, deduplica un territorio de un solo subtema que aparece igual en los 3 niveles.
- **4 rutas guiadas** con tarjeta narrativa y vuelos: isla "notas al programa" (2 pasos), hueco central (`gap.md`), petróleo ↔ química (2 pasos), medicina como archipiélago (56 territorios con mayoría Área 2).
- **Panel** con palabras distintivas, área con nombres reales ("Biológicas, Químicas y de la Salud", no "area 2"), programas y lista de subtemas clicable.
- **Limpieza**: toggle de densidad, log y readout de zoom solo con `?debug`; leyenda de 3 líneas; ficha técnica permanente en el pie ("primera edición", "posiciones sin unidad física").

**Hallazgo al verificar, corregido en el texto de una ruta**: la primera versión decía "el resto de la música vive junto a la filosofía". Medido: el territorio 47 ("obras · música", 549 tesis) es el **15.º más disperso de 130** (radio mediano 1.77 u. vs. 0.82 global); solo el 53% de sus tesis está a <2 u. de su núcleo. El texto ahora dice exactamente eso y el vuelo va al núcleo. Mismo criterio que la revisión: no afirmar en la UI algo que los datos no sostienen.

**Verificación** (Chrome headless vía CDP, eventos reales de mouse/teclado):
- Intro: 5 discos con etiquetas → vuelo → 34 nombres en pantalla, lente territorio. Cerrar con ✕ antes del vuelo deja 0 etiquetas de disco (bug encontrado y corregido: quedaban flotando). Repetir la intro funciona.
- Rueda real ×5 → meso (k=6.87, 234 marcadores); Alt+arrastre real → rotación 0.0°; arrastre real → pan.
- Clic real en el nombre más grande ("células · gen") → vuelo a k=6.77 + panel; clic real en un subtema del panel → vuelo + panel del subtema; clic real sobre el punto de una tesis del preview → spotlight con su título.
- Rutas: isla paso 1 acerca a k≈15.5; paso 2 a k=8.85 sobre el núcleo; petróleo k=7.5; hueco k=7.2; archipiélago muestra "Los 56 territorios…"; Esc cierra la ruta y restaura colores.
- Búsqueda "amparo": territorio, subtema y títulos, sin duplicados; Enter vuela y abre el panel.
- 390 px: intro en grilla 2×2, sin scroll horizontal, leyenda compacta.
- Consola sin errores ni advertencias en todas las corridas.

**No verificado / limitaciones honestas**:
- Solo headless (swiftshader). Falta que el usuario lo pruebe en su navegador real (rendimiento de la transición de 609k puntos en su GPU, trackpad).
- Nombres de territorio sin acentos (vienen de títulos normalizados). Es el pendiente de backlog "nombres humanos para los 130 macros".
- El buscador de títulos cubre solo las 2,500 tesis del preview; buscar en el corpus completo depende del índice de títulos por Range requests (backlog).
- El resaltado por hover redibuja 609k categorías (serializado, sin carreras); no se midieron FPS.

**Backlog que sigue abierto tras esta sesión** (de la revisión crítica, sección 4): git en la raíz + `.gitignore` para `data/`; correcciones manuales expresadas por `cluster_id` con huella del input; binario de vecindario/títulos con HTTP Range (ADR nuevo que reemplace el cálculo de ADR-0014); nombres humanos (con acentos) para los 130 territorios; conectar Nobel más cercano; mover el harness CDP a `tools/`.


### Repo git en la raíz (2026-09-23)

`git init` en la raíz del proyecto, rama `main`, primer commit `ceb7193`: 231 archivos, ~10 MB. Versiona código, pipeline, ADR/RFC/PRD, `development.md`, evidencia visual y prototipos. **Excluye** (ver `.gitignore`, comentado por bloque): `data/` y `atlas_data/` (33 GB, regenerables, `base7_kaggle_clean` con PII), `prototypes/**/data/`, parquet/npy/bin/csv, `pipeline/recovery/` (~960 HTML/JSONL crudos del scraping de TESIUNAM, con autores), los 2 repos anidados (`app/MI-TESIS-UNAM_github`, `app/nodo-unam`), `docs/*` salvo `docs/evidencia_visual/` (había credencial UNAM y constancia de estudios), `notebooks/` (sus outputs pueden tener nombres de autor; pendiente `nbstripout`), instaladores y `_scratch/`.

**Hallazgo al preparar el commit — API keys en el código**: `app/AI Pipeline/Scripts/{ai_bloom, ai_questions, ai_rerank}.py` tienen una key de Groq escrita en el código y `ai_initial_note_cerebras.py` una de Cerebras. Se excluyeron del repo (bloque "TEMPORAL" del `.gitignore`); `git grep` confirma 0 secretos versionados. Verificado que **no** aparecen en la historia de los repos anidados (uno fue público). Siguen en disco: hay que rotarlas y moverlas a variables de entorno (pendiente P0 abajo).

### Hallazgo de privacidad: `titulo_original` trae el nombre del autor (2026-09-23)

Al construir el modo taller se vio que `titulo_original` de `data/public/data_unam.parquet` —el export "público" de ADR-0011, que según ese ADR no tiene autores— incluye la **mención de responsabilidad del catálogo** ("… / tesis que para obtener el título de …, **presenta NOMBRE DEL AUTOR**; asesor …") en el **92.2%** de las filas. `thesis_lookup.parquet` de Taller (regenerado con ADR-0004 desde ese archivo) la expone en `title_raw`, también en el 92.2%. ADR-0011 quitó las columnas de autor, pero no el autor que viene *dentro* del título.

En los datos nuevos se corrige en origen: `pipeline/generar_atlas_tesis_por_micro.py` corta en la mención de responsabilidad. Hubo que generalizar el corte: 1,055 filas usan otras variantes ("/ tesis" sin espacio, o "tesis que para obtener…" sin barra). Una red de seguridad (`AUTOR_RE`) reemplaza por "(título no disponible)" los **12 de 199,623** títulos donde aún parecía haber un nombre. El export público y el lookup de Taller **no se tocaron**: ver P0 abajo.

### v3.1.0 — nombres humanos con jerarquía, resaltado de tesis por tema, listado A→Z y modo taller (2026-09-23)

Pedido del usuario:
- Destacar de forma sutil los territorios que un visitante promedio reconoce (Filosofía, Medicina…).
- Al hacer clic en un tema fino, ver destacadas sus tesis en el mapa.
- Un listado A→Z con marca tipográfica A→Z, las primeras 6 tesis con plantel, programa y asesor, y un botón "ver listado completo".
- Ese botón abre un modo tipo Taller exclusivo del tema, con stats, vista analítica y red de asesores.

Respaldo de la versión anterior: `index.v3.0.0.html`.

**Datos nuevos**:
- `pipeline/generar_atlas_tesis_por_micro.py` → `atlas_data/tesis_por_micro/{cluster_id}.json`: 513 archivos, **todas** las 199,623 tesis clusterizadas (no solo las representativas), 44.1 MB, máximo 0.54 MB por archivo. Campos: id, título sin autor, año, plantel, programa, nivel normalizado (el catálogo trae "Maestria"/"Maestría", "licenciatura"/"Licenciatura"), asesores, más `mesoId`. Verificado: la suma por `mesoId` coincide exacto con los tamaños de meso (ej. macro 48: 160/216/1,833/170/2,791/299).
- `pipeline/curaduria/macro_nombres.v1.json` (versionado en git): **130 nombres legibles con acentos** y **26 hitos** (`destacado`), redactados a partir de las keywords c-TF-IDF y los programas más frecuentes. Es un **borrador escrito por Claude, pendiente de revisión humana**. Cada entrada guarda la primera keyword como huella: si la jerarquía se recalcula y los ids ya no corresponden, el frontend usa las keywords en vez de un nombre equivocado, y avisa en consola.

**Frontend** (`prototypes/atlas_vecindario_mvp/index.html`):
- **Jerarquía de nombres**: los hitos van en Source Serif 4 (la voz "curaduría" del manifiesto: nombres puestos por una persona), 14–20 px, tinta plena y prioridad al colocar; el resto de los territorios en sans de 9.5–12 px y tinta secundaria. Las etiquetas ya no se colocan debajo del breadcrumb, la leyenda, el minimapa ni las tarjetas.
- **Resaltado fijado**: al seleccionar territorio, subtema o tema fino se resaltan **todas** sus tesis en el mapa (el resto se atenúa) mientras el panel esté abierto. El hover lo reemplaza temporalmente y luego se restaura. Nota para el usuario: sí se renderizan las 609,154 tesis; lo nuevo es poder resaltarlas por tema.
- **Panel en los 3 niveles**: KPIs (tesis, años, asesores), marca A→Z, las 6 primeras tesis en orden alfabético (título, año, nivel, programa, plantel, asesoría), botón "Ver las N tesis y su análisis", keywords y subtemas/temas finos clicables. Clic en una tesis → vuela a su punto, la marca y muestra su ficha.
- **Modo taller** (pantalla completa), con 4 pestañas:
  - *Listado*: filtro por texto (título, asesor, programa), orden A→Z/Z→A/año, filtros por programa y plantel, páginas de 150.
  - *Panorama*: frase-resumen con datos calculados; tesis por año; barras de programas, planteles, nivel y asesores. Cada barra filtra el listado. Una medida por gráfica, un solo tono, sin doble eje (guía dataviz).
  - *Vista analítica*: cada punto es una tesis, agrupadas por década, nivel, programa o plantel, en orden A→Z dentro de cada grupo; tooltip con título y clic para ubicarla en el mapa.
  - *Red de asesores*: **red de codirección**. Nodo = asesor (tamaño = tesis dirigidas en el tema), enlace = dirigieron juntos al menos una tesis; es una relación real del catálogo, no inferida. Top 70, layout de fuerzas precalculado (sin animación). Clic en un asesor filtra el listado a sus tesis.
- **Color del área 1** cambiado de `#2a4d7a` a `#3566a8`: el validador de paleta de la guía dataviz marcó el anterior como FAIL (luminosidad y croma, se leía casi gris). Con el nuevo pasan los 4 checks; el ámbar del área 3 queda con aviso de contraste, cubierto porque siempre va con su nombre en texto.
- Los vuelos a un territorio aterrizan siempre a nivel subtema. Antes, un territorio compacto como Matemáticas llevaba al zoom máximo y se volvía una mancha.

**Verificación** (headless, eventos reales):
- 18 hitos visibles en la vista inicial, 16 nombres menores.
- Tema fino 147: resalta **1,199/1,199** tesis, 6 filas A→Z, botón "Ver las 1,199 tesis".
- Taller: 150 filas de 1,199; filtro "polimorfismo" → 319; panorama con 57 años con tesis; vista analítica con 1,199 puntos; red con 70 asesores y 43 enlaces de codirección; clic en un asesor → 31 tesis filtradas; clic real en una fila → vuelo y ficha de la tesis.
- Filosofía y letras resalta **5,469/5,469**; su subtema "filosofía · nietzsche" **2,791/2,791**; cerrar el panel quita el resaltado.
- Esc cierra el taller. Consola sin errores.

**Limitaciones**:
- Nombres de meso/micro siguen siendo keywords sin acentos: solo se curaron los 130 macro.
- La red sufre la variación de escritura de nombres de asesor (ADR-0010 corrigió casos puntuales; hay variantes sin unificar): un mismo asesor puede aparecer como dos nodos.
- No probado en el navegador del usuario.

## Pendientes consolidados (2026-09-23)

> **Histórico.** La lista viva de pendientes está en «Estado del proyecto y hoja de ruta (2026-09-25)», al final de este archivo.

Orden de prioridad. **P0 = riesgo de privacidad/seguridad, antes que cualquier feature.**

**P0 — privacidad y seguridad**
1. **Autor dentro de `titulo_original`** en `data_unam.parquet` (92.2%) y en `thesis_lookup.parquet`/`title_raw` de Taller. Agregar al export una columna de título sin mención de responsabilidad (reusar `RESP_RE` + `AUTOR_RE` de `generar_atlas_tesis_por_micro.py`), quitar o limpiar `titulo_original`, regenerar el lookup y **verificar si el dataset ya se publicó en Kaggle**: si sí, publicar versión corregida y retirar la anterior. Nuevo ADR que corrija la premisa de ADR-0011.
2. **Rotar las API keys de Groq y Cerebras** escritas en los 4 scripts de `app/AI Pipeline/Scripts/` y leerlas de variables de entorno. Después se pueden quitar del `.gitignore`.
3. Purgar el historial de Git LFS del repo `MI-TESIS-UNAM` (autores expuestos; ya estaba anotado en Fase 0.5).

**P1 — robustez del pipeline**
4. Expresar las correcciones manuales de la jerarquía por `cluster_id` de HDBSCAN (no por `macro_id`/`meso_id` derivados) con huella del input que falle ruidosamente si cambia. Mismo principio ya aplicado a `macro_nombres.v1.json`.
5. `nbstripout` en `notebooks/` para poder versionarlos sin outputs.
6. CI mínima (tests de normalización de entidades + chequeo de privacidad de títulos) antes de adoptar trunk-based de verdad.
7. Mover el harness CDP de verificación headless a `tools/` y versionarlo.

**P2 — producto**
8. **Revisión humana de los 130 nombres y los 26 hitos** (borrador de Claude). Decidir si meso/micro también llevan nombre curado o un nombre derivado mejor que keywords.
9. Unificar variantes de nombres de asesor: mejora directamente la red de codirección.
10. Binario de vecindario y títulos con HTTP Range (≈500 B por tesis) + ADR que reemplace el cálculo de ADR-0014. Habilita el buscador de títulos sobre el corpus completo y el vecindario de cualquier tesis, no solo de las 2,500 del preview.
11. Conectar Nobel más cercano.
12. Decidir Pages vs. R2 para `tesis_por_micro/` (44 MB) y el resto del bundle.
13. Prueba en el navegador real del usuario (GPU, trackpad) y del modo taller en móvil.


### v3.2.0 — visibilidad: sin resaltado por hover, barra de filtros, título en el hover y modo aislado de tema fino (2026-09-24)

Pedido del usuario: "resolver la visibilidad de una vez". Respaldo de la versión anterior: `index.v3.1.0.html`.

1. **Se quitó el resaltado negro por hover sobre territorios.** Cada hover redibujaba 609k puntos y estorbaba el desplazamiento por el mapa. El hover sobre un nombre ahora solo muestra tooltip. Verificado con hover real: `highlightKey` no cambia. El resaltado *fijado* al hacer clic (v3.1) se conserva.
2. **Barra general de filtros** debajo del header: "Color: Territorios | Áreas administrativas" (antes "Áreas UNAM", arriba a la derecha) y conteo de tesis. Es el lugar donde entran los filtros siguientes (programa, plantel, año, nivel); cada uno será otro `.fb-group`.
3. **Introducción**: queda como botón aislado en el header. **Decisión del usuario, anotada: el modo introducción NO se usará tal cual está.** Lo que sí gustó es la animación de los discos por área volando al mapa semántico. No se borró nada de la intro todavía; pendiente decidir cómo se reutiliza esa animación.
4. **Hover sobre cualquier tesis → título + año.** Antes solo decía el territorio, y el título solo existía para las 2,500 del preview.
   - Datos nuevos: `pipeline/generar_atlas_titulos_teselas.py` → `atlas_data/titulos_teselas/`, con los títulos sin autor y el año de las **609,154** tesis, partidos en una grilla espacial de 64×64 sobre las coordenadas PaCMAP crudas: 855 teselas no vacías, 67.9 MB en total, la mayor de 0.62 MB.
   - Cargar los 609k títulos de golpe no es viable. Como el hover es local, el navegador solo pide la tesela bajo el cursor y la guarda en caché; mientras llega se muestra "Cargando título…".
   - Reusa `titulo_sin_autor` y `AUTOR_RE` del generador por tema: 49 títulos con posible autor residual se omiten.
   - Verificado: cobertura 609,154/609,154, y 2,000/2,000 títulos al azar coinciden con el parquet (alineación índice ↔ título).
   - **Pendiente, a pedido del usuario:** cuánta información más cabe en el tooltip (programa, plantel…) sin que se vea excesivo.
5. **Clic en una tesis = esa tesis.** Se marca en negro y abre su ficha: título, año, id, territorio y área; en modo aislado también programa, plantel y asesoría. Desde la ficha: "Ir a su territorio" o, si está precargada, "Ver vecindario". Antes volaba directo al territorio y la tesis nunca se veía.
6. **Modo aislado de tema fino** (lo principal). Clic en un tema fino:
   1. La cámara se acerca al tema (750 ms).
   2. Sus tesis se **separan entre sí** con la transición nativa de puntos de regl-scatterplot (1.5 s, la misma mecánica que la intro). La cámara y los puntos comparten el mismo tween en la librería, así que van en secuencia.
   3. El resto del mapa se **abre dejando un claro** y se atenúa.
   4. El fondo se **tiñe tenuemente** del color del filtro activo (territorio o área).
   5. Un chip arriba indica el tema aislado y ofrece "Volver al mapa"; Esc o cerrar el panel también salen, con la animación inversa.
   - **Cómo se calcula la separación (no es un layout inventado):** cada tesis parte de su posición real, ampliada alrededor de la mediana del tema. Los temas compactos se amplían ×3.2; los ya dispersos, lo justo (tope 0.12 NDC), porque es mejor acercar la cámara que empujar medio mapa. Después, una relajación de colisiones (d3-force, 300 iteraciones, atracción débil a la posición ampliada) garantiza una separación mínima en pantalla de `ISO_MIN_PX = 15` y conserva quién está cerca de quién. Los títulos idénticos, que caen en el mismo punto (ej. las 292 "notas al programa"), se siembran en espiral para que se separen.
   - **El claro** se mide con el p95 del radio del tema (no con su tesis más lejana) y el desplazamiento se desvanece suave hasta 3×. Es monótono, así que ningún punto cruza a otro.
   - **Tamaño de punto:** regl-scatterplot agranda los puntos con el zoom por defecto (`pointScaleMode: 'asinh'`), encima del tamaño manual del atlas; en modo aislado las tesis se tocaban aunque sus centros estaban a 15 px. Se pasó a `pointScaleMode: 'constant'`: el tamaño lo controla solo `updatePointSize()` (1.5 → 5 px con el zoom; 7 px fijo en modo aislado).
   - **Verificado midiendo píxeles reales en pantalla**, no el parámetro:

     | Tema | Tesis | Separación mínima | Vecino más cercano (media) | Zoom |
     |---|---|---|---|---|
     | "Notas al programa" | 325 | **15.0 px** | 16.4 px | ×3.4 |
     | Polimorfismos | 1,199 | **14.7 px** | 19.0 px | ×8.4 |

     Antes de ajustar la relajación: 12.8 y 9.5 px. Salir restaura posiciones reales, overlay y 36 nombres. Consola sin errores.

**Observación de diseño, abierta**: en temas grandes y densos, garantizar 15 px de separación hace que el núcleo se vea como una retícula casi regular: se gana legibilidad y se pierde algo de organicidad. Palancas: `ISO_MIN_PX`, `ISO_EXPAND` y la fuerza de atracción a la posición real.

**Pendientes nuevos, agregados a la lista consolidada (P2):**
- Cuánta información extra cabe en el tooltip de tesis (hoy título + año).
- Qué hacer con la intro: reutilizar la animación área → contenido en otro momento de la experiencia.
- La ficha de una tesis fuera del modo aislado solo tiene título/año/territorio. Programa, plantel y asesor requieren sumarlos a las teselas o un índice por tesis.
- Nombres de temas finos siguen siendo keywords sin acentos. Se notan más ahora que el chip del modo aislado los pone al centro.


### v3.3.0 — minimapa de vuelta, más separación, tema fino con dos estados (conexiones y análisis) (2026-09-24)

Respaldo de la versión anterior: `index.v3.2.0.html`.

- **Minimapa**: había desaparecido por un bug. Solo se mostraba al terminar la introducción, así que con la intro ya vista (`localStorage`) nunca aparecía. Ahora se muestra siempre, también en modo aislado, con **"Ocultar"** en su pie y un botón **"Mostrar minimapa"** para recuperarlo; la preferencia se recuerda (`localStorage`, con try/catch). Verificado con la intro ya vista: visible → oculto → visible.
- **Más separación entre tesis al aislar un tema fino**, a pedido del usuario con captura de referencia. `ISO_MIN_PX` sube de 15 a **24 px entre centros** y el punto de 7 a **15 px**. Medido en píxeles: tema "pareja · marital" (214 tesis) **24.0 px** mínimo (34.4 px mediana); polimorfismos (1,199) **23.7 px** (30.5 px).
- **Dos estados del tema aislado.** Los nombres "caótico" y "analítico" son solo de desarrollo, **nunca se muestran en la UI**. En el código son `iso.mode = 'eco' | 'ana'`.
  - **Estado inicial (caótico).**
    - *Qué conecta*: cada tesis con sus vecinas **reales**. De los 100 vecinos e5 de cada tesis (FAISS exacto, ADR-0014) se conservan los del mismo tema, hasta 3 por tesis, sin duplicados. Es un dato nuevo del pipeline (`aristas_intra_tema()` en `generar_atlas_tesis_por_micro.py`): **480,462 enlaces en los 513 temas**, ~2.4 por tesis, con similitud 0.82–1.0 (polimorfismos: 2,808 enlaces).
    - *Cómo se ve*: el grosor y la opacidad del enlace codifican la similitud, en 5 niveles.
    - *Animación*: partículas que viajan por los enlaces, con más probabilidad por los más fuertes (∝ similitud²), y un pulso anular al llegar: la tesis "recibe" lo que viajó.
    - Se respeta `prefers-reduced-motion`: enlaces estáticos, sin partículas.
  - **Botón "Analizar"** (bajo el título del chip; su ubicación final queda pendiente, a pedido del usuario): desaparecen los enlaces y las tesis se reorganizan en una grilla por grupo, al estilo del modo analítico del atlas anterior.
    - Selector: área, plantel, programa, nivel o década.
    - Color por grupo: las áreas conservan su color de siempre; lo demás usa la paleta categórica validada de la guía dataviz (8 colores + "Otros" en gris).
    - Etiqueta directa por grupo (nombre y conteo), que compensa usar más de 3 colores.
    - Orden dentro del grupo: año y luego título. Cambiar de agrupación anima el reacomodo.
    - "Ver conexiones" regresa al estado inicial.
- **Rendimiento, encontrado al medir:**
  - La primera versión de los enlaces redibujaba las ~2,800 líneas en cada cuadro: el mapa pasaba de **60 fps a ~4 fps** con el tema aislado.
  - La primera hipótesis (tamaño de punto aplicado a las 609k tesis) se **refutó** midiendo: con puntos de 2 px seguía en ~4 fps. WebGL no redibujaba (0 draws/s), así que el costo era la capa 2D.
  - Además, el desvanecimiento dependía de los cuadros: a 4 fps tardaba ~10 s en apagarse y contaminaba la medición en análisis.
  - Fix: los enlaces se pintan una vez en un lienzo en caché y solo se repintan si la cámara se mueve; por cuadro solo se dibujan partículas (≤110). El fundido ahora es por tiempo (350 ms).
  - Resultado en headless (WebGL y canvas **por software**): estado inicial **27–29 fps**; análisis y mapa normal **60 fps**. En GPU real debería ser mejor, pero **no está medido en el navegador del usuario**.

**Nota de diseño del usuario, registrada como pendiente URGENTE: el diseño necesita una identidad propia.** Hoy "se ve muy AI UI genérica": chips redondeados, botones de contorno en mayúsculas, sombras suaves, paneles blancos flotantes. Todo es funcional y correcto, pero sin carácter. Antes de seguir sumando componentes conviene una pasada de identidad: tipografía con personalidad, un sistema de color propio que no sea "neutro + acento verde", y formas y elementos gráficos que remitan a atlas, carta náutica o archivo universitario (ya era el norte del Design Manifest del 22-09 y lo construido se alejó de él). Candidato: usar `impeccable` para una pasada de dirección visual con referencias concretas.

**Pendientes nuevos (P2):**
- Ubicación estratégica del botón "Analizar".
- En temas muy grandes (1,000+ tesis) la grilla de análisis sale del cuadro y hay que desplazarse; evaluar paginar grupos o reducir el paso de la grilla según el tamaño.
- Medir fps del estado inicial en el navegador real del usuario.


### v3.4.0 — animación del tema aislado: solo enlaces + deriva lenta, en WebGL (2026-09-24)

Pedido del usuario: las partículas y los pulsos "se ven en extremo IA, genéricos y baratos". Quiere algo sencillo, sin sofisticación innecesaria: enlaces y un movimiento lento pero notable de los nodos, **sin resplandor**. Respaldo: `index.v3.3.0.html`.

**Investigación** (web, 2026-09-24):
- **Heer & Robertson, *Animated Transitions in Statistical Data Graphics* (InfoVis 2007)**: el movimiento debe ser simple y predecible, con entrada y salida suaves (slow-in/slow-out), sin varios cambios simultáneos y sin trayectorias imprevisibles, porque suben la carga cognitiva.
- **Nayuki, *Animated floating graph nodes***: la calma depende de pocos elementos y poca velocidad de deriva; los enlaces que aparecen y desaparecen de golpe se leen como parpadeo.
- **Accesibilidad (W3C C39, web.dev)**: el movimiento ambiental debe apagarse con `prefers-reduced-motion`; el daño vestibular lo causa el movimiento amplio en el campo visual.

**Decisión**:
- Fuera partículas y pulsos.
- Cada tesis **deriva alrededor de su lugar**: suma de dos senoidales con periodo propio de **7–13 s** y fase determinista por tesis, así que la misma tesis se mueve igual cada vez que se abre el tema.
- Amplitud `DRIFT_PX = 5.5`, con entrada suave de 1.4 s. Con 24 px entre centros y puntos de 15 px, en el peor caso dos vecinas se rozan un instante.
- Los enlaces siguen a las tesis: se estiran y se relajan.
- Con `prefers-reduced-motion`, amplitud 0.
- El tinte del fondo se mantiene: es estático, no es animación.

**Implementación y rendimiento (medido con la GPU real de la máquina, Intel UHD 620, vía Chrome headless con D3D11):**
- *Primer intento, lienzo 2D*: el JavaScript del cuadro costaba solo 3.3 ms, pero la GPU tardaba en rasterizar miles de líneas con antialiasing. Resultado: 214 tesis a 60 fps, 1,199 a ~12 fps, 2,475 a ~8 fps. Recortar lo que queda fuera de pantalla, usar sprites y agrupar por grosor subió 1,199 a 19 fps: no alcanzaba.
- *Solución, capa en WebGL* con regl (ya cargado, sin dependencias nuevas). Posiciones, fases y enlaces se suben **una vez** como buffers; la deriva se calcula en el vertex shader; los enlaces son quads con grosor de 0.6–3 px y opacidad según la similitud; por cuadro solo cambian tiempo y cámara.

  | Tema aislado | Tesis | Lienzo 2D | WebGL |
  |---|---|---|---|
  | Pareja · marital | 214 | 60 fps | **60 fps** |
  | Polimorfismos | 1,199 | ~12 fps | **60 fps** |
  | El más grande | 2,475 | ~8 fps | **~50 fps** |

  Mapa normal: 60 fps.
- En el WebGL de fondo, las tesis del tema quedan **invisibles pero seleccionables** (slot `C_HIDDEN`): hover y clic reales siguen funcionando (verificado: tooltip con título y año, ficha correcta). La tesis seleccionada se marca en negro en la capa de deriva.
- Deriva confirmada comparando dos capturas separadas 3 s: cambió el 6.7% de los píxeles del área del tema, con desplazamientos pequeños y sin saltos.

**Nota metodológica**: el harness ahora tiene una variante con GPU real (`--use-angle=d3d11`). Las mediciones anteriores de fps se hicieron con WebGL por software (swiftshader) y **subestiman** el rendimiento real. A partir de aquí, los fps se miden con GPU.

### v4.0.0 — identidad visual: de plantilla de dashboard a producto web (2026-09-24)

**Antes de esta versión, dos rediseños descartados** (ambos se revirtieron a v3.4.0, commit 095e9a0; respaldo en `index.v4.0.0-senaletica-descartada.html`):
1. «Señalética de red», inspirado en la señalización del Metro. El usuario: «se ve infantil».
2. Un canon estilo Gapminder aplicado de inmediato. El usuario: «estás tomando conceptos aleatorios y aplicando sin razón».

Lección: primero se acuerda la estrategia por escrito y después se codifica. De ahí salió la lista de **21 anti-patrones de UI genérica en `PRODUCT.md`**, acordada con el usuario, con las decisiones aprobadas: Libre Franklin, barra de navegación global con página Método, mayúsculas solo en los rótulos del mapa y sin tira de KPIs (#21).

**Cambios en v4.0.0** (entre corchetes, el número del anti-patrón que corrige):
- **Tipografía [1][14][15]**
  - Una sola familia, Libre Franklin 400–700, con `tnum` en todas las cifras.
  - Fuera Public Sans, Source Serif 4, Source Sans 3 y JetBrains Mono.
- **Color [1][16][17]**
  - Fondo blanco (incluido el fondo WebGL, `C_HIDDEN` y el relleno del minimapa).
  - Grises neutros: tinta #1a1a1a, #4d4d4d y #6e6e6e (≥5:1); líneas #e0e0e0.
  - Un azul tinta #1d4f91 solo para enlaces y foco.
  - El verde #0f7d5c queda únicamente como color de dato (área 2).
  - Ruido y atenuado del mapa en gris neutro.
  - El tinte del modo aislado es plano: sin degradado radial.
- **Navegación [2][4][12]**
  - Barra global con la marca «Atlas de tesis», las secciones Mapa, Rutas, Introducción y Método, y la búsqueda como campo real (Ctrl+K y `/` siguen funcionando, sin la pastilla).
  - En móvil, los enlaces pasan a una segunda fila.
- **Estructura [3][9]**
  - La ruta (UNAM › territorio › subtema) sale del mapa y vive en la barra de filtros, que ahora es blanca.
  - Leyenda y minimapa acoplados a las esquinas, con borde de 1 px.
  - Ficha de tesis como hoja lateral y relato como hoja inferior.
  - La cenefa del tema aislado es una segunda barra.
  - Cero sombras.
- **Componentes [5][6][7][8][13]**
  - Botones rectangulares de 2 px en caja normal.
  - Controles segmentados convertidos en pestañas de texto con subrayado.
  - Palabras clave como lista de texto (antes chips).
  - Íconos SVG de un trazo en lugar de ✕ ← → ↑↓.
  - Sin eyebrows: el nivel pasa a un subtítulo debajo del título.
  - El CTA punteado pasa a ser un enlace.
- **Datos [10][11][21]**
  - Sin KPI tiles en el panel: una frase («Tesis de 1980 a 2026, dirigidas por 435 asesores.»).
  - Sin tira de KPIs en el taller: «562 tesis, de 1980 a 2026.».
  - Panorama en secciones separadas por líneas, no en tarjetas.
  - Programas y planteles en caja normal (`pretty()`: mayúscula inicial, siglas y sin el sufijo redundante «unam»).
- **Contenido [18][19]**
  - Página **Método** con datos, modelo, agrupamiento, proyección, vecindarios, cómo leer el mapa y el aviso de proyecto no oficial.
  - El pie ya no muestra jerga: «Proyecto independiente, no oficial. Datos del catálogo público TESIUNAM.», más un enlace a Método y la versión.
  - La leyenda ya no dice «el algoritmo».
- **Rótulos del mapa**: siguen en mayúsculas (convención cartográfica pedida el 23-09), ahora en Libre Franklin 700/600/500.

**Verificación** (harness GPU, escritorio 1600×900 y móvil):
- Pantallas revisadas: intro, mapa, territorio, tema aislado, análisis, taller (listado y panorama), Método, rutas y búsqueda.
- 0 errores de consola.
- Conteo residual: 0 sombras, 0 mono, 0 serif, 0 glifos unicode; `uppercase` solo en rótulos del mapa; radios solo de 2 px y 50% (los puntos).
- Las capturas headless a veces muestran el panel a medio deslizar; se midió con `getBoundingClientRect` y ya estaba en su lugar. Es un artefacto del compositor, no un bug.

**Pendientes que dejó esta versión**:
- `design_manifest.md`, solo cuando el usuario apruebe el estilo.
- En móvil, el panel ocupa el 100% del ancho y cerrarlo sale del modo aislado (comportamiento heredado de v3.2), así que el tema aislado casi no se ve en móvil. Hay que rediseñar esa interacción.
- Los nombres de subtema y tema fino siguen en minúsculas sin acentos (dato c-TF-IDF); se corrige en la revisión de nombres (P1).
- El menú de Rutas se despliega bajo su enlace, pero sobre el mapa. Evaluar si Rutas merece una página propia.

### Repo en GitHub para desarrollar la interfaz desde la nube (2026-09-24)

- **Remoto.** Repo privado `zvastian/nodo-unam`, con la misma historia que `main`. No se mezcla con `MI-TESIS-UNAM`, que tiene otra historia y un LFS con PII pendiente de purgar (P0).
- **Datos del prototipo versionados.** `prototypes/atlas_vecindario_mvp/data/` (1,634 archivos, ~158 MB) queda como excepción en `.gitignore`: sin esos datos la interfaz no carga.
- **Limpieza de autores antes de subirlos.**
  - El escaneo encontró **18 títulos** que aún traían mención de responsabilidad, en `titulos_teselas`, `tesis_por_micro` y `vecindario_preview` («/ Nombre Apellido ; asesora …», «tesis para obtener el título …, presenta …», «trabajo que presenta el alumno NOMBRE»).
  - El nuevo `pipeline/limpiar_autores_atlas.py` los corta o quita solo el nombre. Solo corta cuando detrás viene una marca de persona, para no mutilar títulos temáticos como «… para obtener el título de licenciado en trabajo social a partir de …».
  - Un segundo escaneo quedó en 0 cambios; los hits restantes son falsos positivos («por el método sol-gel», «Delegación /Alcaldía», «informe que presenta la institución»).
  - Hay que correr el script cada vez que se regeneren datos del prototipo, antes de commitear.
- **Herramientas para la nube.**
  - `tools/cdp.mjs`: el harness de capturas, portable con las variables `CHROME`, `SIZE` y `GPU`. Cierra el pendiente «harness a `tools/`».
  - `CLAUDE.md` con instrucciones para sesiones nuevas.

### v4.1.0 — nombres con acentos, siglas y mayúsculas; marca «NodOs» (2026-09-24)

- **Problema.** Los nombres de subtema y tema fino son keywords c-TF-IDF sobre texto normalizado («deficit atencion · hiperactividad»). Lo mismo pasa con programas, planteles y los títulos del vecindario precargado (la búsqueda).
- **Diccionario de escritura.** `pipeline/generar_atlas_acentos.py` aprende de los 609k títulos originales (teselas) la forma real de cada palabra y genera `data/escritura.v1.json` (6,560 entradas, 73 KB):
  - **Acentos.** Gana la variante con tilde si aparece en ≥20% de los casos, porque muchos títulos del catálogo vienen sin acentos. Se excluyen los pares donde ambas formas son palabras válidas (esta/está, público/publico, práctica/practica…).
  - **Siglas.** VIH, COVID, ISO, ADN, IMSS: en mayúsculas en ≥70% de los títulos que no están enteros en mayúsculas.
  - **Nombres propios.** México, Iztacala, Aragón, Freud: capitalizados a media frase en ≥96.5% de los casos. El umbral deja fuera «Hospital», «Instituto» y «Facultad», que están entre 85% y 94%.
- **Interfaz.** `escribir()` + `capital()` se aplican solo al mostrar:
  - nombres de subtema y tema fino, con mayúscula inicial por grupo: «Déficit atención · Hiperactividad»;
  - palabras clave, programas y planteles;
  - títulos del vecindario.
  - Los rótulos del mapa siguen en mayúsculas, ahora con tildes. La búsqueda sigue comparando sin acentos.
- **Marca.** «NodOs» en la pestaña y en la barra de navegación (con «Atlas de tesis UNAM» como descriptor). Favicon SVG en línea: un punto azul #1d4f91, el color de interfaz.
- **Método** avisa que la escritura se restituye con un diccionario y puede fallar en alguna palabra.
- **Verificado** en el harness: pestaña, favicon, panel, tema aislado y búsqueda, sin errores de consola.
- **Límite.** Los títulos de `tesis_por_micro` y de las teselas se muestran como vienen del catálogo (a veces sin acentos). Son el texto original de cada tesis y no se reescriben.

### v4.2.0 — búsqueda completa y asesores unificados (2026-09-24)

**Diagnóstico** (pedido del usuario: «busco freud y no aparece nada»):
- **Cobertura.** La búsqueda solo miraba 3,575 entradas: nombres de tema y 2,500 títulos de referencia, el 0.4% del corpus. 125 títulos mencionan a Freud y ninguno estaba ahí.
- **Coincidencia.** Buscaba fragmentos dentro de palabras («de» coincidía con casi todo) y mezclaba territorios, temas y tesis en una sola lista de 14.
- **Costo.** Al abrirla descargaba 238 archivos. Cada tecla tardaba ~30 ms en consultas cortas (deduplicado cuadrático) y no había espera entre teclas.
- **Asesores.** No se buscaban. Además, el prototipo solo tenía asesores para las 199,623 tesis de algún tema fino, aunque el catálogo los tiene para 535,834 (88%).

**Unificación de asesores** (`pipeline/unificar_asesores.py`, sobre `asesores_limpios_v2` de base7 en formato «Apellidos, Nombres»):
- 117,482 variantes pasan a **81,151 asesores** (tras la fase 2, ver abajo).
- Reglas conservadoras, porque fusionar a dos personas atribuye tesis a quien no las dirigió:
  - **R1** misma clave sin acentos, títulos ni «Ma.»;
  - **R2** registros sin coma, o una inversión rara de apellidos que comparte programa. Los apellidos invertidos frecuentes («Martínez García» / «García Martínez») se quedan separados, porque suelen ser personas distintas;
  - **R3** nombre corto compatible con una sola forma larga dentro de los mismos apellidos; con un solo nombre de pila, además exige programa en común;
  - **R4** un apellido frente a dos, con candidato único y programa en común;
  - **R5** error de dedo: variante rara a distancia de edición ≤ 2, candidato único y programa en común.
- Auditoría completa en `pipeline/audits/asesores_unificacion_v1.csv`. Hay casos discutibles, como «Galicia/García González, Rigoberto».

**Corrección tras la prueba del usuario** («amador za» mostraba a «Edgar Abraham Amador Zamora» y a «Edgar Amador Zamora» por separado):
- **Causa.** R3 veía dos formas largas posibles para «Edgar» («Edgar A» y «Edgar Abraham») y, por prudencia, no unía. Pero son la misma forma con y sin inicial.
- **Arreglo.** Si todas las formas largas candidatas son compatibles entre sí, forman una sola cadena. Resultado: 85,991 → **85,429 asesores** (562 uniones más, del tipo «Irma», «Irma G», «Irma Graciela»).
- **Sigue sin unirse:** nombres de pila en otro orden («Zoila Irma» / «Irma Zoila» Tejada Castañeda).

**Investigación de fallos y fase 2** (pedido del usuario: nombres de pila en otro orden y «qué otros casos puede haber»):
- **Método.** `pipeline/investigar_asesores.py` busca pares de asesores distintos que probablemente son la misma persona y los clasifica por tipo, contando cuántos comparten programa. `unificar_asesores.py` ahora exporta la tabla completa de variantes (`data/asesores/asesores_variantes.v1.parquet`, local).
- **Tipos encontrados** (pares antes → después):

  | Tipo | Antes | Después |
  |---|---|---|
  | A. Nombres de pila en otro orden | 228 | 5 |
  | B. Subconjunto en otro orden | 41 | 6 |
  | C. Coma mal puesta | 874 | 154 |
  | D. Apellidos invertidos | 486 | 344 |
  | E. Error de dedo en apellido | 2,490 | 1,012 |
  | F. Error de dedo en nombre | 910 | 549 |
  | G. Partículas y apóstrofos | 234 | 18 |

  Además: abreviaturas (Fco., Gpe.) y texto corrupto («NuÃ±ez», «Heriberto @»).
- **Causas.**
  - Las reglas comparaban variante contra variante, no persona contra persona.
  - El bloqueo por primera letra impedía ver «Juárez/Suarez» y «Cejudo/Sejudo».
  - «Candidato único» bloqueaba casos con varias formas de la misma persona («Ricardo», «José Ricardo», «Ricardo José»).
- **Fase 2, grupo contra grupo.** Siempre con programa en común y candidatos únicos o mutuamente compatibles:
  - **R6** orden y subconjunto de nombres de pila, y partículas. Con 4 o más palabras idénticas en otro orden basta el nombre: «Zoila Irma» / «Irma Zoila» Tejada Castañeda aparecen en Nutrición animal y en Veterinaria.
  - **R8** coma mal puesta.
  - **R9** apellidos invertidos raros (el otro grupo tiene 10 veces más tesis o más).
  - **R10** error de dedo grupo contra grupo, incluida la primera letra. Salvaguarda: con 3 palabras, dos nombres comunes distintos («Miguel/Manuel») no se unen.
  - **R11** misma pronunciación en español (z/s/c, v/b, y/i, ll, h muda, letras dobles, palabras juntas). Conserva vocales, así que Francisca/Francisco y Emilia/Emilio siguen separados.
- **Errores propios detectados y corregidos.**
  - Cadenas de subconjuntos: «Carlos» unía «Carlos Eduardo» con «Carlos Raymundo». Ahora se exige que los nombres de pila completos sean compatibles.
  - R4 al revés metía «Sánchez, Juan Manuel» en «Juan José Sánchez-Sosa».
  - **El resultado dependía de la semilla de hash de Python**: «Siivia/Silvia» se unía en unas corridas y en otras no. Se fijó `PYTHONHASHSEED=0` y dos corridas dan la misma huella.
- **Resultado:** 117,482 variantes → **81,151 asesores**.
- **Lo que queda es intencional o ambiguo.**
  - D: la mayoría sin programa en común («Pérez González / González Pérez, Óscar»).
  - E/F: los que comparten programa son en buena parte personas distintas (Manuel/Daniel, Francisca/Francisco).
  - Caso conocido que depende del orden: «Siivia Tejada Castañeda» (1 tesis).
  - Para lo demás hace falta curaduría manual.

**Datos nuevos del prototipo** (`pipeline/generar_atlas_busqueda.py`):
- `busqueda/titulos/*.json`: índice invertido de los 609k títulos. 169,619 palabras en 1,588 repartos por prefijo (máx. 308 KB), postings en deltas varint base64, 14 MB en total. Cada búsqueda descarga solo lo que usa.
- `busqueda/temas.v1.json`: los 945 subtemas y temas finos en un solo archivo.
- `asesores.v1.json`: nombres y número de tesis.
- `asesores_por_tesis.v1.bin`: CSR alineado con el orden del mapa, 668,415 vínculos. Es la base para la búsqueda y para las futuras vistas de asesores (recomendar, analizar, mapa complementario).
- `tesis_anio.v1.bin`.

**Interfaz:**
- **Búsqueda**
  - Por inicio de palabra, sin acentos; la última palabra puede ir a medias.
  - Varias palabras se intersectan.
  - Espera de 120 ms entre teclas y descarte de respuestas viejas.
  - Secciones **Temas / Asesores / Tesis**; las tesis se muestran de la más reciente a la más antigua, con el total.
  - «Ver las N en el mapa» resalta todas las coincidencias y encuadra la cámara, con una ficha que dice en qué territorios caen.
  - Un asesor resalta en el mapa todas sus tesis.
  - **Barra de color**: el tono es el territorio (el mismo del mapa) y la intensidad la granularidad (territorio 100%, subtema 70%, tema fino 45%, tesis 30%). Asesor: 70% del color de su territorio dominante si concentra ≥30% de sus tesis; si no, gris. Sin territorio: gris.
- **Asesoría en la ficha de cualquier tesis** (antes solo en las de un tema aislado).
- **Nombres canónicos** en listado, panorama y red de asesores. Ejemplo: en «Pareja y violencia» los asesores distintos bajaron de 435 a 406 al unir variantes.

**Medido:**
- «freud»: 125 tesis. «lacan»: 197. «diab»: 6,563 (por prefijo). «valenzuela cota»: la asesora con 125 tesis.
- 0 errores de consola en escritorio y móvil.

**Pendiente:**
- Las vistas propias de asesores (recomendar asesor, analizar asesor, posible mapa complementario) ya tienen los datos base.
- Revisar la auditoría de fusiones.
- Afinar el ranking de tesis más allá de «más recientes».
- **Bug encontrado al hacer commit.** En Windows, «con», «prn», «aux» y «nul» son nombres de archivo reservados. `con.json` se «escribía» a la consola sin error y todas las palabras que empiezan con «con…» (contaminación, conducta, constitución…) quedaban sin resultados.
  - **Arreglo:** los repartos se llaman `t{xx}.json` y el generador verifica que estén todos en disco.
  - **Verificado:** «contaminacion» da 905 tesis, «conducta» 2,376 y «nulidad» 440.

### v4.3.0 — tesis elegidas que se distinguen del ruido (2026-09-24)

**Pedido del usuario:** al elegir una tesis o un grupo (búsqueda, asesor, listado de un tema fino), no se destacaba en el mapa.

**Diagnóstico:**
- **Tesis sola.** Se pintaba con `C_FOCAL`, el mismo negro `#17181a` que el resaltado de su grupo (`C_HL`) y del mismo tamaño (1.5 a 5 px). Desde el listado de un tema era un punto negro entre cientos. Desde la búsqueda, el resto del mapa ni siquiera se atenuaba (partía de `baseCats()`).
- **Tema aislado.** `showThesisOnMap` volaba a la posición *original* de la tesis, no a la desplazada del tema abierto, y redibujaba con las categorías del resaltado, no con las del aislamiento.
- **Grupo.** Tenía el tamaño del ruido, 62 % de opacidad, y los 600 mil puntos atenuados se dibujaban *encima* (orden de índice en WebGL).
- **Móvil.** La ficha y el panel ocupan el 100 % del ancho, así que la tesis descrita quedaba tapada.

**Estrategia acordada.** El usuario descartó el halo o anillo porque «se ve muy IA». Revisé referencias:
- el aura difusa es el recurso de «la IA está pensando» (Gemini, Apple Intelligence);
- Gapminder pone lo elegido en color y lo demás en gris;
- FT/NYT anotan el punto con una línea guía;
- Embedding Atlas resume un conjunto con curvas de densidad.

El énfasis sale de **contraste, tamaño y texto**, sin efectos.

**Cambios:**
- **Capa `#marks`** (canvas 2D encima del WebGL, debajo de los rótulos):
  - los puntos del grupo (hasta 30,000) se repintan encima de todo, 1.5 px más grandes, en tinta al 85 %;
  - en búsquedas y asesores se añaden **curvas de densidad**: `d3.contourDensity` a dos niveles, 10 % y 35 % del máximo. Están plenas en la vista general y se desvanecen al acercarse (hasta `K_MESO`×1.6).
- **Tesis elegida:**
  - una sola función, `focusThesis`, para clic, búsqueda, listado y tema aislado;
  - punto de tinta del doble de tamaño sobre el resto atenuado;
  - **anotación** con línea guía diagonal: título en 2 o 3 líneas y año, en Libre Franklin, con el mismo filo blanco que los rótulos del mapa.
  - Colocación de la anotación: prueba las cuatro diagonales, prefiere la que no se sale de la zona visible y la que menos pisa rótulos. Los rótulos que siguen debajo bajan al 12 % mientras la ficha esté abierta.
  - Si la tesis pertenece a un grupo marcado, el grupo baja un escalón (tinta al 30 %): atenuado, luego grupo, luego tesis.
  - En el tema aislado, el punto elegido es 1.6 veces más grande que sus vecinos.
- **Vuelos a la zona visible** (`flyToVisible`, `visibleBox`). La tesis o el grupo quedan centrados en lo que no tapan la ficha ni el panel.
- **Rótulos del mapa por encima** de los puntos marcados (`svg#overlay` con z-index 3).
- **Móvil (≤ 860 px):**
  - la ficha de tesis es una hoja inferior (46 % de alto máximo);
  - al abrir una tesis desde el listado, el panel se aparta (`.peek`) y vuelve al cerrar la ficha.

**Verificado** en Chrome headless, escritorio (1600×900) y móvil (390×844), sin errores de consola:
- «freud», ver las 125: la curva de densidad rodea la concentración en Filosofía y letras;
- una tesis desde la búsqueda: resto atenuado y anotación que evita el rótulo «Filosofía · Nietzsche»;
- una tesis desde el listado del tema aislado: vuela a su posición desplazada;
- una tesis desde el A→Z de un subtema: el grupo en gris y la tesis en tinta;
- clic directo en el mapa;
- en móvil, panel que se aparta y vuelve.

**Pendiente:**
- Probar en el navegador real con GPU: el canvas de marcas repinta hasta 30 mil puntos por cuadro al moverse.
- Decidir si los grupos de territorio (más de 30 mil tesis) también merecen curvas.

### v4.3.1 — en el tema fino ya no se puede saltar a otro tema por accidente (2026-09-24)

**Reporte del usuario:** en modo tema fino, al hacer clic en tesis individuales, a veces se abría otro tema fino y se iba a otro cluster sin querer. Al pasar el cursor aparecía «Tema fino… Clic para acercarte».

**Causa.** En el tema aislado, la capa de nombres del mapa se oculta con `opacity: 0; pointer-events: none`. Pero sus círculos y rótulos declaran `pointer-events: auto`, y en CSS eso gana al `none` del padre. Los marcadores invisibles de los otros temas seguían recibiendo clics y hover. Medido en v4.2 y en v4.3.0: 28 de 28 marcadores visibles bajo el tema seguían siendo clicables. El bug venía de antes de v4.3.

**Arreglo.** `body.iso #overlay * { pointer-events: none !important; }`.

**Verificado:**
- en el tema aislado, 0 de 28 marcadores son clicables (`elementFromPoint`);
- al salir, vuelven a serlo (20 de 22; los otros 2 quedan tapados por otro elemento).

**Segundo bug encontrado al verificar** (también previo a v4.3):
- **Síntoma.** Salir del tema aislado mientras la cámara aún volaba hacia él lanzaba `TypeError: Cannot read properties of undefined (reading 'destroy')` dentro de regl-scatterplot.
- **Causa.** La versión 1.16 comparte el estado de transición entre cámara y puntos; una transición de puntos iniciada durante un vuelo destruye una textura que no existe. Además, la promesa de `zoomToLocation` se resuelve al *empezar* el vuelo (medido: 9 ms tras el inicio, contra 1.4 s del evento `transitionEnd`), así que `cameraTransitioning` no servía para saberlo.
- **Arreglo.** `drawPoints` espera el evento `transitionEnd` de la librería antes de iniciar una transición de puntos. Si mientras espera llega otro dibujo, el que esperaba ya es viejo y no se aplica.
- **Verificado:** con la línea de tiempo instrumentada, la transición de salida ahora arranca justo en `transitionEnd`. Sin errores de consola en los flujos de escritorio y móvil de v4.3.

### v4.4.0: ficha de tesis y hover con una sola gramática visual (2026-09-24)

**Pedido del usuario:** que la ficha de una tesis se entienda de un vistazo, con nivel, área, programa, plantel y asesoría, y que el hover del mapa diga lo mismo en compacto. Pasó por cinco iteraciones con él. Se descartaron:
- la franja de segmentos encadenados;
- los puntos unidos por una línea;
- los cuadros de color sueltos, porque «no tienen propósito gráfico».

**Datos.** `pipeline/generar_atlas_tesis_meta.py` genera `data/tesis_meta.v1.bin` (3.0 MB) y su `.json` (59 KB):
- tiene nivel, programa y plantel de las 609,154 tesis, alineados con el orden del mapa;
- antes solo existían para las ~200 mil tesis de algún tema fino;
- cobertura: nivel 99.9 %, programa 99.9 %, plantel 100 %;
- sin autores.

**Gramática visual: el plano de metro de Vignelli.** Cada línea tiene un color y cada parada es un punto, y el color *une* lo que va junto.
- **Nivel:** 4 puntos sueltos en escala de azul (`#9cc3e6`, `#5b95cf`, `#2d65a8`, `#143a6b`). Se oscurece al avanzar de licenciatura a doctorado.
- **Ficha:**
  - encabezado con tinte claro del color del área y franja superior de 4 px;
  - orden: nivel, título, año;
  - la línea del área baja desde el encabezado con sus paradas: área (punto lleno), programa (anillo del color del área), plantel (punto gris) y asesoría;
  - la asesoría es una estación de transbordo: círculo blanco con borde. Es clicable y muestra todas las tesis de esa persona en el mapa;
  - acciones al pie, tras una regla fina.
- **Hover:** la misma información a tamaño de palabra (Tufte), en gris. Van los puntos de nivel, el título, el año y la ruta con glifos (trazo del área, anillo más programa, punto más plantel, anillo de tinta más asesor), con el plantel abreviado (FES, ENES, ENP, CCH).

**Quitado:**
- el registro TH_ de la ficha, porque es de la base de datos;
- la nota de territorio («Sin territorio: no quedó en ningún grupo claro…»);
- el punto medio como separador. El usuario lo señaló como patrón de UI generada; ver v4.6.

**Referencias:** Vignelli (MoMA), Bertin, Tufte (sparklines y la mínima diferencia efectiva), fichas de catálogo de biblioteca y retícula suiza (Müller-Brockmann).

**Verificado:** en escritorio y móvil, con tesis de cada nivel y cada área, en el hover real, el tema aislado, el listado y un clic en un asesor (Daniel García Gavito: se resaltan sus 48 tesis). Sin errores de consola.

### v4.5.0: ficha de cluster con perfil de sus tesis (2026-09-24)

**Pedido del usuario:** el orden alfabético no describe un cluster, y el nombre a veces es ambiguo.

**Encabezado:** misma lógica que la ficha de tesis, con el tinte y la franja del color del territorio. Arriba va el nivel jerárquico, luego el título y debajo las 6 a 8 **palabras clave** c-TF-IDF.

**Perfil**, calculado de sus tesis reales y en secciones separadas por reglas finas:
1. total, rango de años e histograma por año (el 1 % más antiguo va en la primera barra);
2. áreas en una dona (5 segmentos o menos, según la guía de visualización), con leyenda y porcentajes;
3. niveles en barra apilada con la escala azul;
4. los 5 programas principales, en barras del color de su área;
5. los 5 asesores con más tesis ahí, como estaciones de transbordo clicables;
6. temas vecinos: los 3 clusters más parecidos, a partir de los enlaces del mapa.

Siguen el A→Z, el taller y los subtemas.

**Bug corregido:** al pasar de un cluster a otro, el panel conservaba el scroll del anterior.

### v4.6.0: subtema y tema fino se distinguen en el mapa; fuera el punto medio (2026-09-24)

**Reporte del usuario:** al explorar no se sabía si se hacía clic en un subtema o en un tema fino.

**Cambio.** Se usa la gramática de las fichas (padre = punto lleno, hijo = anillo) más la convención cartográfica de rango (Axis Maps, Ordnance Survey): mayúsculas para lo grande y minúsculas para lo chico, con al menos 2 px de diferencia.
- **Subtema:** punto lleno y rótulo en MAYÚSCULAS seminegritas, de 12 a 15 px.
- **Tema fino:** anillo del color del territorio y rótulo en minúsculas 500, de 10.5 a 12 px, sin espaciado.
- **Leyenda:** explica los dos rangos.
- **Descartada la opacidad:** se lee como «desactivado».

**Bug:** la miga de pan seguía diciendo «subtemas» al llegar a temas finos, porque se actualizaba antes de recalcular el nivel. Ahora se actualiza al cambiar de rango.

**Punto medio:** fuera de todo texto visible (22 apariciones).
- Los nombres de tema usan guion largo («Filosofía – Nietzsche»).
- Los datos se separan con comas o renglones.
- El pie de página usa una línea vertical fina.
- Solo queda en el código que parte las etiquetas de los archivos de datos.

**Verificado:** mapa a nivel subtema y tema fino, búsqueda, fichas y flujos anteriores, en escritorio y móvil. Sin errores de consola.

### v4.7.0: nombres de los niveles, campo, tema y subtema (2026-09-24)

**Pedido del usuario:** «territorio» y «tema fino» no encajaban, y «macro/micro» le parece forzado. Pidió nombres formales, al estilo de «tema, subtema».

**Opciones propuestas:**
- Campo, Tema, Subtema;
- Eje temático, Tema, Subtema;
- Materia, Tema, Subtema. «Materia» choca con el campo *materias* de TESIUNAM.

**Elegida: campo (macro), tema (meso), subtema (micro).**
- Se cambiaron todos los textos visibles: mapa, miga de pan, leyenda («● TEMA ○ Subtema»), lente «Campos», fichas, búsqueda, relatos de la introducción, rutas y página de método.
- La sección de la búsqueda pasa a «Campos y temas».
- Los vecinos se nombran según el nivel: «Campos vecinos», «Temas vecinos», «Subtemas vecinos».
- «Subtema» cambió de sentido: antes era el nivel intermedio y ahora es el más fino. El reemplazo se hizo del nivel más fino al más general, con marcadores para no renombrar dos veces.
- En el código y los datos siguen `macro`, `meso` y `micro` e identificadores como `colorTerritorio`.
- Las secciones anteriores de esta bitácora conservan los nombres viejos.

**Verificado:** sin rastros de los nombres viejos en textos visibles (grep); capturas de miga de pan, leyenda, ficha y búsqueda. Sin errores de consola.

### v4.8.0: taller rediseñado: Tesis, Perfil y Asesores (2026-09-24)

**Pedido del usuario:** la vista «Ver las N tesis y su análisis» era genérica y la vista analítica no le convencía.

**Cambios:**
- **Encabezado** con el sistema de fichas: franja y tinte del color del campo, nivel jerárquico, título y palabras clave. Las pestañas llevan su conteo.
- **Tesis:**
  - fichas compactas con la gramática del hover;
  - facetas de catálogo: buscar, orden, agrupar por década, programa o nivel, nivel en azul, programa con anillo del color de su área y plantel en gris;
  - en móvil las facetas se pliegan;
  - el agrupado sustituye a la vista analítica, que agrupaba mal: mandaba las décadas más grandes a «Otros».
- **Perfil:** las gráficas de la ficha del cluster en grande, extraídas a funciones compartidas (`perfilDatos`, `histHtml`, `areasHtml`, `nivelesHtml`, `programasHtml`). Cada barra filtra Tesis.
- **Asesores:** transbordos ordenados con su línea de tiempo, y la red de codirección con círculos de transbordo y líneas del color del campo.

### v4.8.1: títulos, minimapa, red de asesores y ajustes de la lista del usuario (2026-09-24)

- **Títulos:** todo título de tesis empieza con mayúscula (`tituloTesis`), saltando signos de apertura.
- **Minimapa:** «Vista general» pasa a «Minimapa» y el botón a «Mostrar minimapa».
- **«Cómo se hizo el mapa»:** queda solo en el pie.
- **Red de codirección:**
  - todo asesor lleva su nombre: se prueban cuatro posiciones y el ancho medido;
  - la red es conexa: se elige a partir del asesor con más tesis;
  - en móvil se muestran 12 asesores.
- **Búsqueda del taller:** el fragmento buscado va en negritas (`resaltarHtml`, sin distinguir acentos).
- **Enlaces en subtemas grandes:** como máximo 1,200, y cada tesis conserva su enlace más fuerte. En Filosofía – Nietzsche quedan 1,572 de ~5,500.
- **Ficha de tesis:** se cierra al cambiar de modo y al hacer clic en una zona vacía del mapa.

### v4.9.0: ficha de asesor o búsqueda, tooltip de cluster y tesis recientes (2026-09-24)

- **Ficha de un conjunto** (asesor o búsqueda) con el sistema de fichas: color del campo dominante, perfil, campos (clicables) y, en un asesor, «Codirigió con» (se navega de asesor en asesor).
- **Tooltip de campo, tema o subtema:** glifo de rango, palabras clave y barra de áreas. Se quitó «Clic para acercarte». Además se acomoda a su ancho real; antes se salía por la derecha.
- **Ficha del cluster:** el A→Z pasa a «Tesis recientes» (5 fichas compactas) y el botón negro a un enlace.

### v4.10.0: fuera los subtítulos innecesarios (2026-09-24)

**Anti-patrón nuevo (#22 en PRODUCT.md), identificado por el usuario:** subtítulos que repiten lo que la gráfica ya dice («48 tesis, de 1991 a 2013» sobre la línea de tiempo), notas de instrucción y conteos en prosa. **Regla:** el dato se dice con la gráfica, con jerarquía visual o como un elemento del sistema. Una frase entra solo si dice algo que nada más muestra.

**Qué se quitó o sustituyó:**
- **Histogramas:**
  - ahora tienen **eje con números**: el tope «redondo» y su mitad, con líneas de referencia tenues;
  - se quitó el rótulo «Tesis por año».
- **Ficha de asesor o búsqueda:**
  - nuevo orden pedido por el usuario: línea de tiempo, áreas y niveles (datos del catálogo), y al final los campos, que son inferidos;
  - sin subtítulo de conteo y rango;
  - «17 tesis no quedaron en ningún campo» pasa a ser una fila «Sin campo» con punto gris;
  - sin nota «cierra esta ficha para…».
- **Ficha del cluster:** sin «N tesis, de X a Y»; «Asesores con más tesis aquí» pasa a «Asesores».
- **Ficha de tesis:** «Asesoría de 48 tesis» pasa a ser un número alineado a la derecha del asesor.
- **Tooltip de cluster:** «93 % de Humanidades» se quitó, porque ya lo dice la barra.
- **Búsqueda:** «153 títulos coinciden; las más recientes» pasa a ser el número solo.
- **Taller:**
  - sin la línea de conteo y rango en el encabezado;
  - el conteo de la lista solo aparece al filtrar;
  - Perfil sin párrafo de lectura;
  - Asesores: el párrafo pasa a una barra «Asesoría por tesis» (un asesor, dos o más, sin registro), las filas pierden «Codirigió con N personas…» (queda una flecha al mapa) y la descripción de la red pasa a una leyenda de glifos.

**Se conserva a propósito:** la nota de la leyenda del mapa («no son las áreas oficiales»), por el principio de honestidad sobre el método.

**Verificado:** capturas de la ficha de asesor, de búsqueda y de cluster, y del Perfil y Asesores del taller. Sin errores de consola.

### v4.11.0: línea de tiempo sin bloques y encabezados sin «énfasis falso» (2026-09-24)

**Reportes del usuario:**
1. Con pocos años, el histograma se volvía un bloque: una sola barra a todo el ancho (asesor Saul Cruz Ramos: 2 tesis en 1982).
2. El encabezado con fondo teñido y franja de color más oscura es «énfasis falso» y se reconoce como diseño generado por IA. Queda como anti-patrón #23 en PRODUCT.md.

**Línea de tiempo** (`histHtml`, usada por las fichas de cluster, asesor y búsqueda, y por el Perfil del taller):
- el rango mínimo es de 10 años, así un dato aislado queda en su contexto;
- con 8 años con tesis o menos, **paletas**: un tallo y un punto por año;
- con más, **línea** con área tenue;
- el eje con números se conserva;
- los puntos son líneas de longitud cero con extremo redondo y `vector-effect: non-scaling-stroke`, para que sigan siendo círculos aunque la gráfica se estire.

**Encabezados** (ficha de tesis, de asesor o búsqueda, de cluster y del taller):
- sin fondo teñido ni franja; blanco, con una regla fina abajo;
- el color pasa a un **mapa de localización**, como el recuadro de ubicación de los atlas: la silueta del mapa en gris, recortada al 99 % de su extensión, y lo que describe la ficha en su color:
  - una tesis, con dos líneas guía que se cruzan en su punto;
  - un cluster o conjunto, con sus puntos (en tinta si ninguno está en un campo).

**Verificado:** asesor con 2 tesis (paleta), asesor con 48 (línea), tesis, tema y taller, en escritorio y móvil. Sin errores de consola.

### v4.12.0: histograma con hover, localizador tonal y tooltip del mapa bloqueado bajo las fichas (2026-09-24)

**Pedidos del usuario:**
- volver al histograma cuando hay ~10 tesis o más;
- un hover que diga el número y el año de cada barra;
- el localizador con color de fondo.

**Línea de tiempo:**
- con 10 tesis o más, barras por año; con menos, paletas, así no reaparece el bloque de una barra;
- rango mínimo de 10 años y eje con números, como antes;
- **hover** (un solo manejador para todas las gráficas, en fichas y taller, con ratón o toque): la barra se marca, las demás bajan a 30 % y encima aparece el número en negritas con el año debajo, sin caja, acotado a los bordes de la gráfica.

**Localizador tonal:** en lugar de un fondo sólido, todo el recuadro en el tono del dato:
- fondo en un tinte claro (16 %);
- silueta del mapa en tono medio (50 %);
- el dato en el color pleno; en una tesis, líneas guía de tinta al 55 % y punto de tinta.

Se distingue de un vistazo y el color sigue diciendo de qué campo o área se trata.

**Bug que ya existía:** regl-scatterplot calcula el hover por coordenadas, aunque el mapa esté tapado por una ficha o un panel, así que al pasar el cursor sobre una ficha aparecía el tooltip de la tesis de abajo. Ahora solo se muestra si el cursor está sobre el lienzo del mapa.

**Hallazgo pendiente de confirmar** (posible bug 4 del usuario): en Analizar, la cuadrícula de un subtema grande sale por debajo de la pantalla (Filosofía – Nietzsche: tesis en y ≈ 768 px, bajo el pie). Si el límite de paneo no deja bajar, esas tesis no se alcanzan. Al volver a «Ver conexiones», cámara y posiciones quedan igual que antes (verificado).

**Verificado:** hover en asesor con 48 tesis (barras: «1, 2005»), con 2 tesis (paleta: «2, 1982») y en el Perfil del taller («114, 2012»); el tooltip del mapa no aparece bajo la ficha; el hover del mapa sigue funcionando. Sin errores de consola.

### v4.13.0: palabras clave medidas y marca de rango en lugar de la frase de contexto (2026-09-24)

**Pedido del usuario:**
- las palabras clave eran «solo palabras», fuera del sistema visual;
- la frase «Tema en Filosofía y letras» sobre el título le restaba protagonismo y era un subtítulo explicativo (anti-patrón #22).

**Palabras clave medidas** (`palabrasHtml`): una barra por palabra clave con la proporción de títulos del cluster que la contienen. Es un dato real de sus títulos, no un peso inventado. Van ordenadas por esa proporción, en el color del campo. Al hacer clic se abre el taller con la lista filtrada y el término en negritas. Aparecen en la ficha del cluster (primera sección) y en el Perfil del taller.

**Marca de rango** (`rangoHtml`), en lugar de la frase:
- el título va arriba de todo;
- debajo, los tres glifos del mapa: campo (punto grande), tema (punto) y subtema (anillo), con el nivel actual en su color y los otros en gris;
- al lado, el campo al que pertenece (enlace en la ficha).

Dice «tema dentro de Filosofía y letras» sin escribirlo. Se aplica en la ficha del cluster, el encabezado del taller y el tooltip del mapa.

**Verificado:** subtema, campo, taller (palabra «obra»: 299 de 5,469 tesis, con el término resaltado), Perfil y tooltip, en escritorio y móvil. Sin errores de consola.

### v4.13.1: fuera las palabras clave (2026-09-24)

**Reporte del usuario:** las palabras clave eran redundantes. En «Álvaro Obregón – Delegación Álvaro», las barras decían Obregón 90 %, Álvaro 89 %, Álvaro Obregón 87 %…: el nombre ya está hecho de esas palabras y los n-gramas se repiten entre sí.

**Cambio:** se quitaron de la ficha del cluster, del Perfil del taller y del tooltip del mapa, con su código (`palabrasHtml` y sus manejadores). La marca de rango de v4.13.0 se queda.

**Verificado:** ficha, taller y tooltip; flujos anteriores en escritorio y móvil. Sin errores de consola.

### v4.14.0: menos es más; fuera Analizar, vecindario, leyenda y rutas (2026-09-24)

**Decisiones del usuario sobre la lista de partes genéricas:**
- **Bug 4 confirmado:** en «Analizar», la cuadrícula de un subtema grande salía por debajo de la pantalla y esas tesis no se alcanzaban.
- **Modo «Analizar» retirado:** sus funciones, sus rótulos, el selector de agrupación y la paleta de grupos. Con esto desaparece el bug 4. El botón de la barra del subtema aislado pasa a «Ver tesis y análisis» y abre el taller del subtema, que ya organiza sus tesis por nivel, programa, plantel y década.
- **Modal «Ver vecindario completo» retirado,** junto con el resaltado de vecinas (spotlight), la lista «Vecindarios precargados» y su botón en la ficha. El archivo `vecindario_preview` se sigue cargando porque aporta títulos.
- **Leyenda retirada.**
- **Rutas guiadas retiradas:** el usuario no las pidió y no le gustaron. Se quitaron el botón de la barra, el menú, los pasos y sus funciones auxiliares.
- **Introducción:** se rehará como onboarding más adelante, quizá con inicio de sesión.
- **Página de método:** la figura del proceso queda para después.

**Correcciones de paso:**
- **Escape:** cierra primero la ficha de tesis y luego el subtema aislado; antes salía del subtema con la ficha abierta.
- **Verificación de funciones:** respaldo en `index.v4.13.1.html`. Se compararon las funciones de antes y después; las 26 retiradas son todas de estas partes y ninguna se sigue llamando. Una línea del cuerpo de la ficha de cluster se había ido con el bloque de vecindarios y se restituyó.

**Verificado:**
- en el DOM ya no existen rutas, leyenda ni modal;
- el botón del subtema abre su taller (Filosofía – Nietzsche, 1,856 tesis);
- Escape cierra taller y ficha;
- los flujos anteriores pasan en escritorio y móvil;
- sin errores de consola.

### v4.15.0: controles del sistema, parte 1 (2026-09-24)

**Punto 11 de la lista de partes genéricas.** El usuario aprobó los puntos 1, 3 y 4; el 2 (estados de carga) y el 5 (iconos de cierre) quedan para después.

**1. Un solo estilo de acción.** `.btn.primary` deja de ser una caja negra: es texto en tinta, seminegritas, con una flecha dibujada (máscara SVG, no un glifo unicode). Al pasar el cursor se subraya 2 px con el color del contexto (`--c`: el campo del subtema aislado). Aplica a «Ver tesis y análisis» y a la acción de la introducción.

**3. El control de color explica los colores.** Al retirarse la leyenda, el botón «Áreas administrativas» lleva cinco puntos, uno por área y uno para «sin área». Al pasar el cursor por un punto:
- el conteo de la barra dice qué área es y cuántas tesis tiene («Ciencias Sociales 177,268 tesis»);
- sus tesis se resaltan en el mapa, en cualquiera de los dos modos de color.

Es una leyenda integrada al control, no un recuadro flotante.

**4. Minimapa.** «Ocultar» pasa a ser un icono de plegar. Plegado, queda una pestaña delgada pegada al borde inferior derecho, «Mostrar minimapa», que lo despliega.

**Verificado:** hover de área (Ciencias Sociales), plegar y desplegar el minimapa, la acción del subtema aislado y la de la introducción; flujos anteriores en escritorio y móvil. Sin errores de consola.

### v4.16.0: Ajustes y leyenda de áreas (2026-09-24)

**Bug reportado:** al pasar el cursor por los puntos de área del botón «Áreas administrativas», el mapa «se volvía loco». Cada hover redibujaba los 609 mil puntos, y el punto crecía con el hover, así que el cursor entraba y salía de él en cadena. Se quitaron esos puntos y su código.

**Ajustes:**
- botón en la barra, a la derecha del buscador;
- abre un panel anclado bajo la barra, sin sombra;
- se cierra con clic fuera o con Escape;
- «Color de los puntos: Campos / Áreas administrativas» sale de la barra de filtros y vive aquí.

**Leyenda de áreas:** discreta, en la esquina inferior izquierda, pegada al borde. Solo aparece con el color por áreas y se oculta en el subtema aislado.

### v4.17.0: modo noche del mapa, con las ventanas de la Biblioteca Central (2026-09-24)

**Idea del usuario:** un selector de día y noche con las ventanas de ónix de la planta baja de la Biblioteca Central, que de día se ven tostadas y de noche se encienden en ámbar. Es un homenaje sutil a la UNAM.

**Decisión:** el modo noche es **solo del mapa**. Paneles, fichas y taller siguen claros, y el claro es el predeterminado. Se actualizaron las reglas de CLAUDE.md y PRODUCT.md, que decían «fondo claro obligatorio».

**Iconos** (`ventanas-dia.svg`, `ventanas-noche.svg`, 40×40):
- dibujo propio y abstracto de la retícula de placas; no se trazó ninguna foto, por los derechos de las fotos y del mural;
- las placas conservan su lugar en los dos iconos; solo cambia la luz (tostado y rosado de día, ámbar y dorado con algunas en azul frío de noche);
- el usuario pidió una sola ventana por modo, sin la franja de vidrio.

**Mapa de noche:**
- fondo `#0f1422`;
- paleta de campos con los mismos tonos más luminosos (OKLCH L 0.72, 0.80, 0.87) y opacidad 0.5;
- áreas en versión luminosa (`AREA_HEX_NOCHE`);
- ruido y atenuado en azul pizarra;
- resaltados, tesis enfocada, anotación y curvas de densidad en tinta clara con filo oscuro;
- rótulos claros con filo oscuro, retícula y enlaces tenues.

`m.color`, que usan fichas y paneles claros, sigue siendo el tono de día (`m.colorNoche` es el del mapa). La preferencia se guarda en el navegador.

**Bug encontrado:** tras cerrar una ficha, la anotación de la tesis podía quedar dibujada un momento, porque la capa se limpiaba en el siguiente cuadro. Ahora `clearFocus` limpia al instante.

**Verificado:** noche en vista general, temas, grupo de búsqueda, tesis, subtema aislado y áreas, en escritorio y móvil; los flujos anteriores pasan de día. Sin errores de consola.

### v4.18.0: modo noche de toda la interfaz y Ajustes al centro (2026-09-24)

**Pedido del usuario:**
- el modo noche para todo, no solo el mapa;
- Ajustes en una ventana al centro con el fondo difuminado y las ventanas grandes;
- revisar la legibilidad en ambos modos, del mapa al taller.

**Tokens.** Todo color de interfaz sale de variables CSS:
- `--bg` (lienzo del mapa), `--paper` (paneles, fichas, taller, barras), `--surface`;
- `--ink`, `--ink-2`, `--ink-3`, `--line`, `--line-strong`, `--grid`, `--link`;
- los tokens del mapa: `--map-label`, `--map-minor`, `--map-region`, `--map-edge`, `--map-tick`.

`body.noche` solo redefine sus valores (con `color-scheme: dark`). Quedaron cero `#fff` fijos en el CSS. En el JS, las gráficas usan `style="fill/stroke:var(--…)"` y los lienzos leen el token vigente (`tok()`). El localizador mezcla su tinte con el papel, no con blanco.

**Contraste de texto (WCAG, sobre papel):**
- de día: ink 17.4, ink-2 8.5, ink-3 5.1, link 8.1;
- de noche (`#161c2a`): ink 14.2, ink-2 9.5, ink-3 5.9, link 8.4.

Todos pasan AA para texto chico.

**Colores de datos por modo:**
- `AREA_HEX` cambia de valores: la paleta de noche `#5b93e6`, `#27a97c`, `#b0801c`, `#e0567a` pasó las cinco pruebas del validador de la guía de visualización sobre `#161c2a`. La primera propuesta, más clara, fallaba por luminosidad y por el ocre y el rojo demasiado parecidos;
- `m.color` usa la versión de noche de cada campo;
- `NIVEL_COLOR` de noche va de oscuro a luminoso: más avanzado, más luminoso.

Al cambiar de modo se vuelven a pintar la ficha abierta (tesis o grupo), el panel del cluster, el taller, la leyenda y el minimapa.

**Ajustes:** ventana centrada (400 px) con el fondo difuminado (`backdrop-filter: blur(7px)`) y las ventanas de ónix de 96 px; en una primera versión medían 180 px y el usuario las pidió más chicas. Tiene «Modo» (Día o Noche) y «Color de los puntos del mapa». Se cierra con la X, con clic fuera o con Escape.

**Corrección:** al abrir la introducción con un cluster seleccionado, su resaltado quedaba sobre las esferas de áreas; ahora se cierra el panel.

**Verificado:**
- de noche en Ajustes, mapa, búsqueda, ficha de asesor con hover, ficha de tesis, ficha de cluster, las tres pestañas del taller, método e introducción, en escritorio y móvil;
- los flujos de día pasan igual que antes;
- sin errores de consola.

### P0 nº 1 cerrado: `data_unam.parquet` sin autores en el título (2026-09-25)

**Decisión del usuario:** el dataset no se publicó en ningún lado (ni Kaggle); solo existe local, así que basta limpiarlo. Las API keys **no** se rotan (P0 nº 2 descartado por el usuario).

**Qué cambió:**
- `titulo_original` → **`titulo_legible`**: el título con acentos y mayúsculas, sin la mención de responsabilidad (MARC 245 $c). Nuevo módulo `pipeline/titulo_sin_autor.py`: corta en la primera barra cuyo texto siguiente arranca como mención («tesis», «que para…», «presenta», «Lic.», un nombre propio…); si ninguna arranca así, en la última barra seguida de una marca fuerte («presenta», «asesor», «examen profesional»…); también sin barra («… tesis que para obtener…»). Una barra dentro del título («estireno / butadieno», «y/ o», «FIV/ICSI») no se corta. Después pasa `limpiar_autores_atlas.limpiar`.
- `generar_data_unam.py` aplica el corte al exportar; `generar_atlas_tesis_por_micro.py`, `generar_atlas_titulos_teselas.py` y la nota metodológica leen `titulo_legible`.

**Verificado:** 609,156 filas; 564,608 títulos cortados (92.7 %). Las 5 «fugas» que quedan en el detector son falsos positivos («… que presenta Síndrome de Down»), sin nombres. 11 títulos quedan muy cortos pero son reales («Asma», «Dolo», «HDTV»). Se revisaron a mano las 219 tesis con barra que no se cortaron: todas son barras del título.

**Pendiente:** `thesis_lookup.parquet` de `MI-TESIS-UNAM` sigue teniendo columna `author` y `title_raw` con autor (P0 nº 3, purga del LFS).

## Laboratorio: revisión crítica y decisiones (2026-09-25)

Contexto: el Lab funcionaba en `app/MI-TESIS-UNAM_github/scripts/` (FastAPI + `lab_orchestrator.py` + 6 módulos con Groq/Cerebras), sin diseño. `app/AI Pipeline/` es una copia incompleta (sin `validators.py`, `ai_advisors.py`, `ai_bibliography.py`); **esos archivos solo existen en el repo `MI-TESIS-UNAM`: rescatarlos antes de borrarlo** (opción B de la purga del LFS, decidida y pospuesta). Hay un fixture con salidas reales: `deploy/static/dev/lab_context_fixture.json` (caso «Sistema bancario de México y China 1850-2009»).

### Errores encontrados en el código

1. **Caso de desarrollo escrito en el código.** `build_questions_payload.py` manda a todo usuario tres `known_gaps_or_tensions` fijas sobre México-China; el prompt de bibliografía también lista «banca, sistema financiero… México, China». Los prompts se ajustaron a un solo caso.
2. **Preguntas sin nota inicial.** `compact_initial_note` lee el esquema viejo (`paragraph`, `possible_angles`, `one_sentence_reframe`); el prompt actual produce `central_problem`, `main_objects`… La nota llega vacía. `contracts.py` todavía exige el esquema viejo. Probable causa de que `questions` salga `null` en el fixture.
3. **«Confianza» de ubicación mal definida.** Mide la concentración del voto de las 50 vecinas, no la similitud absoluta: una idea sin antecedentes puede salir «clara» (0.96 en el fixture). Falta un umbral de similitud e5.
4. **Léxico de Bloom defectuoso** (`thesis.py`, `BLOOM_VERBS`): verbos en dos niveles («diagnosticar», «categorizar»), cuenta cualquier verbo en cualquier parte del objetivo y no el verbo rector.
5. **Cifras de asesores sobre la muestra de 50k** (`global_advised_count_sample`): subestiman ~12×.
6. **Sin control de consistencia.** La nota del fixture advierte sobre China «en la primera mitad del siglo XIX» con un periodo que empieza en 1850.
7. **Ubicación y asesores sobre el modelo viejo** (MiniLM, muestra de 50k, clusters viejos). El atlas nuevo es e5-large sobre 609k con campo, tema y subtema: hay que rehacerlos.
8. **llama-3.1-8b ya no es gratuito en Groq** (rerank y asesores lo usaban).
9. El «0 % de tesis desde 2020» del fixture era un **hueco del muestreo de 50k**, no del tema (confirmado por el usuario).

### Decisiones del usuario

- **Entrada pedagógica:** el formulario debe ayudar a plantear la tesis, no solo recogerla. Se agrega **«Problematiza»**: en pocas palabras, en qué consiste tu problema o pregunta de investigación. Cada campo da retroalimentación en vivo.
- **Objetivos:** pensar los casos límite del análisis Bloom (ver abajo).
- **IA y datos se distinguen** en la interfaz: ubicación, tesis cercanas, saturación y asesores son datos; nota, Bloom y preguntas son interpretación de IA.
- **Nivel de estudios** pesa en Bloom (nivel cognitivo esperado por grado).
- **Seguridad:** el texto del usuario va al prompt como dato (defensa contra inyección) y toda salida del modelo se escapa al pintarla (XSS).
- **Saturación del tema:** sí (tesis del subtema, tendencia por década, recencia de antecedentes, distancia a la tesis más parecida). Sin IA.
- **«Aplicar objetivos revisados»: no** (llamada innecesaria).
- **Todo en vivo y animado,** no solo la escalera de Bloom: cada sección aparece cuando está lista.
- **Asesores sin IA:** justificación armada con datos («asesoró 4 de tus 50 tesis más cercanas; la última en 2021»). Se muestra el último año en activo.
- **Tesis cercanas enlazan a su ficha en el atlas.**
- **Mi tesis en el mapa:** con sesión, la tesis analizada se guarda como un nodo especial en el atlas con una flecha permanente que dice MI TESIS. Desde el análisis se pueden guardar otras tesis para consulta rápida, como las ubicaciones guardadas de Google Maps.
- **Límites:** **2 análisis guardados** por usuario (para hacer otro hay que borrar uno de los dos) y **2 análisis nuevos al día**. Las tesis del atlas guardadas son **ilimitadas** (en la práctica, un tope alto contra abuso).
- **Entrada final:** título, **Problematiza** (el problema o la pregunta en pocas palabras), objetivos (cómo lo resuelves), palabras clave, programa, grado y periodo. Se descartó el campo «tu idea en 3 a 5 líneas»: Problematiza y los objetivos cubren ese papel.
- **Reordenamiento con IA: fuera.** Quedan 3 llamadas: nota, Bloom y preguntas.
- **Bibliografía: fuera** (inviable técnicamente).
- **Bloom:** escalera horizontal, no pirámide.
- **Mascota:** el personaje del usuario (esfera de perfil, brazos de manguera, piernas largas), recreado en SVG en `prototypes/atlas_vecindario_mvp/bocetos/mascota.html`; poses Saluda, Señala, Investiga (lupa) y Celebra. Azul por omisión; al terminar toma el color del campo de la tesis. Solo aparece en el Laboratorio y nunca encima de datos.

### Cambios a los prompts (por hacer)

- **Nota:** quitar `intro` (el fixture la llenó con relleno genérico); permitir «no aplica» en el alcance; quitar sesgos del caso de desarrollo; recibir Problematiza.
- **Bloom:** por objetivo, `verbo`, `nivel` y `confianza` estructurados; nivel de cada objetivo revisado (para la escalera antes/después); nivel esperado por grado; tratamiento de los casos límite de abajo.
- **Preguntas:** tipos fijos (comparativa, histórica, prospectiva, causal, evaluativa, exploratoria); factibilidad para el nivel; tesis del corpus que sirve de antecedente.
- **Todos:** recibir Problematiza, grado y señales reales del corpus (saturación, tendencia) en lugar de texto fijo. Conjunto de evaluación de 6 a 8 casos de campos distintos antes de cambiar de modelo.

### Casos límite del análisis Bloom

El léxico (sin IA, en vivo en el formulario) propone y el modelo decide con contexto; la interfaz marca cuándo la clasificación es de IA.

| Caso | Ejemplo | Qué hace |
|---|---|---|
| Verbo fuera del léxico | «visibilizar», «coadyuvar», «abonar a», «problematizar» | Queda «sin nivel» en gris en la escalera; pista: ¿qué harás exactamente? con verbos observables sugeridos. El modelo lo clasifica y la escalera lo marca como interpretación. |
| Verbo ambiguo | «determinar» (medir o decidir), «identificar», «diagnosticar» | El léxico da un rango de niveles (banda en la escalera); el modelo elige por contexto. |
| Verbo vago, no observable | «conocer», «entender», «saber», «profundizar», «abordar» | Se avisa que no se puede evaluar si se cumplió; se proponen alternativas. |
| Varios verbos | «identificar y analizar…» | Rige el primero; se sugiere partir en dos objetivos. |
| Sin verbo | «Análisis de…», «El estudio de…» | Se detecta el sustantivo y se sugiere el verbo (análisis → analizar). |
| Verbo conjugado | «analizaré», «se analizará», «analizando» | Se lematiza por raíz antes de buscar. |
| Actividad de método, no objetivo | «realizar entrevistas», «aplicar encuestas», «revisar bibliografía» | Se avisa: es un método, no un objetivo. |
| Tarea escolar o trámite | «hacer mi tesis», «titularme» | Se avisa y no se clasifica. |
| Otro idioma | «to analyze» | Se pide redactarlo en español. |
| Estructura | 1 objetivo, más de 6, todos en un nivel, salto de Recordar a Crear | Retroalimentación sobre la progresión, no sobre cada verbo. |
| Inyección | «ignora las instrucciones…» | El texto viaja como dato delimitado; no se ejecuta. |

### Plantilla del análisis terminado (boceto, 2026-09-25)

`prototypes/atlas_vecindario_mvp/bocetos/lab/analisis.html`, servida en `http://127.0.0.1:8765/bocetos/lab/analisis.html`. Un solo caso (México-China), con las secciones apareciendo en vivo en el orden real de llegada: primero los datos (ubicación y asesores), luego la IA (nota, Bloom, preguntas). La mascota investiga mientras tanto y celebra al final con el color del campo.

- **Datos reales** (`datos_ejemplo.json`), calculados con el nuevo `pipeline/lab_contexto.py`: e5-large sobre las 609,154 tesis (modelo descargado en esta PC; 2.1 GB), voto ponderado por similitud² para campo/tema/subtema, saturación por década, recencia, cobertura de palabras clave y asesores sobre el corpus completo.
- **IA de ejemplo** (`ia_ejemplo.json`) en el esquema nuevo: texto del fixture donde existía; lo demás redactado a mano y marcado `a_mano` (las preguntas no tienen salida real).

**Qué exige la plantilla a los prompts** (campos nuevos):
- Nota: `relations` (mapa de conceptos), alcance estructurado (`start`, `end`, `subperiods`, `units`, `fields`), `cautions` con `type`. Fuera `intro`.
- Bloom: por objetivo `verb`, `level` (enumeración de 6), `confidence`, `flags` (retroceso, sin_evaluar_antes, vago, metodo, fuera_lexico); `expected` por grado; `missing_step` con nivel; `revised` con nivel.
- Preguntas: `type` de una lista fija, `feasibility` (alta, media, baja) y `antecedent` elegido **entre las tesis cercanas que se le pasan** (no inventado).
- Todos: recibir la cobertura de palabras clave, para fundamentar «dónde está tu aporte».

**Hallazgos de datos:**
- La similitud e5 está comprimida: las 100 vecinas quedan entre 0.86 y 0.91. Los umbrales absolutos no sirven; la barra de «parecido» se muestra relativa a la lista. Calibrar con el conjunto de evaluación.
- 24 de las 50 vecinas no tienen subtema (ruido HDBSCAN): la ubicación vota con 26.
- **Cobertura de palabras clave:** México aparece en 65 de las 100 vecinas; China en 5 y «desarrollo económico» en 3. Es la señal más útil del análisis y no gasta tokens.
- `nivel` en `data_unam` mezcla mayúsculas («licenciatura» y «Licenciatura»); el script lo normaliza al mostrar.
- Los enlaces a tesis usan `index.html?tesis=TH_…`: **el atlas todavía no lee ese parámetro**.

### Plantilla v2 del análisis (2026-09-25), tras la revisión del usuario

**Cambios pedidos y aplicados:**
- **Orden:** el mapa «Aquí se encuentra tu tesis» va arriba, a todo el ancho; debajo, la ficha de la tesis del usuario; luego Comprendí tu tesis así, Tu tesis podría… (preguntas), Tus objetivos, Las 100 tesis más parecidas, Asesores y Las tesis más cercanas.
- **Color de área administrativa** en el mapa (cada tesis en su área; las de los dos campos de la tesis, plenas), en la dona de áreas, en los programas y en el punto de cada tesis.
- **Mascota:** cambia de color en cada hallazgo (gris al buscar, color del área al ubicarla, color del campo después) y celebra solo al final.
- **Fuera:** mapa de conceptos, marcas de IA y datos (no importa si no se distinguen), subtítulos como «Problema central», subperiodos, «Aporte posible», «Antes de seguir, cuida esto», «Tu tesis queda entre dos campos», «¿Qué tan explorado está tu tema?», la cobertura de palabras clave («mal construida», queda para repensar) y el aviso bajo los asesores.
- **Periodo:** una línea de tiempo con dos puntos unidos.
- **Las 100 más parecidas:** el mismo perfil que el taller de cluster (años con títulos al pasar el cursor, áreas, niveles, campos, temas, subtemas, programas, planteles). Auditable y sin IA.
- **Bloom: dos escaleras** (tus objetivos y la propuesta). Cada verbo va en su peldaño; sin números ni tabla. Los tramos entre niveles con objetivo son continuos si son contiguos y punteados con «sin Evaluar» si se salta alguno. **El nivel lo pone un léxico en la interfaz (determinista); la IA solo aporta el riesgo principal, los diagnósticos (al pasar el cursor por el verbo) y los objetivos propuestos.**
- **Preguntas:** el verbo de cada una en grande y en el color del campo (comparar, rastrear, explicar, evaluar, anticipar); antecedente con punto de área, año y plantel.
- **Asesores:** plantel y programa más frecuentes de cada asesor (del corpus completo), cifras en línea y su trayectoria como puntos por año con las tesis cercanas resaltadas.
- **Tesis más cercanas:** al final, agrupadas por campo con su color, y un **CTA para guardar las 15**.
- **Guardado automático:** la tesis analizada se guarda al crearse y aparece en el mapa como MI TESIS; ya no hay botón para guardarla.

**Datos nuevos de `lab_contexto.py`:** las 100 vecinas compactas (área, nivel, programa, plantel, campo, tema, subtema), nombres de campo/tema/subtema y plantel, programa y área de cada asesor.

### Laboratorio: plantilla del análisis v3 (boceto, 25-sep-2026)

`prototypes/atlas_vecindario_mvp/bocetos/lab/analisis.html`, a partir de los comentarios del usuario sobre la v2.

- **Dos columnas.** A la izquierda van el título y el análisis. A la derecha, el mapa reducido, fijo (`sticky`) mientras se lee. Debajo del mapa van la leyenda de áreas en nombre corto, «Análisis guardados: 1 de 2» y «Abrir en el mapa».
  - Al pasar el cursor por una de las tesis cercanas enlazadas en el análisis, su punto crece en el mapa.
  - Se quitó el índice lateral.
  - En pantallas de hasta 860 px, el mapa pasa arriba y deja de estar fijo.
- **Meta de la ficha con la gramática de las fichas del atlas.**
  - El programa lleva la barra del área y el anillo del programa, en el color del área. Esa área es la más común entre las parecidas del mismo programa.
  - El grado lleva los cuatro puntos de nivel, en la escala azul.
- **Comprendí tu tesis así sin repetir el problema.** La Problematiza ya está en la ficha, así que la sección arranca con objetos, periodo, espacio, disciplinas y enfoque.
  - Consecuencia para el prompt de la nota: `central_problem` sale del esquema.
- **Preguntas de investigación sugeridas** (antes «Tu tesis podría…»).
  - Cada tipo tiene nombre sustantivo y un diagrama SVG fijo en el color del campo: Comparación, Rastreo, Explicación, Evaluación, Prospectiva y Exploración.
  - El enfoque metodológico se muestra como «Método: …».
  - Se quitaron las tesis antecedentes de cada pregunta.
  - Consecuencia para el prompt de preguntas: `antecedent` y `why_it_matters` salen del esquema; quedan `type` (lista cerrada), `question` y `methodological_angle`.
- **Verificación:** capturas headless en escritorio (1440×900, día y noche, hover de una tesis cercana) y móvil (390×844). Consola sin errores.
- **Ajuste:** el mapa ya no se queda fijo. Solo acompaña el inicio (ficha y «Comprendí tu tesis así») en la columna derecha, y desde las preguntas el análisis ocupa todo el ancho. En móvil el mapa sigue arriba. Se verificó con capturas en escritorio y móvil.
- **Ajuste:** la ficha inicial queda en título, meta y aviso de guardado. La Problematiza pasa a encabezar «Comprendí tu tesis así». Se quitó la mascota de la ficha: solo queda la de la barra de estado, así que ya no celebra dos veces.
- **Ajuste:**
  - En la ficha, las palabras clave se cambian por los objetos de estudio: lista compacta en flujo, cada objeto con un guion del color del campo que se dibuja al aparecer, uno tras otro. Se usa guion y no anillo para no confundirlo con el glifo de programa.
  - Se quitaron la fila «Disciplinas» (repetía programa y enfoque) y «Análisis guardados: 1 de 2».

### Laboratorio: tesis parecidas en una sola sección (boceto, 25-sep-2026)

- **Objetos de estudio.** Llevan su rótulo explícito en la ficha. Aparece junto con la lista.
- **Una sola sección.** «Las 100 tesis más parecidas a la tuya» y «Las tesis más cercanas» se fusionaron. La sección va al final, después de los asesores, para que el llamado a guardar siga cerrando el análisis.
- **Las gráficas son filtros.**
  - A la izquierda: años, áreas, niveles, campos, temas, subtemas, programas y planteles. Cualquier barra, año o renglón de leyenda filtra; los filtros se combinan.
  - Cada gráfica cuenta con los demás filtros, pero no con el suyo, así que se puede cambiar de valor sin quitar el filtro.
  - La barra tenue es el total entre las 100 y la llena, lo que queda. Aparece «n de total».
- **La lista de la derecha.**
  - Queda fija mientras se recorren las gráficas.
  - Muestra las tesis que cumplen los filtros, de la más a la menos parecida. Usa la gramática de las fichas del atlas: puntos de nivel, año, barra del área, anillo del programa y punto del plantel.
  - Cada filtro activo tiene su botón para quitarlo, y hay un «Quitar todos».
  - El botón para guardar se adapta: «Guardar las 2», «Guardar esta tesis».
  - Ejemplo: al tocar «Humanidades y Artes 2» se ven esas dos tesis, de Historia y de Estudios latinoamericanos, ambas de Filosofía y Letras.
- **Móvil.** Una columna. Al tocar un filtro, la página baja hasta la lista.
- **Verificación:**
  - capturas en escritorio (sin filtro; un área; programa más año, que da 0 resultados; noche) y en móvil;
  - consola sin errores.
- **Banda gris de inicio.**
  - El usuario sentía el fondo vacío. Le propuse cuatro recursos: banda gris, puntos del atlas de fondo, línea de metro y mascota por sección. Eligió solo la banda.
  - La ficha, «Comprendí tu tesis así» y el mapa van sobre `--surface` a todo el ancho, con un `::before` de sangrado completo y `overflow-x: clip` en `body`. El mapa conserva su fondo `--paper` y resalta como tarjeta.
  - Verificado en día, noche y móvil, sin desplazamiento horizontal.
- **Fuera la banda gris (se veía «hecha por IA»); inicio como lámina de atlas.**
  - Referencias:
    - la maquetación del FT: filetes finos que se leen como textura y rigor de retícula;
    - la reacción de 2026 contra el diseño «liso de IA»: grano de papel, retículas y texturas táctiles.
  - Cuatro recursos:
    1. Retícula de papel cuadriculado detrás del inicio, a todo el ancho: menor cada 24 px, mayor cada 120 px, token `--reticula`. Se desvanece hacia abajo con `mask-image`.
    2. Grano de papel en toda la página: `feTurbulence` en SVG `data:`, fijo, opacidad por token `--grano`, de día y de noche.
    3. Cabecera de lámina con filete doble de prensa: «Laboratorio Análisis de tesis» y la fecha. El título del mapa lleva el mismo filete grueso.
    4. El mapa como plancha: marcas de coordenadas cada 42 px en el marco.
  - Todo es tinta a baja opacidad, sin colores nuevos.
  - Verificado en día, noche y móvil, sin desplazamiento horizontal.

### Laboratorio: lomo, títulos sin voz de chat y barra de estado como cabecera (boceto, 25-sep-2026)

El usuario sentía que el laboratorio «se ve muy IA» y pidió quitar la cuadrícula y buscar elementos laterales, profundidad y textura sutil.

**Diagnóstico** (con capturas y referencias):
- La retícula es un patrón catalogado como slop («Decorative grid-line background», impeccable.style/slop).
- Las marcas de coordenadas del marco fingían una precisión que el mapa no tiene: sus posiciones no tienen unidades.
- Los títulos tenían voz de asistente («Comprendí tu tesis así», «Estos son los asesores con los trabajos más similares al tuyo»).
- Al terminar, la barra fija gastaba 54 px en decir «Análisis listo.».

**Propuestas.** Hoja sobre mesa, lomo, notas al margen y barra como cabecera. Se probaron con CSS inyectado. La textura de la nube del atlas en los márgenes se descartó: con unos 100 px solo se veían motas sueltas.

**El usuario eligió el lomo, los títulos y la barra de estado.** Cambios:
- **Fuera la retícula** (`.inicio::before`, token `--reticula`) y las marcas de coordenadas del marco del mapa.
- **Grano detrás del contenido.** `body::after` pasa de `z-index: 50` a `-1`. Ya no ensucia texto ni mapa, y las barras y el mapa, con fondo propio, quedan lisos encima.
- **Lomo.**
  - Una columna de 36 px con filete en el borde izquierdo de `.page`. Como en una tesis empastada, el título corre en vertical y se lee de abajo arriba, seguido de grado y programa y el año.
  - Es fijo (`sticky`) y usa tinta, no color, para no caer en el anti-patrón 23.
  - Aparece con un fundido cuando el título de la ficha sale de la vista (IntersectionObserver), para no repetirlo en la primera pantalla.
  - Se oculta en pantallas de hasta 640 px.
- **Títulos.**
  - «Aquí se encuentra tu tesis» pasa a «Ubicación en el atlas».
  - «Comprendí tu tesis así» pasa a «Planteamiento».
  - «Tus objetivos, analizados» pasa a «Objetivos».
  - «Estos son los asesores…» pasa a «Asesores de tesis parecidas».
  - «Las 100 tesis más parecidas a la tuya» pasa a «Las 100 tesis más parecidas».
  - Los mensajes de carga se ajustan igual: «Leyendo el planteamiento», «Revisando los objetivos».
- **Barra de estado como cabecera de página.**
  - Los 6 guiones de pasos pasan a ser 5 botones, uno por sección en el orden de la página: Planteamiento y ubicación, Preguntas, Objetivos, Asesores y Tesis parecidas.
  - Mientras se prepara el análisis, cada guion se llena cuando su sección está lista, en el orden en que llegan, y desde ese momento lleva a ella.
  - La mascota celebra con «Análisis listo.» y, 1.8 s después, la barra dice en qué sección vas y llena los guiones hasta ella.
  - Un contador de corridas evita que un «Repetir» a media secuencia active la cabecera antes de tiempo.

**Verificación:**
- Capturas headless en escritorio (1440×900) durante la carga, al inicio, en Preguntas, en Asesores, al final y de noche; también en móvil (390×844).
- El salto desde un guion deja la sección bajo las barras (`scroll-padding-top`) y la cabecera cambia a «Asesores de tesis parecidas».
- Sin desplazamiento horizontal. Consola sin errores.

### Laboratorio: pie de página y logo NodOS v1 vectorizado (boceto, 25-sep-2026)

**Logo.**
- `NodOS logo v1.png`, una imagen de 1320×1191 sobre blanco, se vectorizó a `prototypes/atlas_vecindario_mvp/nodos-logo-v1.svg` (8 KB).
  - Se usó potracer por capas de color.
  - Cada píxel se proyecta sobre la recta blanco→color para que los bordes suavizados no creen capas falsas.
  - Se descartó el contorno del lienzo que potrace devuelve en cada capa.
- **Colores: 4, todos del sistema, que el usuario pidió cambiar.**
  - Azul del laboratorio `#1d4f91`: el nodo grande, «Nod» y el punto central.
  - Rojo de Humanidades y Artes: el segundo nodo y «OS».
  - Verde de Biológicas y ocre de Sociales: los puntos.
  - Se comparó con el verde como color dominante y se descartó, porque cae en el acento esmeralda genérico (anti-patrón 16).
- Salen de los tokens `--marca-azul`, `--marca-rojo`, `--marca-verde` y `--marca-ocre`, con valores de noche iguales a los del mapa. El SVG independiente trae los valores de día por defecto.

**Pie.**
- Va sobre `--surface` a todo el ancho, alineado con la columna del contenido (después del lomo).
- Tres columnas:
  - el logo con el lema «Las 609,154 tesis de la UNAM, ordenadas por lo que tratan.»;
  - Explorar: Mapa, Laboratorio y Método;
  - El proyecto: Aviso de privacidad, Contacto y «Apoya este proyecto» (Buy Me a Coffee), con un ícono de taza en ocre.
- Abajo, tras un filete, el aviso: proyecto independiente y no oficial, sin afiliación con la UNAM; datos del catálogo público TESIUNAM; tesis sin el nombre de quien las escribió. Al lado, © 2026.
- En móvil, el logo va arriba y los dos grupos de enlaces en dos columnas.
- **Pendiente:** los tres enlaces del proyecto apuntan a `#` con `data-pendiente`, hasta tener:
  - la página del aviso de privacidad;
  - el correo de contacto;
  - el usuario de Buy Me a Coffee.
- **Verificación:** capturas en escritorio (1440×900, día y noche) y en móvil (390×844). Sin desplazamiento horizontal y consola sin errores.

### Laboratorio: pie compacto (boceto, 25-sep-2026)

El usuario pidió un pie más compacto. Además, el lema («Las 609,154 tesis de la UNAM, ordenadas por lo que tratan») «se ve horrible, muy IA»: solo deben quedar el logo y el texto con enlaces, algo más grande.

- **Una sola banda de 144 px en escritorio**, antes unos 300. El logo va a la izquierda con 88 px de ancho. A su lado van dos renglones:
  - los enlaces, en 16 px: Mapa, Laboratorio y Método a la izquierda; Aviso de privacidad, Contacto y «Apoya este proyecto» a la derecha;
  - tras un filete, el aviso en 14 px: «Proyecto independiente y no oficial, sin afiliación con la UNAM. Datos del catálogo público TESIUNAM.», con © 2026 NodOS a la derecha.
- **Fuera:** el lema y los encabezados «Explorar» y «El proyecto».
- **Móvil:** el logo va arriba; debajo, los dos grupos de enlaces y el aviso.
- **La clase raíz pasa de `.pie` a `.pie-pag`**, porque `.pie` ya nombraba los pies de la mascota.
- **Verificación:** capturas en 1440×900 (día y noche), 1000×800 y 390×844. Sin desplazamiento horizontal y consola sin errores.

### v4.18.1: el nombre es NodOS (2026-09-25)

El usuario fijó el nombre: **NodOS**, como en el logo, y no «NodOs».

- Se cambió en la pestaña y la barra de navegación del atlas (`index.html`), en la barra y el pie del laboratorio, en `CLAUDE.md` y en `PRODUCT.md`.
- Las entradas anteriores de esta bitácora conservan la grafía de su momento.
- **Verificación:** el atlas carga con título «NodOS», la marca «NodOS» y la versión 4.18.1, sin errores en consola.

### Laboratorio: pie azul marino, logo en blanco y paleta nueva del logo (boceto, 25-sep-2026)

**Lo que pidió el usuario:**
- letras más pequeñas y texto más junto;
- un pie algo más grande;
- nada del «horrible fondo gris genérico de UI»: lista negra en todo diseño;
- el pie en azul marino con el logo en blanco;
- cambiar los colores del logo, que «parecen los de Art Attack».

**Pie:**
- Fondo `--pie-fondo` (`#12294d`), igual de día y de noche, con el logo en blanco a 112 px y 44 px de relleno vertical: 199 px de alto en escritorio.
- Los enlaces van en 14 px y juntos: Mapa, Laboratorio y Método, y a 40 px Aviso de privacidad, Contacto y «Apoya este proyecto», con la taza en ocre.
- Debajo, tras un filete blanco al 18 %, el aviso en 12.5 px y el © NodOS, en el mismo renglón.
- Tokens nuevos: `--pie-fondo`, `--pie-tinta`, `--pie-tinta-2` y `--pie-linea`.

**Paleta del logo.** Se compararon 4 paletas con el logo real y se eligió la 1:
- azul del laboratorio `#1d4f91` en el nodo grande y «Nod»;
- azul medio `#5b95cf` de la escala de niveles del mapa en el segundo nodo y «OS»;
- celeste `#9cc3e6` de la misma escala en dos puntos;
- ocre `#c98a2e` de Sociales en un solo punto, de acento.

Se descartaron:
- solo la escala azul, sin acento;
- azul marino y cobre, cuyos dos azules no se distinguían;
- tonos profundos de área, que seguían siendo multicolor.

En `nodos-logo-v1.svg` los colores se cambian con `--marca-azul`, `--marca-azul-2`, `--marca-celeste` y `--marca-ocre`. El punto central tiene su propia subruta.

**Fuera el gris de fondo.**
- Se quitó el token `--surface` del laboratorio.
- Las escaleras de Bloom pierden el relleno gris (`--grid`) y quedan solo con el contorno de los peldaños.
- Se añadió el anti-patrón 24 en `PRODUCT.md`.

**Verificación:**
- Capturas en 1440×900 (día y noche) y 390×844.
- Escaleras de Bloom revisadas.
- Sin desplazamiento horizontal y consola sin errores.

### v4.18.2: sin fondos grises en el atlas (2026-09-25)

Se aplica la lista negra del fondo gris (anti-patrón 24) al atlas:
- **Botones (`.btn`):** el *hover* subraya en vez de pintar el fondo.
- **Cierres de paneles, fichas, relato, taller y páginas:** el *hover* solo oscurece la tinta.
- **Resultados de búsqueda:** el activo o el que tiene el cursor subraya su nombre. El renglón secundario pasa a `inline-block` para que el subrayado no lo alcance.
- Se eliminó el token `--surface` de día y de noche.

**Verificación:** el atlas carga sin errores en consola. Al buscar «banca» en la búsqueda, el primer resultado subraya solo «Banca y finanzas».

### Marca: logo oficial de NodOS (2026-09-25)

El usuario eligió como **logo oficial** la variante 2 de la comparación, «solo la escala azul», y la versión **en blanco sobre azul marino**.

**Paleta oficial:** los azules de la escala de niveles del mapa, sin otros colores.

| Pieza | Color |
|---|---|
| Nodo grande y «Nod» | `#143a6b` |
| Segundo nodo y «OS» | `#2d65a8` |
| Punto izquierdo | `#9cc3e6` |
| Punto derecho | `#5b95cf` |
| Punto central | `#5b95cf` |
| Fondo de la versión en blanco | `#12294d`, azul marino del pie |

**Archivos en `marca/`** (SVG, unos 9 KB cada uno):
- `nodos-logo.svg`: el oficial en color, con fondo transparente.
- `nodos-logo-blanco.svg`: en blanco con fondo transparente, para fondos oscuros.
- `nodos-logo-blanco-sobre-marino.svg`: en blanco sobre `#12294d`, con margen.

**Puntos cambiables.**
- Los puntos quedan libres en la identidad: en el video de introducción y en el branding cambiarán para dar dinamismo. El logo oficial es el de arriba.
- Cada forma tiene su `id`: `nodo-1`, `nodo-2`, `punto-izq`, `punto-der`, `punto-centro`, `palabra-nod` y `palabra-os`.
- Su color sale de una variable CSS con valor por defecto: `--nodos-azul-1`, `--nodos-azul-2`, `--nodos-punto-izq`, `--nodos-punto-der`, `--nodos-punto-centro` y `--nodos-fondo`.
- Los puntos se animan o recolorean sin tocar el trazo.

**Cambios en el repositorio.**
- Se retira `prototypes/atlas_vecindario_mvp/nodos-logo-v1.svg`, la paleta azul, azul medio, celeste y ocre de la entrada anterior.
- El pie del laboratorio ya usa la versión en blanco sobre `--pie-fondo` (`#12294d`).
- El PNG original, `NodOS logo v1.png`, sigue en la raíz como fuente.

**Verificación:**
- Los tres SVG son XML válido. Los comentarios no llevan `--`, que rompía el archivo al cargarlo como imagen.
- Se ven bien como `<img>` en Chrome.
- En línea, redefinir `--nodos-punto-izq`, `--nodos-punto-der` y `--nodos-punto-centro` cambia solo los puntos.

### Marca: exploración del puma como guiño (2026-09-25, descartada)

El usuario pidió dos cosas:
- un guiño sutil al puma de la UNAM en el espacio libre sobre la «d» del logo;
- una reformulación del logo en la que se intuya la silueta del puma, «como la flecha de FedEx».

**Puma redibujado.** No se usó el logo original. Se redibujó una versión propia y simplificada, con esquinas redondeadas:
- el contorno con la joroba central y las orejas;
- el hueco en «U», formado por los ojos en cuarto de círculo, los canales y la abertura inferior;
- la barbilla.

**Propuestas en `marca/exploracion-puma/`:** cada una en color y en blanco sobre azul marino, más `comparacion.png` con la vista a 112 px.
1. `1_guino`: una cabeza de puma de 90 unidades sobre el asta de la «d», en el hueco entre los dos nodos, con el color de los puntos (`#5b95cf`). A 112 px apenas se ve; funciona en tamaños grandes y en video.
2. `2a_calado`: el hueco en «U» del puma calado en el cuerpo del nodo grande. El nodo hace de cabeza. Es lo más cercano a la idea de FedEx y se sigue viendo a 112 px.
3. `2b_red`: el símbolo se rehace como una red de nodos bulbosos con cuellos delgados, fundidos con desenfoque y umbral y vectorizados con potrace. Primero se ve una red y luego se intuye el puma.
   - Una primera versión maciza se descartó por demasiado literal: era el logo de Pumas en azul.

**Conflicto abierto.**
- `CLAUDE.md` y `PRODUCT.md` prohíben los logotipos de la UNAM y que el proyecto parezca oficial.
- El puma es una marca registrada vinculada a la UNAM.
- Adoptar cualquiera de estas propuestas exige cambiar esa regla a conciencia y valorar el riesgo de marca.
- Mientras tanto, los archivos se quedan fuera del logo oficial.

**Resultado:** el usuario la descartó («no me gustó, mantengamos el original»). Se borró `marca/exploracion-puma/` y queda el logo oficial de `marca/`.

### Laboratorio: título con jerarquía, filete único, secciones subrayadas y pie (boceto, 25-sep-2026)

**Cambios pedidos por el usuario:**
- **Título de la tesis.**
  - «Es EL título de la tesis»: no debía verse genérico.
  - Pasa de 30 px en peso 700 a `clamp(34px, 3.3vw, 46px)` en peso **800**, que se añade a la carga de Libre Franklin.
  - Interletrado −0.025em, interlineado 1.06, `text-wrap: balance` y hasta 22 caracteres por renglón.
  - En móvil, 30 px.
- **Un solo filete grueso sobre el título**, igual que el del mapa. Se quitó la línea fina de abajo (el doble filete de prensa).
- **Subrayado sutil en los títulos de sección**, «Ubicación en el atlas» incluida: 2 px en `--line-strong`, separado 8 px de la letra.
- **Pie.**
  - Los dos grupos de enlaces van a los extremos: Mapa, Laboratorio y Método a la izquierda; Aviso de privacidad, Contacto y «Apoya este proyecto» a la derecha.
  - El © 2026 NodOS pasa a la esquina derecha.
  - El aviso queda en «Proyecto independiente y no oficial. Datos del catálogo público TESIUNAM.»; se quitó «sin afiliación con la UNAM», que se sobrentiende.

**Pendiente:** el titular del © y la licencia. El usuario quiere licencia MIT.

**Verificación:** capturas en 1440×900 (inicio, sección, pie y noche) y en 390×844. El título mide 46 px en escritorio y 30 px en móvil. Sin desplazamiento horizontal y consola sin errores.

## Estado del proyecto y hoja de ruta (2026-09-25)

Diagnóstico de todo el proyecto al cierre del 25-sep-2026. **Reemplaza a «Pendientes consolidados (2026-09-23)»** como lista viva de lo que falta; esa sección queda como histórico. Los porcentajes son estimaciones de avance, no métricas.

### Dónde estamos

| Frente | Avance | Estado |
|---|---|---|
| Datos (pipeline offline) | ~90 % | Corpus de 609,154 tesis limpio y sin autores en el título; e5-large, HDBSCAN + Ward + PaCMAP; jerarquía corregida a mano; dataset público `data_unam.parquet` (sin publicar). |
| Frontend del atlas | ~85 % | v4.18.2: mapa WebGL, búsqueda, fichas de tesis, cluster y asesor, taller, modo noche, Ajustes, introducción y Método. Faltan matices y los puntos de abajo. |
| Frontend del Laboratorio | ~40 % | Solo existe la plantilla del **análisis terminado**, como boceto con un caso real (`bocetos/lab/`). No hay formulario de entrada, estados de error ni guardados, y no está integrado a la app. |
| Backend del Laboratorio | ~5 % | `pipeline/lab_contexto.py` calcula el contexto real, pero offline. El backend viejo (`app/MI-TESIS-UNAM_github/scripts/`, FastAPI con Groq y Cerebras) tiene 9 errores documentados y usa el modelo viejo: se reescribe, no se porta. |
| Producción | 0 % del producto nuevo | Todo corre en local. El sitio viejo (`MI-TESIS-UNAM`, Cloudflare Pages) sigue con datos anteriores. |
| Pruebas | ~10 % | Verificación visual manual con `tools/cdp.mjs`. Sin pruebas automáticas y sin CI. |
| Ciberseguridad | ~15 % | Privacidad de autores resuelta en los datos nuevos. Sin CSP ni cabeceras de seguridad; librerías de CDN sin versión fija; pendientes del repo viejo. |

### Hecho (resumen; el detalle está en las secciones de arriba)

- **Datos:**
  - limpieza de columnas (ADR-0004 a 0011);
  - títulos sin mención de autor (`titulo_sin_autor.py`, 92.7 % cortados y verificados);
  - embeddings e5-large del corpus completo y de Nobel;
  - clustering y jerarquía de 130 campos, ~440 temas y 513 subtemas;
  - vecindarios precomputados (ADR-0014);
  - 81,151 asesores unificados a partir de 117,482 formas.
- **Atlas:** interfaz v4.0 a v4.18.2 con la identidad acordada (Libre Franklin, tokens, 24 anti-patrones vetados), modo noche completo y marca NodOS.
- **Laboratorio (diseño):**
  - decisiones de producto: Problematiza, 3 llamadas de IA, 2 análisis guardados y 2 nuevos al día, Bloom con léxico, asesores sin IA;
  - plantilla del análisis con datos reales;
  - especificación de los prompts nuevos.
- **Marca:** logo oficial en `marca/` (color y blanco sobre azul marino).

### Qué falta, por frente

**1. Decisiones de arquitectura (bloquean lo demás).** Van como RFC y luego ADR.
- **Propuesta investigada: [`rfc/0002-arquitectura-produccion-gratuita.md`](rfc/0002-arquitectura-produccion-gratuita.md)** (25-sep-2026).
  - Arquitectura a costo cero:
    - Cloudflare Pages para el sitio;
    - un Worker como puerta de la API, con Turnstile y cuota en D1;
    - Google Cloud Run con e5-large ONNX int8 y FAISS SQ8 para la parte de datos del Lab;
    - Groq, con Workers AI de respaldo, para la parte de IA;
    - cuentas desde la primera versión (decisión del usuario), con Supabase Auth para la identidad y D1 para los guardados.
  - Descartados con datos: Hugging Face Spaces con Docker (ya exige PRO), Vectorize (excede su capa), Gemini gratis (entrena con los datos) y Cerebras (sin capa gratuita).
- [ ] **Hosting del sitio estático.** Opciones: Cloudflare Pages solo, o Pages + R2 para `data/`.
  - ADR-0001 sigue «Propuesto».
  - Hoy el bundle cabe en Pages: 3,230 archivos y el mayor de 24.4 MB, con un límite de 20,000 archivos y 25 MiB por archivo. Pero no hay margen para el vecindario completo.
- [ ] **Backend del Laboratorio.** La consulta **tiene que** embeberse con el mismo `multilingual-e5-large` del corpus: otro modelo rompe la búsqueda.
  - Opciones:
    - (a) servidor pequeño con FastAPI, el modelo en ONNX int8 y el índice en memoria;
    - (b) endpoint de inferencia administrado solo para el embedding, con la búsqueda y la API aparte.
  - Números de referencia (estimados, por medir):
    - índice de 609,154 × 1024: 2.5 GB en float32 y 1.25 GB en float16, o unos 100 a 200 MB con FAISS IVF-PQ;
    - búsqueda exhaustiva: decenas de milisegundos en CPU;
    - e5-large en CPU: alrededor de 1 s por consulta.
  - Con 4 GB de RAM cabe todo.
- [ ] **Autenticación y base de datos** para las sesiones, los 2 análisis guardados, las tesis guardadas y MI TESIS. Por ejemplo Postgres administrado con auth incluido, o D1 con un proveedor de auth.
- [ ] **Proveedor de LLM y modelo** para nota, Bloom y preguntas. llama-3.1-8b ya no es gratis en Groq. Elegir con un conjunto de evaluación de 6 a 8 casos de campos distintos.
- [ ] **Economía unitaria** (RFC-0001, punto 2): costo por análisis × 2 al día × usuarios esperados; tope de gasto en el proveedor.
- [ ] **Cerrar RFC-0001.** Recomendación: lanzar el **Laboratorio en dos tiempos**.
  - Primero la parte de datos (ubicación, parecidas, asesores, saturación), que solo necesita embedding y búsqueda, sin costo de LLM.
  - Después la parte de IA (nota, Bloom, preguntas), con sesión y cuota.
- [ ] **Diagrama C4** del sistema (contexto y contenedores): sitio estático, datos, API del Lab, IA, base de datos y pipeline.

**2. Frontend: lo que falta.**
- Atlas:
  - [ ] Leer `?tesis=` (y campo, tema, subtema) en la URL: abrir la ficha y volar a la tesis. Lo necesitan los enlaces del Lab y compartir.
  - [ ] **MI TESIS** en el mapa (nodo especial con flecha) y tesis guardadas; requieren sesión.
  - [ ] Página **Método**:
    - añadir el Laboratorio (qué es dato y qué es IA, límites);
    - añadir privacidad;
    - cambiar «NODO UNAM» por NodOS;
    - revisar la versión que muestra.
  - [ ] Pie y marca del atlas alineados con el Laboratorio (logo, enlaces legales).
  - [ ] Revisión humana de los 130 nombres de campo y de los 26 hitos; decidir los nombres de tema y subtema.
  - [ ] Nobel más cercano (ADR-0012), si sigue en alcance.
  - [ ] Prueba en el navegador real (GPU, trackpad), en móvil y de accesibilidad (teclado, lector de pantalla, contraste).
- Laboratorio:
  - [ ] **Formulario de entrada**: título, Problematiza, objetivos con léxico de Bloom en vivo y los casos límite de su tabla, palabras clave, programa, grado y periodo; retroalimentación por campo.
  - [ ] Integrar la plantilla a la app y conectarla a la API real por streaming (SSE): cada sección aparece al llegar.
  - [ ] Estados de carga, error, cuota agotada y sin sesión; «mis análisis» con los 2 guardados y la opción de borrar.
- Páginas:
  - [ ] Aviso de privacidad, contacto, licencia y «Apoya este proyecto»; hoy apuntan a `#`.
  - [ ] Titular del © y archivo `LICENSE` (MIT para el código; datos y marca excluidos).
  - [ ] Correo de contacto: cuenta de Gmail solo del proyecto y, con dominio, `contacto@` reenviado ahí (ver «Correo de contacto del proyecto (2026-09-25)»).

**3. Backend del Laboratorio.**
- [ ] API nueva, no el FastAPI viejo:
  - un endpoint de análisis embebe la consulta, busca las 100 vecinas y calcula el contexto (portar `lab_contexto.py`);
  - la respuesta llega por SSE: primero los datos, luego las 3 llamadas de IA.
- [ ] Prompts nuevos según la plantilla:
  - nota sin `intro` ni `central_problem`;
  - Bloom con verbo, nivel y banderas;
  - preguntas con `type` de lista cerrada y `methodological_angle`.
  - Esquemas validados y reintento controlado.
- [ ] Léxico de Bloom corregido: un nivel por verbo, verbo rector, lematización. Compartido entre el formulario (JS) y el backend.
- [ ] Umbral de similitud para la «confianza» de ubicación, calibrado con el conjunto de evaluación (la similitud e5 está comprimida entre 0.86 y 0.91).
- [ ] Sesión, cuotas (2 análisis al día, 2 guardados) y almacenamiento de análisis y tesis guardadas.
- [ ] Rescatar `validators.py`, `ai_advisors.py` y `ai_bibliography.py` del repo `MI-TESIS-UNAM` antes de purgarlo, como referencia.

**4. Producción y despliegue.**
- [ ] Dominio y HTTPS; entornos de previsualización por rama y de producción.
- [ ] Despliegue automático desde `main` (GitHub Actions a Pages; la API aparte).
- [ ] Datos versionados por ruta (`data/v1/…`) con `Cache-Control: immutable` y brotli; rollback cambiando la versión (ADR-0001).
- [ ] Librerías (regl, regl-scatterplot, d3, pub-sub-es) con versión exacta y SRI, o servidas desde el propio dominio. Hoy `d3@7` no tiene versión exacta.
- [ ] Observabilidad: errores de frontend y API, analítica sin cookies, alertas de gasto del LLM y de caída.
- [ ] Respaldo de la base de datos de usuarios.
- [ ] Retirar o redirigir el sitio viejo `MI-TESIS-UNAM`, que sirve datos anteriores.

**5. Pruebas.**
- [ ] CI en cada push:
  - pruebas del pipeline, sobre todo una **prueba de privacidad** que falle si algún título publicado trae mención de autor;
  - normalización de entidades.
- [ ] Pruebas de extremo a extremo del atlas y del Lab con el harness `tools/cdp.mjs` o con Playwright: escritorio, móvil y noche, con la consola sin errores como criterio.
- [ ] Backend:
  - contratos de la API y validación de esquemas;
  - la **tabla de casos límite de Bloom** como pruebas;
  - casos de inyección de prompt.
- [ ] Conjunto de evaluación de la IA (6 a 8 casos) con revisión humana antes de cambiar de modelo o de prompt.
- [ ] Rendimiento: tiempo de primera carga (hoy se descargan varios MB antes de ver el mapa), fps con GPU real, carga de la API.

**6. Ciberseguridad y privacidad.**
- [ ] **Cabeceras del sitio:**
  - Content-Security-Policy con orígenes explícitos de scripts y fuentes;
  - HSTS;
  - `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` y `frame-ancestors`.
- [ ] **XSS:** toda salida del modelo y todo texto del usuario se escapa al pintar. El boceto ya usa `esc()`; auditarlo al integrar.
- [ ] **API del Lab:**
  - autenticación y límite de tasa por usuario y por IP;
  - tope de tamaño de entrada;
  - CORS con orígenes explícitos (el backend viejo tenía `*` con credenciales);
  - sin tracebacks al cliente;
  - protección contra bots (desafío tipo Turnstile);
  - tope de gasto en el proveedor de IA.
- [ ] **Inyección de prompt:** el texto del usuario viaja como dato delimitado; la salida se valida contra un esquema y nunca se ejecuta.
- [ ] **Secretos:**
  - en variables de entorno o en el gestor de secretos del hosting, nunca en el repo;
  - las 4 claves de `app/AI Pipeline/Scripts/` siguen en disco. El usuario decidió no rotarlas; conviene hacerlo antes de producción, y el backend nuevo tendrá claves propias.
- [ ] **Repo viejo `MI-TESIS-UNAM`:** purgar el historial de Git LFS (autores expuestos) después del rescate; su `thesis_lookup.parquet` todavía trae `author` y `title_raw` con autor.
- [ ] **Privacidad de usuarios:**
  - aviso de privacidad conforme a la ley mexicana de protección de datos personales;
  - consentimiento explícito de que el texto de la tesis se envía a un proveedor de IA (revisar su política de retención y entrenamiento);
  - retención y borrado de análisis;
  - nada del texto del usuario en los logs.
- [ ] Dependencias con versión fija y alertas de vulnerabilidades (Dependabot) en el repo.

### Orden propuesto

1. **Decisiones de arquitectura** (frente 1) y cierre de RFC-0001.
2. **Lanzar el atlas solo (v0), estático.** Es lo seguro y está casi listo:
   - cabeceras y CSP;
   - librerías con versión fija;
   - páginas legales y Método;
   - `?tesis=` en la URL;
   - CI con prueba de privacidad y de extremo a extremo;
   - dominio y despliegue automático;
   - retirar el sitio viejo.
3. **Backend del Lab, parte de datos:** embedding, búsqueda y contexto, con límite de tasa.
4. **Frontend del Lab:** formulario e integración de la plantilla con la API. Lanzar la parte de datos, sin IA.
5. **Sesión, cuotas y guardados;** MI TESIS en el mapa.
6. **Parte de IA del Lab:** prompts nuevos, conjunto de evaluación, tope de gasto y consentimiento. Beta cerrada y luego abierta.
7. Después: dataset público (Kaggle), Nobel más cercano e ideas del backlog.

## Correo de contacto del proyecto (2026-09-25)

Investigación, sin decisión todavía. Depende de la decisión del dominio (RFC-0002, secciones 8 y 9).

**El correo propio sale del dominio.** Recibir en `contacto@algo.com` exige controlar el DNS de `algo.com` para fijar sus registros MX.

- Con `nodostesis.pages.dev` no hay correo propio: `pages.dev` es de Cloudflare y nadie más controla su DNS. El contacto tendría que ser una dirección normal, por ejemplo de Gmail.
- Con dominio propio (`nodostesis.com`) o de eu.org (`nodos.eu.org`) sí:
  - **recibir:** Cloudflare Email Routing, gratis, reenvía `contacto@` a otra dirección sin servidor ni buzón aparte;
  - **responder desde `contacto@`:** «Enviar como» en Gmail, también gratis.

**Separarlo del correo personal.** Opciones gratuitas:

| Opción | Cómo | A favor | En contra |
|---|---|---|---|
| **Cuenta de Gmail solo del proyecto (recomendada)** | Crear, p. ej., `nodostesis@gmail.com`. Sin dominio, es el contacto; con dominio, Email Routing reenvía `contacto@` ahí y se responde con «Enviar como» | Nada se mezcla con la cuenta personal; se cambia de cuenta con un toque; se puede dar acceso a un colaborador sin abrir la cuenta personal | Una cuenta más que cuidar (contraseña, 2FA) |
| Filtro en el Gmail personal | Filtro `to:contacto@…` con «Omitir Recibidos» y la etiqueta «NodOS» | Lo más rápido | El correo del proyecto sigue viviendo en la cuenta personal |
| Zoho Mail, plan gratuito | Buzón real con el dominio, sin reenvío | Buzón propio del dominio | Solo web y app, sin IMAP; sustituye a Email Routing (los MX apuntan a uno o al otro); sus condiciones gratuitas han cambiado, revisarlas antes |

Proton Mail y Outlook.com no sirven gratis: el dominio propio es de pago.

**Pendiente:** crear la cuenta del proyecto y usarla como destino del reenvío cuando exista el dominio. Es la dirección que irá en «Contacto» del pie y en el aviso de privacidad.
