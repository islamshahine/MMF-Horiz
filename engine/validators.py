"""Centralised engineering input validation for AQUASIGHT™ MMF (pure Python).

All numeric checks assume **SI base values** — the same dict ``inputs`` that
``compute_all`` receives after ``render_sidebar`` → ``convert_inputs`` (see
``engine/units.py``). Lengths in messages are labelled **(SI, m)**; the sidebar
still shows imperial/metric via ``fmt`` / ``ulbl`` / ``dv`` — do not convert
validation thresholds to display units here.
"""
from __future__ import annotations

import copy
from typing import Any, List, Sequence

# Reference inputs (SI) aligned with tests/test_integration.py::_INPUTS — used only when
# user inputs fail validation so compute_all can still return a full computed dict.
_MAT = {"ASTM A516-70": {"S_kgf_cm2": 1200, "T_max_c": 350, "rho": 7850}}
_REF_LAYERS = [
    {"Type": "Gravel", "Depth": 0.20, "epsilon0": 0.46, "d10": 6.0, "cu": 1.0,
     "rho_p_eff": 2600, "psi": 0.90, "is_porous": False, "is_support": True,
     "lv_threshold_m_h": None, "ebct_threshold_min": None},
    {"Type": "Fine sand", "Depth": 0.80, "epsilon0": 0.42, "d10": 0.8, "cu": 1.3,
     "rho_p_eff": 2650, "psi": 0.80, "is_porous": False, "is_support": False,
     "lv_threshold_m_h": 12.0, "ebct_threshold_min": 4.0},
    {"Type": "Anthracite", "Depth": 0.80, "epsilon0": 0.48, "d10": 1.3, "cu": 1.5,
     "rho_p_eff": 1450, "psi": 0.70, "is_porous": False, "is_support": False,
     "lv_threshold_m_h": 15.0, "ebct_threshold_min": 2.0},
]
REFERENCE_FALLBACK_INPUTS: dict[str, Any] = {
    "total_flow": 21000.0, "streams": 1, "n_filters": 16,
    "hydraulic_assist": 0, "redundancy": 1,
    "feed_temp": 27.0, "feed_sal": 35.0,
    "temp_low": 15.0, "temp_high": 35.0,
    "tss_low": 5.0, "tss_avg": 10.0, "tss_high": 20.0,
    "bw_temp": 27.0, "bw_sal": 35.0,
    "velocity_threshold": 12.0, "ebct_threshold": 5.0,
    "nominal_id": 5.5, "total_length": 24.3, "end_geometry": "Elliptic 2:1",
    "lining_mm": 4.0, "material_name": "ASTM A516-70",
    "mat_info": _MAT["ASTM A516-70"],
    "shell_radio": "FULL", "head_radio": "FULL",
    "design_pressure": 7.0, "corrosion": 1.5, "steel_density": 7850.0,
    "ov_shell": 0.0, "ov_head": 0.0,
    "nozzle_plate_h": 1.0, "np_bore_dia": 50.0, "np_density": 50.0,
    "np_beam_sp": 500.0, "np_override_t": 0.0, "np_slot_dp": 0.03,
    "collector_h": 4.2, "freeboard_mm": 200,
    "layers": copy.deepcopy(_REF_LAYERS),
    "solid_loading": 1.5, "captured_solids_density": 1020.0,
    "solid_loading_scale": 1.0, "maldistribution_factor": 1.0,
    "alpha_calibration_factor": 1.0, "tss_capture_efficiency": 1.0,
    "expansion_calibration_scale": 1.0,
    "alpha_specific": 1e12, "dp_trigger_bar": 1.0,
    "bw_velocity": 30.0, "air_scour_rate": 55.0,
    "air_scour_mode": "manual", "air_scour_target_expansion_pct": 20.0,
    "airwater_step_water_m_h": 12.5,
    "bw_timeline_stagger": "feasibility_trains",
    "bw_cycles_day": 1,
    "bw_s_drain": 10, "bw_s_air": 1, "bw_s_airw": 5,
    "bw_s_hw": 10, "bw_s_settle": 2, "bw_s_fill": 10, "bw_total_min": 38,
    "vessel_pressure_bar": 4.0, "blower_air_delta_p_bar": 0.15, "blower_eta": 0.70, "blower_inlet_temp_c": 30.0,
    "tank_sf": 1.5, "bw_head_mwc": 15.0,
    "default_rating": "150#", "nozzle_stub_len": 350, "strainer_mat": "SS 316L",
    "air_header_dn": 200, "manhole_dn": 600, "n_manholes": 1,
    "support_type": "Saddle", "saddle_h": 0.8, "saddle_contact_angle": 120.0,
    "leg_h": 1.2, "leg_section": 150.0, "base_plate_t": 20.0, "gusset_t": 12.0,
    "protection_type": "Rubber lining",
    "external_environment": "Non-marine (industrial / inland)",
    "seismic_design_category": "Not evaluated",
    "seismic_importance_factor": 1.0,
    "spectral_accel_sds": 0.0,
    "site_class_asce": "B",
    "basic_wind_ms": 0.0,
    "wind_exposure": "C",
    "rubber_type_sel": "EPDM", "rubber_layers": 2,
    "rubber_cost_m2": 0.0, "rubber_labor_m2": 0.0,
    "epoxy_type_sel": "High-build epoxy", "epoxy_dft_um": 350.0,
    "epoxy_coats": 2, "epoxy_cost_m2": 0.0, "epoxy_labor_m2": 0.0,
    "ceramic_type_sel": "Ceramic-filled epoxy", "ceramic_dft_um": 500.0,
    "ceramic_coats": 2, "ceramic_cost_m2": 0.0, "ceramic_labor_m2": 0.0,
    "cart_flow": 21000.0, "cart_size": '40"', "cart_rating": 10,
    "cart_housing": 40, "cart_cip": False,
    "cart_dhc_override_g": 0.0,
    "cf_sync_feed_tss": False, "cf_sync_tss_band": "avg",
    "cf_inlet_tss": 10.0, "cf_outlet_tss": 1.5,
    "dp_dist": 0.02, "dp_inlet_pipe": 0.30, "dp_outlet_pipe": 0.20,
    "p_residual": 0.5, "static_head": 0.0,
    "pump_eta": 0.75, "bw_pump_eta": 0.72, "motor_eta": 0.95,
    "elec_tariff": 0.10, "op_hours_yr": 8400,
    "design_life_years": 20, "discount_rate": 5.0,
    "project_life_years": 20,
    "inflation_rate": 2.0,
    "escalation_energy_pct": 2.5,
    "escalation_maintenance_pct": 3.0,
    "tax_rate": 0.0,
    "depreciation_method": "straight_line",
    "depreciation_years": 20,
    "salvage_value_pct": 5.0,
    "maintenance_pct_capex": 2.0,
    "replacement_interval_media": 7.0,
    "replacement_interval_nozzles": 10.0,
    "replacement_interval_lining": 15.0,
    "annual_benefit_usd": 0.0,
    "steel_cost_usd_kg": 3.5,
    "erection_usd_vessel": 50000.0, "piping_usd_vessel": 80000.0,
    "instrumentation_usd_vessel": 30000.0, "civil_usd_vessel": 40000.0,
    "engineering_pct": 12.0, "contingency_pct": 10.0,
    "media_replace_years": 7.0,
    "econ_media_gravel": 80.0, "econ_media_sand": 150.0,
    "econ_media_anthracite": 400.0,
    "nozzle_replace_years": 10.0, "nozzle_unit_cost": 15.0,
    "labour_usd_filter_yr": 5000.0, "chemical_cost_m3": 0.005,
    "grid_intensity": 0.45, "steel_carbon_kg": 1.85, "concrete_carbon_kg": 0.13,
    "media_co2": {"Fine sand": 0.006, "Anthracite": 0.150},
}


