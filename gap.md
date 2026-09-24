# El "hueco central" del atlas: ¿evidencia de un vacío real de conocimiento en la UNAM?

_Investigación 2026-09-22, a pedido del usuario, a partir de la observación ya registrada en `development.md` (item 1 del checklist de evidencia visual) sobre el hueco visible en `docs/evidencia_visual/01_mapa_pacmap_clusters_hdbscan.png`._

## Pregunta original

¿Los pasos que ya se corrieron (embeddings e5-large, HDBSCAN, PaCMAP) son metodológicamente suficientes para decir que ese hueco central es un **vacío real** en la producción de conocimiento de la UNAM — un área temática que la universidad genuinamente no investiga? Si lo es: ¿qué coordenadas/áreas administrativas abarca, y qué temas podrían faltar ahí?

## Veredicto, primero

**No. La evidencia disponible no sostiene la lectura de "vacío real de conocimiento".** Es un artefacto combinado de (a) la geometría del layout PaCMAP y (b) una concentración moderada de títulos cortos/genéricos de **varias disciplinas distintas** que ya están bien representadas en otras zonas del mapa. No hay un tema ausente identificable — hay, si acaso, un patrón de *cómo se titulan* ciertas tesis, no de qué *no se investiga*. Las tres razones concretas están en la sección 3.

Esto no invalida el resto del pipeline (HDBSCAN/PaCMAP/e5-large) — de hecho la validación cruzada con los laureados Nobel (ver `development.md`, sección Nobel) mostró que el layout captura estructura temática real con alta fidelidad. Este hallazgo específico es sobre una región puntual (0.41% del corpus), no sobre el pipeline en general.

## 1. Metodología

Script: `pipeline/analizar_hueco_central.py` (reproducible, sin parámetros ocultos). Pasos:

1. **Centro geométrico** = centroide (x̄, ȳ) del layout PaCMAP completo (609,154 puntos) → `(0.086, 0.107)`.
2. **Perfil de densidad radial**: anillos concéntricos de ancho 0.2 unidades desde el centroide, densidad = puntos / área del anillo. Pico de densidad: 2,108.5 pts/unidad² en r≈3.0.
3. **Radio del hueco**: primer radio (desde el centro, hacia afuera) donde la densidad alcanza 30% del pico → **r = 1.80**. Umbral arbitrario pero explícito y barato de auditar/ajustar (`DENSITY_THRESHOLD` en el script).
4. **Composición**: para los puntos con r < 1.80, se cruzó `cluster_id` (HDBSCAN), `topic_label` (c-TF-IDF, `cluster_topics_ctfidf.parquet`), `area` administrativa, y `titulo` (`data/public/data_unam.parquet`) contra el resto del corpus como baseline.

## 2. Resultados numéricos

**Región**: 2,509 puntos (**0.41% del corpus**, no un porcentaje grande). Bounding box: `x ∈ [-1.71, 1.88]`, `y ∈ [-1.67, 1.90]` — el mapa completo abarca `x ∈ [-26.43, 26.58]`, `y ∈ [-24.50, 24.68]`, así que el hueco ocupa una fracción minúscula del área total del lienzo (~0.5% del rango lineal en cada eje).

**Área administrativa (hueco vs. corpus completo, factor de enriquecimiento)**:

| Área | Global | En el hueco | Enriquecimiento |
|---|---|---|---|
| Área 1 (Físico-Matemáticas) | 20.5% | 30.9% | **1.51x** |
| Área 2 (Biológicas y Salud) | 40.4% | 39.3% | 0.97x (≈baseline) |
| Área 3 (Sociales) | 29.1% | 17.1% | **0.59x (sub-representada)** |
| Área 4 (Humanidades y Artes) | 8.3% | 9.8% | 1.18x |
| (sin área) | 1.7% | 2.9% | 1.70x |

El hueco **no** es una mezcla proporcional de las 4 áreas — sobre-representa Área 1 y sub-representa notablemente Área 3, con Área 2 exactamente en línea con el baseline global.

**Ruido HDBSCAN**: 68.0% dentro del hueco vs. **67.2% global — prácticamente idéntico**. Este es el punto que corrige la nota anterior en `development.md`: el hueco *no* es excepcionalmente ruidoso comparado con el resto del corpus. La composición interesante está en el 32% que sí tiene cluster.

