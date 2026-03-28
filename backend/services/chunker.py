from __future__ import annotations
import re, sys, os, logging
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas import Chunk, ChunkMeta, DocSource
from services.reader import ParsedDoc

logger = logging.getLogger(__name__)

RE_DIEU    = re.compile(r"^(Dieu\s+\d+[\.\:\s].{0,100})$",   re.IGNORECASE)
RE_DIEU_VN = re.compile(r"^(\u0110i\u1ec1u\s+\d+[\.\:\s].{0,100})$", re.IGNORECASE)
RE_KHOAN   = re.compile(r"^(\d+[\.\)]\s+\S.{0,100})$")
RE_DIEM    = re.compile(r"^([a-z\u0111\u0110]\)\s+.{0,100})$")
RE_PHU_LUC = re.compile(r"^(Ph\u1ee5\s*l\u1ee5c\s+[\dA-Z]+.{0,80})$", re.IGNORECASE)


def _is_dieu(s: str) -> bool:
    return bool(RE_DIEU.match(s) or RE_DIEU_VN.match(s))


class Chunker:

    def __init__(self):
        import config as cfg
        self.max_size = cfg.CHUNK_MAX
        self.overlap  = cfg.CHUNK_OVL
        self.min_size = cfg.CHUNK_MIN

    def chunk(
        self, doc: ParsedDoc, doc_id: str,
        source: DocSource, session_id: str,
    ) -> List[Chunk]:
        lines    = [p.text for p in doc.paragraphs]
        page_map = {i: p.page for i, p in enumerate(doc.paragraphs)}

        chunks = self._structural(lines, page_map, doc_id, source, session_id)
        if len(chunks) < 3:
            logger.info(f"Khong nhan cau truc ro ({doc_id}) -> sliding window")
            chunks = self._sliding("\n".join(lines), doc_id, source, session_id)

        chunks = [c for c in chunks if len(c.text.strip()) >= self.min_size]
        logger.info(f"{len(chunks)} chunks | {doc_id} source={source.value}")
        return chunks

    def _structural(
        self, lines: List[str], page_map: dict,
        doc_id: str, source: DocSource, session_id: str,
    ) -> List[Chunk]:
        chunks: List[Chunk] = []
        idx = 0
        cur_dieu:  Optional[str] = None
        cur_khoan: Optional[str] = None
        cur_diem:  Optional[str] = None
        cur_lines: List[str]     = []
        cur_page:  int           = 0

        def flush():
            nonlocal idx, cur_khoan, cur_diem
            if not cur_lines:
                return
            body = "\n".join(cur_lines).strip()
            if len(body) < self.min_size:
                return
            hp = " > ".join(p for p in [cur_dieu, cur_khoan, cur_diem] if p) \
                 or "Phan dau tai lieu"
            chunks.append(Chunk(
                text=body,
                metadata=ChunkMeta(
                    doc_id=doc_id, source=source, session_id=session_id,
                    dieu=cur_dieu, khoan=cur_khoan, diem=cur_diem,
                    page=cur_page, chunk_index=idx, heading_path=hp,
                ),
            ))
            idx += 1

        for li, line in enumerate(lines):
            s    = line.strip()
            page = page_map.get(li, 0)
            if not s:
                continue

            if RE_PHU_LUC.match(s) or _is_dieu(s):
                flush()
                cur_dieu  = s; cur_khoan = None; cur_diem = None
                cur_lines = [s]; cur_page = page

            elif RE_KHOAN.match(s) and cur_dieu:
                if len("\n".join(cur_lines)) > self.overlap:
                    flush()
                    cur_khoan = s.split()[0]; cur_diem = None
                    # Fix: giu lai tieu de Dieu hien tai de chunk con co context
                    cur_lines = ([cur_dieu] if cur_dieu else []) + [s]
                    cur_page  = page
                else:
                    cur_khoan = s.split()[0]
                    cur_lines.append(s)

            elif RE_DIEM.match(s) and cur_khoan:
                cur_diem = s[0]
                cur_lines.append(s)

            else:
                cur_lines.append(s)
                if not cur_page and page:
                    cur_page = page

            # Force flush neu chunk qua lon
            if len("\n".join(cur_lines)) > self.max_size:
                flush()
                # Fix: luon bat dau chunk moi bang tieu de Dieu
                # Dam bao chunk_index va dieu/khoan duoc giu lai dung
                header = []
                if cur_dieu:  header.append(cur_dieu)
                if cur_khoan: header.append(cur_khoan)
                # Giu 3 dong cuoi lam overlap context
                tail = cur_lines[-3:] if len(cur_lines) > 3 else cur_lines
                cur_lines = header + tail

        flush()
        return chunks

    def _sliding(
        self, text: str, doc_id: str,
        source: DocSource, session_id: str,
    ) -> List[Chunk]:
        chunks = []
        step   = self.max_size - self.overlap
        for i, start in enumerate(range(0, len(text), step)):
            snippet = text[start: start + self.max_size].strip()
            if len(snippet) < self.min_size:
                continue
            chunks.append(Chunk(
                text=snippet,
                metadata=ChunkMeta(
                    doc_id=doc_id, source=source, session_id=session_id,
                    chunk_index=i, heading_path=f"Doan {i + 1}",
                ),
            ))
        return chunks