def validate_positive(name: str, value: Any, errors: List[str], *, exclusive_min: float = 0.0) -> None:
    """Append an error if value is not a number > exclusive_min."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        errors.append(f"{name}: value is not numeric ({value!r}).")
        return
    if v <= exclusive_min:
        errors.append(f"{name}: must be > {exclusive_min:g} (got {v:g}).")


def validate_range(
    name: str,
    value: Any,
    lo: float,
    hi: float,
    errors: List[str],
    *,
    inclusive: bool = True,
) -> None:
    """Append an error if value is outside [lo, hi] (inclusive) or (lo, hi) if not inclusive."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        errors.append(f"{name}: value is not numeric ({value!r}).")
        return
    if inclusive:
        ok = lo <= v <= hi
    else:
        ok = lo < v < hi
    if not ok:
        errors.append(f"{name}: must be within [{lo:g}, {hi:g}] (got {v:g}).")


def validate_required(keys: Sequence[str], data: dict, errors: List[str]) -> None:
    """Append errors for any missing keys in data."""
    for k in keys:
        if k not in data or data[k] is None:
            errors.append(f"Missing required input: {k}.")


def validate_layers(layers: Any, errors: List[str], warnings: List[str]) -> None:
    """Validate media layer list structure and physical fields."""
    if not isinstance(layers, list) or len(layers) == 0:
        errors.append("Media layers: at least one layer is required.")
        return
    for i, layer in enumerate(layers):
        if not isinstance(layer, dict):
            errors.append(f"Media layer {i + 1}: must be a dict.")
            continue
        depth = layer.get("Depth")
        try:
            d = float(depth)
        except (TypeError, ValueError):
            errors.append(f"Media layer {i + 1}: Depth must be numeric.")
        else:
            if d <= 0:
                errors.append(f"Media layer {i + 1}: Depth must be > 0.")

        mtype = str(layer.get("Type", ""))
        d10 = layer.get("d10")
        if mtype.strip().lower() != "custom":
            try:
                d10v = float(d10)
            except (TypeError, ValueError):
                errors.append(f"Media layer {i + 1} ({mtype}): d10 must be numeric.")
            else:
                if d10v <= 0:
                    errors.append(f"Media layer {i + 1} ({mtype}): d10 must be > 0.")

        eps = layer.get("epsilon0")
        try:
            ev = float(eps)
        except (TypeError, ValueError):
            errors.append(f"Media layer {i + 1}: epsilon0 must be numeric.")
        else:
            if not (0.0 < ev < 1.0):
                errors.append(
                    f"Media layer {i + 1}: epsilon0 must be strictly between 0 and 1 (got {ev:g})."
                )

        if not layer.get("is_support"):
            lvt = layer.get("lv_threshold_m_h")
            if lvt is not None:
                try:
                    if float(lvt) <= 0.0:
                        errors.append(
                            f"Media layer {i + 1}: lv_threshold_m_h must be > 0 when set."
                        )
                except (TypeError, ValueError):
                    errors.append(
                        f"Media layer {i + 1}: lv_threshold_m_h must be numeric when set."
                    )
            ebt = layer.get("ebct_threshold_min")
            if ebt is not None:
                try:
                    if float(ebt) <= 0.0:
                        errors.append(
                            f"Media layer {i + 1}: ebct_threshold_min must be > 0 when set."
                        )
                except (TypeError, ValueError):
                    errors.append(
                        f"Media layer {i + 1}: ebct_threshold_min must be numeric when set."
                    )

    # Capture weights (% of filterable solids) — explicit mode requires Σ = 100 %.
    _non_sup = [L for L in layers if isinstance(L, dict) and not L.get("is_support")]
    if _non_sup:
        _has_cap = [L.get("capture_frac") is not None for L in _non_sup]
        if any(_has_cap) and not all(_has_cap):
            warnings.append(
                "Media: capture weight is set on some but not all filterable layers — "
                "layers without a weight use a **depth-proportional** share. "
                "For an explicit **percentage split**, set capture weight on **every** filterable layer "
                "so they sum to **100%**."
            )
        if _non_sup and all(L.get("capture_frac") is not None for L in _non_sup):
            try:
                sum_pct = sum(float(L["capture_frac"]) * 100.0 for L in _non_sup)
            except (TypeError, ValueError):
                warnings.append(
                    "Media: capture_frac on filterable layers must be numeric when set."
                )
            else:
                if abs(sum_pct - 100.0) > 0.5:
                    warnings.append(
                        f"Media: capture weights on filterable layers sum to **{sum_pct:.1f}%** "
                        f"(target **100%** for a literal percentage cake split). "
                        f"The engine still **normalises** relative weights in ΔP/cake — "
                        f"adjust values or use **Normalize to 100%** in the sidebar."
                    )


