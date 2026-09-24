# ADR-0013: Propuesta — migrar de FAISS+Leiden manual a estilo BERTopic (UMAP+HDBSCAN+c-TF-IDF)

- **Estado**: Aceptado (2026-09-21). Incluye también el cambio de UMAP a **PaCMAP** para la reducción a 2D (ver razonamiento en `development.md`, sesión 2026-09-21) — PaCMAP modela explícitamente pares "mid-near" (distancia intermedia) además de vecinos/lejanos, y usa una ponderación por etapas (global primero, local después) que UMAP no tiene — mejor preservación de la posición relativa entre macroclusters distantes, no solo la cohesión interna de cada uno.

## Contexto

Pipeline actual documentado en `nodo_unam.md`: embeddings → índice FAISS → grafo de similitud (mutual rank + score mínimo) → **Leiden** para clustering → jerarquía macro/meso/micro **curada a mano** porque Leiden a resolución 1.0 dio 9,515 clusters (demasiados) y no ofrece jerarquía nativa — hubo que re-correrlo con distintos parámetros y diseñar una "política editorial" manual para consolidar en macro/meso/micro.

Investigación (2026-09-21) sobre el estado del arte actual de clustering semántico de documentos encontró que **BERTopic** (embeddings → UMAP → HDBSCAN → c-TF-IDF) es hoy el pipeline estándar y activamente mantenido para este caso de uso exacto, con ventajas concretas frente al enfoque actual:

- **HDBSCAN** encuentra el número de clusters de la estructura real de los datos (no requiere adivinar un parámetro de resolución), tiene jerarquía nativa (se puede cortar el árbol de clustering en distintos niveles — reemplazaría el proceso manual de macro/meso/micro), y maneja "ruido" de forma nativa (una tesis que no encaja bien en ningún grupo se marca como tal, en vez de forzarse dentro del cluster menos malo, que es lo que hace Leiden).
- **c-TF-IDF** genera automáticamente una etiqueta de palabras clave por cluster (ej. "derecho · penal · delito · víctima") — hoy la identificación de un microcluster depende de mostrar "tesis representativas" (ejemplos), no de una etiqueta temática real.
- UMAP se mantiene (sigue siendo sólido); se evalúa PaCMAP como alternativa que preserva mejor la estructura global entre clusters distantes, sin urgencia de cambiarlo de inmediato.

## Decisión propuesta

Migrar el paso de clustering de Leiden (sobre grafo FAISS) a HDBSCAN (sobre los embeddings de e5-large, posiblemente tras reducción UMAP), y adoptar c-TF-IDF para generar etiquetas automáticas de tema por cluster en cada nivel de la jerarquía (macro/meso/micro).

## Consecuencias esperadas

- (+) Elimina el proceso manual de "correr Leiden varias veces y curar a mano" — la jerarquía sale de la estructura real de los datos.
- (+) Etiquetas de tema automáticas mejoran la exploración del atlas (un usuario ve "de qué trata" un cluster sin tener que leer tesis de ejemplo).
- (+) Manejo nativo de ruido/outliers — hoy esas tesis se fuerzan dentro de algún cluster igual.
- (-) Requiere reimplementar el paso de clustering (no es un cambio trivial de un parámetro).
- (-) HDBSCAN puede dejar una fracción de tesis como "ruido" (sin cluster asignado) — hay que decidir qué hacer con esas en la UI (¿una categoría "sin clasificar" visible, o se ocultan?).
- Pendiente de decisión del usuario antes de implementar: ¿se procede con esta migración ahora, como parte de la reconstrucción del atlas, o se mantiene Leiden por ahora y se revisita después?

**Fuentes de la investigación**: BERTopic pipeline (embedding → UMAP → HDBSCAN → c-TF-IDF) confirmado como estándar 2026 vía búsqueda directa; comparación UMAP/PaCMAP/TriMap sobre preservación de estructura local vs. global.
