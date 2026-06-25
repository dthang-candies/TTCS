"""
evaluation/compare.py
So sánh kết quả của nhiều lần chạy thành bảng dễ đọc.

Cách dùng:
  # So sánh tất cả lần chạy
  python evaluation/compare.py

  # Sắp xếp theo F1 giảm dần
  python evaluation/compare.py --sort f1

  # Chỉ xem top 5 lần chạy tốt nhất
  python evaluation/compare.py --top 5

  # Xem chi tiết từng cặp của 1 lần chạy
  python evaluation/compare.py --detail run_20240301_143022
"""

import argparse
import json
from pathlib import Path

ROOT_DIR    = Path(__file__).parent.parent
RESULTS_DIR = ROOT_DIR / "evaluation" / "results"


# ══════════════════════════════════════════════════════════════════════
# Load
# ══════════════════════════════════════════════════════════════════════

def load_runs() -> list[dict]:
    """Load tất cả lần chạy trong results/."""
    runs = []
    if not RESULTS_DIR.exists():
        return runs

    for run_dir in sorted(RESULTS_DIR.iterdir()):
        cfg_file = run_dir / "config.json"
        met_file = run_dir / "metrics.json"
        if not cfg_file.exists() or not met_file.exists():
            continue

        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            met = json.loads(met_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        runs.append({
            "run_id":    cfg["run_id"],
            "timestamp": cfg.get("timestamp", "")[:16].replace("T", " "),
            "note":      cfg.get("note", "—")[:18],
            "model":     cfg["params"].get("model", "—"),
            "top_k":     cfg["params"].get("top_k", "—"),
            "threshold": cfg["params"].get("threshold", "—"),
            "chunk_max": cfg["params"].get("chunk_max", "—"),
            "n_pairs":   met.get("n_pairs", 0),
            "n_failed":  met.get("n_failed", 0),
            # Micro metrics (dùng để so sánh chính)
            "micro_p":   met["micro"]["precision"],
            "micro_r":   met["micro"]["recall"],
            "micro_f1":  met["micro"]["f1"],
            # Macro metrics
            "macro_p":   met["macro"]["precision"],
            "macro_r":   met["macro"]["recall"],
            "macro_f1":  met["macro"]["f1"],
            # Totals
            "tp": met["totals"]["tp"],
            "fp": met["totals"]["fp"],
            "fn": met["totals"]["fn"],
        })

    return runs


# ══════════════════════════════════════════════════════════════════════
# Display
# ══════════════════════════════════════════════════════════════════════

def print_summary_table(runs: list[dict], sort_by: str = "micro_f1"):
    """In bảng tổng hợp tất cả lần chạy."""
    if not runs:
        print("Chưa có lần chạy nào. Chạy: python evaluation/run_eval.py")
        return

    # Sắp xếp
    key_map = {
        "f1":        "micro_f1",
        "precision": "micro_p",
        "recall":    "micro_r",
        "time":      "timestamp",
    }
    sort_key = key_map.get(sort_by, "micro_f1")
    runs = sorted(runs, key=lambda x: x[sort_key], reverse=(sort_key != "timestamp"))

    # Header
    sep = "─" * 110
    print(f"\n{'='*110}")
    print("  SO SÁNH CÁC LẦN CHẠY — Legal RAG Comparator")
    print(f"{'='*110}")
    print(
        f"  {'Run ID':<22} {'Timestamp':<17} {'Note':<18} {'Model':<14} "
        f"{'k':>3} {'thr':>5} {'Pairs':>5} "
        f"{'micro_P':>8} {'micro_R':>8} {'micro_F1':>9} "
        f"{'macro_F1':>9}"
    )
    print(f"  {sep}")

    best_f1 = max(r["micro_f1"] for r in runs)

    for r in runs:
        marker = " ★" if r["micro_f1"] == best_f1 else "  "
        failed_note = f" ({r['n_failed']} lỗi)" if r["n_failed"] > 0 else ""
        print(
            f"{marker} {r['run_id']:<22} {r['timestamp']:<17} {r['note']:<18} "
            f"{r['model']:<14} {r['top_k']:>3} {r['threshold']:>5} "
            f"{str(r['n_pairs']) + failed_note:>5} "
            f"{r['micro_p']:>8.4f} {r['micro_r']:>8.4f} {r['micro_f1']:>9.4f} "
            f"{r['macro_f1']:>9.4f}"
        )

    print(f"  {sep}")
    print(f"  ★ = lần chạy tốt nhất theo micro F1\n")

    # Tóm tắt
    best = runs[0]
    print(f"  Tốt nhất : {best['run_id']}  —  F1={best['micro_f1']:.4f}  (note: {best['note']})")
    if len(runs) > 1:
        diff = best["micro_f1"] - runs[-1]["micro_f1"]
        print(f"  Chênh lệch tốt nhất vs kém nhất: {diff:+.4f}")
    print()


def print_detail(run_id: str):
    """In kết quả chi tiết từng cặp của 1 lần chạy."""
    run_dir = RESULTS_DIR / run_id
    if not run_dir.exists():
        print(f"Không tìm thấy: {run_dir}")
        return

    details_file = run_dir / "details.json"
    config_file  = run_dir / "config.json"
    if not details_file.exists():
        print(f"Không có details.json trong {run_dir}")
        return

    cfg     = json.loads(config_file.read_text(encoding="utf-8"))
    details = json.loads(details_file.read_text(encoding="utf-8"))

    print(f"\n{'='*80}")
    print(f"  Chi tiết: {run_id}")
    print(f"  Note    : {cfg.get('note', '—')}")
    print(f"  Params  : top_k={cfg['params']['top_k']}  "
          f"threshold={cfg['params']['threshold']}  "
          f"model={cfg['params']['model']}")
    print(f"{'='*80}")
    print(
        f"  {'Pair ID':<15} {'n_GT':>5} {'n_Pred':>7} "
        f"{'P':>8} {'R':>8} {'F1':>8} "
        f"{'TP':>4} {'FP':>4} {'FN':>4} {'Time':>7}"
    )
    print(f"  {'─'*78}")

    # Sắp xếp từ kém đến tốt
    details_sorted = sorted(details, key=lambda x: x["f1"])

    for d in details_sorted:
        flag = " ⚠" if d["f1"] < 0.5 else ("  ✓" if d["f1"] >= 0.8 else "   ")
        print(
            f"{flag} {d['pair_id']:<15} {d['n_gt']:>5} {d['n_pred']:>7} "
            f"{d['precision']:>8.3f} {d['recall']:>8.3f} {d['f1']:>8.3f} "
            f"{d['tp']:>4} {d['fp']:>4} {d['fn']:>4} "
            f"{d.get('elapsed_s', 0):>6.1f}s"
        )

    print(f"  {'─'*78}")

    avg_f1 = sum(d["f1"] for d in details) / len(details)
    print(f"  Macro F1 trung bình: {avg_f1:.4f}\n")

    # Phân tích lỗi — những thay đổi bị bỏ sót nhiều nhất
    all_missed = []
    for d in details:
        for m in d.get("missed", []):
            all_missed.append(f"{m['change_type']} @ {m['vi_tri']}")

    if all_missed:
        from collections import Counter
        top_missed = Counter(all_missed).most_common(5)
        print("  Thay đổi bị bỏ sót nhiều nhất (FN):")
        for item, count in top_missed:
            print(f"     {count}x  {item}")
        print()


def print_comparison(run_ids: list[str]):
    """So sánh chi tiết 2-3 lần chạy cụ thể theo từng cặp."""
    if len(run_ids) < 2:
        print("Cần ít nhất 2 run_id để so sánh.")
        return

    all_details = {}
    for rid in run_ids:
        f = RESULTS_DIR / rid / "details.json"
        if f.exists():
            all_details[rid] = {
                d["pair_id"]: d
                for d in json.loads(f.read_text(encoding="utf-8"))
            }

    all_pairs = sorted(set(
        pid for details in all_details.values() for pid in details
    ))

    print(f"\n{'='*90}")
    print(f"  So sánh chi tiết {len(run_ids)} lần chạy")
    print(f"{'='*90}")
    header = f"  {'Pair ID':<15}"
    for rid in run_ids:
        header += f"  {rid[-16:]:>18}"
    print(header)
    print(f"  {'─'*88}")

    for pair_id in all_pairs:
        row = f"  {pair_id:<15}"
        for rid in run_ids:
            d = all_details.get(rid, {}).get(pair_id)
            if d:
                row += f"  F1={d['f1']:.3f} P={d['precision']:.2f} R={d['recall']:.2f}"
            else:
                row += f"  {'—':>18}"
        print(row)
    print()


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="So sánh kết quả các lần chạy evaluation"
    )
    parser.add_argument("--sort",   default="f1",
                        choices=["f1", "precision", "recall", "time"],
                        help="Sắp xếp theo tiêu chí nào (default: f1)")
    parser.add_argument("--top",    type=int, default=None,
                        help="Chỉ hiển thị N lần chạy tốt nhất")
    parser.add_argument("--detail", default=None,
                        help="Xem chi tiết từng cặp của 1 lần chạy")
    parser.add_argument("--compare", nargs="+", default=None,
                        help="So sánh 2-3 run_id cụ thể theo từng cặp")
    args = parser.parse_args()

    # ── Detail mode ───────────────────────────────────────────────────
    if args.detail:
        print_detail(args.detail)
        return

    # ── Compare mode ──────────────────────────────────────────────────
    if args.compare:
        print_comparison(args.compare)
        return

    # ── Summary table ─────────────────────────────────────────────────
    runs = load_runs()
    if args.top:
        # Sắp xếp theo F1 trước khi cắt top N
        runs = sorted(runs, key=lambda x: x["micro_f1"], reverse=True)[: args.top]

    print_summary_table(runs, sort_by=args.sort)

    if runs:
        print("  Để xem chi tiết 1 lần chạy:")
        print(f"    python evaluation/compare.py --detail {runs[0]['run_id']}\n")
        if len(runs) >= 2:
            print("  Để so sánh 2 lần chạy:")
            r1, r2 = runs[0]["run_id"], runs[1]["run_id"]
            print(f"    python evaluation/compare.py --compare {r1} {r2}\n")


if __name__ == "__main__":
    main()
