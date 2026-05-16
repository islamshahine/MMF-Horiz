"""
Metric explainability registry — equation contributors and ``computed`` paths.

Advisory documentation for UI tooltips and report export (not a second solver).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class MetricContributor:
    label: str
    path: str
    role: str


@dataclass(frozen=True)
class MetricExplanation:
    metric_id: str
    title: str
    equation: str
    contributors: Tuple[MetricContributor, ...]
    doc_section: str = "AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md"


def _dig(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _resolve_path(path: str, inputs: dict, computed: dict) -> Any:
    p = str(path or "").strip()
    if p.startswith("inputs."):
        return _dig(inputs, p[7:])
    if p.startswith("computed."):
        return _dig(computed, p[9:])
    if p in inputs:
        return inputs[p]
    return _dig(computed, p)


def _fmt_val(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        if abs(v) >= 100 or (abs(v) > 0 and abs(v) < 0.01):
            return f"{v:.4g}"
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, (list, dict)):
        return f"<{type(v).__name__}>"
    return str(v)


METRIC_REGISTRY: Dict[str, MetricExplanation] = {
    "q_per_filter": MetricExplanation(
        "q_per_filter",
        "Flow per filter (hydraulic N)",
        "Q_filter = Q_plant / (streams × N_hydraulic_paths)",
        (
            MetricContributor("Plant flow", "inputs.total_flow", "m³/h basis"),
            MetricContributor("Streams", "inputs.streams", "parallel trains"),
            MetricContributor("Filters / stream", "inputs.n_filters", "physical count"),
            MetricContributor("Redundancy R", "inputs.redundancy", "outage derate"),
        ),
        "§3 Process basis",
    ),
    "solid_loading_effective": MetricExplanation(
        "solid_loading_effective",
        "Effective M_max (solids inventory)",
        "M_eff = M_max × solid_loading_scale",
        (
            MetricContributor("M_max (sidebar)", "inputs.solid_loading", "kg/m² design cap"),
            MetricContributor("Scale factor", "inputs.solid_loading_scale", "sensitivity knob"),
            MetricContributor("Effective value", "computed.solid_loading_effective_kg_m2", "used in cycles"),
        ),
        "§4 Filtration / cake",
    ),
    "maldistribution_factor": MetricExplanation(
        "maldistribution_factor",
        "Filtration maldistribution factor",
        "LV_eff = LV_nom × mal_f  ·  Ergun ΔP uses mal_f on interstitial velocity",
        (
            MetricContributor("Applied factor", "computed.maldistribution_factor", "in Ergun + cycles"),
            MetricContributor("From collector model", "computed.maldistribution_from_collector_model", "bool"),
            MetricContributor("Collector calc", "computed.collector_hyd.maldistribution_factor_calc", "1D model"),
        ),
        "§11.4 Collector / Ergun",
    ),
    "dp_dirty": MetricExplanation(
        "dp_dirty",
        "Pressure drop — dirty (BW trigger)",
        "ΔP = Σ Ergun(layers) + Ruth cake to dp_trigger",
        (
            MetricContributor("Trigger", "inputs.dp_trigger_bar", "BW initiation setpoint"),
            MetricContributor("α specific", "inputs.alpha_specific", "cake resistance"),
            MetricContributor("M_eff", "computed.solid_loading_effective_kg_m2", "inventory cap"),
            MetricContributor("mal_f", "computed.maldistribution_factor", "velocity bias"),
            MetricContributor("Output", "computed.bw_dp.dp_dirty_bar", "bar"),
        ),
        "§4 ΔP — Ergun + Ruth",
    ),
    "cycle_expected_h": MetricExplanation(
        "cycle_expected_h",
        "Filtration cycle — expected (N, design TSS)",
        "t_cycle = min(t_Ruth→ΔP_set, t_Mmax) with TSS × T correction",
        (
            MetricContributor("TSS design", "inputs.tss_avg", "mg/L"),
            MetricContributor("Temperature", "inputs.feed_temp", "°C"),
            MetricContributor("LV", "computed.filt_cycles.N.lv_m_h", "m/h"),
            MetricContributor("Expected h", "computed.cycle_uncertainty.N.cycle_expected_h", "h"),
        ),
        "§4 Cycle matrix",
    ),
    "cycle_uncertainty_spread": MetricExplanation(
        "cycle_uncertainty_spread",
        "Cycle uncertainty spread",
        "spread% = 100 × (t_cons − t_opt) / t_exp",
        (
            MetricContributor("Optimistic", "computed.cycle_uncertainty.N.cycle_optimistic_h", "h"),
            MetricContributor("Expected", "computed.cycle_uncertainty.N.cycle_expected_h", "h"),
            MetricContributor("Conservative", "computed.cycle_uncertainty.N.cycle_conservative_h", "h"),
            MetricContributor("Spread", "computed.cycle_uncertainty.N.spread_pct", "%"),
        ),
        "§4 Cycle uncertainty",
    ),
    "bw_trains": MetricExplanation(
        "bw_trains",
        "BW systems required (plant-wide)",
        "bw_trains = ceil(N_active × Δt_bw / T_cycle)",
        (
            MetricContributor("BW duration", "computed.bw_timeline.bw_duration_h", "h"),
            MetricContributor("Cycle (design TSS)", "computed.bw_timeline.t_cycle_h", "h"),
            MetricContributor("Rated trains", "computed.bw_timeline.bw_trains", "integer"),
            MetricContributor("Demand index", "computed.bw_timeline.sim_demand", "concurrent load"),
        ),
        "§5 BW feasibility",
    ),
    "peak_concurrent_bw": MetricExplanation(
        "peak_concurrent_bw",
        "Peak concurrent filters in BW",
        "Peak over horizon of count(filters in BW phase)",
        (
            MetricContributor("Stagger model", "computed.bw_timeline.stagger_model", "mode"),
            MetricContributor("Horizon", "computed.bw_timeline.horizon_h", "h"),
            MetricContributor("Peak count", "computed.bw_timeline.peak_concurrent_bw", "filters"),
            MetricContributor("Train cap met", "computed.bw_timeline.meets_bw_trains_cap", "bool"),
        ),
        "§5 BW scheduler",
    ),
    "operating_envelope_n": MetricExplanation(
        "operating_envelope_n",
        "Operating envelope — N scenario point",
        "Plant LV = Q/ā ; EBCT_min = min_layer(V_layer/Q)×60 ; classified vs layer caps/floors",
        (
            MetricContributor("LV (N)", "computed.operating_envelope.scenario_points[0].lv_m_h", "m/h"),
            MetricContributor("EBCT min (N)", "computed.operating_envelope.scenario_points[0].ebct_min_min", "min"),
            MetricContributor("Region", "computed.operating_envelope.scenario_points[0].region", "stable|marginal|elevated|critical"),
            MetricContributor("LV cap ref", "computed.operating_envelope.lv_cap_reference_m_h", "m/h"),
            MetricContributor("EBCT floor ref", "computed.operating_envelope.ebct_floor_reference_min", "min"),
        ),
        "§3.23 Operating envelope",
    ),
    "design_targets_lcow": MetricExplanation(
        "design_targets_lcow",
        "LCOW vs design target",
        "LCOW = (CAPEX×CRF + OPEX) / annual flow — compared to user cap in Assessment",
        (
            MetricContributor("LCOW", "computed.design_targets.baseline.metrics.lcow_usd_m3", "USD/m³"),
            MetricContributor("Meets targets", "computed.design_targets.baseline.meets_targets", "bool"),
            MetricContributor("Cap", "computed.design_targets.targets.max_lcow_usd_m3", "USD/m³"),
            MetricContributor("Econ bench", "computed.econ_bench.lcow", "USD/m³"),
        ),
        "§3.24 Design to target",
    ),
    "collector_flow_imbalance": MetricExplanation(
        "collector_flow_imbalance",
        "Collector flow imbalance",
        "imbalance% = 100 × (q_max − q_min) / q_mean across lateral stations",
        (
            MetricContributor("Imbalance %", "computed.collector_hyd.flow_imbalance_pct", "%"),
            MetricContributor("Method", "computed.collector_hyd.method", "1D solver"),
            MetricContributor("Distribution factor", "computed.collector_hyd.distribution_factor", "−"),
        ),
        "§11.4 Collector 1B",
    ),
    "bed_expansion_pct": MetricExplanation(
        "bed_expansion_pct",
        "Bed expansion (design BW)",
        "ε = (H_exp − H_packed) / H_packed from Richardson–Zaki / drift flux",
        (
            MetricContributor("Expansion %", "computed.bw_exp.expansion_pct", "%"),
            MetricContributor("BW velocity", "inputs.bw_velocity", "m/h"),
            MetricContributor("Media d50", "inputs.layers", "layer properties"),
        ),
        "§5 Bed expansion",
    ),
    "strainer_material": MetricExplanation(
        "strainer_material",
        "Strainer nozzle alloy",
        "Selection from salinity-based guidance (weight catalogue; corrosion = owner)",
        (
            MetricContributor("Feed salinity", "inputs.feed_sal", "ppt"),
            MetricContributor("Material", "inputs.strainer_mat", "alloy / polymer"),
            MetricContributor("Advisory tone", "computed.strainer_material_advisory.tone", "ok / advisory / warning"),
        ),
        "§6 Internals / corrosion",
    ),
    "nozzle_plate_open_area": MetricExplanation(
        "nozzle_plate_open_area",
        "Nozzle plate open area fraction",
        "φ = n_holes × π d²/4 / A_plate (mechanical + layout revision)",
        (
            MetricContributor("Open area %", "computed.collector_nozzle_plate.open_area_pct", "%"),
            MetricContributor("Hole count", "computed.collector_nozzle_plate.n_holes_total", "−"),
            MetricContributor("Layout revision", "computed.collector_nozzle_plate.layout_revision", "−"),
        ),
        "§11 Nozzle plate",
    ),
}


def get_metric_explanation(
    metric_id: str,
    inputs: dict,
    computed: dict,
) -> Optional[Dict[str, Any]]:
    """Resolve registry entry with live values from inputs / computed."""
    entry = METRIC_REGISTRY.get(str(metric_id or "").strip())
    if not entry:
        return None
    contrib_out: List[Dict[str, str]] = []
    for c in entry.contributors:
        val = _resolve_path(c.path, inputs, computed)
        contrib_out.append({
            "label": c.label,
            "path": c.path,
            "role": c.role,
            "value": _fmt_val(val),
        })
    help_lines = [
        entry.title,
        entry.equation,
        "",
        "Contributors:",
    ]
    for row in contrib_out:
        help_lines.append(f"• {row['label']}: {row['value']} ({row['role']})")
    help_lines.append(f"\nDoc: {entry.doc_section}")
    return {
        "metric_id": entry.metric_id,
        "title": entry.title,
        "equation": entry.equation,
        "doc_section": entry.doc_section,
        "contributors": contrib_out,
        "help_text": "\n".join(help_lines),
    }


def metric_help_text(metric_id: str, inputs: dict, computed: dict) -> str:
    """Short tooltip text for ``st.metric(..., help=...)``."""
    ex = get_metric_explanation(metric_id, inputs, computed)
    if not ex:
        return ""
    lines = [ex["equation"], ""]
    for row in ex["contributors"][:4]:
        lines.append(f"{row['label']}: {row['value']}")
    lines.append(f"({ex['doc_section']})")
    text = "\n".join(lines)
    return text if len(text) <= 480 else text[:477] + "…"


def build_explainability_index(inputs: dict, computed: dict) -> Dict[str, Any]:
    """Bundle of resolved explanations for report / API (subset of registry)."""
    resolved: Dict[str, Any] = {}
    for mid in METRIC_REGISTRY:
        ex = get_metric_explanation(mid, inputs, computed)
        if ex:
            resolved[mid] = ex
    return {
        "metrics": resolved,
        "metric_ids": list(METRIC_REGISTRY.keys()),
        "doc_reference": "AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md",
    }


def list_metric_ids() -> List[str]:
    return list(METRIC_REGISTRY.keys())
