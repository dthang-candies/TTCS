"""
ui/session_state.py — Quản lý st.session_state tập trung
"""

import streamlit as st


def init():
    defaults = {
        "session_id":       None,
        "ingest_done":      False,
        "compare_done":     False,
        "ingest_result":    None,
        "compare_result":   None,
        "file_a_name":      None,
        "file_b_name":      None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset():
    for k in ["session_id", "ingest_result", "compare_result",
              "file_a_name", "file_b_name"]:
        st.session_state[k] = None
    st.session_state["ingest_done"]  = False
    st.session_state["compare_done"] = False


def set_ingest(result: dict):
    st.session_state["session_id"]     = result["session_id"]
    st.session_state["ingest_result"]  = result
    st.session_state["ingest_done"]    = True
    st.session_state["file_a_name"]    = result.get("file_a_name", "")
    st.session_state["file_b_name"]    = result.get("file_b_name", "")
    st.session_state["compare_done"]   = False
    st.session_state["compare_result"] = None


def set_compare(result: dict):
    st.session_state["compare_result"] = result
    st.session_state["compare_done"]   = True


def get(key, default=None):
    return st.session_state.get(key, default)
