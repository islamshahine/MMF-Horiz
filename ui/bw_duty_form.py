"""Sidebar BW duty-chart form — submit-only (no full plant recompute on widget change)."""
from __future__ import annotations

import streamlit as st


_STAGGER_OPTS = (
    "feasibility_trains",
    "optimized_trains",
    "tariff_aware_v3",
    "milp_lite",
    "uniform",
)
_STAGGER_LABELS = {
    "feasibility_trains": "Feasibility BW trains (recommended)",
    "optimized_trains": "Optimized trains (peak only)",
    "tariff_aware_v3": "Tariff-aware v3 (peak + off-peak + blackouts)",
    "milp_lite": "MILP lite (C5) — ILP ≤2 d; 3+ d uses feasibility spacing",
    "uniform": "Uniform (legacy comparison)",
}


def _default_bw_duty_applied() -> dict:
    return {
        "bw_schedule_horizon_days": 7,
        "bw_timeline_stagger": "feasibility_trains",
        "bw_peak_tariff_start_h": 14.0,
        "bw_peak_tariff_end_h": 22.0,
        "bw_tariff_peak_multiplier": 1.5,
        "bw_maintenance_blackout_enabled": False,
        "bw_maintenance_blackout_t0_h": 0.0,
        "bw_maintenance_blackout_t1_h": 0.0,
    }


def render_bw_duty_chart_form(out: dict) -> None:
    """
    Duty chart settings (inside ``st.form``).

    Widget changes do **not** rerun the app until **Update duty chart** is clicked.
    """
    if st.session_state.pop("_bw_duty_flash", False):
        st.success(
            "Duty chart updated — open **Backwash** (main tab) → **§5 Filter duty timeline**."
        )
    if "_bw_duty_applied" not in st.session_state:
        st.session_state["_bw_duty_applied"] = _default_bw_duty_applied()
    _applied = dict(st.session_state["_bw_duty_applied"])
    _hz_opts = [1, 3, 7, 14]
    try:
        _hz_idx = _hz_opts.index(int(_applied.get("bw_schedule_horizon_days", 7)))
    except ValueError:
        _hz_idx = 2
    _stagger_cur = str(_applied.get("bw_timeline_stagger", "feasibility_trains"))
    if _stagger_cur not in _STAGGER_OPTS:
        _stagger_cur = "feasibility_trains"

    with st.form("bw_duty_chart_form", clear_on_submit=False):
        st.caption(
            "Changes apply only when you click **Update duty chart** — "
            "switching stagger here does **not** rerun the full model."
        )
        _f_horizon = int(
            st.selectbox(
                "Duty chart horizon (days)",
                options=_hz_opts,
                index=_hz_idx,
                help="Multi-day Gantt on Backwash tab · scheduling aid only (not DCS).",
            )
        )
        _f_stagger = st.selectbox(
            "Duty chart stagger (Backwash tab)",
            options=list(_STAGGER_OPTS),
            index=list(_STAGGER_OPTS).index(_stagger_cur),
            format_func=lambda x: _STAGGER_LABELS[x],
            help="MILP CBC runs only for 1–2 d horizons; 3+ d uses fast feasibility-train spacing (not full v3 search).",
        )
        _pt1, _pt2, _pt3 = st.columns(3)
        _f_pt0 = float(
            _pt1.number_input(
                "Peak tariff from (h)",
                min_value=0.0,
                max_value=23.5,
                value=float(_applied.get("bw_peak_tariff_start_h", 14.0)),
                step=0.5,
            )
        )
        _f_pt1 = float(
            _pt2.number_input(
                "Peak tariff to (h)",
                min_value=0.5,
                max_value=24.0,
                value=float(_applied.get("bw_peak_tariff_end_h", 22.0)),
                step=0.5,
            )
        )
        _f_mult = float(
            _pt3.number_input(
                "Peak tariff × vs off-peak",
                min_value=1.0,
                max_value=5.0,
                value=float(_applied.get("bw_tariff_peak_multiplier", 1.5)),
                step=0.1,
            )
        )
        _f_maint = bool(
            st.checkbox(
                "Maintenance blackout on duty horizon",
                value=bool(_applied.get("bw_maintenance_blackout_enabled", False)),
            )
        )
        _mb1, _mb2 = st.columns(2)
        _f_mb0 = float(
            _mb1.number_input(
                "Blackout start (h from t=0)",
                min_value=0.0,
                value=float(_applied.get("bw_maintenance_blackout_t0_h", 0.0)),
                step=1.0,
            )
        )
        _f_mb1 = float(
            _mb2.number_input(
                "Blackout end (h)",
                min_value=0.0,
                value=float(_applied.get("bw_maintenance_blackout_t1_h", 24.0)),
                step=1.0,
            )
        )
        if st.form_submit_button("Update duty chart", type="primary"):
            st.session_state["_bw_duty_applied"] = {
                "bw_schedule_horizon_days": _f_horizon,
                "bw_timeline_stagger": _f_stagger,
                "bw_peak_tariff_start_h": _f_pt0,
                "bw_peak_tariff_end_h": _f_pt1,
                "bw_tariff_peak_multiplier": _f_mult,
                "bw_maintenance_blackout_enabled": _f_maint,
                "bw_maintenance_blackout_t0_h": _f_mb0 if _f_maint else 0.0,
                "bw_maintenance_blackout_t1_h": _f_mb1 if _f_maint else 0.0,
            }
            st.session_state["_bw_duty_dirty"] = True
            st.session_state["_bw_duty_only_rerun"] = True
            st.session_state["_bw_duty_flash"] = True
            st.session_state["mmf_pending_main_tab"] = "🔄 Backwash"

    out.update(st.session_state["_bw_duty_applied"])
    st.caption(
        "**Workflow:** pick stagger → **Update duty chart** → view timeline. "
        "**Feasibility** is fastest on 7 d. **MILP lite** solves ILP only for 1–2 d horizons. "
        "**Tariff-aware v3** on 7 d may take ~10–30 s with many filters."
    )
