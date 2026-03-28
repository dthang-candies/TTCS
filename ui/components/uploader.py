"""
ui/components/uploader.py
Khong dung icon.
"""

import streamlit as st
from formatters import file_size


def render() -> tuple:
    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        st.markdown(
            '<div style="'
            'font-size:0.72rem;font-weight:700;'
            'color:#6b7280;letter-spacing:0.08em;'
            'margin-bottom:8px;'
            '">TAI LIEU A &mdash; PHIEN BAN GOC</div>',
            unsafe_allow_html=True,
        )
        file_a = st.file_uploader(
            "Chon file A", type=["docx", "pdf"],
            key="upload_a", label_visibility="collapsed",
        )
        if file_a:
            st.markdown(
                f'<div style="'
                f'padding:10px 14px;'
                f'background:#eff6ff;'
                f'border:1px solid #bfdbfe;'
                f'border-radius:4px;'
                f'margin-top:6px;'
                f'">'
                f'<div style="font-size:0.84rem;font-weight:600;color:#1e40af;">{file_a.name}</div>'
                f'<div style="font-size:0.75rem;color:#6b7280;margin-top:2px;">{file_size(file_a)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with col_b:
        st.markdown(
            '<div style="'
            'font-size:0.72rem;font-weight:700;'
            'color:#6b7280;letter-spacing:0.08em;'
            'margin-bottom:8px;'
            '">TAI LIEU B &mdash; PHIEN BAN MOI</div>',
            unsafe_allow_html=True,
        )
        file_b = st.file_uploader(
            "Chon file B", type=["docx", "pdf"],
            key="upload_b", label_visibility="collapsed",
        )
        if file_b:
            st.markdown(
                f'<div style="'
                f'padding:10px 14px;'
                f'background:#ecfdf5;'
                f'border:1px solid #a7f3d0;'
                f'border-radius:4px;'
                f'margin-top:6px;'
                f'">'
                f'<div style="font-size:0.84rem;font-weight:600;color:#065f46;">{file_b.name}</div>'
                f'<div style="font-size:0.75rem;color:#6b7280;margin-top:2px;">{file_size(file_b)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    return file_a, file_b
