"""Caracteriza el 'hueco central' del mapa PaCMAP (visto por primera vez en
docs/evidencia_visual/01_mapa_pacmap_clusters_hdbscan.png, item 1 del
checklist de evidencia visual) para responder una pregunta metodologica
concreta: es esto evidencia valida de un vacio REAL de conocimiento generado
en la UNAM (un tema que nadie investiga), o un artefacto del layout?

Ver `gap.md` para el analisis completo y el veredicto -- este script solo
genera los numeros, no los interpreta.

Metodologia:
1. Centro geometrico = centroide (x,y medio) del corpus completo.
2. Perfil de densidad radial en anillos de 0.2 unidades -- localiza el radio
   donde la densidad supera 30% del pico (banda de baja densidad = "hueco").
3. Composicion del hueco: % ruido HDBSCAN vs. clusters reales presentes
   (con su etiqueta c-TF-IDF), distribucion por area administrativa vs. el
   baseline global (factor de enriquecimiento, mismo criterio que
   `graficar_atlas_por_area.py`), y tasa de titulos duplicados vs. el resto
   del corpus (proxy de "titulo generico/boilerplate").
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
TOPICS_PATH = Path(os.getenv("TOPICS_PATH", "data/clustering/cluster_topics_ctfidf.parquet"))
TITULOS_PATH = Path(os.getenv("TITULOS_PATH", "data/public/data_unam.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/clustering/hueco_central_puntos.parquet"))

DENSITY_THRESHOLD = float(os.getenv("DENSITY_THRESHOLD", "0.30"))  # fraccion del pico de densidad
BIN_WIDTH = float(os.getenv("BIN_WIDTH", "0.2"))
BOILERPLATE_MIN_COUNT = int(os.getenv("BOILERPLATE_MIN_COUNT", "5"))


def main():
    print("Cargando...")
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "area", "cluster_id"])
    topics = pd.read_parquet(TOPICS_PATH)
    titulos = pd.read_parquet(TITULOS_PATH, columns=["thesis_id", "titulo"])

    df = layout.merge(clusters, on="thesis_id", how="left").merge(titulos, on="thesis_id", how="left")
    assert df["cluster_id"].notna().all()

    cx, cy = df["x"].mean(), df["y"].mean()
    print(f"Centroide: x={cx:.3f}, y={cy:.3f}")

    df["r"] = np.sqrt((df["x"] - cx) ** 2 + (df["y"] - cy) ** 2)

    bins = np.arange(0, 12.01, BIN_WIDTH)
    counts, edges = np.histogram(df["r"], bins=bins)
    anillo_area = np.pi * (edges[1:] ** 2 - edges[:-1] ** 2)
    densidad = counts / anillo_area

    pico = densidad.max()
    umbral = DENSITY_THRESHOLD * pico
    r_hueco = next(edges[i] for i in range(len(densidad)) if densidad[i] >= umbral)
    print(f"Pico de densidad: {pico:.1f} en r~{edges[np.argmax(densidad)]:.1f} | "
          f"radio del hueco (30% del pico): {r_hueco:.2f}")

    gap = df[df["r"] < r_hueco].copy()
    print(f"\nPuntos en el hueco: {len(gap):,} ({len(gap)/len(df)*100:.2f}% del corpus)")
    print(f"Bounding box: x=[{gap['x'].min():.2f}, {gap['x'].max():.2f}], "
          f"y=[{gap['y'].min():.2f}, {gap['y'].max():.2f}]")

    ruido_pct = (gap["cluster_id"] == -1).mean() * 100
    ruido_pct_global = (df["cluster_id"] == -1).mean() * 100
    print(f"\nRuido en el hueco: {ruido_pct:.1f}% (global: {ruido_pct_global:.1f}%)")

    top_clusters = gap[gap["cluster_id"] != -1]["cluster_id"].value_counts().head(10)
    print("\nTop clusters reales en el hueco:")
    for cid, n in top_clusters.items():
        label_rows = topics.loc[topics["cluster_id"] == cid, "topic_label"]
        label = label_rows.iloc[0] if len(label_rows) else "?"
        print(f"  cluster {cid}: n={n} ({n/len(gap)*100:.1f}%) -- {label}")

    area_global = df["area"].value_counts(normalize=True).sort_index()
    area_hueco = gap["area"].value_counts(normalize=True).sort_index()
    comp = pd.DataFrame({"global": area_global, "hueco": area_hueco}).fillna(0)
    comp["enriquecimiento"] = comp["hueco"] / comp["global"]
    print("\nArea administrativa -- hueco vs. corpus completo:")
    print(comp.round(3))

    dup_hueco = gap["titulo"].duplicated(keep=False).mean() * 100
    resto = df[df["r"] >= r_hueco]
    dup_resto = resto["titulo"].duplicated(keep=False).mean() * 100
    print(f"\nTitulos duplicados -- hueco: {dup_hueco:.1f}% | resto del corpus: {dup_resto:.1f}%")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    gap.to_parquet(OUTPUT_PATH, index=False)
    print("\nGuardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
