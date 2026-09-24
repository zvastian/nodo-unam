# Problema: calibración del paso de clustering (HDBSCAN) del atlas semántico — pido diagnóstico externo

_Escrito 2026-09-21 para que otra IA revise el razonamiento y la solución propuesta. Contexto completo desde cero abajo, no asume que se leyó nada de la conversación previa._

## 1. Qué es el proyecto

NODO UNAM: plataforma que explora 609,156 tesis de la UNAM (1873–2026). Una de sus features centrales es un "atlas semántico": un mapa 2D donde cada tesis es un punto, agrupado por similitud temática (embeddings de su título), navegable en niveles macro/meso/micro. Existía una versión anterior (muestra de 50k tesis, modelo de embeddings MiniLM, clustering con Leiden sobre un grafo FAISS, reducción a 2D con UMAP) que se decidió reconstruir desde cero sobre el corpus completo (609,156) con un modelo de embeddings mejor.

## 2. Decisiones ya tomadas antes de este problema (no están en debate)

- **Modelo de embeddings**: `intfloat/multilingual-e5-large` (1024 dimensiones), reemplaza al MiniLM viejo (384 dim). Ya generado y verificado: `embeddings_full_e5large.npy` (609,154 × 1024, normas=1.0, float32).
- **Texto embebido**: solo el título de la tesis (no se concatena programa/nivel/área/plantel — decisión de producto explícita, para no sesgar el clustering hacia categorías ya existentes como filtro).
- **Arquitectura de clustering**: se decidió migrar de Leiden (manual, requería "correr varias veces y curar a mano" la jerarquía macro/meso/micro) a un pipeline estilo **BERTopic**: reducción de dimensionalidad → **HDBSCAN** (clustering con jerarquía nativa, maneja ruido/outliers sin forzarlos a un cluster) → **c-TF-IDF** (etiquetas automáticas de tema por cluster). Para la reducción a 2D específicamente para visualización se decidió usar **PaCMAP** en vez de UMAP (mejor preservación de estructura global entre macroclusters). Esta decisión está documentada como ADR-0013 (estado: Aceptado).
- **Plataforma de cómputo**: correr en **Kaggle Notebooks** (no local). La máquina local tiene 16.6GB RAM total, ~9.4GB libres en un momento normal — insuficiente con margen para 609,154 puntos × 1024 dim. Además hubo un incidente real: correr localmente con paralelismo (`core_dist_n_jobs=-1`, 8 workers) hizo que la RAM libre bajara de 7.7GB a 2.9GB en 1 hora sin terminar, porque Windows no tiene `fork()` (solo `spawn`) y cada worker duplica su copia completa de los datos. Kaggle (Linux, `fork()` real, sin duplicación de memoria, ~30GB RAM en sesión sin GPU) resuelve ese problema de raíz. Se decidió explícitamente **no usar GPU** en Kaggle para este paso — HDBSCAN y la reducción de dimensionalidad (PCA o PaCMAP) son CPU-only, no usan CUDA; activar el acelerador GPU de Kaggle no ayuda en nada aquí y solo gastaría la cuota semanal de 30h de GPU (que sí hace falta para el paso de generación de embeddings, que usa `sentence-transformers`).

## 3. El paso concreto que se está ejecutando ahora mismo

`pipeline/clustering_hdbscan.py`: toma los embeddings (609,154 × 1024), los reduce de dimensionalidad, corre HDBSCAN sobre la versión reducida, guarda los cluster_id por tesis + el árbol condensado de HDBSCAN (fuente de la jerarquía macro/meso/micro) + el modelo de reducción de dimensionalidad ajustado.

**Por qué se reduce dimensionalidad antes de HDBSCAN** (no es negociable, es práctica estándar): correr HDBSCAN directo sobre 1024 dimensiones es inviable por la maldición de la dimensionalidad — las distancias dejan de ser informativas y el costo computacional/memoria se dispara. Se reduce primero a una dimensión moderada (típicamente 10-50 en la literatura) y sobre **eso** se clusteriza. La reducción a 2D para visualización (PaCMAP, ya decidida) es un paso completamente aparte, para mostrar en pantalla, no para alimentar el clustering.

**Parámetros de HDBSCAN usados en todas las pruebas**: `min_cluster_size=40`, `min_samples=10`, `cluster_selection_method='eom'`.

## 4. Cronología de pruebas y obstáculos (en orden)

### 4.1 Smoke test local, muestra de 30,000 tesis, PCA a 50 dimensiones
Resultado: 3 clusters encontrados, 84% de las tesis sin cluster ("ruido"). Se interpretó como posible artefacto de un subsample muy chico (5% del corpus) rompiendo la densidad local real que existiría en el corpus completo — no se usó para calibrar nada, solo confirmó que el código corre sin errores.

