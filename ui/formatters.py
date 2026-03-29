"""
ui/formatters.py
Khong dung icon, chi dung chu va mau sac.
"""

from config import (
    CHANGE_COLOR, CHANGE_BG, CHANGE_BORDER, CHANGE_LABEL,
    MUC_DO_COLOR, MUC_DO_BG, MUC_DO_LABEL,
)


def badge_html(change_type: str) -> str:
    color  = CHANGE_COLOR.get(change_type,  "#374151")
    bg     = CHANGE_BG.get(change_type,     "#f9fafb")
    border = CHANGE_BORDER.get(change_type, "#9ca3af")
    label  = CHANGE_LABEL.get(change_type,  change_type)
    return (
        f'<span style="'
        f'display:inline-block;'
        f'background:{bg};'
        f'color:{color};'
        f'border:1px solid {border};'
        f'padding:2px 10px;'
        f'border-radius:3px;'
        f'font-size:0.72rem;'
        f'font-weight:700;'
        f'letter-spacing:0.07em;'
        f'">{label}</span>'
    )


def muc_do_html(muc_do: str) -> str:
    color = MUC_DO_COLOR.get(muc_do, "#374151")
    bg    = MUC_DO_BG.get(muc_do,    "#f9fafb")
    label = MUC_DO_LABEL.get(muc_do, muc_do)
    return (
        f'<span style="'
        f'background:{bg};'
        f'color:{color};'
        f'font-size:0.72rem;'
        f'font-weight:600;'
        f'padding:2px 8px;'
        f'border-radius:3px;'
        f'letter-spacing:0.04em;'
        f'">{label.upper()}</span>'
    )


def citation_block(citation: dict | None, label: str, doc_name: str = "", theme: str = "light") -> str:
    dark = theme == "dark"
    title = doc_name if doc_name else f"Tai lieu {label}"

    empty_bg = "#1e293b" if dark else "#f9fafb"
    empty_border = "#334155" if dark else "#e5e7eb"
    empty_color = "#64748b" if dark else "#9ca3af"

    if not citation:
        return (
            f'<div style="'
            f'padding:12px 16px;'
            f'background:{empty_bg};'
            f'border:1px solid {empty_border};'
            f'border-radius:4px;'
            f'color:{empty_color};'
            f'font-size:0.82rem;'
            f'">'
            f'Khong co trich dan tu {title}.'
            f'</div>'
        )

    path  = citation.get("heading_path", "")
    text  = citation.get("text", "").replace("<", "&lt;").replace(">", "&gt;")
    idx   = citation.get("chunk_index", "")

    if label == "A":
        border_color = "#3b82f6"
        header_bg    = "#1e3a5f" if dark else "#eff6ff"
        header_color = "#93c5fd" if dark else "#1e40af"
    else:
        border_color = "#10b981"
        header_bg    = "#064e3b" if dark else "#ecfdf5"
        header_color = "#6ee7b7" if dark else "#065f46"

    content_bg = "#0f172a" if dark else "#ffffff"
    content_color = "#e2e8f0" if dark else "#1f2937"

    path_row = ""
    if path:
        path_row = (
            f'<div style="'
            f'font-size:0.72rem;'
            f'font-weight:600;'
            f'color:{header_color};'
            f'letter-spacing:0.05em;'
            f'margin-bottom:8px;'
            f'">{path}</div>'
        )

    return (
        f'<div style="border:1px solid {border_color};border-radius:4px;overflow:hidden;">'
        f'<div style="'
        f'background:{header_bg};'
        f'padding:6px 12px;'
        f'border-bottom:1px solid {border_color};'
        f'font-size:0.72rem;'
        f'font-weight:700;'
        f'color:{header_color};'
        f'letter-spacing:0.07em;'
        f'">{title.upper()}</div>'
        f'<div style="padding:12px 16px;background:{content_bg};">'
        f'{path_row}'
        f'<div style="'
        f'font-size:0.84rem;'
        f'color:{content_color};'
        f'line-height:1.65;'
        f'white-space:pre-wrap;'
        f'">{text}</div>'
        f'</div>'
        f'</div>'
    )


def file_size(file) -> str:
    mb = len(file.getvalue()) / (1024 * 1024)
    return f"{mb:.2f} MB"


def seconds(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    return f"{int(s // 60)}m {s % 60:.0f}s"
