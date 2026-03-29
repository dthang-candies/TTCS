"""
ui/components/result_card.py
Card hien thi 1 thay doi. Khong dung icon.
"""

import streamlit as st
from formatters import badge_html, muc_do_html, citation_block
from config import CHANGE_BORDER


def render(item: dict, index: int, name_a: str = "Tai lieu A", name_b: str = "Tai lieu B", theme: str = "light"):
    dark = theme == "dark"
    change_type  = item.get("change_type", "SUA")
    left_color   = CHANGE_BORDER.get(change_type, "#9ca3af")
    mo_ta        = item.get("mo_ta",    "")
    vi_tri       = item.get("vi_tri",   "")
    muc_do       = item.get("muc_do",   "trung binh")
    ly_giai      = item.get("ly_giai",  "")
    citation_a   = item.get("citation_a")
    citation_b   = item.get("citation_b")
    has_citation = bool(citation_a or citation_b)

    # Theme-aware colors
    mo_ta_color = "#f1f5f9" if dark else "#111827"
    ly_giai_color = "#94a3b8" if dark else "#6b7280"
    vi_tri_color = "#cbd5e1" if dark else "#6b7280"
    vi_tri_bg = "#334155" if dark else "#f3f4f6"
    divider_color = "#334155" if dark else "#f3f4f6"

    # ── Wrapper voi duong ke trai mau ──────────────────────────────────
    st.markdown(
        f'<div style="'
        f'border-left:4px solid {left_color};'
        f'padding-left:16px;'
        f'margin-bottom:4px;'
        f'">',
        unsafe_allow_html=True,
    )

    # ── Hang 1: Badge + Vi tri + Muc do ────────────────────────────────
    col_badge, col_loc, col_muc = st.columns([2, 5, 1.5])

    with col_badge:
        st.markdown(badge_html(change_type), unsafe_allow_html=True)

    with col_loc:
        if vi_tri:
            st.markdown(
                f'<span style="'
                f'font-size:0.80rem;'
                f'color:{vi_tri_color};'
                f'font-family:monospace;'
                f'background:{vi_tri_bg};'
                f'padding:2px 8px;'
                f'border-radius:3px;'
                f'">{vi_tri}</span>',
                unsafe_allow_html=True,
            )

    with col_muc:
        st.markdown(muc_do_html(muc_do), unsafe_allow_html=True)

    # ── Hang 2: Mo ta ──────────────────────────────────────────────────
    st.markdown(
        f'<p style="'
        f'font-size:0.92rem;'
        f'font-weight:500;'
        f'color:{mo_ta_color};'
        f'margin:8px 0 4px;'
        f'line-height:1.5;'
        f'">{mo_ta}</p>',
        unsafe_allow_html=True,
    )

    # ── Ly giai (neu co) ───────────────────────────────────────────────
    if ly_giai:
        st.markdown(
            f'<p style="'
            f'font-size:0.80rem;'
            f'color:{ly_giai_color};'
            f'margin:0 0 6px;'
            f'font-style:italic;'
            f'">{ly_giai}</p>',
            unsafe_allow_html=True,
        )

    # ── Trich dan (expander) ────────────────────────────────────────────
    if has_citation:
        with st.expander("Xem trich dan tu van ban goc"):
            ca_col, cb_col = st.columns(2, gap="medium")

            with ca_col:
                st.markdown(
                    citation_block(citation_a, "A", name_a, theme=theme),
                    unsafe_allow_html=True,
                )

            with cb_col:
                st.markdown(
                    citation_block(citation_b, "B", name_b, theme=theme),
                    unsafe_allow_html=True,
                )

    st.markdown('</div>', unsafe_allow_html=True)

    # Duong ke mo giua cac card
    st.markdown(
        f'<div style="height:1px;background:{divider_color};margin:14px 0;"></div>',
        unsafe_allow_html=True,
    )
