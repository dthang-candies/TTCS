"""
ui/app.py — Legal RAG Comparator (Streamlit, flat SaaS-style UI).

Chạy từ thư mục ui:  streamlit run app.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from theme_styles import streamlit_css
from config import DEMO_MODE, MAX_FILE_MB
import session_state as ss
from api_client import get_client, APIError
from formatters import seconds, file_size
from components import filter_bar, result_card

# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Legal RAG Comparator",
    layout="wide",
    initial_sidebar_state="expanded",
)

ss.init()
_theme = st.session_state.get("ui_theme", "light")

# Layout phẳng + theme (sidebar 300px, gỡ viền Streamlit, nút phẳng — xem theme_styles.py)
st.markdown(streamlit_css(_theme), unsafe_allow_html=True)

_dark = _theme == "dark"
_title_c = "#f8fafc" if _dark else "#0f172a"
_sub_c = "#94a3b8" if _dark else "#64748b"


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        f'<div style="border-bottom:1px solid {"#334155" if _dark else "#e2e8f0"};padding-bottom:1rem;margin-bottom:0.75rem;">'
        f'<p style="font-size:1.125rem;font-weight:700;color:{"#f8fafc" if _dark else "#0f172a"};margin:0;">'
        f"Legal RAG Comparator</p>"
        f'<p style="font-size:0.875rem;color:{_sub_c};margin:0.35rem 0 0;line-height:1.45;">'
        f"Phân tích thay đổi văn bản pháp lý</p></div>",
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<p class="sb-section-title">TRẠNG THÁI</p>', unsafe_allow_html=True)
        if DEMO_MODE:
            st.markdown(
                '<div class="demo-mode-pill">DEMO MODE</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="demo-mode-pill" style="background:#ecfdf5 !important;border-color:#a7f3d0 !important;'
                'color:#047857 !important;">PRODUCTION</div>',
                unsafe_allow_html=True,
            )

    with st.container():
        st.markdown('<p class="sb-section-title">CẤU HÌNH</p>', unsafe_allow_html=True)
        top_k = st.slider("Context (top-k chunks)", 1, 20, 7)
        focus_dieu = st.text_input(
            "Giới hạn điều khoản",
            placeholder="Ví dụ: Điều 5",
        ) or None

    with st.container():
        st.markdown('<p class="sb-section-title">PHIÊN LÀM VIỆC</p>', unsafe_allow_html=True)
        sid = ss.get("session_id")
        if sid:
            st.caption(f"Session: `{sid}`")
        if st.button("Đặt lại", use_container_width=True, key="sb_reset"):
            ss.reset()
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Một thanh ngang: tiêu đề | trạng thái | Kiểm tra | Dark/Light
# ═══════════════════════════════════════════════════════════════════════════

if DEMO_MODE:
    _status_inner = "DEMO MODE"
    _status_accent = "#818cf8"
else:
    _status_inner = "Đã kết nối"
    _status_accent = "#34d399"

# `key` → class `st-key-hdr_toolbar` trên DOM (Streamlit), CSS nhắm đúng 2 nút — không phụ thuộc stHorizontalBlock
with st.container(key="hdr_toolbar"):
    b1, b2, b3, b4 = st.columns([3.4, 2.2, 0.75, 0.65], gap="small")

    with b1:
        st.markdown(
            f'<p style="margin:0;font-size:0.98rem;font-weight:600;color:{_title_c};letter-spacing:-0.02em;">'
            f"So sánh văn bản pháp luật - TTCS - Nhóm 3</p>",
            unsafe_allow_html=True,
        )

    with b2:
        st.markdown(
            f'<p style="margin:0;font-size:0.8125rem;color:{_sub_c};white-space:nowrap;">'
            f"Trạng thái (<span style=\"color:{_status_accent};font-weight:600;\">{_status_inner}</span>)</p>",
            unsafe_allow_html=True,
        )

    with b3:
        if st.button("Kiểm tra", key="hdr_check", type="secondary"):
            if DEMO_MODE:
                st.session_state["hdr_check_msg"] = (
                    "Demo mode — không gọi backend. Đặt DEMO_MODE=false trong .env để kiểm tra API thật."
                )
            else:
                try:
                    h = get_client().health()
                    st.session_state["hdr_check_msg"] = (
                        f"Trạng thái API: {h.get('status', '—')}."
                    )
                except APIError as e:
                    st.session_state["hdr_check_msg"] = str(e)
            st.rerun()

    with b4:
        _btn_theme = "Light" if _dark else "Dark"
        if st.button(_btn_theme, key="hdr_theme", type="secondary"):
            st.session_state["ui_theme"] = "light" if _dark else "dark"
            st.rerun()

st.caption(
    "Phát hiện thay đổi trong văn bản hợp đồng tiếng Việt bằng RAG và LLM — Legal RAG Comparator"
)

_msg = ss.get("hdr_check_msg")
if _msg:
    st.markdown(
        '<div style="border-radius:0.75rem;background:#f0f9ff;'
        'padding:12px 16px;font-size:0.875rem;color:#0c4a6e;margin-bottom:1.25rem;">'
        f"{_msg}</div>",
        unsafe_allow_html=True,
    )

st.markdown('<div class="step-block"></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# Section 1 — Upload
# ═══════════════════════════════════════════════════════════════════════════

st.subheader("1. Tải lên tài liệu")

col_a, col_b = st.columns(2, gap="large")

with col_a:
    st.markdown(
        """
