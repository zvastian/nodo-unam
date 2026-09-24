"""Clustering del atlas semantico: PCA -> HDBSCAN sobre el corpus completo
(609,154 tesis, embeddings de intfloat/multilingual-e5-large, 1024-dim).

Reemplaza el proceso manual de Leiden (macro/meso/micro a mano) por la
jerarquia nativa de HDBSCAN (ver ADR-0013). Este script cubre el paso 1 de
"Proximos pasos concretos" en development.md -- SOLO clustering, no las
etiquetas c-TF-IDF (paso 2) ni la proyeccion 2D con PaCMAP (paso 3, script
aparte: son dos cosas distintas, PaCMAP es para visualizar, no para
alimentar el clustering).

Por que PCA antes de HDBSCAN: correr HDBSCAN directo sobre las 1024
dimensiones completas es la practica que se descarto a proposito (nota en
development.md, seccion "Decision tomada"). Se reduce primero a un
numero moderado de dimensiones (aqui 50, tipico 10-50) para que las
distancias en las que HDBSCAN basa la densidad sigan siendo significativas
(maldicion de la dimensionalidad) y para que el costo de memoria/computo
sea manejable.

Por que IncrementalPCA + mmap en vez de PCA normal: la maquina local tiene
16GB de RAM total y ya tenia ~11GB ocupados por otros procesos al momento
de escribir esto. Cargar el .npy completo (2.49GB) como arreglo denso y
correr SVD completo encima es el patron que mas facilmente lleva a un OOM
silencioso. Leyendo con mmap y ajustando la PCA en lotes (partial_fit) el
sistema operativo puede paginar el archivo bajo presion de memoria en vez
de que el proceso muera.

Decision 2026-09-21 (ver development.md, "Decision tomada"): correr en
**Kaggle**, no local. Motivo concreto, no solo el checklist generico del
doc: la corrida completa local con core_dist_n_jobs=-1 (8 workers, Windows
usa spawn no fork -- cada worker duplica su copia de los datos) se comio
la RAM libre de 7.7GB a 2.9GB en 1h sin terminar (incidente 2026-09-21,
ver Changelog). Con solo 16.6GB de RAM total en la maquina y ~9.4GB libres
en un momento normal, no hay margen para una corrida de 609,154 x 1024
que ademas construye un condensed tree. Kaggle da RAM conocida de
antemano (tipicamente ~30GB en sesion sin GPU) sin tener que degradar a
core_dist_n_jobs=1 (mono-hilo, mas lento) para evitar el mismo problema.

Como correrlo en Kaggle:
1. Crear un Kaggle Dataset nuevo subiendo `data/embeddings/embeddings_full_e5large.npy`
   (2.49GB) + `data/embeddings/embeddings_meta.parquet` -- son las salidas
   de generar_embeddings_full_e5.py, no el dataset de texto original.
2. Crear un Kaggle Notebook nuevo. **Accelerator: None/CPU** (Settings >
   Accelerator) -- HDBSCAN y PCA son CPU-only, activar GPU aqui solo
   resta cuota semanal de GPU sin ningun beneficio.
3. Agregar el dataset del paso 1 como input del notebook.
4. **No instalar hdbscan.** Corrección 2026-09-21: la imagen base de
   Kaggle SI trae hdbscan preinstalado (0.8.42 al momento de escribir
   esto, junto con scikit-learn/joblib). Forzar `pip install hdbscan==X`
   con version fija dispara una reinstalacion que compila las extensiones
   Cython/C desde cero (varios minutos, no segundos) en vez de usar la
   que ya esta lista. No hace falta, 0.8.42 sirve igual.
   `REDUCTION_METHOD=umap` (default actual) usa `umap-learn`, que
   normalmente tambien viene preinstalado en la imagen base de Kaggle --
   **verificar con `import umap` antes de instalar nada** (misma leccion
   del incidente de hdbscan: no asumir que falta sin comprobarlo). Si de
   verdad falta, `!pip install umap-learn`.
   Si en cambio vas a usar `REDUCTION_METHOD=pacmap` (solo tiene sentido
   para el paso 3 de layout 2D, no para este paso), esa si hace falta
   instalarla: `!pip install pacmap==0.9.1` (version verificada local) --
   no viene preinstalada en Kaggle.
5. Pegar este script en una celda. Ajustar env vars antes de importar
   (o exportarlas en una celda `!export` no funciona entre celdas en
   Kaggle -- usar `os.environ[...] = ...` en Python al inicio de la celda):
   - `SOURCE_DIR = /kaggle/input/<nombre-dataset>`
   - `OUTPUT_DIR = /kaggle/working`
   - `CORE_DIST_N_JOBS`: en Kaggle (Linux, fork real, sin la duplicacion
     de memoria de Windows/spawn) es seguro subirlo por encima de 1 --
     pero Kaggle da 4 vCPUs en sesion sin GPU, asi que `-1` (todos los
     cores) es razonable ahi, no hace falta el mono-hilo forzado que
     hizo falta local.
6. Correr. Al terminar, descargar `clusters_hdbscan.parquet`,
   `condensed_tree.parquet`, `embeddings_<metodo><n>.npy` (ej.
   `embeddings_umap5.npy`) y `<metodo>_model.joblib` desde
   `/kaggle/working/` -- van a `data/clustering/` local para que el
   resto del pipeline (c-TF-IDF, paso 2) los use igual que si hubiera
   corrido local.

Para calibrar MIN_CLUSTER_SIZE/MIN_SAMPLES sin repetir la reduccion en
cada intento (la reduccion es el paso caro, HDBSCAN sobre 5-10
dimensiones es rapido): correr una vez con REDUCTION_METHOD=umap sobre
el corpus completo, guardar `embeddings_umap5.npy`, y en corridas
siguientes apuntar `REDUCED_EMBEDDINGS_PATH` a ese archivo -- el script
lo carga directo y salta `reduce_dimensions()` por completo. Asi el
barrido de parametros de HDBSCAN (ver solution.md, seccion 5) itera
solo sobre el paso barato.

Antes de comprometer la corrida completa (609,154 filas, puede tardar):
correr primero con SAMPLE_N alto (ej. 100000-150000) para confirmar que
no crashea con las env vars de Kaggle y que el tiempo estimado cabe en la
sesion de 9h. **Aviso importante sobre el smoke test local ya hecho
(SAMPLE_N=30000, 2026-09-21)**: dio 84% de ruido y solo 3 clusters -- eso
NO es una señal de que min_cluster_size/min_samples esten mal calibrados.
Un subsample aleatorio de 30k sobre 609k rompe la densidad local que
existe en el corpus completo (los vecinos reales de una tesis rara vez
sobreviven un muestreo aleatorio de ~5%), asi que ese resultado no debe
usarse para ajustar parametros -- solo confirmo que el codigo corre sin
errores. La calibracion real de MIN_CLUSTER_SIZE/MIN_SAMPLES solo tiene
sentido mirando los diagnosticos de la corrida completa (o de un sample
mucho mas grande, no uno tan chico que destruye la estructura que se
busca medir).

Parametros de HDBSCAN expuestos por env var para iterar sin editar el
script (ver diagnosticos que imprime al final: numero de clusters, %
ruido, distribucion de tamanos -- eso es lo que hay que mirar para decidir
si min_cluster_size esta bien calibrado).

**Incidente 2026-09-21, smoke test Kaggle con PCA_COMPONENTS=150**: el fit
de HDBSCAN tardo mas de 45 minutos sobre apenas 100k puntos (vs 6.3 min a
50 componentes) -- no es una desaceleracion lineal esperable por 3x mas
dimensiones, es degradacion del KD-tree/ball-tree que usa HDBSCAN para
buscar vecinos: esas estructuras dejan de ser eficientes por encima de
~20-30 dimensiones y el costo se acerca a fuerza bruta. Subir
PCA_COMPONENTS para retener mas varianza (0.435 a 50d, 0.684 a 150d)
mejora la fidelidad de la reduccion pero **empeora** el tiempo de
clustering de forma no lineal -- son objetivos en tension, no la misma
perilla, **mientras el reductor sea PCA**.

**Diagnostico 2026-09-21 (ver solution.md): la causa real del bloque
gigante + 57.5% de ruido no era la varianza retenida por el PCA, era que
PCA preserva varianza GLOBAL, no densidad LOCAL -- y HDBSCAN clusteriza
por densidad local. Con PCA los embeddings de e5 quedan casi uniformes
en el espacio reducido sin importar cuantas dimensiones se retengan.**
Por eso el reductor default cambio a **UMAP** (`min_dist=0.0`,
`metric="cosine"`), la configuracion estandar de facto para este paso
exacto en pipelines estilo BERTopic/Top2Vec -- preserva vecindarios
(no varianza global) y funciona bien en 5-10 dimensiones, donde el
arbol de HDBSCAN sigue siendo eficiente. PaCMAP se evaluo tambien pero
se descarto para ESTE paso: esta disenado y validado para visualizacion
2D/3D (sus pares "mid-near" priorizan disposicion global, no compactar
clusters densos) -- se mantiene como estaba decidido en ADR-0013, pero
solo para el layout 2D de paso 3, no como preprocesamiento de HDBSCAN.
PCA se conserva como opcion legacy/referencia, no como default.

**Verificado 2026-09-21 contra generar_embeddings_full_e5.py y
data_unam.parquet, antes de cambiar el reductor:**
- Prefijo "query: " de e5: SI esta aplicado correctamente (linea 47-54
  de ese script). No hace falta regenerar embeddings.
- Las 2 filas de diferencia entre el corpus (609,156) y los embeddings
  (609,154) son exactamente las 2 tesis con titulo vacio, filtradas a
  proposito por ese mismo script (linea 71) -- no es un desalineado.
- Titulos duplicados: 7,449 titulos se repiten cubriendo 21,465 filas
  (3.5% del corpus) -- el peor caso es "notas al programa" (292 veces).
  Es real pero secundario: no explica un ~57% de ruido por si solo.
  `embeddings_meta.parquet` hoy NO guarda `titulo` (solo thesis_id/
  programa/nivel/area/plantel), asi que deduplicar por titulo antes de
  ajustar el reductor requeriria agregar esa columna en
  generar_embeddings_full_e5.py -- pendiente, no bloqueante para probar
  UMAP primero.

**Calibracion 2026-09-21 (ver smoke test 100k, tabla en development.md):
CLUSTER_SELECTION_METHOD default cambia de "eom" a "leaf".** `eom` colapsaba
99% del corpus en un solo cluster; `leaf` da granularidad razonable (87
clusters, 154-2,104 tesis en el smoke test) pero deja 64.2% del corpus como
ruido. En vez de seguir barriendo min_cluster_size/min_samples a ciegas
entre esos dos extremos (interpola entre "un blob" y "mucho ruido", no
encuentra un punto intermedio estable -- es una limitacion conocida de
cluster_selection_method, no un problema de calibracion fina), se agrega
**soft clustering** (`soft_reassign_noise()`, via
`hdbscan.all_points_membership_vectors`, requiere `prediction_data=True`
en el fit): para cada punto de ruido calcula su membership fraccional a
los clusters ya encontrados y lo reasigna si supera SOFT_CLUSTER_THRESHOLD
(default 0.1, punto de partida). Los puntos ya asignados por HDBSCAN no se
tocan. Aviso de costo: `all_points_membership_vectors` sobre 609,154 puntos
es un paso adicional no trivial (aparte del fit de HDBSCAN) -- presupuestar
tiempo extra en la sesion de Kaggle, y usar SAMPLE_N para medir el costo
real antes de comprometerse a la corrida completa. Desactivable con
SOFT_CLUSTERING=0 para comparar contra la asignacion dura o probar
CLUSTER_SELECTION_METHOD=eom sin pagar el costo extra.
"""
import os
import time
from pathlib import Path

