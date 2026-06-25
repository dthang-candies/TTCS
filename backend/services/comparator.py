from __future__ import annotations
import sys, os, logging, re, unicodedata, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import Chunk, MatchedPair, ChangeItem, ChangeType, Citation, DocSource
from services.chunker import _parse_khoan_line, _is_dieu

logger = logging.getLogger(__name__)

# ── Pattern rule-based (Tầng 2) ───────────────────────────────────────
# Hỗ trợ DOCX placeholder: "..10.. năm", "10 năm", "10.000.000 VNĐ"
_RE_DURATION = re.compile(
    r"\.{0,3}(\d+(?:[.,]\d+)?)\.{0,3}\s*(ngày|năm|tháng|giờ|ngay|nam|thang|gio)\b",
    re.IGNORECASE,
)
_RE_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_RE_MONEY = re.compile(r"(\d[\d.,\s]*)\s*(?:vnđ|vnd|đồng|usd)\b", re.IGNORECASE)
_RE_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")
_RE_ACTOR = re.compile(
    r"\b(bên\s+[ab]|bên\s+thuê|bên\s+cho\s+thuê|bên\s+mua|bên\s+bán|"
    r"ben\s+[ab]|ben\s+thue|ben\s+cho\s+thue)\b",
    re.IGNORECASE,
)
_RE_NEGATION = re.compile(
    r"\b(không\s+được|không|chưa|cấm|cam|khong\s+duoc|khong|chua)\b", re.IGNORECASE
)
_LEGAL_KEYWORDS = (
    "bồi thường", "boi thuong", "phạt vi phạm", "phat vi pham",
    "chấm dứt", "cham dut", "thanh toán", "thanh toan", "gia hạn", "gia han",
    "nghĩa vụ", "nghia vu", "bảo mật", "bao mat", "đơn phương", "don phuong",
)


@dataclass
class _PairEval:
    """Kết quả đánh giá local; llm_job set khi cần gọi LLM."""
    items: List[ChangeItem]
    call_type: str
    llm_job: Optional[Tuple[Chunk, Chunk, str, float, List[ChangeItem]]] = None


# ── Unicode helpers ───────────────────────────────────────────────────

def _unicode_normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text.lower())
    return text.strip()


def _citation_match(needle: str, haystack: str) -> bool:
    n = _unicode_normalize(needle[:60])
    h = _unicode_normalize(haystack)
    return n in h


