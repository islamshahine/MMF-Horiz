"""Streamlit hooks for inlet feed / BW outlet collector optimization."""
from __future__ import annotations

from typing import Any

from engine.units import display_value, si_value


def collector_optim_context_si(session: Any, unit_system: str) -> dict[str, Any]:
    """Build SI context for ``optimise_collector_design`` from session widgets."""
    last = dict(session.get("mmf_last_inputs") or {})
    area = float(session.get("mmf_last_avg_area") or last.get("avg_area") or 25.0)
    q_pf = float(session.get("mmf_last_q_per_filter") or last.get("q_per_filter") or 0.0)
    bw_vel = si_value(
        float(session.get("bw_velocity", last.get("bw_velocity", 30.0))),
        "velocity_m_h",
        unit_system,
    )
    q_bw = max(bw_vel * area, q_pf * 2.0) if area > 0 else q_pf * 2.0

    linked = bool(session.get("collector_header_id_linked", True))
    if linked:
        hdr = si_value(
            float(session.get("_collector_header_id_linked_disp", 0.59)),
            "length_m",
            unit_system,
        )
    else:
        hdr = si_value(
            float(session.get("collector_header_id_manual", 0.25)),
            "length_m",
            unit_system,
        )

    return {
        "q_bw_m3h": q_bw,
        "filter_area_m2": area,
        "cyl_len_m": float(
            session.get("mmf_last_cyl_len")
            or last.get("cyl_len")
            or 8.0,
        ),
        "nominal_id_m": float(
            session.get("mmf_last_nominal_id")
            or si_value(
                float(session.get("nominal_id", last.get("nominal_id", 5.5))),
                "length_m",
                unit_system,
            ),
        ),
        "np_bore_dia_mm": si_value(
            float(session.get("np_bore_dia", last.get("np_bore_dia", 50))),
            "length_mm",
            unit_system,
        ),
        "np_density_per_m2": float(session.get("np_density", last.get("np_density", 10)) or 10),
        "collector_header_id_m": hdr,
        "n_bw_laterals": int(session.get("n_bw_laterals", 4) or 4),
        "lateral_dn_mm": si_value(
            float(session.get("lateral_dn_mm", 50)),
            "length_mm",
            unit_system,
        ),
        "lateral_spacing_m": si_value(
            float(session.get("lateral_spacing_m", 0)),
            "length_m",
            unit_system,
        ),
        "lateral_length_m": si_value(
            float(session.get("lateral_length_m", 0)),
            "length_m",
            unit_system,
        ),
        "lateral_orifice_d_mm": si_value(
            float(session.get("lateral_orifice_d_mm", 0)),
            "length_mm",
            unit_system,
        ),
        "n_orifices_per_lateral": int(session.get("n_orifices_per_lateral", 0) or 0),
        "nozzle_plate_h_m": si_value(
            float(session.get("nozzle_plate_h", last.get("nozzle_plate_h", 1.0))),
            "length_m",
            unit_system,
        ),
        "collector_h_m": si_value(
            float(session.get("collector_h", last.get("collector_h", 4.2))),
            "length_m",
            unit_system,
        ),
        "use_geometry_lateral": bool(session.get("use_geometry_lateral", True)),
        "lateral_material": str(session.get("lateral_material", "Stainless steel")),
        "lateral_construction": str(
            session.get("lateral_construction", "Drilled perforated pipe"),
        ),
        "max_lateral_open_area_fraction": float(
            session.get("max_lateral_open_area_fraction", 0) or 0,
        ),
        "wedge_slot_width_mm": si_value(
            float(session.get("wedge_slot_width_mm", 0)),
            "length_mm",
            unit_system,
        ),
        "wedge_open_area_fraction": float(
            session.get("wedge_open_area_fraction", 0) or 0,
        ),
        "bw_head_mwc": float(session.get("bw_head_mwc", last.get("bw_head_mwc", 15)) or 15),
        "lateral_discharge_cd": float(session.get("lateral_discharge_cd", 0.62) or 0.62),
        "rho_water": float(last.get("rho_bw", 1000) or 1000),
    }


def run_collector_optimization_from_session() -> None:
    """on_change — grid-search collector layout and apply best patch to widgets."""
    import streamlit as st

    from engine.collector_optimisation import optimise_collector_design
    from ui.collector_apply import apply_collector_patch_to_session

    us = st.session_state.get("unit_system", "metric")
    ctx = collector_optim_context_si(st.session_state, us)
    with st.spinner("Running collector optimization solver…"):
        result = optimise_collector_design(ctx)
    if result.get("ok"):
        apply_collector_patch_to_session(result.get("patch") or {}, us)
        st.session_state["_collector_opt_message"] = str(result.get("message", "Done."))
    else:
        st.session_state["_collector_opt_message"] = str(
            result.get("message", "Optimization failed."),
        )
    # on_click already triggers a script rerun; st.rerun() inside callbacks is a no-op.
