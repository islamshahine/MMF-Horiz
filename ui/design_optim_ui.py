"""Assessment-tab design optimisation — plant grid (hydraulic sweep + rank) + collector."""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from engine.optimisation import optimise_design
from ui.design_optim_apply import (
    apply_plant_patch_to_session,
    objective_display_name,
    objective_metric_key,
)
from ui.helpers import fmt, ulbl

_OBJECTIVE_OPTIONS = [
    ("hydraulic", "Hydraulic check only (all rows)"),
    ("capex", "Minimise total CAPEX"),
    ("opex", "Minimise annual OPEX"),
    ("steel", "Minimise empty steel weight"),
    ("carbon", "Minimise lifecycle CO₂"),
]
_OBJECTIVE_IDS = [o[0] for o in _OBJECTIVE_OPTIONS]
_OBJECTIVE_LABELS = {o[0]: o[1] for o in _OBJECTIVE_OPTIONS}


def _run_plant_study(
    inputs: dict,
    *,
    objective: str,
    nf_lo: int,
    nf_hi: int,
    top_k: int,
    cap_dp: bool,
) -> dict[str, Any]:
    patches = [{"n_filters": nf} for nf in range(int(nf_lo), int(nf_hi) + 1)]
    constraints = None
    if cap_dp:
        constraints = {"max_dp_dirty_bar": float(inputs.get("dp_trigger_bar", 1.0))}
    rank_obj = objective if objective != "hydraulic" else "capex"
    return optimise_design(
        inputs,
        patches,
        objective=rank_obj,
        top_k=top_k if objective != "hydraulic" else max(len(patches), 1),
        constraints=constraints,
    )


def _plant_study_row(
    row: dict,
    *,
    velocity_threshold: float,
    hydraulic_assist: int,
    rank: int | None = None,
) -> dict[str, Any]:
    patch = row.get("patch") or {}
    metrics = row.get("metrics") or {}
    nf = int(patch.get("n_filters", 0))
    design_n = max(1, nf - int(hydraulic_assist))
    details = row.get("details") or {}
    lv = details.get("lv_n_m_h")
    feasible = bool(row.get("feasible"))
    lv_hdr = f"LV — N scenario ({ulbl('velocity_m_h')})"
    thr_hdr = f"Threshold ({ulbl('velocity_m_h')})"
    violations = list(row.get("violations") or [])
    per_layer_lv_ok = "lv_exceeds_threshold" not in violations
    if lv is None or (isinstance(lv, float) and lv != lv):
        lv_disp = "—"
        bulk_lv_ok = False
    else:
        lv_disp = fmt(float(lv), "velocity_m_h", 2)
        bulk_lv_ok = float(lv) <= float(velocity_threshold)
    lim_layer = details.get("lv_limiting_layer") or details.get("lv_worst_layer") or "—"
    lim_lv = details.get("lv_limiting_m_h") or details.get("lv_worst_m_h")
    lim_cap = details.get("lv_limiting_cap_m_h") or details.get("lv_worst_cap_m_h")
    if lim_lv is not None and lim_cap is not None:
        if per_layer_lv_ok:
            layer_lv_disp = f"{float(lim_lv):.2f} (cap {float(lim_cap):.2f})"
        else:
            layer_lv_disp = f"{float(lim_lv):.2f} > cap {float(lim_cap):.2f}"
    else:
        layer_lv_disp = "—"
    rec: dict[str, Any] = {}
    if rank is not None:
        rec["Rank"] = rank
    rec.update({
        "Physical / stream": nf,
        "Design N / stream": design_n,
        lv_hdr: lv_disp,
        thr_hdr: fmt(float(velocity_threshold), "velocity_m_h", 2),
        "Bulk LV OK": "Yes" if bulk_lv_ok else "No",
        "Per-layer LV OK": "Yes" if per_layer_lv_ok else "No",
        "Limiting layer": lim_layer,
        f"Layer LV vs cap ({ulbl('velocity_m_h')})": layer_lv_disp,
        "Feasible (all checks)": "Yes" if feasible else "No",
        "Violations": ", ".join(violations) or "—",
        "CAPEX MUSD": round(float(metrics.get("total_capex_usd", 0)) / 1e6, 3),
        "OPEX MUSD/yr": round(float(metrics.get("total_opex_usd_yr", 0)) / 1e6, 3),
        "Steel t": round(float(metrics.get("steel_kg", 0)) / 1000, 2),
        "CO₂ kt": round(float(metrics.get("co2_lifecycle_kg", 0)) / 1000, 2),
    })
    return rec


def _plant_study_all_rows_dataframe(
    all_rows: list[dict],
    *,
    velocity_threshold: float,
    hydraulic_assist: int,
) -> pd.DataFrame:
    rows = [
        _plant_study_row(
            row,
            velocity_threshold=velocity_threshold,
            hydraulic_assist=hydraulic_assist,
        )
        for row in all_rows
    ]
    return pd.DataFrame(rows)