import hdbscan
import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import IncrementalPCA

SOURCE_DIR = Path(os.getenv("SOURCE_DIR", "data/embeddings"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "data/clustering"))

EMBEDDINGS_PATH = SOURCE_DIR / "embeddings_full_e5large.npy"
META_PATH = SOURCE_DIR / "embeddings_meta.parquet"

# "umap" (default desde 2026-09-21, ver diagnostico arriba -- preserva
# vecindarios/densidad local, lo que HDBSCAN necesita), "pca" (legacy,
# preserva varianza global, es lo que producia el bloque gigante + 57.5%
# de ruido) o "pacmap" (queda para el layout 2D de paso 3, no recomendado
# como preprocesamiento de HDBSCAN -- ver diagnostico arriba).
REDUCTION_METHOD = os.getenv("REDUCTION_METHOD", "umap").lower()

# Dimension objetivo de la reduccion. Default depende del metodo: UMAP/
# PaCMAP preservan estructura desde dimensiones bajas (5-10 es tipico en
# BERTopic-like pipelines para UMAP); PCA es lineal y necesita mas
# dimensiones para retener varianza comparable (tipico 50), aunque eso
# no arregla el problema de fondo (ver diagnostico arriba). Override con
# PCA_COMPONENTS si se quiere otro valor para un barrido.
_DEFAULT_DIM = {"umap": "5", "pacmap": "15", "pca": "50"}.get(REDUCTION_METHOD, "50")
PCA_COMPONENTS = int(os.getenv("PCA_COMPONENTS", _DEFAULT_DIM))
PCA_BATCH_SIZE = int(os.getenv("PCA_BATCH_SIZE", "20000"))

