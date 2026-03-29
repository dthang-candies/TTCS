"""
CSS theo theme light/dark — bám palette Slate / Indigo / Emerald.
Bao gồm layout phẳng: sidebar 300px cố định, gỡ viền/bóng mặc định Streamlit.
"""


def flat_layout_css(theme: str) -> str:
    """Quy tắc layout bắt buộc: sidebar 300px, khối layout không viền/bóng, nút phẳng."""
    dark = theme == "dark"
    hdr_btn_border = "#334155" if dark else "#e2e8f0"
    exp_bg = "#1e293b" if dark else "#ffffff"
    exp_border = "#334155" if dark else "#e2e8f0"

    return f"""
<style>
/* ── 1) Sidebar width EXACTLY 300px (CRITICAL) ─────────────────────────── */
[data-testid="stSidebar"] {{
    min-width: 300px !important;
    max-width: 300px !important;
    width: 300px !important;
}}

/* ── 2) Layout chrome: zero default borders/shadows (Streamlit blocks) ───── */
div[data-testid="stColumn"],
div[data-testid="column"],
[data-testid="stColumn"],
[data-testid="column"],
div[data-testid="stVerticalBlock"],
div[data-testid="stHorizontalBlock"] {{
    border: none !important;
    box-shadow: none !important;
    background-color: transparent !important;
}}
.stDeployButton {{
    display: none !important;
}}

/* Expander: global strip; restore chỉ trong main để vẫn đọc được */
[data-testid="stExpander"] {{
    border: none !important;
    box-shadow: none !important;
    background-color: transparent !important;
}}
[data-testid="stMain"] [data-testid="stExpander"] {{
    border: 1px solid {exp_border} !important;
    border-radius: 8px !important;
    background: {exp_bg} !important;
    box-shadow: none !important;
}}
[data-testid="stMain"] [data-testid="stExpander"] details {{
    background: {exp_bg} !important;
    border: none !important;
    border-radius: 8px !important;
}}
[data-testid="stMain"] [data-testid="stExpander"] summary {{
    background: {"#1e293b" if dark else "#f8fafc"} !important;
    border-radius: 8px !important;
    padding: 0.65rem 1rem !important;
}}
[data-testid="stMain"] [data-testid="stExpander"] summary,
[data-testid="stMain"] [data-testid="stExpander"] summary *,
[data-testid="stMain"] [data-testid="stExpander"] summary span,
[data-testid="stMain"] [data-testid="stExpander"] summary p,
[data-testid="stMain"] [data-testid="stExpander"] [data-testid="stExpanderToggleIcon"] {{
    color: {"#e2e8f0" if dark else "#1e293b"} !important;
    -webkit-text-fill-color: {"#e2e8f0" if dark else "#1e293b"} !important;
}}
[data-testid="stMain"] [data-testid="stExpander"] [data-testid="stExpanderToggleIcon"] svg {{
    fill: {"#e2e8f0" if dark else "#1e293b"} !important;
    stroke: {"#e2e8f0" if dark else "#1e293b"} !important;
}}

/* ── 3) Buttons: thin slate border, flat, 8px radius ───────────────────── */
.stButton > button {{
    border: 1px solid #e2e8f0 !important;
    box-shadow: none !important;
    border-radius: 8px !important;
}}

/* Primary / secondary / disabled — giữ hierarchy rõ */
.stButton > button[kind="primary"]:not(:disabled) {{
    background: #4f46e5 !important;
    color: #ffffff !important;
    border-color: #4f46e5 !important;
}}
.stButton > button[kind="primary"]:hover:not(:disabled) {{
    background: #4338ca !important;
    border-color: #4338ca !important;
}}
.stButton > button[kind="primary"]:disabled {{
    background: {"#334155" if dark else "#e2e8f0"} !important;
    color: #94a3b8 !important;
    border: 1px solid {"#475569" if dark else "#e2e8f0"} !important;
    cursor: not-allowed !important;
    opacity: 1 !important;
}}

/* Header toolbar (Kiểm tra / Dark): đặt trong header_toolbar_btn_css() — load sau cùng */

/* Sidebar: nút full width, nền nhạt */
[data-testid="stSidebar"] .stButton > button {{
    width: 100% !important;
}}
[data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {{
    border: 1px solid {hdr_btn_border} !important;
    background: {"#1e293b" if dark else "#f1f5f9"} !important;
    color: {"#e2e8f0" if dark else "#334155"} !important;
}}
[data-testid="stSidebar"] .stButton > button:not([kind="primary"]):hover:not(:disabled) {{
    background: {"#334155" if dark else "#e2e8f0"} !important;
}}

/* Bỏ khung kép bọc nút trong main (trừ sidebar) */
[data-testid="stMain"] div.stButton {{
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}}
</style>
"""