def _pareto_dataframe(
    pareto_rows: list[dict],
    *,
    velocity_threshold: float,
    hydraulic_assist: int,
) -> pd.DataFrame:
    out = []
    for row in pareto_rows:
        rec = _plant_study_row(
            row,
            velocity_threshold=velocity_threshold,
            hydraulic_assist=hydraulic_assist,
        )
        m = row.get("metrics") or {}
        rec["CAPEX USD"] = round(float(m.get("total_capex_usd", 0)), 0)
        rec["OPEX USD/yr"] = round(float(m.get("total_opex_usd_yr", 0)), 0)
        out.append(rec)
    return pd.DataFrame(out)


def _plant_study_ranked_dataframe(
    ranked_rows: list[dict],
    objective: str,
    *,
    velocity_threshold: float,
    hydraulic_assist: int,
) -> pd.DataFrame:
    mkey = objective_metric_key(objective)
    obj_col = objective_display_name(objective)
    out = []
    for rank, row in enumerate(ranked_rows, start=1):
        rec = _plant_study_row(
            row,
            velocity_threshold=velocity_threshold,
            hydraulic_assist=hydraulic_assist,
            rank=rank,
        )
        rec[obj_col] = round(float((row.get("metrics") or {}).get(mkey, 0)), 2)
        out.append(rec)
    return pd.DataFrame(out)


