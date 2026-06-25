
import argparse
import json
import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

# ── Paths mặc định ────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).parent.parent
GT_DIR    = ROOT_DIR / "evaluation" / "ground_truth"
DATA_DIR  = ROOT_DIR / "data" / "samples"
RESULTS_DIR = ROOT_DIR / "evaluation" / "results"


# ══════════════════════════════════════════════════════════════════════
# CLI arguments
# ══════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Đánh giá độ chính xác Legal RAG Comparator"
    )
    p.add_argument("--backend",   default="http://localhost:8000",
                   help="URL backend FastAPI")
    p.add_argument("--top_k",     type=int,   default=5,
                   help="Số chunk context cho LLM (default: 5)")
    p.add_argument("--threshold", type=float, default=0.85,
                   help="Ngưỡng cosine similarity để ghép cặp (default: 0.85)")
    p.add_argument("--chunk_max", type=int,   default=800,
                   help="Kích thước chunk tối đa (default: 800)")
    p.add_argument("--model",     default="qwen2.5:7b",
                   help="Tên model Ollama (default: qwen2.5:7b)")
    p.add_argument("--pair",      default=None,
                   help="Chỉ chạy 1 cặp cụ thể, ví dụ: pair_01")
    p.add_argument("--note",      default="",
                   help="Ghi chú mô tả lần chạy này")
    p.add_argument("--gt_dir",    default=str(GT_DIR),
                   help="Thư mục chứa ground truth JSON")
    p.add_argument("--data_dir",  default=str(DATA_DIR),
                   help="Thư mục chứa các cặp tài liệu")
    return p.parse_args()


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def check_backend(backend_url: str) -> bool:
    """Kiểm tra backend có đang chạy không."""
    try:
        r = requests.get(f"{backend_url}/health", timeout=5)
        data = r.json()
        if data.get("status") == "ok":
            print(f"Backend online: {backend_url}")
            return True
        else:
            print(f"Backend degraded: {data.get('message', '')}")
            return True   # vẫn thử chạy
    except requests.ConnectionError:
        print(f"Không kết nối được backend tại {backend_url}")
        print("Kiểm tra: uvicorn main:app --port 8000")
        return False


def normalize_vi_tri(vi_tri: str) -> str:
    """Chuẩn hóa vi_tri để so sánh linh hoạt hơn."""
    return vi_tri.lower().strip().replace("  ", " ")


def match_score(pred_vt: str, gt_vt: str) -> bool:
    """
    So sánh vi_tri linh hoạt:
    - "Điều 2 > Khoản 2.1" match "Điều 2, Khoản 2.1"
    - Bỏ qua sự khác biệt >, ,, dấu cách
    """
    def clean(s):
        return (s.lower()
                 .replace(">", " ").replace(",", " ")
                 .replace("  ", " ").strip())
    return clean(pred_vt) == clean(gt_vt)


def compute_metrics(gt_changes: list, pred_changes: list) -> dict:
    """
    So sánh predicted vs ground truth.
    Match theo (vi_tri, change_type) — linh hoạt với vi_tri.
    """
    gt_set   = [(c["vi_tri"], c["change_type"]) for c in gt_changes]
    pred_set = [(c["vi_tri"], c["change_type"]) for c in pred_changes]

    tp_list, fp_list, fn_list = [], [], []

    used_pred = set()
    for gt_vt, gt_type in gt_set:
        found = False
        for i, (p_vt, p_type) in enumerate(pred_set):
            if i in used_pred:
                continue
            if p_type == gt_type and match_score(p_vt, gt_vt):
                tp_list.append((gt_vt, gt_type))
                used_pred.add(i)
                found = True
                break
        if not found:
            fn_list.append((gt_vt, gt_type))

    for i, item in enumerate(pred_set):
        if i not in used_pred:
            fp_list.append(item)

    tp = len(tp_list)
    fp = len(fp_list)
    fn = len(fn_list)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1":        round(f1,        4),
        "matched":  [{"vi_tri": v, "change_type": t} for v, t in tp_list],
        "missed":   [{"vi_tri": v, "change_type": t} for v, t in fn_list],
        "extra":    [{"vi_tri": v, "change_type": t} for v, t in fp_list],
    }


# ══════════════════════════════════════════════════════════════════════
# Per-pair pipeline
# ══════════════════════════════════════════════════════════════════════