def header_toolbar_btn_css(theme: str) -> str:
    """
    Hai nút Kiểm tra / Dark|Light nằm trong st.container(key="hdr_toolbar")
    → Streamlit gán class st-key-hdr_toolbar (ổn định hơn stHorizontalBlock).

    Light: nền xám nhạt; Dark: nền slate.
    """
    dark = theme == "dark"
    bg = "#334155" if dark else "#e2e8f0"
    fg = "#f8fafc" if dark else "#0f172a"
    bd = "#475569" if dark else "#cbd5e1"
    h_bg = "#475569" if dark else "#cbd5e1"
    h_fg = "#f8fafc" if dark else "#0f172a"

    # Container key="hdr_toolbar" → class dạng st-key-$$ID-<hash>-hdr_toolbar (sanitize), không phải .st-key-hdr_toolbar
    sel = """[data-testid="stMain"] [class*="st-key"][class*="hdr_toolbar"] .stButton > button"""

    return f"""
<style>
{sel} {{
    background-color: {bg} !important;
    background-image: none !important;
    color: {fg} !important;
    border: 1px solid {bd} !important;
    box-shadow: none !important;
    border-radius: 8px !important;
    width: auto !important;
    min-width: unset !important;
    -webkit-text-fill-color: {fg} !important;
}}
{sel} *,
{sel} p,
{sel} span {{
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
}}
{sel}:hover:not(:disabled) {{
    background-color: {h_bg} !important;
    background-image: none !important;
    color: {h_fg} !important;
    -webkit-text-fill-color: {h_fg} !important;
    border-color: {bd} !important;
}}
{sel}:hover:not(:disabled) *,
{sel}:hover:not(:disabled) p,
{sel}:hover:not(:disabled) span {{
    color: inherit !important;
    -webkit-text-fill-color: inherit !important;
}}
</style>
"""


