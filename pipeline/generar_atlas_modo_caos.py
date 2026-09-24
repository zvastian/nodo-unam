"""Genera el payload del "modo caos" (vista cruda, decidida en development.md
seccion "vista curada vs. vista cruda del atlas") -- los 609,154 puntos del
layout PaCMAP completo, SIN curar, para renderizar con `regl-scatterplot`
(decision ya tomada en development.md tras investigar alternativas).

Formato binario, no JSON: a esta escala (609k puntos) un JSON de objetos
pesaria decenas de MB y el parseo en el navegador seria lento. En cambio:
arrays tipados concatenados en un solo .bin (Float32 x, Float32 y,
Int32 macroCode, Int32 areaCode), mas un .json chico con los offsets/conteos
para que el frontend pueda hacer `new Float32Array(buffer, offset, count)`
directo sin parsear nada pesado. macroCode = macro_id si la tesis tiene
macro asignado (clusterizada), -1 si es ruido HDBSCAN (67.2% del corpus) --
el ruido se muestra siempre en el modo caos, es literalmente el punto de
esta vista (ver development.md: "el contraste narrativo real esta en
mostrar tambien el ruido como dispersion visible sin bucket").

areaCode agregado 2026-09-23 (a pedido del usuario: "eso [color por area]
solo aplica en los clusters, por que en las tesis individuales no?") -- 1-4
= area administrativa real (independiente de si HDBSCAN la considero ruido
o no, el area es un dato del catalogo, no del clustering), 0 = sin area
registrada (10,257 filas, "Por Clasificar", ver Fase 1 de development.md).
"""
import json
import os
import struct
from pathlib import Path

import numpy as np
import pandas as pd

LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
OUT_BIN = Path(os.getenv("OUT_BIN", "atlas_data/atlas_chaos_mode.v1.bin"))
OUT_META = Path(os.getenv("OUT_META", "atlas_data/atlas_chaos_mode.v1.json"))


def main():
    print("Cargando...")
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id", "area"])
    micro_a_macro = pd.read_parquet(JERARQUIA_PATH, columns=["cluster_id", "macro_id"]).drop_duplicates("cluster_id")

    df = layout.merge(clusters, on="thesis_id", how="left").merge(micro_a_macro, on="cluster_id", how="left")
    df["macro_id"] = df["macro_id"].fillna(-1).astype("int32")
    AREA_CODES = {"area 1": 1, "area 2": 2, "area 3": 3, "area 4": 4}
    df["area_code"] = df["area"].map(AREA_CODES).fillna(0).astype("int32")
    print(f"Puntos: {len(df):,} | con macro: {(df['macro_id']>=0).sum():,} | ruido: {(df['macro_id']==-1).sum():,}")
    print(f"Area: {df['area_code'].value_counts().sort_index().to_dict()} (0=sin area, 1-4=area 1-4)")

    x = df["x"].to_numpy(dtype="float32")
    y = df["y"].to_numpy(dtype="float32")
    macro_code = df["macro_id"].to_numpy(dtype="int32")
    area_code = df["area_code"].to_numpy(dtype="int32")
    thesis_id_bytes = "\n".join(df["thesis_id"].tolist()).encode("utf-8")

    OUT_BIN.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_BIN, "wb") as f:
        off_x = f.tell(); f.write(x.tobytes())
        off_y = f.tell(); f.write(y.tobytes())
        off_macro = f.tell(); f.write(macro_code.tobytes())
        off_area = f.tell(); f.write(area_code.tobytes())
        off_ids = f.tell(); f.write(thesis_id_bytes)

    meta = {
        "version": "atlas-chaos-mode-v1",
        "n": int(len(df)),
        "note": "El campo thesisIds es un blob de texto separado por \\n, en el MISMO ORDEN que x/y/macroCode/areaCode -- "
                "para mapear un punto a su thesis_id, splitear por \\n y usar el mismo indice.",
        "fields": {
            "x": {"dtype": "float32", "byteOffset": off_x, "count": len(df)},
            "y": {"dtype": "float32", "byteOffset": off_y, "count": len(df)},
            "macroCode": {"dtype": "int32", "byteOffset": off_macro, "count": len(df), "note": "-1 = ruido HDBSCAN, sin macro"},
            "areaCode": {"dtype": "int32", "byteOffset": off_area, "count": len(df), "note": "0 = sin area, 1-4 = area 1-4 (dato de catalogo, no de clustering)"},
            "thesisIdsBlob": {"dtype": "utf8_newline_separated", "byteOffset": off_ids, "byteLength": len(thesis_id_bytes)},
        },
        "binFile": OUT_BIN.name,
    }
    meta["totalBytes"] = OUT_BIN.stat().st_size
    with open(OUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    tam_mb = OUT_BIN.stat().st_size / (1024 * 1024)
    print(f"Guardado: {OUT_BIN} ({tam_mb:.1f} MB)")
    print(f"Guardado: {OUT_META}")


if __name__ == "__main__":
    main()
