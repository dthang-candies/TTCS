"""
backend/core/vector_db.py
ChromaDB wrapper — 1 collection / session, filter theo source A|B.
"""

from __future__ import annotations
import sys, os, logging
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import Chunk, ChunkMeta, RetrievalResult, DocSource

logger = logging.getLogger(__name__)
_client = None


def _get_client():
    global _client
    if _client is None:
        import chromadb, config as cfg
        from chromadb.config import Settings
        os.makedirs(cfg.CHROMA_DB_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=cfg.CHROMA_DB_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        logger.info(f"ChromaDB: {cfg.CHROMA_DB_DIR}")
    return _client


class VectorDB:
    def __init__(self):
        import config as cfg
        self.metric   = cfg.CHROMA_METRIC
        self.client   = _get_client()
        from core.embedding import get_embedder
        self.embedder = get_embedder()

    # ── Index ──────────────────────────────────────────────────────────

    def index_chunks(self, chunks: List[Chunk], session_id: str) -> int:
        if not chunks:
            return 0
        col   = self._col(session_id)
        texts = [c.text for c in chunks]
        ids   = [f"{c.metadata.doc_id}_{c.metadata.chunk_index}" for c in chunks]
        vecs  = self.embedder.encode_dense(texts)
        metas = [self._to_dict(c.metadata) for c in chunks]
        col.upsert(ids=ids, embeddings=vecs, documents=texts, metadatas=metas)
        logger.info(f"Indexed {len(chunks)} chunks → session={session_id}")
        return len(chunks)

    # ── Query ──────────────────────────────────────────────────────────

    def query(
        self, query_text: str, session_id: str,
        source: DocSource, top_k: int = 5,
    ) -> List[RetrievalResult]:
        col = self._col(session_id)
        n   = min(top_k, self._count(col, source))
        if n == 0:
            return []
        vec = self.embedder.encode_dense([query_text])[0]
        res = col.query(
            query_embeddings=[vec], n_results=n,
            where={"source": source.value},
            include=["documents", "metadatas", "distances"],
        )
        return [
            RetrievalResult(
                text=res["documents"][0][i],
                metadata=self._from_dict(res["metadatas"][0][i]),
                similarity=round(1 - res["distances"][0][i], 4),
            )
            for i in range(len(res["documents"][0]))
        ]

    def get_all(self, session_id: str, source: DocSource) -> List[Chunk]:
        """Lấy toàn bộ chunk của 1 tài liệu (dùng cho matcher)."""
        res = self._col(session_id).get(
            where={"source": source.value},
            include=["documents", "metadatas"],
        )
        chunks = [
            Chunk(text=t, metadata=self._from_dict(m))
            for t, m in zip(res["documents"], res["metadatas"])
        ]
        return sorted(chunks, key=lambda c: c.metadata.chunk_index)

    # ── Management ─────────────────────────────────────────────────────

    def session_exists(self, session_id: str) -> bool:
        try:
            self.client.get_collection(f"session_{session_id}")
            return True
        except Exception:
            return False

    def delete_session(self, session_id: str):
        try:
            self.client.delete_collection(f"session_{session_id}")
            logger.info(f"Đã xóa session {session_id}")
        except Exception as e:
            logger.warning(f"Xóa session lỗi: {e}")

    def chunk_counts(self, session_id: str) -> Dict[str, int]:
        col = self._col(session_id)
        a   = self._count(col, DocSource.A)
        b   = self._count(col, DocSource.B)
        return {"A": a, "B": b, "total": a + b}

    @property
    def is_ready(self) -> bool:
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False

    # ── Private ────────────────────────────────────────────────────────

    def _col(self, sid: str):
        return self.client.get_or_create_collection(
            name=f"session_{sid}",
            metadata={"hnsw:space": self.metric},
        )

    def _count(self, col, source: DocSource) -> int:
        try:
            return len(col.get(where={"source": source.value})["ids"])
        except Exception:
            return 0

    @staticmethod
    def _to_dict(m: ChunkMeta) -> dict:
        return {
            "doc_id": m.doc_id, "source": m.source.value,
            "session_id": m.session_id, "dieu": m.dieu or "",
            "khoan": m.khoan or "", "diem": m.diem or "",
            "page": m.page or 0, "chunk_index": m.chunk_index,
            "heading_path": m.heading_path,
        }

    @staticmethod
    def _from_dict(d: dict) -> ChunkMeta:
        return ChunkMeta(
            doc_id=d["doc_id"], source=DocSource(d["source"]),
            session_id=d["session_id"], dieu=d.get("dieu") or None,
            khoan=d.get("khoan") or None, diem=d.get("diem") or None,
            page=d.get("page") or None, chunk_index=d["chunk_index"],
            heading_path=d.get("heading_path", ""),
        )