# UMAP: min_dist=0.0 empaca los puntos de un mismo vecindario en vez de
# esparcirlos (bueno para clustering por densidad, malo para verse lindo
# en 2D -- por eso el layout de visualizacion usa PaCMAP, no esto).
# metric="cosine" porque los embeddings de e5 estan normalizados a norma
# 1 (equivalente a euclidiana salvo un factor monotono, pero coseno es
# la convencion documentada para este tipo de embeddings).
UMAP_N_NEIGHBORS = int(os.getenv("UMAP_N_NEIGHBORS", "15"))
UMAP_MIN_DIST = float(os.getenv("UMAP_MIN_DIST", "0.0"))
UMAP_METRIC = os.getenv("UMAP_METRIC", "cosine")

# Si se apunta a un .npy ya reducido (de una corrida anterior de
# reduce_dimensions), se carga directo y se salta la reduccion por
# completo -- para iterar MIN_CLUSTER_SIZE/MIN_SAMPLES sin repetir el
# paso caro. Ver instrucciones de Kaggle arriba.
REDUCED_EMBEDDINGS_PATH = os.getenv("REDUCED_EMBEDDINGS_PATH", "")

# Calibracion inicial recomendada 2026-09-21 (ver solution.md) tras el
# diagnostico del bloque gigante + 57.5% de ruido con min_cluster_size=40:
# subir el piso reduce la fragmentacion en clusters minusculos pegados al
# piso viejo. Sigue siendo punto de partida para un barrido, no un valor
# final -- calibrar mirando los diagnosticos que imprime este script.
MIN_CLUSTER_SIZE = int(os.getenv("MIN_CLUSTER_SIZE", "150"))
MIN_SAMPLES = int(os.getenv("MIN_SAMPLES", "5"))

