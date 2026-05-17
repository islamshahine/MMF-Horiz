"""Sidebar collector BW-flow sweep — submit-only (no sweep inside ``compute_all``)."""
from __future__ import annotations

import streamlit as st


def _default_collector_envelope_applied() -> dict:
    return {
        "collector_bw_envelope_n_points": 7,
        "collector_bw_envelope_q_low_frac": 0.55,
        "collector_bw_envelope_q_high_frac": 1.15,
    }


def render_collector_bw_envelope_form() -> None:
    if st.session_state.pop("_collector_envelope_flash", False):
        st.success(
            "BW-flow sweep complete — open **Backwash** → collector / underdrain studies for charts."
        )
    if "_collector_envelope_applied" not in st.session_state:
        st.session_state["_collector_envelope_applied"] = _default_collector_envelope_applied()
    _applied = dict(st.session_state["_collector_envelope_applied"])
    _has = bool(
        (st.session_state.get("mmf_collector_bw_envelope") or {}).get("active")
    )

    with st.form("collector_bw_envelope_form", clear_on_submit=False):
        st.caption(
            "The sweep runs **only** when you click **Run BW-flow sweep** — "
            "not when you open this panel or change other sidebar fields."
        )
        if _has:
            st.caption("Last sweep is cached for this geometry until you change collector inputs or **Apply**.")
        _e1, _e2 = st.columns(2)
        with _e1:
            _f_n = int(
                st.number_input(
                    "Sweep base points (3–25)",
                    min_value=3,
                    max_value=25,
                    step=1,
                    value=int(_applied.get("collector_bw_envelope_n_points", 7)),
                )
            )
        with _e2:
            _f_lo = float(
                st.number_input(
                    "Low flow / design",
                    min_value=0.05,
                    max_value=0.98,
                    step=0.05,
                    format="%.2f",
                    value=float(_applied.get("collector_bw_envelope_q_low_frac", 0.55)),
                )
            )
        _f_hi = float(
            st.number_input(
                "High flow / design",
                min_value=1.02,
                max_value=1.80,
                step=0.05,
                format="%.2f",
                value=float(_applied.get("collector_bw_envelope_q_high_frac", 1.15)),
            )
        )
        st.caption(
            "Design-point BW flow is always included. "
            "Feasible = converged distribution and imbalance ≤ 55% (screening cap)."
        )
        if st.form_submit_button("Run BW-flow sweep", type="primary"):
            st.session_state["_collector_envelope_applied"] = {
                "collector_bw_envelope_n_points": _f_n,
                "collector_bw_envelope_q_low_frac": _f_lo,
                "collector_bw_envelope_q_high_frac": _f_hi,
            }
            st.session_state["_collector_envelope_rerun"] = True
            st.session_state["_collector_envelope_flash"] = True
            st.session_state["mmf_pending_main_tab"] = "🔄 Backwash"
