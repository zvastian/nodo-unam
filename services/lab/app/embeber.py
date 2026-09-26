"""Embedding de la consulta con e5-large en ONNX (float32 por defecto; ver evaluar.py), sin torch.

Reproduce lo que hacía SentenceTransformer("intfloat/multilingual-e5-large"): tokenizar con
truncado a 512, promediar last_hidden_state con la máscara de atención y normalizar a norma 1.
El corpus se embebió así en float32; la consulta tiene que caer en el mismo espacio
(prueba de aceptación en evaluar.py).
"""
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

MAX_TOKENS = 512


class Embebedor:
    def __init__(self, carpeta: Path, archivo: str = "model_fp32.onnx", hilos: int = 0):
        self.tok = Tokenizer.from_file(str(carpeta / "tokenizer.json"))
        self.tok.enable_truncation(MAX_TOKENS)
        self.tok.no_padding()
        op = ort.SessionOptions()
        if hilos:
            op.intra_op_num_threads = hilos
        self.sesion = ort.InferenceSession(str(carpeta / archivo), op, providers=["CPUExecutionProvider"])

    def __call__(self, texto: str) -> np.ndarray:
        e = self.tok.encode(texto)
        ids = np.array([e.ids], dtype=np.int64)
        mascara = np.array([e.attention_mask], dtype=np.int64)
        h = self.sesion.run(None, {"input_ids": ids, "attention_mask": mascara})[0][0]
        m = mascara[0][:, None].astype(np.float32)
        v = (h * m).sum(0) / max(m.sum(), 1.0)
        return (v / np.linalg.norm(v)).astype(np.float32)
