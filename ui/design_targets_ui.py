"""Assessment — design-to-target grid search + Apply to sidebar."""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from engine.design_targets import normalize_targets, search_design_targets, targets_active
from engine.units import display_value, si_value
from ui.design_optim_apply import apply_plant_patch_to_session
from ui.helpers import fmt, ulbl


def _target_row_display(row: dict, *, rank: int | None = None) -> dict[str, Any]:
    patch = row.get("patch") or {}
    m = row.get("target_metrics") or row.get("metrics") or {}
    rec: dict[str, Any] = {}
    if rank is not None:
        rec["Rank"] = rank
    rec.update({
        "n_filters": patch.get("n_filters", "—"),
        f"ID ({ulbl('length_m')})": fmt(patch.get("nominal_id"), "length_m", 2)
        if patch.get("nominal_id") is not None
        else "—",
        f"BW vel ({ulbl('velocity_m_h')})": fmt(patch.get("bw_velocity"), "velocity_m_h", 1)
        if patch.get("bw_velocity") is not None
        else "—",
        f"ΔP dirty ({ulbl('pressure_bar')})": fmt(m.get("dp_dirty_bar"), "pressure_bar", 3),
        f"LCOW ({ulbl('cost_usd_per_m3')})": fmt(m.get("lcow_usd_m3"), "cost_usd_per_m3", 4),
        f"Q BW ({ulbl('flow_m3h')})": fmt(m.get("q_bw_m3h"), "flow_m3h", 1),
        "CAPEX MUSD": round(float(m.get("total_capex_usd", 0)) / 1e6, 3),
        "Feasible": "Yes" if row.get("feasible") else "No",
        "Meets targets": "Yes" if row.get("meets_targets") else "No",
        "Violations": ", ".join(
            list(row.get("violations") or []) + list(row.get("target_violations") or [])
        ) or "—",
    })
    return rec


