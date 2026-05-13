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
    "flow_m3d": (
        "m³/d", "MGD",
        0.000264172,  # 1 m³/d = 0.000264172 MGD
        3785.41,      # 1 MGD  = 3785.41 m³/d
    ),
    # Velocity / loading rate
    "velocity_m_h": (
        "m/h", "gpm/ft²",
        0.40746,    # 1 m/h = 0.40746 gpm/ft²
        2.4542,     # 1 gpm/ft² = 2.4542 m/h
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
    # Power
    "power_kw": (
        "kW", "hp",
        1.34102,    # 1 kW = 1.34102 hp
        0.745700,   # 1 hp = 0.7457 kW
    ),
    # Cost — no conversion, always USD
    "cost_usd": (
        "USD", "USD",
        1.0, 1.0,
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
    "design_pressure":    "pressure_bar",
    "corrosion":          "length_mm",
    "lining_mm":          "length_mm",
    "np_bore_dia":        "length_mm",
    "np_beam_sp":         "length_mm",
    "bw_velocity":        "velocity_m_h",
    "air_scour_rate":     "velocity_m_h",
    "velocity_threshold": "velocity_m_h",
    "solid_loading":      "mass_kg",
    "tss_low":            "concentration_mg_l",
    "tss_avg":            "concentration_mg_l",
    "tss_high":           "concentration_mg_l",
}


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
    return result
