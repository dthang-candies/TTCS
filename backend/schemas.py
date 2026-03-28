"""
backend/schemas.py
"""
from __future__ import annotations
from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────

class ChangeType(str, Enum):
    ADDED     = "THEM"
    DELETED   = "XOA"
    MODIFIED  = "SUA"
    UNCHANGED = "KHONG DOI NOI DUNG"
    REORDERED = "DOI VI TRI"

class DocSource(str, Enum):
    A = "A"
    B = "B"


# ── Chunk ─────────────────────────────────────────────────────────────

class ChunkMeta(BaseModel):
    doc_id:       str
    source:       DocSource
    session_id:   str
    dieu:         Optional[str] = None
    khoan:        Optional[str] = None
    diem:         Optional[str] = None
    page:         Optional[int] = None
    chunk_index:  int
    heading_path: str = ""

class Chunk(BaseModel):
    text:     str
    metadata: ChunkMeta


# ── Ingest ────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    session_id:   str
    chunks_a:     int
    chunks_b:     int
    total_chunks: int
    file_a_name:  str
    file_b_name:  str
    message:      str = "Ingest thanh cong"


# ── Retrieval ─────────────────────────────────────────────────────────

class RetrievalResult(BaseModel):
    text:       str
    metadata:   ChunkMeta
    similarity: float = Field(..., ge=0.0, le=1.0)

class RetrievalRequest(BaseModel):
    session_id: str
    query:      str
    source:     DocSource
    top_k:      int = Field(default=5, ge=1, le=20)

class RetrievalResponse(BaseModel):
    session_id: str
    query:      str
    source:     DocSource
    results:    List[RetrievalResult]


# ── Comparison ────────────────────────────────────────────────────────

class Citation(BaseModel):
    source:       DocSource
    text:         str
    heading_path: str
    chunk_index:  int

# Map tat ca bien the LLM co the tra ve ve 3 gia tri hop le
_MUC_DO_MAP = {
    "cao":   "cao",
    "high":  "cao",
    "trung binh":  "trung binh",
    "medium": "trung binh",
    "tb":    "trung binh",
    "thap":  "thap",
    "low":   "thap",
}

class ChangeItem(BaseModel):
    change_type: ChangeType
    mo_ta:       str
    vi_tri:      str
    citation_a:  Optional[Citation] = None
    citation_b:  Optional[Citation] = None
    muc_do:      Literal["cao", "trung binh", "thap"] = "trung binh"
    ly_giai:     Optional[str] = None

    @field_validator("muc_do", mode="before")
    @classmethod
    def normalize_muc_do(cls, v):
        if not isinstance(v, str):
            return "trung binh"
        return _MUC_DO_MAP.get(v.strip().lower(), "trung binh")

class CompareRequest(BaseModel):
    session_id: str
    focus_dieu: Optional[str] = None
    top_k:      int = Field(default=5, ge=1, le=10)

class CompareResponse(BaseModel):
    session_id:        str
    total_changes:     int
    changes_added:     int
    changes_deleted:   int
    changes_modified:  int
    changes_unchanged: int
    changes_reordered: int = 0
    change_list:       List[ChangeItem]
    tom_tat:           str
    processing_time:   float


# ── Health ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:          Literal["ok", "degraded", "error"]
    llm_ready:       bool
    embedding_ready: bool
    vectordb_ready:  bool
    message:         str = ""

class ErrorResponse(BaseModel):
    error:  str
    detail: Optional[str] = None
    code:   int


# ── Internal ──────────────────────────────────────────────────────────

class MatchedPair(BaseModel):
    chunk_a:    Optional[Chunk] = None
    chunk_b:    Optional[Chunk] = None
    sim_score:  float = 0.0
    is_matched: bool  = True
    match_strategy: str = "semantic"

class Report(BaseModel):
    session_id:  str
    change_list: List[ChangeItem]
    tom_tat:     str
    total:       int
    added:       int
    deleted:     int
    modified:    int
    unchanged:   int
    reordered:   int = 0
    elapsed_sec: float
