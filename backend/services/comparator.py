from __future__ import annotations
import sys, os, logging, re, unicodedata, time
from collections import Counter
from difflib import SequenceMatcher
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import Chunk, MatchedPair, ChangeItem, ChangeType, Citation, DocSource
from services.chunker import _parse_khoan_line, _is_dieu

logger = logging.getLogger(__name__)


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
        from core.llm_engine import get_llm
        self.llm = get_llm()

    # ── Public ────────────────────────────────────────────────────────

    def compare_all(self, pairs: List[MatchedPair]) -> List[ChangeItem]:
        results: List[ChangeItem] = []
        stats = {
            "total": len(pairs), "llm_calls": 0, "fast_skip": 0,
            "fast_modified": 0, "skipped": 0, "llm_sec": 0.0,
        }
        t_all = time.perf_counter()

        for i, pair in enumerate(pairs, 1):
            t0 = time.perf_counter()
            items, call_type = self._compare_one(pair)
            pair_sec = time.perf_counter() - t0
            results.extend(items)
            if call_type == "llm":
                stats["llm_calls"] += 1
                stats["llm_sec"] += pair_sec
            elif call_type == "fast_skip":
                stats["fast_skip"] += 1
            elif call_type == "fast_modified":
                stats["fast_modified"] += 1
            else:
                stats["skipped"] += 1
            logger.info(
                f"[PROFILE] compare_pair={i}/{stats['total']} | "
                f"type={call_type} | pair_sec={pair_sec:.3f} | "
                f"context={self._pair_context(pair)}"
            )

        logger.info(
            f"[PROFILE] comparator_done | pairs={stats['total']} | "
            f"llm_calls={stats['llm_calls']} | fast_skip={stats['fast_skip']} | "
            f"fast_modified={stats['fast_modified']} | skipped={stats['skipped']} | "
            f"llm_total_sec={stats['llm_sec']:.3f} | "
            f"comparator_sec={time.perf_counter() - t_all:.3f} | "
            f"changes={len(results)}"
        )
        logger.info(f"Tổng: {len(results)} thay đổi")
        return results

    # ── Core comparison ───────────────────────────────────────────────

    def _compare_one(self, pair: MatchedPair) -> tuple[List[ChangeItem], str]:
        """Trả về (items, call_type) với call_type: llm | skip_added | skip_deleted | skip_equal."""
        if pair.chunk_a and not pair.chunk_b:
            return [self._make_deleted(pair.chunk_a)], "skip_deleted"
        if pair.chunk_b and not pair.chunk_a:
            return [self._make_added(pair.chunk_b)], "skip_added"
        if not pair.chunk_a or not pair.chunk_b:
            return [], "skip"

        ratio = self._text_ratio(pair.chunk_a.text, pair.chunk_b.text)
        # Ghép nhầm: cùng Điều nhưng khác Khoản + nội dung rất khác → XÓA (không reorder/SUA)
        if self._is_deleted_mismatch(pair, ratio):
            logger.info(
                f"[MISMATCH_DELETE] vi_tri={self._resolve_vi_tri('', pair.chunk_a, pair.chunk_a)} | "
                f"sim={pair.sim_score:.2f} ratio={ratio:.2f}"
            )
            return [self._make_deleted(pair.chunk_a)], "skip_deleted"

        items: List[ChangeItem] = []

        reorder = self._detect_reorder(pair.chunk_a, pair.chunk_b)
        if reorder:
            items.append(reorder)

        if self._normalized_equal(pair.chunk_a.text, pair.chunk_b.text):
            return items or [ChangeItem(
                change_type=ChangeType.UNCHANGED,
                mo_ta="Nội dung 2 đoạn tương đương sau khi chuẩn hóa.",
                vi_tri=self._resolve_vi_tri("", pair.chunk_a, pair.chunk_b),
                citation_a=None, citation_b=None, muc_do="thap",
            )], "skip_equal"

        sim = pair.sim_score
        has_critical = self._critical_legal_signal_changed(
            pair.chunk_a.text, pair.chunk_b.text
        )

        # Fast path: gần giống hệt, không có tín hiệu pháp lý quan trọng
        if not has_critical and (sim >= 0.97 or ratio >= 0.97):
            logger.info(
                f"[FAST_SKIP] sim={sim:.2f} ratio={ratio:.2f} "
                f"critical={has_critical} llm_called=False"
            )
            unchanged = ChangeItem(
                change_type=ChangeType.UNCHANGED,
                mo_ta="Nội dung hai đoạn gần giống nhau (độ tương đồng cao).",
                vi_tri=self._resolve_vi_tri("", pair.chunk_a, pair.chunk_b),
                citation_a=None, citation_b=None, muc_do="thap",
            )
            return (items + [unchanged]) if items else [unchanged], "fast_skip"

        # Medium path: khác biệt nhỏ, không cần LLM
        if not has_critical and sim >= 0.90:
            logger.info(
                f"[FAST_MODIFIED] sim={sim:.2f} ratio={ratio:.2f} "
                f"critical={has_critical} llm_called=False"
            )
            return items + [self._fast_modified(pair.chunk_a, pair.chunk_b)], "fast_modified"

        context = pair.chunk_a.metadata.heading_path or pair.chunk_b.metadata.heading_path
        logger.info(
            f"[LLM_COMPARE] sim={sim:.2f} ratio={ratio:.2f} "
            f"critical={has_critical} llm_called=True | context=[{context}]"
        )
        try:
            raw_items = self.llm.compare_chunks(
                pair.chunk_a.text, pair.chunk_b.text, context=context
            )
        except (TimeoutError, RuntimeError) as e:
            logger.warning(f"LLM lỗi tại [{context}]: {e}")
            return items + [self._fallback_modified(pair.chunk_a, pair.chunk_b, context, pair.sim_score)], "llm"

        for d in raw_items:
            item = self._build_item(d, pair.chunk_a, pair.chunk_b, pair.sim_score)
            if item:
                items.append(item)

        if not items:
            items.append(self._fallback_modified(pair.chunk_a, pair.chunk_b, context, pair.sim_score))

        return items, "llm"

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

    def _detect_reorder(self, ca: Chunk, cb: Chunk) -> ChangeItem | None:
        vi_tri_a = self._resolve_vi_tri("", ca, ca)
        vi_tri_b = self._resolve_vi_tri("", cb, cb)
        # Cùng Điều/Khoản/Điểm → không phải đổi vị trí (chunk_index lệch do THÊM/XÓA nơi khác)
        if vi_tri_a and vi_tri_b and vi_tri_a == vi_tri_b:
            return None

        if self._normalized_equal(ca.text, cb.text):
            return None
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

    # ── Severity logic ────────────────────────────────────────────────

    def _infer_severity(self, text_a: str, text_b: str, sim_score: float) -> tuple[str, str]:
        a_norm = self._normalize(text_a)
        b_norm = self._normalize(text_b)
        ratio  = SequenceMatcher(None, a_norm[:2000], b_norm[:2000]).ratio()

        has_critical = self._critical_legal_signal_changed(text_a, text_b)

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

    # ── Critical signal detection ─────────────────────────────────────

    @staticmethod
    def _critical_legal_signal_changed(text_a: str, text_b: str) -> bool:
        a_low = _unicode_normalize(text_a)
        b_low = _unicode_normalize(text_b)

        patterns = {
            "money":    r"\b\d[\d\.,]*\s*(?:vnd|vnđ|đồng|usd|%)\b",
            "date":     r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            "duration": r"\b\d+\s*(?:ngay|thang|nam|gio|ngày|tháng|năm|giờ)\b",
            "actor":    r"\b(?:bên a|bên b|ben a|ben b|bên mua|bên bán|ben mua|ben ban)\b",
            "negation": r"\b(?:không|khong|chưa|chua|cấm|cam|không được|khong duoc)\b",
        }
        for pat in patterns.values():
            if Counter(re.findall(pat, a_low)) != Counter(re.findall(pat, b_low)):
                return True

        # Số liệu tổng quát (FIX: dùng Counter)
        if Counter(re.findall(r"\d+(?:[\.,]\d+)?", a_low)) != \
           Counter(re.findall(r"\d+(?:[\.,]\d+)?", b_low)):
            return True

        # Từ khoá pháp lý quan trọng
        keywords = (
            "bồi thường", "boi thuong",
            "phạt vi phạm", "phat vi pham",
            "chấm dứt", "cham dut",
            "gia hạn", "thanh toán", "thanh toan",
            "nghĩa vụ", "nghia vu",
            "bảo mật", "bao mat",
            "sở hữu trí tuệ", "so huu tri tue",
            "đơn phương", "don phuong",
            "bất khả kháng", "bat kha khang",
        )
        set_a = {k for k in keywords if k in a_low}
        set_b = {k for k in keywords if k in b_low}
        return set_a != set_b

    # ── Utilities ─────────────────────────────────────────────────────

    def _text_ratio(self, text_a: str, text_b: str) -> float:
        a = self._normalize(text_a)[:2000]
        b = self._normalize(text_b)[:2000]
        return SequenceMatcher(None, a, b).ratio()

    def _fast_modified(self, ca: Chunk, cb: Chunk) -> ChangeItem:
        vi_tri = self._resolve_vi_tri("", ca, cb)
        return ChangeItem(
            change_type=ChangeType.MODIFIED,
            mo_ta=f"Thay đổi nhỏ tại: {vi_tri}" if vi_tri else "Thay đổi nhỏ về cách diễn đạt",
            vi_tri=vi_tri,
            citation_a=Citation(source=DocSource.A, text=ca.text[:220].strip(),
                                heading_path=ca.metadata.heading_path,
                                chunk_index=ca.metadata.chunk_index),
            citation_b=Citation(source=DocSource.B, text=cb.text[:220].strip(),
                                heading_path=cb.metadata.heading_path,
                                chunk_index=cb.metadata.chunk_index),
            muc_do="thap",
            ly_giai="Khác biệt nhỏ, độ tương đồng cao.",
        )

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
