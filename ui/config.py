"""
ui/config.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DEMO_MODE           = os.getenv("DEMO_MODE", "true").lower() == "true"
BACKEND_URL         = os.getenv("BACKEND_URL",         "http://localhost:8000")
API_TIMEOUT         = int(os.getenv("API_TIMEOUT",        "180"))
API_INGEST_TIMEOUT  = int(os.getenv("API_INGEST_TIMEOUT", "300"))

APP_TITLE    = "Legal RAG Comparator"
APP_SUBTITLE = "So sanh van ban hop dong tieng Viet"
APP_ICON     = None
APP_LAYOUT   = "wide"

# -- Loai thay doi --
CHANGE_COLOR = {
    "THEM":               "#166534",
    "XOA":                "#991b1b",
    "SUA":                "#92400e",
    "KHONG DOI NOI DUNG": "#374151",
    "DOI VI TRI":         "#1e40af",
}

CHANGE_BG = {
    "THEM":               "#f0fdf4",
    "XOA":                "#fef2f2",
    "SUA":                "#fffbeb",
    "KHONG DOI NOI DUNG": "#f9fafb",
    "DOI VI TRI":         "#eff6ff",
}

CHANGE_BORDER = {
    "THEM":               "#16a34a",
    "XOA":                "#dc2626",
    "SUA":                "#d97706",
    "KHONG DOI NOI DUNG": "#9ca3af",
    "DOI VI TRI":         "#3b82f6",
}

CHANGE_LABEL = {
    "THEM":               "THEM MOI",
    "XOA":                "BI XOA",
    "SUA":                "SUA DOI",
    "KHONG DOI NOI DUNG": "KHONG DOI",
    "DOI VI TRI":         "DOI VI TRI",
}

MUC_DO_COLOR = {
    "cao":        "#991b1b",
    "trung binh": "#92400e",
    "thap":       "#374151",
}

MUC_DO_BG = {
    "cao":        "#fef2f2",
    "trung binh": "#fffbeb",
    "thap":       "#f9fafb",
}

MUC_DO_LABEL = {
    "cao":        "Cao",
    "trung binh": "Trung binh",
    "thap":       "Thap",
}
