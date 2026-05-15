"""Design basis & traceability bundle for reports / JSON export (no Streamlit)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DOC_REFERENCE = "AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md"


def build_design_basis(inputs: dict, computed: dict) -> dict[str, Any]:
    """Assumptions, limits, and traceability links for enterprise review."""
    ch = computed.get("collector_hyd") or {}
    des = ch.get("design") or {} if ch else {}
    mal_used = float(computed.get("maldistribution_factor", 1.0) or 1.0)
    mal_from_model = bool(computed.get("maldistribution_from_collector_model"))

    assumptions = [
        "Process flows and filter count from sidebar process basis; outage N−R per stream.",
        "Water properties from salinity & temperature (IAPWS-style correlations).",
        "Media ΔP: Ergun + Ruth cake; LV/EBCT use chordal slice areas per layer.",
        f"Maldistribution factor **{mal_used:.3f}** — "
        + ("from 1D collector model." if mal_from_model else "manual / calibration."),
        "BW vessel nozzle DN from §4 schedule (velocity targets in engine/nozzles.py).",
        "Collector header ID linked to §4 Backwash inlet/outlet internal diameter when enabled.",
        "Fouling assistant (if used) is advisory only — not auto-applied to design duty.",
    ]

    limits = [
        "Collector header velocity advisory ≤ 3.0 m/s (1D model).",
        "Lateral perforation / slot velocity targets from lateral construction type.",
        "Maldistribution factor capped at 2.0 in Ergun integration.",
        "Cycle uncertainty: optimistic / expected / conservative envelopes (not Monte Carlo).",
        "ASME thickness: user overrides or calculated t_min + corrosion allowance.",
    ]

    traceability: list[dict[str, Any]] = [
        {
            "output": "q_per_filter",
            "value_si": round(float(computed.get("q_per_filter", 0)), 3),
            "unit": "m³/h",
            "source": "process.basis",
            "doc_section": "§3 Process basis",
        },
        {
            "output": "maldistribution_factor",
            "value": mal_used,
            "unit": "−",
            "source": "collector_hydraulics" if mal_from_model else "user_input",
            "doc_section": "§11.4 Priority 1 — collector 1A",
        },
        {
            "output": "bw_velocity",
            "value_si": round(float(inputs.get("bw_velocity", 0)), 3),
            "unit": "m/h",
            "source": "user_input",
            "doc_section": "§5 Backwash",
        },
    ]

    if ch:
        traceability.extend([
            {
                "output": "collector_hyd.maldistribution_factor_calc",
                "value": float(ch.get("maldistribution_factor_calc", 1.0)),
                "unit": "−",
                "source": ch.get("method", "collector_hydraulics"),
                "doc_section": "§11.4 — 1D Darcy + orifice ladder",
            },
            {
                "output": "collector_hyd.flow_imbalance_pct",
                "value": float(ch.get("flow_imbalance_pct", 0)),
                "unit": "%",
                "source": "distribution_solver",
                "doc_section": "§11.4 — 1B distribution",
            },
            {
                "output": "collector_hyd.lateral_length_m",
                "value_si": float(ch.get("lateral_length_m", 0)),
                "unit": "m",
                "source": "collector_geometry",
                "doc_section": "§11.4 — L_max geometry",
            },
        ])

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

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "doc_reference": DOC_REFERENCE,
        "project": {
            "name": str(inputs.get("project_name", "")),
            "document": str(inputs.get("doc_number", "")),
            "revision": str(inputs.get("revision", "")),
            "client": str(inputs.get("client", "")),
            "engineer": str(inputs.get("engineer", "")),
        },
        "assumptions": assumptions,
        "limits_and_criteria": limits,
        "traceability": traceability,
        "collector": collector_block,
        "exclusions": [
            "In-app CFD solve — not included; JSON/CSV BC export for external tools only.",
            "3D tee losses / nozzle-plate network — 1D+ dual-end screening only.",
            "Structural FEA of header/lateral tees — screening only.",
            "DCS / MILP backwash optimiser — not in this build (heuristic multi-day scheduler only).",
            "Monte Carlo uncertainty — not claimed.",
        ],
    }
