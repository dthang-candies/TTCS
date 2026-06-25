"""
backend/core/embedding.py
BGE-M3 singleton — lazy load, dùng lại suốt vòng đời app.
"""

from __future__ import annotations
import sys, os, logging
from typing import List, Union
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
    Tự chọn CUDA khi khả dụng (config.EMBEDDING_DEVICE).
    """

    def __init__(self):
        import config as cfg
        self._model_name = cfg.EMBEDDING_MODEL
        self._fp16       = cfg.EMBEDDING_FP16
        self._batch      = cfg.EMBEDDING_BATCH
        self._maxlen     = cfg.EMBEDDING_MAXLEN
        self._device     = cfg.EMBEDDING_DEVICE
        self._model      = None
        self._load()

    def _load(self):
        try:
            from FlagEmbedding import BGEM3FlagModel
            logger.info(f"Loading {self._model_name} on {self._device} ...")
            self._model = BGEM3FlagModel(
                self._model_name,
                use_fp16=self._fp16,
                device=self._device,
            )
            actual = str(getattr(self._model, "device", self._device))
            logger.info(
                f"BGE-M3 sẵn sàng | device={actual} | batch={self._batch} | fp16={self._fp16}"
            )
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
        vecs = out["dense_vecs"]
        if isinstance(vecs, np.ndarray):
            return vecs.tolist()
        return vecs

    def similarity(
        self,
        a: Union[List[float], np.ndarray],
        b: Union[List[float], np.ndarray],
    ) -> float:
        va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
        d = np.linalg.norm(va) * np.linalg.norm(vb)
        return float(np.dot(va, vb) / d) if d > 0 else 0.0

    @property
    def device(self) -> str:
        return self._device

    @property
    def is_ready(self) -> bool:
        return self._model is not None
