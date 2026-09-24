"""Reemplaza a `generar_layout_pacmap_con_nobel.py`: ese script ajustaba
PaCMAP conjunto (tesis + Nobel concatenados) siguiendo la recomendacion
original de development.md ("posicion realmente comparable"), pero el
resultado fue un colapso real, medido: 650/1026 laureados (63%) cayeron en
practicamente la misma coordenada, 997/1026 (97%) comprimidos en solo 4
ubicaciones -- PaCMAP no encuentra estructura interna real en un grupo de
1,026 puntos (0.17% del total) que entre si son mas parecidos por idioma/
registro (citas formales en ingles) que por contenido, frente a 609,154
tesis en espanol -- los trata casi como un solo outlier degenerado en vez
de darles posiciones individuales.

Fix: en vez de pedirle a PaCMAP que resuelva ese desbalance, se interpola
la posicion de cada laureado desde las tesis mas parecidas que YA tienen
una posicion 2D aceptada (`layout_pacmap2d.parquet`, la corrida tesis-solo
del paso 3, sin tocar). Para cada nodo Nobel: top-K tesis mas similares por
coseno en el espacio de 1024d, posicion = promedio de sus (x,y) ya
calculadas, ponderado por similitud. Mismo principio que la correccion de
hubness de `generar_nobel_cercano.py` -- no confiar en un solo vecino
"mas cercano" cuando el candidato tiene geometria patologica; promediar
sobre K vecinos diluye el efecto de cualquier hub individual.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

THESIS_EMB_PATH = Path(os.getenv("THESIS_EMB_PATH", "data/embeddings/embeddings_full_e5large.npy"))
THESIS_META_PATH = Path(os.getenv("THESIS_META_PATH", "data/embeddings/embeddings_meta.parquet"))
NOBEL_EMB_PATH = Path(os.getenv("NOBEL_EMB_PATH", "data/embeddings/nobel_embeddings_e5large.npy"))
NOBEL_META_PATH = Path(os.getenv("NOBEL_META_PATH", "data/embeddings/nobel_embeddings_meta.parquet"))
TESIS_LAYOUT_PATH = Path(os.getenv("TESIS_LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/clustering/nobel_posicion_interpolada.parquet"))

K = int(os.getenv("K", "25"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "20000"))


def main():
    print(f"Leyendo {THESIS_EMB_PATH} (mmap)")
    X_tesis = np.load(THESIS_EMB_PATH, mmap_mode="r")
    thesis_meta = pd.read_parquet(THESIS_META_PATH, columns=["thesis_id"])
    tesis_layout = pd.read_parquet(TESIS_LAYOUT_PATH).set_index("thesis_id")
    xy = tesis_layout.loc[thesis_meta["thesis_id"], ["x", "y"]].to_numpy()

    print(f"Leyendo {NOBEL_EMB_PATH}")
    X_nobel = np.load(NOBEL_EMB_PATH).astype("float32")
    nobel_meta = pd.read_parquet(NOBEL_META_PATH)

    n_tesis = X_tesis.shape[0]
    n_nobel = X_nobel.shape[0]

    # Primer intento (sin corregir) colapso igual que el ajuste conjunto de
    # PaCMAP: unas pocas tesis "genericas" (las mismas candidatas al hueco
    # central del mapa, ver checklist de evidencia visual) resultan "la mas
    # cercana" para cientos de nodos Nobel distintos -- mismo problema de
    # hubness que en generar_nobel_cercano.py, visto del otro lado (aqui la
    # tesis es el "candidato" que puede volverse hub, Nobel es la "consulta").
    # Fix: z-score de cada tesis contra los 1,026 nobel (barato -- ya esta
    # todo en el batch, no hace falta una pasada aparte como en el otro
    # script) antes de elegir vecinos e interpolar.
    best_sim = np.full((n_nobel, K), -np.inf, dtype="float32")   # similitud cruda (para diagnostico/pesos)
    best_z = np.full((n_nobel, K), -np.inf, dtype="float32")     # z-score (usado para elegir vecinos)
    best_idx = np.full((n_nobel, K), -1, dtype="int64")

    for start in range(0, n_tesis, BATCH_SIZE):
        end = min(start + BATCH_SIZE, n_tesis)
        batch = np.asarray(X_tesis[start:end], dtype="float32")
        sims = X_nobel @ batch.T  # (1026, batch)
        z = (sims - sims.mean(axis=0, keepdims=True)) / np.maximum(sims.std(axis=0, keepdims=True), 1e-6)

        cand_z = np.concatenate([best_z, z], axis=1)
        cand_sim = np.concatenate([best_sim, sims], axis=1)
        cand_idx = np.concatenate([
            best_idx,
            np.tile(np.arange(start, end), (n_nobel, 1)),
        ], axis=1)
        order = np.argpartition(-cand_z, K - 1, axis=1)[:, :K]
        best_z = np.take_along_axis(cand_z, order, axis=1)
        best_sim = np.take_along_axis(cand_sim, order, axis=1)
        best_idx = np.take_along_axis(cand_idx, order, axis=1)
        print(f"  {end:,}/{n_tesis:,}", flush=True)

    print("Interpolando posicion 2D por promedio ponderado de z-score (corregido por hubness)...")
    # pesos tipo softmax sobre el z-score, no la similitud cruda -- realza
    # vecinos genuinamente distintivos sin descartar del todo al resto de K
    w = np.exp((best_z - best_z.max(axis=1, keepdims=True)) * 2)
    w = w / w.sum(axis=1, keepdims=True)

    pos_x = (w * xy[best_idx, 0]).sum(axis=1)
    pos_y = (w * xy[best_idx, 1]).sum(axis=1)

    result = pd.DataFrame({
        "node_id": nobel_meta["node_id"],
        "x": pos_x.astype("float32"),
        "y": pos_y.astype("float32"),
        "sim_vecino_top1": best_sim.max(axis=1),
    })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUTPUT_PATH, index=False)

    print("\nOK")
    print("Guardado:", OUTPUT_PATH, result.shape)

    # chequeo de colapso: distancia al vecino mas cercano DENTRO de nobel
    from scipy.spatial import cKDTree
    tree = cKDTree(result[["x", "y"]].to_numpy())
    d, _ = tree.query(result[["x", "y"]].to_numpy(), k=2)
    print(f"\nDistancia al vecino Nobel mas cercano: mediana={np.median(d[:,1]):.3f}, "
          f"p10={np.percentile(d[:,1],10):.3f}")
    print(f"Nobel con vecino a distancia < 0.05 (posible colapso): {(d[:,1]<0.05).sum()} de {len(result)}")


if __name__ == "__main__":
    main()
