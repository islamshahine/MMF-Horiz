"""Streamlit helpers for project JSON (pp_* / ab_* session snapshot)."""

from __future__ import annotations

import streamlit as st

from engine.project_io import (
    AB_RFQ_SESSION_TO_QUANTITY,
    PERSISTED_STREAMLIT_KEYS,
    coerce_persist_session_value,
)
from engine.units import si_value


def collect_ui_session_persist_dict() -> dict:
    """Snapshot allowed pp_* / ab_* keys from session_state for project JSON."""
    out: dict = {}
    _us = str(st.session_state.get("unit_system") or "metric")
    for k in PERSISTED_STREAMLIT_KEYS:
        if k not in st.session_state:
            continue
        cv = coerce_persist_session_value(st.session_state[k])
        if cv is None:
            continue
        if k in AB_RFQ_SESSION_TO_QUANTITY and _us == "imperial" and isinstance(cv, (int, float)):
            cv = si_value(float(cv), AB_RFQ_SESSION_TO_QUANTITY[k], _us)
        out[k] = cv
    return out
