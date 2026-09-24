import json
import re
from pathlib import Path
import pyarrow.dataset as ds
import unicodedata

import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================
META_PATH = "sample_50k_final_15d.parquet"
EMBEDDINGS_PATH = "sample_50k_embeddings.npy"
NODES_PATH = "cluster_nodes_final_50k.parquet"
EDGES_PATH = "cluster_edges_mutual_knn_50k.parquet"
BIBLIOGRAPHY_PATH = "semantic_bibliography_dataset.parquet"
QUERY_VECTOR_PATH = "query_vector.json"
CLUSTER_COL = "cluster"


# ============================================================
# HELPERS
# ============================================================

def normalize_id(x):
    """
    Normaliza IDs de tesis para hacer match con doc_number.
    Ejemplo: 881440 -> '000881440'
    """
    if pd.isna(x):
        return None
    return str(x).strip().zfill(9)


def l2_normalize(v):
    """
    Normaliza un vector para similitud coseno.
    """
    v = np.asarray(v, dtype=np.float32)
    norm = np.linalg.norm(v)

    if norm == 0:
        return v

    return v / norm


def split_objectives(objectives):
    """
    Acepta objetivos como lista o como string largo.
    Devuelve lista limpia.
    """
    if isinstance(objectives, list):
        return [str(o).strip() for o in objectives if str(o).strip()]

    if isinstance(objectives, str):
        parts = re.split(r"\n|;|\.\s+", objectives)
        return [p.strip(" -•\t") for p in parts if p.strip()]

    return []

def normalize_title_key(s):
    """
    Normaliza títulos para hacer match exacto entre:
    - meta["titulo_normalizado"]
    - bibliography_df["titulo_normalizado"]

    No usa fuzzy.
    """
    if pd.isna(s):
        return ""

    s = str(s).lower().strip()

    # quitar acentos
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))

    # normalizar separadores comunes
    s = s.replace(":", " ")
    s = s.replace("/", " ")
    s = s.replace("-", " ")
    s = s.replace("–", " ")
    s = s.replace("—", " ")

    # quitar puntuación rara
    s = re.sub(r"[^a-z0-9ñ\s]", " ", s)

    # espacios
    s = re.sub(r"\s+", " ", s).strip()

    return s

BLOOM_VERBS = {
    "recordar": [
        "identificar", "listar", "definir", "describir", "reconocer",
        "nombrar", "señalar", "enumerar", "localizar", "memorizar",
        "recuperar", "reproducir", "indicar", "citar", "etiquetar",
        "subrayar", "registrar", "repasar", "copiar", "repetir",
        "marcar", "mencionar", "recolectar", "catalogar", "situar",
        "retener", "observar", "apreciar", "referenciar", "tabular"
    ],
    "comprender": [
        "explicar", "interpretar", "resumir", "clasificar", "comparar",
        "distinguir", "comprender", "parafrasear", "ilustrar", "inferir",
        "predecir", "traducir", "ejemplificar", "asociar", "reescribir",
        "discutir", "extrapolar", "narrar", "simbolizar", "generalizar",
        "reinterpretar", "esquematizar", "categorizar", "contextualizar",
        "reflexionar", "deducir", "contrastar", "relacionar", "reformular",
        "clarificar"
    ],
    "aplicar": [
        "aplicar", "usar", "implementar", "emplear", "utilizar",
        "resolver", "calcular", "ejecutar", "operar", "practicar",
        "manipular", "experimentar", "simular", "adaptar", "editar",
        "completar", "modificar", "programar", "producir", "preparar",
        "automatizar", "ensayar", "realizar", "transferir", "desplegar",
        "configurar", "instalar", "demostrar", "modelar", "presentar"
    ],
    "analizar": [
        "analizar", "examinar", "diferenciar", "diagnosticar", "estudiar",
        "descomponer", "inspeccionar", "cuestionar", "investigar", "testear",
        "depurar", "rastrear", "descubrir", "detectar", "mapear",
        "segmentar", "separar", "atribuir", "correlacionar", "jerarquizar",
        "discriminar", "escrutar", "diseccionar", "triangular", "identificar",
        "caracterizar", "vincular", "perfilar", "categorizar", "ordenar"
    ],
    "evaluar": [
        "juzgar", "criticar", "validar", "determinar", "medir",
        "argumentar", "defender", "debatir", "justificar", "refutar",
        "monitorear", "auditar", "calificar", "ponderar", "fundamentar",
        "contraargumentar", "puntuar", "dictaminar", "arbitrar", "recomendar",
        "concluir", "decidir", "sopesar", "priorizar", "estimar",
        "revisar", "apreciar", "verificar", "seleccionar", "diagnosticar"
    ],
    "crear": [
        "proponer", "diseñar", "desarrollar", "formular", "generar",
        "elaborar", "crear", "sugerir", "inventar", "planificar",
        "imaginar", "componer", "integrar", "combinar", "innovar",
        "idear", "proyectar", "sintetizar", "redactar", "publicar",
        "codificar", "prototipar", "articular", "reimaginar", "transformar",
        "iniciar", "fundar", "trazar", "estructurar", "hipotetizar",
        "construir", "organizar"
    ],
}

