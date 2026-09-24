"""Genera `atlas_data/atlas_macro_graph.v1.json` -- el grafo de macro-nodos
que carga eager en el frontend (paso 6 de "Proximos pasos concretos" en
development.md, adaptando el esquema de `nodo_unam.md` / el manifest viejo
`atlas_preview_data/atlas_manifest.v1.json` a la jerarquia HDBSCAN nueva).

Diferencias deliberadas contra el esquema viejo (ver development.md,
"Decision editorial fuerte: estructura de v1 -- 100% data-driven"):
- Sin anchors de las 4 areas ni "quadrant_area_mix_with_deterministic_jitter"
  -- la posicion de cada macro es directamente su centroide real en el
  layout PaCMAP (mediana x,y de sus miembros), nada artificial.
- IDs de macro son "M{macro_id}" (130 total), no "Area{1-4}_M{00..}" -- el
  area ya no es parte de la estructura, solo metadata (`areaMix`).
- Edges: el sistema viejo los sacaba de un grafo semantico FAISS real a
  nivel tesis (no lo tenemos reconstruido para e5-large todavia). Aqui se
  aproximan con similitud coseno entre CENTROIDES de macro (promedio
  ponderado de los centroides de sus micro-clusters, ya calculados para el
  detector de heterogeneidad) -- top-K vecinos por macro, no todos los pares,
  para no generar un grafo denso de ~8,000 edges. Marcado explicitamente
  como aproximacion en el schema note.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
MACRO_TOPICS_PATH = Path(os.getenv("MACRO_TOPICS_PATH", "data/clustering/macro_topics_ctfidf.parquet"))
MICRO_CENTROIDES_PATH = Path(os.getenv("MICRO_CENTROIDES_PATH", "data/clustering/micro_cluster_centroides.npy"))
MICRO_CENTROIDES_IDS_PATH = Path(os.getenv("MICRO_CENTROIDES_IDS_PATH", "data/clustering/micro_cluster_ids_orden.npy"))
DATA_UNAM_PATH = Path(os.getenv("DATA_UNAM_PATH", "data/public/data_unam.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "atlas_data/atlas_macro_graph.v1.json"))

TOP_K_EDGES = int(os.getenv("TOP_K_EDGES", "5"))
TOP_N_PROGRAMAS = int(os.getenv("TOP_N_PROGRAMAS", "8"))

SEED = 42


def paleta_hsv(ids: np.ndarray, seed: int) -> dict:
    n = len(ids)
    rng = np.random.default_rng(seed)
    orden = rng.permutation(n)
    hues = orden / n
    sats = 0.55 + 0.35 * ((orden * 7) % n) / n
    vals = 0.55 + 0.35 * ((orden * 13) % n) / n
    rgb = matplotlib_hsv_to_rgb(np.stack([hues, sats, vals], axis=1))
    hexs = ["#%02x%02x%02x" % tuple((c * 255).astype(int)) for c in rgb]
    return dict(zip(ids, hexs))


def matplotlib_hsv_to_rgb(hsv):
    import matplotlib.colors
    return matplotlib.colors.hsv_to_rgb(hsv)


def main():
    print("Cargando datos...")
    j = pd.read_parquet(JERARQUIA_PATH)
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id", "area"])
    topics = pd.read_parquet(MACRO_TOPICS_PATH).set_index("cluster_id")
    centroides = np.load(MICRO_CENTROIDES_PATH)
    centroide_ids = np.load(MICRO_CENTROIDES_IDS_PATH)
    idx_of = {c: i for i, c in enumerate(centroide_ids)}
    programas = pd.read_parquet(DATA_UNAM_PATH, columns=["thesis_id", "programa"])

    df = layout.merge(clusters, on="thesis_id", how="left").merge(
        j[["cluster_id", "macro_id", "meso_id"]], on="cluster_id", how="left"
    ).merge(programas, on="thesis_id", how="left")
    asignadas = df[df["macro_id"].notna()].copy()
    asignadas["macro_id"] = asignadas["macro_id"].astype(int)

    total_clusterizado = len(asignadas)
    macro_ids = np.sort(asignadas["macro_id"].unique())
    print(f"Macros: {len(macro_ids)}")

    colores = paleta_hsv(macro_ids, SEED)

    print("Calculando centroide de embeddings por macro (para similitud entre macros)...")
    macro_centroide_emb = {}
    for macro_id in macro_ids:
        micros = j.loc[j["macro_id"] == macro_id, "cluster_id"].unique()
        idxs = [idx_of[m] for m in micros if m in idx_of]
        tam = j.loc[j["cluster_id"].isin(micros), ["cluster_id", "n_tesis"]].drop_duplicates("cluster_id").set_index("cluster_id")["n_tesis"]
        w = np.array([tam[m] for m in micros if m in idx_of], dtype="float64")
        vecs = centroides[idxs]
        c = (vecs * w[:, None]).sum(axis=0) / w.sum()
        macro_centroide_emb[macro_id] = c / np.linalg.norm(c)

    emb_matrix = np.stack([macro_centroide_emb[m] for m in macro_ids])
    sims = emb_matrix @ emb_matrix.T
    np.fill_diagonal(sims, -1)

    print("Construyendo nodos...")
    nodes = []
    area_labels = {"area 1": "Área 1", "area 2": "Área 2", "area 3": "Área 3", "area 4": "Área 4", "": "Sin área"}
    for macro_id in macro_ids:
        sub = asignadas[asignadas["macro_id"] == macro_id]
        n_tesis = len(sub)
        n_micro = j.loc[j["macro_id"] == macro_id, "cluster_id"].nunique()
        n_meso = j.loc[j["macro_id"] == macro_id, "meso_id"].nunique()
        area_mix = sub["area"].value_counts(normalize=True).to_dict()
        area_mix = {k if k else "sin_area": round(v, 5) for k, v in area_mix.items()}
        dominante = max(area_mix.items(), key=lambda kv: kv[1])
        label = topics.loc[macro_id, "topic_label"] if macro_id in topics.index else ""
        top_progs = (
            sub["programa"].value_counts().head(TOP_N_PROGRAMAS)
        )
        programs_top = " | ".join(f"{p} ({n})" for p, n in top_progs.items())

        nodes.append({
            "id": f"M{macro_id}",
            "macroId": int(macro_id),
            "level": "macro",
            "label": label,
            "size": int(n_tesis),
            "sourceMicroClusters": int(n_micro),
            "sourceMesoClusters": int(n_meso),
            "position": {"x": round(float(sub["x"].median()), 5), "y": round(float(sub["y"].median()), 5)},
            "areaMix": area_mix,
            "dominantArea": dominante[0],
            "dominantAreaShare": round(dominante[1], 5),
            "color": colores[macro_id],
            "programsTop": programs_top,
        })

    print("Construyendo edges (top-K vecinos por similitud de centroide)...")
    edges = []
    vistos = set()
    for i, macro_id in enumerate(macro_ids):
        vecinos_idx = np.argsort(-sims[i])[:TOP_K_EDGES]
        for j_idx in vecinos_idx:
            otro_id = macro_ids[j_idx]
            par = tuple(sorted((int(macro_id), int(otro_id))))
            if par in vistos:
                continue
            vistos.add(par)
            score = float(sims[i, j_idx])
            if score <= 0:
                continue
            edges.append({
                "source": f"M{macro_id}",
                "target": f"M{otro_id}",
                "meanScore": round(score, 5),
                "weight": round(score, 5),
                "isApproximate": True,
            })
    print(f"Nodos: {len(nodes)} | Edges: {len(edges)}")

    graph = {
        "version": "atlas-macro-graph-v1",
        "schemaNote": (
            "Posicion = centroide real del layout PaCMAP (mediana x,y de los miembros del macro), sin jitter "
            "artificial. Edges = similitud coseno entre centroides de embeddings de macro (top-{} vecinos por "
            "macro), APROXIMACION -- no hay grafo semantico a nivel tesis reconstruido para e5-large todavia "
            "(el viejo grafo FAISS era de otro modelo de embeddings, MiniLM, y no se reconstruyo)."
        ).format(TOP_K_EDGES),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "totalTesisClusterizadas": int(total_clusterizado),
        "nodes": nodes,
        "edges": edges,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print("Guardado:", OUTPUT_PATH, f"({OUTPUT_PATH.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
