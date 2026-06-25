"""
backend/main.py
FastAPI entrypoint.

Endpoints:
  GET  /health
  POST /ingest
  POST /compare
  POST /retrieve
  GET  /sessions/{id}/stats
  DELETE /sessions/{id}

Chay local  : uvicorn main:app --reload --port 8000
Chay Colab  : !uvicorn main:app --host 0.0.0.0 --port 8000 &
"""
from __future__ import annotations
import sys, os, logging, time, uuid, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as cfg

# Logging
os.makedirs(cfg.LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(cfg.LOG_DIR, "backend.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from schemas import (
    IngestResponse, CompareRequest, CompareResponse,
    RetrievalRequest, RetrievalResponse, HealthResponse, ErrorResponse,
    DocSource,
)
from core.embedding  import get_embedder
from core.vector_db  import VectorDB
from core.llm_engine import get_llm
from services.reader     import DocumentReader
from services.chunker    import Chunker
from services.matcher    import Matcher
from services.comparator import Comparator
from services.reporter   import Reporter

app = FastAPI(
    title=cfg.API_TITLE,
    version=cfg.API_VERSION,
    description="So sanh van ban phap ly tieng Viet bang RAG + LLM",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(cfg.UPLOAD_DIR,    exist_ok=True)
os.makedirs(cfg.CHROMA_DB_DIR, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────

def _validate_file(file: UploadFile):
    fname = file.filename or ""
    ext = os.path.splitext(fname)[1].lower()
    if ext not in cfg.ALLOWED_EXT:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Chi ho tro {cfg.ALLOWED_EXT}. Nhan duoc: {ext}",
        )

def _save_upload(file: UploadFile, dest: str):
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

def _check_file_size(path: str):
    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > cfg.MAX_FILE_MB:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File vuot gioi han {cfg.MAX_FILE_MB}MB (file = {size_mb:.1f}MB)",
        )


# ── Error handler ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"Unhandled: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error=type(exc).__name__, detail=str(exc), code=500).model_dump(),
    )


# ═══════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    try:
        embed_ready = get_embedder().is_ready
    except Exception:
        embed_ready = False
    try:
        db_ready = VectorDB().is_ready
    except Exception:
        db_ready = False
    try:
        llm_ready = get_llm().is_ready
    except Exception:
        llm_ready = False

    all_ok = embed_ready and db_ready and llm_ready
    return HealthResponse(
        status="ok" if all_ok else "degraded",
        llm_ready=llm_ready,
        embedding_ready=embed_ready,
        vectordb_ready=db_ready,
        message="" if all_ok else "Mot so component chua san sang",
    )


@app.post("/ingest", response_model=IngestResponse, tags=["Pipeline"])
async def ingest(
    file_a:     UploadFile = File(...),
    file_b:     UploadFile = File(...),
    session_id: str        = Form(default=""),
):
    _validate_file(file_a)
    _validate_file(file_b)

    sid      = session_id.strip() or str(uuid.uuid4())[:8]
    work_dir = os.path.join(cfg.UPLOAD_DIR, sid)
    os.makedirs(work_dir, exist_ok=True)

    path_a = os.path.join(work_dir, f"A_{file_a.filename}")
    path_b = os.path.join(work_dir, f"B_{file_b.filename}")

    _save_upload(file_a, path_a)
    _save_upload(file_b, path_b)
    _check_file_size(path_a)
    _check_file_size(path_b)

    logger.info(f"Ingest | session={sid} | A={file_a.filename} B={file_b.filename}")

    reader  = DocumentReader()
    chunker = Chunker()
    db      = VectorDB()

    if db.session_exists(sid):
        db.delete_session(sid)

    doc_a    = reader.read(path_a)
    doc_b    = reader.read(path_b)
    chunks_a = chunker.chunk(doc_a, doc_id=f"{sid}_A", source=DocSource.A, session_id=sid)
    chunks_b = chunker.chunk(doc_b, doc_id=f"{sid}_B", source=DocSource.B, session_id=sid)

    db.index_chunks(chunks_a, sid)
    db.index_chunks(chunks_b, sid)

    return IngestResponse(
        session_id=sid,
        chunks_a=len(chunks_a),
        chunks_b=len(chunks_b),
        total_chunks=len(chunks_a) + len(chunks_b),
        file_a_name=file_a.filename,
        file_b_name=file_b.filename,
    )


@app.post("/compare", response_model=CompareResponse, tags=["Pipeline"])
async def compare(req: CompareRequest):
    db = VectorDB()
    if not db.session_exists(req.session_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Session '{req.session_id}' khong ton tai. Goi /ingest truoc.",
        )

    t0 = time.time()
    logger.info(f"Compare | session={req.session_id} focus={req.focus_dieu}")

    chunks_a = db.get_all(req.session_id, DocSource.A)
    chunks_b = db.get_all(req.session_id, DocSource.B)

    pairs   = Matcher().match(chunks_a, chunks_b, focus_dieu=req.focus_dieu, top_k=req.top_k)
    changes = Comparator().compare_all(pairs)
    report  = Reporter().build(
        session_id  = req.session_id,
        changes     = changes,
        name_a      = f"Tai lieu A (session {req.session_id})",
        name_b      = f"Tai lieu B (session {req.session_id})",
        elapsed_sec = time.time() - t0,
    )

    return CompareResponse(
        session_id        = report.session_id,
        total_changes     = report.total,
        changes_added     = report.added,
        changes_deleted   = report.deleted,
        changes_modified  = report.modified,
        changes_unchanged = report.unchanged,
        changes_reordered = report.reordered,
        change_list       = report.change_list,
        tom_tat           = report.tom_tat,
        processing_time   = report.elapsed_sec,
    )


@app.post("/retrieve", response_model=RetrievalResponse, tags=["Debug"])
async def retrieve(req: RetrievalRequest):
    db = VectorDB()
    if not db.session_exists(req.session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Session khong ton tai")
    results = db.query(req.query, req.session_id, req.source, req.top_k)
    return RetrievalResponse(
        session_id=req.session_id, query=req.query,
        source=req.source, results=results,
    )


@app.get("/sessions/{session_id}/stats", tags=["Debug"])
async def session_stats(session_id: str):
    db = VectorDB()
    if not db.session_exists(session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Session khong ton tai")
    return db.chunk_counts(session_id)


@app.delete("/sessions/{session_id}", tags=["System"])
async def delete_session(session_id: str):
    VectorDB().delete_session(session_id)
    work_dir = os.path.join(cfg.UPLOAD_DIR, session_id)
    if os.path.isdir(work_dir):
        shutil.rmtree(work_dir, ignore_errors=True)
    return {"message": f"Da xoa session {session_id}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=cfg.API_HOST, port=cfg.API_PORT, workers=cfg.API_WORKERS)