# Default cambia de "eom" a "leaf" 2026-09-21 (ver smoke test 100k en
# development.md): eom colapsaba 99% del corpus en un solo cluster (busca
# el nodo mas "estable" del arbol condensado, que aqui resulto ser casi
# todo el dataset); leaf da granularidad util (87 clusters, 154-2,104
# tesis) pero deja 64.2% como ruido -- ese ruido se recupera abajo con
# soft clustering en vez de perseguirlo solo con hiperparametros de HDBSCAN.
CLUSTER_SELECTION_METHOD = os.getenv("CLUSTER_SELECTION_METHOD", "leaf")

# Soft clustering (ver hdbscan.all_points_membership_vectors): rescata
# puntos de ruido calculando su membership fraccional a cada cluster ya
# encontrado, en vez de dejarlos en -1 solo porque "leaf" es conservador
# asignando membresia dura. Requiere prediction_data=True en el fit.
# Desactivar con SOFT_CLUSTERING=0 para comparar contra el resultado duro
# (ej. al probar CLUSTER_SELECTION_METHOD=eom) sin pagar el costo extra.
SOFT_CLUSTERING = os.getenv("SOFT_CLUSTERING", "1") == "1"
# Umbral de probabilidad minima para aceptar la reasignacion de un punto
# de ruido a su cluster de mayor membership. Punto de partida conservador,
# no un valor final -- calibrar mirando cuanto ruido queda tras aplicarlo.
SOFT_CLUSTER_THRESHOLD = float(os.getenv("SOFT_CLUSTER_THRESHOLD", "0.1"))

