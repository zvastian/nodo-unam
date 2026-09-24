"""Genera `atlas_data/meso_by_macro/{macro_id}.json` y
`atlas_data/micro_by_macro/{macro_id}.json` -- las capas lazy que se cargan
al hacer click en un macro (ver `atlas_data/atlas_macro_graph.v1.json` para
el nivel eager).

Edges dentro de cada subgrafo: similitud coseno entre vectores c-TF-IDF
COMPLETOS de los meso/micro (mismos `meso_ctfidf_matrix.npz` /
`micro_ctfidf_matrix.npz` ya construidos para el detector de heterogeneidad
-- reusar esa matriz aqui es deliberado, mantiene consistencia entre "que
tan relacionados se ven en el grafo" y "que tan relacionados los juzgo al
decidir si separarlos").
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
MACRO_TOPICS_PATH = Path(os.getenv("MACRO_TOPICS_PATH", "data/clustering/macro_topics_ctfidf.parquet"))
MESO_TOPICS_PATH = Path(os.getenv("MESO_TOPICS_PATH", "data/clustering/meso_topics_ctfidf.parquet"))
MICRO_TOPICS_PATH = Path(os.getenv("MICRO_TOPICS_PATH", "data/clustering/cluster_topics_ctfidf.parquet"))
MESO_CTFIDF_IDS = Path(os.getenv("MESO_CTFIDF_IDS", "data/clustering/meso_ctfidf_ids.npy"))
MESO_CTFIDF_MATRIX = Path(os.getenv("MESO_CTFIDF_MATRIX", "data/clustering/meso_ctfidf_matrix.npz"))
MICRO_CTFIDF_IDS = Path(os.getenv("MICRO_CTFIDF_IDS", "data/clustering/micro_ctfidf_ids.npy"))
MICRO_CTFIDF_MATRIX = Path(os.getenv("MICRO_CTFIDF_MATRIX", "data/clustering/micro_ctfidf_matrix.npz"))
DATA_UNAM_PATH = Path(os.getenv("DATA_UNAM_PATH", "data/public/data_unam.parquet"))
OUT_MESO_DIR = Path(os.getenv("OUT_MESO_DIR", "atlas_data/meso_by_macro"))
OUT_MICRO_DIR = Path(os.getenv("OUT_MICRO_DIR", "atlas_data/micro_by_macro"))

TOP_N_PROGRAMAS = 6
EDGE_MIN_SIM = 0.02  # por debajo de esto, en la escala de estas matrices, no se dibuja edge (ver development.md)


def construir_subgrafos(nivel, id_col, parent_col, ctfidf_ids_path, ctfidf_matrix_path, topics_path, out_dir):
    j = pd.read_parquet(JERARQUIA_PATH)
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id", "area"])
    topics = pd.read_parquet(topics_path).set_index("cluster_id")
    programas = pd.read_parquet(DATA_UNAM_PATH, columns=["thesis_id", "programa"])
    ctfidf_ids = np.load(ctfidf_ids_path)
    M = sp.load_npz(ctfidf_matrix_path)
    idx_of = {c: i for i, c in enumerate(ctfidf_ids)}

    df = layout.merge(clusters, on="thesis_id", how="left").merge(
        j[["cluster_id", "macro_id", "meso_id"]], on="cluster_id", how="left"
    ).merge(programas, on="thesis_id", how="left")
    asignadas = df[df["macro_id"].notna()].copy()
    asignadas["macro_id"] = asignadas["macro_id"].astype(int)

    out_dir.mkdir(parents=True, exist_ok=True)
    n_archivos = 0
    for macro_id, grupo in j.groupby("macro_id"):
        ids_del_nivel = sorted(grupo[id_col].unique().tolist())
        sub_tesis = asignadas[asignadas["macro_id"] == macro_id]

        nodes = []
        for nid in ids_del_nivel:
            sub = sub_tesis[sub_tesis[id_col] == nid]
            if len(sub) == 0:
                continue
            area_mix = sub["area"].value_counts(normalize=True)
            dominante = area_mix.index[0] if len(area_mix) else ""
            label = topics.loc[nid, "topic_label"] if nid in topics.index else ""
            top_progs = sub["programa"].value_counts().head(TOP_N_PROGRAMAS)
            programs_top = " | ".join(f"{p} ({n})" for p, n in top_progs.items())
            nodes.append({
                "id": f"{'C' if nivel=='meso' else 'U'}{nid}",
                "clusterId": int(nid),
                "macroId": int(macro_id),
                "level": nivel,
                "label": label,
                "size": int(len(sub)),
                "position": {"x": round(float(sub["x"].median()), 5), "y": round(float(sub["y"].median()), 5)},
                "dominantArea": dominante,
                "dominantAreaShare": round(float(area_mix.iloc[0]), 5) if len(area_mix) else 0.0,
                "programsTop": programs_top,
            })

        edges = []
        idxs = [idx_of[i] for i in ids_del_nivel if i in idx_of]
        ids_validos = [i for i in ids_del_nivel if i in idx_of]
        if len(idxs) >= 2:
            vecs = M[idxs].toarray()
            sims = vecs @ vecs.T
            for a in range(len(ids_validos)):
                for b in range(a + 1, len(ids_validos)):
                    score = float(sims[a, b])
                    if score >= EDGE_MIN_SIM:
                        edges.append({
                            "source": f"{'C' if nivel=='meso' else 'U'}{ids_validos[a]}",
                            "target": f"{'C' if nivel=='meso' else 'U'}{ids_validos[b]}",
                            "meanScore": round(score, 5),
                        })

        payload = {
            "version": f"atlas-{nivel}-subgraph-v1",
            "macroId": int(macro_id),
            "nodes": nodes,
            "edges": edges,
        }
        out_path = out_dir / f"M{int(macro_id)}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        n_archivos += 1

    print(f"{nivel}: {n_archivos} archivos guardados en {out_dir}")


def main():
    construir_subgrafos("meso", "meso_id", "macro_id", MESO_CTFIDF_IDS, MESO_CTFIDF_MATRIX, MESO_TOPICS_PATH, OUT_MESO_DIR)
    construir_subgrafos("micro", "cluster_id", "macro_id", MICRO_CTFIDF_IDS, MICRO_CTFIDF_MATRIX, MICRO_TOPICS_PATH, OUT_MICRO_DIR)


if __name__ == "__main__":
    main()
