"""
engine/units.py
───────────────
Unit conversion system for AQUASIGHT™ MMF.

All internal engine calculations use SI (metric) units.
This module converts between SI and imperial for display.

Design principle
----------------
- Engine ALWAYS works in SI: m, m³/h, bar, kg, °C, mm
- Conversions happen at the UI boundary ONLY
- Every quantity has a:
    display_value(si_value, quantity, system) -> float
    si_value(display_value, quantity, system) -> float
    unit_label(quantity, system) -> str

Supported unit systems
----------------------
"metric"   SI units (m, m³/h, bar, kg, °C)
"imperial" US/UK units (ft, gpm, psi, lb, °F)

Quantity catalogue
------------------
Each entry: (metric_label, imperial_label,
             to_imperial_factor, to_metric_factor)
to_imperial = si_value * to_imperial_factor
to_metric   = imperial_value * to_metric_factor

Exports
-------
UNIT_SYSTEMS        list of available systems
QUANTITIES          dict of quantity definitions
display_value(v, quantity, system) -> float
si_value(v, quantity, system) -> float
unit_label(quantity, system) -> str
format_value(v, quantity, system, decimals) -> str
convert_inputs(inputs_display, system) -> inputs_si
    Converts a full inputs dict from display to SI.
"""

UNIT_SYSTEMS = ["metric", "imperial"]

# ── Conversion factors ─────────────────────────────────────
# Format: quantity_key: (
#     metric_label,
#     imperial_label,
#     metric_to_imperial_factor,
#     imperial_to_metric_factor,
# )
QUANTITIES = {
    # Flow
    "flow_m3h": (
        "m³/h", "gpm",
        4.40287,    # 1 m³/h = 4.40287 gpm
        0.22712,    # 1 gpm  = 0.22712 m³/h
    ),
    # Blower inlet flow: SI base value is Nm³/h (0 °C, 1.01325 bar); imperial = SCFM
    # (≈ 60 °F, 14.696 psia).  1 SCFM ≈ 1.699 Nm³/h (common HVAC / blower catalogue factor).
    "air_flow_nm3h": (
        "Nm³/h", "SCFM",
        1.0 / 1.699,
        1.699,
    ),
    "flow_m3_min": (
        "m³/min", "ft³/min",
        35.3147,
        0.0283168464,
    ),
    "flow_m3d": (
        "m³/d", "MGD",
        0.000264172,  # 1 m³/d = 0.000264172 MGD
        3785.41,      # 1 MGD  = 3785.41 m³/d
    ),
    "volume_m3_per_day": (
        "m³/d", "ft³/d",
        35.3147,     # 1 m³/d → ft³/d
        0.0283168464,
    ),
    # Velocity / loading rate
    "velocity_m_h": (
        "m/h", "gpm/ft²",
        0.40746,    # 1 m/h = 0.40746 gpm/ft²
        2.4542,     # 1 gpm/ft² = 2.4542 m/h
    ),
    "velocity_m_s": (
        "m/s", "ft/s",
        3.28084,
        0.30480,
    ),
    # Pressure
    "pressure_bar": (
        "bar", "psi",
        14.5038,    # 1 bar = 14.5038 psi
        0.068948,   # 1 psi = 0.068948 bar
    ),
    "pressure_mwc": (
        "mWC", "ft WC",
        3.28084,    # 1 mWC = 3.28084 ft WC
        0.30480,    # 1 ft WC = 0.30480 mWC
    ),
    "pressure_kpa": (
        "kPa", "psi",
        0.145037738,   # 1 kPa → psi
        6.8947572932,  # 1 psi → kPa
    ),
    # Length
    "length_m": (
        "m", "ft",
        3.28084,    # 1 m = 3.28084 ft
        0.30480,    # 1 ft = 0.30480 m
    ),
    "length_mm": (
        "mm", "in",
        0.039370,   # 1 mm = 0.03937 in
        25.4000,    # 1 in = 25.4 mm
    ),
    # Area
    "area_m2": (
        "m²", "ft²",
        10.7639,    # 1 m² = 10.7639 ft²
        0.092903,   # 1 ft² = 0.092903 m²
    ),
    # Volume
    "volume_m3": (
        "m³", "ft³",
        35.3147,    # 1 m³ = 35.3147 ft³
        0.028317,   # 1 ft³ = 0.028317 m³
    ),
    # Mass
    "mass_kg": (
        "kg", "lb",
        2.20462,    # 1 kg = 2.20462 lb
        0.453592,   # 1 lb = 0.453592 kg
    ),
    "mass_t": (
        "t", "short ton",
        1.10231,    # 1 metric ton = 1.10231 short tons
        0.907185,   # 1 short ton = 0.907185 t
    ),
    "mass_rate_kg_d": (
        "kg/d", "lb/d",
        2.20462,
        0.453592,
    ),
    # Temperature
    "temperature_c": (
        "°C", "°F",
        None,       # non-linear — handled separately
        None,
    ),
    # Density
    "density_kg_m3": (
        "kg/m³", "lb/ft³",
        0.062428,   # 1 kg/m³ = 0.062428 lb/ft³
        16.0185,    # 1 lb/ft³ = 16.0185 kg/m³
    ),
    "co2_intensity_kg_m3": (
        "kg CO₂/m³", "lb CO₂/ft³",
        0.062428,
        16.0185,
    ),
    "co2_kg_per_kwh": (
        "kg CO₂/kWh", "lb CO₂/kWh",
        2.20462,
        0.453592,
    ),
    # Areal loading (cake / solids on media)
    "loading_kg_m2": (
        "kg/m²", "lb/ft²",
        0.204816,   # 1 kg/m² = (2.20462 lb/kg) / (10.7639 ft²/m²)
        4.88243,    # 1 lb/ft² → kg/m²
    ),
    "linear_density_kg_m": (
        "kg/m", "lb/ft",
        0.671969,   # kg/m → lb/ft
        1.48816,
    ),
    # Dynamic viscosity (engine uses cP); imperial shown as lb·s/ft²
    "viscosity_cp": (
        "cP", "lb·s/ft²",
        6.8523e-5,  # 1 cP = 10⁻³ Pa·s = (10⁻³/14.5939) lb·s/ft²
        14593.9,
    ),
    # Power
    "power_kw": (
        "kW", "hp",
        1.34102,    # 1 kW = 1.34102 hp
        0.745700,   # 1 hp = 0.7457 kW
    ),
    "energy_kwh_m3": (
        "kWh/m³", "kWh/ft³",
        0.0283168464,  # kWh per m³ → kWh per ft³ (= ÷ 35.3147)
        35.3147,
    ),
    # Cost — no conversion, always USD
    "cost_usd": (
        "USD", "USD",
        1.0, 1.0,
    ),
    "cost_usd_per_m3": (
        "USD/m³", "USD/ft³",
        0.0283168464,
        35.3147,
    ),
    "cost_usd_per_m3d": (
        "USD/(m³/d)", "USD/(ft³/d)",
        0.0283168464,
        35.3147,
    ),
    "cost_usd_per_kg": (
        "USD/kg", "USD/lb",
        0.453592,
        2.20462,
    ),
    # Dimensionless — no conversion
    "dimensionless": (
        "", "",
        1.0, 1.0,
    ),
    # Time — no conversion
    "time_min": (
        "min", "min",
        1.0, 1.0,
    ),
    "time_h": (
        "h", "h",
        1.0, 1.0,
    ),
    # Concentration
    "concentration_mg_l": (
        "mg/L", "mg/L",
        1.0, 1.0,
    ),
    # Salinity
    "salinity_ppt": (
        "ppt", "ppt",
        1.0, 1.0,
    ),
    # Specific resistance
    "alpha_m_kg": (
        "×10⁹ m/kg", "×10⁹ m/kg",
        1.0, 1.0,
    ),
    # Scalar reported per m² of plate (e.g. nozzles/m²) → per ft²
    "quantity_per_m2": (
        "/m²", "/ft²",
        0.092903,   # multiply SI value (per m²) → per ft²
        10.7639,
    ),
    # Traditional pressure-unit stress (not SI Pa)
    "stress_kgf_cm2": (
        "kgf/cm²", "psi",
        14.2233433071,
        0.07030695796,
    ),
    "force_kn": (
        "kN", "lbf",
        224.809,
        0.00444822,
    ),
    "moment_knm": (
        "kN·m", "ft·lbf",
        737.562,
        0.00135582,
    ),
    "flow_l_min": (
        "L/min", "gal/min",
        0.264172,
        3.78541,
    ),
}