def validate_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Cross-check key engineering inputs (SI magnitudes, same contract as ``compute_all``).

    ``render_sidebar`` must have applied ``convert_inputs`` so lengths, flows,
    and velocities here are SI even when the UI unit toggle is imperial.

    Returns
    -------
    dict with keys:
        valid: bool
        errors: list[str]
        warnings: list[str]
    """
    errors: List[str] = []
    warnings: List[str] = []

    validate_required(
        [
            "total_flow", "streams", "n_filters", "nominal_id", "total_length",
            "nozzle_plate_h", "collector_h", "bw_velocity", "layers",
        ],
        inputs,
        errors,
    )
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    validate_positive("total_flow", inputs["total_flow"], errors)
    validate_positive("streams", inputs["streams"], errors)
    try:
        nf = int(inputs["n_filters"])
        if nf < 1:
            errors.append("n_filters: must be an integer >= 1.")
    except (TypeError, ValueError):
        errors.append("n_filters: must be an integer >= 1.")

    try:
        ha = int(inputs.get("hydraulic_assist", 0))
        if ha < 0 or ha > 4:
            errors.append("hydraulic_assist: must be an integer from 0 to 4.")
    except (TypeError, ValueError):
        errors.append("hydraulic_assist: must be an integer from 0 to 4.")

    try:
        _nf = int(inputs["n_filters"])
        _ha = int(inputs.get("hydraulic_assist", 0))
        _rd = int(inputs.get("redundancy", 0))
        if _ha >= _nf:
            errors.append(
                "hydraulic_assist (physical spares / stream): must be < total physical number of filters / stream."
            )
        if _nf - _ha - _rd < 1:
            errors.append(
                "filters/stream − standby − outage depth must leave ≥1 active path "
                "in the worst hydraulic scenario."
            )
    except (TypeError, ValueError):
        pass

    validate_positive("nominal_id", inputs["nominal_id"], errors)

    try:
        nid = float(inputs["nominal_id"])
        tlen = float(inputs["total_length"])
        if tlen <= nid:
            errors.append(
                f"total_length ({tlen:g} m, SI) must be greater than nominal_id ({nid:g} m, SI)."
            )
    except (TypeError, ValueError):
        errors.append("nominal_id / total_length: must be numeric.")

    validate_positive("bw_velocity", inputs["bw_velocity"], errors)

    try:
        np_h = float(inputs["nozzle_plate_h"])
        col_h = float(inputs["collector_h"])
        if col_h <= np_h:
            errors.append(
                f"collector_h ({col_h:g} m, SI) must be greater than nozzle_plate_h ({np_h:g} m, SI)."
            )
    except (TypeError, ValueError):
        errors.append("nozzle_plate_h / collector_h: must be numeric.")

    layers = inputs.get("layers")
    validate_layers(layers, errors, warnings)

    valid = len(errors) == 0
    return {"valid": valid, "errors": errors, "warnings": warnings}
