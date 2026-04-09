# Legal RAG Comparator
> So sánh và phát hiện thay đổi trong văn bản hợp đồng tiếng Việt bằng RAG + LLM

Hệ thống nhận 2 phiên bản hợp đồng (DOCX/PDF), tự động phát hiện thay đổi theo từng điều khoản, trích dẫn bằng chứng trực tiếp từ văn bản gốc và tổng hợp báo cáo bằng tiếng Việt.

---

## Mục lục
- [Legal RAG Comparator](#legal-rag-comparator)
  - [Mục lục](#mục-lục)
  - [Tính năng](#tính-năng)
  - [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
  - [Cấu trúc thư mục](#cấu-trúc-thư-mục)
  - [Cài đặt](#cài-đặt)
    - [Yêu cầu](#yêu-cầu)
    - [1. Clone repo](#1-clone-repo)
    - [2. Cài UI (local)](#2-cài-ui-local)
    - [3. Cài Backend (Google Colab)](#3-cài-backend-google-colab)
  - [Chạy đầy đủ (có backend)](#chạy-đầy-đủ-có-backend)
  - [Đánh giá mô hình](#đánh-giá-mô-hình)
    - [Chuẩn bị ground truth](#chuẩn-bị-ground-truth)
    - [Chạy đánh giá](#chạy-đánh-giá)
    - [Ví dụ kết quả](#ví-dụ-kết-quả)
  - [Tech Stack](#tech-stack)

---

##  Tính năng

- **Đọc DOCX và PDF** — chuẩn hóa Unicode, sửa lỗi OCR tự động
- **Chunking theo cấu trúc pháp lý** — tách chunk theo Điều → Khoản → Điểm
- **RAG retrieval** — tìm điều khoản liên quan bằng BGE-M3 embedding
- **LLM phân tích** — Qwen2.5-7B so sánh từng cặp điều khoản
- **Citation validation** — mọi kết luận có trích dẫn, loại bỏ hallucination
- **Evaluation** — đo Precision/Recall/F1 trên 20 cặp tài liệu mẫu
- **Demo mode** — chạy UI với dữ liệu giả, không cần backend

---

##  Kiến trúc hệ thống

![architecture](images/Screenshot%202026-03-12%20at%2010.44.42.png)

**Luồng xử lý:**
```
Upload A+B → reader → chunker → BGE-M3 → data/chroma_db/
           → matcher (ghép cặp Điều/Khoản)
           → comparator (Qwen2.5-7B + citation validate)
           → reporter → UI
```

---

##  Cấu trúc thư mục

```
TTCS/
├── .env                               # Biến môi trường (không commit)
├── .env.example                       # Template
├── .gitignore
├── README.md
│
├── data/
│   ├── chroma_db/                     # Vector DB (tự sinh, không commit)
│   └── samples/                       # Tài liệu mẫu để demo
│       ├── pair_01/
│       │   ├── version_a.docx
│       │   └── version_b.docx
│       └── pair_02/
│
├── notebooks/                         # Quá trình nghiên cứu
│   ├── 01_test_chunking.ipynb         # Test regex Điều/Khoản/Điểm
│   ├── 02_test_embedding.ipynb        # Test BGE-M3, visualize vector
│   └── 03_test_retrieval.ipynb        # Test ChromaDB query, xem top-k
│
├── backend/                           # Chạy trên Google Colab
│   ├── main.py                        # FastAPI endpoints
│   ├── config.py                      # Cấu hình tập trung
│   ├── schemas.py                     # Pydantic models
│   ├── requirements.txt
│   ├── core/
│   │   ├── embedding.py               # BGE-M3 singleton
│   │   ├── vector_db.py               # ChromaDB wrapper
│   │   └── llm_engine.py             # Qwen2.5-7B qua Ollama
│   └── services/
│       ├── reader.py                  # Đọc DOCX + PDF
│       ├── chunker.py                 # Chia chunk
│       ├── matcher.py                 # Ghép cặp chunk A ↔ B
│       ├── comparator.py             # Gọi LLM + validate citation
│       └── reporter.py               # Tổng hợp Report
│
├── ui/                                # Chạy local
│   ├── app.py                         # Streamlit entrypoint
│   ├── config.py
│   ├── api_client.py                  # Mock / Real client
│   ├── mock_data.py                   # Dữ liệu giả cho demo
│   ├── session_state.py
│   ├── formatters.py
│   ├── requirements.txt
│   └── components/
│       ├── uploader.py
│       ├── result_card.py
│       └── filter_bar.py
│
└── evaluation/                        # Đánh giá độ chính xác
    ├── run_eval.py                    # Chạy test 20 cặp
    ├── compare.py                     # So sánh nhiều lần chạy
    ├── ground_truth/                  # Nhãn thật (nên commit)
    │   ├── pair_01.json
    │   └── ...pair_20.json
    └── results/                       # Tự sinh khi chạy (không commit)
        └── run_YYYYMMDD_HHMMSS/
            ├── config.json            # Tham số lần chạy
            ├── metrics.json           # Precision / Recall / F1
            └── details.json           # Chi tiết từng cặp
```

---

## Cài đặt

### Yêu cầu

| Thành phần | Phiên bản |
|---|---|
| Python | ≥ 3.10 |
| RAM local | ≥ 8 GB |
| GPU Colab | T4 16 GB |

### 1. Clone repo

```bash
git clone https://github.com/<your-username>/TTCS.git
cd TTCS
cp .env.example .env
```

### 2. Cài UI (local)

```bash
cd ui
python3 -m venv venv
source venv/bin/activate        
pip install -r requirements.txt
```

### 3. Cài Backend (Google Colab)

Chạy file notebook/TTCS.ipynd


---

##  Chạy đầy đủ (có backend)

```bash
# Bước 1 — Chạy backend trên Colab, lấy URL ngrok
# Bước 2 — Cập nhật .env
BACKEND_URL=https://xxxx-xx-xxx.ngrok-free.app
DEMO_MODE=false

# Bước 3 — Chạy UI
cd ui
source venv/bin/activate
streamlit run app.py
```

---

##  Đánh giá mô hình

### Chuẩn bị ground truth

Tạo file `evaluation/ground_truth/pair_01.json` cho mỗi cặp tài liệu:

```json
{
  "pair_id": "pair_01",
  "file_a": "version_a.docx",
  "file_b": "version_b.docx",
  "changes": [
    {
      "change_type": "SỬA",
      "vi_tri": "Điều 2 > Khoản 2.1",
      "mo_ta": "Thời hạn tăng từ 12 lên 24 tháng",
      "muc_do": "cao"
    }
  ]
}
```

### Chạy đánh giá

```bash
# Lần 1 — baseline
python evaluation/run_eval.py --note "baseline"

# Lần 2 — tăng top_k
python evaluation/run_eval.py --top_k 8 --note "topk_8"

# Lần 3 — giảm threshold
python evaluation/run_eval.py --threshold 0.75 --note "thr_075"

# So sánh các lần chạy
python evaluation/compare.py
```

### Ví dụ kết quả

| Run ID| Note| Model |  top_k  | thr  |P     | R    |  F1| 
| --- |---|---|---|---|---|---|---| 
run_20240301_143022  |baseline     |qwen2.5:7b |   5  | 0.85|  0.812| 0.743| 0.776
run_20240301_160512  |topk_8  |    qwen2.5:7b   | 8   | 0.85 | 0.834 | 0.771 | 0.801
run_20240302_090000   | thr_075  |   qwen2.5:7b |   5 |  0.75 | 0.798 | 0.810 | 0.804

---


## Tech Stack

| Layer | Công nghệ | Mục đích |
|---|---|---|
| UI | Streamlit | Giao diện người dùng |
| API | FastAPI | REST backend |
| LLM | Qwen2.5-7B (Ollama) | Phân tích so sánh |
| Embedding | BGE-M3 (FlagEmbedding) | Vector hóa văn bản |
| Vector DB | ChromaDB | Lưu trữ và tìm kiếm vector |
| Doc Parser | python-docx, PyMuPDF | Đọc DOCX/PDF |
| Runtime | Google Colab T4 | Chạy LLM + Embedding |

---