### 4.2 Migración a Kaggle
Varios obstáculos operativos, no conceptuales:
- Pegar código multilínea en el editor de celdas de Kaggle corrompe la indentación (el auto-indent del editor tipo CodeMirror se dispara en cada salto de línea del pegado). Se resolvió subiendo el script `.py` como archivo dentro del dataset de Kaggle y ejecutándolo con `exec(open(path).read())` en vez de pegarlo como texto.
- Se asumió erróneamente que `hdbscan` no viene preinstalado en la imagen base de Kaggle y se pidió `!pip install hdbscan==0.8.44` con versión fija — en realidad Kaggle SI trae hdbscan preinstalado (0.8.42), y fijar una versión distinta disparó una recompilación desde código fuente de las extensiones Cython/C que tardó minutos sin necesidad. Corregido: no instalar nada, usar la versión preinstalada.

### 4.3 Smoke test en Kaggle, muestra de 100,000 tesis, PCA a 50 dimensiones (IncrementalPCA)
Resultado:
```
Total tesis: 100,000
Clusters encontrados: 3
Ruido (sin cluster): 57,458 (57.5%)
Tamaños de cluster: 43, 58, 42441  (uno gigante + dos minúsculos, pegados al piso min_cluster_size=40)
Varianza explicada acumulada por el PCA: 0.435 (43.5%)
Probabilidad media de asignación (excl. ruido): 0.978
Tiempo del fit de HDBSCAN: 377.9s (~6.3 min)
```
Este resultado, con una muestra 3x más grande y más representativa que el smoke local (16% del corpus, no 5%), repite el mismo patrón cualitativo: pocos clusters, uno gigante amorfo, mayoría de ruido. Ya no se puede atribuir solo a que el subsample es chico — hay una señal real de mal calibrado.

**Mi hipótesis en ese momento**: el PCA solo retiene 43.5% de la varianza en 50 dimensiones — se está perdiendo más de la mitad de la información antes de clusterizar, lo cual podría explicar que HDBSCAN no logre separar temas reales (todo se ve parecido tras perder tanta señal) y que el resto caiga como ruido.

### 4.4 Segundo smoke test en Kaggle, mismos 100,000 (mismo seed=42, comparable), PCA a 150 dimensiones
Se subió `PCA_COMPONENTS` de 50 a 150 para retener más varianza antes de clusterizar.

Resultado del PCA: varianza explicada subió de 0.435 a **0.684** (68.4%) — mejora real en fidelidad de la reducción.

Pero el fit de HDBSCAN **tardó más de 45 minutos** (vs 6.3 min a 50 dimensiones) sobre los mismos 100,000 puntos, sin haber terminado cuando se decidió cancelarlo. No llegó a imprimir el diagnóstico final.

## 5. Mi diagnóstico del punto 4.4 (esto es lo que pido que revisen)

Interpreté el salto de 6.3 min → 45+ min (sin terminar) al subir de 50 a 150 dimensiones como **no explicable por una desaceleración lineal** (3x más dimensiones no debería dar >7x más tiempo, y sigue sin terminar). Mi hipótesis: las estructuras de búsqueda de vecinos que usa HDBSCAN internamente para calcular "core distances" (KD-tree / ball-tree) dejan de ser eficientes por encima de aproximadamente 20-30 dimensiones — el costo se acerca a fuerza bruta, lo cual degrada el tiempo de forma no lineal, no proporcional al número de dimensiones.

De ahí concluí que **subir la dimensión del PCA para retener más varianza y subir la dimensión objetivo del reductor son objetivos en tensión, no la misma perilla**: más varianza retenida (bueno para la calidad del clustering) requiere más dimensiones (malo para el tiempo de cómputo de HDBSCAN, de forma no lineal).

## 6. Mi solución propuesta (implementada parcialmente, SIN probar todavía)

En vez de seguir subiendo la dimensión de un reductor **lineal** (PCA) para compensar la pérdida de fidelidad, propuse cambiar a un reductor **no lineal que preserva estructura de vecindarios** (no solo varianza global) apuntando a una dimensión objetivo **baja** (10-15, no 50-150), donde los árboles de HDBSCAN siguen siendo eficientes. La herramienta elegida es **PaCMAP**, porque el proyecto ya la había adoptado (ADR-0013) para la reducción a 2D — reutilizar la misma librería para el paso previo a clustering es consistente con esa decisión y es, de hecho, más cercano al pipeline estándar de BERTopic (que usa UMAP, un reductor no lineal similar, para este mismo paso — el proyecto ya había optado por PaCMAP sobre UMAP en general).

