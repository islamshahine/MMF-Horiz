"""
engine/water.py
───────────────
Water and seawater physical properties.

Correlations
------------
Density  : Millero & Poisson (1981) — UNESCO, valid 0–40°C, 0–42 ppt
Viscosity: Sharqawy, Lienhard & Zubair (2010), valid 0–180°C, 0–150 g/kg

Salinity conventions
--------------------
The app works in g/kg (= ppt) practical salinity.
Conversion helpers for TDS (mg/L) are provided.
Typical values:
  Fresh water        :  0 ppt
  Brackish           :  1–10 ppt
  Seawater           : 35 ppt
  RO reject (SWRO)   : 60–70 ppt
  RO reject (BWRO)   : 5–20 ppt
"""

import math


# ── Default scenario presets ────────────────────────────────────────────────
FEED_PRESETS = {
    "Fresh water (0 ppt)":       {"salinity_ppt": 0.0,  "temp_c": 25.0},
    "Brackish (5 ppt)":          {"salinity_ppt": 5.0,  "temp_c": 25.0},
    "Seawater (35 ppt)":         {"salinity_ppt": 35.0, "temp_c": 27.0},
    "Warm seawater (35 ppt)":    {"salinity_ppt": 35.0, "temp_c": 32.0},
    "Custom":                    {"salinity_ppt": 35.0, "temp_c": 27.0},
}

BW_PRESETS = {
    "Same as feed":              None,   # resolved in app
    "Fresh water (0 ppt)":       {"salinity_ppt": 0.0,  "temp_c": 25.0},
    "SWRO reject (~65 ppt)":     {"salinity_ppt": 65.0, "temp_c": 29.0},
    "BWRO reject (~15 ppt)":     {"salinity_ppt": 15.0, "temp_c": 27.0},
    "Custom":                    {"salinity_ppt": 35.0, "temp_c": 27.0},
}


def water_properties(temp_c: float, salinity_ppt: float) -> dict:
    """
    Density and dynamic viscosity of water / seawater.

    Parameters
    ----------
    temp_c       : Temperature, °C  (0–40)
    salinity_ppt : Salinity, g/kg = ppt  (0–70)

    Returns
    -------
    dict:
        temp_c           input temperature
        salinity_ppt     input salinity
        density_kg_m3    kg/m³
        viscosity_pa_s   Pa·s
        viscosity_cp     cP  (= mPa·s)
        tds_mg_l         approx. TDS in mg/L  (= ppt × density)
    """
    T = float(temp_c)
    S = float(salinity_ppt)
    S = max(0.0, min(S, 70.0))   # clamp to valid range
    T = max(0.0, min(T, 60.0))

    # Pure water density (Kell 1975)
    rho_w = (999.842594
             + 6.793952e-2  * T
             - 9.095290e-3  * T**2
             + 1.001685e-4  * T**3
             - 1.120083e-6  * T**4
             + 6.536332e-9  * T**5)

    # Seawater density correction (Millero & Poisson 1981)
    A = (8.24493e-1 - 4.0899e-3*T + 7.6438e-5*T**2
         - 8.2467e-7*T**3 + 5.3875e-9*T**4)
    B = -5.72466e-3 + 1.0227e-4*T - 1.6546e-6*T**2
    C =  4.8314e-4
    rho = rho_w + A*S + B*S**1.5 + C*S**2

    # Pure water viscosity (Korson et al.)
    mu_w = 4.2844e-5 + 1.0 / (0.157 * (T + 64.993)**2 - 91.296)

    # Seawater viscosity correction (Sharqawy et al. 2010)
    s = S / 1000.0   # dimensionless mass fraction
    A_v = 1.541 + 1.998e-2*T - 9.52e-5*T**2
    B_v = 7.974 - 7.561e-2*T + 4.724e-4*T**2
    mu  = mu_w * (1.0 + A_v*s + B_v*s**2)

    return {
        "temp_c":          round(T,   2),
        "salinity_ppt":    round(S,   2),
        "density_kg_m3":   round(rho, 3),
        "viscosity_pa_s":  round(mu,  7),
        "viscosity_cp":    round(mu * 1000, 4),
        "tds_mg_l":        round(S * rho,   1),
    }


def three_scenario_properties(
    temp_min_c: float, temp_avg_c: float, temp_max_c: float,
    sal_min_ppt: float, sal_avg_ppt: float, sal_max_ppt: float,
) -> dict:
    """
    Compute water properties for three operating scenarios.

    Worst-case for density  : max salinity, min temperature (densest → heaviest loads)
    Worst-case for viscosity: max salinity, min temperature (highest viscosity → max ΔP)
    Design case             : average salinity, average temperature

    Returns
    -------
    dict with keys 'min', 'avg', 'max', each a water_properties dict.
    Also includes 'design' (= avg scenario) for use in calculations.
    """
    scenarios = {
        "min": water_properties(temp_min_c, sal_min_ppt),
        "avg": water_properties(temp_avg_c, sal_avg_ppt),
        "max": water_properties(temp_max_c, sal_max_ppt),
    }
    scenarios["design"] = scenarios["avg"]
    return scenarios