<p style="margin:0 0 10px 0;line-height:1.4;">
  <span style="display:inline-block;background:#4f46e5;color:#fff;font-weight:700;
    padding:2px 8px;border-radius:4px;margin-right:8px;font-size:0.8rem;">A</span>
  <span style="color:#5b21b6;font-weight:800;font-size:0.7rem;letter-spacing:0.06em;">
    TÀI LIỆU A — PHIÊN BẢN GỐC
  </span>
</p>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="upload-mark upload-mark-a"></div>',
        unsafe_allow_html=True,
    )
    file_a = st.file_uploader(
        "Chọn hoặc kéo thả file",
        type=["docx", "pdf"],
        key="file_a",
    )
    if file_a:
        st.caption(f"{file_a.name} · {file_size(file_a)}")
    else:
        st.caption("Chưa chọn file")

with col_b:
    st.markdown(
        """
<p style="margin:0 0 10px 0;line-height:1.4;">
  <span style="display:inline-block;background:#059669;color:#fff;font-weight:700;
    padding:2px 8px;border-radius:4px;margin-right:8px;font-size:0.8rem;">B</span>
  <span style="color:#047857;font-weight:800;font-size:0.7rem;letter-spacing:0.06em;">
    TÀI LIỆU B — PHIÊN BẢN MỚI
  </span>
</p>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="upload-mark upload-mark-b"></div>',
        unsafe_allow_html=True,
    )
    file_b = st.file_uploader(
        "Chọn hoặc kéo thả file",
        type=["docx", "pdf"],
        key="file_b",
    )
    if file_b:
        st.caption(f"{file_b.name} · {file_size(file_b)}")
    else:
        st.caption("Chưa chọn file")

if file_a and file_b:
    if ss.get("file_a_name") != file_a.name or ss.get("file_b_name") != file_b.name:
        ss.reset()

can_ingest = bool(file_a and file_b)

if st.button(
    "Xử lý tài liệu",
    type="primary",
    use_container_width=True,
    disabled=not can_ingest,
    key="btn_ingest",
):
    with st.spinner("Đang parse, chunk và index tài liệu..."):
        try:
            result = get_client().ingest(
                file_a=(file_a.name, file_a.getvalue(), file_a.type),
                file_b=(file_b.name, file_b.getvalue(), file_b.type),
            )
            ss.set_ingest(result)
            st.session_state["hdr_check_msg"] = None
            st.rerun()
        except APIError as e:
            st.error(str(e))

st.caption(f"Hỗ trợ tài liệu định dạng: .docx và .pdf — tối đa {MAX_FILE_MB} MB mỗi file.")

# Ingest summary
if ss.get("ingest_done") and ss.get("ingest_result"):
    r = ss.get("ingest_result")
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:0.75rem;padding:10px 14px;margin-bottom:12px;">'
        '<span style="font-size:0.8125rem;color:#047857;font-weight:600;">Đã xử lý thành công.</span>'
        f'<span style="font-size:0.8125rem;color:#64748b;margin-left:8px;">Session: {r["session_id"]}</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Chunks A", r["chunks_a"])
    m2.metric("Chunks B", r["chunks_b"])
    m3.metric("Tổng chunks", r["total_chunks"])
    m4.metric("Session", r["session_id"])

# ═══════════════════════════════════════════════════════════════════════════
# Section 2 — Compare
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("<br>", unsafe_allow_html=True)
st.subheader("2. So sánh tài liệu")

ing_ok = bool(ss.get("ingest_done"))
if not ing_ok:
    st.caption("Hoàn thành bước 1 trước.")
else:
    st.caption("So sánh toàn bộ hoặc theo điều khoản đã giới hạn ở sidebar.")

if st.button(
    "Bắt đầu so sánh",
    type="primary",
    use_container_width=True,
    disabled=not ing_ok,
    key="btn_compare",
):
    with st.spinner("LLM đang phân tích từng điều khoản..."):
        try:
            result = get_client().compare(
                session_id=ss.get("session_id"),
                focus_dieu=focus_dieu,
                top_k=top_k,
            )
            ss.set_compare(result)
            st.session_state["hdr_check_msg"] = None
            st.rerun()
        except APIError as e:
            st.error(str(e))

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# Section 3 — Results
# ═══════════════════════════════════════════════════════════════════════════

if not ss.get("compare_done"):
    st.stop()

res = ss.get("compare_result")
if not res:
    st.stop()

_badge_bg = "linear-gradient(145deg,#4f46e5,#4338ca)"
st.markdown(
    f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">'
    f'<div style="width:36px;height:36px;background:{_badge_bg};border-radius:0.5rem;'
    f'display:flex;align-items:center;justify-content:center;font-size:0.875rem;font-weight:700;color:#fff;">3</div>'
    f'<h3 style="font-size:1.125rem;font-weight:600;color:{_title_c};margin:0;">Kết quả so sánh</h3>'
    "</div>",
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Tổng thay đổi", res.get("total_changes", 0))
c2.metric("Thêm mới", res.get("changes_added", 0))
c3.metric("Bị xóa", res.get("changes_deleted", 0))
c4.metric("Sửa đổi", res.get("changes_modified", 0))
c5.metric("Đổi vị trí", res.get("changes_reordered", 0))
c6.metric("Không đổi", res.get("changes_unchanged", 0))
c7.metric("Thời gian", seconds(res.get("processing_time", 0)))

if res.get("tom_tat"):
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:{"#1e293b" if _dark else "#ffffff"};border:1px solid {"#334155" if _dark else "#e2e8f0"};'
        f'border-left:4px solid #4f46e5;border-radius:0 0.75rem 0.75rem 0;padding:14px 18px;margin:0 0 20px;">'
        f'<div style="font-size:0.7rem;font-weight:700;color:{_sub_c};letter-spacing:0.08em;margin-bottom:8px;">TÓM TẮT</div>'
        f'<p style="font-size:0.875rem;color:{_title_c};line-height:1.65;margin:0;">{res["tom_tat"]}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )

change_list = res.get("change_list", [])

if not change_list:
    st.success("Không phát hiện thay đổi đáng kể giữa hai tài liệu.")
    st.stop()

st.markdown(
    f'<div style="background:{"#0f172a" if _dark else "#f8fafc"};border:1px solid {"#334155" if _dark else "#e2e8f0"};'
    f'border-radius:0.75rem;padding:12px 16px;margin-bottom:14px;">',
    unsafe_allow_html=True,
)
type_f, muc_f, kw_f = filter_bar.render(change_list)
st.markdown("</div>", unsafe_allow_html=True)

filtered = filter_bar.apply(change_list, type_f, muc_f, kw_f)

ir = ss.get("ingest_result") or {}
name_a = ir.get("file_a_name", "Tài liệu A")
name_b = ir.get("file_b_name", "Tài liệu B")

if not filtered:
    st.warning("Không có kết quả khớp bộ lọc.")
    st.stop()

count_note = (
    f"Hiển thị {len(filtered)} / {len(change_list)} thay đổi"
    if len(filtered) < len(change_list)
    else f"{len(change_list)} thay đổi"
)
st.markdown(
    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
    f'<span style="font-size:0.875rem;font-weight:600;color:{_title_c};">Danh sách thay đổi</span>'
    f'<span style="font-size:0.8125rem;color:{_sub_c};">{count_note}</span>'
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    f'<div style="border:1px solid {"#334155" if _dark else "#e2e8f0"};border-radius:0.75rem;'
    f'padding:16px 20px;background:{"#1e293b" if _dark else "#ffffff"};">',
    unsafe_allow_html=True,
)
for i, item in enumerate(filtered):
    result_card.render(item, i, name_a=name_a, name_b=name_b, theme=_theme)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
st.download_button(
    label="Tải xuống kết quả (JSON)",
    data=json.dumps(res, ensure_ascii=False, indent=2),
    file_name=f"compare_{ss.get('session_id')}.json",
    mime="application/json",
)
