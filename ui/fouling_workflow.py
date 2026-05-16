"""Guided fouling assistant workflow (sidebar) — advisory only, no compute_all hook."""
from __future__ import annotations

from typing import Any

import streamlit as st

from engine.fouling import (
    SDI_BLOCKED_CAP_DEFAULT,
    SDI_BLOCKED_CAP_OPTIONS,
    build_fouling_assessment,
    fouling_advisory_recommendations,
)
from engine.units import display_value, si_value, unit_label


def _fouling_compact_note(text: str, *, tone: str = "warn") -> None:
    """Sidebar-sized note (smaller than default ``st.warning``)."""
    _icon = "⚠" if tone == "warn" else "ℹ"
    st.markdown(
        f'<p style="font-size:0.78rem;line-height:1.45;margin:0.35rem 0;opacity:0.92">'
        f"{_icon} {text}</p>",
        unsafe_allow_html=True,
    )


def _render_cycle_crosscheck_table(cross: dict[str, Any]) -> None:
    """Compact run-time band for narrow sidebar (avoids truncated ``st.metric`` labels)."""
    _rows = (
        ("Indicative (fouling)", cross["indicative_run_time_h"]),
        ("Model expected", cross["cycle_expected_h"]),
        ("Optimistic", cross["cycle_optimistic_h"]),
        ("Conservative", cross["cycle_conservative_h"]),
    )
    _body = "".join(
        f"<tr><td>{_lbl}</td><td style='text-align:right'><b>{float(_h):.1f} h</b></td></tr>"
        for _lbl, _h in _rows
    )
    st.markdown(
        f"""<table style="width:100%;font-size:0.78rem;line-height:1.5;border-collapse:collapse;">
        <thead><tr style="opacity:0.85">
        <th style="text-align:left;font-weight:600">Scenario</th>
        <th style="text-align:right;font-weight:600">Cycle</th>
        </tr></thead><tbody>{_body}</tbody></table>""",
        unsafe_allow_html=True,
    )