Cambios hechos en `pipeline/clustering_hdbscan.py` (código escrito, **NO ejecutado ni verificado todavía**):
- Nueva env var `REDUCTION_METHOD` = `"pca"` (default, comportamiento original sin cambios) o `"pacmap"`.
- Nueva función `reduce_dimensions_pacmap()`: usa `pacmap.PaCMAP(n_components=PCA_COMPONENTS, random_state=SAMPLE_SEED).fit_transform(X)` sobre el arreglo materializado en memoria (PaCMAP no soporta ajuste incremental por lotes como `IncrementalPCA.partial_fit`, a diferencia del PCA que sí se hace por lotes con `mmap` por restricciones de RAM local — en Kaggle esto no debería ser problema, hay RAM de sobra).
- `reduce_dimensions()` ahora despacha a PCA o PaCMAP según la env var.
- Nombres de archivo de salida ahora incluyen el método y la dimensión (`embeddings_pacmap15.npy`, `pacmap_model.joblib`) en vez de estar hardcodeados a "pca50".
- Documentación en el docstring del script actualizada con instrucciones para instalar `pacmap==0.9.1` en Kaggle (no viene preinstalado, a diferencia de hdbscan) y con la narrativa completa del incidente de los 45 minutos.

**Esto no se ha corrido todavía.** No sé si PaCMAP a 10-15 dimensiones sobre 100k (o 609k) puntos de 1024 dim va a terminar en un tiempo razonable, ni si el resultado de clustering va a mejorar (menos ruido, clusters de tamaño más razonable, sin el "blob gigante").

## 7. Lo que NO he verificado / dudas abiertas para el diagnóstico externo

1. **¿Es correcto el diagnóstico de "degradación de KD-tree por encima de ~20-30 dimensiones" como causa del salto de 6.3 min a 45+ min?** Es mi hipótesis, no la verifiqué con profiling real (no inspeccioné qué fase interna de `hdbscan.HDBSCAN.fit()` es la que se volvió lenta, ni si `core_dist_n_jobs=-1` seguía paralelizando bien a 150 dimensiones).
2. **¿PaCMAP es la herramienta correcta para este paso, o hay algo más estándar/probado en pipelines BERTopic-like?** Sé que BERTopic usa UMAP por defecto para este paso exacto (no PCA), y que el proyecto ya adoptó PaCMAP como alternativa a UMAP para la visualización 2D — pero no verifiqué si PaCMAP es una elección tan probada como UMAP específicamente como *preprocesamiento para clustering* (a diferencia de para visualización, que es su uso más común y para el que sí hay evidencia dentro del proyecto).
3. **¿La dimensión objetivo recomendada (10-15) es razonable para 609k puntos de este dominio (títulos de tesis), o debería ajustarse?**
4. **¿El patrón "un cluster gigante (42%) + dos minúsculos + 57.5% ruido" tiene otras explicaciones plausibles que no exploré** — por ejemplo, `min_cluster_size=40` / `min_samples=10` mal calibrados para este tamaño de corpus independientemente del reductor, la métrica de distancia (euclidiana sobre embeddings normalizados, no coseno explícito — aunque son equivalentes salvo un factor monótono cuando los vectores están normalizados a norma 1, lo cual sí es el caso aquí), o algún problema en cómo se construye el texto embebido que no he considerado.
5. **¿Vale la pena correr PaCMAP con `apply_pca=True` (default de la librería, que internamente hace un PCA rápido antes de su propio pipeline) o desactivarlo, dado que ya se detectó que PCA solo captura 43-68% de la varianza en este dataset?** No investigué qué hace exactamente ese parámetro interno de PaCMAP ni si interactúa mal con el hallazgo del punto anterior.
6. **Costo de iteración**: cada prueba (aunque sea con 100k, no el corpus completo) ya tomó entre 6 y 45+ minutos solo en el paso de clustering, sin contar el tiempo de lectura/PCA previo. Si PaCMAP en 609k también resulta lento, no tengo todavía un plan B claro más allá de "seguir bajando la dimensión objetivo".

## 8. Qué necesito del diagnóstico

Evaluar si el razonamiento de las secciones 5 y 6 es sólido, señalar si hay un enfoque mejor establecido en la literatura/práctica para "reducir dimensionalidad de embeddings de texto antes de HDBSCAN a escala de cientos de miles de puntos" que no estoy considerando, y idealmente dar una recomendación concreta de parámetros/herramienta antes de gastar otra corrida de Kaggle (cada iteración cuesta tiempo de sesión real, aunque no cuota de GPU).
