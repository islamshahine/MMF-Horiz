"""engine/project_io.py — Project JSON serialisation / deserialisation.

Exports:
  SCHEMA_VERSION         str
  PERSISTED_STREAMLIT_KEYS  frozenset[str]  pp_* / ab_* keys stored under _ui_session in JSON
  coerce_persist_session_value(v) -> bool|int|float|str|None
  WIDGET_KEY_MAP         dict  inputs_key → session_state widget key (when they differ)
  inputs_to_json(inputs, ui_session_overrides=...) -> str
  get_widget_state_map(inputs) -> dict   {widget_key: value} ready for st.session_state
  json_to_inputs(json_str)    -> dict
  engine_inputs_dict(loaded)  -> dict    drop _ui_session before compute / strict payloads
  default_filename(project_name, doc_number) -> str
No Streamlit imports — pure Python only.
"""
import json
import re
from datetime import datetime
from numbers import Integral, Real
from typing import Any

SCHEMA_VERSION = "1.0"
_EXCLUDED = {"mat_info", "bw_total_min"}   # derived at render time, not user inputs

# Streamlit-only widgets (Pumps & power / air blower RFQ) — saved in JSON as _ui_session.
PERSISTED_STREAMLIT_KEYS: frozenset[str] = frozenset(
    {
        "pp_n_feed_parallel",
        "pp_n_bw_dol",
        "pp_n_bw_vfd",
        "pp_n_blowers",
        "pp_econ_bw_phil",
        "pp_blower_mode",
        "pp_feed_orient",
        "pp_feed_std",
        "pp_feed_mat",
        "pp_feed_seal",
        "pp_feed_vfd",
        "pp_bw_orient",
        "pp_bw_std",
        "pp_bw_mat",
        "pp_bw_seal",
        "pp_bw_vfd_allow",
        "pp_align_econ_energy",
        "pp_feed_iec",
        "ab_elevation_amsl_m",
        "ab_amb_temp_min_c",
        "ab_amb_temp_avg_c",
        "ab_amb_temp_max_c",
        "ab_rh_min_pct",
        "ab_rh_avg_pct",
        "ab_rh_max_pct",
        "ab_barometric_bara",
        "ab_installation_class",
        "ab_noise_limit_dba",
        "ab_electrical_area",
        "ab_site_location_notes",
        "ab_dust_salt_notes",
        "ab_corrosive_notes",
    }
)

# Air-blower RFQ (§4b) — ``_ui_session`` / project JSON always store **SI** for these keys.
# Streamlit ``session_state`` holds **display** values when ``unit_system == "imperial"``;
# ``get_widget_state_map`` converts SI→display on load; ``collect_ui_session_persist_dict``
# converts display→SI on save; ``ui/sidebar._reconvert_session_units`` transposes on toggle.
AB_RFQ_SESSION_TO_QUANTITY: dict[str, str] = {
    "ab_elevation_amsl_m": "length_m",
    "ab_amb_temp_min_c": "temperature_c",
    "ab_amb_temp_avg_c": "temperature_c",
    "ab_amb_temp_max_c": "temperature_c",
    "ab_barometric_bara": "pressure_bar",
}

# Dynamic media-layer widget prefixes → quantity (SI in JSON → display on imperial load).
_LAYER_WIDGET_PREFIX_QTY: tuple[tuple[str, str], ...] = (
    ("ld_", "length_m"),
    ("d10_", "length_mm"),
    ("rhd_", "density_kg_m3"),
    ("rh_", "density_kg_m3"),
    ("lv_thr_", "velocity_m_h"),
)


def _quantity_for_widget_key(wgt_key: str) -> str | None:
    """Return quantity id for a Streamlit widget key, or None if dimensionless."""
    q = AB_RFQ_SESSION_TO_QUANTITY.get(wgt_key)
    if q:
        return q
    from engine.units import SESSION_WIDGET_QUANTITIES

    q = SESSION_WIDGET_QUANTITIES.get(wgt_key)
    if q:
        return q
    for prefix, pq in _LAYER_WIDGET_PREFIX_QTY:
        if wgt_key.startswith(prefix) and wgt_key[len(prefix) :].isdigit():
            return pq
    return None