**Aclaración explícita (pregunta natural al leer esto): ¿el hueco es simplemente "las tesis que no caen en ningún cluster"? No.** Densidad total y composición son dos medidas distintas. De los 409,531 puntos de ruido en todo el corpus, solo ~1,706 (0.42%) caen dentro del hueco — casi exactamente la misma proporción que el hueco representa del corpus completo (0.41%). El ruido está repartido de forma prácticamente uniforme por *todo* el mapa, no concentrado en el centro. Lo que define al hueco es que caen **pocas tesis en total ahí** (densidad ~50-135 pts/área cerca del centro vs. pico de 2,108.5 pts/área en la banda densa, 15-40x menos denso) — de esas pocas, la mezcla ruido/cluster es la normal del corpus, no una anomalía.

**Clusters reales presentes** (de los 513 totales, los que aparecen en el hueco — top 3 concentran 25.0% del hueco):

| Cluster | % del hueco | Tema (c-TF-IDF) |
|---|---|---|
| 16 | 9.2% | reforzamiento · respuestas · estímulos · demora · intervalo · reforzador (análisis experimental de la conducta / condicionamiento operante) |
| 416 | 8.1% | química · didáctica · enseñanza · bachillerato · aprendizaje (enseñanza de la química, no química como disciplina) |
| 503 | 7.7% | teorema · espacios · gráficas · grupos · álgebras (matemáticas puras/discretas) |
| 417 | 1.7% | enseñanza · aprendizaje · bachillerato · biología (didáctica de la biología) |
| + una cola larga de ~15 clusters con 6-11 puntos cada uno (tuberculosis, filosofía/Nietzsche, AFORES/retiro, sífilis...) | ~2% | temas dispares sin relación entre sí |

**Títulos duplicados**: 8.8% en el hueco vs. 3.5% en el resto del corpus (**2.5x**). Real pero moderado — la mayoría de los puntos del hueco *no* son duplicados literales. Ejemplos de los títulos más repetidos ahí: "sincope" (12), "asma" (7), "el vih" (6), "aislamiento del campo operatorio" (6) — títulos de una sola palabra o casi, típicos de reportes de caso clínico breves.

Muestra de títulos no duplicados dentro del hueco (aleatoria, `random_state=42`): *"cetram tacubaya"*, *"la novacion"*, *"twitter"*, *"k núcleos en la digráfica de líneas"*, *"kainopolis"*, *"progecto prion"* — todos títulos cortos, de una disciplina distinta cada uno, sin vocabulario de dominio que los distinga de un título genérico.

## 3. Por qué esto NO es evidencia válida de un vacío real

1. **La tasa de ruido en el hueco es igual a la del corpus completo (68.0% vs 67.2%).** Si el hueco fuera "donde no hay investigación", esperaríamos una tasa de ruido *anormalmente alta* ahí — no la hay. El hueco no está más vacío de contenido clusterizable que cualquier otra región del mapa.
2. **Lo que sí hay ahí no es un tema ausente, son temas presentes en otro lugar.** Behavioral/conducta (cluster 16), química didáctica (cluster 416) y matemáticas puras (cluster 503) son clusters reales de tamaño normal (150-2,475 tesis cada uno según la bitácora de calibración de HDBSCAN) — **existen y tienen presencia sustancial en el atlas**, solo que una fracción pequeña de sus miembros (los de título más corto/genérico dentro de ese mismo tema) cae geométricamente cerca del centroide. Un vacío real implicaría *ausencia* de un tema, no la *presencia parcial* de varios temas ya documentados.
3. **La heterogeneidad del contenido restante contradice la hipótesis de "un tema faltante".** La cola larga de clusters minúsculos (tuberculosis, Nietzsche, AFORES, sífilis, "breves consideraciones acerca de...") no comparte ningún campo disciplinar — es la firma de un **mecanismo de título genérico transversal a disciplinas**, no de un hueco temático específico. Si existiera un vacío real y localizado, se esperaría encontrar *un* tema coherente ausente, no fragmentos de una decena de temas ya conocidos.