class Comparator:

    def __init__(self):
        import config as cfg
        self.min_citation_len = cfg.CITATION_MIN_LEN
        # Ngưỡng severity từ config (có thể tune qua .env)
        self._low_sim    = getattr(cfg, "SEVERITY_LOW_SIM_FLOOR",     0.93)
        self._low_ratio  = getattr(cfg, "SEVERITY_LOW_RATIO_FLOOR",   0.88)
        self._med_sim    = getattr(cfg, "SEVERITY_MEDIUM_SIM_FLOOR",  0.82)
        self._med_ratio  = getattr(cfg, "SEVERITY_MEDIUM_RATIO_FLOOR",0.70)
        self._hi_sim     = getattr(cfg, "SEVERITY_HIGH_SIM_FLOOR",    0.70)
        self._hi_ratio   = getattr(cfg, "SEVERITY_HIGH_RATIO_FLOOR",  0.42)
        self._fast_sim   = getattr(cfg, "COMPARATOR_FAST_SIM",   0.97)
        self._fast_ratio = getattr(cfg, "COMPARATOR_FAST_RATIO", 0.97)
        self._medium_sim = getattr(cfg, "COMPARATOR_MEDIUM_SIM", 0.90)
        self._prep_workers = getattr(cfg, "COMPARATOR_PREP_WORKERS", 4)
        self._llm_sim_floor = getattr(cfg, "COMPARATOR_LLM_SIM_FLOOR", 0.90)
        self._llm_ratio_floor = getattr(cfg, "COMPARATOR_LLM_RATIO_FLOOR", 0.80)
        self._llm_rule_sim = getattr(cfg, "COMPARATOR_LLM_RULE_SIM", 0.95)
        self._llm_rule_ratio = getattr(cfg, "COMPARATOR_LLM_RULE_RATIO", 0.85)
        self._llm_long_chars = getattr(cfg, "COMPARATOR_LLM_LONG_CHARS", 1000)
        self._llm_long_ratio = getattr(cfg, "COMPARATOR_LLM_LONG_RATIO", 0.85)
        self._llm_batch_size = getattr(cfg, "LLM_BATCH_SIZE", 5)
        from core.llm_engine import get_llm
        self.llm = get_llm()

    # ── Public ────────────────────────────────────────────────────────

    def compare_all(self, pairs: List[MatchedPair]) -> List[ChangeItem]:
        results: List[ChangeItem] = []
        stats = {
            "total": len(pairs), "llm_calls": 0, "llm_batches": 0,
            "fast_skip": 0, "rule_based": 0, "fast_modified": 0,
            "exact": 0, "skipped": 0, "llm_sec": 0.0, "prep_sec": 0.0,
        }
        t_all = time.perf_counter()

        # Phase 1: đánh giá local song song (CPU) — không gọi LLM
        indexed: List[Tuple[int, _PairEval, float]] = []
        use_parallel = self._prep_workers > 1 and len(pairs) > 1

        if use_parallel:
            with ThreadPoolExecutor(max_workers=self._prep_workers) as pool:
                futs = {pool.submit(self._evaluate_pair, p): i for i, p in enumerate(pairs)}
                for fut in as_completed(futs):
                    i = futs[fut]
                    t0 = time.perf_counter()
                    ev = fut.result()
                    indexed.append((i, ev, time.perf_counter() - t0))
        else:
            for i, pair in enumerate(pairs):
                t0 = time.perf_counter()
                indexed.append((i, self._evaluate_pair(pair), time.perf_counter() - t0))

        indexed.sort(key=lambda x: x[0])
        stats["prep_sec"] = sum(x[2] for x in indexed)

        # Phase 2a: kết quả không cần LLM
        llm_pending: List[Tuple[int, _PairEval, float]] = []
        ordered: List[Tuple[int, List[ChangeItem], str, float, float]] = []

        for i, ev, prep_sec in indexed:
            if ev.llm_job is None:
                ordered.append((i, ev.items, ev.call_type, prep_sec, prep_sec))
                ct = ev.call_type
                if ct == "exact":
                    stats["exact"] += 1
                elif ct == "fast_skip":
                    stats["fast_skip"] += 1
                elif ct == "rule_based":
                    stats["rule_based"] += 1
                elif ct == "fast_modified":
                    stats["fast_modified"] += 1
                else:
                    stats["skipped"] += 1
            else:
                llm_pending.append((i, ev, prep_sec))

        # Phase 2b: LLM batch (tối đa LLM_BATCH_SIZE cặp / request)
        llm_results: dict[int, Tuple[List[ChangeItem], str, float]] = {}
        for b in range(0, len(llm_pending), self._llm_batch_size):
            batch = llm_pending[b: b + self._llm_batch_size]
            t0 = time.perf_counter()
            batch_out = self._finish_llm_batch([ev for _, ev, _ in batch])
            batch_sec = time.perf_counter() - t0
            stats["llm_batches"] += 1
            stats["llm_sec"] += batch_sec
            per_pair = batch_sec / len(batch)
            # batch_out luôn phải là list[(items, call_type)] — tránh zip với tuple trần
            if isinstance(batch_out, tuple):
                batch_out = [batch_out]
            for (idx, _, prep_sec), result in zip(batch, batch_out):
                if isinstance(result, tuple) and len(result) >= 2:
                    items, call_type = result[0], result[1]
                else:
                    items, call_type = result, "llm"
                llm_results[idx] = (items, call_type, per_pair)
                stats["llm_calls"] += 1

        for idx, _, prep_sec in llm_pending:
            items, call_type, pair_sec = llm_results[idx]
            ordered.append((idx, items, call_type, prep_sec, pair_sec))

        ordered.sort(key=lambda x: x[0])
        for pair_num, entry in enumerate(ordered, 1):
            i, items, call_type, prep_sec, pair_sec = entry
            results.extend(items)
            logger.info(
                f"[PROFILE] compare_pair={pair_num}/{stats['total']} | "
                f"type={call_type} | pair_sec={pair_sec:.3f} | "
                f"prep_sec={prep_sec:.3f} | context={self._pair_context(pairs[i])}"
            )

        logger.info(
            f"[PROFILE] comparator_done | pairs={stats['total']} | "
            f"llm_calls={stats['llm_calls']} | llm_batches={stats['llm_batches']} | "
            f"exact={stats['exact']} | fast_skip={stats['fast_skip']} | "
            f"rule_based={stats['rule_based']} | fast_modified={stats['fast_modified']} | "
            f"skipped={stats['skipped']} | "
            f"prep_total_sec={stats['prep_sec']:.3f} | llm_total_sec={stats['llm_sec']:.3f} | "
            f"comparator_sec={time.perf_counter() - t_all:.3f} | "
            f"prep_workers={self._prep_workers if use_parallel else 1} | "
            f"changes={len(results)}"
        )
        logger.info(f"Tổng: {len(results)} thay đổi")
        return results

    # ── Core comparison ───────────────────────────────────────────────

    def _compare_one(self, pair: MatchedPair) -> tuple[List[ChangeItem], str]:
        """Trả về (items, call_type) — giữ API nội bộ cho tương thích."""
        ev = self._evaluate_pair(pair)
        if ev.llm_job is None:
            return ev.items, ev.call_type
        return self._finish_llm(ev)

    def _evaluate_pair(self, pair: MatchedPair) -> _PairEval:
        """3 tầng: EXACT → RULE → (fast/medium) → LLM."""
        if pair.chunk_a and not pair.chunk_b:
            return _PairEval([self._make_deleted(pair.chunk_a)], "skip_deleted")
        if pair.chunk_b and not pair.chunk_a:
            return _PairEval([self._make_added(pair.chunk_b)], "skip_added")
        if not pair.chunk_a or not pair.chunk_b:
            return _PairEval([], "skip")

        ca, cb = pair.chunk_a, pair.chunk_b
        ratio = self._text_ratio(ca.text, cb.text)
        sim = pair.sim_score

        if self._is_deleted_mismatch(pair, ratio):
            logger.info(
                f"[MISMATCH_DELETE] vi_tri={self._resolve_vi_tri('', ca, ca)} | "
                f"sim={sim:.2f} ratio={ratio:.2f}"
            )
            return _PairEval([self._make_deleted(ca)], "skip_deleted")

        items: List[ChangeItem] = []
        reorder = self._detect_reorder(ca, cb, ratio=ratio)
        if reorder:
            items.append(reorder)

        # ── Tầng 1: EXACT ─────────────────────────────────────────────
        if self._normalized_equal(ca.text, cb.text):
            unchanged = items or [self._unchanged_item(ca, cb)]
            return _PairEval(unchanged, "exact")

        # ── Tầng 2: RULE số liệu (ưu tiên trước fast-skip) ────────────
        # Ví dụ Điều 3: ..10.. năm → ..100.. năm
        if self._is_simple_numeric_only_change(ca.text, cb.text):
            rule_items = self._detect_structured_changes(ca, cb, sim, ratio)
            if rule_items:
                logger.info(
                    f"[RULE_BASED] sim={sim:.2f} ratio={ratio:.2f} "
                    f"changes={len(rule_items)} llm_called=False"
                )
                return _PairEval(items + rule_items, "rule_based")

        # ── Fast path: chỉ khi KHÔNG có thay đổi số/tín hiệu pháp lý ─
        if (
            sim >= self._fast_sim
            and ratio >= self._fast_ratio
            and not self._digits_counter_changed(ca.text, cb.text)
            and not self._has_structured_signal(ca.text, cb.text)
        ):
            logger.info(
                f"[FAST_SKIP] sim={sim:.2f} ratio={ratio:.2f} llm_called=False"
            )
            out = items + [self._unchanged_item(ca, cb, fast=True)]
            return _PairEval(out, "fast_skip")

        # ── Cặp khả nghi → LLM ────────────────────────────────────────
        if self._is_suspicious_for_llm(sim, ratio, ca, cb):
            context = ca.metadata.heading_path or cb.metadata.heading_path
            logger.info(
                f"[LLM_COMPARE] sim={sim:.2f} ratio={ratio:.2f} "
                f"suspicious=True llm_called=True | context=[{context}]"
            )
            return _PairEval(items, "llm", (ca, cb, context, sim, items))

        # ── Medium path ───────────────────────────────────────────────
        if sim >= self._medium_sim:
            logger.info(
                f"[FAST_MODIFIED] sim={sim:.2f} ratio={ratio:.2f} llm_called=False"
            )
            return _PairEval(
                items + [self._heuristic_modified(ca, cb, sim, ratio)],
                "fast_modified",
            )

        # ── Fallback LLM ──────────────────────────────────────────────
        context = ca.metadata.heading_path or cb.metadata.heading_path
        logger.info(
            f"[LLM_COMPARE] sim={sim:.2f} ratio={ratio:.2f} "
            f"suspicious=fallback llm_called=True | context=[{context}]"
        )
        return _PairEval(items, "llm", (ca, cb, context, sim, items))

    @staticmethod
    def _digits_counter_changed(text_a: str, text_b: str) -> bool:
        a = _unicode_normalize(text_a)
        b = _unicode_normalize(text_b)
        return Counter(_RE_DIGITS.findall(a)) != Counter(_RE_DIGITS.findall(b))

    def _is_suspicious_for_llm(
        self, sim: float, ratio: float, ca: Chunk, cb: Chunk,
    ) -> bool:
        """Cặp khả nghi — cần LLM: thay đổi lớn, diễn đạt lại, hoặc không chỉ đổi số."""
        # Chỉ đổi số/tiền/% → rule xử lý, không LLM
        if self._is_simple_numeric_only_change(ca.text, cb.text):
            return False
        if ratio < self._llm_ratio_floor or sim < self._llm_sim_floor:
            return True
        max_len = max(len(ca.text), len(cb.text))
        if max_len > self._llm_long_chars and ratio < self._llm_long_ratio:
            return True
        if ratio < self._llm_rule_ratio or sim < self._llm_rule_sim:
            return True
        if not self._has_structured_signal(ca.text, cb.text):
            return ratio < 0.92 or sim < 0.95
        return True

    def _is_simple_numeric_only_change(self, text_a: str, text_b: str) -> bool:
        """True khi khác biệt chỉ là số liệu/tiền/tỉ lệ/thời hạn — rule xử lý được."""
        if not self._digits_counter_changed(text_a, text_b):
            return False
        a_low = _unicode_normalize(text_a)
        b_low = _unicode_normalize(text_b)
        other_diff = (
            Counter(_RE_ACTOR.findall(a_low)) != Counter(_RE_ACTOR.findall(b_low))
            or Counter(_RE_NEGATION.findall(a_low)) != Counter(_RE_NEGATION.findall(b_low))
            or {k for k in _LEGAL_KEYWORDS if k in a_low} != {k for k in _LEGAL_KEYWORDS if k in b_low}
        )
        return not other_diff

    def _needs_llm(self, sim: float, ratio: float, ca: Chunk, cb: Chunk) -> bool:
        """Legacy gate — dùng _is_suspicious_for_llm."""
        return self._is_suspicious_for_llm(sim, ratio, ca, cb)

    def _unchanged_item(
        self, ca: Chunk, cb: Chunk, fast: bool = False
    ) -> ChangeItem:
        mo_ta = (
            "Nội dung hai đoạn gần giống nhau (độ tương đồng cao)."
            if fast
            else "Nội dung 2 đoạn tương đương sau khi chuẩn hóa."
        )
        return ChangeItem(
            change_type=ChangeType.UNCHANGED,
            mo_ta=mo_ta,
            vi_tri=self._resolve_vi_tri("", ca, cb),
            citation_a=None, citation_b=None, muc_do="thap",
        )

    def _finish_llm_batch(
        self, evals: List[_PairEval]
    ) -> List[tuple[List[ChangeItem], str]]:
        jobs = [ev.llm_job for ev in evals]
        triples = [(ca.text, cb.text, ctx) for ca, cb, ctx, _, _ in jobs]  # type: ignore[misc]
        try:
            batch_raw = self.llm.compare_chunks_batch(triples)
        except (TimeoutError, RuntimeError) as e:
            logger.warning(f"LLM batch lỗi: {e}")
            batch_raw = [None] * len(jobs)

        results: List[tuple[List[ChangeItem], str]] = []
        if len(batch_raw) != len(jobs):
            logger.warning(
                f"LLM batch size mismatch: jobs={len(jobs)} raw={len(batch_raw)}"
            )
            if len(jobs) == 1 and batch_raw and isinstance(batch_raw[0], dict):
                batch_raw = [batch_raw]

        raw_aligned = batch_raw if len(batch_raw) == len(jobs) else [None] * len(jobs)
        for ev, raw_items in zip(evals, raw_aligned):
            ca, cb, context, sim, items = ev.llm_job  # type: ignore[misc]
            items = list(items)
            if raw_items is None:
                results.append((items + [self._fallback_modified(ca, cb, context, sim)], "llm"))
                continue
            if isinstance(raw_items, dict):
                raw_items = [raw_items]
            for d in raw_items:
                if isinstance(d, str):
                    d = {
                        "change_type": "SUA",
                        "mo_ta": d,
                        "vi_tri": context,
                        "trich_dan_a": ca.text[:120].strip(),
                        "trich_dan_b": cb.text[:120].strip(),
                        "muc_do": "trung binh",
                    }
                item = self._build_item(d, ca, cb, sim)
                if item:
                    items.append(item)
            if not items:
                items.append(self._fallback_modified(ca, cb, context, sim))
            results.append((items, "llm"))
        return results

    def _finish_llm(self, ev: _PairEval) -> tuple[List[ChangeItem], str]:
        return self._finish_llm_batch([ev])[0]

    @staticmethod
    def _pair_context(pair: MatchedPair) -> str:
        if pair.chunk_a:
            return pair.chunk_a.metadata.heading_path or "?"
        if pair.chunk_b:
            return pair.chunk_b.metadata.heading_path or "?"
        return "?"

    # ── Reorder detection ─────────────────────────────────────────────

    def _is_deleted_mismatch(self, pair: MatchedPair, ratio: float) -> bool:
        """Ghép nhầm giữa các Khoản/Điểm — nội dung A thực tế đã bị xóa ở B."""
        if ratio >= 0.65:
            return False
        ca, cb = pair.chunk_a, pair.chunk_b
        if not ca or not cb:
            return False
        dieu_a = self._extract_dieu_number((ca.metadata.dieu or "").strip())
        dieu_b = self._extract_dieu_number((cb.metadata.dieu or "").strip())
        same_dieu = bool(
            dieu_a and dieu_b
            and _unicode_normalize(dieu_a) == _unicode_normalize(dieu_b)
        )
        khoan_a = (ca.metadata.khoan or "").strip().rstrip(".")
        khoan_b = (cb.metadata.khoan or "").strip().rstrip(".")
        khoan_diff = bool(khoan_a and khoan_b and khoan_a != khoan_b)
        diem_a = (ca.metadata.diem or "").strip().lower()
        diem_b = (cb.metadata.diem or "").strip().lower()
        diem_diff = bool(diem_a and diem_b and diem_a != diem_b)
        if same_dieu and (khoan_diff or diem_diff):
            return True
        if dieu_a and dieu_b and not same_dieu and ratio < 0.45:
            return True
        return False

    def _detect_reorder(self, ca: Chunk, cb: Chunk, ratio: float | None = None) -> ChangeItem | None:
        vi_tri_a = self._resolve_vi_tri("", ca, ca)
        vi_tri_b = self._resolve_vi_tri("", cb, cb)
        # Cùng Điều/Khoản/Điểm → không phải đổi vị trí (chunk_index lệch do THÊM/XÓA nơi khác)
        if vi_tri_a and vi_tri_b and vi_tri_a == vi_tri_b:
            return None

        if self._normalized_equal(ca.text, cb.text):
            return None
        if ratio is None:
            ratio = self._text_ratio(ca.text, cb.text)
        if ratio >= 0.92:
            return None
        # Nội dung quá khác → không phải di chuyển (thường là ghép nhầm hoặc XÓA/THÊM)
        if ratio < 0.65:
            return None

        dieu_a = self._extract_dieu_number((ca.metadata.dieu or "").strip())
        dieu_b = self._extract_dieu_number((cb.metadata.dieu or "").strip())
        dieu_changed = bool(
            dieu_a and dieu_b
            and _unicode_normalize(dieu_a) != _unicode_normalize(dieu_b)
        )

        khoan_a = (ca.metadata.khoan or "").strip().rstrip(".")
        khoan_b = (cb.metadata.khoan or "").strip().rstrip(".")
        khoan_changed = bool(khoan_a and khoan_b and khoan_a != khoan_b)

        diem_a = (ca.metadata.diem or "").strip().lower()
        diem_b = (cb.metadata.diem or "").strip().lower()
        diem_changed = bool(diem_a and diem_b and diem_a != diem_b)

        if not dieu_changed and not khoan_changed and not diem_changed:
            return None

        if dieu_changed:
            mo_ta = f"Điều khoản đổi số thứ tự: '{dieu_a}' → '{dieu_b}'."
            vi_tri = f"{dieu_a} (A) → {dieu_b} (B)"
        else:
            mo_ta = "Nội dung tương ứng được di chuyển sang vị trí khác."
            vi_tri = f"{vi_tri_a} → {vi_tri_b}"

        return ChangeItem(
            change_type=ChangeType.REORDERED, mo_ta=mo_ta, vi_tri=vi_tri,
            citation_a=Citation(source=DocSource.A, text=ca.text[:200].strip(),
                                heading_path=ca.metadata.heading_path,
                                chunk_index=ca.metadata.chunk_index),
            citation_b=Citation(source=DocSource.B, text=cb.text[:200].strip(),
                                heading_path=cb.metadata.heading_path,
                                chunk_index=cb.metadata.chunk_index),
            muc_do="trung binh",
        )

    # ── Added / Deleted ───────────────────────────────────────────────

    def _make_deleted(self, chunk: Chunk) -> ChangeItem:
        vi_tri = self._resolve_vi_tri("", chunk, chunk)
        return ChangeItem(
            change_type=ChangeType.DELETED,
            mo_ta=f"Điều khoản bị xóa: {vi_tri}",
            vi_tri=vi_tri,
            citation_a=Citation(source=DocSource.A, text=chunk.text[:300].strip(),
                                heading_path=chunk.metadata.heading_path,
                                chunk_index=chunk.metadata.chunk_index),
            citation_b=None, muc_do="cao",
        )

    def _make_added(self, chunk: Chunk) -> ChangeItem:
        vi_tri = self._resolve_vi_tri("", chunk, chunk)
        return ChangeItem(
            change_type=ChangeType.ADDED,
            mo_ta=f"Điều khoản thêm mới: {vi_tri}",
            vi_tri=vi_tri,
            citation_a=None,
            citation_b=Citation(source=DocSource.B, text=chunk.text[:300].strip(),
                                heading_path=chunk.metadata.heading_path,
                                chunk_index=chunk.metadata.chunk_index),
            muc_do="cao",
        )

    # ── Build ChangeItem từ LLM output ───────────────────────────────

    def _build_item(self, d: dict, ca: Chunk, cb: Chunk, sim_score: float) -> ChangeItem | None:
        raw_type  = d.get("change_type", "SUA")
        _type_map = {
            "THEM":               ChangeType.ADDED,
            "XOA":                ChangeType.DELETED,
            "SUA":                ChangeType.MODIFIED,
            "KHONG DOI NOI DUNG": ChangeType.UNCHANGED,
            "KHONG_DOI":          ChangeType.UNCHANGED,
            "DOI VI TRI":         ChangeType.REORDERED,
        }
        change_type = _type_map.get(str(raw_type).strip().upper(), ChangeType.MODIFIED)

        mo_ta = d.get("mo_ta", "").strip()
        if not mo_ta:
            return None

        citation_a = self._extract_citation(
            d.get("trich_dan_a", ""), ca, DocSource.A
        )
        citation_b = self._extract_citation(
            d.get("trich_dan_b", ""), cb, DocSource.B
        )

        llm_muc_do       = d.get("muc_do", "trung binh")
        heuristic_muc_do, ly_giai = self._infer_severity(ca.text, cb.text, sim_score)
        has_critical     = self._critical_legal_signal_changed(ca.text, cb.text)
        muc_do           = self._pick_severity(
            change_type, llm_muc_do, heuristic_muc_do, has_critical
        )

        vi_tri = self._resolve_vi_tri(d.get("vi_tri", ""), ca, cb)

        return ChangeItem(
            change_type=change_type, mo_ta=mo_ta, vi_tri=vi_tri,
            citation_a=citation_a, citation_b=citation_b,
            muc_do=muc_do, ly_giai=ly_giai,
        )

    # ── Citation extraction ───────────────────────────────────────────

    def _extract_citation(
        self, trich_dan: str, chunk: Chunk, source: DocSource
    ) -> Citation | None:
        
        trich = trich_dan.strip()
        if not trich or len(trich) < self.min_citation_len:
            return None

        # Kiểm tra 60 ký tự đầu của trích dẫn có trong chunk không
        if _citation_match(trich, chunk.text):
            return Citation(
                source=source, text=trich,
                heading_path=chunk.metadata.heading_path,
                chunk_index=chunk.metadata.chunk_index,
            )

        # Fallback: tìm từ khóa dài nhất từ trich_dan trong chunk
        key = _unicode_normalize(trich[:40])
        if len(key) >= 10 and key in _unicode_normalize(chunk.text):
            return Citation(
                source=source, text=trich,
                heading_path=chunk.metadata.heading_path,
                chunk_index=chunk.metadata.chunk_index,
            )

        logger.debug(
            f"Citation {source.value} không khớp chunk [{chunk.metadata.heading_path}]: "
            f"'{trich[:50]}'"
        )
        return None

    # ── vi_tri resolution ─────────────────────────────────────────────

    @staticmethod
    def _extract_dieu_number(dieu_raw: str) -> str:
        """Trích 'Điều X' từ chuỗi dieu metadata, bỏ phần tiêu đề phía sau.
        Ví dụ: 'Điều 3. Thời hạn thuê' → 'Điều 3'
        """
        if not dieu_raw:
            return ""
        m = re.match(r"((?:Điều|Dieu|Phụ lục|Phu luc)\s+[\d\w]+)", dieu_raw, re.IGNORECASE)
        return m.group(1).strip() if m else dieu_raw.strip()

    @staticmethod
    def _infer_khoan_from_text(text: str) -> str | None:
        """Lấy số Khoản cuối cùng trong thân chunk (sửa metadata lệch khi '9.' tách dòng)."""
        last: str | None = None
        for line in text.split("\n"):
            s = line.strip()
            if not s or _is_dieu(s):
                continue
            parsed = _parse_khoan_line(s)
            if parsed:
                last = parsed[0]
        if not last:
            return None
        return last.rstrip(".").rstrip(")")

    def _resolve_vi_tri(self, llm_vi_tri: str, ca: Chunk, cb: Chunk) -> str:
        """
        Luôn build vi_tri từ metadata chunk (đáng tin cậy) thay vì dùng
        text tự do từ LLM.
        Format chuẩn: "Điều X > Khoản Y > Điểm Z"
        """
        meta = ca.metadata if ca else cb.metadata
        if not meta:
            return llm_vi_tri or ""

        chunk = ca if ca else cb
        inferred_khoan = self._infer_khoan_from_text(chunk.text) if chunk else None

        parts = []

        # Trích "Điều X" (bỏ tiêu đề dài phía sau)
        dieu_clean = self._extract_dieu_number(meta.dieu or "")
        if dieu_clean:
            parts.append(dieu_clean)

        # Ưu tiên Khoản suy ra từ thân chunk (đúng hơn metadata khi số Khoản tách dòng)
        if inferred_khoan:
            parts.append(f"Khoản {inferred_khoan}")
        elif meta.khoan:
            khoan_num = meta.khoan.rstrip(".").rstrip(")")
            parts.append(f"Khoản {khoan_num}")

        # Thêm "Điểm Z" nếu có
        if meta.diem:
            parts.append(f"Điểm {meta.diem}")

        if parts:
            return " > ".join(parts)

        # Fallback: heading_path gốc hoặc LLM
        return ca.metadata.heading_path or cb.metadata.heading_path or llm_vi_tri or ""

    # ── Rule-based structured change detection (Tầng 2) ───────────────

    def _detect_structured_changes(
        self, ca: Chunk, cb: Chunk, sim: float, ratio: float,
    ) -> Optional[List[ChangeItem]]:
        """Rule cho đổi số/tiền/%/thời hạn — không cần LLM nếu chỉ khác số."""
        if not self._is_simple_numeric_only_change(ca.text, cb.text):
            return None

        a_low = _unicode_normalize(ca.text)
        b_low = _unicode_normalize(cb.text)
        descriptions: List[str] = []

        descriptions.extend(self._diff_counter_labels(
            _RE_DURATION.findall(a_low), _RE_DURATION.findall(b_low),
            "thời hạn", lambda m: f"{m[0]} {m[1]}",
        ))
        descriptions.extend(self._diff_counter_labels(
            _RE_PERCENT.findall(a_low), _RE_PERCENT.findall(b_low),
            "tỉ lệ", lambda m: f"{m}%",
        ))
        descriptions.extend(self._diff_counter_labels(
            _RE_MONEY.findall(a_low), _RE_MONEY.findall(b_low),
            "số tiền", lambda m: (m[0] if isinstance(m, tuple) else m).strip(),
        ))

        if not descriptions:
            descriptions.extend(self._describe_digit_diff(a_low, b_low))
        if not descriptions:
            return None

        vi_tri = self._resolve_vi_tri("", ca, cb)
        mo_ta = "; ".join(descriptions[:4])
        muc_do = "cao" if any(
            x in mo_ta.lower()
            for x in ("năm", "ngày", "tháng", "%", "vnđ", "vnd", "đồng", "tiền")
        ) else "trung binh"
        snip_a, snip_b = self._diff_snippets(ca.text, cb.text)

        return [ChangeItem(
            change_type=ChangeType.MODIFIED,
            mo_ta=mo_ta,
            vi_tri=vi_tri,
            citation_a=Citation(source=DocSource.A, text=snip_a,
                                heading_path=ca.metadata.heading_path,
                                chunk_index=ca.metadata.chunk_index),
            citation_b=Citation(source=DocSource.B, text=snip_b,
                                heading_path=cb.metadata.heading_path,
                                chunk_index=cb.metadata.chunk_index),
            muc_do=muc_do,
            ly_giai="Phát hiện bằng rule (thay đổi số liệu/thời hạn/tiền/tỉ lệ).",
        )]

    @staticmethod
    def _diff_counter_labels(
        items_a: list, items_b: list, label: str, fmt,
    ) -> List[str]:
        ca, cb = Counter(items_a), Counter(items_b)
        if ca == cb:
            return []
        out: List[str] = []
        removed = list((ca - cb).elements())
        added = list((cb - ca).elements())
        if removed and added:
            out.append(
                f"Thay đổi {label}: '{fmt(removed[0])}' → '{fmt(added[0])}'"
            )
        elif removed:
            out.append(f"Bỏ {label}: '{fmt(removed[0])}'")
        elif added:
            out.append(f"Thêm {label}: '{fmt(added[0])}'")
        return out

    @staticmethod
    def _describe_digit_diff(a_low: str, b_low: str) -> List[str]:
        """Fallback mô tả khi Counter số khác nhưng regex thời hạn không khớp."""
        ca, cb = Counter(_RE_DIGITS.findall(a_low)), Counter(_RE_DIGITS.findall(b_low))
        if ca == cb:
            return []
        removed = list((ca - cb).elements())
        added = list((cb - ca).elements())
        if removed and added:
            return [f"Thay đổi số liệu: '{removed[0]}' → '{added[0]}'"]
        if removed:
            return [f"Bỏ số liệu: '{removed[0]}'"]
        if added:
            return [f"Thêm số liệu: '{added[0]}'"]
        return []

    @staticmethod
    def _has_structured_signal(text_a: str, text_b: str) -> bool:
        a_low = _unicode_normalize(text_a)
        b_low = _unicode_normalize(text_b)
        if Counter(_RE_DIGITS.findall(a_low)) != Counter(_RE_DIGITS.findall(b_low)):
            return True
        checks = [
            Counter(_RE_DURATION.findall(a_low)) != Counter(_RE_DURATION.findall(b_low)),
            Counter(_RE_PERCENT.findall(a_low)) != Counter(_RE_PERCENT.findall(b_low)),
            Counter(_RE_MONEY.findall(a_low)) != Counter(_RE_MONEY.findall(b_low)),
            Counter(_RE_ACTOR.findall(a_low)) != Counter(_RE_ACTOR.findall(b_low)),
            Counter(_RE_NEGATION.findall(a_low)) != Counter(_RE_NEGATION.findall(b_low)),
            {k for k in _LEGAL_KEYWORDS if k in a_low} != {k for k in _LEGAL_KEYWORDS if k in b_low},
        ]
        return any(checks)

    def _is_only_structured_diff(self, text_a: str, text_b: str) -> bool:
        """True nếu phần lớn khác biệt thuộc loại structured (rule)."""
        a_norm = self._normalize(text_a)
        b_norm = self._normalize(text_b)
        sm = SequenceMatcher(None, a_norm, b_norm)
        unstructured = 0
        total = max(len(a_norm), len(b_norm), 1)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            chunk_a = a_norm[i1:i2] if tag != "insert" else ""
            chunk_b = b_norm[j1:j2] if tag != "delete" else ""
            if not self._chunk_is_structured(chunk_a, chunk_b):
                unstructured += max(len(chunk_a), len(chunk_b))
        return (unstructured / total) < 0.20

    @staticmethod
    def _chunk_is_structured(chunk_a: str, chunk_b: str) -> bool:
        combined = f"{chunk_a} {chunk_b}"
        if not combined.strip():
            return True
        if len(combined.strip()) <= 40:
            return True
        for rx in (_RE_DURATION, _RE_PERCENT, _RE_MONEY, _RE_ACTOR, _RE_NEGATION):
            if rx.search(combined):
                return True
        low = combined.lower()
        if any(k in low for k in _LEGAL_KEYWORDS):
            return True
        return False

    @staticmethod
    def _diff_snippets(text_a: str, text_b: str, width: int = 220) -> tuple[str, str]:
        a_norm = text_a.lower()
        b_norm = text_b.lower()
        sm = SequenceMatcher(None, a_norm, b_norm)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("replace", "delete") and i2 > i1:
                start = max(0, i1 - 40)
                return text_a[start:i2 + 40].strip()[:width], text_b[max(0, j1 - 40):j2 + 40].strip()[:width]
            if tag == "insert" and j2 > j1:
                return text_a[max(0, i1 - 40):i1 + 40].strip()[:width], text_b[max(0, j1 - 40):j2 + 40].strip()[:width]
        return text_a.strip()[:width], text_b.strip()[:width]

    def _heuristic_modified(
        self, ca: Chunk, cb: Chunk, sim: float, ratio: float,
    ) -> ChangeItem:
        vi_tri = self._resolve_vi_tri("", ca, cb)
        muc_do, ly_giai = self._infer_severity(ca.text, cb.text, sim)
        snip_a, snip_b = self._diff_snippets(ca.text, cb.text)
        return ChangeItem(
            change_type=ChangeType.MODIFIED,
            mo_ta=f"Thay đổi tại: {vi_tri}" if vi_tri else "Nội dung thay đổi",
            vi_tri=vi_tri,
            citation_a=Citation(source=DocSource.A, text=snip_a,
                                heading_path=ca.metadata.heading_path,
                                chunk_index=ca.metadata.chunk_index),
            citation_b=Citation(source=DocSource.B, text=snip_b,
                                heading_path=cb.metadata.heading_path,
                                chunk_index=cb.metadata.chunk_index),
            muc_do=muc_do, ly_giai=ly_giai,
        )

    # ── Severity logic ────────────────────────────────────────────────

    def _infer_severity(self, text_a: str, text_b: str, sim_score: float) -> tuple[str, str]:
        a_norm = self._normalize(text_a)
        b_norm = self._normalize(text_b)
        ratio  = SequenceMatcher(None, a_norm[:2000], b_norm[:2000]).ratio()

        has_critical = self._has_structured_signal(text_a, text_b)

        # Critical signal đổi → luôn là cao
        if has_critical:
            return "cao", "Thay đổi số liệu, chủ thể, phủ định hoặc điều kiện ràng buộc."

        # FIX: dùng ngưỡng từ config thay vì hardcode
        if sim_score >= self._low_sim and ratio >= self._low_ratio:
            return "thap", "Chủ yếu thay đổi cách diễn đạt, nội dung gần tương đương."

        if sim_score >= self._med_sim and ratio >= self._med_ratio:
            return "trung binh", "Nội dung có sửa đổi một phần nhưng vẫn giữ nhiều thành phần chung."

        if sim_score < self._hi_sim or ratio < self._hi_ratio:
            return "cao", "Nội dung thay đổi lớn, có dấu hiệu viết lại hoặc lệch nghĩa."

        return "trung binh", "Độ tương đồng trung bình, cần xem xét kỹ."

    @staticmethod
    def _pick_severity(
        change_type: ChangeType,
        llm_muc_do: str,
        heuristic_muc_do: str,
        has_critical: bool,
    ) -> str:
        if change_type in (ChangeType.ADDED, ChangeType.DELETED):
            return "cao"

        order = {"thap": 1, "trung binh": 2, "cao": 3}
        llm_norm = str(llm_muc_do).strip().lower()
        if llm_norm not in order:
            llm_norm = "trung binh"

        llm_score = order[llm_norm]
        heu_score = order.get(heuristic_muc_do, 2)

        # Nếu LLM và heuristic đều đánh giá thấp → tin thap
        if llm_score == 1 and heu_score == 1 and not has_critical:
            return "thap"

        # Nếu có critical signal → ít nhất trung bình
        result_score = max(llm_score, heu_score)
        if has_critical and result_score < 2:
            result_score = 2

        return {1: "thap", 2: "trung binh", 3: "cao"}[result_score]

    # ── Legacy alias (severity / build_item) ──────────────────────────

    @staticmethod
    def _critical_legal_signal_changed(text_a: str, text_b: str) -> bool:
        return Comparator._has_structured_signal(text_a, text_b)

    # ── Utilities ─────────────────────────────────────────────────────

    def _text_ratio(self, text_a: str, text_b: str) -> float:
        a = self._normalize(text_a)[:2000]
        b = self._normalize(text_b)[:2000]
        return SequenceMatcher(None, a, b).ratio()

    def _fast_modified(self, ca: Chunk, cb: Chunk) -> ChangeItem:
        return self._heuristic_modified(ca, cb, 0.95, 0.95)

    def _fallback_modified(
        self, ca: Chunk, cb: Chunk, context: str, sim_score: float
    ) -> ChangeItem:
        has_critical     = self._critical_legal_signal_changed(ca.text, cb.text)
        muc_do, ly_giai  = self._infer_severity(ca.text, cb.text, sim_score)
        vi_tri = self._resolve_vi_tri("", ca, cb)
        return ChangeItem(
            change_type=ChangeType.MODIFIED,
            mo_ta=f"Nội dung thay đổi tại: {vi_tri}" if vi_tri else "Nội dung thay đổi",
            vi_tri=vi_tri,
            citation_a=Citation(source=DocSource.A, text=ca.text[:220].strip(),
                                heading_path=ca.metadata.heading_path,
                                chunk_index=ca.metadata.chunk_index),
            citation_b=Citation(source=DocSource.B, text=cb.text[:220].strip(),
                                heading_path=cb.metadata.heading_path,
                                chunk_index=cb.metadata.chunk_index),
            muc_do=muc_do, ly_giai=ly_giai,
        )

    @staticmethod
    def _normalized_equal(text_a: str, text_b: str) -> bool:
        def norm(text: str) -> str:
            text = _unicode_normalize(text)
            return re.sub(r"[^\w\s%/.-]", "", text).strip()
        return norm(text_a) == norm(text_b)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()
