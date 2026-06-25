"""
ui/components/filter_bar.py
Khong dung icon trong filter options.
"""

import streamlit as st
from config import CHANGE_LABEL


def render(change_list: list) -> tuple[str, str, str]:
    col1, col2, col3 = st.columns([2, 2, 3], gap="medium")

    # Lay cac loai co trong danh sach
    available_types = sorted({c.get("change_type", "") for c in change_list if c.get("change_type")})
    type_options = ["Tat ca"] + available_types

    muc_do_options = ["Tat ca", "cao", "trung binh", "thap"]
    muc_do_labels  = {
        "Tat ca":    "Tat ca muc do",
        "cao":       "Cao",
        "trung binh":"Trung binh",
        "thap":      "Thap",
    }

    with col1:
        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;color:#6b7280;'
            'letter-spacing:0.06em;margin-bottom:6px;">LOAI THAY DOI</div>',
            unsafe_allow_html=True,
        )
        type_sel = st.selectbox(
            "Loai", type_options,
            format_func=lambda x: "Tat ca loai" if x == "Tat ca" else CHANGE_LABEL.get(x, x),
            key="filter_type", label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;color:#6b7280;'
            'letter-spacing:0.06em;margin-bottom:6px;">MUC DO</div>',
            unsafe_allow_html=True,
        )
        muc_sel = st.selectbox(
            "Muc do", muc_do_options,
            format_func=lambda x: muc_do_labels.get(x, x),
            key="filter_muc", label_visibility="collapsed",
        )

    with col3:
        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;color:#6b7280;'
            'letter-spacing:0.06em;margin-bottom:6px;">TIM KIEM</div>',
            unsafe_allow_html=True,
        )
        kw = st.text_input(
            "Tim kiem", placeholder="Noi dung, dieu khoan...",
            key="filter_kw", label_visibility="collapsed",
        )

    type_filter = type_sel if type_sel != "Tat ca" else "Tat ca"
    muc_filter  = muc_sel  if muc_sel  != "Tat ca" else "Tat ca"

    return type_filter, muc_filter, kw.strip()


def apply(change_list: list, type_filter: str, muc_filter: str, kw: str) -> list:
    result = change_list
    if type_filter != "Tat ca":
        result = [c for c in result if c.get("change_type") == type_filter]
    if muc_filter != "Tat ca":
        result = [c for c in result if c.get("muc_do") == muc_filter]
    if kw:
        kl = kw.lower()
        result = [
            c for c in result
            if kl in c.get("mo_ta",   "").lower()
            or kl in c.get("vi_tri",  "").lower()
            or kl in (c.get("citation_a") or {}).get("text", "").lower()
            or kl in (c.get("citation_b") or {}).get("text", "").lower()
        ]
    return result