**Mecanismo más probable (consistente con la hipótesis ya registrada en development.md, ahora con más evidencia)**: títulos cortos y de vocabulario poco específico — sin importar la disciplina real — producen embeddings más cercanos al promedio del corpus. La repulsión de "far pairs" de PaCMAP empuja los clusters temáticamente coherentes hacia una capa externa, dejando el centro geométrico como zona de baja densidad donde caen, por accidente geométrico compartido (no por afinidad temática), fragmentos de títulos genéricos de disciplinas que no tienen nada en común entre sí.

## 4. Inferencia de temas — respuesta honesta

La pregunta original pedía inferir qué temas "podrían estar tratándose" ahí, con el ejemplo de "física nuclear". **No hay evidencia que sostenga inferir un tema faltante específico** (ni física nuclear ni ningún otro) — hacerlo sería inventar una conclusión que los datos no respaldan. Lo que la evidencia sí permite decir, con confianza, es:

- Los tres temas con mayor presencia real en el hueco son **análisis experimental de la conducta**, **enseñanza de la química** y **matemáticas puras/discretas** — pero los tres están **presentes**, no ausentes, en el corpus de la UNAM (son clusters HDBSCAN de tamaño normal).
- No se identificó ningún tema con presencia cero en el hueco que uno esperaría encontrar ahí por proximidad disciplinar a los tres de arriba (ej. física teórica, estadística aplicada) — la composición es demasiado heterogénea para sugerir un patrón de "campo vecino faltante".

**Cómo se buscaría un vacío real, si se quisiera hacer en serio** (no ejecutado aquí, es una idea para más adelante): comparar la distribución de tamaños de cluster de la UNAM contra una taxonomía externa de disciplinas (ej. clasificación CONACYT/CTI o UNESCO de campos de la ciencia) para ver qué campos *reconocidos externamente* tienen cero o casi cero clusters HDBSCAN propios — eso sería evidencia de ausencia real, a diferencia de "qué cae cerca del centroide de un layout no lineal".

## 5. Visualización

`docs/evidencia_visual/09_hueco_central_composicion.png` (script: `pipeline/graficar_hueco_central.py`). Dos paneles: localizador (mapa completo con círculo rojo marcando el hueco, para dimensionar que es 0.41% del corpus) + zoom coloreado por los 3 clusters reales más grandes presentes ahí (azul/naranja/verde) más dos categorías neutras (ruido y "otros clusters reales", ambos en gris/tostado — no se les asigna tono categórico porque no son el foco de la comparación). Solo 3 tonos con identidad categórica en el panel de zoom, siguiendo el límite de la guía de dataviz del proyecto para separación CVD-segura en todos los pares de un scatter.

**Para recrear ambos (análisis + gráfica)**:
```
python pipeline/analizar_hueco_central.py
python pipeline/graficar_hueco_central.py
```
Requiere `layout_pacmap2d.parquet`, `clusters_hdbscan.parquet`, `cluster_topics_ctfidf.parquet` y `data/public/data_unam.parquet` (para los títulos), todos ya presentes en el repo.

## 6. Implicación para el paso 5 (corte macro/meso, pendiente)

Refuerza la nota ya escrita en `development.md` item 1: la zona central no debe tratarse como "un macro más" al construir el corte desde `condensed_tree.parquet`. Con esta investigación, la recomendación es más específica: **excluir explícitamente la región r<1.80 del centroide (o marcarla como "zona de títulos genéricos, sin tema propio") en vez de dejar que el corte por umbral de rama la asigne a cualquiera de los macros vecinos** — asignarla arrastraría hacia ese macro una mezcla de fragmentos de conducta/química-didáctica/matemáticas que no pertenece temáticamente a ningún macro en particular.

---

# Parte 2: el hueco GRANDE (2026-09-22) — corrección de método, no solo un hallazgo nuevo

**El usuario señaló, viendo `docs/evidencia_visual/09_hueco_central_composicion.png`, que el hueco que se acababa de analizar (arriba) es chico — hay uno notablemente más grande a su izquierda que nunca se caracterizó.** Al investigarlo se encontró algo más importante que un segundo hueco: **el método de la Parte 1 tenía un defecto real.**

## Qué estaba mal

