"""Guided fouling assistant workflow (sidebar) — advisory only, no compute_all hook."""
from __future__ import annotations

import streamlit as st

from engine.fouling import (
    SDI_BLOCKED_CAP_DEFAULT,
    SDI_BLOCKED_CAP_OPTIONS,
    effective_sdi15_for_correlation,
    estimate_bw_frequency,
    estimate_fouling_severity,
    estimate_run_time,
    estimate_solids_loading,
    fouling_advisory_recommendations,
    fouling_confidence_level,
    water_stability_class,
)
from engine.units import display_value, si_value, unit_label


def render_fouling_guided_workflow(out: dict, unit_system: str, *, on_apply_solid_loading) -> None:
    """Four-step fouling interpretation; does not mutate ``out`` except via explicit Apply."""
    st.warning(
        "**Advisory only** — empirical correlations (`engine/fouling.py`). "
        "Not a design basis until validated with pilot or operating data."
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
        "**SDI₁₅** = ASTM 15-minute index on **MMF feed (inlet)** — not RO-feed SDI₃ after filtration. "
        "Typical inlet: wells **~2–3.5**; open intake often **> 5** or test **blocked (∞)**. "
        "Target **SDI ~ 3** before membranes is a **downstream** goal (MMF + cartridge), not this field."
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
        help=(
            "When the 0.45 µm SDI test plugs before 15 min, enter a bracketing cap here. "
            "For **M_max** design, rely on **TSS** (Process tab) and pilot data — not this cap alone."
        ),
    )
    _c1f, _c2f = st.columns(2)
    with _c1f:
        if _sdi_blocked:
            _cap_opts = list(SDI_BLOCKED_CAP_OPTIONS)
            _cap_default = SDI_BLOCKED_CAP_DEFAULT
            _cap_idx = _cap_opts.index(_cap_default) if _cap_default in _cap_opts else 1
            _f_sdi = st.selectbox(
                "SDI₁₅ cap — MMF inlet, advisory (−)",
                _cap_opts,
                index=_cap_idx,
                format_func=lambda v: f"{v:.0f}  (open intake / blocked test bracket)",
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
                help="Measured ASTM D4189 SDI₁₅ on water entering the multimedia filter.",
            )
    with _c2f:
        _f_mfi = st.number_input(
            "MFI index — MMF feed inlet (−)",
            value=2.0,
            min_value=0.0,
            max_value=15.0,
            step=0.1,
            key="fouling_mfi",
            help="0–10+ severity from your lab protocol (not raw s/L²).",
        )

    _sdi_eff, _sdi_extra = effective_sdi15_for_correlation(
        float(_f_sdi),
        test_blocked=_sdi_blocked,
        blocked_cap=float(st.session_state.get("fouling_sdi_cap", SDI_BLOCKED_CAP_DEFAULT)),
    )

    _lv_si = max(0.1, float(si_value(float(_f_lv_disp), "velocity_m_h", unit_system)))
    _tss_use = max(0.05, float(out.get("tss_avg", 10.0)))
    _esl = estimate_solids_loading(tss_mg_l=_tss_use, lv_m_h=_lv_si, sdi15=_sdi_eff, mfi_index=float(_f_mfi))
    _sev = estimate_fouling_severity(
        sdi15=_sdi_eff, mfi_index=float(_f_mfi), tss_mg_l=_tss_use, lv_m_h=_lv_si,
    )
    _rt = estimate_run_time(
        sdi15=_sdi_eff, mfi_index=float(_f_mfi), tss_mg_l=_tss_use, lv_m_h=_lv_si,
    )
    _bw = estimate_bw_frequency(run_time_h=float(_rt["run_time_h"]))

    _stab = water_stability_class(
        severity=str(_sev["severity"]),
        seasonal_variability=str(st.session_state.get("fouling_seasonal_var", "moderate")),
        algae_risk=str(st.session_state.get("fouling_algae_risk", "low")),
    )
    _tone = _stab["tone"]
    if _tone == "ok":
        st.success(f"Water stability class: **{_stab['label']}**")
    elif _tone == "caution":
        st.info(f"Water stability class: **{_stab['label']}**")
    else:
        st.warning(f"Water stability class: **{_stab['label']}**")

    _sugg_si = float(_esl["solid_loading_kg_m2"])
    _sugg_disp = display_value(_sugg_si, "loading_kg_m2", unit_system)
    st.session_state["_fouling_last_sugg_disp"] = round(float(_sugg_disp), 5)

    st.markdown("##### Step 3 — Operational interpretation")
    st.markdown(
        f"- **Suggested M_max:** {_sugg_disp:.3f} {unit_label('loading_kg_m2', unit_system)}  \n"
        f"- **Fouling score:** {_sev['score']:.0f}/100 ({_sev['severity']})  \n"
        f"- **Indicative run time:** ~{_rt['run_time_h']:.1f} h  \n"
        f"- **Implied BW frequency:** ~{_bw['bw_cycles_per_day']:.1f} cycles/day "
        f"(assumes {_bw['assumed_bw_block_h']:.1f} h blocked per event)"
    )
    _cu_note = ""
    if st.session_state.get("_fouling_link_uncertainty"):
        _cu_note = " Review **Filtration → cycle uncertainty** after Apply for optimistic/conservative band."
    st.caption(
        "High SDI variability or algae risk can shorten real run time versus this single-point estimate."
        + _cu_note
    )

    st.markdown("##### Step 4 — Recommendations & confidence")
    _has_pretreat = st.session_state.get("fouling_upstream", "none") not in ("none", "")
    if _sdi_blocked:
        st.info(
            f"Using SDI cap **{_sdi_eff:g}** in correlations. "
            "**TSS low / avg / high** on the Process tab remains the primary driver for M_max in `compute_all`."
        )

    _conf = fouling_confidence_level(
        sdi15=_sdi_eff,
        mfi_index=float(_f_mfi),
        tss_mg_l=_tss_use,
        has_upstream_uf_daf=_has_pretreat,
        seasonal_variability=str(st.session_state.get("fouling_seasonal_var", "moderate")),
    )
    st.caption(f"**Confidence:** {_conf['level']} — {_conf['note']}")
    for _line in fouling_advisory_recommendations(
        severity=str(_sev["severity"]),
        score=float(_sev["score"]),
        stability_label=str(_stab["label"]),
        run_time_h=float(_rt["run_time_h"]),
    ):
        st.markdown(f"- {_line}")

    _seen_fw = set()
    for _w in _sdi_extra + _esl.get("warnings", ()) + _sev.get("warnings", ()) + _rt.get("warnings", ()):
        if _w and _w not in _seen_fw:
            _seen_fw.add(_w)
            st.warning(_w)

    st.button("Apply suggested solid loading (M_max)", key="fouling_apply_mmax", on_click=on_apply_solid_loading)
