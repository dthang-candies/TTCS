"""
ui/api_client.py
DEMO_MODE=true  → MockClient (dữ liệu giả, delay mô phỏng)
DEMO_MODE=false → RealClient (gọi FastAPI backend)
"""

import time
import logging
import requests
from config import (
    DEMO_MODE, BACKEND_URL,
    API_TIMEOUT, API_INGEST_TIMEOUT,
)
from mock_data import MOCK_INGEST, MOCK_COMPARE

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, msg: str, code: int = 0):
        super().__init__(msg)
        self.code = code


# ── Mock ──────────────────────────────────────────────────────────────

class MockClient:

    def health(self) -> dict:
        return {
            "status": "ok", "llm_ready": True,
            "embedding_ready": True, "vectordb_ready": True,
            "message": "DEMO MODE",
        }

    def ingest(self, file_a, file_b) -> dict:
        time.sleep(1.2)
        return {**MOCK_INGEST,
                "file_a_name": file_a[0],
                "file_b_name": file_b[0]}

    def compare(self, session_id: str, focus_dieu=None, top_k: int = 5) -> dict:
        time.sleep(1.8)
        result = dict(MOCK_COMPARE)
        if focus_dieu:
            filtered = [
                c for c in result["change_list"]
                if focus_dieu.lower() in c.get("vi_tri", "").lower()
            ]
            result = {**result, "change_list": filtered,
                      "total_changes": len(filtered)}
        return result

    def retrieve(self, session_id: str, query: str, source: str, top_k: int = 5) -> dict:
        return {
            "session_id": session_id, "query": query, "source": source,
            "results": [
                {
                    "text": f"[DEMO] Kết quả {i+1} cho: '{query}'",
                    "metadata": {"heading_path": f"Điều {i+2}", "chunk_index": i, "source": source},
                    "similarity": round(0.95 - i * 0.08, 3),
                }
                for i in range(min(top_k, 3))
            ],
        }


# ── Real ──────────────────────────────────────────────────────────────

class RealClient:

    def health(self) -> dict:
        try:
            r = requests.get(f"{BACKEND_URL}/health", timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError:
            raise APIError(
                f"Không kết nối được backend tại **{BACKEND_URL}**\n\n"
                "Kiểm tra:\n"
                "- Backend có đang chạy không?\n"
                "- Nếu dùng Colab: URL ngrok còn hiệu lực không?\n"
                "- File `.env` có đúng `BACKEND_URL` không?"
            )
        except requests.Timeout:
            raise APIError("Backend không phản hồi (timeout 10s)")

    def ingest(self, file_a, file_b) -> dict:
        try:
            r = requests.post(
                f"{BACKEND_URL}/ingest",
                files={"file_a": file_a, "file_b": file_b},
                timeout=API_INGEST_TIMEOUT,
            )
            self._raise(r)
            return r.json()
        except requests.ConnectionError:
            raise APIError("Mất kết nối trong lúc upload.")
        except requests.Timeout:
            raise APIError(f"Upload timeout ({API_INGEST_TIMEOUT}s).")

    def compare(self, session_id: str, focus_dieu=None, top_k: int = 5) -> dict:
        payload = {"session_id": session_id, "top_k": top_k}
        if focus_dieu:
            payload["focus_dieu"] = focus_dieu
        try:
            r = requests.post(
                f"{BACKEND_URL}/compare",
                json=payload, timeout=API_TIMEOUT,
            )
            self._raise(r)
            return r.json()
        except requests.Timeout:
            raise APIError(f"So sánh timeout ({API_TIMEOUT}s).")

    def retrieve(self, session_id: str, query: str, source: str, top_k: int = 5) -> dict:
        r = requests.post(
            f"{BACKEND_URL}/retrieve",
            json={"session_id": session_id, "query": query,
                  "source": source, "top_k": top_k},
            timeout=API_TIMEOUT,
        )
        self._raise(r)
        return r.json()

    @staticmethod
    def _raise(r: requests.Response):
        if r.status_code == 404:
            raise APIError("Session không tồn tại.", 404)
        if r.status_code == 413:
            raise APIError("File quá lớn (> 20 MB).", 413)
        if r.status_code == 415:
            raise APIError("Định dạng file không hỗ trợ.", 415)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", "")
            except Exception:
                detail = r.text[:200]
            raise APIError(f"Lỗi {r.status_code}: {detail}", r.status_code)


# ── Singleton ─────────────────────────────────────────────────────────

_client = None

def get_client():
    global _client
    if _client is None:
        _client = MockClient() if DEMO_MODE else RealClient()
    return _client
