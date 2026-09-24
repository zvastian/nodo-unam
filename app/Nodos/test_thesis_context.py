import json
import re
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# -----------------------------
# Helpers
# -----------------------------

def normalize_id(x):
    if pd.isna(x):
        return None
    return str(x).strip().zfill(9)


def l2_normalize(v):
    v = np.asarray(v, dtype=np.float32)
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def split_objectives(objectives):
    if isinstance(objectives, list):
        return [str(o).strip() for o in objectives if str(o).strip()]
    if isinstance(objectives, str):
        parts = re.split(r"\n|;|\.\s+", objectives)
        return [p.strip(" -•\t") for p in parts if p.strip()]
    return []


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
    q = l2_normalize(query_vector)
    Xn = X / np.linalg.norm(X, axis=1, keepdims=True)

    sims = Xn @ q

    idx = np.argsort(sims)[::-1][:k]

    return idx, sims[idx]


def build_thesis_record(row, similarity=None, cluster_col="cluster_15d"):
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

    if cluster_col in row:
        record["cluster_id"] = int(row[cluster_col]) if pd.notna(row[cluster_col]) else None

    if similarity is not None:
        record["embedding_similarity"] = float(similarity)

    return record