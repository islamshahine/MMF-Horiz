"""Sidebar staged orifice schedule — submit-only (not inside ``compute_all``)."""
from __future__ import annotations

import streamlit as st

_STAGED_OPTS = (0, 2, 3, 4)


def _default_staged_applied() -> dict:
    return {"collector_staged_orifice_groups": 0}


def render_collector_staged_orifice_form() -> None:
    if st.session_state.pop("_collector_staged_flash", False):
        st.success(
            "Staged orifice schedule updated — **Backwash** → expand "
            "**Optional collector studies — BW sweep & staged perforation Ø** "
            "(just below Collector intelligence)."
        )
    if "_collector_staged_applied" not in st.session_state:
        st.session_state["_collector_staged_applied"] = _default_staged_applied()
    _applied = dict(st.session_state["_collector_staged_applied"])
    _cur = int(_applied.get("collector_staged_orifice_groups", 0) or 0)
    if _cur not in _STAGED_OPTS:
        _cur = 0
    _has = bool(
        (st.session_state.get("mmf_collector_staged_orifices") or {}).get("active")
    )

    with st.form("collector_staged_orifice_form", clear_on_submit=False):
        st.caption(
            "Drill schedule runs **only** when you click the button — "
            "not when you change other sidebar fields."
        )
        if _has:
            st.caption("Last schedule is cached until collector geometry changes or **Apply**.")
        _f_groups = int(
            st.selectbox(
                "Staged perforation Ø bands per lateral",
                options=list(_STAGED_OPTS),
                index=list(_STAGED_OPTS).index(_cur),
                format_func=lambda x: (
                    "Off"
                    if x == 0
                    else f"{x} contiguous Ø bands (drill schedule)"
                ),
                help="Advisory table from frozen per-hole flows — does not re-run the 1B solver.",
            )
        )
        if st.form_submit_button("Run staged orifice schedule", type="primary"):
            st.session_state["_collector_staged_applied"] = {
                "collector_staged_orifice_groups": _f_groups,
            }
            st.session_state["_collector_staged_rerun"] = True
            st.session_state["_collector_staged_flash"] = True
            st.session_state["_collector_studies_expand"] = True
            st.session_state["mmf_pending_main_tab"] = "🔄 Backwash"
            st.session_state["mmf_scroll_to_id"] = "mmf-anchor-collector-optional-studies"
