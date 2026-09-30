"""Correccion manual del layout: traslada la isla de "Notas al programa (recitales)"
junto a Musica (2026-09-28, v4.35.0).

e5 agrupo estas tesis por la formula del titulo ("notas al programa del recital...")
y no por su disciplina, y quedaron en una isla lejos de Musica. Se traslada la isla
completa, sin deformarla: todos los puntos reciben el mismo desplazamiento.

Que se mueve:
  - el macro 49 dentro de la caja de la isla (x < -10 y y > 10);
  - las tesis de ruido dentro de esa caja cuyo titulo diga "notas al programa"
    (hoy no hay ninguna; la regla queda por si el layout cambia).

No sobrescribe `layout_pacmap2d.parquet`: escribe `layout_pacmap2d_corregido.parquet`
y `layout_movidos.json` (thesis_id movidos y desplazamiento).
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
DATA_PATH = Path(os.getenv("DATA_PATH", "data/public/data_unam.parquet"))
OUT_LAYOUT = Path(os.getenv("OUT_LAYOUT", "data/clustering/layout_pacmap2d_corregido.parquet"))
OUT_MOVIDOS = Path(os.getenv("OUT_MOVIDOS", "data/clustering/layout_movidos.json"))

MACRO_RECITALES = 49
CAJA_ISLA = {"x_max": -10.0, "y_min": 10.0}
# Destino de la mediana de la isla: espacio libre justo debajo del borde inferior de Musica
# (macro 47, nucleo en ~(6.8, 0)); elegido buscando el hueco mas cercano sin tapar puntos.
DESTINO = (8.25, -2.75)


def main():
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id"])
    micro_a_macro = pd.read_parquet(JERARQUIA_PATH, columns=["cluster_id", "macro_id"]).drop_duplicates("cluster_id")
    titulos = pd.read_parquet(DATA_PATH, columns=["thesis_id", "titulo_legible"])
    df = (layout.merge(clusters, on="thesis_id", how="left")
                .merge(micro_a_macro, on="cluster_id", how="left")
                .merge(titulos, on="thesis_id", how="left"))
    df["macro_id"] = df["macro_id"].fillna(-1).astype(int)
    assert len(df) == len(layout) and (df["thesis_id"].values == layout["thesis_id"].values).all()

    en_caja = (df["x"] < CAJA_ISLA["x_max"]) & (df["y"] > CAJA_ISLA["y_min"])
    es_recital = df["titulo_legible"].str.contains(r"notas? al pro?gram", case=False, na=False)
    mover = en_caja & ((df["macro_id"] == MACRO_RECITALES) | ((df["macro_id"] == -1) & es_recital))
    n = int(mover.sum())
    print(f"Tesis a mover: {n} (macro 49: {int((mover & (df['macro_id'] == MACRO_RECITALES)).sum())}, "
          f"ruido con titulo de recital: {int((mover & (df['macro_id'] == -1)).sum())})")

    dx = DESTINO[0] - float(df.loc[mover, "x"].median())
    dy = DESTINO[1] - float(df.loc[mover, "y"].median())
    print(f"Desplazamiento: dx={dx:.4f}, dy={dy:.4f}")

    out = layout.copy()
    out.loc[mover.values, "x"] = (out.loc[mover.values, "x"] + dx).astype(out["x"].dtype)
    out.loc[mover.values, "y"] = (out.loc[mover.values, "y"] + dy).astype(out["y"].dtype)
    OUT_LAYOUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_LAYOUT, index=False)

    with open(OUT_MOVIDOS, "w", encoding="utf-8") as f:
        json.dump({"dx": dx, "dy": dy, "destino_mediana": DESTINO, "n": n,
                   "thesis_ids": df.loc[mover, "thesis_id"].tolist()}, f, ensure_ascii=False)
    print(f"Guardado: {OUT_LAYOUT}\nGuardado: {OUT_MOVIDOS}")


if __name__ == "__main__":
    main()
