
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR = Path(__file__).parent

# ── Paths ─────────────────────────────────────────────────────────────
CHROMA_DB_DIR = str(BASE_DIR.parent / "data" / "chroma_db")
UPLOAD_DIR    = str(BASE_DIR / "uploads")
LOG_DIR       = str(BASE_DIR / "logs")

# ── LLM (Ollama / Qwen2.5-7b) ─────────────────────────────────────────

LLM_BASE_URL       = os.getenv("LLM_BASE_URL",    "http://localhost:11434")
LLM_MODEL_NAME     = os.getenv("LLM_MODEL_NAME",  "qwen2.5:7b")
LLM_TEMPERATURE    = float(os.getenv("LLM_TEMPERATURE",    "0.05"))   
LLM_MAX_TOKENS     = int(os.getenv("LLM_MAX_TOKENS",       "2048"))   
LLM_TIMEOUT        = int(os.getenv("LLM_TIMEOUT",          "600"))    
LLM_NUM_CTX        = int(os.getenv("LLM_NUM_CTX",          "4096"))   
LLM_REPEAT_PENALTY = float(os.getenv("LLM_REPEAT_PENALTY", "1.1"))    
LLM_TOP_P          = float(os.getenv("LLM_TOP_P",          "0.9"))   

# ── Embedding (BGE-M3) ────────────────────────────────────────────────
EMBEDDING_MODEL  = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_FP16   = os.getenv("EMBEDDING_FP16",  "true").lower() == "true"
EMBEDDING_BATCH  = int(os.getenv("EMBEDDING_BATCH",  "8"))
EMBEDDING_MAXLEN = int(os.getenv("EMBEDDING_MAXLEN", "512"))

# ── ChromaDB ──────────────────────────────────────────────────────────
CHROMA_METRIC = os.getenv("CHROMA_METRIC", "cosine")

# ── Chunking ──────────────────────────────────────────────────────────

CHUNK_MAX = int(os.getenv("CHUNK_MAX", "2500"))
CHUNK_OVL = int(os.getenv("CHUNK_OVL", "300"))
CHUNK_MIN = int(os.getenv("CHUNK_MIN",  "30"))

# ── Comparison ────────────────────────────────────────────────────────
# FIX: hạ SIM_THRESHOLD 0.78→0.75 tránh bỏ sót cặp khớp thực
SIM_THRESHOLD       = float(os.getenv("SIM_THRESHOLD",       "0.75"))
MERGE_SIM_THRESHOLD = float(os.getenv("MERGE_SIM_THRESHOLD", "0.68"))
MAX_MERGE_WINDOW    = int(os.getenv("MAX_MERGE_WINDOW",       "2"))
CITATION_MIN_LEN    = int(os.getenv("CITATION_MIN_LEN",       "15"))  
MAX_CHANGES         = int(os.getenv("MAX_CHANGES",             "50"))

# ── Severity thresholds (dùng trong comparator._infer_severity) ───────
SEVERITY_LOW_SIM_FLOOR     = float(os.getenv("SEVERITY_LOW_SIM_FLOOR",     "0.93"))
SEVERITY_LOW_RATIO_FLOOR   = float(os.getenv("SEVERITY_LOW_RATIO_FLOOR",   "0.88"))
SEVERITY_MEDIUM_SIM_FLOOR  = float(os.getenv("SEVERITY_MEDIUM_SIM_FLOOR",  "0.82"))
SEVERITY_MEDIUM_RATIO_FLOOR= float(os.getenv("SEVERITY_MEDIUM_RATIO_FLOOR","0.70"))
SEVERITY_HIGH_SIM_FLOOR    = float(os.getenv("SEVERITY_HIGH_SIM_FLOOR",    "0.70"))
SEVERITY_HIGH_RATIO_FLOOR  = float(os.getenv("SEVERITY_HIGH_RATIO_FLOOR",  "0.42"))

# ── FastAPI ───────────────────────────────────────────────────────────
API_HOST     = os.getenv("API_HOST",    "0.0.0.0")
API_PORT     = int(os.getenv("API_PORT", "8000"))
API_WORKERS  = int(os.getenv("API_WORKERS", "1"))
API_TITLE    = "Legal RAG Comparator API"
API_VERSION  = "1.0.0"
CORS_ORIGINS = ["*"]

ALLOWED_EXT = {".docx", ".pdf"}
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "20"))