def _render_plant_study(
    inputs: dict,
    *,
    n_filters: int,
    velocity_threshold: float,
    hydraulic_assist: int,
    redundancy: int,
) -> None:
    st.caption(
        "Vary **how many filters are installed per stream**. Each row is one **full plant recalculation**. "
        "Use **Hydraulic check** to compare filtration rate at the **N outage** case, or pick a cost/weight "
        "objective to rank feasible options and **apply** a row to the sidebar."
    )
    with st.expander("How LV checks work in this table", expanded=False):
        st.markdown(
            "**Bulk LV @ N** is the plant-average filtration rate at the **N outage** case "
            "(design N = physical − standby), compared to the sidebar **velocity threshold**. "
            "**Per-layer LV** rescales that rate by each layer’s **chordal area** "
            "(smaller area → higher local LV). A row can pass the bulk check but fail "
            "**Per-layer LV** — that is when you see `lv_exceeds_threshold` even though bulk LV "
            "is below 12 m/h. **Feasible** also requires EBCT, freeboard, and optional ΔP caps."
        )

    objective = st.selectbox(
        "Study mode",
        _OBJECTIVE_IDS,
        format_func=lambda k: _OBJECTIVE_LABELS[k],
        key="plant_opt_objective",
    )
    rank_mode = objective != "hydraulic"

    c1, c2, c3 = st.columns(3)
    with c1:
        nf_lo = int(st.number_input(
            "Filters per stream — from",
            value=int(n_filters),
            min_value=max(int(redundancy) + 1, 1),
            key="plant_opt_nf_lo",
        ))
    with c2:
        nf_hi = int(st.number_input(
            "Filters per stream — to",
            value=min(int(n_filters) + 8, 80),
            min_value=1,
            key="plant_opt_nf_hi",
        ))
    with c3:
        top_k = int(st.number_input(
            "Show top ranked",
            value=5,
            min_value=1,
            max_value=20,
            key="plant_opt_topk",
            disabled=not rank_mode,
        ))

    cap_dp = st.checkbox(
        f"Also require dirty-bed ΔP ≤ backwash trigger ({fmt(inputs.get('dp_trigger_bar', 1), 'pressure_bar', 2)})",
        value=False,
        key="plant_opt_cap_dp",
    )
    span = max(0, int(nf_hi) - int(nf_lo) + 1)
    if span > 48:
        st.warning(f"This study runs **{span}** full plant models — expect a short wait.")

    if st.button("Run study", type="primary", key="plant_opt_run"):
        if nf_hi < nf_lo:
            st.error("**To** must be ≥ **From**.")
        else:
            with st.spinner(f"Evaluating {span} filter counts…"):
                st.session_state["_plant_opt_result"] = _run_plant_study(
                    inputs,
                    objective=objective,
                    nf_lo=nf_lo,
                    nf_hi=nf_hi,
                    top_k=top_k,
                    cap_dp=cap_dp,
                )
                st.session_state["_plant_opt_objective"] = objective
                st.session_state["_plant_opt_ha"] = int(hydraulic_assist)
                st.session_state["_plant_opt_vthr"] = float(velocity_threshold)

    result = st.session_state.get("_plant_opt_result")
    if not result:
        return

    obj = st.session_state.get("_plant_opt_objective", objective)
    ha = int(st.session_state.get("_plant_opt_ha", hydraulic_assist))
    vthr = float(st.session_state.get("_plant_opt_vthr", velocity_threshold))
    all_rows = result.get("all") or []

    st.markdown("#### Results (all filter counts)")
    if all_rows:
        st.dataframe(
            _plant_study_all_rows_dataframe(
                all_rows, velocity_threshold=vthr, hydraulic_assist=ha,
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("No results to display.")

    pset = result.get("pareto_capex_opex") or []
    if len(pset) >= 2:
        with st.expander(
            "Pareto — CAPEX vs annual OPEX (non-dominated feasible)",
            expanded=False,
        ):
            st.caption(
                "No other **feasible** row in this study has both lower total CAPEX and lower annual OPEX. "
                "Use for capital vs operating trade-offs (MVP 2-objective front)."
            )
            st.dataframe(
                _pareto_dataframe(pset, velocity_threshold=vthr, hydraulic_assist=ha),
                use_container_width=True,
                hide_index=True,
            )

    if obj == "hydraulic":
        st.caption(
            "Hydraulic-only mode does not change the sidebar. Switch study mode to a cost objective "
            "and re-run to rank feasible options and apply a filter count."
        )
        return

    st.markdown(f"#### Top ranked — {_OBJECTIVE_LABELS.get(obj, obj)}")
    st.markdown(
        f"**Feasible:** {result.get('feasible_count', 0)} / {result.get('evaluated', 0)}"
    )
    ranked = result.get("top") or []
    if not ranked:
        st.warning("No feasible candidates — relax constraints or widen the filter-count range.")
        return

    best = ranked[0]
    mkey = objective_metric_key(obj)
    st.success(
        f"Best: **{best['patch'].get('n_filters')} filters / stream** · "
        f"{objective_display_name(obj)} = {float(best['metrics'].get(mkey, 0)):,.0f}"
    )
    st.dataframe(
        _plant_study_ranked_dataframe(
            ranked, obj, velocity_threshold=vthr, hydraulic_assist=ha,
        ),
        use_container_width=True,
        hide_index=True,
    )

    pick_labels = [
        f"#{i} — {r['patch'].get('n_filters')} filters/stream ({objective_display_name(obj)}="
        f"{float(r['metrics'].get(mkey, 0)):,.0f})"
        for i, r in enumerate(ranked, start=1)
    ]
    pick_idx = st.selectbox(
        "Select row to apply",
        range(len(pick_labels)),
        format_func=lambda i: pick_labels[i],
        key="plant_opt_pick",
    )
    b1, b2 = st.columns(2)
    with b1:
        if st.button("Apply best to sidebar", type="primary", key="plant_opt_apply_best"):
            applied = apply_plant_patch_to_session(
                best["patch"], st.session_state.get("unit_system", "metric"),
            )
            st.session_state["_plant_opt_apply_msg"] = (
                f"Sidebar updated from best row ({', '.join(applied) or 'filters per stream'})."
            )
            st.rerun()
    with b2:
        if st.button("Apply selected row to sidebar", key="plant_opt_apply_sel"):
            row = ranked[int(pick_idx)]
            applied = apply_plant_patch_to_session(
                row["patch"], st.session_state.get("unit_system", "metric"),
            )
            st.session_state["_plant_opt_apply_msg"] = (
                f"Sidebar updated from rank #{int(pick_idx) + 1} "
                f"({', '.join(applied) or 'filters per stream'})."
            )
            st.rerun()


def _render_collector_optimisation() -> None:
    st.caption(
        "Searches **collector lateral layout** (flow balance through the underdrain — not whole-plant cost). "
        "Same tool as **Sidebar → Re-optimize after edits**."
    )
    from ui.collector_optim_ui import run_collector_optimization_from_session

    if st.button("Run collector optimisation", type="secondary", key="assess_collector_opt_run"):
        run_collector_optimization_from_session()
    msg = st.session_state.get("_collector_opt_message")
    if msg:
        st.info(msg)


def render_design_optimisation_panel(
    inputs: dict,
    *,
    n_filters: int,
    velocity_threshold: float,
    hydraulic_assist: int,
    redundancy: int,
) -> None:
    """Plant filter-count study + collector optimisation for Assessment tab."""
    apply_msg = st.session_state.pop("_plant_opt_apply_msg", None)
    if apply_msg:
        st.success(apply_msg)

    tab_plant, tab_col = st.tabs(["Filters per stream (full plant)", "Collector hydraulics"])
    with tab_plant:
        _render_plant_study(
            inputs,
            n_filters=n_filters,
            velocity_threshold=velocity_threshold,
            hydraulic_assist=hydraulic_assist,
            redundancy=redundancy,
        )
    with tab_col:
        _render_collector_optimisation()
