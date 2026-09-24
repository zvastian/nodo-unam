"""Corrección quirúrgica sobre `jerarquia_macro_meso.parquet` (v2): separa los
macros confirmados como genuinamente heterogéneos en sus meso constituyentes
(cada meso se vuelve su propio macro), sin tocar los ~83 restantes.

Metodología completa en development.md, sección "Corrección manual sobre la
jerarquía v2". Resumen: se usó similitud coseno entre vectores c-TF-IDF
COMPLETOS (no solo top-8) de los meso dentro de cada macro como filtro de
candidatos (umbral <0.045 de similitud media) -- 11 candidatos. Cada uno se
revisó a mano con títulos de tesis reales antes de decidir: 7 resultaron ser
falsos positivos (campos amplios pero legítimamente coherentes -- odontología,
bioética legal, derecho laboral-fiscal, comunicación/diseño, derecho civil-
mercantil, neurociencia/psiquiatría, exploración sanitaria/hospital) y se
dejaron sin cambios. Los 6 confirmados como genuinamente incoherentes:

  58 -- matemáticas + fluidos + astronomía + robótica + estadística + medicina de laboratorio
  56 -- veterinaria + cromatografía + radiología + enfermedad infecciosa + farmacia
  25 -- hotel + autobuses + bomberos + mercado (agrupados por formato "anteproyecto", no tema)
  61 -- tuberculosis + síndromes raros sin relación + "alerta Amber" (niños desaparecidos)
  30 -- energía + turismo médico + transporte + geografía económica + vivienda + telecom + residuos + fauna + atmósfera + clima
  88 -- epidemiología dental + medicina familiar + nutrición infantil + enfermería + salud reproductiva + cardiología

No se re-corre Ward ni se recalculan embeddings -- es una reasignación
directa de `macro_id` para los micro-clusters de estos 6 macros, uno por meso.
"""
import os
from pathlib import Path

import pandas as pd

JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
EMB_META_PATH = Path(os.getenv("EMB_META_PATH", "data/embeddings/embeddings_meta.parquet"))
CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
OUT_TESIS = Path(os.getenv("OUT_TESIS", "data/clustering/tesis_macro_meso.parquet"))

MACROS_A_SEPARAR = [58, 56, 25, 61, 30, 88]

# Ronda 2 (2026-09-22): macro 54 -- similitud MEDIA alta (0.063, por encima del
# umbral de ronda 1) escondia una estructura bimodal real: dos sub-bloques
# internamente muy parecidos entre si (petroleo, quimica/materiales) pero casi
# sin relacion mutua (sim_inter=0.032, similar a los casos ya confirmados
# incoherentes). Verificado con titulos reales -- ver development.md. Division
# manual en 3 (no automatica: el limite entre "quimica de sintesis" y
# "materiales/metalurgia" broto ambiguo incluso con Ward sobre los propios
# vectores c-TF-IDF de los meso, asi que se dejaron juntos en vez de forzar
# una frontera que no se pudo justificar con evidencia clara):
#   peso {255 pozos, 256 refineria} -> petroleo/refinacion
#   meso {254} -> agroindustria/ambiental (mal etiquetado como "aguas residuales")
#   meso {257,258,259,260,261,262} -> quimica de sintesis + materiales (queda unido)
SEPARACION_MANUAL_FINA = {
    54: {
        "peso_a_grupo": {255: "a", 256: "a", 254: "b"},  # resto (257,258,259,260,261,262) -> grupo "c" implicito
    },
    # Ronda 3 (2026-09-22): macro 19 mezcla derecho de familia (95 patria
    # potestad, 96 divorcio, 97 concubinato/matrimonio -- analisis legal) con
    # psicologia de pareja/violencia (93 satisfaccion marital/dependencia
    # emocional, 94 violencia familiar -- analisis psicologico/social, no
    # juridico). Mismo tema, dos disciplinas distintas. Verificado con titulos.
    19: {
        "peso_a_grupo": {95: "a", 96: "a", 97: "a", 93: "b", 94: "b"},
    },
}

