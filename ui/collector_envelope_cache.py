"""On-demand collector BW-flow envelope — avoids N× hydraulics inside ``compute_all``."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import streamlit as st

from engine.collector_envelope import build_collector_bw_flow_envelope
from engine.collector_manifold import K_TEE_BRANCH_DEFAULT
from engine.water import water_properties

_ENVELOPE_CACHE_VERSION = 1

_COLLECTOR_KW_KEYS = (
    "filter_area_m2",
    "cyl_len_m",
    "nominal_id_m",
    "np_bore_dia_mm",
    "np_density_per_m2",
    "collector_header_id_m",
    "n_laterals",
    "lateral_dn_mm",
    "lateral_spacing_m",
    "lateral_length_m",
    "lateral_orifice_d_mm",
    "n_orifices_per_lateral",
    "nozzle_plate_h_m",
    "collector_h_m",
    "use_geometry_lateral",
    "lateral_material",
    "lateral_construction",
    "max_open_area_fraction",
    "wedge_slot_width_mm",
    "wedge_open_area_fraction",
    "bw_head_mwc",
    "discharge_coefficient",
    "rho_water",
    "header_feed_mode",
    "k_tee_branch",
)


def collector_compute_kwargs(work: dict[str, Any], computed: dict[str, Any]) -> dict[str, Any]:
    """Same kwargs as ``compute_all`` uses for ``compute_collector_hydraulics`` (no q_bw)."""
    avg_area = float(computed.get("avg_area") or 1.0)
    cyl_len = float(computed.get("cyl_len") or 1.0)
    nominal_id = float(computed.get("nominal_id") or work.get("nominal_id") or 1.0)
    bw_wp = water_properties(
        float(work.get("bw_temp", 25) or 25),
        float(work.get("bw_sal", 35) or 35),
    )
    rho_bw = float(bw_wp["density_kg_m3"])
    return dict(
        filter_area_m2=avg_area,
        cyl_len_m=cyl_len,
        nominal_id_m=nominal_id,
        np_bore_dia_mm=float(work.get("np_bore_dia", 50.0) or 50.0),
        np_density_per_m2=float(work.get("np_density", 45.0) or 45.0),
        collector_header_id_m=float(work.get("collector_header_id_m", 0.25) or 0.25),
        n_laterals=int(work.get("n_bw_laterals", 4) or 4),
        lateral_dn_mm=float(work.get("lateral_dn_mm", 50.0) or 50.0),
        lateral_spacing_m=float(work.get("lateral_spacing_m", 0.0) or 0.0),
        lateral_length_m=float(work.get("lateral_length_m", 0.0) or 0.0),
        lateral_orifice_d_mm=float(work.get("lateral_orifice_d_mm", 0.0) or 0.0),
        n_orifices_per_lateral=int(work.get("n_orifices_per_lateral", 0) or 0),
        nozzle_plate_h_m=float(work.get("nozzle_plate_h", 0) or 0),
        collector_h_m=float(work.get("collector_h", 0) or 0),
        use_geometry_lateral=bool(work.get("use_geometry_lateral", True)),
        lateral_material=str(work.get("lateral_material", "Stainless steel")),
        lateral_construction=str(work.get("lateral_construction", "Drilled perforated pipe")),
        max_open_area_fraction=float(work.get("max_lateral_open_area_fraction", 0) or 0),
        wedge_slot_width_mm=float(work.get("wedge_slot_width_mm", 0) or 0),
        wedge_open_area_fraction=float(work.get("wedge_open_area_fraction", 0) or 0),
        bw_head_mwc=float(work.get("bw_head_mwc", 15.0) or 15.0),
        discharge_coefficient=float(work.get("lateral_discharge_cd", 0.62) or 0.62),
        rho_water=rho_bw,
        header_feed_mode=str(work.get("collector_header_feed_mode", "one_end") or "one_end"),
        k_tee_branch=(
            K_TEE_BRANCH_DEFAULT
            if bool(work.get("collector_tee_loss_enable", False))
            else 0.0
        ),
    )


def reference_q_bw_m3h(work: dict[str, Any], computed: dict[str, Any]) -> float:
    avg_area = float(computed.get("avg_area") or 1.0)
    q_per = float(computed.get("q_per_filter") or 0.0)
    bw_vel = float(work.get("bw_velocity", 30) or 30)
    return max(bw_vel * avg_area, 2.0 * q_per)


def envelope_model_fingerprint(work: dict[str, Any], computed: dict[str, Any]) -> str:
    kw = collector_compute_kwargs(work, computed)
    payload = {k: kw[k] for k in _COLLECTOR_KW_KEYS if k in kw}
    payload["reference_q_bw_m3h"] = round(reference_q_bw_m3h(work, computed), 4)
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


@st.cache_data(show_spinner=False)
def build_collector_bw_flow_envelope_cached(
    kwargs_tuple: tuple[tuple[str, Any], ...],
    reference_q_bw_m3h: float,
    n_points: int,
    q_low_frac: float,
    q_high_frac: float,
    cache_version: int = _ENVELOPE_CACHE_VERSION,
) -> dict[str, Any]:
    kw = dict(kwargs_tuple)
    return build_collector_bw_flow_envelope(
        compute_kwargs=kw,
        reference_q_bw_m3h=float(reference_q_bw_m3h),
        n_points=int(n_points),
        q_low_frac=float(q_low_frac),
        q_high_frac=float(q_high_frac),
    )


def refresh_collector_envelope_in_computed(
    work: dict[str, Any],
    computed: dict[str, Any],
) -> dict[str, Any]:
    applied = st.session_state.get("_collector_envelope_applied")
    if not isinstance(applied, dict):
        applied = _default_collector_envelope_applied()
    kw = collector_compute_kwargs(work, computed)
    q_ref = reference_q_bw_m3h(work, computed)
    kwargs_tuple = tuple(sorted(kw.items()))
    env = build_collector_bw_flow_envelope_cached(
        kwargs_tuple,
        float(q_ref),
        int(applied.get("collector_bw_envelope_n_points", 7) or 7),
        float(applied.get("collector_bw_envelope_q_low_frac", 0.55) or 0.55),
        float(applied.get("collector_bw_envelope_q_high_frac", 1.15) or 1.15),
    )
    computed["collector_bw_envelope"] = env
    fp = envelope_model_fingerprint(work, computed)
    st.session_state["mmf_collector_bw_envelope"] = env
    st.session_state["mmf_collector_bw_envelope_fp"] = fp
    return env


def restore_collector_envelope_if_valid(
    work: dict[str, Any],
    computed: dict[str, Any],
) -> None:
    """Re-attach a prior sweep after a full plant recompute when geometry is unchanged."""
    env = st.session_state.get("mmf_collector_bw_envelope")
    fp_saved = st.session_state.get("mmf_collector_bw_envelope_fp")
    if not isinstance(env, dict) or not env.get("active") or not fp_saved:
        return
    if envelope_model_fingerprint(work, computed) != fp_saved:
        computed["collector_bw_envelope"] = None
        return
    computed["collector_bw_envelope"] = env


def _default_collector_envelope_applied() -> dict[str, Any]:
    return {
        "collector_bw_envelope_n_points": 7,
        "collector_bw_envelope_q_low_frac": 0.55,
        "collector_bw_envelope_q_high_frac": 1.15,
    }
