from __future__ import annotations
import sys, os, json, re, logging, requests, time
from typing import Optional, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger = logging.getLogger(__name__)

_instance = None

_SYS_COMPARE_BATCH = (
    "Bạn là chuyên gia kiểm tra hợp đồng tiếng Việt.\n"
    "So sánh từng CẶP BẢN A (gốc) / BẢN B (mới).\n"
    "Trả về JSON array gồm đúng N phần tử (N = số cặp).\n"
    "Mỗi phần tử là array các thay đổi của cặp tương ứng, hoặc [] nếu không đổi.\n"
    "Schema phần tử con:\n"
    '{"change_type":"SUA|THEM|XOA|KHONG_DOI","mo_ta":"...","vi_tri":"...","trich_dan_a":"...","trich_dan_b":"...","muc_do":"cao|trung binh|thap"}\n'
    "Chỉ trả JSON array, không markdown."
)


def get_llm():
    global _instance
    if _instance is None:
        _instance = LLMEngine()
    return _instance


class LLMEngine:

    _VALID_MUC_DO = ("cao", "trung binh", "thap")

    # ── System prompt tối ưu cho 7b ──────────────────────────────────
    # Ngắn hơn nhưng rõ ràng hơn → 7b tuân theo tốt hơn 14b prompt dài
    _SYS_COMPARE = (
        "Bạn là chuyên gia kiểm tra hợp đồng tiếng Việt.\n"
        "Nhiệm vụ: So sánh BẢN A (gốc) và BẢN B (mới), liệt kê TẤT CẢ sự thay đổi.\n\n"
        "QUY TẮC:\n"
        "• So sánh TỪNG CHỮ SỐ: '10 năm' vs '100 năm' → muc_do=cao\n"
        "• Phát hiện thay đổi chủ thể, phủ định, điều kiện ràng buộc\n"
        "• Chỉ trả về KHONG_DOI khi hai đoạn GIỐNG HỆT 100%\n"
        "• KHÔNG viết giải thích, KHÔNG dùng markdown\n"
        "• Chỉ trả về JSON array hợp lệ, bắt đầu bằng '[' và kết thúc bằng ']'\n\n"
        "Schema mỗi phần tử:\n"
        '{"change_type":"SUA|THEM|XOA|KHONG_DOI|DOI VI TRI","mo_ta":"...","vi_tri":"Điều X Khoản Y Điểm Z",'
        '"trich_dan_a":"nguyen van trong A","trich_dan_b":"nguyen van trong B","muc_do":"cao|trung binh|thap"}'
    )

    _SYS_SUMMARY = (
        "Bạn là trợ lý tóm tắt văn bản pháp lý tiếng Việt.\n"
        "Tóm tắt ngắn gọn, khách quan, nêu rõ điều khoản cụ thể."
    )

    def __init__(self):
        import config as cfg
        self._url    = cfg.LLM_BASE_URL
        self._model  = cfg.LLM_MODEL_NAME
        self._temp   = cfg.LLM_TEMPERATURE          # 0.05 từ config
        self._maxt   = cfg.LLM_MAX_TOKENS
        self._tout   = cfg.LLM_TIMEOUT
        self._num_ctx     = getattr(cfg, "LLM_NUM_CTX",        4096)
        self._repeat_pen  = getattr(cfg, "LLM_REPEAT_PENALTY", 1.1)
        self._top_p       = getattr(cfg, "LLM_TOP_P",          0.9)
        self._keep_alive  = getattr(cfg, "LLM_KEEP_ALIVE",     "30m")
        self._batch_size  = getattr(cfg, "LLM_BATCH_SIZE",      5)
        self._session     = requests.Session()
        self._ready = False
        self._check()

    def _check(self):
        try:
            r = requests.get(f"{self._url}/api/tags", timeout=5)
            if r.status_code == 200:
                names = [m["name"] for m in r.json().get("models", [])]
                if any(self._model in n for n in names):
                    self._ready = True
                    logger.info(
                        f"Ollama ready | {self._model} | "
                        f"temp={self._temp} num_ctx={self._num_ctx}"
                    )
                else:
                    logger.warning(f"Model chưa pull: ollama pull {self._model}")
        except requests.ConnectionError:
            logger.warning("Ollama chưa chạy. Chạy: ollama serve")

    # ── Public API ────────────────────────────────────────────────────

    def compare_chunks(self, text_a: str, text_b: str, context: str = "") -> List[dict]:
        if text_a.strip() == text_b.strip():
            return [self._no_change(context)]

        import config as cfg
        max_chars = cfg.LLM_COMPARE_MAX_CHARS
        return self._compare_single_raw(text_a, text_b, context, max_chars)

    def _compare_single_raw(
        self, text_a: str, text_b: str, context: str, max_chars: int,
    ) -> List[dict]:
        loc = f"Vị trí: {context}\n\n" if context else ""
        a_text = text_a[:max_chars].strip()
        b_text = text_b[:max_chars].strip()
        prompt = (
            f"{loc}"
            f"=== BẢN A ===\n{a_text}\n\n"
            f"=== BẢN B ===\n{b_text}\n\n"
            "Liệt kê TẤT CẢ thay đổi. Chú ý:\n"
            "- Số liệu, thời hạn, tỉ lệ\n"
            "- Chủ thể hành động (Bên A/Bên B)\n"
            "- Điều kiện ràng buộc, phủ định\n\n"
            "Trả về JSON array. Trả về [] nếu không có thay đổi."
        )
        prompt_len = len(prompt) + len(self._SYS_COMPARE)
        logger.info(
            f"[PROFILE] llm_compare_start | context=[{context}] | "
            f"prompt_chars={prompt_len} | a_chars={len(a_text)} | b_chars={len(b_text)}"
        )
        t0 = time.perf_counter()
        raw = self._chat(prompt, self._SYS_COMPARE)
        llm_sec = time.perf_counter() - t0
        items = [self._fix_item(d) for d in self._parse_list(raw)]
        logger.info(
            f"[PROFILE] llm_compare_done | context=[{context}] | "
            f"llm_sec={llm_sec:.3f} | parsed_items={len(items)} | raw_chars={len(raw)}"
        )
        if not items:
            reason = self._diagnose_parse(raw)
            logger.warning(
                f"LLM trả [] tại [{context}] — fallback SUA | reason={reason} | "
                f"preview={raw[:200]!r}"
            )
            items = [{
                "change_type": "SUA",
                "mo_ta": f"Nội dung thay đổi tại: {context}" if context else "Nội dung thay đổi",
                "vi_tri": context,
                "trich_dan_a": _safe_truncate(text_a, 120),
                "trich_dan_b": _safe_truncate(text_b, 120),
                "muc_do": "trung binh",
            }]
        return items

    def compare_chunks_batch(
        self,
        pairs: List[Tuple[str, str, str]],
    ) -> List[List[dict]]:
        """So sánh tối đa LLM_BATCH_SIZE cặp trong một request Ollama."""
        if not pairs:
            return []
        import config as cfg
        max_chars = cfg.LLM_COMPARE_MAX_CHARS

        # Luôn dùng một code path — kể cả 1 cặp — trả về List[List[dict]]
        if len(pairs) == 1:
            text_a, text_b, context = pairs[0]
            return [self._compare_single_raw(text_a, text_b, context, max_chars)]
        sections: List[str] = []
        for idx, (text_a, text_b, context) in enumerate(pairs, 1):
            a_text = text_a[:max_chars].strip()
            b_text = text_b[:max_chars].strip()
            loc = f"Vị trí: {context}" if context else f"Cặp {idx}"
            sections.append(
                f"=== CẶP {idx} | {loc} ===\n"
                f"BẢN A:\n{a_text}\n\n"
                f"BẢN B:\n{b_text}"
            )

        prompt = (
            f"So sánh {len(pairs)} cặp đoạn văn bản pháp lý.\n\n"
            + "\n\n".join(sections)
            + f"\n\nTrả về JSON array gồm đúng {len(pairs)} phần tử. "
            f"Mỗi phần tử là array object thay đổi (hoặc []).\n"
            f'Ví dụ: [[{{"change_type":"SUA","mo_ta":"...","vi_tri":"...","trich_dan_a":"...","trich_dan_b":"...","muc_do":"cao"}}], []]'
        )

        logger.info(
            f"[PROFILE] llm_batch_start | pairs={len(pairs)} | "
            f"prompt_chars={len(prompt) + len(_SYS_COMPARE_BATCH)}"
        )
        t0 = time.perf_counter()
        raw = self._chat(prompt, _SYS_COMPARE_BATCH)
        llm_sec = time.perf_counter() - t0

        parsed = self._parse_batch(raw, len(pairs))
        out: List[List[dict]] = []
        for i, (text_a, text_b, context) in enumerate(pairs):
            items = [self._fix_item(d) for d in self._normalize_batch_items(parsed[i], context, text_a, text_b)]
            if not items and text_a.strip() != text_b.strip():
                items = [{
                    "change_type": "SUA",
                    "mo_ta": f"Nội dung thay đổi tại: {context}" if context else "Nội dung thay đổi",
                    "vi_tri": context,
                    "trich_dan_a": _safe_truncate(text_a, 120),
                    "trich_dan_b": _safe_truncate(text_b, 120),
                    "muc_do": "trung binh",
                }]
            out.append(items)

        logger.info(
            f"[PROFILE] llm_batch_done | pairs={len(pairs)} | llm_sec={llm_sec:.3f} | "
            f"total_items={sum(len(x) for x in out)}"
        )
        return out

    def summarize(self, changes: List[dict], name_a: str, name_b: str) -> str:
        if not changes:
            return "Không phát hiện thay đổi đáng kể."
        meaningful = [c for c in changes if c.get("change_type") not in ("KHONG_DOI", "KHONG DOI NOI DUNG")]
        if not meaningful:
            return "Hai tài liệu có nội dung tương đương."
        prompt = (
            f"Tài liệu gốc: {name_a}\n"
            f"Tài liệu mới: {name_b}\n\n"
            f"Danh sách thay đổi:\n"
            f"{json.dumps(meaningful[:12], ensure_ascii=False, indent=2)}\n\n"
            "Viết tóm tắt 3-5 câu về các thay đổi quan trọng nhất. "
            "Nêu rõ điều khoản cụ thể và mức độ ảnh hưởng."
        )
        return self._chat(prompt, self._SYS_SUMMARY)

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ── Private helpers ───────────────────────────────────────────────

    def _fix_item(self, d: dict) -> dict:
        """Chuẩn hoá muc_do và change_type về dạng lowercase không dấu."""
        raw_muc_do = re.sub(r"\s+", " ", str(d.get("muc_do", "")).strip().lower())
        _muc_map = {
            "cao": "cao", "high": "cao", "3": "cao",
            "trung binh": "trung binh", "trung bình": "trung binh",
            "medium": "trung binh", "tb": "trung binh", "2": "trung binh",
            "thap": "thap", "thấp": "thap", "low": "thap", "1": "thap",
        }
        d["muc_do"] = _muc_map.get(raw_muc_do, "trung binh")

        # Chuẩn hoá change_type
        raw_ct = str(d.get("change_type", "SUA")).strip().upper()
        _ct_map = {
            "SUA": "SUA", "MODIFIED": "SUA",
            "THEM": "THEM", "ADDED": "THEM", "THÊM": "THEM",
            "XOA": "XOA", "DELETED": "XOA", "XÓA": "XOA",
            "KHONG_DOI": "KHONG DOI NOI DUNG",
            "KHONG DOI NOI DUNG": "KHONG DOI NOI DUNG",
            "DOI_VI_TRI" : "DOI VI TRI", "DOI VI TRI": "REORDER",
            "UNCHANGED": "KHONG DOI NOI DUNG",
        }
        d["change_type"] = _ct_map.get(raw_ct, "SUA")
        return d

    def _no_change(self, context: str) -> dict:
        return {
            "change_type": "KHONG DOI NOI DUNG",
            "mo_ta": "Nội dung 2 đoạn giống nhau.",
            "vi_tri": context,
            "trich_dan_a": "",
            "trich_dan_b": "",
            "muc_do": "thap",
        }

    def _estimate_num_ctx(self, prompt: str, system: Optional[str] = None) -> int:
        """num_ctx vừa đủ prompt → giảm thời gian prefill trên GPU nhỏ."""
        total_chars = len(prompt) + (len(system) if system else 0)
        est_tokens = total_chars // 3 + self._maxt + 128
        rounded = max(1024, ((est_tokens + 255) // 256) * 256)
        return min(self._num_ctx, rounded)

    def _chat(self, prompt: str, system: Optional[str] = None) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        total_chars = len(prompt) + (len(system) if system else 0)
        num_ctx = self._estimate_num_ctx(prompt, system)
        try:
            t0 = time.perf_counter()
            r = self._session.post(
                f"{self._url}/api/chat",
                json={
                    "model": self._model,
                    "messages": msgs,
                    "stream": False,
                    "keep_alive": self._keep_alive,
                    "options": {
                        "temperature":    self._temp,
                        "num_predict":    self._maxt,
                        "num_ctx":        num_ctx,
                        "repeat_penalty": self._repeat_pen,
                        "top_p":          self._top_p,
                    },
                },
                timeout=self._tout,
            )
            llm_sec = time.perf_counter() - t0
            r.raise_for_status()
            raw = r.json()["message"]["content"].strip()
            logger.info(
                f"[PROFILE] ollama_chat | llm_sec={llm_sec:.3f} | "
                f"prompt_chars={total_chars} | num_ctx={num_ctx} | "
                f"response_chars={len(raw)} | "
                f"timeout_cfg={self._tout}s | preview={raw[:300]!r}"
            )
            return raw
        except requests.Timeout:
            logger.error(
                f"[PROFILE] ollama_timeout | elapsed>={self._tout}s | "
                f"prompt_chars={total_chars}"
            )
            raise TimeoutError(f"LLM timeout sau {self._tout}s.")
        except requests.HTTPError as e:
            raise RuntimeError(f"Ollama HTTP error: {e}")

    @staticmethod
    def _parse_list(raw: str) -> List[dict]:
        """
        Parse JSON array từ output của Qwen2.5-7b.
        Qwen hay thêm text trước/sau JSON → cần extract mạnh hơn.
        """
        # Bước 1: bỏ markdown fences
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        cleaned = re.sub(r"```\s*$",         "", cleaned).strip()

        # Bước 2: tìm đoạn bắt đầu bằng '[' đầu tiên → kết thúc bằng ']' cuối
        start = cleaned.find("[")
        end   = cleaned.rfind("]")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start: end + 1]
            try:
                data = json.loads(candidate)
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict) and "change_type" in x]
            except json.JSONDecodeError:
                pass

        # Bước 3: thử sửa JSON lỗi phổ biến (trailing comma, single-quote)
        try:
            fixed = re.sub(r",\s*([\]}])", r"\1", cleaned)   # trailing comma
            fixed = fixed.replace("'", '"')                   # single → double quote
            start2 = fixed.find("[")
            end2   = fixed.rfind("]")
            if start2 != -1 and end2 > start2:
                data = json.loads(fixed[start2: end2 + 1])
                if isinstance(data, list):
                    return [x for x in data if isinstance(x, dict) and "change_type" in x]
        except json.JSONDecodeError:
            pass

        # Bước 4: tách từng object riêng lẻ
        result = []
        for obj_str in re.findall(r"\{[^{}]+\}", cleaned, re.DOTALL):
            try:
                obj = json.loads(obj_str)
                if isinstance(obj, dict) and "change_type" in obj:
                    result.append(obj)
            except json.JSONDecodeError:
                continue
        return result

    @staticmethod
    def _diagnose_parse(raw: str) -> str:
        """Chẩn đoán lý do parse trả rỗng — chỉ dùng cho log."""
        if not raw or not raw.strip():
            return "empty_response"
        stripped = raw.strip()
        if stripped == "[]":
            return "literal_empty_array"
        if "[" not in raw and "{" not in raw:
            return "no_json_structure"
        if "[" in raw and "change_type" not in raw:
            return "json_without_change_type"
        if "change_type" in raw:
            return "json_parse_failed_or_invalid_schema"
        return "unknown"

    def _normalize_batch_items(
        self, raw_items: list, context: str, text_a: str, text_b: str,
    ) -> List[dict]:
        """Chuyển string / object lẫn lộn từ batch LLM thành list dict chuẩn."""
        out: List[dict] = []
        for d in raw_items:
            if isinstance(d, dict) and d.get("change_type"):
                out.append(d)
            elif isinstance(d, str) and d.strip():
                out.append({
                    "change_type": "SUA",
                    "mo_ta": d.strip(),
                    "vi_tri": context,
                    "trich_dan_a": _safe_truncate(text_a, 120),
                    "trich_dan_b": _safe_truncate(text_b, 120),
                    "muc_do": "trung binh",
                })
        return out

    def _parse_batch(self, raw: str, expected: int) -> List[List[dict]]:
        """Parse [[{...}], [{...}]] — fallback tách object nếu model trả phẳng."""
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end > start:
            try:
                data = json.loads(cleaned[start: end + 1])
                if isinstance(data, list) and len(data) == expected:
                    result: List[List[dict]] = []
                    for elem in data:
                        if isinstance(elem, list):
                            result.append(list(elem))
                        elif isinstance(elem, dict) and "change_type" in elem:
                            result.append([elem])
                        else:
                            result.append([])
                    if len(result) == expected:
                        return result
            except json.JSONDecodeError:
                pass

        flat = self._parse_list(raw)
        if not flat:
            return [[] for _ in range(expected)]
        if len(flat) >= expected:
            return [[flat[i]] if i < len(flat) else [] for i in range(expected)]
        # Một object / cặp — gán cặp đầu, còn lại rỗng
        out = [[] for _ in range(expected)]
        out[0] = flat
        return out


def _safe_truncate(text: str, max_chars: int) -> str:
    """Cắt text không quá max_chars, ưu tiên cắt tại khoảng trắng."""
    if len(text) <= max_chars:
        return text.strip()
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.strip() + "…"
