"""Link cycle-duration uncertainty bands to LCOW / OPEX envelopes (deterministic)."""
from __future__ import annotations

import math
from typing import Any

from engine.economics import capital_recovery_factor


def _finite_pos(h: float) -> bool:
    return math.isfinite(h) and h > 1e-6


def _bw_energy_scale(expected_h: float, corner_h: float) -> float:
    """Scale BW pump + blower annual energy vs expected cycle length."""
    if not (_finite_pos(expected_h) and _finite_pos(corner_h)):
        return 1.0
    return float(expected_h) / float(corner_h)


def lcow_envelope_from_cycle_uncertainty(
    *,
    capex_total_usd: float,
    econ_opex: dict[str, Any],
    cycle_uncertainty_n: dict[str, Any],
    discount_rate_pct: float,
    design_life_years: int,
    annual_flow_m3: float,
    electricity_tariff: float | None = None,
) -> dict[str, Any]:
    """
    Derive optimistic / expected / conservative LCOW from the N-scenario cycle band.

    CAPEX is unchanged. Non-energy OPEX is unchanged. BW pump and blower **energy cost**
    scales with implied backwash frequency ``∝ 1 / cycle_hours`` relative to the expected
    cycle at design TSS.
    """
    annual_flow_m3 = max(float(annual_flow_m3), 1.0)
    crf = capital_recovery_factor(float(discount_rate_pct), int(design_life_years))
    capex_ann = float(capex_total_usd) * crf

    opt_h = float(cycle_uncertainty_n.get("cycle_optimistic_h", 0) or 0)
    exp_h = float(cycle_uncertainty_n.get("cycle_expected_h", 0) or 0)
    con_h = float(cycle_uncertainty_n.get("cycle_conservative_h", 0) or 0)

    total_opex = float(econ_opex.get("total_opex_usd_yr", 0) or 0)
    energy_cost = float(econ_opex.get("energy_cost_usd_yr", 0) or 0)
    non_energy = max(0.0, total_opex - energy_cost)

    tariff = float(
        electricity_tariff
        if electricity_tariff is not None
        else (energy_cost / max(float(econ_opex.get("energy_kwh_yr", 0) or 0), 1.0))
    )

    e_f = float(econ_opex.get("energy_kwh_filtration_yr", 0) or 0)
    e_b = float(econ_opex.get("energy_kwh_bw_pump_yr", 0) or 0)
    e_l = float(econ_opex.get("energy_kwh_blower_yr", 0) or 0)
    if e_f == 0 and e_b == 0 and e_l == 0:
        e_tot = float(econ_opex.get("energy_kwh_yr", 0) or 0)
        e_f = e_tot * 0.55
        e_b = e_tot * 0.30
        e_l = e_tot * 0.15

    cost_f = e_f * tariff
    cost_b = e_b * tariff
    cost_l = e_l * tariff
    bw_cost = cost_b + cost_l

    scale_exp = 1.0
    scale_opt = _bw_energy_scale(exp_h, opt_h)
    scale_con = _bw_energy_scale(exp_h, con_h)

    def _opex_for_scale(s: float) -> float:
        return non_energy + cost_f + bw_cost * s

    def _lcow(opex_yr: float) -> float:
        return (capex_ann + opex_yr) / annual_flow_m3

    opex_exp = _opex_for_scale(scale_exp)
    opex_opt = _opex_for_scale(scale_opt)
    opex_con = _opex_for_scale(scale_con)
    lcow_exp = _lcow(opex_exp)
    lcow_opt = _lcow(opex_opt)
    lcow_con = _lcow(opex_con)

    spread = lcow_con - lcow_opt
    spread_pct = (spread / lcow_exp * 100.0) if lcow_exp > 1e-12 else 0.0

    return {
        "method": "cycle_band_scales_bw_pump_and_blower_energy",
        "design_tss_mg_l": cycle_uncertainty_n.get("design_tss_mg_l"),
        "cycle_optimistic_h": round(opt_h, 2) if math.isfinite(opt_h) else None,
        "cycle_expected_h": round(exp_h, 2) if math.isfinite(exp_h) else None,
        "cycle_conservative_h": round(con_h, 2) if math.isfinite(con_h) else None,
        "bw_energy_scale_optimistic": round(scale_opt, 4),
        "bw_energy_scale_conservative": round(scale_con, 4),
        "opex_optimistic_usd_yr": round(opex_opt, 0),
        "opex_expected_usd_yr": round(opex_exp, 0),
        "opex_conservative_usd_yr": round(opex_con, 0),
        "lcow_optimistic_usd_m3": round(lcow_opt, 4),
        "lcow_expected_usd_m3": round(lcow_exp, 4),
        "lcow_conservative_usd_m3": round(lcow_con, 4),
        "lcow_spread_usd_m3": round(spread, 4),
        "lcow_spread_pct": round(spread_pct, 1),
        "stability": cycle_uncertainty_n.get("stability"),
        "note": (
            "Longer filtration cycle (optimistic) → fewer backwashes → lower BW energy OPEX. "
            "CAPEX and media/labour/chemical OPEX are held at the base case."
        ),
    }