def widget_display_scalar(val: Any, wgt_key: str, unit_system: str) -> Any:
    """Convert a scalar SI value to display units for widget hydration (metric: unchanged)."""
    if unit_system != "imperial" or not isinstance(val, (int, float)):
        return val
    qty = _quantity_for_widget_key(wgt_key)
    if not qty:
        return val
    from engine.units import display_value as _dv

    return float(_dv(float(val), qty, "imperial"))


def _apply_imperial_widget_display(result: dict, unit_system: str) -> None:
    """In-place: convert all unitised widget scalars from SI (project JSON) to imperial display."""
    if unit_system != "imperial":
        return
    for wk, v in list(result.items()):
        nv = widget_display_scalar(v, wk, unit_system)
        if nv is not v:
            result[wk] = nv


def coerce_persist_session_value(v: Any) -> bool | int | float | str | None:
    """Normalise a Streamlit widget value for JSON under ``_ui_session`` (handles numpy scalars)."""
    if isinstance(v, bool):
        return v
    try:
        import numpy as np

        if isinstance(v, np.bool_):
            return bool(v)
    except ImportError:
        pass
    if isinstance(v, str):
        return v
    if isinstance(v, Integral) and not isinstance(v, bool):
        return int(v)
    if isinstance(v, Real) and not isinstance(v, bool):
        return float(v)
    return None


