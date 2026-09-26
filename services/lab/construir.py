"""Artefactos del servicio de datos del Laboratorio (ADR-0015).

Genera en services/lab/artefactos/ todo lo que el servicio carga al arrancar; en producción
estos archivos se suben a Cloud Storage y la imagen los descarga (la imagen queda chica).

  modelo/model_fp32.onnx   e5-large exportado a ONNX en float32 (+ .data, 2.2 GB). Es el que usa
                           el servicio: las cuantizaciones probadas no pasan la prueba de evaluar.py
                           (int8 dinámico: 84 % del top-100; ver development.md, 2026-09-26)
  modelo/model_int8.onnx   int8 dinámico, solo para comparar en evaluar.py
  modelo/tokenizer.json    tokenizador rápido de e5-large
  indice_ivf_sq8.faiss     FAISS IVF (4,096 listas) con escalar de 8 bits, producto interno
  meta.parquet             una fila por vector, en el mismo orden: lo que usa el contexto
  precalculo.json          nombres de campo/tema/subtema, décadas y estadísticas de asesores

Corre con el Python del pipeline (torch, transformers, onnx, faiss), no con el del servicio,
y necesita los datos locales de data/ (no están en el repo).

Uso (desde la raíz del repo):
  python services/lab/construir.py modelo|indice|meta|todo
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "artefactos"
EMB = ROOT / "data" / "embeddings" / "embeddings_full_e5large.npy"
EMB_META = ROOT / "data" / "embeddings" / "embeddings_meta.parquet"
DATA = ROOT / "data" / "public" / "data_unam.parquet"
LAYOUT = ROOT / "data" / "clustering" / "layout_pacmap2d.parquet"
APP = ROOT / "prototypes" / "atlas_vecindario_mvp" / "data"
MODELO = "intfloat/multilingual-e5-large"
AREA_COD = {"area 1": 1, "area 2": 2, "area 3": 3, "area 4": 4}


def modelo():
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoModel, AutoTokenizer

    d = OUT / "modelo"
    d.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(MODELO)
    tok.backend_tokenizer.save(str(d / "tokenizer.json"))
    m = AutoModel.from_pretrained(MODELO).eval()

    class Envoltura(torch.nn.Module):
        """Solo last_hidden_state; el promedio con la máscara se hace en el servicio."""
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, input_ids, attention_mask):
            return self.m(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state

    ej = tok(["query: ejemplo de consulta"], return_tensors="pt")
    fp32 = d / "model_fp32.onnx"
    lote, largo = torch.export.Dim("lote", max=64), torch.export.Dim("largo", max=512)
    torch.onnx.export(
        Envoltura(m), (ej["input_ids"], ej["attention_mask"]), str(fp32),
        input_names=["input_ids", "attention_mask"], output_names=["last_hidden_state"],
        dynamic_shapes={"input_ids": {0: lote, 1: largo}, "attention_mask": {0: lote, 1: largo}},
        dynamo=True, external_data=True,
    )
    print("fp32 exportado", fp32)
    quantize_dynamic(str(fp32), str(d / "model_int8.onnx"), weight_type=QuantType.QInt8)
    print("int8", round((d / "model_int8.onnx").stat().st_size / 1e6), "MB")


def indice():
    """IVF + SQ8: con nprobe=768 da 99.1 % del top-100 exacto en 210 ms; el SQ8 plano da
    99.5 % pero tarda 750 ms (evaluar.py). El servicio fija nprobe con LAB_NPROBE."""
    import faiss

    X = np.load(EMB, mmap_mode="r")
    n, dim = X.shape
    idx = faiss.IndexIVFScalarQuantizer(faiss.IndexFlatIP(dim), dim, 4096, faiss.ScalarQuantizer.QT_8bit, faiss.METRIC_INNER_PRODUCT)
    rng = np.random.default_rng(0)
    idx.train(np.ascontiguousarray(X[np.sort(rng.choice(n, 200_000, replace=False))], dtype=np.float32))
    for i in range(0, n, 50_000):
        idx.add(np.ascontiguousarray(X[i:i + 50_000], dtype=np.float32))
    OUT.mkdir(parents=True, exist_ok=True)
    faiss.write_index(idx, str(OUT / "indice_ivf_sq8.faiss"))
    print("índice", idx.ntotal, "vectores;", round((OUT / "indice_ivf_sq8.faiss").stat().st_size / 1e6), "MB")


def cargar_micros():
    """thesis_id -> (micro, meso, macro) y los años de las tesis de cada subtema."""
    asignacion, anios = {}, {}
    for f in (APP / "tesis_por_micro").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf8"))
        cid = d["clusterId"]
        anios[cid] = [r[2] for r in d["rows"]]
        for r in d["rows"]:
            asignacion[r[0]] = (cid, d["mesoId"], d["macroId"])
    return asignacion, anios


def nombres():
    mac = json.loads((APP / "macro_nombres.v1.json").read_text(encoding="utf8"))
    macro = {int(k): v["nombre"] for k, v in mac["macros"].items()}
    meso, micro = {}, {}
    for f in (APP / "meso_by_macro").glob("*.json"):
        for n in json.loads(f.read_text(encoding="utf8"))["nodes"]:
            meso[n["clusterId"]] = n.get("name") or n["label"]
    for f in (APP / "micro_by_macro").glob("*.json"):
        for n in json.loads(f.read_text(encoding="utf8"))["nodes"]:
            micro[n["clusterId"]] = n.get("name") or n["label"]
    return macro, meso, micro


def decada(a):
    return int(a) // 10 * 10 if a and a > 1800 else None


def meta():
    """Metadatos en el orden de los vectores. Sin autores: data_unam ya no los trae."""
    ids = pd.read_parquet(EMB_META, columns=["thesis_id"])["thesis_id"]
    d = pd.read_parquet(DATA, columns=["thesis_id", "anio", "titulo_legible", "programa", "nivel", "plantel", "area", "asesores"])
    d = d.drop_duplicates("thesis_id").set_index("thesis_id").reindex(ids)
    lay = pd.read_parquet(LAYOUT).set_index("thesis_id").reindex(ids)
    asignacion, anios_micro = cargar_micros()
    asig = [asignacion.get(t, (-1, -1, -1)) for t in ids]
    m = pd.DataFrame({
        "thesis_id": ids.to_numpy(),
        "titulo": d["titulo_legible"].fillna("").to_numpy(),
        "anio": d["anio"].fillna(0).astype("int32").to_numpy(),
        "area": d["area"].fillna("").str.lower().map(AREA_COD).fillna(0).astype("int8").to_numpy(),
        "nivel": d["nivel"].fillna("").str.capitalize().to_numpy(),
        "programa": d["programa"].fillna("").to_numpy(),
        "plantel": d["plantel"].fillna("").to_numpy(),
        "asesores": d["asesores"].fillna("").to_numpy(),
        "x": lay["x"].astype("float32").to_numpy(), "y": lay["y"].astype("float32").to_numpy(),
        "micro": np.array([a[0] for a in asig], dtype="int32"),
        "meso": np.array([a[1] for a in asig], dtype="int32"),
        "macro": np.array([a[2] for a in asig], dtype="int32"),
    })
    OUT.mkdir(parents=True, exist_ok=True)
    m.to_parquet(OUT / "meta.parquet", compression="zstd", index=False)
    print("meta", len(m), "filas;", round((OUT / "meta.parquet").stat().st_size / 1e6, 1), "MB")

    # --- precálculo: lo que no depende de la consulta ---
    n_macro, n_meso, n_micro = nombres()
    corpus_dec = Counter(decada(a) for a in m["anio"])
    subtemas = {str(k): {"n": len(v), "decadas": {str(dd): c for dd, c in Counter(decada(a) for a in v).items() if dd}} for k, v in anios_micro.items()}
    total, ultimo = Counter(), defaultdict(int)
    por_anio = defaultdict(Counter)
    plantel_de, programa_de, area_de = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for s, an, pl, pr, ar in zip(m["asesores"], m["anio"], m["plantel"], m["programa"], m["area"]):
        for a in s.split("|"):
            if a.strip():
                total[a] += 1
                ultimo[a] = max(ultimo[a], int(an))
                por_anio[a][int(an)] += 1
                if pl: plantel_de[a][pl] += 1
                if pr: programa_de[a][pr] += 1
                area_de[a][int(ar)] += 1
    asesores = {a: {
        "total": total[a], "ultimo": ultimo[a],
        "por_anio": {str(k): v for k, v in sorted(por_anio[a].items()) if k > 1900},
        "plantel": plantel_de[a].most_common(1)[0][0] if plantel_de[a] else None,
        "programa": programa_de[a].most_common(1)[0][0] if programa_de[a] else None,
        "area": area_de[a].most_common(1)[0][0] if area_de[a] else 0,
    } for a in total}
    pre = {
        "nombres": {"campo": {str(k): v for k, v in n_macro.items()}, "tema": {str(k): v for k, v in n_meso.items()}, "subtema": {str(k): v for k, v in n_micro.items()}},
        "corpus_decadas": {str(k): v for k, v in corpus_dec.items() if k},
        "subtemas": subtemas,
        "asesores": asesores,
    }
    (OUT / "precalculo.json").write_text(json.dumps(pre, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    print("precálculo:", len(asesores), "asesores;", round((OUT / "precalculo.json").stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    paso = sys.argv[1] if len(sys.argv) > 1 else "todo"
    for nombre, f in [("meta", meta), ("indice", indice), ("modelo", modelo)]:
        if paso in (nombre, "todo"):
            f()
