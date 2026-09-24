"""ADR-0014: vecindario semantico tesis-tesis, 100% precomputado via FAISS.

Para cada una de las 609,154 tesis, encuentra sus TOP_K vecinos mas cercanos
(similitud coseno) dentro del mismo corpus -- reemplaza el endpoint on-demand
que preveia ADR-0003 (ahora superado). FAISS corre una sola vez aqui (build-
time), nunca se despliega como servicio -- ver ADR-0014 para el porque.

Embeddings ya normalizados (norma=1) -> similitud coseno = producto punto ->
IndexFlatIP (exacto, no aproximado: a este tamano de corpus una busqueda
exacta en GPU toma minutos, no hace falta pagar la perdida de recall de un
indice aproximado tipo IVF/HNSW -- mismo criterio de "no sobre-ingenieria"
ya aplicado en el resto del pipeline esta semana).

Se busca TOP_K+1 vecinos por consulta y se descarta explicitamente el propio
indice de la fila (no "cualquier similitud 1.0", por si hay duplicados
exactos de titulo -- ya documentados, ~7,449 casos, ver development.md).

Diagnosticos incluidos (impresos al final, no corregidos automaticamente
todavia -- ver seccion "Pendiente" de ADR-0014, medir antes de decidir si
hace falta una segunda pasada de correccion por z-score, igual que se hizo
para Nobel en generar_nobel_cercano.py):
  1. Hubness: que tan concentrado esta el top-1 en pocas tesis "hub".
  2. Duplicados: que fraccion de tesis tiene un top-1 con similitud > 0.999
     (probable titulo identico o casi identico).

Uso local (smoke test, subconjunto real para no esperar la corrida completa):
    SAMPLE_N=20000 python pipeline/generar_vecindario_knn.py

Uso en Kaggle (corpus completo, GPU) -- estimado ~10-20 min con T4/P100 contra
~75-80 min en CPU local (medido: el trabajo es ~7.6e14 FLOPs, una GPU sostiene
varios TFLOPS en este tipo de carga). Subir este script como nueva version del
mismo dataset que ya tiene los embeddings ("sebastiandiazprado/embeddings"),
activar acelerador GPU en la configuracion del notebook, y correr como
"Save & Run All" (commit) -- NUNCA sesion interactiva/Draft, aprendido por las
malas con el incidente de HDBSCAN (ver development.md). /kaggle/working si
sobrevive una cancelacion a medio camino (confirmado esa misma sesion), asi
que los shards quedan a salvo igual que en local.

    # Celda 1 -- confirmar/instalar soporte GPU de FAISS antes de importar nada mas
    import subprocess, sys
    try:
        import faiss
        assert faiss.get_num_gpus() > 0
    except (ImportError, AssertionError):
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faiss-gpu-cu12"], check=True)
        import faiss
    print("GPUs detectadas por FAISS:", faiss.get_num_gpus())  # debe ser >0 antes de seguir

    # Celda 2 -- env vars antes de exec(), no despues
    import os
    os.environ["SOURCE_DIR"] = "/kaggle/input/datasets/sebastiandiazprado/embeddings"
    os.environ["OUTPUT_DIR"] = "/kaggle/working"
    os.environ["SHARD_DIR"] = "/kaggle/working/vecindario_shards"
    os.environ["SHARD_SIZE"] = "50000"   # mas grande que el default local (20000): en GPU cada shard
                                          # tarda segundos, no minutos -- menos archivos, mismo criterio
    os.environ["BATCH_SIZE"] = "16384"   # batches mas grandes aprovechan mejor la GPU
    # SAMPLE_N sin fijar (o "0") -- corpus completo

    # Celda 3
    exec(open("/kaggle/input/datasets/sebastiandiazprado/embeddings/generar_vecindario_knn.py").read())

    # Celda 4 (opcional, verificacion rapida antes de dar la corrida por buena)
    import pandas as pd
    r = pd.read_parquet("/kaggle/working/data/vecindario/tesis_vecindario_top100.parquet")
    print(r.shape, r.iloc[0]["neighbor_ids"][:5])

Checkpointing por shards (2026-09-22): la corrida completa en CPU local toma
~75-80 min (medido con smoke tests de 20k/100k, escala O(n^2) limpia) -- para
poder apagar la maquina a medias sin perder el avance, el resultado se
escribe en shards de SHARD_SIZE filas bajo SHARD_DIR conforme se completan,
no solo al final. Al volver a correr el script, los shards ya escritos en
disco se saltan (se detectan por nombre de archivo) y solo se calculan los
que faltan -- reanudable entre apagones, no hace falta ningun flag especial.
Al terminar todos los shards, se concatenan en OUTPUT_PATH; los shards no se
borran (mismo criterio de "no borrar hasta confirmar" ya aplicado con los
backups de este pipeline).
"""
import os
import time
from pathlib import Path

