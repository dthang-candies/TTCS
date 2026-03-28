"""
ui/app.py -- Streamlit entrypoint (phien ban moi, khong icon)
Chay: streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import streamlit as st

from config import APP_TITLE, APP_LAYOUT, DEMO_MODE, BACKEND_URL
import session_state as ss
from api_client import get_client, APIError
from formatters import seconds
from components import uploader, filter_bar, result_card

# ── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Font: He thong (khong import Google Fonts de tranh load cham) */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "Inter", "Helvetica Neue", Arial, sans-serif !important;
}

/* An element Streamlit mac dinh */
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1080px !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid #1f2937 !important;
}
[data-testid="stSidebar"] * { color: #d1d5db !important; }
[data-testid="stSidebar"] hr { border-color: #1f2937 !important; }

/* Buttons */
.stButton > button {
    font-size: 0.84rem !important;
    font-weight: 600 !important;
    border-radius: 4px !important;
    border: 1.5px solid #d1d5db !important;
    color: #374151 !important;
    background: #ffffff !important;
    padding: 0.45rem 1rem !important;
    transition: background 0.12s, color 0.12s !important;
}
.stButton > button:hover {
    background: #f9fafb !important;
    border-color: #9ca3af !important;
}
.stButton > button[kind="primary"] {
    background: #111827 !important;
    color: #ffffff !important;
    border-color: #111827 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1f2937 !important;
    border-color: #1f2937 !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    border: 1.5px dashed #d1d5db !important;
    border-radius: 6px !important;
    background: #fafafa !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #9ca3af !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] { font-size: 0.84rem !important; }

/* Metrics */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 12px 16px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    color: #6b7280 !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #111827 !important;
}

/* Expander */
[data-testid="stExpander"] {
    border: 1px solid #e5e7eb !important;
    border-radius: 4px !important;
    background: #fafafa !important;
    margin-top: 6px !important;
}
details > summary {
    font-size: 0.80rem !important;
    font-weight: 500 !important;
    color: #6b7280 !important;
    padding: 8px 12px !important;
}
details > summary:hover { color: #111827 !important; }

/* Selectbox / TextInput */
.stSelectbox > div > div,
.stTextInput > div > div > input {
    font-size: 0.84rem !important;
    border-radius: 4px !important;
    border: 1.5px solid #e5e7eb !important;
    color: #111827 !important;
}

/* Spinner */
.stSpinner > div { border-top-color: #111827 !important; }

/* Alert */
.stAlert {
    border-radius: 4px !important;
    font-size: 0.84rem !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f9fafb; }
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ── Init state ────────────────────────────────────────────────────────
ss.init()

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════

with st.sidebar:
    # Logo / Ten app
    st.markdown(
        '<div style="padding:16px 0 12px;">'
        '<div style="font-size:1rem;font-weight:700;color:#f9fafb;'
        'letter-spacing:-0.01em;">Legal RAG</div>'
        '<div style="font-size:0.75rem;color:#6b7280;margin-top:2px;">'
        'So sanh van ban hop dong</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # Trang thai ket noi
    st.markdown(
        '<div style="font-size:0.70rem;font-weight:700;color:#4b5563;'
        'letter-spacing:0.08em;margin-bottom:8px;">TRANG THAI</div>',
        unsafe_allow_html=True,
    )

    if DEMO_MODE:
        st.markdown(
            '<div style="background:#1f2937;border-radius:4px;'
            'padding:8px 12px;font-size:0.80rem;color:#fbbf24;'
            'font-weight:600;">DEMO MODE</div>'
            '<div style="font-size:0.74rem;color:#4b5563;margin-top:4px;">'
            'Du lieu mo phong</div>',
            unsafe_allow_html=True,
        )
    else:
        if st.button("Kiem tra ket noi", use_container_width=True):
            try:
                h  = get_client().health()
                ok = h.get("status") == "ok"
                status_text  = "Online" if ok else "Offline"
                status_color = "#4ade80" if ok else "#f87171"
                st.markdown(
                    f'<div style="background:#1f2937;border-radius:4px;'
                    f'padding:8px 12px;font-size:0.80rem;font-weight:600;'
                    f'color:{status_color};">{status_text}</div>',
                    unsafe_allow_html=True,
                )
            except APIError as e:
                st.error(str(e))

    st.divider()

    # Cau hinh so sanh
    st.markdown(
        '<div style="font-size:0.70rem;font-weight:700;color:#4b5563;'
        'letter-spacing:0.08em;margin-bottom:10px;">CAU HINH SO SANH</div>',
        unsafe_allow_html=True,
    )

    top_k = st.slider(
        "Context (top-k chunks)", 1, 10, 5,
        help="So chunk lay lam context cho LLM",
    )

    focus_dieu = st.text_input(
        "Gioi han dieu khoan",
        placeholder="Vi du: Dieu 5",
        help="De trong = so sanh toan bo",
    ) or None

    st.divider()

    # Session info + reset
    sid = ss.get("session_id")
    if sid:
        st.markdown(
            f'<div style="font-size:0.72rem;color:#6b7280;margin-bottom:8px;">'
            f'Session hien tai:<br>'
            f'<span style="font-family:monospace;color:#9ca3af;">{sid}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Dat lai", use_container_width=True):
            ss.reset()
            st.rerun()
    else:
        st.markdown(
            '<div style="font-size:0.72rem;color:#4b5563;">'
            'Chua co session nao.</div>',
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

# ── Tieu de ──────────────────────────────────────────────────────────
st.markdown(
    '<h1 style="font-size:1.55rem;font-weight:700;color:#111827;'
    'letter-spacing:-0.02em;margin:0 0 2px;">'
    'Legal RAG Comparator</h1>'
    '<p style="font-size:0.88rem;color:#6b7280;margin:0 0 24px;">'
    'Phat hien thay doi trong van ban hop dong tieng Viet bang RAG va LLM</p>',
    unsafe_allow_html=True,
)

if DEMO_MODE:
    st.info(
        "Demo mode — Dang dung du lieu mo phong. "
        "Doi DEMO_MODE=false trong .env de ket noi backend that."
    )

# ─────────────────────────────────────────────────────────────────────
# BUOC 1 — TAI LEN
# ─────────────────────────────────────────────────────────────────────

st.markdown(
    '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">'
    '<div style="width:24px;height:24px;background:#111827;border-radius:4px;'
    'display:flex;align-items:center;justify-content:center;'
    'font-size:0.72rem;font-weight:700;color:#fff;flex-shrink:0;">1</div>'
    '<div style="font-size:0.95rem;font-weight:600;color:#111827;">Tai len tai lieu</div>'
    '</div>',
    unsafe_allow_html=True,
)

file_a, file_b = uploader.render()

if file_a and file_b:
    if (ss.get("file_a_name") != file_a.name or ss.get("file_b_name") != file_b.name):
        ss.reset()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    col_btn, col_hint = st.columns([2, 6])
    with col_btn:
        label_ingest = "Xu ly tai lieu" if not DEMO_MODE else "Xu ly (Demo)"
        if st.button(label_ingest, type="primary", use_container_width=True):
            with st.spinner("Dang parse, chunk va index tai lieu..."):
                try:
                    result = get_client().ingest(
                        file_a=(file_a.name, file_a.getvalue(), file_a.type),
                        file_b=(file_b.name, file_b.getvalue(), file_b.type),
                    )
                    ss.set_ingest(result)
                    st.rerun()
                except APIError as e:
                    st.error(str(e))
    with col_hint:
        if not ss.get("ingest_done"):
            st.caption("Ho tro: .docx va .pdf — toi da 20 MB moi file")
else:
    st.markdown(
        '<p style="font-size:0.82rem;color:#9ca3af;margin-top:8px;">'
        'Chon ca 2 file de tiep tuc.</p>',
        unsafe_allow_html=True,
    )

# Ket qua ingest
if ss.get("ingest_done") and ss.get("ingest_result"):
    r = ss.get("ingest_result")
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Thanh trang thai
    st.markdown(
        '<div style="background:#f0fdf4;border:1px solid #bbf7d0;'
        'border-radius:4px;padding:10px 14px;margin-bottom:12px;">'
        '<span style="font-size:0.82rem;color:#166534;font-weight:600;">'
        'Da xu ly thanh cong.</span>'
        f'<span style="font-size:0.80rem;color:#6b7280;margin-left:8px;">'
        f'Session: {r["session_id"]}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chunks A",    r["chunks_a"])
    c2.metric("Chunks B",    r["chunks_b"])
    c3.metric("Tong chunks", r["total_chunks"])
    c4.metric("Session",     r["session_id"])

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.markdown(
    '<hr style="border:none;border-top:1px solid #f3f4f6;margin:20px 0;">',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────
# BUOC 2 — SO SANH
# ─────────────────────────────────────────────────────────────────────

st.markdown(
    '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">'
    '<div style="width:24px;height:24px;'
    f'background:{"#111827" if ss.get("ingest_done") else "#e5e7eb"};'
    'border-radius:4px;display:flex;align-items:center;justify-content:center;'
    'font-size:0.72rem;font-weight:700;'
    f'color:{"#fff" if ss.get("ingest_done") else "#9ca3af"};flex-shrink:0;">2</div>'
    '<div style="font-size:0.95rem;font-weight:600;'
    f'color:{"#111827" if ss.get("ingest_done") else "#9ca3af"};">So sanh tai lieu</div>'
    '</div>',
    unsafe_allow_html=True,
)

if not ss.get("ingest_done"):
    st.markdown(
        '<p style="font-size:0.82rem;color:#9ca3af;margin:0;">Hoan thanh buoc 1 truoc.</p>',
        unsafe_allow_html=True,
    )
else:
    col_btn2, col_note2 = st.columns([2, 6])
    with col_btn2:
        label_cmp = "Bat dau so sanh" if not DEMO_MODE else "So sanh (Demo)"
        if st.button(label_cmp, type="primary", use_container_width=True):
            with st.spinner("LLM dang phan tich tung dieu khoan..."):
                try:
                    result = get_client().compare(
                        session_id=ss.get("session_id"),
                        focus_dieu=focus_dieu,
                        top_k=top_k,
                    )
                    ss.set_compare(result)
                    st.rerun()
                except APIError as e:
                    st.error(str(e))
    with col_note2:
        note = f"Chi so sanh: {focus_dieu}" if focus_dieu else "So sanh toan bo tai lieu"
        st.caption(note)

st.markdown(
    '<hr style="border:none;border-top:1px solid #f3f4f6;margin:20px 0;">',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────
# BUOC 3 — KET QUA
# ─────────────────────────────────────────────────────────────────────

if not ss.get("compare_done"):
    st.stop()

res = ss.get("compare_result")
if not res:
    st.stop()

st.markdown(
    '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">'
    '<div style="width:24px;height:24px;background:#111827;border-radius:4px;'
    'display:flex;align-items:center;justify-content:center;'
    'font-size:0.72rem;font-weight:700;color:#fff;flex-shrink:0;">3</div>'
    '<div style="font-size:0.95rem;font-weight:600;color:#111827;">Ket qua so sanh</div>'
    '</div>',
    unsafe_allow_html=True,
)

# -- Thong ke tong quan ---
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Tong thay doi",   res.get("total_changes",  0))
c2.metric("Them moi",        res.get("changes_added",  0))
c3.metric("Bi xoa",          res.get("changes_deleted",0))
c4.metric("Sua doi",         res.get("changes_modified",0))
c5.metric("Khong doi",       res.get("changes_unchanged",0))
c6.metric("Thoi gian",       seconds(res.get("processing_time", 0)))

# -- Tom tat LLM ---
if res.get("tom_tat"):
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="'
        f'background:#f9fafb;'
        f'border:1px solid #e5e7eb;'
        f'border-left:4px solid #111827;'
        f'border-radius:0 4px 4px 0;'
        f'padding:14px 18px;'
        f'margin:0 0 20px;'
        f'">'
        f'<div style="font-size:0.70rem;font-weight:700;color:#6b7280;'
        f'letter-spacing:0.08em;margin-bottom:8px;">TOM TAT</div>'
        f'<p style="font-size:0.88rem;color:#1f2937;line-height:1.65;margin:0;">'
        f'{res["tom_tat"]}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

change_list = res.get("change_list", [])

if not change_list:
    st.success("Khong phat hien thay doi dang ke giua 2 tai lieu.")
    st.stop()

# -- Bo loc ---
st.markdown(
    '<div style="background:#f9fafb;border:1px solid #e5e7eb;'
    'border-radius:4px;padding:12px 16px;margin-bottom:14px;">',
    unsafe_allow_html=True,
)
type_f, muc_f, kw_f = filter_bar.render(change_list)
st.markdown('</div>', unsafe_allow_html=True)

filtered = filter_bar.apply(change_list, type_f, muc_f, kw_f)

# Dem va nhan biet ten file
ir = ss.get("ingest_result") or {}
name_a = ir.get("file_a_name", "Tai lieu A")
name_b = ir.get("file_b_name", "Tai lieu B")

if not filtered:
    st.warning("Khong co ket qua khop bo loc.")
    st.stop()

# -- Header danh sach ---
count_note = (
    f"Hien thi {len(filtered)} / {len(change_list)} thay doi"
    if len(filtered) < len(change_list)
    else f"{len(change_list)} thay doi"
)
st.markdown(
    f'<div style="'
    f'display:flex;justify-content:space-between;align-items:center;'
    f'margin-bottom:12px;'
    f'">'
    f'<span style="font-size:0.84rem;font-weight:600;color:#374151;">'
    f'Danh sach thay doi</span>'
    f'<span style="font-size:0.78rem;color:#9ca3af;">{count_note}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# -- Danh sach card ---
st.markdown(
    '<div style="border:1px solid #e5e7eb;border-radius:6px;'
    'padding:16px 20px;background:#ffffff;">',
    unsafe_allow_html=True,
)
for i, item in enumerate(filtered):
    result_card.render(item, i, name_a=name_a, name_b=name_b)
st.markdown('</div>', unsafe_allow_html=True)

# -- Download ---
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
st.download_button(
    label="Tai xuong ket qua (JSON)",
    data=json.dumps(res, ensure_ascii=False, indent=2),
    file_name=f"compare_{ss.get('session_id')}.json",
    mime="application/json",
)
