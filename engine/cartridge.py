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
• Design sizing with safety factor (SF):
    n_elements = ceil(Q_design / (q_derated / SF))
    SF = 1.5  for standard (disposable) polymer elements
    SF = 1.2  for CIP systems (SS 316L regenerable elements — cleaning is frequent)
• ΔP model: vendor quadratic  ΔP[mbar] = a·q² + b·q + c
  where q = lpm per element.  Base curves measured on 40" element:
    1 µm absolute : a=0.0002,  b=0.304,  c=−5.539
    5 µm absolute : a=0.0003,  b=0.152,  c=−2.3975
  Other lengths derived via TIE-ratio scaling (k = 4/N_TIE):
    a_N = a_40 × k²,  b_N = b_40 × k,  c_N = c_40
  Direct vendor override: 60" @ 5 µm  (a=0.0002, b=0.1025, c=−6.3865).
• Dirt holding capacity (DHC):
    Polymer (standard) : 30 g/TIE per element (Table 10, reference @ 5 µm)
    SS 316L (CIP)      : 45 g/TIE per element (metal media holds more solids)
    Rating multiplier  : finer absolute ratings → lower effective DHC (tighter media),
      so replacement interval does not invert vs coarser ratings when flow/element drops.
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

SAFETY_FACTOR_STD = 1.5   # standard disposable polymer elements
SAFETY_FACTOR_CIP = 1.2   # CIP / SS 316L regenerable elements (more frequent cleaning)
SAFETY_FACTOR     = SAFETY_FACTOR_STD   # default alias

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
MARKET_ROUNDS                = [1, 3, 5, 7, 12, 18, 21, 28, 36, 52, 75, 100, 160, 200]
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

# ── Dirt holding capacity ─────────────────────────────────────────────────────
DHC_G_PER_TIE        = 30.0   # g/TIE — polymer (standard) — Table 10 (reference @ 5 µm)
DHC_G_PER_TIE_SS316L = 45.0   # g/TIE — SS 316L metal media (higher void volume)

# Finer absolute ratings hold less mass before the same ΔP trip (tighter pleat / less void).
# Without this, sizing gives **more** elements @ 1 µm → **less** flow/element → **longer** life than 10 µm,
# which reverses physical expectation. Multiplier applies to DHC only (same TSS mass balance).
_DHC_RATING_MULT: dict[int, float] = {
    1:  0.52,   # ~tighter media vs 5 µm reference
    5:  1.00,
    10: 1.22,   # coarser → higher DHC; tuned with BASE_FLOW_TIE so life increases 1→5→10 µm
}

# ── Fallback replacement interval when TSS loading is zero (days) ─────────────
# Used only by cartridge_optimise() which has no TSS inputs.
_FREQ_DAYS_FALLBACK: dict = {1: 30, 5: 60, 10: 90}
_FREQ_DAYS_SS316L:   dict = {1: 180, 5: 365, 10: 730}

# ── Maximum practical replacement interval ────────────────────────────────────
_MAX_INTERVAL_DAYS = 5 * 365   # 5 years — cap for near-zero TSS loading

# ── Element unit cost USD — mid-market industrial (2024) ──────────────────────
# Polymer (disposable, pleated)
_COST_USD: dict = {
    ('10"', 1):  55,  ('10"', 5):  42,  ('10"', 10):  32,
    ('20"', 1):  85,  ('20"', 5):  65,  ('20"', 10):  50,
    ('30"', 1): 120,  ('30"', 5):  95,  ('30"', 10):  72,
    ('40"', 1): 160,  ('40"', 5): 125,  ('40"', 10):  95,
    ('50"', 1): 195,  ('50"', 5): 155,  ('50"', 10): 118,
    ('60"', 1): 230,  ('60"', 5): 180,  ('60"', 10): 138,
    ('70"', 1): 265,  ('70"', 5): 210,  ('70"', 10): 160,
}
# SS 316L (regenerable; higher upfront, lower annualised replacement cost)
_COST_USD_SS316L: dict = {
    ('10"', 1):  210,  ('10"', 5):  165,  ('10"', 10):  125,
    ('20"', 1):  360,  ('20"', 5):  280,  ('20"', 10):  210,
    ('30"', 1):  510,  ('30"', 5):  400,  ('30"', 10):  305,
    ('40"', 1):  660,  ('40"', 5):  520,  ('40"', 10):  395,
    ('50"', 1):  820,  ('50"', 5):  645,  ('50"', 10):  490,
    ('60"', 1):  975,  ('60"', 5):  765,  ('60"', 10):  585,
    ('70"', 1): 1130,  ('70"', 5):  890,  ('70"', 10):  675,
}