def streamlit_css(theme: str) -> str:
    dark = theme == "dark"

    app_bg = "#020617" if dark else "#f8fafc"
    main_text = "#f8fafc" if dark else "#0f172a"
    muted = "#94a3b8" if dark else "#64748b"

    sb_bg = "#0f172a" if dark else "#ffffff"
    sb_border = "#334155" if dark else "#e2e8f0"
    sb_label = "#94a3b8" if dark else "#64748b"
    sb_title = "#f8fafc" if dark else "#0f172a"

    card_bg = "#1e293b" if dark else "#ffffff"
    card_border = "#334155" if dark else "#e2e8f0"
    card_shadow = "none"

    clause_bg = "#020617" if dark else "#ffffff"
    clause_text = "#f8fafc" if dark else "#1e293b"
    clause_ph = "#64748b" if dark else "#94a3b8"

    metric_bg = card_bg
    metric_label = "#94a3b8" if dark else "#64748b"
    metric_val = "#f8fafc" if dark else "#0f172a"

    base = f"""
<style>
html, body, [class*="css"] {{
    font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif !important;
}}

#MainMenu {{ visibility: hidden !important; height: 0 !important; }}
footer {{ visibility: hidden !important; height: 0 !important; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}
[data-testid="stDecoration"],
a[href*="streamlit.app/cloud"] {{
    display: none !important;
}}

.stApp, [data-testid="stAppViewContainer"] {{
    background: {app_bg} !important;
    color: {main_text};
}}

[data-testid="stMain"] {{
    background: {app_bg} !important;
}}
[data-testid="stMain"] > div {{
    background: transparent !important;
    box-shadow: none !important;
}}
.block-container {{
    padding-top: 1.25rem !important;
    padding-bottom: 2.5rem !important;
    padding-left: clamp(1rem, 3vw, 2.5rem) !important;
    padding-right: clamp(1rem, 3vw, 2.5rem) !important;
    max-width: min(1320px, 100%) !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}

[data-testid="stMain"] h1 {{
    font-size: clamp(1.35rem, 2.2vw, 1.75rem) !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    padding-bottom: 0.15rem !important;
}}
[data-testid="stMain"] h2 {{
    font-size: 1.125rem !important;
    font-weight: 600 !important;
    margin-top: 0.5rem !important;
}}
[data-testid="stMain"] h3 {{
    font-size: 1.125rem !important;
    font-weight: 600 !important;
    color: {main_text} !important;
}}

section.main,
.main {{
    background: transparent !important;
}}

[data-testid="stHorizontalBlock"] {{
    gap: 1.25rem !important;
    align-items: flex-start !important;
}}

/* Cột trong main: không viền xám */
[data-testid="stMain"] [data-testid="column"],
[data-testid="stMain"] [data-testid="stColumn"] {{
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
}}
[data-testid="stMain"] [data-testid="column"] > div[data-testid="stVerticalBlock"],
[data-testid="stMain"] [data-testid="stColumn"] > div[data-testid="stVerticalBlock"],
[data-testid="stMain"] [data-testid="column"] [data-testid="stVerticalBlock"] > div {{
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}}
[data-testid="stMain"] [data-testid="column"] .element-container {{
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}}

/* Header row đầu tiên: phẳng */
[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type {{
    align-items: center !important;
    flex-wrap: wrap !important;
    gap: 0.5rem 1.25rem !important;
    padding: 0.35rem 0 !important;
    margin-bottom: 0.65rem !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}}
[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"],
[data-testid="stMain"] [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="stColumn"] {{
    background: transparent !important;
    border: none !important;
}}

/* Sidebar nền + không dùng khung BorderWrapper có viền xám */
[data-testid="stSidebar"] {{
    background: {sb_bg} !important;
    border-right: 1px solid {sb_border} !important;
}}
[data-testid="stSidebar"] .block-container {{
    padding-top: 1rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}}
[data-testid="stSidebar"] label {{ color: {sb_label} !important; }}
[data-testid="stSidebar"] [data-baseweb="typo"] {{ color: {sb_title} !important; }}

[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    padding: 0 !important;
    margin-bottom: 1rem !important;
}}

[data-testid="stSidebar"] .stTextInput > div > div > input {{
    background: {clause_bg} !important;
    color: {clause_text} !important;
    border: 1px solid {"#475569" if dark else "#e2e8f0"} !important;
    border-radius: 0.5rem !important;
}}
[data-testid="stSidebar"] .stTextInput > div > div > input::placeholder {{
    color: {clause_ph} !important;
}}

[data-testid="stSlider"] [data-baseweb="slider"] div[data-testid="stTickBarMax"] {{
    background: {"#334155" if dark else "#e2e8f0"} !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] div[data-testid="stTickBarMin"] {{
    background: #6366f1 !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"],
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stSliderThumb"] {{
    background: #4f46e5 !important;
    border: 2px solid #ffffff !important;
}}

.stButton > button {{
    font-size: 0.875rem !important;
    font-weight: 600 !important;
    padding: 0.5rem 1rem !important;
    white-space: nowrap !important;
    transition: background 0.15s, color 0.15s, border-color 0.15s !important;
}}

/* Upload */
.upload-mark-a ~ div [data-testid="stFileUploader"],
.upload-mark-a ~ * [data-testid="stFileUploader"] {{
    border: 2px dashed {"#a5b4fc" if not dark else "#6366f1"} !important;
    border-radius: 0.75rem !important;
    background: {"#1e293b" if dark else "rgba(238, 242, 255, 0.65)"} !important;
    padding: 6px !important;
    transition: background 0.2s, border-color 0.2s !important;
}}
.upload-mark-b ~ div [data-testid="stFileUploader"],
.upload-mark-b ~ * [data-testid="stFileUploader"] {{
    border: 2px dashed {"#6ee7b7" if not dark else "#34d399"} !important;
    border-radius: 0.75rem !important;
    background: {"#1e293b" if dark else "rgba(236, 253, 245, 0.65)"} !important;
    padding: 6px !important;
    transition: background 0.2s, border-color 0.2s !important;
}}
.upload-mark-a ~ div [data-testid="stFileUploader"]:hover,
.upload-mark-a ~ * [data-testid="stFileUploader"]:hover {{
    background: {"#334155" if dark else "rgba(224, 231, 255, 0.85)"} !important;
}}
.upload-mark-b ~ div [data-testid="stFileUploader"]:hover,
.upload-mark-b ~ * [data-testid="stFileUploader"]:hover {{
    background: {"#334155" if dark else "rgba(209, 250, 229, 0.9)"} !important;
}}
.upload-mark-a ~ div [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"],
.upload-mark-b ~ div [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"],
.upload-mark-a ~ * [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"],
.upload-mark-b ~ * [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {{
    background: transparent !important;
    border: none !important;
}}

/* Global file uploader dropzone override — fix dark bg in light mode */
[data-testid="stFileUploaderDropzone"] {{
    background: {"#1e293b" if dark else "transparent"} !important;
    border: {"1px solid #334155" if dark else "none"} !important;
    border-radius: 0.5rem !important;
}}
[data-testid="stFileUploaderDropzone"] * {{
    color: {"#cbd5e1" if dark else "#334155"} !important;
}}
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] small * {{
    color: {"#94a3b8" if dark else "#64748b"} !important;
}}

[data-testid="stFileUploader"] label,
[data-testid="stFileUploader"] label * {{
    color: {"#94a3b8" if dark else "#475569"} !important;
}}
[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] * {{
    font-size: 0.8125rem !important;
    color: {"#cbd5e1" if dark else "#334155"} !important;
}}
[data-testid="stFileUploaderDropzoneInstructions"] small {{
    color: {"#94a3b8" if dark else "#64748b"} !important;
}}
[data-testid="stFileUploaderDropzone"] button {{
    background: {"#1e293b" if dark else "#ffffff"} !important;
    color: {"#e2e8f0" if dark else "#334155"} !important;
    border: 1px solid {"#475569" if dark else "#e2e8f0"} !important;
    border-radius: 0.5rem !important;
    box-shadow: none !important;
}}
[data-testid="stFileUploader"] svg {{
    stroke: {"#94a3b8" if dark else "#64748b"} !important;
    opacity: 0.9 !important;
}}

[data-testid="stMetric"] {{
    background: {metric_bg};
    border: 1px solid {card_border};
    border-radius: 0.75rem;
    padding: 12px 16px !important;
    box-shadow: {card_shadow};
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    color: {metric_label} !important;
    text-transform: uppercase !important;
}}
[data-testid="stMetricValue"] {{
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: {metric_val} !important;
}}

.stSelectbox > div > div,
.stTextInput > div > div > input {{
    font-size: 0.875rem !important;
    border-radius: 0.5rem !important;
}}

[data-testid="stAppViewContainer"] .block-container .stTextInput > div > div > input {{
    background: {card_bg} !important;
    color: {main_text} !important;
    border-color: {card_border} !important;
}}

.stSpinner > div {{ border-top-color: #4f46e5 !important; }}
.stAlert {{ border-radius: 0.75rem !important; }}

/*
 * Streamlit bọc nội dung mỗi cột bằng [data-testid="stVerticalBlockBorderWrapper"].
 * KHÔNG được gán viền toàn main — nếu không mọi ô trong st.columns (kể cả hàng header)
 * sẽ có khung xám. Viền nội dung chỉ đặt trong HTML/markdown khi cần.
 */
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    margin-bottom: 0 !important;
    box-shadow: none !important;
}}
/* Một số bản Streamlit bọc thêm lớp emotion — gỡ viền trong khối cột */
[data-testid="stMain"] [data-testid="column"] [class*="st-emotion-cache"],
[data-testid="stMain"] [data-testid="stColumn"] [class*="st-emotion-cache"] {{
    border: none !important;
    box-shadow: none !important;
}}

.sb-section-title {{
    font-size: 0.6875rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    color: {sb_label} !important;
    margin: 0 0 0.75rem 0 !important;
    text-transform: uppercase !important;
}}

.demo-mode-pill {{
    text-align: center;
    padding: 0.6rem 1rem;
    border-radius: 0.5rem;
    font-weight: 600;
    font-size: 0.875rem;
    line-height: 1.35;
    letter-spacing: 0.02em;
    background: {"#312e81" if dark else "#eef2ff"} !important;
    color: {"#c7d2fe" if dark else "#4338ca"} !important;
    border: 1px solid {"#4338ca" if dark else "#c7d2fe"} !important;
}}

[data-testid="stAppViewContainer"] .stCaption {{ color: {muted} !important; }}

.upload-preview {{
    background: {"#334155" if dark else "#f1f5f9"} !important;
    border: 1px solid {card_border} !important;
    border-radius: 0.5rem !important;
}}
.upload-preview .fn {{ color: {"#e2e8f0" if dark else "#334155"} !important; }}
.upload-preview .sz {{ color: {"#94a3b8" if dark else "#64748b"} !important; }}

.upload-cloud-svg {{ stroke: {"#64748b" if dark else "#94a3b8"} !important; }}
.upload-hint-title {{ color: {"#e2e8f0" if dark else "#334155"} !important; }}
.upload-hint-sub {{ color: {"#94a3b8" if dark else "#64748b"} !important; }}

.step-block {{ margin-bottom: 0.25rem; }}

::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {app_bg}; }}
::-webkit-scrollbar-thumb {{ background: {"#475569" if dark else "#cbd5e1"}; border-radius: 3px; }}
</style>
"""

    return flat_layout_css(theme) + base + header_toolbar_btn_css(theme)
