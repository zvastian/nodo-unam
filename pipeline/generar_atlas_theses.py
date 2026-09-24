"""Genera `atlas_data/theses_by_micro/{micro_id}.json` -- tesis representativas
por micro-cluster, capa lazy mas pesada de las curadas (antes de vecindario).

Seleccion: mas cercanas al centroide del micro-cluster (mismo principio que
el manifest viejo, `nearest_to_microcluster_centroid...`), con deduplicacion
simple por titulo exacto (si el mismo titulo se repite N veces -- caso ya
documentado, ej. "notas al programa" -- se muestra una sola vez con nota de
cuantas copias hay, no N tarjetas identicas).

Decision de privacidad (2026-09-22, confirmada con el usuario): se incluye
`asesor` (dato academico publico, ya limpiado en el dataset publico via
ADR-0010) pero NO nombre de autor -- el dataset publico (`data_unam.parquet`)
ya no incluye nombres de autor en absoluto (solo `num_autores`), asi que esto
es automatico, no requiere filtrar nada.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
EMBEDDINGS_PATH = Path(os.getenv("EMBEDDINGS_PATH", "data/embeddings/embeddings_full_e5large.npy"))
EMB_META_PATH = Path(os.getenv("EMB_META_PATH", "data/embeddings/embeddings_meta.parquet"))
MICRO_CENTROIDES_PATH = Path(os.getenv("MICRO_CENTROIDES_PATH", "data/clustering/micro_cluster_centroides.npy"))
MICRO_CENTROIDES_IDS_PATH = Path(os.getenv("MICRO_CENTROIDES_IDS_PATH", "data/clustering/micro_cluster_ids_orden.npy"))
DATA_UNAM_PATH = Path(os.getenv("DATA_UNAM_PATH", "data/public/data_unam.parquet"))
OUT_DIR = Path(os.getenv("OUT_DIR", "atlas_data/theses_by_micro"))

MIN_DISPLAY = 5
MAX_DISPLAY = 25
MAX_POR_TITULO = 2


def main():
    print("Cargando...")
    j = pd.read_parquet(JERARQUIA_PATH, columns=["cluster_id", "meso_id", "macro_id"])
    emb_meta = pd.read_parquet(EMB_META_PATH, columns=["thesis_id"])
    clusters = pd.read_parquet("data/clustering/clusters_hdbscan.parquet", columns=["thesis_id", "cluster_id"])
    datos = pd.read_parquet(DATA_UNAM_PATH, columns=[
        "thesis_id", "titulo", "anio", "asesor", "programa", "nivel", "area", "plantel"
    ])
    X = np.asarray(np.load(EMBEDDINGS_PATH, mmap_mode="r"), dtype="float32")
    centroides = np.load(MICRO_CENTROIDES_PATH)
    centroide_ids = np.load(MICRO_CENTROIDES_IDS_PATH)
    idx_centroide_of = {c: i for i, c in enumerate(centroide_ids)}

    aligned = emb_meta.merge(clusters, on="thesis_id", how="left")
    cluster_id_arr = aligned["cluster_id"].to_numpy()
    micro_a_macro = j.drop_duplicates("cluster_id").set_index("cluster_id")[["macro_id", "meso_id"]]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_archivos = 0
    micro_ids = np.sort(pd.unique(cluster_id_arr[cluster_id_arr != -1]))
    print(f"Micro-clusters a procesar: {len(micro_ids)}")

    datos = datos.set_index("thesis_id")

    for micro_id in micro_ids:
        mask = cluster_id_arr == micro_id
        thesis_ids = aligned.loc[mask, "thesis_id"].to_numpy()
        vecs = X[mask]
        if micro_id not in idx_centroide_of:
            continue
        centroide = centroides[idx_centroide_of[micro_id]]
        sims = vecs @ centroide

        orden = np.argsort(-sims)
        seleccionadas = []
        conteo_titulo = {}
        for i in orden:
            tid = thesis_ids[i]
            if tid not in datos.index:
                continue
            fila = datos.loc[tid]
            titulo = fila["titulo"]
            if pd.isna(titulo):
                continue
            conteo_titulo.setdefault(titulo, 0)
            if conteo_titulo[titulo] >= MAX_POR_TITULO:
                continue
            conteo_titulo[titulo] += 1
            seleccionadas.append((tid, float(sims[i]), fila))
            if len(seleccionadas) >= MAX_DISPLAY:
                break

        if len(seleccionadas) < MIN_DISPLAY and len(seleccionadas) < mask.sum():
            pass  # se muestran menos de 5 solo si el cluster es homogeneo en titulo (ya documentado en display_policy)

        theses = []
        for tid, score, fila in seleccionadas:
            theses.append({
                "thesisId": tid,
                "title": fila["titulo"],
                "year": int(fila["anio"]) if pd.notna(fila["anio"]) else None,
                "advisor": fila["asesor"] if pd.notna(fila["asesor"]) else None,
                "program": fila["programa"],
                "level": fila["nivel"],
                "area": fila["area"],
                "campus": fila["plantel"],
                "representativeScore": round(score, 5),
            })

        macro_id = int(micro_a_macro.loc[micro_id, "macro_id"]) if micro_id in micro_a_macro.index else None
        meso_id = int(micro_a_macro.loc[micro_id, "meso_id"]) if micro_id in micro_a_macro.index else None
        payload = {
            "version": "atlas-representative-theses-v1",
            "micro": {
                "id": f"U{micro_id}",
                "clusterId": int(micro_id),
                "macroId": macro_id,
                "mesoId": meso_id,
                "size": int(mask.sum()),
                "shown": len(theses),
                "selection": {
                    "method": "nearest_to_micro_centroid_dedup_by_exact_title",
                    "minDisplay": MIN_DISPLAY,
                    "maxDisplay": MAX_DISPLAY,
                    "maxPerTitle": MAX_POR_TITULO,
                },
            },
            "theses": theses,
        }
        with open(OUT_DIR / f"U{int(micro_id)}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        n_archivos += 1
        if n_archivos % 100 == 0:
            print(f"  {n_archivos}/{len(micro_ids)}")

    print(f"\nGuardados {n_archivos} archivos en {OUT_DIR}")


if __name__ == "__main__":
    main()
