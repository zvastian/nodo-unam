"""Genera atlas_data/titulos_index/{shard}.json -- indice global compacto
thesisId -> {titulo, anio}, unica pieza de metadata que la vista de
vecindario (paso 3 del backlog) necesita para mostrar una lista de vecinos.

Por que un indice global y no shardear por rango de tesis "dueña" (como
neighbors_by_thesis): medido antes de decidir (no asumido) -- en una muestra
de 20 tesis, sus ~90 vecinos deduplicados caen en un promedio de 87.65 shards
DISTINTOS de los 610 usados para neighbors_by_thesis (rango 69-94). Los
thesis_id son orden de registro, no tienen relacion con similitud semantica,
asi que cualquier esquema de sharding por rango de ID no reduce cuantos bytes
hace falta descargar para resolver una lista de vecinos -- practicamente
todos los shards se tocan igual. La unica estrategia que realmente ahorra
bytes es cargar el indice completo UNA VEZ por sesion (amortizado sobre todas
las listas de vecinos que el usuario explore despues), no repartirlo por
rango de tesis "dueña".

Se shardea igual en N piezas, pero solo por el limite de tamaño de archivo
de texto publicado en Artifacts (16MB) -- no por localidad de acceso. Cada
shard es un rango contiguo de thesis_id con arrays posicionales (title[i],
year[i] para el id idStart+i) -- evita repetir claves JSON 609,156 veces.

NO incluye programa/nivel/area/plantel/asesor -- el MVP de vecindario solo
necesita titulo+año para listar y para poder "entrar" a un vecino como nuevo
foco (recursion de la misma vista). Detalle completo por tesis individual
queda pendiente, ver development.md.
"""
import json
import math
import os
from pathlib import Path

import pandas as pd

DATA_UNAM_PATH = Path(os.getenv("DATA_UNAM_PATH", "data/public/data_unam.parquet"))
OUT_DIR = Path(os.getenv("OUT_DIR", "atlas_data/titulos_index"))
MANIFEST_PATH = Path(os.getenv("MANIFEST_PATH", "atlas_data/atlas_titulos_index_manifest.v1.json"))
N_SHARDS = int(os.getenv("N_SHARDS", "8"))


def main():
    print("Cargando...")
    d = pd.read_parquet(DATA_UNAM_PATH, columns=["thesis_id", "titulo", "anio"])
    nums = d["thesis_id"].str.replace("TH_", "", regex=False).astype(int)
    assert nums.is_monotonic_increasing and nums.iloc[0] == 1, "esperaba thesis_id contiguo desde 1, verificar antes de indexar posicionalmente"
    n = len(d)
    print(f"  {n} tesis, id 1..{nums.iloc[-1]}, contiguo verificado")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shard_size = math.ceil(n / N_SHARDS)

    titles = d["titulo"].where(d["titulo"].notna(), None).tolist()
    years = d["anio"].astype("Int64")
    years = [int(y) if pd.notna(y) else None for y in years]

    sizes_mb = []
    for s in range(N_SHARDS):
        lo = s * shard_size
        hi = min(lo + shard_size, n)
        payload = {
            "version": "atlas-titulos-index-v1",
            "shard": s,
            "idStart": lo + 1,
            "idEnd": hi,
            "titles": titles[lo:hi],
            "years": years[lo:hi],
        }
        out_path = OUT_DIR / f"{s:02d}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        sizes_mb.append(round(out_path.stat().st_size / (1024 * 1024), 2))
        print(f"  shard {s}: ids {lo+1}-{hi}, {sizes_mb[-1]}MB")

    manifest = {
        "version": "atlas-titulos-index-manifest-v1",
        "totalTheses": n,
        "shardSize": shard_size,
        "totalShards": N_SHARDS,
        "pathTemplate": "titulos_index/{shard:02d}.json",
        "shardResolution": "shard = (int(thesisId[3:]) - 1) // shardSize",
        "offsetInShard": "idx = (int(thesisId[3:]) - 1) - (shard * shardSize); titulo = titles[idx]; anio = years[idx]",
        "maxShardSizeMb": max(sizes_mb),
        "totalSizeMb": round(sum(sizes_mb), 1),
        "note": "Cargar TODOS los shards una sola vez por sesion (no hay localidad de acceso por vecindario, medido: ~88/100 vecinos de una tesis caen en shards distintos de neighbors_by_thesis). Solo titulo+anio -- detalle completo (programa/nivel/area/plantel/asesor) pendiente.",
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nManifest: {MANIFEST_PATH}")
    print(f"Total: {manifest['totalSizeMb']}MB en {N_SHARDS} shards, max {manifest['maxShardSizeMb']}MB/shard")


if __name__ == "__main__":
    main()