import faiss
import numpy as np
import pandas as pd

# SOURCE_DIR ya debe apuntar a la carpeta que CONTIENE los archivos de
# embeddings directamente (mismo criterio que clustering_hdbscan.py) -- en
# local es "data/embeddings"; en Kaggle es la raiz plana del dataset
# (/kaggle/input/datasets/sebastiandiazprado/embeddings), sin "data/embeddings/"
# repetido adentro. Bug real de esta sesion: la version anterior horneaba
# "data/embeddings/..." dentro del default incluso cuando SOURCE_DIR ya
# apuntaba a Kaggle, y el archivo no existia ahi con esa ruta duplicada.
SOURCE_DIR = Path(os.getenv("SOURCE_DIR", "data/embeddings"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "."))

THESIS_EMB_PATH = Path(os.getenv("THESIS_EMB_PATH", str(SOURCE_DIR / "embeddings_full_e5large.npy")))
THESIS_META_PATH = Path(os.getenv("THESIS_META_PATH", str(SOURCE_DIR / "embeddings_meta.parquet")))
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", str(OUTPUT_DIR / "data/vecindario/tesis_vecindario_top100.parquet")))
SHARD_DIR = Path(os.getenv("SHARD_DIR", str(OUTPUT_DIR / "data/vecindario/shards")))

TOP_K = int(os.getenv("TOP_K", "100"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "4096"))
SAMPLE_N = int(os.getenv("SAMPLE_N", "0"))  # 0 = corpus completo
SHARD_SIZE = int(os.getenv("SHARD_SIZE", "20000"))  # filas por shard guardado a disco


def shard_path(start: int, end: int) -> Path:
    return SHARD_DIR / f"shard_{start:07d}_{end:07d}.parquet"


def compute_shard(index, X, thesis_ids, start: int, end: int) -> pd.DataFrame:
    """Calcula el vecindario de las filas [start, end) contra el indice completo."""
    n_rows = end - start
    top_ids = np.empty((n_rows, TOP_K), dtype=object)
    top_sim = np.empty((n_rows, TOP_K), dtype="float32")

    for b_start in range(start, end, BATCH_SIZE):
        b_end = min(b_start + BATCH_SIZE, end)
        batch = X[b_start:b_end]
        sims, idx = index.search(batch, TOP_K + 1)

        for row in range(b_end - b_start):
            global_row = b_start + row
            local_row = global_row - start
            row_idx = idx[row]
            row_sim = sims[row]

            # Descartar explicitamente la propia fila, no "cualquier sim==1.0"
            # (duplicados exactos de titulo tambien dan sim==1.0 y son vecinos
            # reales, no el self-match que hay que excluir).
            keep_mask = row_idx != global_row
            row_idx = row_idx[keep_mask][:TOP_K]
            row_sim = row_sim[keep_mask][:TOP_K]

            top_ids[local_row, :len(row_idx)] = thesis_ids[row_idx]
            top_sim[local_row, :len(row_sim)] = row_sim

    return pd.DataFrame({
        "thesis_id": thesis_ids[start:end],
        "neighbor_ids": list(top_ids),
        "neighbor_similarities": list(top_sim),
    })