# Windows no tiene fork(), solo spawn -- cada worker de joblib/loky reimporta
# el proceso completo y recibe su propia copia de los datos. Con
# core_dist_n_jobs=-1 (8 workers) esto hizo que la RAM subiera de 7.7GB a
# 2.9GB en 1h sin terminar (ver incidente 2026-09-21 en development.md).
# Default 1 = sin multiprocessing, mas lento por core pero sin duplicacion
# de memoria. Subir con cuidado y solo si sobra RAM de verdad.
CORE_DIST_N_JOBS = int(os.getenv("CORE_DIST_N_JOBS", "1"))

# Para smoke tests antes de comprometerse a la corrida completa (609,154
# filas): tomar una muestra aleatoria reproducible de SAMPLE_N filas.
# SAMPLE_N=0 (default) usa el corpus completo.
SAMPLE_N = int(os.getenv("SAMPLE_N", "0"))
SAMPLE_SEED = int(os.getenv("SAMPLE_SEED", "42"))


def reduce_dimensions_pca(X: np.ndarray) -> np.ndarray:
    print(f"PCA incremental: {X.shape[1]}d -> {PCA_COMPONENTS}d "
          f"(batch_size={PCA_BATCH_SIZE})")
    pca = IncrementalPCA(n_components=PCA_COMPONENTS, batch_size=PCA_BATCH_SIZE)

    n = X.shape[0]
    n_batches = (n + PCA_BATCH_SIZE - 1) // PCA_BATCH_SIZE
    t0 = time.time()
    for i, start in enumerate(range(0, n, PCA_BATCH_SIZE), start=1):
        end = min(start + PCA_BATCH_SIZE, n)
        pca.partial_fit(X[start:end])
        print(f"  fit lote {i}/{n_batches} ({end:,}/{n:,}) "
              f"[{time.time() - t0:.1f}s]", flush=True)
    print(f"  fit total: {time.time() - t0:.1f}s, "
          f"varianza explicada acumulada: {pca.explained_variance_ratio_.sum():.3f}",
          flush=True)

    t0 = time.time()
    out = np.empty((n, PCA_COMPONENTS), dtype="float32")
    for i, start in enumerate(range(0, n, PCA_BATCH_SIZE), start=1):
        end = min(start + PCA_BATCH_SIZE, n)
        out[start:end] = pca.transform(X[start:end]).astype("float32")
        print(f"  transform lote {i}/{n_batches} ({end:,}/{n:,}) "
              f"[{time.time() - t0:.1f}s]", flush=True)
    return out, pca


