"""engine/project_io.py — Project JSON serialisation / deserialisation.

Exports:
  SCHEMA_VERSION         str
  WIDGET_KEY_MAP         dict  inputs_key → session_state widget key (when they differ)
  inputs_to_json(inputs) -> str
  get_widget_state_map(inputs) -> dict   {widget_key: value} ready for st.session_state
  json_to_inputs(json_str)    -> dict
  default_filename(project_name, doc_number) -> str
No Streamlit imports — pure Python only.
"""
import json
import re
from datetime import datetime

SCHEMA_VERSION = "1.0"
_EXCLUDED = {"mat_info", "bw_total_min"}   # derived at render time, not user inputs

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
    "vessel_pressure_bar": "ves_press", "blower_eta": "blower_eta",
    "blower_inlet_temp_c": "blower_t",  "tank_sf": "tank_sf", "bw_head_mwc": "bw_hd",
    "air_header_dn": "ah_dn",
    # Econ — hydraulics
    "np_slot_dp": "np_slot", "p_residual": "p_res",   "dp_inlet_pipe": "dp_in",
    "dp_dist": "dp_dist",    "dp_outlet_pipe": "dp_out", "static_head": "stat_h",
    # Econ — efficiencies
    "pump_eta": "pump_e", "bw_pump_eta": "bwp_e", "motor_eta": "mot_e",
    # Econ — energy
    "elec_tariff": "elec_t", "op_hours_yr": "op_hr",
    # Econ — CAPEX
    "design_life_years": "des_life", "discount_rate": "disc_rate", "currency": "currency",
    "steel_cost_usd_kg": "st_cost",  "erection_usd_vessel": "erect_usd",
    "piping_usd_vessel": "pip_usd",  "instrumentation_usd_vessel": "instr_usd",
    "civil_usd_vessel": "civil_usd", "engineering_pct": "eng_pct", "contingency_pct": "cont_pct",
    # Econ — OPEX
    "media_replace_years": "med_int", "econ_media_gravel": "mc_gr",
    "econ_media_sand": "mc_sd",       "econ_media_anthracite": "mc_an",
    "nozzle_replace_years": "noz_int", "nozzle_unit_cost": "noz_cost",
    "labour_usd_filter_yr": "lab_usd", "chemical_cost_m3": "chem_m3",
    # Econ — carbon
    "grid_intensity": "grid_co2",    "steel_carbon_kg": "st_co2",
    "concrete_carbon_kg": "con_co2", "media_co2_gravel": "mco_gr",
    "media_co2_sand": "mco_sd",      "media_co2_anthracite": "mco_an",
}


def inputs_to_json(inputs: dict) -> str:
    """Serialise the inputs dict to a pretty-printed JSON string."""
    data = {k: v for k, v in inputs.items() if k not in _EXCLUDED}
    data["_schema"] = SCHEMA_VERSION
    data["_saved"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return json.dumps(data, indent=2, default=str)


def get_widget_state_map(inputs: dict) -> dict:
    """Return {widget_key: value} suitable for bulk-setting st.session_state on load."""
    result: dict = {}
    # Mapped keys (widget key differs from inputs key)
    for inp_key, wgt_key in WIDGET_KEY_MAP.items():
        if inp_key not in inputs:
            continue
        val = inputs[inp_key]
        if inp_key == "alpha_specific":
            val = val / 1e9   # widget stores the pre-×1e9 value
        result[wgt_key] = val
    # Scalar inputs not in the map — sidebar now uses key=inputs_key
    for inp_key, val in inputs.items():
        if inp_key in WIDGET_KEY_MAP or inp_key in _EXCLUDED or inp_key == "layers":
            continue
        if isinstance(val, (bool, int, float, str)):
            result[inp_key] = val
    # Layer widgets
    for i, layer in enumerate(inputs.get("layers", [])):
        result[f"lt_{i}"]  = layer.get("Type", "Fine sand")
        result[f"ld_{i}"]  = layer.get("Depth", 0.5)
        result[f"sup_{i}"] = layer.get("is_support", False)
        result[f"cap_{i}"] = round(layer.get("capture_frac", 0.0) * 100, 1)
        if layer.get("gac_mode") is not None:
            result[f"gac_mode_{i}"] = layer["gac_mode"]
    return result


def json_to_inputs(json_str: str) -> dict:
    """Deserialise project JSON. Returns inputs dict (metadata keys stripped)."""
    data = json.loads(json_str)
    data.pop("_schema", None)
    data.pop("_saved", None)
    return data


def default_filename(project_name: str, doc_number: str) -> str:
    """Slug-based filename for the project JSON download."""
    slug = re.sub(r"[^\w]+", "_", f"{project_name}_{doc_number}").strip("_")
    return f"{slug}.mmf.json"