def render_design_targets_panel(inputs: dict, computed: dict) -> None:
    unit_sys = str(inputs.get("unit_system") or st.session_state.get("unit_system") or "metric")
    dt = computed.get("design_targets") or {}
    baseline = dt.get("baseline") or {}
    bm = baseline.get("metrics") or {}

    apply_msg = st.session_state.pop("_design_targets_apply_msg", None)
    if apply_msg:
        st.success(apply_msg)

    st.caption(
        "Find filter count / vessel ID / BW velocity combinations that meet your caps. "
        "Each candidate runs full **compute_all** — explicit **Apply** only (no auto-write)."
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        use_dp = st.checkbox("Cap dirty ΔP", value=bool(dt.get("targets", {}).get("max_dp_dirty_bar")),
                             key="dt_use_dp")
        dp_val = st.number_input(
            f"Max dirty ΔP ({ulbl('pressure_bar')})",
            min_value=0.1,
            value=float(display_value(
                float(dt.get("targets", {}).get("max_dp_dirty_bar")
                      or inputs.get("dp_trigger_bar", 0.6)),
                "pressure_bar",
                unit_sys,
            )),
            step=0.05,
            disabled=not use_dp,
            key="dt_max_dp",
        )
    with c2:
        use_lcow = st.checkbox("Cap LCOW", value=False, key="dt_use_lcow")
        _lcow_def = float((computed.get("econ_bench") or {}).get("lcow", 0.05) or 0.05) * 1.1
        lcow_val = st.number_input(
            f"Max LCOW ({ulbl('cost_usd_per_m3')})",
            min_value=0.001,
            value=float(display_value(_lcow_def, "cost_usd_per_m3", unit_sys)),
            format="%.4f",
            disabled=not use_lcow,
            key="dt_max_lcow",
        )
    with c3:
        use_bw = st.checkbox("Cap BW flow", value=False, key="dt_use_bw")
        _q_bw = float((computed.get("bw_hyd") or {}).get("q_bw_m3h", 400) or 400)
        bw_val = st.number_input(
            f"Max Q_BW ({ulbl('flow_m3h')})",
            min_value=1.0,
            value=float(display_value(_q_bw * 1.05, "flow_m3h", unit_sys)),
            step=10.0,
            disabled=not use_bw,
            key="dt_max_bw",
        )
    with c4:
        use_capex = st.checkbox("Cap CAPEX", value=False, key="dt_use_capex")
        _cap = float((computed.get("econ_capex") or {}).get("total_capex_usd", 5e6) or 5e6)
        capex_m = st.number_input(
            "Max CAPEX (M USD)",
            min_value=0.1,
            value=round(_cap / 1e6, 2),
            step=0.5,
            disabled=not use_capex,
            key="dt_max_capex_m",
        )

    targets_si = normalize_targets({
        "max_dp_dirty_bar": si_value(dp_val, "pressure_bar", unit_sys) if use_dp else None,
        "max_lcow_usd_m3": si_value(lcow_val, "cost_usd_per_m3", unit_sys) if use_lcow else None,
        "max_q_bw_m3h": si_value(bw_val, "flow_m3h", unit_sys) if use_bw else None,
        "max_capex_usd": float(capex_m) * 1e6 if use_capex else None,
    })

    if not targets_active(targets_si):
        st.warning("Enable at least one target cap to run a search.")
        return

    nf = int(inputs.get("n_filters", 6))
    g1, g2, g3, g4 = st.columns(4)
    with g1:
        nf_lo = int(st.number_input("n_filters min", min_value=4, value=max(4, nf - 3), key="dt_nf_lo"))
    with g2:
        nf_hi = int(st.number_input("n_filters max", min_value=nf_lo, value=nf + 3, key="dt_nf_hi"))
    with g3:
        sweep_id = st.checkbox("Sweep vessel ID ±5%", value=False, key="dt_sweep_id")
    with g4:
        sweep_bw = st.checkbox("Sweep BW velocity ±15%", value=False, key="dt_sweep_bw")

    top_k = int(st.slider("Top recommendations", 1, 10, 5, key="dt_top_k"))

    if baseline and bm:
        st.markdown("**Current design vs targets**")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric(f"ΔP dirty ({ulbl('pressure_bar')})", fmt(bm.get("dp_dirty_bar"), "pressure_bar", 3))
        b2.metric(f"LCOW ({ulbl('cost_usd_per_m3')})", fmt(bm.get("lcow_usd_m3"), "cost_usd_per_m3", 4))
        b3.metric(f"Q BW ({ulbl('flow_m3h')})", fmt(bm.get("q_bw_m3h"), "flow_m3h", 1))
        ok = baseline.get("meets_targets") and baseline.get("feasible")
        b4.metric("Meets all targets", "Yes" if ok else "No")
        if baseline.get("target_violations"):
            st.caption("Target gaps: " + ", ".join(baseline["target_violations"]))

    if st.button("Run design-to-target search", type="primary", key="dt_run_search"):
        grid_spec: dict[str, Any] = {
            "n_filters": list(range(nf_lo, nf_hi + 1)),
        }
        nid = float(inputs.get("nominal_id", 3.0))
        if sweep_id:
            grid_spec["nominal_id"] = [nid * 0.95, nid, nid * 1.05]
        bwv = float(inputs.get("bw_velocity", 30.0))
        if sweep_bw:
            grid_spec["bw_velocity"] = [bwv * 0.85, bwv, bwv * 1.15]

        with st.spinner("Evaluating candidates (compute_all per row)…"):
            result = search_design_targets(inputs, targets_si, grid_spec, top_k=top_k)
        st.session_state["design_targets_search"] = result

    search = st.session_state.get("design_targets_search")
    if not search or not search.get("enabled"):
        return

    st.caption(
        f"Evaluated **{search.get('evaluated', 0)}** · feasible **{search.get('feasible_count', 0)}** · "
        f"meets targets **{search.get('meets_targets_count', 0)}**"
    )

    ranked = search.get("ranked") or []
    if not ranked:
        st.info("No candidates met all targets and engineering checks. Widen the grid or relax caps.")
        with st.expander("All evaluated rows", expanded=False):
            all_rows = [_target_row_display(r) for r in (search.get("all") or [])]
            if all_rows:
                st.dataframe(pd.DataFrame(all_rows), use_container_width=True, hide_index=True)
        return

    df = pd.DataFrame([
        _target_row_display(r, rank=i + 1) for i, r in enumerate(ranked)
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("**Apply recommendation to sidebar**")
    for i, row in enumerate(ranked[:5]):
        patch = row.get("patch") or {}
        label = (
            f"#{i + 1}: n={patch.get('n_filters')} · "
            f"ID {fmt(patch.get('nominal_id'), 'length_m', 2)} · "
            f"BW {fmt(patch.get('bw_velocity'), 'velocity_m_h', 1)}"
        )
        if st.button(f"Apply {label}", key=f"dt_apply_{i}"):
            applied = apply_plant_patch_to_session(patch, unit_sys)
            st.session_state["_design_targets_apply_msg"] = (
                f"Applied patch keys: {', '.join(applied)}. Re-run **Apply** on sidebar to recalculate."
            )
            st.rerun()