# Public aliases — used by app.py to build the editable price table
COST_TABLE_POLYMER = _COST_USD
COST_TABLE_SS316L  = _COST_USD_SS316L


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
    """
    Clean-element ΔP in mbar at actual flow q_lpm_element (lpm/element).

    Vendor quadratic overrides have negative intercepts (regression fit over a
    high-flow measurement range).  When the polynomial evaluates ≤ 0 — i.e. the
    operating point is below the calibrated range — fall back to the TIE-scaled
    40" base curve, which is always positive at practical design flows.
    """
    a, b, c = _dp_coeffs(size_label, rating_um)
    result = a * q_lpm_element ** 2 + b * q_lpm_element + c
    if result <= 0 and (size_label, rating_um) in _DP_OVERRIDE:
        ties   = ELEMENT_CATALOGUE[size_label]["ties"]
        k      = 4.0 / ties
        a0, b0, c0 = _DP_BASE_40[rating_um]
        result = a0 * k * k * q_lpm_element ** 2 + b0 * k * q_lpm_element + c0
    return max(0.0, result)


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
    element_size: str        = '40"',
    rating_um: int           = 5,
    mu_cP: float             = 1.0,
    n_elem_per_housing: int  = DEFAULT_ELEMENTS_PER_HOUSING,
    is_CIP_system: bool      = False,
    cf_inlet_tss_mg_l: float = 2.0,
    cf_outlet_tss_mg_l: float = 0.5,
) -> dict:
    """
    Size a cartridge polishing filter bank.

    Parameters
    ----------
    design_flow_m3h     : Total flow to the cartridge station, m³/h
    element_size        : '20"' | '30"' | '40"' | '50"' | '60"' | '70"'
    rating_um           : 1 | 5 | 10  (µm absolute)
    mu_cP               : Feed water dynamic viscosity, cP
    n_elem_per_housing  : Elements per housing vessel (from MARKET_ROUNDS)
    is_CIP_system       : True → SS 316L elements; SF=1.2, higher DHC, SS costs
    cf_inlet_tss_mg_l   : TSS entering the CF (= MMF effluent), mg/L
    cf_outlet_tss_mg_l  : TSS target leaving the CF, mg/L (≤ cf_inlet_tss_mg_l)

    Replacement interval
    --------------------
    Derived from mass balance:
        loading [g/h/element] = (cf_inlet − cf_outlet) [g/m³] × q [m³/h/element]
        interval [h]          = DHC [g] / loading [g/h]
    DHC [g]                 = (g/TIE × ties) × rating multiplier (finer → lower DHC).
    Capped at _MAX_INTERVAL_DAYS. Falls back to rating-based table when loading = 0.

    ΔP profile
    ----------
    Linear from ΔP_clean (BOL) to DP_REPLACEMENT_BAR (EOL = 1.0 bar) as
    cake mass accumulates from 0 to DHC.  Average ΔP = (clean + 1.0) / 2.

    Returns
    -------
    dict — sizing, TSS loading, ΔP profile, DHC, and economics
    """
    if element_size not in ELEMENT_CATALOGUE:
        raise ValueError(f"Unknown element size: {element_size!r}")
    if rating_um not in _DP_BASE_40:
        raise ValueError(f"Unsupported rating: {rating_um} µm")

    cat  = ELEMENT_CATALOGUE[element_size]
    ties = cat["ties"]
    area = cat["area_m2"]

    sf       = SAFETY_FACTOR_CIP if is_CIP_system else SAFETY_FACTOR_STD
    material = "SS 316L" if is_CIP_system else "Polymer"

    cap_visc  = _cap_m3h_element(element_size, rating_um, mu_cP)
    cap_rated = cap_visc / sf

    n_elements       = max(1, math.ceil(design_flow_m3h / cap_rated))
    n_housings       = math.ceil(n_elements / n_elem_per_housing)
    actual_flow_elem = design_flow_m3h / n_elements
    actual_flow_m2   = actual_flow_elem / area
    q_lpm            = actual_flow_elem * 1000.0 / 60.0

    # ── ΔP — clean (BOL) from vendor quadratic ────────────────────────────────
    dp_clean_bar = _dp_mbar(q_lpm, element_size, rating_um) / 1000.0
    # EOL is always the replacement trigger; linear cake progression
    dp_eol_bar   = DP_REPLACEMENT_BAR
    dp_avg_bar   = (dp_clean_bar + dp_eol_bar) / 2.0
    dp_overloaded = dp_clean_bar >= DP_REPLACEMENT_BAR   # element already over-pressured at BOL

    # 5-point ΔP vs accumulated-mass curve (fraction of DHC)
    dhc_per_tie = DHC_G_PER_TIE_SS316L if is_CIP_system else DHC_G_PER_TIE
    dhc_g       = dhc_per_tie * ties * _DHC_RATING_MULT[rating_um]
    dp_curve    = [
        {
            "mass_frac": f,
            "mass_g":    round(f * dhc_g, 1),
            "dp_bar":    round(dp_clean_bar + (dp_eol_bar - dp_clean_bar) * f, 4),
        }
        for f in [0.0, 0.25, 0.50, 0.75, 1.0]
    ]

    # ── TSS loading & replacement interval ───────────────────────────────────
    cf_inlet  = max(0.0, cf_inlet_tss_mg_l)
    cf_outlet = max(0.0, min(cf_outlet_tss_mg_l, cf_inlet))
    tss_removed_mg_l = cf_inlet - cf_outlet           # g/m³ removed by CF
    tss_removal_pct  = (tss_removed_mg_l / cf_inlet * 100.0) if cf_inlet > 0 else 0.0

    # Loading rate per element [g/h] = [g/m³] × [m³/h]
    loading_g_h = tss_removed_mg_l * actual_flow_elem

    if loading_g_h > 1e-9:
        interval_h = min(dhc_g / loading_g_h, _MAX_INTERVAL_DAYS * 24.0)
    else:
        # Zero loading (CF inlet = outlet): fall back to rating-based defaults
        fb = _FREQ_DAYS_SS316L if is_CIP_system else _FREQ_DAYS_FALLBACK
        interval_h = fb[rating_um] * 24.0

    interval_days = interval_h / 24.0
    repl_per_year = 8760.0 / interval_h

    # ── Economics ─────────────────────────────────────────────────────────────
    cost_table  = _COST_USD_SS316L if is_CIP_system else _COST_USD
    cost_each   = cost_table.get((element_size, rating_um), 200 if is_CIP_system else 120)
    annual_cost = n_elements * repl_per_year * cost_each

    return {
        # Inputs
        "design_flow_m3h":          round(design_flow_m3h,     1),
        "element_size":             element_size,
        "element_area_m2":          area,
        "element_ties":             ties,
        "rating_um":                rating_um,
        "mu_cP":                    round(mu_cP,               3),
        "is_CIP_system":            is_CIP_system,
        "element_material":         material,
        # Capacity
        "cap_m3h_element_base":     round(BASE_FLOW_TIE[rating_um] * ties, 3),
        "cap_m3h_element_visc":     round(cap_visc,            3),
        "cap_m3h_element_rated":    round(cap_rated,           3),
        "safety_factor":            sf,
        # Sizing
        "n_elements":               n_elements,
        "n_elem_per_housing":       n_elem_per_housing,
        "n_housings":               n_housings,
        "actual_flow_m3h_element":  round(actual_flow_elem,    3),
        "actual_flow_m3h_m2":       round(actual_flow_m2,      3),
        "q_lpm_element":            round(q_lpm,               1),
        # ΔP
        "dp_clean_bar":             round(dp_clean_bar,        4),
        "dp_dirty_bar":             round(dp_eol_bar,          4),   # alias for report compat.
        "dp_eol_bar":               round(dp_eol_bar,          4),
        "dp_avg_bar":               round(dp_avg_bar,          4),
        "dp_replacement_bar":       DP_REPLACEMENT_BAR,
        "dp_overloaded":            dp_overloaded,
        "dp_curve":                 dp_curve,
        # DHC
        "dhc_g_element":            round(dhc_g,               1),
        # TSS loading
        "cf_inlet_tss_mg_l":        round(cf_inlet,            2),
        "cf_outlet_tss_mg_l":       round(cf_outlet,           2),
        "tss_removed_mg_l":         round(tss_removed_mg_l,    2),
        "tss_removal_pct":          round(tss_removal_pct,     1),
        "loading_g_h_element":      round(loading_g_h,         4),
        # Replacement (mass-balance derived)
        "interval_h":               round(interval_h,          1),
        "replacement_freq_days":    round(interval_days,       1),
        "replacements_per_year":    round(repl_per_year,       2),
        # Economics
        "cost_per_element_usd":     cost_each,
        "annual_cost_usd":          round(annual_cost,         0),
    }


