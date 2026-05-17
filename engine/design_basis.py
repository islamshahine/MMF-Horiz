"""Design basis & traceability bundle for reports / JSON export (no Streamlit)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from engine.explainability import METRIC_REGISTRY, _fmt_val, _resolve_path

DOC_REFERENCE = "AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md"
SCHEMA_VERSION = "1.1"


def _trace_row(
    trace_id: str,
    label: str,
    output: str,
    path: str,
    *,
    unit: str,
    source: str,
    doc_section: str,
    assumption_ids: Optional[List[str]] = None,
    value: Any = None,
    value_si: Any = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "trace_id": trace_id,
        "label": label,
        "output": output,
        "path": path,
        "unit": unit,
        "source": source,
        "doc_section": doc_section,
    }
    if assumption_ids:
        row["assumption_ids"] = list(assumption_ids)
    if value_si is not None:
        row["value_si"] = value_si
    elif value is not None:
        row["value"] = value
    return row


def _resolve_trace_value(path: str, inputs: dict, computed: dict) -> Any:
    return _resolve_path(path, inputs, computed)


def _build_assumptions_catalog(inputs: dict, computed: dict) -> List[dict[str, Any]]:
    ch = computed.get("collector_hyd") or {}
    mal_used = float(computed.get("maldistribution_factor", 1.0) or 1.0)
    mal_from_model = bool(computed.get("maldistribution_from_collector_model"))
    sl_eff = float(computed.get("solid_loading_effective_kg_m2", 0) or 0)
    sl = float(inputs.get("solid_loading", 0) or 0)
    sl_scale = float(inputs.get("solid_loading_scale", 1.0) or 1.0)

    ud = computed.get("underdrain_system_advisory") or {}
    ud_label = str(ud.get("catalogue_label") or "Custom (manual)")
    strainer = str(inputs.get("strainer_mat") or "")

    rows: List[dict[str, Any]] = [
        {
            "id": "ASM-PROC-01",
            "category": "Process",
            "text": "Process flows and filter count from sidebar; hydraulic N uses streams × filters with outage derate R.",
        },
        {
            "id": "ASM-WATER-01",
            "category": "Water properties",
            "text": "Feed and BW density / viscosity from salinity and temperature (IAPWS-style correlations).",
        },
        {
            "id": "ASM-MEDIA-01",
            "category": "Filtration / media",
            "text": "Media ΔP: Ergun per layer + Ruth cake; LV / EBCT use chordal slice areas per layer.",
        },
        {
            "id": "ASM-MEDIA-02",
            "category": "Filtration / media",
            "text": (
                f"Effective solids inventory M_eff = {sl:.2f} × {sl_scale:.2f} = "
                f"{sl_eff:.2f} kg/m² (sidebar cap × scale)."
            ),
        },
        {
            "id": "ASM-MEDIA-03",
            "category": "Filtration / media",
            "text": (
                f"Maldistribution factor {mal_used:.3f} applied in Ergun and cycle models — "
                + ("from 1D collector distribution." if mal_from_model else "manual / calibration.")
            ),
        },
        {
            "id": "ASM-BW-01",
            "category": "Backwash",
            "text": "BW vessel nozzle DN from §4 schedule (velocity targets in engine/nozzles.py).",
        },
        {
            "id": "ASM-BW-02",
            "category": "Backwash",
            "text": (
                "Multi-day BW scheduler: feasibility / optimized / tariff v3 / optional MILP lite "
                "(discrete ILP); not plant DCS-optimised."
            ),
        },
        {
            "id": "ASM-COLL-01",
            "category": "Collector",
            "text": "Collector header ID linked to §4 BW inlet/outlet internal diameter when enabled.",
        },
        {
            "id": "ASM-INT-01",
            "category": "Internals",
            "text": (
                f"Underdrain catalogue: {ud_label}; strainer material **{strainer or '—'}** "
                "(salinity-based default — not a corrosion guarantee)."
            ),
        },
        {
            "id": "ASM-FOUL-01",
            "category": "Fouling",
            "text": "Fouling workflow (if used) is advisory only — not auto-applied to design duty.",
        },
        {
            "id": "ASM-ENV-01",
            "category": "Process / envelope",
            "text": (
                "Operating envelope map (LV × EBCT): 2D screening grid vs per-layer thresholds; "
                "scenario markers from load_data — not RTD or effluent guarantee."
            ),
        },
        {
            "id": "ASM-DTARGET-01",
            "category": "Optimisation",
            "text": (
                "Design-to-target search: grid over n_filters / ID / BW velocity via compute_all; "
                "ranked rows meeting user caps — Apply to sidebar only, not auto-design."
            ),
        },
        {
            "id": "ASM-SPATIAL-001",
            "category": "Internals",
            "text": (
                "Spatial nozzle loading: 2D grid-Voronoi service areas on BW plate; "
                "lumped Q split by area — not bed RTD or CFD."
            ),
        },
        {
            "id": "ASM-SPATIAL-002",
            "category": "Internals",
            "text": (
                "Local orifice velocity from Q_basis × (A_service / ΣA) / A_open; "
                "dead-zone heuristic uses edge distance and loading factor."
            ),
        },
        {
            "id": "ASM-BLOWER-01",
            "category": "Backwash / energy",
            "text": (
                "Air blower: adiabatic ideal-gas compression in bw_system_sizing; "
                "optional generic vendor map + VFD affinity for screening comparison only."
            ),
        },
        {
            "id": "ASM-BW-SCHED-02",
            "category": "Backwash / scheduling",
            "text": (
                "BW scheduler v3 (tariff_aware_v3): heuristic phase search minimizing peak "
                "concurrent BW, peak-tariff filter-hours, and maintenance blackout overlap — "
                "not MILP or DCS-linked."
            ),
        },
    ]
    if ch:
        rows.append({
            "id": "ASM-COLL-02",
            "category": "Collector",
            "text": f"1D collector model: {ch.get('method', '—')}; distribution screening only (not 3D CFD).",
        })
    return rows


def _build_limits() -> List[str]:
    return [
        "Collector header velocity advisory ≤ 3.0 m/s (1D model).",
        "Lateral perforation / slot velocity targets from lateral construction type.",
        "Maldistribution factor capped at 2.0 in Ergun integration.",
        "Cycle uncertainty: optimistic / expected / conservative envelopes (not Monte Carlo).",
        "ASME thickness: user overrides or calculated t_min + corrosion allowance.",
        "Nozzle plate hole density: manual drilled false-bottom typical 45–55 /m²; wedge / mushroom per catalogue.",
    ]


def _build_traceability(inputs: dict, computed: dict) -> List[dict[str, Any]]:
    """Resolved output ↔ input paths for review and report tables."""
    rows: List[dict[str, Any]] = []
    seq = 0

    def add(
        label: str,
        output: str,
        path: str,
        *,
        unit: str,
        source: str,
        doc_section: str,
        assumption_ids: Optional[List[str]] = None,
    ) -> None:
        nonlocal seq
        seq += 1
        val = _resolve_trace_value(path, inputs, computed)
        row = _trace_row(
            f"TRC-{seq:03d}",
            label,
            output,
            path,
            unit=unit,
            source=source,
            doc_section=doc_section,
            assumption_ids=assumption_ids,
        )
        if isinstance(val, (int, float)) and unit not in ("—", "bool", "text"):
            try:
                row["value_si"] = round(float(val), 6) if abs(float(val)) < 1e6 else round(float(val), 3)
            except (TypeError, ValueError):
                row["value"] = _fmt_val(val)
        else:
            row["value"] = _fmt_val(val)
        rows.append(row)

    add(
        "Plant flow",
        "q_per_filter",
        "inputs.total_flow",
        unit="m³/h",
        source="process.basis",
        doc_section="§3 Process basis",
        assumption_ids=["ASM-PROC-01"],
    )
    add(
        "Streams",
        "streams",
        "inputs.streams",
        unit="—",
        source="process.basis",
        doc_section="§3 Process basis",
        assumption_ids=["ASM-PROC-01"],
    )
    add(
        "Filters per stream",
        "n_filters",
        "inputs.n_filters",
        unit="—",
        source="process.basis",
        doc_section="§3 Process basis",
        assumption_ids=["ASM-PROC-01"],
    )
    add(
        "Flow per filter",
        "q_per_filter",
        "computed.q_per_filter",
        unit="m³/h",
        source="process.basis",
        doc_section="§3 Process basis",
        assumption_ids=["ASM-PROC-01"],
    )
    add(
        "M_max (sidebar)",
        "solid_loading",
        "inputs.solid_loading",
        unit="kg/m²",
        source="user_input",
        doc_section="§4 Filtration / cake",
        assumption_ids=["ASM-MEDIA-02"],
    )
    add(
        "Solid loading scale",
        "solid_loading_scale",
        "inputs.solid_loading_scale",
        unit="−",
        source="user_input",
        doc_section="§4 Filtration / cake",
        assumption_ids=["ASM-MEDIA-02"],
    )
    add(
        "M_eff (cycles)",
        "solid_loading_effective_kg_m2",
        "computed.solid_loading_effective_kg_m2",
        unit="kg/m²",
        source="computed",
        doc_section="§4 Filtration / cake",
        assumption_ids=["ASM-MEDIA-02"],
    )
    add(
        "α specific resistance",
        "alpha_specific",
        "inputs.alpha_specific",
        unit="m/kg",
        source="user_input",
        doc_section="§4 Ruth cake",
        assumption_ids=["ASM-MEDIA-01"],
    )
    add(
        "ΔP BW trigger",
        "dp_trigger_bar",
        "inputs.dp_trigger_bar",
        unit="bar",
        source="user_input",
        doc_section="§4 ΔP — Ergun + Ruth",
        assumption_ids=["ASM-MEDIA-01"],
    )
    add(
        "Maldistribution factor",
        "maldistribution_factor",
        "computed.maldistribution_factor",
        unit="−",
        source="collector_hydraulics" if computed.get("maldistribution_from_collector_model") else "user_input",
        doc_section="§11.4 Collector / Ergun",
        assumption_ids=["ASM-MEDIA-03", "ASM-COLL-02"],
    )
    add(
        "Dirty ΔP (trigger)",
        "dp_dirty_bar",
        "computed.bw_dp.dp_dirty_bar",
        unit="bar",
        source="computed",
        doc_section="§4 ΔP — Ergun + Ruth",
        assumption_ids=["ASM-MEDIA-01"],
    )
    add(
        "Design TSS",
        "tss_avg",
        "inputs.tss_avg",
        unit="mg/L",
        source="user_input",
        doc_section="§4 Cycle matrix",
        assumption_ids=["ASM-MEDIA-01"],
    )
    add(
        "Cycle — expected (N)",
        "cycle_expected_h",
        "computed.cycle_uncertainty.N.cycle_expected_h",
        unit="h",
        source="computed",
        doc_section="§4 Cycle uncertainty",
        assumption_ids=["ASM-MEDIA-01", "ASM-MEDIA-02"],
    )
    _env = computed.get("operating_envelope") or {}
    if _env.get("enabled") and (_env.get("scenario_points") or []):
        add(
            "Envelope region (N)",
            "operating_envelope_region_n",
            "computed.operating_envelope.scenario_points[0].region",
            unit="—",
            source="computed",
            doc_section="§3.23 Operating envelope",
            assumption_ids=["ASM-ENV-01"],
        )
    add(
        "BW velocity",
        "bw_velocity",
        "inputs.bw_velocity",
        unit="m/h",
        source="user_input",
        doc_section="§5 Backwash",
        assumption_ids=["ASM-BW-01"],
    )
    add(
        "BW trains (rated)",
        "bw_trains",
        "computed.bw_timeline.bw_trains",
        unit="—",
        source="computed",
        doc_section="§5 BW feasibility",
        assumption_ids=["ASM-BW-02"],
    )
    add(
        "Peak concurrent BW",
        "peak_concurrent_bw",
        "computed.bw_timeline.peak_concurrent_bw",
        unit="filters",
        source="computed",
        doc_section="§5 BW scheduler",
        assumption_ids=["ASM-BW-02"],
    )
    add(
        "Feed salinity",
        "feed_sal",
        "inputs.feed_sal",
        unit="ppt",
        source="user_input",
        doc_section="§6 Internals / corrosion",
        assumption_ids=["ASM-INT-01"],
    )
    add(
        "Strainer material",
        "strainer_mat",
        "inputs.strainer_mat",
        unit="text",
        source="user_input",
        doc_section="§6 Internals / corrosion",
        assumption_ids=["ASM-INT-01"],
    )
    add(
        "Nozzle plate density",
        "np_density",
        "inputs.np_density",
        unit="/m²",
        source="user_input",
        doc_section="§11 Nozzle plate",
        assumption_ids=["ASM-INT-01"],
    )
    add(
        "Nozzle catalogue",
        "nozzle_catalogue_id",
        "inputs.nozzle_catalogue_id",
        unit="text",
        source="catalogue",
        doc_section="§11 Nozzle plate",
        assumption_ids=["ASM-INT-01"],
    )

    cnp = computed.get("collector_nozzle_plate") or {}
    if cnp:
        add(
            "Plate open area %",
            "open_area_pct",
            "computed.collector_nozzle_plate.open_area_pct",
            unit="%",
            source="nozzle_plate_layout",
            doc_section="§11 Nozzle plate",
            assumption_ids=["ASM-INT-01"],
        )

    ch = computed.get("collector_hyd") or {}
    if ch:
        add(
            "Collector mal_f (calc.)",
            "maldistribution_factor_calc",
            "computed.collector_hyd.maldistribution_factor_calc",
            unit="−",
            source=ch.get("method", "collector_hydraulics"),
            doc_section="§11.4 — 1D Darcy + orifice ladder",
            assumption_ids=["ASM-COLL-02"],
        )
        add(
            "Flow imbalance %",
            "flow_imbalance_pct",
            "computed.collector_hyd.flow_imbalance_pct",
            unit="%",
            source="distribution_solver",
            doc_section="§11.4 — 1B distribution",
            assumption_ids=["ASM-COLL-02"],
        )
        add(
            "Lateral length",
            "lateral_length_m",
            "computed.collector_hyd.lateral_length_m",
            unit="m",
            source="collector_geometry",
            doc_section="§11.4 — L_max geometry",
            assumption_ids=["ASM-COLL-01"],
        )

    return rows


def _build_metric_links() -> List[dict[str, str]]:
    """Cross-link explainability registry IDs to doc sections."""
    return [
        {
            "metric_id": mid,
            "title": entry.title,
            "doc_section": entry.doc_section,
        }
        for mid, entry in METRIC_REGISTRY.items()
    ]


def build_design_basis(inputs: dict, computed: dict) -> dict[str, Any]:
    """Assumptions, limits, and traceability links for enterprise review."""
    ch = computed.get("collector_hyd") or {}
    des = ch.get("design") or {} if ch else {}

    assumptions_catalog = _build_assumptions_catalog(inputs, computed)
    assumptions = [f"**{a['id']}** — {a['text']}" for a in assumptions_catalog]

    collector_block: dict[str, Any] = {}
    if ch:
        from engine.collector_hydraulics import distribution_solver_converged

        collector_block = {
            "method": ch.get("method"),
            "distribution": {
                "iterations": ch.get("distribution_iterations"),
                "converged": distribution_solver_converged(ch),
                "residual_rel": ch.get("distribution_residual_rel"),
            },
            "maldistribution_factor_calc": ch.get("maldistribution_factor_calc"),
            "flow_imbalance_pct": ch.get("flow_imbalance_pct"),
            "design_checklist": list(ch.get("design_checklist") or []),
            "screening": {
                "lateral_dn_suggest_mm": des.get("lateral_dn_suggest_mm"),
                "perforation_d_suggest_mm": des.get("perforation_d_suggest_mm"),
                "n_laterals_suggested": des.get("n_laterals_suggested"),
            },
        }

    ud_adv = computed.get("underdrain_system_advisory") or {}
    underdrain_block = {
        "catalogue_id": inputs.get("nozzle_catalogue_id") or None,
        "catalogue_label": ud_adv.get("catalogue_label") or "Custom (manual)",
        "np_density_per_m2": float(inputs.get("np_density") or 0),
        "strainer_material": str(inputs.get("strainer_mat") or ""),
        "tone": ud_adv.get("tone"),
        "finding_count": len(ud_adv.get("findings") or []),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "doc_reference": DOC_REFERENCE,
        "project": {
            "name": str(inputs.get("project_name", "")),
            "document": str(inputs.get("doc_number", "")),
            "revision": str(inputs.get("revision", "")),
            "client": str(inputs.get("client", "")),
            "engineer": str(inputs.get("engineer", "")),
        },
        "assumptions_catalog": assumptions_catalog,
        "assumptions": assumptions,
        "limits_and_criteria": _build_limits(),
        "traceability": _build_traceability(inputs, computed),
        "explainability_metrics": _build_metric_links(),
        "collector": collector_block,
        "underdrain": underdrain_block,
        "exclusions": [
            "In-app CFD solve — not included; JSON/CSV BC export for external tools only.",
            "3D tee losses / nozzle-plate network — 1D+ dual-end screening only.",
            "Structural FEA of header/lateral tees — screening only.",
            "DCS / MILP backwash optimiser — not in this build (heuristic multi-day scheduler only).",
            "Monte Carlo uncertainty — not claimed.",
            "Gravity-filter underdrain (e.g. Leopold IMT) and collector-drilled orifices — not in pressurized MMF catalogue.",
        ],
    }