# Ronda 4 (2026-09-22): mismo detector + revision manual, esta vez aplicado un
# nivel mas abajo (micro-clusters dentro de cada MESO, no meso dentro de cada
# macro). 3 casos confirmados con titulos reales:
#   meso 293 (macro 117, singleton): "tuberculosis" mezclado con "breves
#     consideraciones acerca de..." (pancreatitis, actinomicosis, tratamiento
#     historico con mercurio) -- mismo patron de grab-bag "reporte breve de
#     caso" ya visto en el viejo macro 61 (de donde viene este meso).
#   meso 281 (macro 112, singleton): fisica de particulas/cuantica (511)
#     vs. astronomia observacional (512) -- dos subcampos de fisica distintos.
#   meso 286 (macro 59, "protesis dentales"): reconstruccion auricular/
#     cirugia plastica (micro 30) vs. injertos dentales/periodontales
#     (micro 81) -- el micro 30 ni siquiera es dental, no deberia quedarse
#     en un macro de protesis dentales.
# Formato: {meso_id: {micro_id: "queda" | "nuevo_macro"}}. "queda" = se
# separa en su propio meso pero se queda en el macro_id original (solo tiene
# sentido si el macro tiene mas de un meso, como el 59). "nuevo_macro" =
# se separa en su propio meso Y su propio macro nuevo.
SEPARACION_MESO_FINA = {
    293: {128: "nuevo_macro", 208: "nuevo_macro"},
    281: {511: "nuevo_macro", 512: "nuevo_macro"},
    286: {81: "queda", 30: "nuevo_macro"},
    # Ronda 5 (2026-09-22): revision de TODOS los meso pendientes (67 de 82).
    # 5 casos mas, confirmados con titulos reales:
    #   meso 343 y 344 (ambos en macro 72, "hospital Zubiran/nutricion"):
    #     cada uno mezcla reportes de caso clinico de organos/condiciones sin
    #     relacion (pancreas, vejiga, laringe, prostata, testiculo vs.
    #     nutricion pediatrica, criosglobulinemia, cancer nasal, sindrome
    #     nefrotico), unidos solo por el genero "experiencia de N anos en el
    #     hospital X" -- refuerza que macro 72 completo es un macro de genero
    #     (nombre de institucion), no de tema, ya sospechado antes.
    #   meso 327 (macro 70, "revision literatura/presentacion clinico"):
    #     mismo patron de genero -- "reporte de un caso y revision de la
    #     literatura" aplicado a condiciones sin relacion (papiloma bucal,
    #     purpura trombocitopenica, porencefalia, brucella).
    #   meso 47 (macro 10, "codigo/articulo DF"): codigo penal (micro 220)
    #     vs. codigo civil (micro 221) -- ramas de derecho distintas.
    #   meso 44 (macro 10): estructura institucional del sistema de justicia
    #     del DF (micro 196) vs. delitos especificos como prostitucion/robo
    #     (micro 200).
    # 343/344/327 se mandan a macro nuevo (sus macros de origen son de
    # genero, no vale la pena dejarlos ahi). 47/44 se quedan en macro 10
    # porque ese macro ya es explicitamente "derecho y administracion del
    # Distrito Federal" en sentido amplio, coherente con esa amplitud.
    343: {272: "nuevo_macro", 273: "nuevo_macro"},
    344: {253: "nuevo_macro", 263: "nuevo_macro"},
    327: {98: "nuevo_macro", 99: "nuevo_macro"},
    47: {220: "queda", 221: "queda"},
    44: {196: "queda", 200: "queda"},
}


