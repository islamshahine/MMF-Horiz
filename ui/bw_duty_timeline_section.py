"""Backwash §5 — multi-day duty timeline (shared by full tab and fast duty-chart rerun)."""
from __future__ import annotations

import streamlit as st

from ui.helpers import (
    bw_timeline_schedule_summary_html,
    bw_timeline_stagger_label,
    render_metric_explain_panel,
)


def render_bw_duty_timeline_section(
    inputs: dict,
    computed: dict,
    *,
    bw_timeline: dict | None = None,
    expanded: bool = False,
    show_compare_panel: bool = True,
) -> dict:
    """Render §5 expander; returns the timeline dict used for the Gantt chart."""
    _applied = st.session_state.get("_bw_duty_applied") or {}
    _tl = dict(bw_timeline if bw_timeline is not None else (computed.get("bw_timeline") or {}))
    n_filters = int(inputs.get("n_filters", 1) or 1)
    streams = int(inputs.get("streams", 1) or 1)
    hydraulic_assist_bw = int(inputs.get("hydraulic_assist", 0) or 0)

    with st.expander("5 · Filter duty timeline (multi-day schematic)", expanded=expanded):
        _cached_tl = None
        if show_compare_panel:
            from ui.bw_stagger_compare_panel import render_bw_stagger_compare_panel

            _cached_tl = render_bw_stagger_compare_panel(inputs, computed)
            if _cached_tl is not None:
                _tl = _cached_tl
        if _cached_tl is None:
            if st.session_state.get("_bw_duty_dirty"):
                st.info(
                    "Click **Update duty chart** in the sidebar (BW section) to apply a new stagger model."
                )
            elif _tl.get("stagger_model") != _applied.get("bw_timeline_stagger"):
                st.warning(
                    "Sidebar stagger differs from this chart — click **Update duty chart** in the BW section."
                )

        _sm = _tl.get("stagger_model", "—")
        _ktr = _tl.get("bw_trains")
        _ktr_s = str(_ktr) if _ktr is not None else "—"
        _sd = _tl.get("sim_demand")
        _sd_s = f"{_sd:.2f}" if isinstance(_sd, (int, float)) else "—"
        _hdays = int(_tl.get("horizon_days") or max(1, round(float(_tl.get("horizon_h", 24)) / 24)))
        st.caption(
            f"**Horizon:** {_hdays} day(s) · **Stagger:** {bw_timeline_stagger_label(_sm)} · "
            f"**BW trains required** (rated N, design temperature, average TSS): **{_ktr_s}** · "
            f"**Concurrent demand index:** **{_sd_s}**.  "
            "Green = operating; red = full backwash sequence. "
            "**Feasibility-train** mode spaces starts by **Δt_bw ÷ BW trains** (matches section 4). "
            "**Optimized trains** adjusts start times to reduce peak overlap — *scheduling aid only*, not plant DCS logic. "
            "**Uniform** is a smooth legacy comparison."
        )
        st.markdown(bw_timeline_schedule_summary_html(_tl), unsafe_allow_html=True)
        for _note in _tl.get("advisory_notes") or []:
            st.caption(_note)
        render_metric_explain_panel(
            inputs,
            computed,
            ["bw_trains", "peak_concurrent_bw"],
            title="How scheduling numbers are built",
        )
        _opt = _tl.get("optimizer") or {}
        if _sm == "optimized_trains" and _opt.get("stream_aware"):
            _psp = _opt.get("per_stream_peak") or []
            st.caption(
                f"Stream-aware optimisation ({_opt.get('n_streams', '—')} streams) — "
                f"per-stream peaks: {', '.join(str(p) for p in _psp)}."
            )
        if _sm == "feasibility_trains":
            st.caption(
                "Feasibility spacing keeps BW starts **Δt_bw ÷ BW trains** apart — "
                "switch sidebar to **Optimized trains** to try lowering peak overlap."
            )
        _hge = _tl.get("hours_operating_ge_design_n_h")
        _heq = _tl.get("hours_operating_eq_design_n_h")
        _hgt = _tl.get("hours_operating_gt_design_n_h")
        _hn1 = _tl.get("hours_operating_eq_n_minus_1_h")
        _hlt = _tl.get("hours_operating_below_n_minus_1_h")
        _ndes = _tl.get("n_design_online_total")
        _nphys = _tl.get("n_physical_timeline")
        _horz = float(_tl.get("horizon_h", 24.0))
        if isinstance(_hge, (int, float)) and _ndes is not None:
            _n1 = float(_hn1) if isinstance(_hn1, (int, float)) else 0.0
            _lt = float(_hlt) if isinstance(_hlt, (int, float)) else 0.0
            _eq = float(_heq) if isinstance(_heq, (int, float)) else float(_hge)
            _gt = float(_hgt) if isinstance(_hgt, (int, float)) else 0.0
            _nper = max(1, n_filters - hydraulic_assist_bw)
            _phys_txt = (
                f"{_nphys} physical" if isinstance(_nphys, int) else f"{streams}×{n_filters} physical"
            )
            _duty_rows = [
                ("At N (all rated online)", f"{_eq:.1f} h"),
                ("At N−1 (one in BW)", f"{_n1:.1f} h"),
                ("Below N−1", f"{_lt:.1f} h"),
            ]
            if hydraulic_assist_bw > 0:
                _duty_rows.append(("N+1 margin", f"{_gt:.1f} h"))
            _duty_body = "".join(
                f"<tr><td>{lbl}</td><td style='text-align:right'><b>{val}</b></td></tr>"
                for lbl, val in _duty_rows
            )
            st.markdown(
                f"<p style='font-size:0.78rem;margin:0.25rem 0 0.15rem 0'>"
                f"<b>Plant-wide duty</b> — {_phys_txt}, {_hdays} d / {_horz:.0f} h · "
                f"design N = {_nper}/stream × {streams} → {_ndes} plant-wide.</p>"
                f"<table style='width:100%;font-size:0.78rem;line-height:1.45;border-collapse:collapse;'>"
                f"{_duty_body}</table>",
                unsafe_allow_html=True,
            )
        from ui.bw_timeline_chart import render_bw_timeline_gantt

        render_bw_timeline_gantt(_tl)
        if _tl.get("filters"):
            _cap_n = _tl.get("hours_operating_eq_design_n_h")
            _cap_n1 = _tl.get("hours_operating_eq_n_minus_1_h")
            _duty_line = ""
            if isinstance(_cap_n, (int, float)) and isinstance(_cap_n1, (int, float)):
                _duty_line = (
                    f" **Duty (plant-wide):** ≈ **{float(_cap_n):.1f}** h at **N** · "
                    f"≈ **{float(_cap_n1):.1f}** h at **N−1** (not in BW count vs design N)."
                )
            st.caption(
                f"Filtration cycle (design TSS) ≈ **{_tl.get('t_cycle_h', '—')}** h · "
                f"BW duration **{_tl.get('bw_duration_h', '—')}** h · "
                f"repeat period **{_tl.get('period_h', '—')}** h.{_duty_line}  {_tl.get('note', '')}"
            )
    return _tl