El análisis de arriba definía "el hueco" como un círculo centrado en el **centroide de los 609,154 puntos** (media de x,y = (0.086, 0.107)), asumiendo implícitamente que la zona de baja densidad es radialmente simétrica alrededor del centro de masa del corpus completo. Al graficar la densidad 2D real sin esa asunción (histograma 2D de 200×200 bins, sin asumir forma ni centro de antemano), la zona de menor densidad real del mapa queda centrada en **(-2.91, -1.40)** — un punto distinto, más de 3 unidades a la izquierda y abajo del centroide del corpus. El círculo de la Parte 1 (r=1.80 alrededor de (0.09, 0.11)) solo alcanzaba a cubrir el borde derecho de esta zona; el grueso de la zona de baja densidad real quedó fuera de ese análisis.

**Lección**: "el centro geométrico del corpus" y "el centro de un hueco visible en el mapa" son dos puntos distintos sin ninguna razón para coincidir, y no hay que asumir que coinciden. La Parte 1 lo asumió sin verificar; esta parte lo corrige detectando la forma directamente de los datos.

## Metodología (sin asumir forma ni centro)

Script: `pipeline/analizar_hueco_izquierdo.py`.

1. Grilla 2D de conteo (200×200 bins) sobre el layout completo.
2. "Ocupado" = celda con ≥3 puntos. "Hueco" = celda no ocupada que queda **completamente encerrada** por celdas ocupadas (`scipy.ndimage.binary_fill_holes` rellena el contorno exterior; la diferencia contra el mapa de ocupación original aísla los huecos internos reales, cualquiera sea su forma — no se asume círculo, elipse, ni ninguna otra geometría).
3. Componentes conexas (`scipy.ndimage.label`) de esos huecos. Se encontraron **39 componentes**; el mayor tiene **135 celdas**, el segundo apenas 14 — el hueco grande domina claramente sobre cualquier otro.
4. Núcleo estricto = esas 135 celdas (densidad casi cero por definición). Zona ampliada = dilatación binaria fija (5 celdas) del núcleo, para tener una muestra con significancia estadística al caracterizar composición.

## Resultados

**Forma y ubicación**: núcleo estricto de 135 celdas, bounding box `x∈[-5.49,-0.46], y∈[-3.11,0.34]`, centroide `(-2.91,-1.40)`. Forma **irregular/alargada** (verificado con el contorno real en la gráfica, no un círculo) — área del bounding box ≈17.4 unidades², más grande que el círculo completo (área≈10.2) que cubría el hueco de la Parte 1. Zona ampliada (dilatación +5 celdas): bbox `x∈[-6.82,0.87], y∈[-4.33,1.57]`, **7,640 tesis (1.25% del corpus)** — 3x más puntos que la zona ampliada de la Parte 1 (2,509, 0.41%).

**Composición — notablemente distinta de la Parte 1**:
- **Ruido: 46.2%, por debajo del 67.2% global** (en la Parte 1 el ruido estaba prácticamente igual al global). Esta zona tiene *menos* ruido que el promedio del mapa — la mayoría de lo que hay ahí son tesis con cluster real asignado, no dispersión sin tema.
- **Un cluster domina con fuerza real**: cluster 7 ("exploración sanitaria · sanitaria · municipio · médico social") = **30.4%** de la zona, 2,322 tesis — un cluster grande y coherente, no un fragmento.
- Le siguen cluster 474 ("rata · hipocampo · núcleo · neuronas · receptores · gaba", neurociencia) 3.6%, cluster 16 (el mismo "reforzamiento/conducta" que ya apareció en la Parte 1) 3.4%, cluster 8 ("servicio social realizado", formato de tesis de servicio social) 3.4%, cluster 472 ("memoria · corteza insular · condicionamiento", neurociencia) 2.9%, y una cola de clusters médicos pequeños (índices de laboratorio, diabetes, síntesis de compuestos).
- **Área administrativa: dominado por completo por Área 2** (Biológicas y de la Salud) — **84.4% de la zona vs. 40.4% global, enriquecimiento 2.09x**. Las otras tres áreas están *sub*-representadas (Área 1: 0.36x, Área 3: 0.15x, Área 4: 0.20x) — el patrón opuesto al de la Parte 1, que no mostraba un área dominante tan marcada.
- Títulos duplicados: 7.1% vs. 3.5% del resto — elevado, pero menos extremo que la Parte 1 (8.8%).
- **Muestra de títulos del núcleo estricto** (los 66 que caen en las celdas de densidad casi cero): *"cociente proteína"*, *"índice PACO2"*, *"status thymo lymphaticus"*, *"el índice PCR"*, *"modificación del índice neutrófilos"*, *"correlación del índice linfocitos CD4"* — un patrón **muy distinto y mucho más coherente** que el de la Parte 1: casi todos son títulos cortos de **índices/cocientes de laboratorio clínico** ("el índice X", "correlación de Y"), no una mezcla heterogénea de disciplinas sin relación.

