"""Genera etiquetas de tema por cluster de HDBSCAN usando c-TF-IDF (class-based
TF-IDF, la tecnica de BERTopic) sobre los titulos de las tesis -- paso 2/7 de
"Proximos pasos concretos" en development.md.

Corre 100% local, no hace falta Kaggle: la entrada es texto (titulos), nada
que ver con las matrices de 609k x 1024 que forzaron mover HDBSCAN a Kaggle
por RAM (ver development.md).

Idea de c-TF-IDF (BERTopic): en vez de TF-IDF documento por documento, cada
CLUSTER se trata como un solo "documento" (todos sus titulos concatenados).
El termino que distingue a un cluster no es el mas frecuente en el, sino el
que aparece mucho ahi y poco en el resto de los clusters:

    tf(t, c)  = conteo de t en el cluster c / total de palabras del cluster c
    idf(t)    = log(1 + A / freq(t))
        A      = promedio de palabras por cluster (total palabras / n clusters)
        freq(t)= conteo total del termino t sumando todos los clusters

El ruido (cluster_id == -1, 67.2% del corpus en la corrida de 609k, ver
development.md) no tiene tema -- se excluye antes de construir la matriz.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

CLUSTERS_PATH = Path(os.getenv("CLUSTERS_PATH", "data/clustering/clusters_hdbscan.parquet"))
TITLES_PATH = Path(os.getenv("TITLES_PATH", "data/public/data_unam.parquet"))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "data/clustering/cluster_topics_ctfidf.parquet"))

TOP_N_KEYWORDS = int(os.getenv("TOP_N_KEYWORDS", "8"))
# Descarta terminos casi unicos en todo el corpus (typos, nombres propios
# aislados) -- sin esto, un typo que aparece 1 vez en un cluster chico puede
# ganarle a palabras genuinamente representativas solo por ser "unico".
MIN_TOTAL_COUNT = int(os.getenv("MIN_TOTAL_COUNT", "3"))
# Descarta terminos casi universales (relleno institucional que aparece en
# la mayoria de los 513 "documentos"/clusters) -- red de seguridad aparte de
# la lista de stopwords de abajo, no depende de que esa lista este completa.
MAX_DF = float(os.getenv("MAX_DF", "0.5"))

# Stopwords en espanol (funcionales, sin contenido semantico) + relleno
# academico especifico de titulos de tesis (aparece en casi todos los
# clusters por ser genero del documento, no tema real).
STOPWORDS_ES = {
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con",
    "contra", "cual", "cuando", "de", "del", "desde", "donde", "durante",
    "e", "el", "ella", "ellas", "ellos", "en", "entre", "era", "erais",
    "eran", "eras", "eres", "es", "esa", "esas", "ese", "eso", "esos",
    "esta", "estas", "este", "esto", "estos", "ha", "hay", "la", "las",
    "le", "les", "lo", "los", "mas", "mi", "mis", "mucho", "muy", "na",
    "ni", "no", "nos", "nosotros", "nuestra", "nuestras", "nuestro",
    "nuestros", "o", "os", "otra", "otras", "otro", "otros", "para",
    "pero", "poco", "por", "porque", "que", "quien", "quienes", "se",
    "sea", "segun", "ser", "si", "sin", "sobre", "son", "su", "sus",
    "te", "tiene", "tienen", "toda", "todas", "todo", "todos", "tu",
    "tus", "un", "una", "uno", "unos", "y", "ya", "tal",
    "tesis", "estudio", "estudios", "analisis", "caso", "propuesta",
    "proyecto", "trabajo", "aplicacion", "evaluacion", "implementacion",
    "desarrollo", "diseno", "elaboracion", "investigacion", "informe",
    "practicas", "mexico", "unam", "df", "cdmx", "nacional", "autonoma",
    "universidad",
}


def load_cluster_titles() -> pd.DataFrame:
    print(f"Leyendo {CLUSTERS_PATH}")
    clusters = pd.read_parquet(CLUSTERS_PATH, columns=["thesis_id", "cluster_id"])
    print(f"Leyendo {TITLES_PATH}")
    titles = pd.read_parquet(TITLES_PATH, columns=["thesis_id", "titulo"])

    df = clusters.merge(titles, on="thesis_id", how="left")
    faltantes = df["titulo"].isna().sum()
    if faltantes:
        print(f"Aviso: {faltantes} tesis sin titulo tras el join, se excluyen")
    df = df[df["titulo"].notna()]

    ruido = int((df["cluster_id"] == -1).sum())
    df = df[df["cluster_id"] != -1].reset_index(drop=True)
    print(f"Tesis con cluster asignado (excluyendo {ruido:,} de ruido): {len(df):,}")
    return df


def main():
    df = load_cluster_titles()

    docs = (
        df.groupby("cluster_id")["titulo"]
        .apply(lambda s: " ".join(s.astype(str)))
        .sort_index()
    )
    cluster_ids = docs.index.to_numpy()
    n_clusters = len(cluster_ids)
    tesis_por_cluster = df.groupby("cluster_id").size().reindex(cluster_ids).to_numpy()
    print(f"Clusters a etiquetar: {n_clusters}")

    vectorizer = CountVectorizer(
        stop_words=list(STOPWORDS_ES),
        ngram_range=(1, 2),
        max_df=MAX_DF,
    )
    X = vectorizer.fit_transform(docs.tolist())  # (n_clusters, n_terminos)
    terms = np.array(vectorizer.get_feature_names_out())
    print(f"Vocabulario tras filtros (stopwords, max_df={MAX_DF}): {len(terms):,} terminos")

    freq_total = np.asarray(X.sum(axis=0)).ravel()  # freq(t): suma sobre todos los clusters
    palabras_por_cluster = np.asarray(X.sum(axis=1)).ravel()  # denominador de tf(t,c)
    A = palabras_por_cluster.sum() / n_clusters  # promedio de palabras por cluster

    idf = np.log(1 + A / np.maximum(freq_total, 1))
    tf = X.multiply(1 / np.maximum(palabras_por_cluster, 1)[:, None]).tocsr()
    c_tfidf = tf.multiply(idf[None, :]).tocsr()

    valido = freq_total >= MIN_TOTAL_COUNT

    rows = []
    for i, cid in enumerate(cluster_ids):
        fila = c_tfidf.getrow(i).toarray().ravel()
        fila[~valido] = 0.0
        top_idx = np.argsort(-fila)[:TOP_N_KEYWORDS]
        top_idx = [j for j in top_idx if fila[j] > 0]
        keywords = [terms[j] for j in top_idx]
        rows.append({
            "cluster_id": int(cid),
            "n_tesis": int(tesis_por_cluster[i]),
            "keywords": keywords,
            "topic_label": " · ".join(keywords),
        })

    result = pd.DataFrame(rows).sort_values("n_tesis", ascending=False).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUTPUT_PATH, index=False)

    print("\nOK")
    print("Guardado:", OUTPUT_PATH, result.shape)
    print("\nTop 15 clusters mas grandes:")
    with pd.option_context("display.max_colwidth", 80):
        print(result[["cluster_id", "n_tesis", "topic_label"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
