"""Genera `atlas_data/atlas_display_policy.v1.json` y
`atlas_data/atlas_manifest.v1.json` -- ensambla y documenta lo ya generado
por `generar_atlas_macro_graph.py`, `generar_atlas_subgraphs.py`,
`generar_atlas_theses.py` y `generar_atlas_modo_caos.py`. Correr este script
AL FINAL, despues de los otros 4.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ATLAS_DIR = Path(os.getenv("ATLAS_DIR", "atlas_data"))
JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))

MIN_VISIBLE_SIZE = 5
MAX_VISIBLE_PER_MACRO = 30


def construir_display_policy():
    j = pd.read_parquet(JERARQUIA_PATH)
    micro_por_macro = j.groupby("macro_id").size()

    visibles = {}
    ocultos = {}
    for macro_id, sub in j.groupby("macro_id"):
        tam = sub.sort_values("n_tesis", ascending=False)
        grandes = tam[tam["n_tesis"] >= MIN_VISIBLE_SIZE].head(MAX_VISIBLE_PER_MACRO)
        chicos_ocultos = len(tam) - len(grandes)
        visibles[f"M{int(macro_id)}"] = int(len(grandes))
        ocultos[f"M{int(macro_id)}"] = int(chicos_ocultos)

    policy = {
        "schema": "nodo-atlas-display-policy",
        "version": "v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "micro": {
            "minVisibleSize": MIN_VISIBLE_SIZE,
            "maxVisibleNodesPerMacro": MAX_VISIBLE_PER_MACRO,
            "hideReason": "below_min_visible_size",
            "fallbackIfEmpty": "show_largest_available",
            "audit": {
                "macroCount": int(j["macro_id"].nunique()),
                "visibleNodesByMacro": visibles,
                "hiddenNodesByMacro": ocultos,
            },
        },
        "representativeTheses": {
            "minDisplayTheses": 5,
            "maxDisplayTheses": 25,
            "maxPerTitle": 2,
            "note": "Micro-clusters muy homogeneos en titulo pueden mostrar menos de 5 tras deduplicacion exacta.",
        },
        "chaosMode": {
            "note": "Ver atlas_chaos_mode.v1.json / .bin -- sin politica de ocultamiento, muestra los 609,154 puntos "
                    "incluyendo el 67.2% de ruido HDBSCAN (deliberado, es el punto del modo caos).",
        },
    }
    out = ATLAS_DIR / "atlas_display_policy.v1.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(policy, f, ensure_ascii=False, separators=(",", ":"))
    print("Guardado:", out)
    return policy


def tamano_mb(path: Path) -> float:
    return round(path.stat().st_size / (1024 * 1024), 4) if path.exists() else None


def construir_manifest():
    macro_graph_path = ATLAS_DIR / "atlas_macro_graph.v1.json"
    meso_dir = ATLAS_DIR / "meso_by_macro"
    micro_dir = ATLAS_DIR / "micro_by_macro"
    theses_dir = ATLAS_DIR / "theses_by_micro"
    chaos_json = ATLAS_DIR / "atlas_chaos_mode.v1.json"
    chaos_bin = ATLAS_DIR / "atlas_chaos_mode.v1.bin"
    neighbors_dir = ATLAS_DIR / "neighbors_by_thesis"
    neighbors_manifest_path = ATLAS_DIR / "atlas_neighbors_manifest.v1.json"
    neighbors_manifest = None
    if neighbors_manifest_path.exists():
        with open(neighbors_manifest_path, encoding="utf-8") as f:
            neighbors_manifest = json.load(f)

    manifest = {
        "schema": "nodo-atlas-manifest",
        "version": "v1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "root": "atlas_data",
        "pipelineNote": (
            "Jerarquia HDBSCAN + Ward sobre centroides de e5-large, 5 rondas de correccion manual con revision "
            "de titulos reales (ver development.md, 'Jerarquia macro/meso/micro'). {n_macro} macro, {n_meso} meso, "
            "{n_micro} micro sobre 609,154 tesis (199,623 clusterizadas, 32.8%)."
        ).format(
            n_macro=pd.read_parquet(JERARQUIA_PATH)["macro_id"].nunique(),
            n_meso=pd.read_parquet(JERARQUIA_PATH)["meso_id"].nunique(),
            n_micro=pd.read_parquet(JERARQUIA_PATH)["cluster_id"].nunique(),
        ),
        "loadingStrategy": {
            "macroGraph": "eager",
            "mesoByMacro": "lazy",
            "microByMacro": "lazy",
            "thesesByMicro": "lazy",
            "chaosMode": "lazy_on_demand",
        },
        "files": {
            "displayPolicy": {"path": "atlas_display_policy.v1.json", "sizeMb": tamano_mb(ATLAS_DIR / "atlas_display_policy.v1.json")},
            "macroGraph": {"path": "atlas_macro_graph.v1.json", "sizeMb": tamano_mb(macro_graph_path)},
            "mesoByMacro": {"pathTemplate": "meso_by_macro/{macroId}.json", "count": len(list(meso_dir.glob("*.json")))},
            "microByMacro": {"pathTemplate": "micro_by_macro/{macroId}.json", "count": len(list(micro_dir.glob("*.json")))},
            "thesesByMicro": {"pathTemplate": "theses_by_micro/{clusterId}.json", "count": len(list(theses_dir.glob("*.json")))},
            "chaosMode": {
                "metaPath": "atlas_chaos_mode.v1.json",
                "binPath": "atlas_chaos_mode.v1.bin",
                "sizeMb": tamano_mb(chaos_bin),
                "note": "Payload binario (Float32Array x,y + Int32Array macroCode) para regl-scatterplot, ver development.md.",
            },
            "neighborhoodByThesis": (
                {
                    "status": "hecho",
                    "pathTemplate": neighbors_manifest["pathTemplate"],
                    "shardManifest": "atlas_neighbors_manifest.v1.json",
                    "count": neighbors_manifest["totalShards"],
                    "sizeMb": round(sum(f.stat().st_size for f in neighbors_dir.glob("*.json")) / (1024 * 1024), 1) if neighbors_dir.exists() else None,
                    "note": "Vecindario tesis-tesis deduplicado por titulo exacto (ADR-0014, FAISS IndexFlatIP sobre "
                            "e5-large, K=100). NO incluye metadata de despliegue por vecino (solo thesisId+similarity) "
                            "-- resolver id->titulo/programa/etc. para el frontend sigue pendiente, ver development.md.",
                }
                if neighbors_manifest
                else {
                    "status": "pendiente",
                    "note": "Requiere reconstruir un indice de vecinos mas cercanos a nivel tesis sobre los embeddings "
                            "e5-large (el viejo grafo FAISS era de MiniLM, no se reconstruyo) -- fuera de alcance de esta "
                            "pasada, ver development.md.",
                }
            ),
        },
        "uiContract": {
            "views": ["curated", "chaos"],
            "curatedLevels": ["macro", "meso", "micro", "theses"],
            "clickFlow": [
                "macro node -> meso subgraph",
                "macro node -> micro subgraph (si el usuario baja directo)",
                "meso/micro node -> representative theses",
                "curated view <-> chaos view toggle (independiente del click flow anterior)",
            ],
        },
        "notes": [
            "Bundle de datos para el atlas nuevo (HDBSCAN + Ward + correccion manual), reemplaza atlas_preview_data/ (Leiden, muestra 50k).",
            "IDs de macro/meso/micro ya no codifican area administrativa (M{macro_id}, C{meso_id}, U{cluster_id}) -- decision 100% data-driven, ver development.md.",
            "theses_by_micro incluye 'advisor' (dato academico publico) pero nunca nombre de autor -- el dataset publico ya no lo trae, decision confirmada con el usuario 2026-09-22.",
            "Todas las capas lazy deben cargarse solo bajo demanda -- no cargar micro_by_macro ni theses_by_micro de todos los macros al inicio.",
        ],
    }
    out = ATLAS_DIR / "atlas_manifest.v1.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("Guardado:", out)


if __name__ == "__main__":
    construir_display_policy()
    construir_manifest()