def bloom_preanalysis(objectives):
    """
    Detecta verbos de objetivos y los mapea a Bloom.
    No usa IA.
    """
    objectives = split_objectives(objectives)

    detected = []
    counts = {level: 0 for level in BLOOM_VERBS}

    for i, obj in enumerate(objectives):
        text = obj.lower()

        for level, verbs in BLOOM_VERBS.items():
            for verb in verbs:
                if re.search(rf"\b{re.escape(verb)}\w*\b", text):
                    detected.append({
                        "objective_index": i,
                        "objective": obj,
                        "verb": verb,
                        "bloom_level": level
                    })
                    counts[level] += 1

    dominant = [
        k for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ]

    missing = [k for k, v in counts.items() if v == 0]

    return {
        "objectives": objectives,
        "detected_verbs": detected,
        "counts_by_level": counts,
        "dominant_levels": dominant,
        "missing_levels": missing
    }


def top_similar_indices(query_vector, X, k=50):
    """
    Busca las tesis más cercanas por similitud coseno.
    """
    q = l2_normalize(query_vector)

    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)

    Xn = X / norms
    sims = Xn @ q

    idx = np.argsort(sims)[::-1][:k]

    return idx, sims[idx]


def build_thesis_record(row, similarity=None, cluster_col=CLUSTER_COL):
    """
    Convierte una fila de meta en un registro compacto para el contexto.
    """
    record = {
        "id": normalize_id(row["ID_Limpio"]),
        "title": row.get("titulo_normalizado"),
        "year": int(row["Año"]) if pd.notna(row.get("Año")) else None,
        "program": row.get("programa"),
        "degree": row.get("nivel_estandar"),
        "area": row.get("area"),
        "advisor": row.get("asesor_limpio_v2"),
        "advisors": row.get("asesores_limpios_v2"),
        "plantel": row.get("plantel_estandarizado"),
        "period": row.get("periodo")
    }

    if cluster_col in row.index:
        value = row.get(cluster_col)
        record["cluster_id"] = int(value) if pd.notna(value) else None

    if similarity is not None:
        record["embedding_similarity"] = float(similarity)

    return record


