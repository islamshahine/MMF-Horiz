"""
engine/collector_ext.py
────────────────────────
Extended collector-height check with a user-configurable minimum freeboard.

Wraps engine.backwash.bed_expansion — no calibrated formulas are changed.
The only difference from engine.backwash.collector_check is that the binary-
search threshold and status thresholds honour the caller-supplied
min_freeboard_m instead of the hardcoded 100 mm.
"""

from engine.backwash import bed_expansion

_RHO_WATER_DEF = 1025.0


def collector_check_ext(
    layers: list,
    nozzle_plate_h_m: float,
    collector_h_m: float,
    bw_velocity_m_h: float,
    water_temp_c: float    = 27.0,
    rho_water: float       = _RHO_WATER_DEF,
    min_freeboard_m: float = 0.10,
) -> dict:
    """
    Collector height check with user-specified minimum freeboard.

    Parameters
    ----------
    layers           : Media layer list (same format as bed_expansion)
    nozzle_plate_h_m : Height of nozzle plate from vessel bottom, m
    collector_h_m    : Height of BW outlet collector from vessel bottom, m
    bw_velocity_m_h  : Proposed BW velocity, m/h
    water_temp_c     : BW water temperature, °C
    rho_water        : BW water density, kg/m³
    min_freeboard_m  : Minimum acceptable freeboard, m (default 0.10 = 100 mm).
                       Governs both the binary-search for max_safe_bw_m_h and
                       the WARNING threshold.

    Returns
    -------
    dict — same keys as engine.backwash.collector_check, plus min_freeboard_m.
    """
    exp            = bed_expansion(layers, bw_velocity_m_h, water_temp_c, rho_water)
    total_settled  = exp["total_settled_m"]
    total_expanded = exp["total_expanded_m"]

    expanded_top   = nozzle_plate_h_m + total_expanded
    freeboard      = collector_h_m - expanded_top
    freq_pct       = freeboard / total_settled * 100 if total_settled > 0 else 0.0

    media_loss     = expanded_top >= collector_h_m
    low_freeboard  = freeboard < min_freeboard_m

    # Binary search: highest u_bw that keeps freeboard ≥ min_freeboard_m
    lo, hi = 0.0, 200.0
    for _ in range(40):
        mid      = (lo + hi) / 2
        exp_test = bed_expansion(layers, mid, water_temp_c, rho_water)
        top_test = nozzle_plate_h_m + exp_test["total_expanded_m"]
        if collector_h_m - top_test >= min_freeboard_m:
            lo = mid
        else:
            hi = mid
    max_safe_bw = round(lo, 1)

    if media_loss:
        status = "CRITICAL — media loss risk"
    elif low_freeboard:
        status = f"WARNING — freeboard < {min_freeboard_m * 1000:.0f} mm"
    else:
        status = "OK"

    return {
        "nozzle_plate_h_m":    round(nozzle_plate_h_m, 3),
        "collector_h_m":       round(collector_h_m,     3),
        "settled_top_m":       round(nozzle_plate_h_m + total_settled, 3),
        "expanded_top_m":      round(expanded_top,      3),
        "freeboard_m":         round(freeboard,         3),
        "freeboard_pct":       round(freq_pct,          1),
        "media_loss_risk":     media_loss,
        "max_safe_bw_m_h":    max_safe_bw,
        "proposed_bw_m_h":    bw_velocity_m_h,
        "status":              status,
        "per_layer":           exp["layers"],
        "total_settled_m":     round(total_settled,     3),
        "total_expanded_m":    round(total_expanded,    3),
        "total_expansion_pct": exp["total_expansion_pct"],
        "min_freeboard_m":     round(min_freeboard_m,   3),
    }
