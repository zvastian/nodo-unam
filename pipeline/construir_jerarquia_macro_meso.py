"""Construye macro/meso encima de los 513 clusters (micro) de HDBSCAN, sin
re-clusterizar los 609,154 puntos -- paso 5 de "Proximos pasos concretos" en
development.md.

v2 (2026-09-22) -- CAMBIO DE CRITERIO DE CORTE, ver justificacion completa en
development.md seccion "Jerarquia macro/meso -- v2, corte por coherencia".
Resumen: la v1 cortaba por CONTEO (banda 50-60, balance, gap) sin ningun
chequeo de que el contenido agrupado tuviera sentido tematico. Inspeccion
manual del macro 35 (el mas grande, v1) encontro que mezclaba 5 campos sin
relacion real (petroleo, veterinaria, quimica de sintesis, ciencia de
alimentos, metalurgia) unidos solo porque comparten registro de escritura
tecnico-procedimental, no contenido. Medido con la altura de fusion Ward: a
la altura que daba 53 grupos (0.484), esos 5 campos seguian fusionados en
UNO; hace falta bajar la altura a <=0.40 para que empiecen a separarse en
partes tematicamente mas sensatas (verificado con muestras de titulo reales
de cada sub-grupo resultante).

Metodo (igual que v1): Ward sobre los 513 centroides de micro-cluster en el
espacio de embeddings (1024d, e5-large, normalizados a coseno).

Corte v2: por DISTANCIA de fusion (`criterion='distance'`), NO por conteo.
Un nodo se corta (se acepta como macro) en el momento en que su altura de
fusion excede D_MACRO -- ya no se fija de antemano cuantos grupos salen,
salen los que la coherencia real permita. D_MACRO=0.40 fue elegido barriendo
el rango completo de alturas y verificando en que punto el caso conocido
(macro 35 de v1) se separa en partes plausibles sin fragmentar en exceso
todavia (a D=0.30 se fragmenta hasta igualar la granularidad de meso, lo que
volveria inutil tener dos niveles separados). Meso usa el mismo criterio,
D_MESO=0.20, aplicado dentro del sub-arbol de cada macro ya cortado.

Costo aceptado y declarado: el numero de macros ya NO cae en una banda
fijada por UI de antemano (v1 pedia 50-60) -- sale de la coherencia real de
los datos. Resultado real de esta corrida: ver el print de mas abajo y
development.md para las cifras finales y la comparacion con v1.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.sparse import csr_matrix

EMBEDDINGS_PATH = Path(os.getenv("EMBEDDINGS_PATH", "data/embeddings/embeddings_full_e5large.npy"))
EMB_META_PATH = Path(os.getenv("EMB_META_PATH", "data/embeddings/embeddings_meta.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
OUT_JERARQUIA = Path(os.getenv("OUT_JERARQUIA", "data/clustering/jerarquia_macro_meso.parquet"))
OUT_TESIS = Path(os.getenv("OUT_TESIS", "data/clustering/tesis_macro_meso.parquet"))
Z_PATH = Path(os.getenv("Z_PATH", "data/clustering/macro_linkage_Z.npy"))
CENTROIDES_PATH = Path(os.getenv("CENTROIDES_PATH", "data/clustering/micro_cluster_centroides.npy"))

D_MACRO = float(os.getenv("D_MACRO", "0.40"))
D_MESO = float(os.getenv("D_MESO", "0.20"))


def main():
    print("Cargando embeddings + metadata...")
    X = np.asarray(np.load(EMBEDDINGS_PATH, mmap_mode="r"), dtype="float32")
    emb_meta = pd.read_parquet(EMB_META_PATH, columns=["thesis_id"])
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id"])

    aligned = emb_meta.merge(clusters, on="thesis_id", how="left")
    assert len(aligned) == X.shape[0]
    cluster_id_arr = aligned["cluster_id"].to_numpy()

    mask = cluster_id_arr != -1
    cluster_ids = np.sort(np.unique(cluster_id_arr[mask]))
    n_clusters = len(cluster_ids)
    print(f"Micro-clusters: {n_clusters}")

    idx_map = {c: i for i, c in enumerate(cluster_ids)}
    X_masked = X[mask]
    rows = np.array([idx_map[c] for c in cluster_id_arr[mask]])
    cols = np.arange(len(rows))
    indicador = csr_matrix((np.ones(len(rows), dtype="float32"), (rows, cols)),
                            shape=(n_clusters, X_masked.shape[0]))

    print("Calculando centroides (1024d) por micro-cluster...")
    sumas = indicador @ X_masked
    tamanos = np.asarray(indicador.sum(axis=1)).ravel()
    centroides = sumas / tamanos[:, None]
    centroides = centroides / np.linalg.norm(centroides, axis=1, keepdims=True)

    print("Clustering jerarquico Ward sobre los centroides...")
    Z = linkage(centroides, method="ward")

    np.save(Z_PATH, Z)
    np.save(Z_PATH.with_name("macro_linkage_cluster_order.npy"), cluster_ids)
    np.save(CENTROIDES_PATH, centroides.astype("float32"))
    print(f"Guardado linkage + centroides: {Z_PATH}, {CENTROIDES_PATH}")

    print(f"\nCorte MACRO por distancia (D_MACRO={D_MACRO})...")
    macro_labels = fcluster(Z, t=D_MACRO, criterion="distance")
    n_macro = len(np.unique(macro_labels))
    print(f"  -> {n_macro} macro-grupos (sin banda de conteo fijada -- sale de la coherencia real)")

    meso_labels = np.zeros(n_clusters, dtype=int)
    meso_id_counter = 0
    print(f"\nCorte MESO por distancia dentro de cada macro (D_MESO={D_MESO})...")
    for m in np.unique(macro_labels):
        sub_idx = np.where(macro_labels == m)[0]
        if len(sub_idx) == 1:
            meso_id_counter += 1
            meso_labels[sub_idx[0]] = meso_id_counter
            continue
        sub_centroides = centroides[sub_idx]
        Zm = linkage(sub_centroides, method="ward")
        lbl = fcluster(Zm, t=D_MESO, criterion="distance")
        for local_i, global_i in enumerate(sub_idx):
            meso_labels[global_i] = meso_id_counter + lbl[local_i]
        meso_id_counter += len(np.unique(lbl))

    jerarquia = pd.DataFrame({
        "cluster_id": cluster_ids,
        "n_tesis": tamanos.astype(int),
        "macro_id": macro_labels,
        "meso_id": meso_labels,
    })

    print(f"\nTotal macro: {jerarquia['macro_id'].nunique()} | Total meso: {jerarquia['meso_id'].nunique()}")
    tam_macro = jerarquia.groupby("macro_id")["n_tesis"].sum().sort_values(ascending=False)
    print(f"Tamano de macro (tesis): min={tam_macro.min()}, mediana={tam_macro.median():.0f}, "
          f"max={tam_macro.max()} ({tam_macro.max()/tamanos.sum()*100:.1f}% del clusterizado)")
    tam_meso = jerarquia.groupby("meso_id")["n_tesis"].sum()
    print(f"Tamano de meso (tesis): min={tam_meso.min()}, mediana={tam_meso.median():.0f}, max={tam_meso.max()}")
    micro_por_macro = jerarquia.groupby("macro_id").size()
    print(f"Micro-clusters por macro: min={micro_por_macro.min()}, mediana={micro_por_macro.median():.0f}, "
          f"max={micro_por_macro.max()}")
    meso_por_macro = jerarquia.groupby("macro_id")["meso_id"].nunique()
    print(f"Meso por macro: min={meso_por_macro.min()}, mediana={meso_por_macro.median():.0f}, max={meso_por_macro.max()}")

    OUT_JERARQUIA.parent.mkdir(parents=True, exist_ok=True)
    jerarquia.to_parquet(OUT_JERARQUIA, index=False)
    print("\nGuardado:", OUT_JERARQUIA)

    tesis_out = aligned[aligned["cluster_id"] != -1].merge(
        jerarquia[["cluster_id", "macro_id", "meso_id"]], on="cluster_id", how="left"
    )
    tesis_out.to_parquet(OUT_TESIS, index=False)
    print("Guardado:", OUT_TESIS, tesis_out.shape)


if __name__ == "__main__":
    main()
