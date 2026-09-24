# Solución: calibración del clustering (HDBSCAN) del atlas semántico

_Escrito 2026-09-21 como respuesta a `problem.md`. Fuentes: `problem.md` y `development.md`._

## 0. Estado de implementación (actualizado 2026-09-21, misma sesión)

Ejecutado sobre el código y los datos reales (no solo el análisis de abajo, que queda como quedó escrito originalmente):

- ✅ **Prefijo de e5 verificado**: `pipeline/generar_embeddings_full_e5.py` sí aplica `"query: "` a cada título. No hace falta regenerar embeddings. (Resuelve la duda **[verificar]** de la sección 4.1.)
- ✅ **2 filas faltantes explicadas**: son las 2 tesis con título vacío, filtradas a propósito en ese mismo script. No es un desalineado. (Resuelve la duda de la sección 4.5.)
- ✅ **Duplicados de título cuantificados**: 7,449 títulos se repiten (21,465 filas, 3.5% del corpus; peor caso "notas al programa" ×292). Real pero secundario — no se implementó deduplicación porque `embeddings_meta.parquet` no guarda `titulo` hoy; requeriría tocar `generar_embeddings_full_e5.py` primero. Queda pendiente, no bloqueante.
- ✅ **`pipeline/clustering_hdbscan.py` modificado**: `REDUCTION_METHOD` default pasó de `pca` a `umap` (`min_dist=0.0`, `metric="cosine"`, 5 dimensiones); `MIN_CLUSTER_SIZE`/`MIN_SAMPLES` suben de 40/10 a 150/5 como punto de partida; se agregó `REDUCED_EMBEDDINGS_PATH` para cachear la reducción y no repetirla en cada barrido de HDBSCAN. PCA y PaCMAP se mantienen como opciones, no como default. Compila sin errores de sintaxis (`py_compile`); **no se corrió** (requiere `umap-learn`/`hdbscan`, deliberadamente no instalados local por el incidente de RAM ya documentado).
- ✅ **`development.md` actualizado**: la entrada contradictoria sobre el texto embebido quedó tachada y marcada obsoleta; la nota técnica de "PCA a 50d" se actualizó con el diagnóstico completo; se agregó entrada al changelog.
- ✅ **No hizo falta ADR nuevo**: releyendo ADR-0013, ya preveía UMAP para este paso ("posiblemente tras reducción UMAP") — la implementación se había desviado hacia PCA y luego PaCMAP sin volver a chequear esa decisión. Se corrigió el código para alinearlo con lo ya decidido, en vez de registrar una decisión nueva.
- ⬜ **Pendiente, requiere Kaggle**: correr el smoke test de 100k con `REDUCTION_METHOD=umap` para confirmar tiempo y calidad antes del corpus completo. Nada de esto se ha validado con una corrida real todavía.

El resto de este documento es el análisis original, sin editar.

## 1. Resumen ejecutivo

- **Causa principal del mal resultado: el reductor (PCA), no HDBSCAN ni el tamaño de la muestra.** PCA preserva varianza global, pero HDBSCAN necesita densidad local. Los embeddings de e5 tras PCA quedan casi uniformes, lo que produce el patrón observado: un bloque gigante, clusters diminutos pegados a `min_cluster_size` y mucho ruido. Más dimensiones de PCA no arreglan esto; solo lo hacen más lento.
- **La propuesta de pasar a un reductor no lineal de baja dimensión es correcta en dirección.** La elección de PaCMAP para este paso no lo es: la herramienta probada es **UMAP con `min_dist=0.0`**, que es exactamente la configuración que BERTopic usa por defecto.
- **La premisa "HDBSCAN y la reducción son solo CPU" es falsa.** RAPIDS cuML trae UMAP y HDBSCAN en GPU. Además, el paso que justificaba reservar la cuota de GPU (generar embeddings) ya terminó.
- **Hay dos posibles causas de datos no exploradas** que deben revisarse antes de gastar otra corrida: el prefijo obligatorio de e5 y los títulos duplicados.

## 2. Evaluación del razonamiento de `problem.md`

### Sección 5: lentitud a 150 dimensiones. Correcta, pero secundaria

El diagnóstico es sólido. Los árboles KD/ball que usa `hdbscan` para vecinos degradan hacia fuerza bruta por encima de ~20-30 dimensiones, así que el costo crece de forma no lineal. Además:

