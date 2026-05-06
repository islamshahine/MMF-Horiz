"""
engine/cartridge.py
───────────────────
Cartridge (polishing) filter sizing — 2.5" OD High-Flow Z pleated elements.

Sizing basis
────────────
• TIE (Ten Inch Equivalent): length normalisation unit.  N" = N/10 TIE.
• Flow capacity (at 1 cP base viscosity, Sea Water basis — Table 9):
    q_cap_m3h_element = BASE_FLOW_TIE[rating_um] × ties
• Viscosity derating (seawater typically 1.0–1.8 cP):
    q_derated = q_cap_m3h_element / mu_cP
• Design sizing with 1.5× safety factor:
    n_elements = ceil(Q_design / (q_derated / SAFETY_FACTOR))
• ΔP model: vendor quadratic  ΔP[mbar] = a·q² + b·q + c
  where q = lpm per element.  Base curves measured on 40" element:
    1 µm absolute : a=0.0002,  b=0.304,  c=−5.539
    5 µm absolute : a=0.0003,  b=0.152,  c=−2.3975
  Other lengths derived via TIE-ratio scaling (k = 4/N_TIE):
    a_N = a_40 × k²,  b_N = b_40 × k,  c_N = c_40
  Direct vendor override: 60" @ 5 µm  (a=0.0002, b=0.1025, c=−6.3865).
• Dirt holding capacity (DHC): 30 g/TIE per element (Table 10, absolute).
• End-of-life trigger: ΔP ≥ 1.0 bar (vendor range 0.69–1.0 bar).
• Optimisation: iterate all standard element lengths; map n_elements to nearest
  MARKET_ROUND ≥ n_elements; fewest housings = recommended configuration.
"""

import math

# ── Flow capacity base: m³/h per TIE at 1 cP (Table 9 — Sea Water) ──────────
BASE_FLOW_TIE: dict = {
    1:  0.68,   # m³/h / TIE @ 1 µm absolute (conservative vs 5 µm)
    5:  0.75,   # m³/h / TIE @ 5 µm absolute — Table 9 Sea Water
    10: 0.90,   # m³/h / TIE @ 10 µm — estimated ~20 % above 5 µm
}

SAFETY_FACTOR = 1.5   # applied to capacity when computing n_elements

# ── Element catalogue (all 2.5" / 63.5 mm OD pleated) ───────────────────────
ELEMENT_CATALOGUE: dict = {
    '10"': {"ties": 1, "area_m2": 0.20},
    '20"': {"ties": 2, "area_m2": 0.37},
    '30"': {"ties": 3, "area_m2": 0.56},
    '40"': {"ties": 4, "area_m2": 0.74},
    '50"': {"ties": 5, "area_m2": 0.93},
    '60"': {"ties": 6, "area_m2": 1.10},
    '70"': {"ties": 7, "area_m2": 1.28},
}

# User-selectable lengths in sidebar (10" excluded — impractically small for plant scale)
ELEMENT_SIZE_LABELS  = ['20"', '30"', '40"', '50"', '60"', '70"']
# All lengths used in the optimisation comparison table
ALL_ELEMENT_LENGTHS  = ['10"', '20"', '30"', '40"', '50"', '60"', '70"']

RATING_UM_OPTIONS    = [1, 5, 10]

# ── Market housing rounds (elements per housing, standard catalogue sizes) ────
MARKET_ROUNDS                = [1, 3, 5, 7, 12, 18, 21, 28, 36, 52, 75, 100]
DEFAULT_ELEMENTS_PER_HOUSING = 36
HOUSING_CAPACITY_OPTIONS     = MARKET_ROUNDS   # alias used in app.py selectors

# ── Vendor ΔP quadratic base — measured on 40" element ───────────────────────
# Y[mbar] = A·x² + B·x + C,   x = lpm per element
_DP_BASE_40: dict = {
    1:  (0.0002,  0.304,  -5.539),    # 40" 1 µm — vendor datasheet
    5:  (0.0003,  0.152,  -2.3975),   # 40" 5 µm — vendor datasheet
    10: (0.00015, 0.080,  -1.200),    # 40" 10 µm — estimated
}

# Direct vendor overrides for specific (size, rating_um) pairs
_DP_OVERRIDE: dict = {
    ('60"', 5): (0.0002, 0.1025, -6.3865),   # 60" 5 µm — vendor datasheet
}

DP_REPLACEMENT_BAR = 1.00   # EOL ΔP trigger (vendor range 0.69–1.00 bar)
_DP_DIRTY_FACTOR   = 2.0    # EOL / clean ratio (approximate)

# ── Dirt holding capacity ─────────────────────────────────────────────────────
DHC_G_PER_TIE = 30.0   # g per TIE per element (absolute rating — Table 10)

