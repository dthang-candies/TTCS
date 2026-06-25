from __future__ import annotations
import sys, os, logging, re
from difflib import SequenceMatcher
from typing import List, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import Chunk, MatchedPair, DocSource

logger = logging.getLogger(__name__)


class Matcher:


    def __init__(self):
        import config as cfg
        self.threshold = cfg.SIM_THRESHOLD
        self.merge_threshold = getattr(cfg, "MERGE_SIM_THRESHOLD", max(0.68, self.threshold - 0.08))
        self.max_merge_window = getattr(cfg, "MAX_MERGE_WINDOW", 2)
        from core.embedding import get_embedder
        self.embedder = get_embedder()

    def match(
        self, chunks_a: List[Chunk], chunks_b: List[Chunk],
        focus_dieu: str | None = None,
        top_k: int = 3,
    ) -> List[MatchedPair]:

        # Lọc theo điều khoản nếu có yêu cầu
        if focus_dieu:
            chunks_a = [c for c in chunks_a if focus_dieu.lower() in c.metadata.heading_path.lower()]
            chunks_b = [c for c in chunks_b if focus_dieu.lower() in c.metadata.heading_path.lower()]

        if not chunks_a and not chunks_b:
            return []

        # ── Bước 1: metadata match (cùng dieu) ───────────────────────
        pairs: List[MatchedPair] = []
        matched_a: Set[int] = set()
        matched_b: Set[int] = set()

        dieu_a = self._group_by_dieu(chunks_a)
        dieu_b = self._group_by_dieu(chunks_b)

        common_dieu = set(dieu_a.keys()) & set(dieu_b.keys())
        for dieu in common_dieu:
            ca_list = dieu_a[dieu]
            cb_list = dieu_b[dieu]
            sub_pairs, sub_ma, sub_mb = self._semantic_match(
                ca_list, cb_list, threshold=self.threshold + 0.03, strategy="same_dieu"
            )
            pairs.extend(sub_pairs)
            matched_a.update(sub_ma)
            matched_b.update(sub_mb)

        # ── Bước 2: semantic match cho các chunk còn lại ──────────────
        remaining_a = [c for c in chunks_a if id(c) not in matched_a]
        remaining_b = [c for c in chunks_b if id(c) not in matched_b]

        if remaining_a and remaining_b:
            sub_pairs, sub_ma, sub_mb = self._semantic_match(
                remaining_a, remaining_b, threshold=self.threshold, strategy="semantic"
            )
            pairs.extend(sub_pairs)
            matched_a.update(sub_ma)
            matched_b.update(sub_mb)

        # ── Bước 2b: thu hồi case 1→N / N→1 bằng cách gộp chunk liền kề ───
        remaining_a = [c for c in chunks_a if id(c) not in matched_a]
        remaining_b = [c for c in chunks_b if id(c) not in matched_b]

        merge_pairs, merge_ma, merge_mb = self._merge_recovery(remaining_a, remaining_b, top_k=top_k)
        pairs.extend(merge_pairs)
        matched_a.update(merge_ma)
        matched_b.update(merge_mb)

        # ── Bước 3: unmatched → THÊM / XÓA ───────────────────────────
        for c in chunks_a:
            if id(c) not in matched_a:
                pairs.append(MatchedPair(chunk_a=c, chunk_b=None, is_matched=False))

        for c in chunks_b:
            if id(c) not in matched_b:
                pairs.append(MatchedPair(chunk_a=None, chunk_b=c, is_matched=False))

        logger.info(
            f"Ghép: {len(pairs)} cặp "
            f"(matched={sum(1 for p in pairs if p.is_matched)}, "
            f"unmatched={sum(1 for p in pairs if not p.is_matched)})"
        )
        return pairs

    # ── Private ────────────────────────────────────────────────────────

    def _semantic_match(
        self,
        ca_list: List[Chunk],
        cb_list: List[Chunk],
        threshold: float,
        strategy: str,
    ) -> tuple[List[MatchedPair], Set[int], Set[int]]:
        """Ghép cặp tốt nhất giữa 2 list bằng cosine similarity."""
        if not ca_list or not cb_list:
            return [], set(), set()

        texts_a  = [c.text for c in ca_list]
        texts_b  = [c.text for c in cb_list]
        vecs_a   = self.embedder.encode_dense(texts_a)
        vecs_b   = self.embedder.encode_dense(texts_b)

        pairs:     List[MatchedPair] = []
        matched_a: Set[int] = set()
        matched_b: Set[int] = set()

        # Ma trận similarity (ia, ib) → score
        scores = []
        for ia, va in enumerate(vecs_a):
            for ib, vb in enumerate(vecs_b):
                semantic = self.embedder.similarity(va, vb)
                lexical = self._lexical_score(ca_list[ia].text, cb_list[ib].text)
                heading = self._heading_score(ca_list[ia], cb_list[ib])
                s = (0.78 * semantic) + (0.14 * lexical) + (0.08 * heading)
                scores.append((s, ia, ib, semantic))

        # Greedy: lấy cặp cao nhất trước
        scores.sort(reverse=True)
        for score, ia, ib, semantic in scores:
            if ia in matched_a or ib in matched_b:
                continue
            if score < threshold:
                break
            pairs.append(MatchedPair(
                chunk_a=ca_list[ia],
                chunk_b=cb_list[ib],
                sim_score=round(max(score, semantic), 4),
                is_matched=True,
                match_strategy=strategy,
            ))
            matched_a.add(ia)
            matched_b.add(ib)

        return (
            pairs,
            {id(ca_list[ia]) for ia in matched_a},
            {id(cb_list[ib]) for ib in matched_b},
        )

    @staticmethod
    def _group_by_dieu(chunks: List[Chunk]) -> dict[str, List[Chunk]]:
        groups: dict[str, List[Chunk]] = {}
        for c in chunks:
            key = c.metadata.dieu or "__no_dieu__"
            groups.setdefault(key, []).append(c)
        return groups

    def _merge_recovery(
        self,
        chunks_a: List[Chunk],
        chunks_b: List[Chunk],
        top_k: int = 3,
    ) -> Tuple[List[MatchedPair], Set[int], Set[int]]:
        if not chunks_a or not chunks_b:
            return [], set(), set()

        pairs: List[MatchedPair] = []
        matched_a: Set[int] = set()
        matched_b: Set[int] = set()

        candidates: list[tuple[float, int, Tuple[int, ...], Chunk]] = []
        for ia, chunk_a in enumerate(chunks_a):
            best = self._best_merged_candidate(chunk_a, chunks_b, top_k=top_k)
            if not best:
                continue
            score, idxs, merged_chunk = best
            if score >= self.merge_threshold:
                candidates.append((score, ia, idxs, merged_chunk))

        candidates.sort(reverse=True, key=lambda x: x[0])
        for score, ia, idxs, merged_chunk in candidates:
            if ia in matched_a or any(i in matched_b for i in idxs):
                continue
            pairs.append(MatchedPair(
                chunk_a=chunks_a[ia],
                chunk_b=merged_chunk,
                sim_score=round(score, 4),
                is_matched=True,
                match_strategy="merged_b",
            ))
            matched_a.add(ia)
            matched_b.update(idxs)

        return (
            pairs,
            {id(chunks_a[ia]) for ia in matched_a},
            {id(chunks_b[ib]) for ib in matched_b},
        )

    def _best_merged_candidate(
        self,
        source_chunk: Chunk,
        target_chunks: List[Chunk],
        top_k: int = 3,
    ) -> Tuple[float, Tuple[int, ...], Chunk] | None:
        source_vec = self.embedder.encode_dense([source_chunk.text])[0]
        singles: list[tuple[float, int]] = []
        for ib, chunk_b in enumerate(target_chunks):
            vec_b = self.embedder.encode_dense([chunk_b.text])[0]
            score = self._combined_score(source_chunk, chunk_b, source_vec=source_vec, target_vec=vec_b)
            singles.append((score, ib))

        singles.sort(reverse=True, key=lambda x: x[0])
        candidate_indices = sorted({ib for _, ib in singles[: max(top_k, self.max_merge_window + 1)]})

        best: Tuple[float, Tuple[int, ...], Chunk] | None = None
        for start in candidate_indices:
            for window in range(2, self.max_merge_window + 1):
                idxs = tuple(i for i in range(start, min(start + window, len(target_chunks))))
                if len(idxs) < 2:
                    continue
                if idxs[-1] - idxs[0] + 1 != len(idxs):
                    continue
                merged_chunk = self._merge_chunks([target_chunks[i] for i in idxs])
                merged_vec = self.embedder.encode_dense([merged_chunk.text])[0]
                score = self._combined_score(source_chunk, merged_chunk, source_vec=source_vec, target_vec=merged_vec)
                if best is None or score > best[0]:
                    best = (score, idxs, merged_chunk)

        return best

    def _combined_score(
        self,
        chunk_a: Chunk,
        chunk_b: Chunk,
        source_vec: List[float] | None = None,
        target_vec: List[float] | None = None,
    ) -> float:
        source_vec = source_vec or self.embedder.encode_dense([chunk_a.text])[0]
        target_vec = target_vec or self.embedder.encode_dense([chunk_b.text])[0]
        semantic = self.embedder.similarity(source_vec, target_vec)
        lexical = self._lexical_score(chunk_a.text, chunk_b.text)
        heading = self._heading_score(chunk_a, chunk_b)
        return (0.75 * semantic) + (0.17 * lexical) + (0.08 * heading)

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        return re.sub(r"[^\w\s%/.-]", " ", text).strip()

    def _lexical_score(self, text_a: str, text_b: str) -> float:
        na = self._normalize_text(text_a)
        nb = self._normalize_text(text_b)
        if not na or not nb:
            return 0.0
        ratio = SequenceMatcher(None, na[:1200], nb[:1200]).ratio()
        ta = set(na.split())
        tb = set(nb.split())
        jaccard = len(ta & tb) / max(1, len(ta | tb))
        return (0.7 * ratio) + (0.3 * jaccard)

    @staticmethod
    def _heading_score(chunk_a: Chunk, chunk_b: Chunk) -> float:
        score = 0.0
        if chunk_a.metadata.dieu and chunk_b.metadata.dieu:
            norm_a = chunk_a.metadata.dieu.lower().strip().rstrip(".:")
            norm_b = chunk_b.metadata.dieu.lower().strip().rstrip(".:")
            if norm_a == norm_b:
                score += 0.7
            elif Matcher._extract_number(norm_a) == Matcher._extract_number(norm_b):
                score += 0.45
        if chunk_a.metadata.khoan and chunk_b.metadata.khoan:
            if chunk_a.metadata.khoan.strip().lower() == chunk_b.metadata.khoan.strip().lower():
                score += 0.2
        if chunk_a.metadata.heading_path and chunk_b.metadata.heading_path:
            if chunk_a.metadata.heading_path.split(">")[0].strip().lower() == chunk_b.metadata.heading_path.split(">")[0].strip().lower():
                score += 0.1
        return min(score, 1.0)

    @staticmethod
    def _extract_number(text: str) -> str:
        m = re.search(r"(\d+(?:\.\d+)*)", text)
        return m.group(1) if m else ""

    @staticmethod
    def _merge_chunks(chunks: List[Chunk]) -> Chunk:
        if len(chunks) == 1:
            return chunks[0]
        first = chunks[0]
        merged_text = "\n".join(c.text for c in chunks if c.text.strip())
        merged_heading = " + ".join(c.metadata.heading_path for c in chunks if c.metadata.heading_path)
        merged_doc = "+".join(c.metadata.doc_id for c in chunks)
        return Chunk(
            text=merged_text,
            metadata=first.metadata.model_copy(
                update={
                    "doc_id": merged_doc,
                    "heading_path": merged_heading or first.metadata.heading_path,
                }
            ),
        )
