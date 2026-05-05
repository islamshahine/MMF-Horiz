"""
engine/cartridge.py
───────────────────
Cartridge (polishing) filter sizing for horizontal MMF downstream.

Sizing basis
────────────
• Nominal element filtration areas (external surface):
    10" = 0.184 m²   20" = 0.37 m²   40" = 0.74 m²
• Max 6 elements per multi-round housing (industry standard)
• Target flux: user-specified m³/h per element; defaults to mid-range
• ΔP model: empirical power-law  ΔP_clean = k × (flux_m3h/m²)^1.2
  Coefficients calibrated to manufacturer data (Pall / Parker / 3M).
• Dirty ΔP ≈ 4 × clean (plugged element at end-of-life)
• Replacement trigger: ΔP_dirty > 0.7 bar
• Annual cost = n_elements × (365 / freq_days) × cost_per_element_USD
"""

import math

# ── Element catalogue ──────────────────────────────────────────────────────────
ELEMENT_SIZES = {
    '10"': {"area_m2": 0.184},
    '20"': {"area_m2": 0.37},
    '40"': {"area_m2": 0.74},
}

ELEMENT_SIZE_LABELS    = ['10"', '20"', '40"']
RATING_UM_OPTIONS      = [1, 5, 10]
MAX_ELEMENTS_PER_HOUSING = 6

# ── ΔP model coefficients: ΔP_clean (bar) = k × (flux m³/h/m²)^1.2 ────────────
# Calibrated at reference flux range 0.3–1.0 m³/h/m²
_DP_COEFF   = {1: 0.18, 5: 0.10, 10: 0.06}
_DP_EXP     = 1.2
_DP_DIRTY_FACTOR     = 4.0   # end-of-life: ~4× clean ΔP
DP_REPLACEMENT_BAR   = 0.70  # replacement trigger

# ── Replacement frequency (days) — indicative, depends on feed TSS ────────────
_FREQ_DAYS = {1: 30, 5: 60, 10: 90}

# ── Element unit cost (USD) — mid-market industrial estimate ──────────────────
_COST_USD = {
    ('10"', 1): 45,  ('10"', 5): 35,  ('10"', 10): 28,
    ('20"', 1): 85,  ('20"', 5): 65,  ('20"', 10): 52,
    ('40"', 1): 160, ('40"', 5): 125, ('40"', 10): 95,
}

# ── Recommended flux range (m³/h per element) — industry norm ─────────────────
RECOMMENDED_FLUX = {
    '10"': (0.05, 0.15),
    '20"': (0.10, 0.30),
    '40"': (0.20, 0.60),
}


def cartridge_design(
    design_flow_m3h: float,
    element_size: str        = '20"',
    rating_um: int           = 5,
    target_flux_m3h_element: float = None,
) -> dict:
    """
    Size a cartridge polishing filter bank.

    Parameters
    ----------
    design_flow_m3h         : Total flow to the cartridge station, m³/h
    element_size            : '10"' | '20"' | '40"'
    rating_um               : 1 | 5 | 10  (µm absolute)
    target_flux_m3h_element : Desired flux per element, m³/h.
                              If None, uses midpoint of recommended range.

    Returns
    -------
    dict — all sizing and economics results
    """
    if element_size not in ELEMENT_SIZES:
        raise ValueError(f"Unknown element size: {element_size!r}")
    if rating_um not in _DP_COEFF:
        raise ValueError(f"Unsupported rating: {rating_um} µm")

    area   = ELEMENT_SIZES[element_size]["area_m2"]
    lo, hi = RECOMMENDED_FLUX[element_size]

    if target_flux_m3h_element is None or target_flux_m3h_element <= 0:
        target_flux_m3h_element = (lo + hi) / 2.0

    # Sizing
    n_elements = max(1, math.ceil(design_flow_m3h / target_flux_m3h_element))
    n_housings = math.ceil(n_elements / MAX_ELEMENTS_PER_HOUSING)
    actual_flux_element = design_flow_m3h / n_elements   # m³/h per element
    actual_flux_m2      = actual_flux_element / area     # m³/h/m²

    # ΔP
    k        = _DP_COEFF[rating_um]
    dp_clean = k * actual_flux_m2 ** _DP_EXP
    dp_dirty = dp_clean * _DP_DIRTY_FACTOR

    # Economics
    freq_days     = _FREQ_DAYS[rating_um]
    repl_per_year = 365.0 / freq_days
    cost_each     = _COST_USD.get((element_size, rating_um), 70)
    annual_cost   = n_elements * repl_per_year * cost_each

    return {
        # Inputs
        "design_flow_m3h":          round(design_flow_m3h,        1),
        "element_size":             element_size,
        "element_area_m2":          area,
        "rating_um":                rating_um,
        "recommended_flux_lo":      lo,
        "recommended_flux_hi":      hi,
        "target_flux_m3h_element":  round(target_flux_m3h_element, 3),
        # Sizing
        "n_elements":               n_elements,
        "n_housings":               n_housings,
        "max_elements_per_housing": MAX_ELEMENTS_PER_HOUSING,
        # Performance
        "actual_flux_m3h_element":  round(actual_flux_element, 3),
        "actual_flux_m3h_m2":       round(actual_flux_m2,      3),
        "dp_clean_bar":             round(dp_clean, 4),
        "dp_dirty_bar":             round(dp_dirty, 4),
        "dp_replacement_bar":       DP_REPLACEMENT_BAR,
        # Economics
        "replacement_freq_days":    freq_days,
        "replacements_per_year":    round(repl_per_year, 1),
        "cost_per_element_usd":     cost_each,
        "annual_cost_usd":          round(annual_cost, 0),
    }