def display_value(
    si_val: float,
    quantity: str,
    system: str = "metric",
) -> float:
    """
    Convert SI value to display value.
    Temperature handled specially (°C → °F = ×9/5 + 32).
    Returns si_val unchanged for metric or unknown quantity.
    """
    if system == "metric" or si_val is None:
        return si_val
    if quantity not in QUANTITIES:
        return si_val
    _, _, factor, _ = QUANTITIES[quantity]
    if quantity == "temperature_c":
        return si_val * 9.0 / 5.0 + 32.0
    if factor is None:
        return si_val
    return si_val * factor


def si_value(
    disp_val: float,
    quantity: str,
    system: str = "metric",
) -> float:
    """
    Convert display value back to SI.
    Temperature: °F → °C = (°F − 32) × 5/9.
    Returns disp_val unchanged for metric.
    """
    if system == "metric" or disp_val is None:
        return disp_val
    if quantity not in QUANTITIES:
        return disp_val
    _, _, _, back_factor = QUANTITIES[quantity]
    if quantity == "temperature_c":
        return (disp_val - 32.0) * 5.0 / 9.0
    if back_factor is None:
        return disp_val
    return disp_val * back_factor


def unit_label(
    quantity: str,
    system: str = "metric",
) -> str:
    """Return the display label for a quantity."""
    if quantity not in QUANTITIES:
        return ""
    metric_lbl, imperial_lbl, _, _ = QUANTITIES[quantity]
    return metric_lbl if system == "metric" \
           else imperial_lbl