def main():
    j = pd.read_parquet(JERARQUIA_PATH)
    max_id = j["macro_id"].max()

    afectados = j[j["macro_id"].isin(MACROS_A_SEPARAR)]
    print(f"Macros a separar: {MACROS_A_SEPARAR}")
    print(f"Micro-clusters afectados: {len(afectados)} | tesis afectadas: {afectados['n_tesis'].sum()}")

    meso_unicos = sorted(afectados["meso_id"].unique())
    nuevo_id_por_meso = {m: max_id + 1 + i for i, m in enumerate(meso_unicos)}
    print(f"Se crean {len(nuevo_id_por_meso)} macros nuevos (ids {max_id+1} a {max_id+len(nuevo_id_por_meso)})")

    j.loc[j["macro_id"].isin(MACROS_A_SEPARAR), "macro_id"] = j.loc[
        j["macro_id"].isin(MACROS_A_SEPARAR), "meso_id"
    ].map(nuevo_id_por_meso)

    # --- Ronda 2: division fina de macro 54 en 3 (no 1-meso-por-macro) ---
    max_id = j["macro_id"].max()
    for macro_viejo, cfg in SEPARACION_MANUAL_FINA.items():
        peso_a_grupo = cfg["peso_a_grupo"]
        mesos_macro = sorted(j.loc[j["macro_id"] == macro_viejo, "meso_id"].unique())
        grupos = {}
        for m in mesos_macro:
            g = peso_a_grupo.get(m, "c")
            grupos.setdefault(g, []).append(m)
        print(f"\nMacro {macro_viejo} dividido en {len(grupos)} grupos finos: {grupos}")
        for g, mesos_g in grupos.items():
            max_id += 1
            j.loc[j["meso_id"].isin(mesos_g), "macro_id"] = max_id
            print(f"  grupo '{g}' (meso {mesos_g}) -> nuevo macro_id {max_id}")

    # --- Ronda 4: division de micro-clusters dentro de un meso (nivel mas fino) ---
    max_meso_id = j["meso_id"].max()
    max_id = j["macro_id"].max()
    for meso_viejo, cfg in SEPARACION_MESO_FINA.items():
        filas = j[j["meso_id"] == meso_viejo]
        if filas.empty:
            continue
        macro_original = filas["macro_id"].iloc[0]
        print(f"\nMeso {meso_viejo} (macro original {macro_original}) dividido en {len(cfg)} micro-clusters:")
        for micro_id, destino in cfg.items():
            max_meso_id += 1
            j.loc[j["cluster_id"] == micro_id, "meso_id"] = max_meso_id
            if destino == "nuevo_macro":
                max_id += 1
                j.loc[j["cluster_id"] == micro_id, "macro_id"] = max_id
                print(f"  micro {micro_id} -> nuevo meso_id {max_meso_id}, nuevo macro_id {max_id}")
            else:
                j.loc[j["cluster_id"] == micro_id, "macro_id"] = macro_original
                print(f"  micro {micro_id} -> nuevo meso_id {max_meso_id}, se queda en macro_id {macro_original}")

    print(f"\nTotal macro tras la corrección: {j['macro_id'].nunique()} (antes: {89})")
    tam_macro = j.groupby("macro_id")["n_tesis"].sum().sort_values(ascending=False)
    print(f"Macro más grande: {tam_macro.max()} ({tam_macro.max()/j['n_tesis'].sum()*100:.1f}% del clusterizado)")
    print(f"Macros singleton (1 solo micro-cluster): {(j.groupby('macro_id').size()==1).sum()}")

    j.to_parquet(JERARQUIA_PATH, index=False)
    print("\nGuardado:", JERARQUIA_PATH)

    emb_meta = pd.read_parquet(EMB_META_PATH, columns=["thesis_id"])
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id"])
    aligned = emb_meta.merge(clusters, on="thesis_id", how="left")
    tesis_out = aligned[aligned["cluster_id"] != -1].merge(
        j[["cluster_id", "macro_id", "meso_id"]], on="cluster_id", how="left"
    )
    tesis_out.to_parquet(OUT_TESIS, index=False)
    print("Guardado:", OUT_TESIS, tesis_out.shape)


if __name__ == "__main__":
    main()