def main():
    t0 = time.time()
    print(f"Leyendo {THESIS_EMB_PATH}")
    X = np.load(THESIS_EMB_PATH, mmap_mode="r")
    meta = pd.read_parquet(THESIS_META_PATH, columns=["thesis_id"])
    print("Corpus completo:", X.shape)

    if SAMPLE_N and SAMPLE_N < X.shape[0]:
        rng = np.random.default_rng(42)
        sample_idx = np.sort(rng.choice(X.shape[0], size=SAMPLE_N, replace=False))
        X = np.asarray(X[sample_idx], dtype="float32")
        meta = meta.iloc[sample_idx].reset_index(drop=True)
        print(f"SAMPLE_N={SAMPLE_N} -> smoke test sobre subconjunto real, no el corpus completo")
    else:
        X = np.asarray(X, dtype="float32")

    n, dim = X.shape
    thesis_ids = meta["thesis_id"].to_numpy()

    SHARD_DIR.mkdir(parents=True, exist_ok=True)

    shard_ranges = [(s, min(s + SHARD_SIZE, n)) for s in range(0, n, SHARD_SIZE)]
    pending = [(s, e) for s, e in shard_ranges if not shard_path(s, e).exists()]
    done_count = len(shard_ranges) - len(pending)
    print(f"Shards: {len(shard_ranges)} totales ({SHARD_SIZE:,} filas c/u), {done_count} ya en disco, {len(pending)} por calcular")

    if not pending:
        print("Todos los shards ya estaban en disco -- nada que calcular, solo se re-arma el resultado final")
    else:
        print(f"Construyendo IndexFlatIP ({n:,} x {dim})")
        index = faiss.IndexFlatIP(dim)

        n_gpu = faiss.get_num_gpus()
        if n_gpu > 0:
            print(f"{n_gpu} GPU(s) detectada(s) -- moviendo el indice a GPU")
            res = faiss.StandardGpuResources()
            index = faiss.index_cpu_to_gpu(res, 0, index)
        else:
            print("Sin GPU -- corriendo en CPU (lento a escala completa, ver docstring para correr en Kaggle)")

        index.add(X)
        print(f"Indice construido en {time.time() - t0:.1f}s")

        t_search = time.time()
        for i, (start, end) in enumerate(pending):
            t_shard = time.time()
            shard_df = compute_shard(index, X, thesis_ids, start, end)
            path = shard_path(start, end)
            tmp_path = path.with_suffix(".parquet.tmp")
            shard_df.to_parquet(tmp_path, index=False)
            tmp_path.rename(path)  # escritura atomica -- un corte a medias no deja un shard corrupto a medio escribir
            elapsed_shard = time.time() - t_shard
            elapsed_total = time.time() - t_search
            done_now = done_count + i + 1
            remaining = len(shard_ranges) - done_now
            eta = (elapsed_total / (i + 1)) * remaining if i > 0 else remaining * elapsed_shard
            print(f"  shard {done_now}/{len(shard_ranges)} guardado ({end:,}/{n:,} filas) "
                  f"[{elapsed_shard:.1f}s, ETA ~{eta/60:.1f} min] -> {path.name}", flush=True)

        print(f"\nTodos los shards calculados en {(time.time() - t_search)/60:.1f} min")

    print("\nConcatenando shards en el resultado final...")
    all_shards = sorted(SHARD_DIR.glob("shard_*.parquet"))
    result = pd.concat([pd.read_parquet(p) for p in all_shards], ignore_index=True)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(OUTPUT_PATH, index=False)
    print("OK -- guardado:", OUTPUT_PATH, result.shape, "(shards intactos en", SHARD_DIR, "por si hace falta reanudar/auditar)")

    run_diagnostics(result)


def run_diagnostics(result: pd.DataFrame):
    """Medir, no asumir -- ver ADR-0014, seccion 'Pendiente'."""
    n = len(result)
    top1_sim = result["neighbor_similarities"].map(lambda arr: arr[0]).to_numpy(dtype="float32")
    top1_ids = result["neighbor_ids"].map(lambda arr: arr[0]).to_numpy()

    print("\nDistribucion de similitud del top-1 (coseno cruda):")
    print(pd.Series(top1_sim).describe())

    dup_rate = (top1_sim > 0.999).mean()
    print(f"\nPosibles duplicados/casi-duplicados: {dup_rate*100:.2f}% de tesis tienen top-1 con similitud > 0.999")

    print("\nHubness: concentracion del top-1 en pocas tesis 'hub'")
    vc = pd.Series(top1_ids).value_counts()
    top15_share = vc.head(15).sum() / n * 100
    print(f"Top 15 tesis mas repetidas como 'top-1 de alguien mas' acaparan {top15_share:.1f}% de las {n:,} asignaciones")
    print(vc.head(15))


if __name__ == "__main__":
    main()
