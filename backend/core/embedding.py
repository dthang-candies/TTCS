"""
backend/core/embedding.py
BGE-M3 singleton — lazy load, dùng lại suốt vòng đời app.
"""

from __future__ import annotations
import sys, os, logging
from typing import List
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)
_instance: "BGEM3Embedder | None" = None


def get_embedder() -> "BGEM3Embedder":
    global _instance
    if _instance is None:
        _instance = BGEM3Embedder()
    return _instance


class BGEM3Embedder:
    """
    Wrapper FlagEmbedding BGEM3FlagModel.
    encode_dense() trả về dense vector 1024 chiều.
    """

    def __init__(self):
        import config as cfg
        self._model_name = cfg.EMBEDDING_MODEL
        self._fp16       = cfg.EMBEDDING_FP16
        self._batch      = cfg.EMBEDDING_BATCH
        self._maxlen     = cfg.EMBEDDING_MAXLEN
        self._model      = None
        self._load()

    def _load(self):
        try:
            from FlagEmbedding import BGEM3FlagModel
            logger.info(f"Loading {self._model_name} ...")
            self._model = BGEM3FlagModel(
                self._model_name, use_fp16=self._fp16
            )
            logger.info("BGE-M3 sẵn sàng")
        except ImportError:
            raise RuntimeError("pip install FlagEmbedding")
        except Exception as e:
            logger.error(f"Load BGE-M3 thất bại: {e}")
            raise

    def encode_dense(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        out = self._model.encode(
            texts,
            batch_size=self._batch,
            max_length=self._maxlen,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return out["dense_vecs"].tolist()

    def similarity(self, a: List[float], b: List[float]) -> float:
        va, vb = np.array(a), np.array(b)
        d = np.linalg.norm(va) * np.linalg.norm(vb)
        return float(np.dot(va, vb) / d) if d > 0 else 0.0

    @property
    def is_ready(self) -> bool:
        return self._model is not None
