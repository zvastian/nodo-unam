"""Genera atlas_data/neighbors_by_thesis/{shard}.json -- vecindario tesis-tesis
deduplicado por titulo exacto, a partir de data/vecindario/tesis_vecindario_top100.parquet
(ADR-0014: FAISS IndexFlatIP, K=100 vecinos por tesis, corpus completo).

Por que dedup: ya documentado en development.md (paso "Corrida real en GPU") --
609,154 tesis en produccion tienen top-1 con titulo boilerplate repetido
("ortodoncia preventiva" x156, "notas al programa" x292, etc: 3.65% del corpus
con top-1 de similitud >0.999). Sin deduplicar, el "vecindario" de una tesis
cae en esos clusters queda dominado por copias identicas del mismo titulo --
cero valor exploratorio. Mismo criterio ya usado en generar_atlas_theses.py
(MAX_POR_TITULO): no colapsar a una sola entrada (perderia la senal de "esto
se repite mucho"), tampoco mostrar las 100 copias -- se cap a 2 apariciones
por titulo exacto, y la 2da entrada mostrada de un titulo repetido lleva el
conteo de cuantas mas se omitieron ("dup").

Formato deliberadamente compacto -- NO incluye titulo/anio/programa/etc. por
vecino. A esta escala (609,154 tesis x hasta 100 vecinos == ~55M pares)
embeber esos campos por entrada infla el payload a varios GB (~4.4GB solo
con titulo, estimado antes de escribir este script) -- 1000x mas grande que
theses_by_micro (513 clusters x ~20 tesis), donde si tiene sentido embeber
todo. El titulo se usa aqui SOLO para decidir deduplicacion en memoria, nunca
se persiste. Resolver id->metadata para mostrar en el frontend (titulo,
programa...) queda pendiente para cuando se construya la vista (paso 3 del
backlog en development.md) -- no se resuelve en este script.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

VECINDARIO_PATH = Path(os.getenv("VECINDARIO_PATH", "data/vecindario/tesis_vecindario_top100.parquet"))
DATA_UNAM_PATH = Path(os.getenv("DATA_UNAM_PATH", "data/public/data_unam.parquet"))
OUT_DIR = Path(os.getenv("OUT_DIR", "atlas_data/neighbors_by_thesis"))
MANIFEST_PATH = Path(os.getenv("MANIFEST_PATH", "atlas_data/atlas_neighbors_manifest.v1.json"))

MAX_POR_TITULO = 2
SHARD_SIZE = 1000
SIM_DECIMALS = 4


def thesis_num(thesis_id: str) -> int:
    return int(thesis_id[3:])


def dedup_neighbors(neighbor_ids, neighbor_sims, titulo_de):
    """Aplica el cap de MAX_POR_TITULO por titulo exacto, en orden de similitud
    (ya viene ordenado desc, verificado contra el pipeline que lo genero).
    Devuelve lista de [id, sim] o [id, sim, dup] si absorbio duplicados extra."""
    conteo_titulo = {}
    ultimo_shown_idx_de_titulo = {}
    salida = []
    for nid, sim in zip(neighbor_ids, neighbor_sims):
        titulo = titulo_de.get(nid)
        if titulo is None or titulo == "":
            salida.append([nid, round(float(sim), SIM_DECIMALS)])
            continue
        n = conteo_titulo.get(titulo, 0)
        if n < MAX_POR_TITULO:
            conteo_titulo[titulo] = n + 1
            ultimo_shown_idx_de_titulo[titulo] = len(salida)
            salida.append([nid, round(float(sim), SIM_DECIMALS)])
        else:
            idx = ultimo_shown_idx_de_titulo[titulo]
            entry = salida[idx]
            if len(entry) == 2:
                entry.append(1)
            else:
                entry[2] += 1
    return salida


def main():
    print("Cargando...")
    neigh = pd.read_parquet(VECINDARIO_PATH)
    titulos = pd.read_parquet(DATA_UNAM_PATH, columns=["thesis_id", "titulo"])
    titulo_de = dict(zip(titulos["thesis_id"], titulos["titulo"]))
    print(f"  {len(neigh)} tesis con vecindario, {len(titulo_de)} titulos cargados")

    neigh = neigh.sort_values("thesis_id").reset_index(drop=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    n_pre_total = 0
    n_post_total = 0
    n_tesis_afectadas = 0
    shard_buf = {}
    shard_actual = None
    shard_range_first = None

    def flush_shard(shard_id, primer_id, ultimo_id, contenido):
        payload = {
            "version": "atlas-neighbors-v1",
            "shard": shard_id,
            "range": [primer_id, ultimo_id],
            "dedup": {"criterion": "exact_title_match", "maxPerTitle": MAX_POR_TITULO},
            "theses": contenido,
        }
        with open(OUT_DIR / f"{shard_id:04d}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    for row in neigh.itertuples(index=False):
        thesis_id = row.thesis_id
        shard_id = (thesis_num(thesis_id) - 1) // SHARD_SIZE

        if shard_actual is None:
            shard_actual = shard_id
            shard_range_first = thesis_id
        elif shard_id != shard_actual:
            flush_shard(shard_actual, shard_range_first, ultimo_id, shard_buf)
            shard_buf = {}
            shard_actual = shard_id
            shard_range_first = thesis_id

        deduped = dedup_neighbors(row.neighbor_ids, row.neighbor_similarities, titulo_de)
        shard_buf[thesis_id] = deduped
        ultimo_id = thesis_id

        n_pre = len(row.neighbor_ids)
        n_post = len(deduped)
        n_pre_total += n_pre
        n_post_total += n_post
        if n_post < n_pre:
            n_tesis_afectadas += 1

    if shard_buf:
        flush_shard(shard_actual, shard_range_first, ultimo_id, shard_buf)

    n_shards = shard_actual + 1
    n_tesis = len(neigh)
    manifest = {
        "version": "atlas-neighbors-manifest-v1",
        "source": str(VECINDARIO_PATH),
        "totalTheses": n_tesis,
        "shardSize": SHARD_SIZE,
        "totalShards": n_shards,
        "pathTemplate": "neighbors_by_thesis/{shard:04d}.json",
        "shardResolution": "shard = (int(thesisId[3:]) - 1) // shardSize",
        "dedup": {
            "criterion": "exact_title_match",
            "maxPerTitle": MAX_POR_TITULO,
            "note": "3ra posicion opcional en cada entrada [id, sim, dup] = cuantos vecinos adicionales con el mismo titulo exacto se omitieron tras las 2 primeras apariciones.",
        },
        "stats": {
            "avgNeighborsPreDedup": round(n_pre_total / n_tesis, 2),
            "avgNeighborsPostDedup": round(n_post_total / n_tesis, 2),
            "thesesAffectedByDedup": n_tesis_afectadas,
            "thesesAffectedByDedupPct": round(100 * n_tesis_afectadas / n_tesis, 2),
        },
        "notes": [
            "NO incluye metadata de despliegue (titulo/anio/programa/...) por vecino -- solo thesisId + similarity. Ver docstring del script generador.",
            "Resolver id->metadata para el frontend queda pendiente, ver development.md paso 'Proximos pasos, pausa 2026-09-22/23'.",
        ],
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n{n_shards} shards guardados en {OUT_DIR}")
    print(f"Promedio vecinos: {manifest['stats']['avgNeighborsPreDedup']} -> {manifest['stats']['avgNeighborsPostDedup']} tras dedup")
    print(f"Tesis afectadas por dedup: {n_tesis_afectadas} ({manifest['stats']['thesesAffectedByDedupPct']}%)")


if __name__ == "__main__":
    main()
