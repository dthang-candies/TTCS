from __future__ import annotations
import sys, os, logging
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import ChangeItem, ChangeType, Report

logger = logging.getLogger(__name__)

# Thu tu uu tien hien thi: so lieu/tien/ngay quan trong nhat
_PRIORITY = {
    ChangeType.ADDED:     1,
    ChangeType.DELETED:   1,
    ChangeType.REORDERED: 2,
    ChangeType.MODIFIED:  3,
    ChangeType.UNCHANGED: 99,
}
_MUC_DO_PRIORITY = {"cao": 1, "trung binh": 2, "thap": 3}


class Reporter:

    def __init__(self):
        from core.llm_engine import get_llm
        self.llm = get_llm()

    def build(
        self,
        session_id:  str,
        changes:     List[ChangeItem],
        name_a:      str,
        name_b:      str,
        elapsed_sec: float,
    ) -> Report:
        import config as cfg

        # Fix 2: Dedup manh hon theo noi dung trich dan thay vi chunk_index
        changes = self._dedup(changes)

        # Gioi han
        if len(changes) > cfg.MAX_CHANGES:
            logger.warning(f"Gioi han {cfg.MAX_CHANGES} (co {len(changes)})")
            changes = changes[:cfg.MAX_CHANGES]

        # Fix 1: Dem day du 5 loai ke ca REORDERED
        added     = sum(1 for c in changes if c.change_type == ChangeType.ADDED)
        deleted   = sum(1 for c in changes if c.change_type == ChangeType.DELETED)
        modified  = sum(1 for c in changes if c.change_type == ChangeType.MODIFIED)
        unchanged = sum(1 for c in changes if c.change_type == ChangeType.UNCHANGED)
        reordered = sum(1 for c in changes if c.change_type == ChangeType.REORDERED)

        logger.info(
            f"Truoc loc: total={len(changes)} "
            f"(+{added} -{deleted} ~{modified} ={unchanged} >>{reordered})"
        )

        # Tom tat LLM (dung tat ca de co du context)
        changes_dict = [
            {"change_type": c.change_type.value, "mo_ta": c.mo_ta,
             "vi_tri": c.vi_tri, "muc_do": c.muc_do}
            for c in changes
        ]
        try:
            tom_tat = self.llm.summarize(changes_dict, name_a, name_b)
        except Exception as e:
            logger.warning(f"LLM summarize loi: {e}")
            tom_tat = self._fallback_summary(added, deleted, modified, reordered)

        # Fix 3: Loc KHONG DOI ra khoi danh sach hien thi
        display_list = [c for c in changes if c.change_type != ChangeType.UNCHANGED]

        # Fix 4: Sap xep: loai quan trong truoc, trong cung loai thi muc cao truoc
        display_list.sort(key=lambda c: (
            _PRIORITY.get(c.change_type, 99),
            _MUC_DO_PRIORITY.get(c.muc_do, 3),
        ))

        logger.info(
            f"Hien thi {len(display_list)}/{len(changes)} "
            f"(bo {unchanged} KHONG DOI, con {len(display_list)} thay doi thuc su)"
        )

        report = Report(
            session_id  = session_id,
            change_list = display_list,
            tom_tat     = tom_tat,
            total       = len(changes),
            added       = added,
            deleted     = deleted,
            modified    = modified,
            unchanged   = unchanged,
            reordered   = reordered,
            elapsed_sec = round(elapsed_sec, 2),
        )
        logger.info(
            f"Report: total={len(changes)} "
            f"(+{added} -{deleted} ~{modified} ={unchanged} >>{reordered}) "
            f"| hien thi={len(display_list)} | {elapsed_sec:.1f}s"
        )
        return report

    @staticmethod
    def _dedup(changes: List[ChangeItem]) -> List[ChangeItem]:
        """
        Dedup mạnh: gộp các thay đổi cùng (vi_tri, change_type) thành 1.
        Giữ lại bản có muc_do cao nhất và mo_ta dài nhất (chất lượng tốt hơn).
        """
        _muc_do_score = {"cao": 3, "trung binh": 2, "thap": 1}

        # Bước 1: Gộp theo (vi_tri, change_type) — giữ bản tốt nhất
        best: dict[tuple, ChangeItem] = {}
        for c in changes:
            key = (c.vi_tri.strip(), c.change_type)
            if key not in best:
                best[key] = c
            else:
                old = best[key]
                old_score = _muc_do_score.get(old.muc_do, 0)
                new_score = _muc_do_score.get(c.muc_do, 0)
                # Ưu tiên: muc_do cao hơn, nếu bằng thì mo_ta dài hơn
                if new_score > old_score or (
                    new_score == old_score and len(c.mo_ta) > len(old.mo_ta)
                ):
                    best[key] = c

        result = list(best.values())

        # Bước 2: Dedup thêm theo nội dung citation (bắt trùng lặp text)
        seen: set = set()
        final: List[ChangeItem] = []
        for c in result:
            text_a = (c.citation_a.text[:80].strip() if c.citation_a else "")
            text_b = (c.citation_b.text[:80].strip() if c.citation_b else "")
            cite_key = (c.change_type, text_a, text_b)
            if cite_key not in seen:
                seen.add(cite_key)
                final.append(c)

        removed = len(changes) - len(final)
        if removed:
            logger.info(f"Dedup: loai {removed} ban trung ({len(changes)} -> {len(final)})")
        return final

    @staticmethod
    def _fallback_summary(
        added: int, deleted: int, modified: int, reordered: int = 0
    ) -> str:
        parts = []
        if added:     parts.append(f"{added} dieu khoan them moi")
        if deleted:   parts.append(f"{deleted} dieu khoan bi xoa")
        if modified:  parts.append(f"{modified} dieu khoan sua doi")
        if reordered: parts.append(f"{reordered} dieu khoan doi vi tri")
        return ("Tai lieu B so voi A: " + ", ".join(parts) + ".") if parts else "Khong co thay doi."