def render_fouling_guided_workflow(
    out: dict,
    unit_system: str,
    *,
    computed: dict[str, Any] | None = None,
    on_apply_solid_loading,
) -> None:
    """Five-step fouling interpretation; does not mutate ``out`` except via explicit Apply."""
    _computed = computed or {}
    _fouling_compact_note(
        "<b>Advisory only</b> — SDI₁₅, MFI, TSS, and filtration-LV correlations. "
        "Not a design basis until validated with pilot or plant data.",
        tone="info",
    )

    st.markdown("##### Step 1 — Feed water characterisation")
    _c1, _c2 = st.columns(2)
    with _c1:
        st.selectbox(
            "Seasonal TSS / SDI variability",
            ["low", "moderate", "high", "very_high"],
            index=1,
            key="fouling_seasonal_var",
            help="How much feed quality swings between normal and upset conditions.",
        )
        st.selectbox(
            "Algae / biofouling risk",
            ["low", "moderate", "high"],
            index=0,
            key="fouling_algae_risk",
        )
    with _c2:
        st.selectbox(
            "Upstream pretreatment",
            ["none", "daf", "uf", "daf_and_uf"],
            index=0,
            key="fouling_upstream",
        )
        st.selectbox(
            "Chlorination / dechlorination",
            ["continuous", "intermittent", "none", "unknown"],
            index=0,
            key="fouling_chlorination",
        )

    st.markdown("##### Step 2 — Fouling indices (SDI / MFI / LV)")
    st.caption(
        "**SDI₁₅** = ASTM 15-minute index on **MMF feed (inlet)**. "
        "**TSS** for M_max in the hydraulic model comes from **Process** (low / avg / high)."
    )
    _vth_disp = float(out.get("velocity_threshold") or 12.0)
    _vth_si = si_value(_vth_disp, "velocity_m_h", unit_system)
    _def_lv_si = max(4.0, min(float(_vth_si) * 0.88, 14.0))
    _f_lv_disp = st.number_input(
        f"Filtration LV for correlation ({unit_label('velocity_m_h', unit_system)})",
        value=float(display_value(_def_lv_si, "velocity_m_h", unit_system)),
        step=float(display_value(0.5, "velocity_m_h", unit_system)),
        min_value=0.0,
        key="fouling_lv_mh",
    )
    _sdi_blocked = st.checkbox(
        "SDI₁₅ test blocked (∞) — use cap value for advisory only",
        value=False,
        key="fouling_sdi_blocked",
    )
    _c1f, _c2f = st.columns(2)
    with _c1f:
        if _sdi_blocked:
            _cap_opts = list(SDI_BLOCKED_CAP_OPTIONS)
            _cap_default = SDI_BLOCKED_CAP_DEFAULT
            _cap_idx = _cap_opts.index(_cap_default) if _cap_default in _cap_opts else 1
            _f_sdi = st.selectbox(
                "SDI₁₅ cap — MMF inlet (−)",
                _cap_opts,
                index=_cap_idx,
                format_func=lambda v: f"{v:.0f}  (blocked test bracket)",
                key="fouling_sdi_cap",
            )
        else:
            _f_sdi = st.number_input(
                "SDI₁₅ — MMF feed inlet (−)",
                value=3.0,
                min_value=0.0,
                max_value=15.0,
                step=0.1,
                key="fouling_sdi",
            )
    with _c2f:
        _f_mfi = st.number_input(
            "MFI index — MMF feed inlet (−)",
            value=2.0,
            min_value=0.0,
            max_value=15.0,
            step=0.1,
            key="fouling_mfi",
        )

    _lv_si = max(0.1, float(si_value(float(_f_lv_disp), "velocity_m_h", unit_system)))
    _tss_use = max(0.05, float(out.get("tss_avg", 10.0)))
    _has_pretreat = st.session_state.get("fouling_upstream", "none") not in ("none", "")
    _cu_n = (_computed.get("cycle_uncertainty") or {}).get("N") if _computed else None

    _assess = build_fouling_assessment(
        tss_mg_l=_tss_use,
        lv_m_h=_lv_si,
        sdi15=float(_f_sdi),
        mfi_index=float(_f_mfi),
        test_blocked=_sdi_blocked,
        blocked_cap=float(st.session_state.get("fouling_sdi_cap", SDI_BLOCKED_CAP_DEFAULT)),
        seasonal_variability=str(st.session_state.get("fouling_seasonal_var", "moderate")),
        algae_risk=str(st.session_state.get("fouling_algae_risk", "low")),
        has_upstream_uf_daf=_has_pretreat,
        cycle_uncertainty_n=_cu_n,
    )

    _sev = _assess["severity"]
    _rt = _assess["run_time"]
    _bw = _assess["bw_frequency"]
    _stab = _assess["stability"]
    _sugg_si = float(_assess["solid_loading_kg_m2"])
    _sugg_disp = display_value(_sugg_si, "loading_kg_m2", unit_system)
    st.session_state["_fouling_last_sugg_disp"] = round(float(_sugg_disp), 5)

    _tone = _stab["tone"]
    if _tone == "ok":
        st.success(f"Water stability class: **{_stab['label']}**")
    elif _tone == "caution":
        st.info(f"Water stability class: **{_stab['label']}**")
    else:
        st.warning(f"Water stability class: **{_stab['label']}**")

    st.markdown("##### Step 3 — Operational consequences")
    _cur_sl = float(out.get("solid_loading") or 0.0)
    _cur_disp = display_value(_cur_sl, "loading_kg_m2", unit_system) if _cur_sl > 0 else None
    _cur_line = (
        f"{_cur_disp:.3f} {unit_label('loading_kg_m2', unit_system)}"
        if _cur_disp is not None
        else "— (set on Media tab)"
    )
    st.markdown(
        f"- **Current M_max (sidebar):** {_cur_line}  \n"
        f"- **Fouling score:** {_sev['score']:.0f}/100 ({_sev['severity']})  \n"
        f"- **Indicative run time (empirical):** ~{_rt['run_time_h']:.1f} h  \n"
        f"- **Implied BW frequency:** ~{_bw['bw_cycles_per_day']:.1f} cycles/day "
        f"(~{_bw['assumed_bw_block_h']:.1f} h per event)"
    )

    st.markdown("##### Step 4 — Cross-check with hydraulic cycle model")
    st.checkbox(
        "Show comparison to Filtration cycle uncertainty (N scenario)",
        value=bool(st.session_state.get("fouling_link_uncertainty", True)),
        key="fouling_link_uncertainty",
        help="Uses the last **compute_all** result (optimistic / expected / conservative cycle band).",
    )
    _cross = _assess["cycle_crosscheck"]
    if st.session_state.get("fouling_link_uncertainty", True):
        if _cross.get("available"):
            _align = str(_cross.get("alignment", ""))
            if _align == "within_band":
                st.success(_cross.get("note", ""))
            else:
                st.info(_cross.get("note", ""))
            _render_cycle_crosscheck_table(_cross)
        else:
            st.caption(_cross.get("note", ""))

    st.markdown("##### Step 5 — Recommendations, confidence & apply")
    if _sdi_blocked:
        _fouling_compact_note(
            f"Using SDI cap <b>{_assess['sdi_effective']:g}</b>. "
            "Process TSS (low / avg / high) remains the primary driver for hydraulic M_max.",
            tone="info",
        )
    _conf = _assess["confidence"]
    st.caption(f"**Confidence:** {_conf['level']} — {_conf['note']}")
    for _line in fouling_advisory_recommendations(
        severity=str(_sev["severity"]),
        score=float(_sev["score"]),
        stability_label=str(_stab["label"]),
        run_time_h=float(_rt["run_time_h"]),
    ):
        st.markdown(f"- {_line}")
    for _w in _assess.get("warnings") or []:
        _fouling_compact_note(_w)

    _ul = unit_label("loading_kg_m2", unit_system)
    st.markdown(
        f'<p style="font-size:0.82rem;line-height:1.5;margin:0.6rem 0 0.25rem 0">'
        f"<b>Suggested M<sub>max</sub> (this assessment):</b> "
        f'<span style="font-size:0.95rem">{_sugg_disp:.3f}</span> {_ul}'
        f"</p>",
        unsafe_allow_html=True,
    )
    st.caption("Use **Apply** below to copy this value to Media → max solids loading.")

    st.button("Apply suggested solid loading (M_max)", key="fouling_apply_mmax", on_click=on_apply_solid_loading)