# Inputs whose session_state key differs from the inputs dict key.
# alpha_specific is stored divided by 1e9 in session_state ("alpha_res").
WIDGET_KEY_MAP: dict[str, str] = {
    # Process — water
    "feed_sal": "f_sal",    "feed_temp": "f_tmp",   "temp_low": "t_low",  "temp_high": "t_high",
    "bw_sal":   "b_sal",    "bw_temp":   "b_tmp",
    # Process — cartridge
    "cart_flow": "cart_flow", "cart_size": "cart_size", "cart_rating": "cart_rating",
    "cart_cip": "cart_cip", "cart_housing": "cart_hsg_sel",
    "cf_inlet_tss": "cf_inlet_tss", "cf_outlet_tss": "cf_outlet_tss",
    # Vessel — mechanical
    "shell_radio": "sh_r", "head_radio": "hd_r", "ov_shell": "ov_sh", "ov_head": "ov_hd",
    "protection_type": "prot_type",
    # Vessel — rubber lining
    "rubber_type_sel": "rub_type", "lining_mm": "rub_t", "rubber_layers": "rub_lay",
    "rubber_cost_m2": "rub_cost",  "rubber_labor_m2": "rub_lab",
    # Vessel — epoxy
    "epoxy_type_sel": "epx_type", "epoxy_dft_um": "epx_dft", "epoxy_coats": "epx_coats",
    "epoxy_cost_m2": "epx_cost",  "epoxy_labor_m2": "epx_lab",
    # Vessel — ceramic
    "ceramic_type_sel": "cer_type", "ceramic_dft_um": "cer_dft", "ceramic_coats": "cer_coats",
    "ceramic_cost_m2": "cer_cost",  "ceramic_labor_m2": "cer_lab",
    # Media — nozzle plate
    "np_bore_dia": "np_bd", "np_density": "np_den", "np_beam_sp": "np_bs", "np_override_t": "np_ov",
    # Media — cake resistance (stored /1e9 in session_state)
    "alpha_specific": "alpha_res",
    # BW
    "freeboard_mm": "fb_mm",   "dp_trigger_bar": "dp_trig", "support_type": "sup_t",
    "bw_s_drain": "bws1",      "bw_s_air": "bws2",    "bw_s_airw": "bws3",
    "bw_s_hw": "bws4",         "bw_s_settle": "bws5", "bw_s_fill": "bws6",
    "vessel_pressure_bar": "ves_press", "blower_air_delta_p_bar": "blower_air_dp",
    "blower_eta": "blower_eta",
    "blower_inlet_temp_c": "blower_t",  "tank_sf": "tank_sf", "bw_head_mwc": "bw_hd",
    "air_header_dn": "ah_dn",
    "saddle_h": "sad_h",
    # Econ — hydraulics
    "np_slot_dp": "np_slot", "p_residual": "p_res",   "dp_inlet_pipe": "dp_in",
    "dp_dist": "dp_dist",    "dp_outlet_pipe": "dp_out", "static_head": "stat_h",
    # Econ — efficiencies
    "pump_eta": "pump_e", "bw_pump_eta": "bwp_e", "motor_iec_class": "pp_feed_iec",
    # Econ — energy
    "elec_tariff": "elec_t", "op_hours_yr": "op_hr",
    # Econ — CAPEX
    "design_life_years": "des_life", "discount_rate": "disc_rate", "currency": "currency",
    "steel_cost_usd_kg": "st_cost",
    "erection_usd_per_kg_steel": "erect_usd_kg",
    "labor_usd_per_kg_steel": "labor_st_kg",
    "civil_usd_per_kg_working": "civil_w_kg",
    "piping_usd_vessel": "pip_usd",
    "instrumentation_usd_vessel": "instr_usd",
    "engineering_pct": "eng_pct", "contingency_pct": "cont_pct",
    "media_replace_years": "med_int", "econ_media_gravel": "mc_gr",
    "econ_media_sand": "mc_sd",       "econ_media_anthracite": "mc_an",
    "nozzle_replace_years": "noz_int", "nozzle_unit_cost": "noz_cost",
    "labour_usd_filter_yr": "lab_usd", "chemical_cost_m3": "chem_m3",
    # Econ — carbon
    "grid_intensity": "grid_co2",    "steel_carbon_kg": "st_co2",
    "concrete_carbon_kg": "con_co2",
    # Media — pilot calibration (explicit map for project reload / tooling)
    "solid_loading_scale": "solid_loading_scale",
    "maldistribution_factor": "maldistribution_factor",
    "alpha_calibration_factor": "alpha_calibration_factor",
    "tss_capture_efficiency": "tss_capture_efficiency",
    "expansion_calibration_scale": "expansion_calibration_scale",
}


