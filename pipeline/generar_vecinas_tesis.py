"""Vecinas de cada tesis en todo el corpus, para el mapa (27-sep-2026).

Para cada una de las 609,154 tesis, las K más parecidas por título (e5-large, producto interno
sobre vectores normalizados), buscadas en el índice FAISS IVF-SQ8 del servicio del Laboratorio y
reordenadas con el producto interno exacto de los embeddings originales.

Salida: prototypes/atlas_vecindario_mvp/data/vecinas/<bloque>.bin, un archivo por cada BLOQUE
tesis en el orden del mapa (atlas_chaos_mode.v1.bin). Cada archivo trae, para sus tesis y en ese
orden, K índices del mapa (int32) y luego K similitudes cuantizadas (uint8: sim = 0.5 + q / 510).
El manifiesto vecinas.v1.json dice K, BLOQUE y la cuantización. El mapa pide solo el bloque de la
tesis abierta.

Uso:
  python pipeline/generar_vecinas_tesis.py --muestra 2000   # mide tiempo y acuerdo con nprobe alto
  python pipeline/generar_vecinas_tesis.py                  # todo el corpus
"""
import argparse
import json
import time
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EMB = ROOT / "data" / "embeddings" / "embeddings_full_e5large.npy"
EMB_META = ROOT / "data" / "embeddings" / "embeddings_meta.parquet"
INDICE = ROOT / "services" / "lab" / "artefactos" / "indice_ivf_sq8.faiss"
ATLAS = ROOT / "prototypes" / "atlas_vecindario_mvp" / "data"
OUT = ATLAS / "vecinas"
K = 30          # vecinas que guarda cada tesis (las 30 que muestra el mapa)
K_BUSCA = 60    # candidatas del índice aproximado, reordenadas con el producto interno exacto
BLOQUE = 4096   # tesis por archivo
LOTE = 4096


def orden_mapa():
    man = json.loads((ATLAS / "atlas_chaos_mode.v1.json").read_text(encoding="utf8"))
    f = man["fields"]["thesisIdsBlob"]
    raw = (ATLAS / man["binFile"]).read_bytes()[f["byteOffset"]:f["byteOffset"] + f["byteLength"]]
    return raw.decode("utf8").split("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--muestra", type=int, default=0)
    ap.add_argument("--nprobe", type=int, default=48)
    a = ap.parse_args()

    ids_mapa = orden_mapa()
    ids_emb = pd.read_parquet(EMB_META, columns=["thesis_id"])["thesis_id"].to_numpy()
    pos_emb = {t: i for i, t in enumerate(ids_emb)}
    emb_de_mapa = np.array([pos_emb[t] for t in ids_mapa], dtype=np.int64)   # fila del mapa -> fila del índice
    mapa_de_emb = np.empty(len(ids_emb), dtype=np.int32); mapa_de_emb[emb_de_mapa] = np.arange(len(ids_mapa), dtype=np.int32)
    n = len(ids_mapa)
    print("tesis:", n)

    X = np.load(EMB, mmap_mode="r")
    idx = faiss.read_index(str(INDICE)); idx.nprobe = a.nprobe

    def vecinas(filas_mapa):
        q = np.ascontiguousarray(X[np.sort(emb_de_mapa[filas_mapa])], dtype=np.float32)
        orden = np.argsort(np.argsort(emb_de_mapa[filas_mapa]))   # X se lee ordenado; se regresa al orden pedido
        q = q[orden]
        _, cand = idx.search(q, K_BUSCA + 1)
        out_i = np.full((len(filas_mapa), K), -1, dtype=np.int32)
        out_s = np.zeros((len(filas_mapa), K), dtype=np.float32)
        for r in range(len(filas_mapa)):
            c = cand[r]; c = c[(c >= 0) & (c != emb_de_mapa[filas_mapa[r]])]
            s = np.asarray(X[np.sort(c)], dtype=np.float32) @ q[r]
            c = np.sort(c); top = np.argsort(-s)[:K]
            out_i[r, :len(top)] = mapa_de_emb[c[top]]; out_s[r, :len(top)] = s[top]
        return out_i, out_s

    if a.muestra:
        rng = np.random.default_rng(0)
        filas = np.sort(rng.choice(n, a.muestra, replace=False))
        t = time.time(); vi, _ = vecinas(filas); dt = time.time() - t
        idx.nprobe = 768; vr, _ = vecinas(filas); idx.nprobe = a.nprobe
        acuerdo = np.mean([len(set(vi[r]) & set(vr[r])) / K for r in range(len(filas))])
        print(f"nprobe {a.nprobe}: {dt:.1f} s para {a.muestra} -> {dt / a.muestra * n / 60:.0f} min estimados; acuerdo con nprobe 768: {acuerdo:.3f}")
        return

    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for b in range(0, n, BLOQUE):
        filas = np.arange(b, min(b + BLOQUE, n))
        vi, vs = vecinas(filas)
        q = np.clip(np.rint((vs - 0.5) * 510), 0, 255).astype(np.uint8)
        (OUT / f"{b // BLOQUE}.bin").write_bytes(vi.tobytes() + q.tobytes())
        hechas = filas[-1] + 1
        print(f"{hechas}/{n}  {(time.time() - t0) / 60:.1f} min", flush=True)
    (ATLAS / "vecinas.v1.json").write_text(json.dumps({
        "version": "atlas-vecinas-v1", "n": n, "k": K, "bloque": BLOQUE,
        "formato": "por bloque: k int32 (indice del mapa, -1 = vacio) por tesis y luego k uint8 por tesis",
        "sim": "0.5 + q / 510", "modelo": "intfloat/multilingual-e5-large, titulo contra titulo",
        "indice": f"IVF4096-SQ8, nprobe {a.nprobe}, {K_BUSCA} candidatas reordenadas con producto interno exacto",
    }, ensure_ascii=False, indent=1), encoding="utf8")
    print("listo")


if __name__ == "__main__":
    main()