# ── Optimisation across element lengths ───────────────────────────────────────

def cartridge_optimise(
    design_flow_m3h: float,
    rating_um: int      = 5,
    mu_cP: float        = 1.0,
    is_CIP_system: bool = False,
) -> list:
    """
    Compare all standard element lengths to find the most efficient configuration.

    Algorithm (per element length):
      1. n_elements = ceil(Q / cap_rated)  [SF + viscosity derating]
         SF = 1.2 for CIP, 1.5 for standard.
      2. nearest_round = smallest MARKET_ROUND ≥ n_elements (1 housing if fits)
      3. n_housings = ceil(n_elements / nearest_round)

    Returns list of dicts sorted by (n_housings ASC, n_elements ASC).
    The entry with is_recommended=True is the best choice.
    """
    sf          = SAFETY_FACTOR_CIP if is_CIP_system else SAFETY_FACTOR_STD
    dhc_per_tie = DHC_G_PER_TIE_SS316L if is_CIP_system else DHC_G_PER_TIE

    rows = []
    for size_label in ALL_ELEMENT_LENGTHS:
        cat  = ELEMENT_CATALOGUE[size_label]
        ties = cat["ties"]

        cap_rated   = _cap_m3h_element(size_label, rating_um, mu_cP) / sf
        n_elem      = max(1, math.ceil(design_flow_m3h / cap_rated))
        best_round  = _nearest_market_round(n_elem)
        n_housings  = math.ceil(n_elem / best_round)

        q_flow_elem   = design_flow_m3h / n_elem
        q_lpm         = q_flow_elem * 1000.0 / 60.0
        dp_clean_mbar = _dp_mbar(q_lpm, size_label, rating_um)
        dp_eol_mbar   = DP_REPLACEMENT_BAR * 1000.0   # EOL = replacement trigger
        fill_pct      = 100.0 * n_elem / (n_housings * best_round)
        dhc_g         = dhc_per_tie * ties * _DHC_RATING_MULT[rating_um]

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
