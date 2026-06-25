
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ChromaDB đọc ANONYMIZED_TELEMETRY ngay lúc import module — phải set trước mọi
# `import chromadb`. https://docs.trychroma.com/telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"

BASE_DIR = Path(__file__).parent

# ── Paths ─────────────────────────────────────────────────────────────
CHROMA_DB_DIR = str(BASE_DIR.parent / "data" / "chroma_db")
UPLOAD_DIR    = str(BASE_DIR / "uploads")
LOG_DIR       = str(BASE_DIR / "logs")

# ── LLM (Ollama / Qwen2.5-7b) ─────────────────────────────────────────

LLM_BASE_URL       = os.getenv("LLM_BASE_URL",    "http://localhost:11434")
LLM_MODEL_NAME     = os.getenv("LLM_MODEL_NAME",  "qwen2.5:7b")
LLM_TEMPERATURE    = float(os.getenv("LLM_TEMPERATURE",    "0.05"))   
LLM_MAX_TOKENS     = int(os.getenv("LLM_MAX_TOKENS",       "256"))
LLM_COMPARE_MAX_CHARS = int(os.getenv("LLM_COMPARE_MAX_CHARS", "500"))   
LLM_TIMEOUT        = int(os.getenv("LLM_TIMEOUT",          "600"))    
LLM_NUM_CTX        = int(os.getenv("LLM_NUM_CTX",          "4096"))   
LLM_REPEAT_PENALTY = float(os.getenv("LLM_REPEAT_PENALTY", "1.1"))    
LLM_TOP_P          = float(os.getenv("LLM_TOP_P",          "0.9"))   
LLM_KEEP_ALIVE     = os.getenv("LLM_KEEP_ALIVE",           "30m")

# ── Embedding (BGE-M3) ────────────────────────────────────────────────
EMBEDDING_MODEL  = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_FP16   = os.getenv("EMBEDDING_FP16",  "true").lower() == "true"
EMBEDDING_MAXLEN = int(os.getenv("EMBEDDING_MAXLEN", "512"))


def _resolve_embedding_device() -> str:
    """Ưu tiên GPU (RTX 3050) khi CUDA khả dụng; override bằng EMBEDDING_DEVICE."""
    explicit = os.getenv("EMBEDDING_DEVICE", "").strip()
    if explicit:
        return explicit
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda:0"
    except ImportError:
        pass
    return "cpu"


def _resolve_embedding_batch(device: str) -> int:
    explicit = os.getenv("EMBEDDING_BATCH")
    if explicit:
        return int(explicit)
    # RTX 3050 4GB + fp16 + maxlen 512: batch 12 thường an toàn
    if device.startswith("cuda"):
        return 12
    return 8


EMBEDDING_DEVICE = _resolve_embedding_device()
EMBEDDING_BATCH  = _resolve_embedding_batch(EMBEDDING_DEVICE)

# ── ChromaDB ──────────────────────────────────────────────────────────
CHROMA_METRIC = os.getenv("CHROMA_METRIC", "cosine")
CHROMA_ANONYMIZED_TELEMETRY = False
CHROMA_UPSERT_BATCH = int(os.getenv("CHROMA_UPSERT_BATCH", "256"))


def chroma_settings():
    """Settings ChromaDB dùng chung — telemetry tắt theo tài liệu chính thức."""
    from chromadb.config import Settings
    return Settings(anonymized_telemetry=CHROMA_ANONYMIZED_TELEMETRY)

# ── Chunking ──────────────────────────────────────────────────────────

CHUNK_MAX = int(os.getenv("CHUNK_MAX", "2500"))
CHUNK_OVL = int(os.getenv("CHUNK_OVL", "300"))
CHUNK_MIN = int(os.getenv("CHUNK_MIN",  "30"))

# ── Comparison ────────────────────────────────────────────────────────
SIM_THRESHOLD       = float(os.getenv("SIM_THRESHOLD",       "0.83"))   # Tăng từ 0.75
MERGE_SIM_THRESHOLD = float(os.getenv("MERGE_SIM_THRESHOLD", "0.74"))
MAX_MERGE_WINDOW    = int(os.getenv("MAX_MERGE_WINDOW",       "2"))
CITATION_MIN_LEN    = int(os.getenv("CITATION_MIN_LEN",       "15"))  
MAX_CHANGES         = int(os.getenv("MAX_CHANGES",             "50"))

# Comparator fast/medium/LLM gates
COMPARATOR_FAST_SIM       = float(os.getenv("COMPARATOR_FAST_SIM",       "0.97"))
COMPARATOR_FAST_RATIO     = float(os.getenv("COMPARATOR_FAST_RATIO",     "0.97"))
COMPARATOR_MEDIUM_SIM     = float(os.getenv("COMPARATOR_MEDIUM_SIM",     "0.90"))
COMPARATOR_PREP_WORKERS   = int(os.getenv("COMPARATOR_PREP_WORKERS",     "4"))
COMPARATOR_LLM_SIM_FLOOR  = float(os.getenv("COMPARATOR_LLM_SIM_FLOOR",  "0.90"))
COMPARATOR_LLM_RATIO_FLOOR= float(os.getenv("COMPARATOR_LLM_RATIO_FLOOR","0.80"))
COMPARATOR_LLM_RULE_SIM   = float(os.getenv("COMPARATOR_LLM_RULE_SIM",   "0.95"))
COMPARATOR_LLM_RULE_RATIO = float(os.getenv("COMPARATOR_LLM_RULE_RATIO", "0.85"))
COMPARATOR_LLM_LONG_CHARS = int(os.getenv("COMPARATOR_LLM_LONG_CHARS",   "1000"))
COMPARATOR_LLM_LONG_RATIO = float(os.getenv("COMPARATOR_LLM_LONG_RATIO", "0.85"))
LLM_BATCH_SIZE            = int(os.getenv("LLM_BATCH_SIZE",              "5"))

# ── Severity thresholds ───────────────────────────────────────────────
SEVERITY_LOW_SIM_FLOOR     = float(os.getenv("SEVERITY_LOW_SIM_FLOOR",     "0.93"))   # Gần như giống nhau
SEVERITY_LOW_RATIO_FLOOR   = float(os.getenv("SEVERITY_LOW_RATIO_FLOOR",   "0.88"))

SEVERITY_MEDIUM_SIM_FLOOR  = float(os.getenv("SEVERITY_MEDIUM_SIM_FLOOR",  "0.84"))   # Sai nhỏ / cách diễn đạt
SEVERITY_MEDIUM_RATIO_FLOOR= float(os.getenv("SEVERITY_MEDIUM_RATIO_FLOOR","0.72"))

SEVERITY_HIGH_SIM_FLOOR    = float(os.getenv("SEVERITY_HIGH_SIM_FLOOR",    "0.78"))   # Sai quan trọng (số ngày, điều kiện...)
SEVERITY_HIGH_RATIO_FLOOR  = float(os.getenv("SEVERITY_HIGH_RATIO_FLOOR",  "0.58"))


# ── FastAPI ───────────────────────────────────────────────────────────
API_HOST     = os.getenv("API_HOST",    "0.0.0.0")
API_PORT     = int(os.getenv("API_PORT", "8000"))
API_WORKERS  = int(os.getenv("API_WORKERS", "1"))
API_TITLE    = "Legal RAG Comparator API"
API_VERSION  = "1.0.0"
CORS_ORIGINS = ["*"]

ALLOWED_EXT = {".docx", ".pdf"}
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "20"))