def run_pair(pair_id: str, gt: dict, args) -> dict | None:
    """Chạy ingest + compare cho 1 cặp, trả về dict kết quả."""
    data_dir = Path(args.data_dir)
    path_a   = data_dir / pair_id / gt["file_a"]
    path_b   = data_dir / pair_id / gt["file_b"]

    if not path_a.exists():
        print(f"  ⚠️  Không tìm thấy: {path_a}")
        return None
    if not path_b.exists():
        print(f"  ⚠️  Không tìm thấy: {path_b}")
        return None

    t_start = time.time()

    # ── Ingest ────────────────────────────────────────────────────────
    try:
        r = requests.post(
            f"{args.backend}/ingest",
            files={
                "file_a": (path_a.name, path_a.read_bytes()),
                "file_b": (path_b.name, path_b.read_bytes()),
            },
            data={"session_id": pair_id},
            timeout=300,
        )
        r.raise_for_status()
        ingest_data = r.json()
        session_id  = ingest_data["session_id"]
        print(f"Ingest OK — chunks A={ingest_data['chunks_a']} B={ingest_data['chunks_b']}")
    except Exception as e:
        print(f"Ingest lỗi: {e}")
        return None

    # ── Compare ───────────────────────────────────────────────────────
    try:
        r = requests.post(
            f"{args.backend}/compare",
            json={"session_id": session_id, "top_k": args.top_k},
            timeout=300,
        )
        r.raise_for_status()
        compare_data = r.json()
        predicted    = compare_data.get("change_list", [])
        print(f"Compare OK — {len(predicted)} thay đổi dự đoán")
    except Exception as e:
        print(f"Compare lỗi: {e}")
        return None

    elapsed = round(time.time() - t_start, 2)

    # ── Metrics ───────────────────────────────────────────────────────
    metrics = compute_metrics(gt["changes"], predicted)

    print(
        f"  📊 P={metrics['precision']:.3f}  "
        f"R={metrics['recall']:.3f}  "
        f"F1={metrics['f1']:.3f}  "
        f"(TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']})  "
        f"[{elapsed}s]"
    )

    return {
        "pair_id":   pair_id,
        "elapsed_s": elapsed,
        "n_gt":      len(gt["changes"]),
        "n_pred":    len(predicted),
        **metrics,
        "predicted": [
            {"vi_tri": c["vi_tri"], "change_type": c["change_type"],
             "muc_do": c.get("muc_do", "")}
            for c in predicted
        ],
    }


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    print("\n" + "="*60)
    print("  Legal RAG Comparator — Evaluation")
    print("="*60)
    print(f"  Backend   : {args.backend}")
    print(f"  top_k     : {args.top_k}")
    print(f"  threshold : {args.threshold}")
    print(f"  chunk_max : {args.chunk_max}")
    print(f"  model     : {args.model}")
    print(f"  note      : {args.note or '—'}")
    print("="*60 + "\n")

    # Kiểm tra backend
    if not check_backend(args.backend):
        sys.exit(1)

    # Tạo thư mục lưu kết quả
    run_id  = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    out_dir = RESULTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Lưu config ngay lúc bắt đầu
    config = {
        "run_id":    run_id,
        "timestamp": datetime.now().isoformat(),
        "note":      args.note,
        "params": {
            "backend":   args.backend,
            "model":     args.model,
            "top_k":     args.top_k,
            "threshold": args.threshold,
            "chunk_max": args.chunk_max,
        },
    }
    (out_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"📁 Kết quả lưu tại: {out_dir}\n")

    # Load ground truth files
    gt_dir   = Path(args.gt_dir)
    gt_files = sorted(gt_dir.glob("*.json"))
    if not gt_files:
        print(f"Không tìm thấy file ground truth trong: {gt_dir}")
        sys.exit(1)

    # Lọc nếu chỉ chạy 1 cặp
    if args.pair:
        gt_files = [f for f in gt_files if f.stem == args.pair]
        if not gt_files:
            print(f"Không tìm thấy ground truth cho: {args.pair}")
            sys.exit(1)

    print(f"Sẽ chạy {len(gt_files)} cặp tài liệu\n")

    # ── Chạy từng cặp ─────────────────────────────────────────────────
    details     = []
    all_tp = all_fp = all_fn = 0
    failed = 0

    for i, gt_file in enumerate(gt_files, 1):
        gt      = json.loads(gt_file.read_text(encoding="utf-8"))
        pair_id = gt.get("pair_id", gt_file.stem)

        print(f"[{i}/{len(gt_files)}] {pair_id}")

        result = run_pair(pair_id, gt, args)
        if result is None:
            failed += 1
            continue

        details.append(result)
        all_tp += result["tp"]
        all_fp += result["fp"]
        all_fn += result["fn"]

    # ── Tổng hợp metrics ──────────────────────────────────────────────
    n = len(details)
    if n == 0:
        print("\n Không có cặp nào chạy thành công.")
        sys.exit(1)

    # Micro average (gộp tất cả TP/FP/FN)
    micro_p  = all_tp / (all_tp + all_fp) if (all_tp + all_fp) > 0 else 0
    micro_r  = all_tp / (all_tp + all_fn) if (all_tp + all_fn) > 0 else 0
    micro_f1 = (2 * micro_p * micro_r / (micro_p + micro_r)
                if (micro_p + micro_r) > 0 else 0)

    # Macro average (trung bình từng cặp)
    macro_p  = sum(d["precision"] for d in details) / n
    macro_r  = sum(d["recall"]    for d in details) / n
    macro_f1 = sum(d["f1"]        for d in details) / n

    metrics_summary = {
        "run_id":   run_id,
        "n_pairs":  n,
        "n_failed": failed,
        "micro": {
            "precision": round(micro_p,  4),
            "recall":    round(micro_r,  4),
            "f1":        round(micro_f1, 4),
        },
        "macro": {
            "precision": round(macro_p,  4),
            "recall":    round(macro_r,  4),
            "f1":        round(macro_f1, 4),
        },
        "totals": {
            "tp": all_tp, "fp": all_fp, "fn": all_fn,
        },
        # Các cặp kém nhất (F1 thấp nhất)
        "worst_pairs": sorted(
            [{"pair_id": d["pair_id"], "f1": d["f1"]} for d in details],
            key=lambda x: x["f1"]
        )[:5],
    }

    # ── Lưu kết quả ───────────────────────────────────────────────────
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "details.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── In tổng kết ───────────────────────────────────────────────────
    print(f"""
{'='*60}
Kết quả — {run_id}
{'='*60}
  Số cặp chạy thành công : {n} / {n + failed}

  Micro  P={micro_p:.4f}   R={micro_r:.4f}   F1={micro_f1:.4f}
  Macro  P={macro_p:.4f}   R={macro_r:.4f}   F1={macro_f1:.4f}

  Tổng   TP={all_tp}  FP={all_fp}  FN={all_fn}

  Lưu tại: {out_dir}
{'='*60}
""")


if __name__ == "__main__":
    main()