- `core_dist_n_jobs` solo paraleliza el cálculo de core distances. La construcción del árbol de expansión mínima (Borůvka/Prim) es mayormente mono-hilo, así que en alta dimensión el paralelismo ayuda poco.
- La "tensión" entre varianza retenida y velocidad es real **solo mientras el reductor sea PCA**. Con un reductor que preserva vecindarios, 5-10 dimensiones bastan y la tensión desaparece. La varianza explicada de PCA no es la métrica relevante para clustering por densidad.

### Sección 6: PaCMAP como reductor previo. Dirección correcta, herramienta equivocada

- **PaCMAP está diseñado y validado para visualización (2D/3D).** Sus pares "mid-near" y "further" priorizan la disposición global, no compactar clusters densos. Hay poca evidencia publicada de su uso como preprocesamiento de HDBSCAN a 10-15 dimensiones.
- **UMAP con `min_dist=0.0` empaca explícitamente los puntos de un mismo vecindario**, que es lo que HDBSCAN necesita. Es el estándar de facto (BERTopic, Top2Vec, la documentación de `hdbscan`).
- **ADR-0013 no obliga a usar PaCMAP aquí.** Esa decisión trata del layout 2D para visualización. El reductor previo al clustering es otro paso con otro objetivo. Usar UMAP ahí es compatible con ADR-0013, que sigue vigente para el mapa. Registrarlo como ADR nuevo (ver sección 6).

## 3. Respuestas a las dudas abiertas (sección 7 de `problem.md`)

| # | Duda | Respuesta |
|---|---|---|
| 1 | ¿KD-tree explica 6.3 min → 45+ min? | Sí, es la explicación más probable, sumada a que el MST no paraleliza. No hace falta perfilar: el cambio de reductor elimina el problema. |
| 2 | ¿PaCMAP es la herramienta correcta? | No para este paso. Usar UMAP (`min_dist=0.0`, `metric="cosine"`). PaCMAP se queda para el 2D. |
| 3 | ¿10-15 dimensiones es razonable? | Bajar a **5** (default de BERTopic). Probar 10 como variante. Por encima de ~15 no hay ganancia y vuelve la lentitud. |
| 4 | ¿Otras explicaciones del blob + ruido? | Sí, varias. Ver sección 4. La métrica euclidiana sobre vectores normalizados no es el problema. |
| 5 | ¿`apply_pca=True` en PaCMAP? | Ese flag reduce a 100 dimensiones con PCA solo para acelerar la búsqueda de vecinos. Es irrelevante si se usa UMAP. Para el 2D de visualización puede dejarse en su default. |
| 6 | Plan B si todo es lento | cuML en GPU (sección 5). En CPU, reducir una vez y guardar el arreglo; calibrar HDBSCAN sobre ese arreglo es rápido en 5 dimensiones. |

## 4. Otras causas del patrón "blob + ruido" (duda 4)

1. **Prefijo de e5 [verificar].** `multilingual-e5-large` espera que cada texto empiece con `"query: "` o `"passage: "`. Para clustering simétrico se usa `"query: "` en todos. Sin prefijo, la calidad de los embeddings cae y la similitud entre textos se comprime, lo que alimenta el blob. Revisar `pipeline/generar_embeddings_full_e5.py`. Si falta el prefijo, hay que regenerar los embeddings antes de calibrar nada.
2. **Títulos duplicados o genéricos.** Títulos repetidos miles de veces ("Informe de servicio social", "Memoria de desempeño profesional", etc.) crean picos de densidad artificiales que distorsionan las core distances. Solución: clusterizar sobre títulos únicos y asignar el cluster a cada tesis con ese título.
3. **Anisotropía de e5.** Los embeddings de e5 tienen similitud coseno alta entre casi cualquier par (rango comprimido). UMAP con métrica coseno sobre vecinos lo tolera bien; PCA no.
4. **Parámetros de HDBSCAN.** `eom` tiende a elegir pocos clusters grandes cuando la jerarquía es plana; `min_samples=10` sube el ruido. Son ajustes finos: calibrarlos **después** de cambiar el reductor, no antes.
5. **Filas faltantes.** Los embeddings tienen 609,154 filas y el corpus 609,156. Confirmar que `embeddings_meta.parquet` alinea por `thesis_id` y no por posición, y documentar qué 2 tesis faltan y por qué.

## 5. Recomendación concreta

### Configuración inicial

```python
# Reductor previo al clustering (no es el mapa 2D)
umap.UMAP(
    n_neighbors=15,
    n_components=5,
    min_dist=0.0,
    metric="cosine",
    random_state=42,
    low_memory=True,
)

# Clustering sobre la salida de 5 dimensiones (euclidiana, default)
hdbscan.HDBSCAN(
    min_cluster_size=150,
    min_samples=5,
    cluster_selection_method="eom",
    prediction_data=True,
)
```

