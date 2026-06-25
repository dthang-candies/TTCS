"""
ui/components/uploader.py — Card upload giống React: nền sáng, viền dashed violet / emerald.
"""

import streamlit as st
from formatters import file_size
from config import MAX_FILE_MB

_CLOUD_SVG = """
<div class="upload-cloud-wrap" style="text-align:center;margin-bottom:8px;">
<svg class="upload-cloud-svg" xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none"
  stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin:0 auto;display:block;">
  <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/>
  <path d="M12 12v9"/><path d="m16 16-4-4-4 4"/>
</svg>
</div>
"""

_HINT = """
<div style="text-align:center;margin-bottom:4px;">
  <p class="upload-hint-title" style="margin:0;font-size:0.875rem;font-weight:600;">Drag and drop file here</p>
  <p class="upload-hint-sub" style="margin:4px 0 0;font-size:0.75rem;">Limit {mb}MB per file • DOCX, PDF</p>
</div>
"""


def _header_a():
    return """
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
      <div style="width:40px;height:40px;border-radius:9999px;background:linear-gradient(145deg,#7c3aed,#4f46e5);
           display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:0.875rem;
           flex-shrink:0;box-shadow:0 1px 3px rgb(15 23 42 / 0.08);">A</div>
      <div style="font-size:0.6875rem;font-weight:800;color:#5b21b6;letter-spacing:0.05em;">
        TÀI LIỆU A — PHIÊN BẢN GỐC
      </div>
    </div>
    """


def _header_b():
    return """
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
      <div style="width:40px;height:40px;border-radius:9999px;background:linear-gradient(145deg,#059669,#0d9488);
           display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:0.875rem;
           flex-shrink:0;box-shadow:0 1px 3px rgb(15 23 42 / 0.08);">B</div>
      <div style="font-size:0.6875rem;font-weight:800;color:#047857;letter-spacing:0.05em;">
        TÀI LIỆU B — PHIÊN BẢN MỚI
      </div>
    </div>
    """


def render() -> tuple:
    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        with st.container(border=True):
            st.markdown(_header_a(), unsafe_allow_html=True)
            st.markdown(_CLOUD_SVG, unsafe_allow_html=True)
            st.markdown(_HINT.format(mb=MAX_FILE_MB), unsafe_allow_html=True)
            st.markdown('<div class="upload-mark upload-mark-a"></div>', unsafe_allow_html=True)
            file_a = st.file_uploader(
                " ",
                type=["docx", "pdf"],
                key="upload_a",
                label_visibility="collapsed",
            )
            if file_a:
                st.markdown(
                    f'<div class="upload-preview" style="padding:10px 14px;margin-top:8px;">'
                    f'<div class="fn" style="font-size:0.8125rem;font-weight:600;">{file_a.name}</div>'
                    f'<div class="sz" style="font-size:0.75rem;margin-top:2px;">{file_size(file_a)}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Chưa chọn file")

    with col_b:
        with st.container(border=True):
            st.markdown(_header_b(), unsafe_allow_html=True)
            st.markdown(_CLOUD_SVG, unsafe_allow_html=True)
            st.markdown(_HINT.format(mb=MAX_FILE_MB), unsafe_allow_html=True)
            st.markdown('<div class="upload-mark upload-mark-b"></div>', unsafe_allow_html=True)
            file_b = st.file_uploader(
                " ",
                type=["docx", "pdf"],
                key="upload_b",
                label_visibility="collapsed",
            )
            if file_b:
                st.markdown(
                    f'<div class="upload-preview" style="padding:10px 14px;margin-top:8px;">'
                    f'<div class="fn" style="font-size:0.8125rem;font-weight:600;">{file_b.name}</div>'
                    f'<div class="sz" style="font-size:0.75rem;margin-top:2px;">{file_size(file_b)}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Chưa chọn file")

    return file_a, file_b
