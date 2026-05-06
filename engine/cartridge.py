"""
engine/cartridge.py
───────────────────
Cartridge (polishing) filter sizing for horizontal MMF downstream.

Sizing basis
────────────
• Standard element: 2.5" (63.5 mm) OD, pleated, lengths 20 / 40 / 50 / 60 inch.
  Filtration area scales linearly with length (same pleat count per inch).
    20" = 0.37 m²   40" = 0.74 m²   50" = 0.93 m²   60" = 1.10 m²
• Elements are loaded in parallel inside multi-round housings.
  Housing capacity (n_elem_per_housing) is user-specified; typical sizes:
  6, 12, 18, 24, 36, 48, 72 elements per housing.
• Target flux: user-specified m³/h per element; defaults to mid-range.
• ΔP model: empirical power-law  ΔP_clean = k × (flux_m3h/m²)^1.2
  Coefficients calibrated to Pall / Parker / 3M manufacturer data.
• Dirty ΔP ≈ 4 × clean (plugged element at end-of-life).
• Replacement trigger: ΔP_dirty > 0.7 bar.
• Annual cost = n_elements × (365 / freq_days) × cost_per_element_USD.
"""

import math

# ── Element catalogue ──────────────────────────────────────────────────────────
# All 2.5" (63.5 mm) OD pleated elements; area scales with length.
ELEMENT_SIZES = {
    '20"': {"area_m2": 0.37},
    '40"': {"area_m2": 0.74},
    '50"': {"area_m2": 0.93},
    '60"': {"area_m2": 1.10},
}

ELEMENT_SIZE_LABELS = ['20"', '40"', '50"', '60"']
RATING_UM_OPTIONS   = [1, 5, 10]

# ── Typical housing capacities (elements per housing) ─────────────────────────
HOUSING_CAPACITY_OPTIONS = [6, 12, 18, 24, 36, 48, 72]
DEFAULT_ELEMENTS_PER_HOUSING = 24

# ── ΔP model: ΔP_clean (bar) = k × (flux m³/h/m²)^1.2 ───────────────────────
_DP_COEFF          = {1: 0.18, 5: 0.10, 10: 0.06}
_DP_EXP            = 1.2
_DP_DIRTY_FACTOR   = 4.0
DP_REPLACEMENT_BAR = 0.70

# ── Replacement frequency (days) — indicative ─────────────────────────────────
_FREQ_DAYS = {1: 30, 5: 60, 10: 90}

# ── Element unit cost (USD) — mid-market industrial ───────────────────────────
_COST_USD = {
    ('20"', 1):  85,  ('20"', 5):  65,  ('20"', 10):  52,
    ('40"', 1): 160,  ('40"', 5): 125,  ('40"', 10):  95,
    ('50"', 1): 195,  ('50"', 5): 155,  ('50"', 10): 118,
    ('60"', 1): 230,  ('60"', 5): 180,  ('60"', 10): 138,
}

# ── Recommended flux range (m³/h per element) ─────────────────────────────────
RECOMMENDED_FLUX = {
    '20"': (0.10, 0.30),
    '40"': (0.20, 0.60),
    '50"': (0.25, 0.75),
    '60"': (0.30, 0.90),
}


def cartridge_design(
    design_flow_m3h: float,
    element_size: str             = '40"',
    rating_um: int                = 5,
    target_flux_m3h_element: float = None,
    n_elem_per_housing: int       = DEFAULT_ELEMENTS_PER_HOUSING,
) -> dict:
    """
    Size a cartridge polishing filter bank.

    Parameters
    ----------
    design_flow_m3h         : Total flow to the cartridge station, m³/h
    element_size            : '20"' | '40"' | '50"' | '60"'
    rating_um               : 1 | 5 | 10  (µm absolute)
    target_flux_m3h_element : Desired flux per element, m³/h.
                              If None, uses midpoint of recommended range.
    n_elem_per_housing      : Elements per housing (6 / 12 / 18 / 24 / 36 / 48 / 72).

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
    n_housings = math.ceil(n_elements / n_elem_per_housing)
    actual_flux_element = design_flow_m3h / n_elements
    actual_flux_m2      = actual_flux_element / area

    # ΔP
    k        = _DP_COEFF[rating_um]
    dp_clean = k * actual_flux_m2 ** _DP_EXP
    dp_dirty = dp_clean * _DP_DIRTY_FACTOR

    # Economics
    freq_days     = _FREQ_DAYS[rating_um]
    repl_per_year = 365.0 / freq_days
    cost_each     = _COST_USD.get((element_size, rating_um), 100)
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
        "n_elem_per_housing":       n_elem_per_housing,
        "n_housings":               n_housings,
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