### Plataforma

- **Opción A, recomendada: cuML en GPU de Kaggle.** `cuml.manifold.UMAP` y `cuml.cluster.HDBSCAN` procesan 609k puntos en minutos. La cuota de GPU ya no compite con los embeddings, que están generados. **[verificar]** que la instalación de cuML coincida con la versión de CUDA de la imagen de Kaggle, y que el HDBSCAN de cuML exponga `condensed_tree_` como lo necesita la jerarquía macro/meso/micro. Si no lo expone, usar cuML solo para UMAP y el `hdbscan` de CPU sobre el arreglo de 5 dimensiones, que es rápido.
- **Opción B: CPU en Kaggle.** `umap-learn` sobre 609k × 1024 es viable en una sesión (orden de decenas de minutos, **[verificar]**). HDBSCAN sobre 5 dimensiones con árboles eficientes debería tardar minutos, no horas.

### Plan de corridas (minimiza sesiones de Kaggle)

1. **Chequeos previos, locales y baratos:** prefijo de e5, conteo de títulos duplicados, alineación por `thesis_id` de las 2 filas faltantes.
2. **Corrida 1, reducción:** deduplicar títulos, ajustar UMAP sobre los únicos del corpus completo, guardar `embeddings_umap5.npy` + mapeo título→tesis. Se hace **una sola vez**.
3. **Corrida 2, barrido de HDBSCAN** sobre el arreglo guardado:
   - `min_cluster_size` ∈ {50, 100, 200, 400}
   - `min_samples` ∈ {5, 10}
   - `cluster_selection_method` ∈ {eom, leaf}
4. **Criterios de aceptación** para elegir configuración:
   - Ruido entre ~15% y 35% (no perseguir 0%; el ruido se reasigna después).
   - Ningún cluster con más de ~5-10% del corpus.
   - Distribución de tamaños sin cola pegada al piso de `min_cluster_size`.
   - Inspección manual de 10-20 clusters con sus etiquetas c-TF-IDF: ¿son temas coherentes?
5. **Reasignar ruido** con `hdbscan.approximate_predict` / membresía suave, o la estrategia de `reduce_outliers` de BERTopic, según lo que necesite el producto.

### Cambios de código pendientes en `pipeline/clustering_hdbscan.py`

- Añadir `"umap"` (y opcionalmente `"cuml_umap"`) a `REDUCTION_METHOD` y hacerlo el default. Mantener `"pca"` solo como referencia.
- Sacar `reduce_dimensions_pacmap()` del camino de clustering; PaCMAP se usa en el paso 3 (layout 2D).
- Separar reducción y clustering en dos etapas con artefacto intermedio en disco, para que el barrido no repita la reducción.
- Registrar por corrida: parámetros, % de ruido, número de clusters, tamaño del mayor cluster y tiempo por fase.

## 6. Documentación a actualizar

- **ADR nuevo (ADR-0014):** "UMAP (`min_dist=0`) como reductor previo a HDBSCAN; PaCMAP se mantiene para el layout 2D (ADR-0013)". Citar el resultado del smoke test de PCA como contexto.
- **`development.md`, entradas obsoletas o contradictorias:**
  - La línea que dice que el texto embebido es `titulo_normalizado | programa | nivel | area | plantel` contradice la corrección de la misma sección (solo título). Marcarla como superada.
  - La nota técnica que dice "PCA a 50d antes de HDBSCAN" queda obsoleta.
  - La auditoría de Fase 1 todavía describe el pipeline con Leiden y UMAP sobre 50k.
  - Agregar al changelog el incidente de los 45 minutos a 150 dimensiones, con esta causa raíz.

## 7. Riesgos del proyecto fuera del clustering (de `development.md`)

Por prioridad, sin relación directa con el problema pero detectados en la lectura:

1. **El proyecto raíz no está en git.** Todo el pipeline y estos experimentos no tienen versiones. Es el riesgo más barato de eliminar.
2. **El historial LFS con nombres de autores no se ha purgado.** Poner el repo en privado no elimina clones ni forks existentes.
3. **ADR-0004 sigue sin ejecutarse.** Producción sirve datos con el hueco de scraping y todavía muestra autores.
4. **Demasiados frentes abiertos a la vez.** Kanban funciona con límite de trabajo en curso. Cerrar el atlas antes de abrir otro frente.
