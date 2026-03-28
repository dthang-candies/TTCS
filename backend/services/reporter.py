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
        Fix 2: Dedup theo noi dung trich dan thuc su.
        Truoc day dung chunk_index -> bi lech khi cung Dieu cat nhieu chunk.
        Bay gio dung (text_a[:80], text_b[:80]) -> bat duoc trung lap thuc su.
        """
        seen:   set              = set()
        result: List[ChangeItem] = []
        for c in changes:
            # Key: noi dung citation thuc su (cat 80 ky tu dau)
            text_a = (c.citation_a.text[:80].strip() if c.citation_a else "")
            text_b = (c.citation_b.text[:80].strip() if c.citation_b else "")
            # Them ca mo_ta de phan biet 2 thay doi khac nhau trong cung cap chunk
            key = (c.change_type, text_a, text_b, c.mo_ta[:60].strip())
            if key not in seen:
                seen.add(key)
                result.append(c)
        removed = len(changes) - len(result)
        if removed:
            logger.info(f"Dedup: loai {removed} ban trung ({len(changes)} -> {len(result)})")
        return result

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