## Veredicto

**Tampoco es evidencia de un vacío real de conocimiento — pero el mecanismo es distinto al de la Parte 1, y la evidencia en contra es aquí todavía más clara:**

1. El ruido está **por debajo** del promedio global (46.2% vs 67.2%), no igual ni por encima — lo opuesto de lo que se esperaría si esta fuera una zona "vacía" de contenido clusterizable.
2. Lo que hay ahí es abrumadoramente un solo cluster grande y real (30.4% en un solo cluster de 2,322 tesis) más un puñado de otros clusters reales de neurociencia/medicina — presencia sustancial, no ausencia.
3. El núcleo estricto (las 66 tesis en celdas de densidad casi cero) tiene un patrón textual **coherente y explicable**: títulos de índices/cocientes clínicos, un formato de titulación breve y estandarizado común en medicina de laboratorio, que comparte muy poco vocabulario específico entre sí pese a pertenecer al mismo campo amplio — exactamente el tipo de título que un modelo de embeddings basado en texto tiene dificultad para anclar con fuerza a un tema específico.

**Interpretación del mecanismo**: a diferencia de la Parte 1 (un atractor de títulos genéricos cruzando *muchas disciplinas distintas*), este hueco es una **zona fronteriza entre varios clusters reales, grandes y bien definidos, todos del mismo campo amplio (Área 2 — ciencias biológicas y de la salud)** — exploración sanitaria, neurociencia (dos clusters distintos: hipocampo/neuronas y memoria/corteza insular), conducta/reforzamiento, servicio social. Estos temas están relacionados por área pero son claramente distintos entre sí; sus títulos comparten un registro breve/técnico similar sin compartir vocabulario específico suficiente para que el clustering los una, y tampoco son tan distintos como para que PaCMAP los separe con un margen amplio — quedan "empujándose" unos a otros con un vacío delgado en el medio. Es la firma de **campos vecinos y relacionados, no de un campo ausente**.

## Visualización

`docs/evidencia_visual/12_hueco_izquierdo_composicion.png` (script: `pipeline/graficar_hueco_izquierdo.py`). Dos paneles: localizador (mapa completo, contorno rojo con la **forma real** del hueco — no un círculo, se dibuja con `ax.contour` sobre la máscara booleana de la componente conexa) + zoom coloreado por los 3 clusters reales más grandes que rodean el hueco (azul=exploración sanitaria, naranja=rata/hipocampo, verde=reforzamiento/conducta) más ruido/otros como contexto neutro. La gráfica muestra visualmente lo que dice el veredicto: el hueco es literalmente el espacio delgado donde esos tres clusters (y más) se tocan sin fundirse.

**Para recrear (análisis + gráfica)**:
```
python pipeline/analizar_hueco_izquierdo.py
python pipeline/graficar_hueco_izquierdo.py
```
Requiere `layout_pacmap2d.parquet`, `clusters_hdbscan.parquet`, `cluster_topics_ctfidf.parquet` y `data/public/data_unam.parquet`, todos ya presentes.

## Nota metodológica para cualquier hueco futuro que se investigue

**No asumir simetría radial ni centrar el análisis en el centroide del corpus sin verificar primero contra la densidad 2D real.** La Parte 1 lo hizo y subestimó el hueco real. El método correcto, usado aquí en la Parte 2, es agnóstico a la forma: detectar componentes conexas de baja densidad sobre una grilla 2D (`scipy.ndimage.binary_fill_holes` + `label`), sin asumir dónde está el centro ni qué forma tiene, y solo después caracterizar lo que se encontró.
