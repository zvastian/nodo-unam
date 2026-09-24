"""Genera atlas_data/vecindario_preview.v1.json -- subconjunto acotado del
vecindario deduplicado (ya generado por generar_vecindario_payload.py) listo
para publicarse dentro del prototipo de artifact "Atlas Macro NODO".

Por que un subconjunto y no los datos completos: la version completa
(atlas_data/neighbors_by_thesis/, 1.26GB en 610 shards) no cabe en los
limites de un artifact (16MB por archivo de texto, 64MB por publish). Este
script recorta a las tesis representativas de los mismos 10 macros que el
prototipo ya precarga con meso/micro (PREFETCHED en el HTML) -- mismo
principio de alcance parcial ya declarado en development.md para esa parte
del prototipo, aplicado ahora al vecindario.

A esta escala acotada (2,500 tesis representativas, tope de 20 vecinos
c/u) SI tiene sentido embeber titulo/anio por vecino directo en el archivo
(a diferencia del payload de produccion completo, donde eso costaria varios
GB) -- son ~50,000 pares, no ~55 millones.
"""
import json
import os
from pathlib import Path

import pandas as pd

JERARQUIA_PATH = Path(os.getenv("JERARQUIA_PATH", "data/clustering/jerarquia_macro_meso.parquet"))
THESES_BY_MICRO_DIR = Path(os.getenv("THESES_BY_MICRO_DIR", "atlas_data/theses_by_micro"))
NEIGHBORS_DIR = Path(os.getenv("NEIGHBORS_DIR", "atlas_data/neighbors_by_thesis"))
DATA_UNAM_PATH = Path(os.getenv("DATA_UNAM_PATH", "data/public/data_unam.parquet"))
OUT_PATH = Path(os.getenv("OUT_PATH", "atlas_data/vecindario_preview.v1.json"))

PREFETCHED = [53, 71, 18, 48, 77, 57, 15, 127, 118, 104]
MAX_VECINOS = 50  # igual al topK=50 del atlas viejo (neighborhood_by_thesis), ver development.md
NEIGHBOR_SHARD_SIZE = 1000


def thesis_num(thesis_id: str) -> int:
    return int(thesis_id[3:])


def main():
    print("Cargando jerarquia y tesis representativas...")
    j = pd.read_parquet(JERARQUIA_PATH, columns=["cluster_id", "macro_id"])
    cluster_ids = j.loc[j["macro_id"].isin(PREFETCHED), "cluster_id"].unique().tolist()

    thesis_ids = []
    cluster_id_de = {}
    macro_id_de_cluster = dict(zip(j["cluster_id"], j["macro_id"]))
    for cid in cluster_ids:
        p = THESES_BY_MICRO_DIR / f"U{cid}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for t in d["theses"]:
            thesis_ids.append(t["thesisId"])
            cluster_id_de[t["thesisId"]] = int(cid)
    thesis_ids = sorted(set(thesis_ids), key=thesis_num)
    print(f"  {len(thesis_ids)} tesis representativas en {len(cluster_ids)} micro-clusters ({len(PREFETCHED)} macros)")

    print("Cargando titulos (para resolver display de vecinos, incluye area para agrupar en modo analytic)...")
    titulos = pd.read_parquet(DATA_UNAM_PATH, columns=["thesis_id", "titulo", "anio", "area"])
    titulo_de = dict(zip(titulos["thesis_id"], titulos["titulo"]))
    anio_de = dict(zip(titulos["thesis_id"], titulos["anio"]))
    area_de = dict(zip(titulos["thesis_id"], titulos["area"]))

    shards_necesarios = sorted(set((thesis_num(t) - 1) // NEIGHBOR_SHARD_SIZE for t in thesis_ids))
    print(f"Leyendo {len(shards_necesarios)} shards de neighbors_by_thesis...")
    neighbor_de = {}
    for s in shards_necesarios:
        p = NEIGHBORS_DIR / f"{s:04d}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        neighbor_de.update(d["theses"])

    out = {}
    thesis_id_set = set(thesis_ids)
    for tid in thesis_ids:
        vecinos = neighbor_de.get(tid, [])[:MAX_VECINOS]
        entradas = []
        for v in vecinos:
            nid = v[0]
            sim = v[1]
            dup = v[2] if len(v) > 2 else 0
            entradas.append({
                "id": nid,
                "title": titulo_de.get(nid),
                "year": int(anio_de[nid]) if nid in anio_de and pd.notna(anio_de[nid]) else None,
                "area": area_de.get(nid) or None,
                "sim": sim,
                "dup": dup,
                "inSample": nid in thesis_id_set,
            })
        out[tid] = {
            "title": titulo_de.get(tid),
            "year": int(anio_de[tid]) if tid in anio_de and pd.notna(anio_de[tid]) else None,
            "area": area_de.get(tid) or None,
            "clusterId": cluster_id_de.get(tid),
            "macroId": int(macro_id_de_cluster.get(cluster_id_de.get(tid))) if cluster_id_de.get(tid) is not None else None,
            "neighbors": entradas,
        }

    by_cluster = {}
    for tid, entry in out.items():
        cid = entry["clusterId"]
        by_cluster.setdefault(str(cid), []).append(tid)

    payload = {
        "version": "atlas-vecindario-preview-v1",
        "scope": "solo tesis representativas de los 10 macros ya precargados con meso/micro en el prototipo (PREFETCHED)",
        "maxNeighborsPerThesis": MAX_VECINOS,
        "totalTheses": len(out),
        "byCluster": by_cluster,
        "theses": out,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"\nGuardado {OUT_PATH} -- {size_mb:.2f}MB, {len(out)} tesis")


if __name__ == "__main__":
    main()