def load_query_vector(path):
    """
    Lee query_vector.json.
    Acepta:
    1) [0.1, 0.2, ...]
    2) {"embedding": [0.1, 0.2, ...]}
    3) {"query_vector": [0.1, 0.2, ...]}
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        vector = data
    elif isinstance(data, dict) and "embedding" in data:
        vector = data["embedding"]
    elif isinstance(data, dict) and "query_vector" in data:
        vector = data["query_vector"]
    else:
        raise ValueError(
            "query_vector.json debe ser una lista de 384 floats, "
            "o un objeto con clave 'embedding' / 'query_vector'."
        )

    vector = np.asarray(vector, dtype=np.float32)

    if vector.shape[0] != 384:
        raise ValueError(f"query_vector debe tener dimensión 384. Tiene: {vector.shape}")

    return vector


def load_bibliography_for_exact_titles(path, titles, max_records=5):
    """
    Carga bibliografía solo para títulos con match exacto-normalizado.

    Regla:
    - NO usa ID_Limpio.
    - NO usa fuzzy.
    - Busca en bibliography["titulo_normalizado"].
    - Devuelve máximo max_records en el orden de los títulos recibidos.
    """

    if not path:
        return {}

    path = Path(path)

    if not path.exists():
        print(f"AVISO: No encontré bibliografía en {path}.")
        return {}

    titles = [
        str(t).strip()
        for t in titles
        if t is not None and str(t).strip()
    ]

    if not titles:
        return {}

    title_keys = [
        normalize_title_key(t)
        for t in titles
    ]

    title_keys = [
        k for k in title_keys
        if k
    ]

    if not title_keys:
        return {}

    wanted_columns = [
        "doc_number",
        "titulo",
        "titulo_normalizado",
        "anio",
        "autor",
        "asesor",
        "programa",
        "nivel",
        "area",
        "plantel",
        "detected_titles",
        "average_title_score",
        "bibliography_embedding_text",
        "bibliography_ref_count",
        "ready_for_ai",
        "ai_context_chunk"
    ]

    dataset = ds.dataset(str(path), format="parquet")
    available_columns = set(dataset.schema.names)

    columns = [
        c for c in wanted_columns
        if c in available_columns
    ]

    table = dataset.to_table(columns=columns)
    df = table.to_pandas()

    if df.empty or "titulo_normalizado" not in df.columns:
        return {}

    df["_title_key"] = df["titulo_normalizado"].apply(normalize_title_key)

    df = df[df["_title_key"].isin(title_keys)].copy()

    if df.empty:
        return {}

    # preservar orden semántico: top 1, top 2, top 3...
    order = {
        key: i
        for i, key in enumerate(title_keys)
    }

    df["_order"] = df["_title_key"].map(order)

    df = (
        df
        .sort_values("_order")
        .drop_duplicates("_title_key")
        .head(max_records)
    )

    return {
        row["_title_key"]: row
        for _, row in df.iterrows()
    }  

    if not path:
        return {}

    path = Path(path)

    if not path.exists():
        print(f"AVISO: No encontré bibliografía en {path}.")
        return {}

    doc_numbers = [
        normalize_id(d)
        for d in doc_numbers
        if d is not None
    ]

    doc_numbers = list(dict.fromkeys(doc_numbers))  # quitar duplicados preservando orden

    if not doc_numbers:
        return {}

    dataset = ds.dataset(str(path), format="parquet")

    wanted_columns = [
        "doc_number",
        "titulo",
        "titulo_normalizado",
        "anio",
        "autor",
        "asesor",
        "programa",
        "nivel",
        "area",
        "plantel",
        "detected_titles",
        "average_title_score",
        "bibliography_embedding_text",
        "bibliography_ref_count",
        "ready_for_ai",
        "ai_context_chunk"
    ]

    available_columns = set(dataset.schema.names)

    columns = [
        c for c in wanted_columns
        if c in available_columns
    ]

    table = dataset.to_table(
        columns=columns,
        filter=ds.field("doc_number").isin(doc_numbers)
    )

    df = table.to_pandas()

    if df.empty:
        return {}

    df["_doc_number"] = df["doc_number"].apply(normalize_id)

    order = {
        doc: i
        for i, doc in enumerate(doc_numbers)
    }

    df["_order"] = df["_doc_number"].map(order)

    df = (
        df
        .sort_values("_order")
        .head(max_records)
    )

    return {
        row["_doc_number"]: row
        for _, row in df.iterrows()
    }
    """
    Carga dataset de bibliografía.
    Soporta JSON list, JSON dict, JSONL y Parquet.
    Si no existe o path está vacío, devuelve DataFrame vacío.
    """

    if not path:
        print("AVISO: Sin bibliografía por ahora. Continuaré sin bibliography_pool.")
        return pd.DataFrame()

    path = Path(path)

    if not path.exists():
        print(f"AVISO: No encontré bibliografía en {path}. Continuaré sin bibliography_pool.")
        return pd.DataFrame()
# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def build_thesis_context(
    user_input,
    query_vector,
    meta,
    X,
    nodes,
    edges,
    bibliography_path=None,
    cluster_col=CLUSTER_COL,
    top_k=50
):
    """
    Construye el contexto estructurado del Laboratorio de Tesis.

    No usa IA.
    Solo retrieval, clusters, bloom, bibliografía, asesores y señales semánticas.
    """

    meta = meta.copy()

    if cluster_col not in meta.columns:
        raise ValueError(
            f"No existe la columna '{cluster_col}' en meta.\n"
            f"Columnas actuales: {meta.columns.tolist()}\n\n"
            "Necesitas usar el parquet de la muestra que ya tenga cluster_15d por tesis. "
            "Si en notebook sí lo tienes, guarda:\n"
            "meta.to_parquet('sample_50k_clusters_with_15d.parquet', index=False)\n"
            "y cambia META_PATH a ese archivo."
        )

    if len(meta) != len(X):
        raise ValueError(
            f"meta y X no tienen el mismo tamaño: meta={len(meta)}, X={len(X)}"
        )

    meta["_doc_number"] = meta["ID_Limpio"].apply(normalize_id)

    # -----------------------------
    # 1. Retrieval top K
    # -----------------------------
    idx, sims = top_similar_indices(query_vector, X, k=top_k)

    retrieved = meta.iloc[idx].copy()
    retrieved["_similarity"] = sims

    top_50 = [
        build_thesis_record(row, similarity=row["_similarity"], cluster_col=cluster_col)
        for _, row in retrieved.iterrows()
    ]

    top_10 = top_50[:10]
    top_5 = top_50[:5]

    # -----------------------------
    # 2. Cluster principal
    # -----------------------------
    top_for_cluster = retrieved.head(20)

    cluster_counts = (
        top_for_cluster[top_for_cluster[cluster_col] != -1][cluster_col]
        .value_counts()
    )

    if len(cluster_counts) > 0:
        main_cluster_id = int(cluster_counts.index[0])
    else:
        main_cluster_id = None

    node_map = {
        int(row["id"]): row.to_dict()
        for _, row in nodes.iterrows()
    }

    main_cluster = None

    if main_cluster_id is not None and main_cluster_id in node_map:
        n = node_map[main_cluster_id]

        main_cluster = {
            "id": main_cluster_id,
            "label": n.get("label"),
            "macro_domain": n.get("macro_domain"),
            "main_area": n.get("main_area"),
            "size": int(n.get("size", 0)),
            "centrality": {
                "degree": float(n.get("degree_centrality", 0)),
                "betweenness": float(n.get("betweenness_centrality", 0)),
                "pagerank": float(n.get("pagerank", 0))
            },
            "x": float(n.get("x", 0)),
            "y": float(n.get("y", 0))
        }

    # -----------------------------
    # 3. Clusters vecinos
    # -----------------------------
    neighbor_clusters = []

    if main_cluster_id is not None and len(edges) > 0:
        e = edges[
            (edges["source"] == main_cluster_id) |
            (edges["target"] == main_cluster_id)
        ].copy()

        if len(e) > 0:
            e["neighbor"] = e.apply(
                lambda r: int(r["target"])
                if int(r["source"]) == main_cluster_id
                else int(r["source"]),
                axis=1
            )

            e = e.sort_values("weight", ascending=False)

            for _, row in e.head(8).iterrows():
                nid = int(row["neighbor"])

                if nid in node_map:
                    n = node_map[nid]

                    neighbor_clusters.append({
                        "id": nid,
                        "label": n.get("label"),
                        "macro_domain": n.get("macro_domain"),
                        "main_area": n.get("main_area"),
                        "edge_weight": float(row["weight"]),
                        "size": int(n.get("size", 0))
                    })

    # -----------------------------
    # 4. Distribuciones top50
    # -----------------------------
    program_distribution = {
        str(k): int(v)
        for k, v in retrieved["programa"].value_counts().head(10).to_dict().items()
    }

    degree_distribution = {
        str(k): int(v)
        for k, v in retrieved["nivel_estandar"].value_counts().head(10).to_dict().items()
    }

    area_distribution = {
        str(k): int(v)
        for k, v in retrieved["area"].value_counts().head(10).to_dict().items()
    }

    # -----------------------------
    # 5. Bloom
    # -----------------------------
    bloom = bloom_preanalysis(user_input.get("objectives", []))
    # -----------------------------
        # -----------------------------
    # 6. Bibliography pool por título exacto
    # -----------------------------
    bibliography_pool = []

    # Regla:
    # tomar top 20 tesis semánticamente cercanas,
    # buscar cuáles tienen bibliografía por título exacto,
    # conservar máximo 5 en orden de cercanía.
    candidate_titles = [
        thesis["title"]
        for thesis in top_50[:20]
    ]

    bib_by_title = load_bibliography_for_exact_titles(
        bibliography_path,
        candidate_titles,
        max_records=5
    )

    for thesis in top_50[:20]:
        title_key = normalize_title_key(thesis["title"])

        if title_key in bib_by_title:
            b = bib_by_title[title_key]

            detected_titles = b.get("detected_titles", [])

            if isinstance(detected_titles, str):
                try:
                    detected_titles = json.loads(detected_titles)
                except Exception:
                    detected_titles = []

            bibliography_pool.append({
                "source_thesis_id": thesis["id"],
                "source_thesis_title": thesis["title"],
                "source_similarity": thesis["embedding_similarity"],

                # ID real del dataset bibliográfico
                "bibliography_doc_number": str(b.get("doc_number", "")),

                # Match seguro
                "match_type": "exact_title",
                "match_score": 100,

                "bibliography_thesis_title": str(b.get("titulo", "")),
                "bibliography_year": int(b.get("anio")) if pd.notna(b.get("anio")) else None,
                "bibliography_program": str(b.get("programa", "")),
                "bibliography_level": str(b.get("nivel", "")),
                "bibliography_area": str(b.get("area", "")),
                "bibliography_plantel": str(b.get("plantel", "")),
                "bibliography_ref_count": int(b.get("bibliography_ref_count", 0))
                if pd.notna(b.get("bibliography_ref_count", None))
                else None,

                "detected_titles": detected_titles[:12]
                if isinstance(detected_titles, list)
                else [],

                "bibliography_embedding_text": str(
                    b.get("bibliography_embedding_text", "")
                )[:2500],

                "ai_context_chunk": str(
                    b.get("ai_context_chunk", "")
                )[:3500]
            })

        if len(bibliography_pool) >= 5:
            break
    
    # -----------------------------
    # 7. Advisor candidates
    # -----------------------------
    advisor_rows = []

    top_retrieved = retrieved.head(50).copy()

    for advisor, group in top_retrieved.groupby("asesor_limpio_v2"):
        if pd.isna(advisor) or str(advisor).strip() == "":
            continue

        years = sorted([
            int(y) for y in group["Año"].dropna().unique().tolist()
        ])

        clusters = []
        for c in group[cluster_col].dropna().unique().tolist():
            c = int(c)
            if c != -1:
                clusters.append(c)

        advisor_rows.append({
            "advisor_name": str(advisor),
            "related_thesis_count": int(len(group)),
            "max_similarity": float(group["_similarity"].max()),
            "avg_similarity": float(group["_similarity"].mean()),
            "years": years,
            "last_year": max(years) if years else None,
            "programs": [
                str(x) for x in group["programa"].value_counts().head(5).index.tolist()
            ],
            "clusters": clusters,
            "representative_theses": [
                build_thesis_record(r, similarity=r["_similarity"], cluster_col=cluster_col)
                for _, r in group.sort_values("_similarity", ascending=False).head(5).iterrows()
            ]
        })

    advisor_candidates = sorted(
        advisor_rows,
        key=lambda x: (
            x["related_thesis_count"],
            x["max_similarity"],
            x["last_year"] or 0
        ),
        reverse=True
    )[:15]

    # -----------------------------
    # 8. Novelty / interdisciplinarity signals
    # -----------------------------
    retrieved_clusters = (
        retrieved[cluster_col]
        .value_counts(normalize=True)
        .head(8)
        .to_dict()
    )

    cluster_pull = []

    for cid, share in retrieved_clusters.items():
        cid = int(cid)

        if cid == -1:
            continue

        if cid in node_map:
            cluster_pull.append({
                "cluster_id": cid,
                "label": node_map[cid].get("label"),
                "macro_domain": node_map[cid].get("macro_domain"),
                "pull": float(share)
            })

    top50_cluster_diversity = int(len([
        c for c in retrieved[cluster_col].unique()
        if int(c) != -1
    ]))

    if len(cluster_pull) <= 2:
        interpretation_hint = "zona_central"
    elif len(cluster_pull) <= 5:
        interpretation_hint = "zona_interdisciplinaria"
    else:
        interpretation_hint = "zona_puente"

    novelty_signals = {
        "cluster_pull": cluster_pull,
        "main_cluster_pull": float(retrieved_clusters.get(main_cluster_id, 0))
        if main_cluster_id is not None
        else None,
        "top50_cluster_diversity": top50_cluster_diversity,
        "interpretation_hint": interpretation_hint
    }

    # -----------------------------
    # 9. Context final
    # -----------------------------
    context = {
        "user_project": {
            "title": user_input.get("title", ""),
            "keywords": user_input.get("keywords", []),
            "objectives": bloom["objectives"],
            "program": user_input.get("program", ""),
            "degree": user_input.get("degree", "")
        },

        "semantic_position": {
            "main_cluster": main_cluster,
            "neighbor_clusters": neighbor_clusters,
            "program_distribution_top50": program_distribution,
            "degree_distribution_top50": degree_distribution,
            "area_distribution_top50": area_distribution
        },

        "similar_theses": {
            "top_50": top_50,
            "top_10_candidates": top_10,
            "top_5_raw": top_5
        },

        "bloom": bloom,

        "bibliography_pool": bibliography_pool,

        "advisor_candidates": advisor_candidates,

        "novelty_signals": novelty_signals
    }

    return context


# ============================================================
# EJECUCIÓN DE PRUEBA LOCAL
# ============================================================

if __name__ == "__main__":
    print("Cargando archivos...")

    meta = pd.read_parquet(META_PATH)
    X = np.load(EMBEDDINGS_PATH)
    nodes = pd.read_parquet(NODES_PATH)
    mutual_edges = pd.read_parquet(EDGES_PATH)
    bibliography_df = pd.DataFrame()
    print("meta:", meta.shape)
    print("X:", X.shape)
    print("nodes:", nodes.shape)
    print("edges:", mutual_edges.shape)
    print("bibliography: carga bajo demanda")

    user_input = {
        "title": "Analisis del sistema bancario de Mexico y China 1850-2009",
        "keywords": [
            "México",
            "China",
            "banco",
            "sistema bancario",
            "economía"
        ],
        "objectives": [
            "Analizar las diferencias entre ambos sistemas bancarios",
            "Reconocer diferencias en los procesos históricos",
            "Sugerir mejoras para el sistema bancario mexicano"
        ],
        "program": "Economía",
        "degree": "Licenciatura"
    }

    query_vector = load_query_vector(QUERY_VECTOR_PATH)

    context = build_thesis_context(
    user_input=user_input,
    query_vector=query_vector,
    meta=meta,
    X=X,
    nodes=nodes,
    edges=mutual_edges,
    bibliography_path=BIBLIOGRAPHY_PATH,
    cluster_col=CLUSTER_COL,
    top_k=50
)

    with open("thesis_context_example.json", "w", encoding="utf-8") as f:
        json.dump(context, f, ensure_ascii=False, indent=2)

    print("\nGuardado thesis_context_example.json")

    print("\nMAIN CLUSTER:")
    print(json.dumps(context["semantic_position"]["main_cluster"], ensure_ascii=False, indent=2))

    print("\nTOP 10 CANDIDATES:")
    print(json.dumps(context["similar_theses"]["top_10_candidates"], ensure_ascii=False, indent=2))

    print("\nBLOOM:")
    print(json.dumps(context["bloom"], ensure_ascii=False, indent=2))

    print("\nBIBLIOGRAPHY POOL SAMPLE:")
    print(json.dumps(context["bibliography_pool"][:2], ensure_ascii=False, indent=2))

    print("\nADVISOR CANDIDATES:")
    print(json.dumps(context["advisor_candidates"][:5], ensure_ascii=False, indent=2))

    print("\nNOVELTY SIGNALS:")
    print(json.dumps(context["novelty_signals"], ensure_ascii=False, indent=2))