def reduce_dimensions_umap(X: np.ndarray) -> np.ndarray:
    import umap  # import tardio: no todos los entornos lo tienen instalado

    print(f"UMAP: {X.shape[1]}d -> {PCA_COMPONENTS}d "
          f"(n_neighbors={UMAP_N_NEIGHBORS}, min_dist={UMAP_MIN_DIST}, "
          f"metric={UMAP_METRIC!r}, sobre {X.shape[0]:,} puntos)", flush=True)
    reducer = umap.UMAP(
        n_neighbors=UMAP_N_NEIGHBORS,
        n_components=PCA_COMPONENTS,
        min_dist=UMAP_MIN_DIST,
        metric=UMAP_METRIC,
        random_state=SAMPLE_SEED,
        low_memory=True,
        verbose=True,
    )

    t0 = time.time()
    out = reducer.fit_transform(np.asarray(X, dtype="float32"))
    print(f"  fit_transform total: {time.time() - t0:.1f}s", flush=True)
    return out.astype("float32"), reducer


def reduce_dimensions_pacmap(X: np.ndarray) -> np.ndarray:
    import pacmap  # import tardio: no todos los entornos lo tienen instalado

    print(f"PaCMAP: {X.shape[1]}d -> {PCA_COMPONENTS}d "
          f"(sobre {X.shape[0]:,} puntos, sin batching -- PaCMAP no soporta "
          f"partial_fit como IncrementalPCA)", flush=True)
    reducer = pacmap.PaCMAP(n_components=PCA_COMPONENTS, random_state=SAMPLE_SEED)

    t0 = time.time()
    # PaCMAP espera un arreglo denso en memoria, no mmap -- ya viene
    # materializado (corpus completo o el subsample del smoke test).
    out = reducer.fit_transform(np.asarray(X, dtype="float32"))
    print(f"  fit_transform total: {time.time() - t0:.1f}s", flush=True)
    return out.astype("float32"), reducer


def reduce_dimensions(X: np.ndarray) -> np.ndarray:
    if REDUCTION_METHOD == "umap":
        return reduce_dimensions_umap(X)
    if REDUCTION_METHOD == "pacmap":
        return reduce_dimensions_pacmap(X)
    if REDUCTION_METHOD == "pca":
        return reduce_dimensions_pca(X)
    raise ValueError(f"REDUCTION_METHOD desconocido: {REDUCTION_METHOD!r} "
                      "(usar 'umap', 'pca' o 'pacmap')")


def run_hdbscan(X_reduced: np.ndarray) -> hdbscan.HDBSCAN:
    print(f"HDBSCAN: min_cluster_size={MIN_CLUSTER_SIZE}, "
          f"min_samples={MIN_SAMPLES}, method={CLUSTER_SELECTION_METHOD}, "
          f"core_dist_n_jobs={CORE_DIST_N_JOBS}, "
          f"prediction_data={SOFT_CLUSTERING}", flush=True)
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        cluster_selection_method=CLUSTER_SELECTION_METHOD,
        core_dist_n_jobs=CORE_DIST_N_JOBS,
        gen_min_span_tree=True,
        # Necesario para hdbscan.all_points_membership_vectors() en el
        # paso de soft clustering de abajo -- construye el arbol de
        # prediccion durante el fit para no tener que recalcularlo despues.
        prediction_data=SOFT_CLUSTERING,
    )
    t0 = time.time()
    clusterer.fit(X_reduced)
    print(f"  fit en {time.time() - t0:.1f}s", flush=True)
    return clusterer