# ── Replacement frequency — indicative (days) ─────────────────────────────────
_FREQ_DAYS: dict = {1: 30, 5: 60, 10: 90}

# ── Element unit cost USD — mid-market industrial (2024) ──────────────────────
_COST_USD: dict = {
    ('10"', 1):  55,  ('10"', 5):  42,  ('10"', 10):  32,
    ('20"', 1):  85,  ('20"', 5):  65,  ('20"', 10):  50,
    ('30"', 1): 120,  ('30"', 5):  95,  ('30"', 10):  72,
    ('40"', 1): 160,  ('40"', 5): 125,  ('40"', 10):  95,
    ('50"', 1): 195,  ('50"', 5): 155,  ('50"', 10): 118,
    ('60"', 1): 230,  ('60"', 5): 180,  ('60"', 10): 138,
    ('70"', 1): 265,  ('70"', 5): 210,  ('70"', 10): 160,
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _dp_coeffs(size_label: str, rating_um: int) -> tuple:
    """
    Return (a, b, c) for Y[mbar] = a·x² + b·x + c  (x in lpm/element).

    Uses vendor override if available; otherwise derives from the 40" base
    curves by TIE-ratio scaling:  k = 4/N_TIE → a = a40·k², b = b40·k.
    """
    if (size_label, rating_um) in _DP_OVERRIDE:
        return _DP_OVERRIDE[(size_label, rating_um)]
    ties     = ELEMENT_CATALOGUE[size_label]["ties"]
    k        = 4.0 / ties           # 40" = 4 TIE reference
    a0, b0, c0 = _DP_BASE_40[rating_um]
    return a0 * k * k, b0 * k, c0


def _dp_mbar(q_lpm_element: float, size_label: str, rating_um: int) -> float:
    """Clean-element ΔP in mbar at actual flow q_lpm_element (lpm/element)."""
    a, b, c = _dp_coeffs(size_label, rating_um)
    return max(0.0, a * q_lpm_element ** 2 + b * q_lpm_element + c)


def _cap_m3h_element(size_label: str, rating_um: int, mu_cP: float) -> float:
    """
    Viscosity-derated flow capacity per element (m³/h).
    Safety factor NOT applied here — caller divides by SAFETY_FACTOR when sizing.
    """
    ties = ELEMENT_CATALOGUE[size_label]["ties"]
    return BASE_FLOW_TIE[rating_um] * ties / max(mu_cP, 0.1)


def _nearest_market_round(n_elements: int) -> int:
    """
    Smallest MARKET_ROUND ≥ n_elements (→ single housing when possible).
    Falls back to 100 (largest round) when n_elements exceeds all rounds.
    """
    fits = [r for r in MARKET_ROUNDS if r >= n_elements]
    return min(fits) if fits else max(MARKET_ROUNDS)


# ── Core sizing function ──────────────────────────────────────────────────────

def cartridge_design(
    design_flow_m3h: float,
    element_size: str       = '40"',
    rating_um: int          = 5,
    mu_cP: float            = 1.0,
    n_elem_per_housing: int = DEFAULT_ELEMENTS_PER_HOUSING,
) -> dict:
    """
    Size a cartridge polishing filter bank.

    Parameters
    ----------
    design_flow_m3h    : Total flow to the cartridge station, m³/h
    element_size       : '20"' | '30"' | '40"' | '50"' | '60"' | '70"'
    rating_um          : 1 | 5 | 10  (µm absolute)
    mu_cP              : Feed water dynamic viscosity, cP (1.0 cP = water @20 °C)
    n_elem_per_housing : Elements per housing vessel (choose from MARKET_ROUNDS)

    Returns
    -------
    dict — sizing, ΔP, DHC, and economics results
    """
    if element_size not in ELEMENT_CATALOGUE:
        raise ValueError(f"Unknown element size: {element_size!r}")
    if rating_um not in _DP_BASE_40:
        raise ValueError(f"Unsupported rating: {rating_um} µm")

    cat  = ELEMENT_CATALOGUE[element_size]
    ties = cat["ties"]
    area = cat["area_m2"]

    cap_visc  = _cap_m3h_element(element_size, rating_um, mu_cP)
    cap_rated = cap_visc / SAFETY_FACTOR

    n_elements       = max(1, math.ceil(design_flow_m3h / cap_rated))
    n_housings       = math.ceil(n_elements / n_elem_per_housing)
    actual_flow_elem = design_flow_m3h / n_elements
    actual_flow_m2   = actual_flow_elem / area
    q_lpm            = actual_flow_elem * 1000.0 / 60.0

    dp_clean_mbar = _dp_mbar(q_lpm, element_size, rating_um)
    dp_eol_mbar   = dp_clean_mbar * _DP_DIRTY_FACTOR
    dp_clean_bar  = dp_clean_mbar / 1000.0
    dp_eol_bar    = dp_eol_mbar   / 1000.0

    dhc_g = DHC_G_PER_TIE * ties

    freq_days     = _FREQ_DAYS[rating_um]
    repl_per_year = 365.0 / freq_days
    cost_each     = _COST_USD.get((element_size, rating_um), 120)
    annual_cost   = n_elements * repl_per_year * cost_each

    return {
        # Inputs
        "design_flow_m3h":          round(design_flow_m3h,   1),
        "element_size":             element_size,
        "element_area_m2":          area,
        "element_ties":             ties,
        "rating_um":                rating_um,
        "mu_cP":                    round(mu_cP,             3),
        # Capacity
        "cap_m3h_element_base":     round(BASE_FLOW_TIE[rating_um] * ties, 3),
        "cap_m3h_element_visc":     round(cap_visc,          3),
        "cap_m3h_element_rated":    round(cap_rated,         3),
        "safety_factor":            SAFETY_FACTOR,
        # Sizing
        "n_elements":               n_elements,
        "n_elem_per_housing":       n_elem_per_housing,
        "n_housings":               n_housings,
        "actual_flow_m3h_element":  round(actual_flow_elem,  3),
        "actual_flow_m3h_m2":       round(actual_flow_m2,    3),
        "q_lpm_element":            round(q_lpm,             1),
        # ΔP
        "dp_clean_bar":             round(dp_clean_bar,      4),
        "dp_dirty_bar":             round(dp_eol_bar,        4),
        "dp_eol_bar":               round(dp_eol_bar,        4),
        "dp_replacement_bar":       DP_REPLACEMENT_BAR,
        # DHC
        "dhc_g_element":            round(dhc_g,             1),
        # Economics
        "replacement_freq_days":    freq_days,
        "replacements_per_year":    round(repl_per_year,     1),
        "cost_per_element_usd":     cost_each,
        "annual_cost_usd":          round(annual_cost,       0),
    }


# ── Optimisation across element lengths ───────────────────────────────────────

def cartridge_optimise(
    design_flow_m3h: float,
    rating_um: int = 5,
    mu_cP: float   = 1.0,
) -> list:
    """
    Compare all standard element lengths to find the most efficient configuration.

    Algorithm (per element length):
      1. n_elements = ceil(Q / cap_rated)  [1.5× SF + viscosity derating]
      2. nearest_round = smallest MARKET_ROUND ≥ n_elements (1 housing if fits)
      3. n_housings = ceil(n_elements / nearest_round)

    Returns list of dicts sorted by (n_housings ASC, n_elements ASC).
    The entry with is_recommended=True is the best choice.
    """
    rows = []
    for size_label in ALL_ELEMENT_LENGTHS:
        cat  = ELEMENT_CATALOGUE[size_label]
        ties = cat["ties"]
        area = cat["area_m2"]

        cap_rated   = _cap_m3h_element(size_label, rating_um, mu_cP) / SAFETY_FACTOR
        n_elem      = max(1, math.ceil(design_flow_m3h / cap_rated))
        best_round  = _nearest_market_round(n_elem)
        n_housings  = math.ceil(n_elem / best_round)

        q_flow_elem   = design_flow_m3h / n_elem
        q_lpm         = q_flow_elem * 1000.0 / 60.0
        dp_clean_mbar = _dp_mbar(q_lpm, size_label, rating_um)
        dp_eol_mbar   = dp_clean_mbar * _DP_DIRTY_FACTOR
        fill_pct      = 100.0 * n_elem / (n_housings * best_round)
        dhc_g         = DHC_G_PER_TIE * ties

        rows.append({
            "size":           size_label,
            "ties":           ties,
            "cap_m3h_elem":   round(cap_rated,              3),
            "n_elements":     n_elem,
            "market_round":   best_round,
            "n_housings":     n_housings,
            "fill_pct":       round(fill_pct,               1),
            "q_lpm_element":  round(q_lpm,                  1),
            "dp_clean_bar":   round(dp_clean_mbar / 1000.0, 4),
            "dp_eol_bar":     round(dp_eol_mbar   / 1000.0, 4),
            "dhc_g":          round(dhc_g,                  1),
            "is_recommended": False,
        })

    rows.sort(key=lambda r: (r["n_housings"], r["n_elements"]))

    # Recommend: fewest housings; tie-break = fewest elements (shorter → cheaper ops)
    min_h = rows[0]["n_housings"]
    min_e = min(r["n_elements"] for r in rows if r["n_housings"] == min_h)
    for r in rows:
        r["is_recommended"] = (r["n_housings"] == min_h and r["n_elements"] == min_e)

    return rows
