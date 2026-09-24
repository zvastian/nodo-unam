"""Top 5 macro-grupos mas poblados, senalados con flechas y una ficha de 3
estadisticas cada uno -- pedido explicito del usuario tras revisar el atlas
micro-vs-macro (`11_atlas_micro_vs_macro.png`) y el caso del macro 31 (isla
aislada de "notas al programa").

3 estadisticas por ficha (no mas, para no saturar): n de tesis, % del
corpus CLUSTERIZADO (no del corpus completo, que incluye el 67.2% de ruido
sin macro asignado -- ver development.md), y area administrativa dominante
con su propio %. Nombre interpretado (ej. "Medicina pediatrica") mas 2
palabras clave crudas de c-TF-IDF entre parentesis, para que el lector
pueda juzgar la etiqueta automatica contra la interpretacion humana.
"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LAYOUT_PATH = Path(os.getenv("LAYOUT_PATH", "data/clustering/layout_pacmap2d.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
TOPICS_PATH = Path(os.getenv("TOPICS_PATH", "data/clustering/macro_topics_ctfidf.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "docs/evidencia_visual/13_top5_macro_poblados.png"))

TOP_N = int(os.getenv("TOP_N", "5"))

# Nombre interpretado a mano por macro_id -- la etiqueta c-TF-IDF cruda ya
# esta en macro_topics_ctfidf.parquet y se muestra tambien (2 keywords),
# esto es solo la lectura humana para el titulo de la ficha.
NOMBRE_INTERPRETADO = {
    53: "Biología molecular / cáncer",
    71: "Medicina interna / nefrología",
    18: "Derecho mercantil / fideicomiso",
    48: "Filosofía / humanidades",
    77: "Procedimientos médico-quirúrgicos",
}

COLORES = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#e34948"]

# Posicion manual de cada ficha (offset en unidades de mapa desde su propio
# centroide) -- se ajusto a mano una vez para evitar que las 5 fichas se
# superpongan entre si o tapen al otro macro, dado que solo son 5 y el
# layout real no es simetrico.
BOX_OFFSET = {
    53: (-16, -2),
    71: (-11, -13),
    18: (10, 3),
    48: (10, 11),
    77: (10, -13),
}


def main():
    layout = pd.read_parquet(LAYOUT_PATH)
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id", "area"])
    jerarquia = pd.read_parquet(JERARQUIA_PATH, columns=["cluster_id", "macro_id"])
    topics = pd.read_parquet(TOPICS_PATH)

    df = layout.merge(clusters, on="thesis_id", how="left").merge(jerarquia, on="cluster_id", how="left")
    total_clusterizado = jerarquia_total = df["macro_id"].notna().sum()

    tam = df.groupby("macro_id").size().sort_values(ascending=False)
    top_ids = tam.head(TOP_N).index.astype(int).tolist()
    print("Top", TOP_N, "macro-grupos:", top_ids)

    fig, ax = plt.subplots(figsize=(16, 13), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    resto = df[~df["macro_id"].isin(top_ids)]
    ax.scatter(resto["x"], resto["y"], s=1.0, c="#e1e0d9", alpha=0.4, linewidths=0, rasterized=True)

    for mid, color in zip(top_ids, COLORES):
        sub = df[df["macro_id"] == mid]
        ax.scatter(sub["x"], sub["y"], s=1.4, c=color, alpha=0.8, linewidths=0, rasterized=True)

    for mid, color in zip(top_ids, COLORES):
        sub = df[df["macro_id"] == mid]
        n = len(sub)
        pct_clusterizado = n / total_clusterizado * 100
        cx, cy = sub["x"].median(), sub["y"].median()

        area_top = sub["area"].value_counts(normalize=True)
        area_label = f"{area_top.index[0]} ({area_top.iloc[0]*100:.0f}%)"

        kw = topics.loc[topics["cluster_id"] == mid, "keywords"].iloc[0][:2]
        kw_str = " · ".join(kw)
        nombre = NOMBRE_INTERPRETADO.get(mid, kw_str)

        dx, dy = BOX_OFFSET.get(mid, (8, 8))
        bx, by = cx + dx, cy + dy

        ax.annotate(
            "", xy=(cx, cy), xytext=(bx, by),
            arrowprops=dict(arrowstyle="->", color=color, lw=1.6, shrinkA=0, shrinkB=6),
            zorder=6,
        )
        texto = (
            f"Macro {mid} — {nombre}\n"
            f"({kw_str})\n"
            f"n = {n:,}  ·  {pct_clusterizado:.1f}% del corpus clusterizado\n"
            f"área dominante: {area_label}"
        )
        ax.text(
            bx, by, texto, fontsize=9.5, color="#1a1a1a", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor=color, linewidth=1.6),
            zorder=7,
        )

    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_aspect("equal")
    ax.set_xlim(df["x"].min() - 2, df["x"].max() + 2)
    ax.set_ylim(df["y"].min() - 2, df["y"].max() + 2)

    ax.set_title(
        "Proyección PaCMAP 2D — los 5 macro-grupos más poblados",
        fontsize=16, fontweight="bold", color="#1a1a1a", pad=16,
    )
    fig.text(
        0.5, 0.005,
        f"n=609,154 tesis · {total_clusterizado:,} clusterizadas (32.8%), {len(tam):,} macro-grupos totales · "
        "% calculado sobre el corpus clusterizado, no sobre el total (el ruido HDBSCAN, 67.2%, no tiene macro) · "
        "área dominante = moda del área administrativa entre los miembros del macro · 2026-09-22",
        ha="center", fontsize=9, color="#666666", family="monospace",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="white")
    print("Guardado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