def soft_reassign_noise(
    clusterer: hdbscan.HDBSCAN, labels: np.ndarray, probabilities: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Rescata puntos de ruido (label == -1) por membership fraccional.

    `leaf` asigna membresia dura de forma conservadora (ver smoke test
    100k: 64.2% de ruido). all_points_membership_vectors calcula, para
    cada punto, que tan cerca esta de cada cluster ya encontrado -- un
    punto de ruido "duro" puede tener de todos modos un vecindario claro.
    Solo se reasignan los puntos de ruido cuya mejor membership supera
    SOFT_CLUSTER_THRESHOLD; los puntos ya asignados por HDBSCAN no se
    tocan (se confia en la asignacion dura donde ya existe).
    """
    n_clusters = int(labels.max()) + 1 if (labels >= 0).any() else 0
    if n_clusters == 0:
        print("Soft clustering: no hay clusters (todo ruido), se omite.", flush=True)
        return labels, probabilities

    print(f"Soft clustering: calculando membership vectors "
          f"({n_clusters} clusters, umbral >= {SOFT_CLUSTER_THRESHOLD})", flush=True)
    t0 = time.time()
    soft_clusters = hdbscan.all_points_membership_vectors(clusterer)
    print(f"  all_points_membership_vectors en {time.time() - t0:.1f}s", flush=True)

    labels_out = labels.copy()
    probabilities_out = probabilities.copy()

    noise_mask = labels == -1
    n_noise = int(noise_mask.sum())
    if n_noise == 0:
        print("  Sin ruido que reasignar.", flush=True)
        return labels_out, probabilities_out

    noise_idx = np.where(noise_mask)[0]
    noise_membership = soft_clusters[noise_idx]
    best_cluster = noise_membership.argmax(axis=1)
    best_prob = noise_membership.max(axis=1)
    rescued = best_prob >= SOFT_CLUSTER_THRESHOLD

    labels_out[noise_idx[rescued]] = best_cluster[rescued]
    probabilities_out[noise_idx[rescued]] = best_prob[rescued]

    n_rescued = int(rescued.sum())
    print(f"  Ruido rescatado: {n_rescued:,}/{n_noise:,} puntos "
          f"({100 * n_rescued / n_noise:.1f}% del ruido original, "
          f"{100 * n_rescued / len(labels):.1f}% del corpus)", flush=True)
    return labels_out, probabilities_out


def print_diagnostics(labels: np.ndarray, probabilities: np.ndarray):
    n = len(labels)
    noise = int((labels == -1).sum())
    cluster_ids = sorted(set(labels) - {-1})
    sizes = pd.Series(labels[labels != -1]).value_counts()

    print("\n--- Diagnostico ---")
    print(f"Total tesis: {n:,}")
    print(f"Clusters encontrados: {len(cluster_ids)}")
    print(f"Ruido (sin cluster): {noise:,} ({100 * noise / n:.1f}%)")
    if len(sizes):
        print(f"Tamano de cluster -- min: {sizes.min()}, mediana: {int(sizes.median())}, "
              f"max: {sizes.max()}")
        print("Top 10 clusters mas grandes:")
        print(sizes.head(10).to_string())
    print(f"Probabilidad media de asignacion (excl. ruido): "
          f"{probabilities[labels != -1].mean():.3f}")


def main():
    if not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(f"No encontre {EMBEDDINGS_PATH}")
    if not META_PATH.exists():
        raise FileNotFoundError(f"No encontre {META_PATH}")

    print(f"Leyendo {EMBEDDINGS_PATH} (mmap)", flush=True)
    X = np.load(EMBEDDINGS_PATH, mmap_mode="r")
    print("Embeddings:", X.shape, X.dtype, flush=True)

    meta = pd.read_parquet(META_PATH)
    assert len(meta) == X.shape[0], "meta y embeddings desalineados"

    if SAMPLE_N and SAMPLE_N < X.shape[0]:
        rng = np.random.default_rng(SAMPLE_SEED)
        idx = np.sort(rng.choice(X.shape[0], size=SAMPLE_N, replace=False))
        print(f"SMOKE TEST: muestra de {SAMPLE_N:,}/{X.shape[0]:,} filas "
              f"(seed={SAMPLE_SEED})", flush=True)
        X = np.asarray(X[idx])  # materializar la muestra, ya cabe en RAM
        meta = meta.iloc[idx].reset_index(drop=True)

    reused_reduction = False
    if REDUCED_EMBEDDINGS_PATH:
        reduced_path = Path(REDUCED_EMBEDDINGS_PATH)
        if not reduced_path.exists():
            raise FileNotFoundError(
                f"REDUCED_EMBEDDINGS_PATH={reduced_path} no existe -- "
                "corre primero sin esta env var para generar el .npy reducido"
            )
        print(f"Cargando reduccion ya calculada: {reduced_path} "
              "(saltando reduce_dimensions())", flush=True)
        X_reduced = np.load(reduced_path)
        if X_reduced.shape[0] != X.shape[0]:
            raise ValueError(
                f"{reduced_path} tiene {X_reduced.shape[0]:,} filas pero X "
                f"(embeddings/meta/sample actuales) tiene {X.shape[0]:,} -- "
                "¿SAMPLE_N distinto al de la corrida que genero ese archivo?"
            )
        reused_reduction = True
    else:
        X_reduced, reducer = reduce_dimensions(X)

    clusterer = run_hdbscan(X_reduced)

    labels_hard = clusterer.labels_
    probabilities_hard = clusterer.probabilities_
    outlier_scores = clusterer.outlier_scores_

    print("\n--- Diagnostico (asignacion dura de HDBSCAN) ---")
    print_diagnostics(labels_hard, probabilities_hard)

    output_dir = OUTPUT_DIR / "smoke_test" if SAMPLE_N else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "clusters_hdbscan.parquet"

    def save_result(labels: np.ndarray, probabilities: np.ndarray) -> None:
        result = meta.copy()
        # cluster_id/cluster_probability: version final recomendada (con soft
        # clustering aplicado, si SOFT_CLUSTERING=1). *_hard preserva la
        # asignacion original de HDBSCAN para poder comparar/auditar.
        result["cluster_id"] = labels
        result["cluster_probability"] = probabilities
        result["cluster_id_hard"] = labels_hard
        result["cluster_probability_hard"] = probabilities_hard
        result["outlier_score"] = outlier_scores
        result.to_parquet(result_path, index=False)
        print(f"\nGuardado: {result_path} {result.shape}")

    # Guardar el resultado duro YA -- antes de intentar soft clustering, no
    # despues. all_points_membership_vectors() es el paso mas lento/incierto
    # de todo el script (sin barra de progreso, y con historial de escalar
    # peor que lineal con muchos clusters -- ver incidente 2026-09-22 en
    # development.md); si se cuelga o se queda sin memoria a mitad de
    # camino, el fit de UMAP+HDBSCAN (el trabajo realmente caro, ~40 min en
    # el corpus completo) ya queda a salvo en disco en vez de perderse.
    save_result(labels_hard, probabilities_hard)

    # condensed tree: fuente de la jerarquia meso/micro (paso 2), se guarda
    # aparte para no tener que re-correr HDBSCAN cuando se extraigan esos
    # niveles. Tambien antes de soft clustering, mismo motivo.
    condensed = clusterer.condensed_tree_.to_pandas()
    condensed.to_parquet(output_dir / "condensed_tree.parquet", index=False)
    print(f"Guardado: {output_dir / 'condensed_tree.parquet'} {condensed.shape}")

    if reused_reduction:
        print(f"\n(reduccion reusada de {REDUCED_EMBEDDINGS_PATH}, "
              "no se vuelve a guardar el .npy ni el modelo del reductor)")
    else:
        reduced_name = f"embeddings_{REDUCTION_METHOD}{PCA_COMPONENTS}.npy"
        np.save(output_dir / reduced_name, X_reduced)
        print(f"Guardado: {output_dir / reduced_name} {X_reduced.shape}")

        model_name = f"{REDUCTION_METHOD}_model.joblib"
        joblib.dump(reducer, output_dir / model_name)
        print(f"Guardado: {output_dir / model_name}")

    print("\nOK (resultado duro + condensed tree + reduccion ya en disco)")

    # Soft clustering al final, a proposito: es el paso mas lento/incierto,
    # y todo lo anterior (lo caro de recomputar) ya quedo a salvo arriba.
    if SOFT_CLUSTERING:
        labels, probabilities = soft_reassign_noise(
            clusterer, labels_hard, probabilities_hard
        )
        print("\n--- Diagnostico (tras soft clustering) ---")
        print_diagnostics(labels, probabilities)
        save_result(labels, probabilities)

    print("\nOK")


if __name__ == "__main__":
    main()