def inputs_to_json(inputs: dict, *, ui_session_overrides: dict[str, Any] | None = None) -> str:
    """Serialise the inputs dict to a pretty-printed JSON string.

    If ``ui_session_overrides`` is set (e.g. from Streamlit session_state), allowed
    keys in :data:`PERSISTED_STREAMLIT_KEYS` are written under ``_ui_session`` for
    reload via :func:`get_widget_state_map`.
    """
    data = {k: v for k, v in inputs.items() if k not in _EXCLUDED}
    if ui_session_overrides:
        _sess: dict[str, bool | int | float | str] = {}
        for k in PERSISTED_STREAMLIT_KEYS:
            if k not in ui_session_overrides:
                continue
            _cv = coerce_persist_session_value(ui_session_overrides[k])
            if _cv is not None:
                _sess[k] = _cv
        if _sess:
            data["_ui_session"] = _sess
    data["_schema"] = SCHEMA_VERSION
    data["_saved"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    out = json.dumps(data, indent=2, default=str)
    try:
        from engine import logger as _log

        _log.log_project_save(str(data.get("project_name", "")), str(data.get("doc_number", "")))
    except Exception:
        pass
    return out


def get_widget_state_map(inputs: dict) -> dict:
    """Return {widget_key: value} suitable for bulk-setting st.session_state on load."""
    result: dict = {}
    _data = dict(inputs)
    _unit_system = str(_data.get("unit_system") or "metric")
    _ui = _data.pop("_ui_session", None)
    # Mapped keys (widget key differs from inputs key)
    for inp_key, wgt_key in WIDGET_KEY_MAP.items():
        if inp_key not in _data:
            continue
        val = _data[inp_key]
        if inp_key == "alpha_specific":
            val = val / 1e9   # widget stores the pre-×1e9 value
        result[wgt_key] = val
    # Scalar inputs not in the map — sidebar now uses key=inputs_key
    for inp_key, val in _data.items():
        if inp_key in WIDGET_KEY_MAP or inp_key in _EXCLUDED or inp_key == "layers":
            continue
        if isinstance(val, (bool, int, float, str)):
            result[inp_key] = val
    # Media carbon intensities — dynamic widget keys per selected type
    for _mt, _co2 in inputs.get("media_co2", {}).items():
        result[f"carbon_{_mt.replace(' ', '_')}"] = _co2
    # Layer widgets
    for i, layer in enumerate(inputs.get("layers", [])):
        result[f"lt_{i}"]  = layer.get("Type", "Fine sand")
        result[f"ld_{i}"]  = layer.get("Depth", 0.5)
        result[f"sup_{i}"] = layer.get("is_support", False)
        result[f"cap_{i}"] = round(layer.get("capture_frac", 0.0) * 100, 1)
        if layer.get("gac_mode") is not None:
            result[f"gac_mode_{i}"] = layer["gac_mode"]
        _lv = layer.get("lv_threshold_m_h")
        if _lv is not None:
            result[f"lv_thr_{i}"] = _lv
        if layer.get("Type") == "Custom":
            if layer.get("d10") is not None:
                result[f"d10_{i}"] = max(0.01, float(layer["d10"]))
            if layer.get("is_porous") and layer.get("rho_dry") is not None:
                result[f"rhd_{i}"] = layer["rho_dry"]
            elif layer.get("rho_p_eff") is not None:
                result[f"rh_{i}"] = layer["rho_p_eff"]
    _cdo = float(inputs.get("cart_dhc_override_g", 0.0) or 0.0)
    if _cdo > 1e-9:
        result["cart_dhc_vendor"] = True
    # Motor class widget (Pumps tab); legacy projects only stored motor_eta.
    if "pp_feed_iec" not in result:
        mi = inputs.get("motor_iec_class")
        if mi in ("IE3", "IE4"):
            result["pp_feed_iec"] = mi
        elif "motor_eta" in inputs:
            m = float(inputs["motor_eta"])
            result["pp_feed_iec"] = "IE4" if abs(m - 0.965) <= abs(m - 0.955) else "IE3"
        else:
            result["pp_feed_iec"] = "IE3"
    # Persisted pp_* / ab_* from file — applied last so they override inputs-derived defaults.
    if isinstance(_ui, dict):
        for _k, _v in _ui.items():
            if _k not in PERSISTED_STREAMLIT_KEYS:
                continue
            _cv = coerce_persist_session_value(_v)
            if _cv is not None:
                result[_k] = _cv
    _apply_imperial_widget_display(result, _unit_system)
    return result


def engine_inputs_dict(loaded: dict) -> dict:
    """Shallow copy of project inputs without ``_ui_session`` (safe for compute / validation)."""
    out = dict(loaded)
    out.pop("_ui_session", None)
    return out


def json_to_inputs(json_str: str) -> dict:
    """Deserialise project JSON. Returns inputs dict (metadata keys stripped)."""
    data = json.loads(json_str)
    pname = str(data.get("project_name", ""))
    pdoc = str(data.get("doc_number", ""))
    data.pop("_schema", None)
    data.pop("_saved", None)
    try:
        from engine import logger as _log

        _log.log_project_load(pname, pdoc)
    except Exception:
        pass
    return data


def default_filename(project_name: str, doc_number: str) -> str:
    """Slug-based filename for the project JSON download."""
    slug = re.sub(r"[^\w]+", "_", f"{project_name}_{doc_number}").strip("_")
    return f"{slug}.mmf.json"