def format_value(
    si_val: float,
    quantity: str,
    system: str = "metric",
    decimals: int = 2,
) -> str:
    """
    Convert SI value and return formatted string with label.
    Example: format_value(1312.5, "flow_m3h", "imperial")
             → "5778.5 gpm"
    """
    if si_val is None:
        return "—"
    val = display_value(si_val, quantity, system)
    lbl = unit_label(quantity, system)
    fmt = f"{val:,.{decimals}f}"
    return f"{fmt} {lbl}".strip()


# ── Input conversion map ───────────────────────────────────
# Maps inputs dict key → quantity key in QUANTITIES
# Used by convert_inputs() to convert a full inputs dict
INPUT_QUANTITY_MAP = {
    "total_flow":         "flow_m3h",
    "nominal_id":         "length_m",
    "total_length":       "length_m",
    "nozzle_plate_h":     "length_m",
    "collector_h":        "length_m",
    "feed_temp":          "temperature_c",
    "bw_temp":            "temperature_c",
    "temp_low":           "temperature_c",
    "temp_high":          "temperature_c",
    "design_temp":        "temperature_c",
    "blower_inlet_temp_c": "temperature_c",
    "design_pressure":    "pressure_bar",
    "dp_trigger_bar":     "pressure_bar",
    "vessel_pressure_bar": "pressure_bar",
    "np_slot_dp":         "pressure_bar",
    "p_residual":         "pressure_bar",
    "dp_inlet_pipe":      "pressure_bar",
    "dp_dist":            "pressure_bar",
    "dp_outlet_pipe":     "pressure_bar",
    "corrosion":          "length_mm",
    "lining_mm":          "length_mm",
    "np_bore_dia":        "length_mm",
    "np_beam_sp":         "length_mm",
    "np_override_t":      "length_mm",
    "ov_shell":           "length_mm",
    "ov_head":            "length_mm",
    "nozzle_stub_len":    "length_mm",
    "air_header_dn":      "length_mm",
    "freeboard_mm":       "length_mm",
    "base_plate_t":       "length_mm",
    "gusset_t":           "length_mm",
    "leg_section":        "length_mm",
    "bw_velocity":        "velocity_m_h",
    "air_scour_rate":     "velocity_m_h",
    "airwater_step_water_m_h": "velocity_m_h",
    "velocity_threshold": "velocity_m_h",
    "cart_flow":          "flow_m3h",
    "solid_loading":      "loading_kg_m2",
    "captured_solids_density": "density_kg_m3",
    "steel_density":      "density_kg_m3",
    "bw_head_mwc":        "pressure_mwc",
    "static_head":        "pressure_mwc",
    "basic_wind_ms":      "velocity_m_s",
    "saddle_h":           "length_m",
    "leg_h":              "length_m",
    "tss_low":            "concentration_mg_l",
    "tss_avg":            "concentration_mg_l",
    "tss_high":           "concentration_mg_l",
}


def transpose_display_value(
    disp_val: float,
    quantity: str,
    old_system: str,
    new_system: str,
) -> float:
    """Convert a single display value from old_system units to new_system units."""
    if old_system == new_system or disp_val is None:
        return disp_val
    si = si_value(disp_val, quantity, old_system)
    return display_value(si, quantity, new_system)


def _build_session_widget_quantities() -> dict:
    """Map Streamlit widget session_state keys → quantity for unit-system toggles."""
    from engine import project_io as _pio
    # inputs dict keys that map to different widget keys per layout branch
    _skip_inputs = {"base_plate_t", "gusset_t", "leg_section"}
    m: dict = {}
    for inp_key, qty in INPUT_QUANTITY_MAP.items():
        if inp_key in _skip_inputs:
            continue
        wkey = _pio.WIDGET_KEY_MAP.get(inp_key, inp_key)
        m[wkey] = qty
    for wkey, qty in (
        ("sad_bp", "length_mm"), ("sad_gt", "length_mm"),
        ("leg_bp", "length_mm"), ("leg_gt", "length_mm"), ("leg_s", "length_mm"),
    ):
        m[wkey] = qty
    return m


def convert_inputs(
    inputs_display: dict,
    system: str,
) -> dict:
    """
    Convert all display-unit inputs back to SI.
    Keys not in INPUT_QUANTITY_MAP are passed unchanged.
    Returns new dict — does not modify original.
    """
    if system == "metric":
        return dict(inputs_display)
    result = dict(inputs_display)
    for key, qty in INPUT_QUANTITY_MAP.items():
        if key in result and result[key] is not None:
            result[key] = si_value(result[key], qty, system)
    # Media layer depths are entered in display length units (m or ft)
    if "layers" in result and result["layers"]:
        for layer in result["layers"]:
            if layer is not None and layer.get("Depth") is not None:
                layer["Depth"] = si_value(layer["Depth"], "length_m", system)
    return result


SESSION_WIDGET_QUANTITIES = _build_session_widget_quantities()
