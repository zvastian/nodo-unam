"""Detector de macros heterogeneos -- prioriza candidatos para revision manual,
NO reemplaza la revision. Ver development.md, seccion "Detector de macros
heterogeneos", para la justificacion completa y sus limitaciones conocidas.

Dos senales, calculadas sobre los vectores c-TF-IDF COMPLETOS (no el top-8)
de los meso dentro de cada macro (ver meso_ctfidf_matrix.npz, generado en la
investigacion del caso macro 56):

1. sim_media: similitud coseno media entre TODOS los pares de meso del macro.
   Buena para detectar macros difusos (muchos meso, todos poco parecidos
   entre si) -- encontro los primeros 6 casos confirmados (58, 56, 25, 61,
   30, 88). Punto ciego conocido: no detecta un macro que en realidad son
   DOS sub-bloques internamente muy parecidos entre si pero sin relacion
   mutua -- el promedio global sale "normal" porque las similitudes altas
   dentro de cada sub-bloque compensan las bajas entre sub-bloques (caso
   real: macro 54/quimica-petroleo, sim_media=0.063, por encima del umbral,
   paso desapercibido en la primera pasada).

2. sim_inter_2grupos: se fuerza un corte Ward en 2 grupos de los meso del
   macro (usando sus propios vectores c-TF-IDF) y se mide la similitud
   promedio SOLO entre los dos grupos resultantes. Detecta el punto ciego
   de (1) -- fue asi como se encontro el problema de macro 54 en retrospectiva.

Ninguna de las dos senales es un clasificador limpio por si sola -- se
verifico que macros ya confirmados como coherentes (66, 14, 20, 44, 18)
caen con valores similares o peores que macros genuinamente incoherentes en
AMBAS metricas. Usar como lista de candidatos a revisar con titulos reales,
no como veredicto automatico.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.cluster.hierarchy import linkage, fcluster

JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
MESO_CTFIDF_IDS = Path(os.getenv("MESO_CTFIDF_IDS", "data/clustering/meso_ctfidf_ids.npy"))
MESO_CTFIDF_MATRIX = Path(os.getenv("MESO_CTFIDF_MATRIX", "data/clustering/meso_ctfidf_matrix.npz"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/clustering/deteccion_heterogeneidad_macro.parquet"))

UMBRAL_SIM_MEDIA = float(os.getenv("UMBRAL_SIM_MEDIA", "0.045"))
UMBRAL_SIM_INTER = float(os.getenv("UMBRAL_SIM_INTER", "0.035"))


def main():
    j = pd.read_parquet(JERARQUIA_PATH)
    meso_ids = np.load(MESO_CTFIDF_IDS)
    M = sp.load_npz(MESO_CTFIDF_MATRIX)
    idx_of = {m: i for i, m in enumerate(meso_ids)}

    resultados = []
    for macro_id, sub in j.groupby("macro_id"):
        mesos = sorted(sub["meso_id"].unique().tolist())
        n_tesis = sub["n_tesis"].sum()
        if len(mesos) < 2:
            resultados.append((macro_id, len(mesos), n_tesis, np.nan, np.nan, False))
            continue

        idxs = [idx_of[m] for m in mesos]
        vecs = M[idxs].toarray()
        sims = vecs @ vecs.T
        np.fill_diagonal(sims, np.nan)
        sim_media = np.nanmean(sims)

        sim_inter = np.nan
        if len(mesos) >= 3:
            Z = linkage(vecs, method="ward")
            labels = fcluster(Z, t=2, criterion="maxclust")
            g1 = [i for i in range(len(mesos)) if labels[i] == 1]
            g2 = [i for i in range(len(mesos)) if labels[i] == 2]
            if g1 and g2:
                sim_inter = np.nan_to_num(sims, nan=0)[np.ix_(g1, g2)].mean()

        flag = (sim_media < UMBRAL_SIM_MEDIA) or (not np.isnan(sim_inter) and sim_inter < UMBRAL_SIM_INTER)
        resultados.append((macro_id, len(mesos), n_tesis, sim_media, sim_inter, flag))

    res = pd.DataFrame(resultados, columns=["macro_id", "n_meso", "n_tesis", "sim_media", "sim_inter_2grupos", "candidato_revision"])
    res = res.sort_values("n_tesis", ascending=False)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    res.to_parquet(OUTPUT_PATH, index=False)

    candidatos = res[res["candidato_revision"]]
    print(f"Macros totales: {len(res)} | candidatos a revisar: {len(candidatos)}")
    print(f"\nUmbral sim_media < {UMBRAL_SIM_MEDIA} o sim_inter_2grupos < {UMBRAL_SIM_INTER}")
    print("\nCandidatos (ordenados por tesis, para priorizar los de mayor impacto):")
    print(candidatos.to_string(index=False))
    print("\nGuardado:", OUTPUT_PATH)
    print("\nRECORDATORIO: esta lista es un punto de partida, no un veredicto. Revisar cada uno con titulos reales antes de separar.")


if __name__ == "__main__":
    main()
