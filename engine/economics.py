"""
engine/economics.py
──────────────────
CAPEX, OPEX, carbon footprint and global benchmark functions for the
AQUASIGHT™ MMF Calculator.
"""


def capital_recovery_factor(discount_rate_pct: float, design_life_years: int) -> float:
    """Annualise CAPEX using the standard CRF formula.

    CRF = i(1+i)^n / ((1+i)^n − 1)
    where i = annual discount rate (decimal) and n = design life (years).
    Returns 1/n for zero discount rate (simple payback).
    """
    i = discount_rate_pct / 100.0
    n = int(design_life_years)
    if i <= 0.0 or n <= 0:
        return 1.0 / max(n, 1)
    return i * (1.0 + i) ** n / ((1.0 + i) ** n - 1.0)


def capex_breakdown(
    weight_total_kg: float,
    n_vessels: int,
    steel_cost_usd_kg: float,
    erection_usd: float,
    piping_usd: float,
    instrumentation_usd: float,
    civil_usd: float,
    engineering_pct: float,
    contingency_pct: float,
) -> dict:
    """
    Returns CAPEX breakdown for the complete filter station.

    Direct costs: steel + erection + piping + instrumentation + civil
    Indirect: engineering % of direct, then contingency % of (direct + eng).
    All cost inputs are per-vessel; multiplied by n_vessels internally.
    """
    steel_cost = weight_total_kg * steel_cost_usd_kg * n_vessels
    direct_installed = (
        steel_cost
        + erection_usd * n_vessels
        + piping_usd * n_vessels
        + instrumentation_usd * n_vessels
        + civil_usd * n_vessels
    )
    engineering_cost = direct_installed * engineering_pct / 100.0
    contingency_cost = (direct_installed + engineering_cost) * contingency_pct / 100.0
    total_capex = direct_installed + engineering_cost + contingency_cost

    return {
        "steel_cost_usd":         round(steel_cost),
        "erection_usd":           round(erection_usd * n_vessels),
        "piping_usd":             round(piping_usd * n_vessels),
        "instrumentation_usd":    round(instrumentation_usd * n_vessels),
        "civil_usd":              round(civil_usd * n_vessels),
        "direct_installed_usd":   round(direct_installed),
        "engineering_usd":        round(engineering_cost),
        "contingency_usd":        round(contingency_cost),
        "total_capex_usd":        round(total_capex),
        "capex_per_vessel_usd":   round(total_capex / n_vessels) if n_vessels else 0,
    }


def opex_annual(
    filtration_power_kw: float,
    bw_power_kw: float,
    blower_power_kw: float,
    n_vessels: int,
    electricity_tariff: float,
    operating_hours: float,
    media_inventory_kg_by_type: dict,
    media_costs_by_type: dict,
    media_interval_years: float,
    n_strainer_nozzles: int,
    nozzle_cost_usd: float,
    nozzle_interval_years: float,
    labour_usd_per_filter_year: float,
    n_filters_total: int,
    chemical_cost_usd_m3: float,
    total_flow_m3h: float,
) -> dict:
    """
    Returns annual OPEX breakdown (USD/year).
    """
    total_power_kw = filtration_power_kw + bw_power_kw + blower_power_kw
    energy_kwh_yr  = total_power_kw * operating_hours
    energy_cost_yr = energy_kwh_yr * electricity_tariff

    media_replace_cost_yr = 0.0
    media_detail: dict = {}
    for mtype, mass_kg in media_inventory_kg_by_type.items():
        unit_usd_kg = media_costs_by_type.get(mtype, 0.0)
        cost_yr = (mass_kg * unit_usd_kg) / max(media_interval_years, 1.0)
        media_replace_cost_yr += cost_yr
        media_detail[mtype] = round(cost_yr)

    nozzle_cost_yr = (n_strainer_nozzles * nozzle_cost_usd) / max(nozzle_interval_years, 1.0)
    labour_cost_yr = labour_usd_per_filter_year * n_filters_total

    annual_flow_m3   = total_flow_m3h * operating_hours
    chemical_cost_yr = chemical_cost_usd_m3 * annual_flow_m3

    total_opex = (energy_cost_yr + media_replace_cost_yr
                  + nozzle_cost_yr + labour_cost_yr + chemical_cost_yr)

    return {
        "energy_cost_usd_yr":   round(energy_cost_yr),
        "media_cost_usd_yr":    round(media_replace_cost_yr),
        "media_detail":         media_detail,
        "nozzle_cost_usd_yr":   round(nozzle_cost_yr),
        "labour_cost_usd_yr":   round(labour_cost_yr),
        "chemical_cost_usd_yr": round(chemical_cost_yr),
        "total_opex_usd_yr":    round(total_opex),
        "opex_per_m3_usd":      round(total_opex / max(annual_flow_m3, 1.0), 4),
        "annual_flow_m3":       round(annual_flow_m3),
    }


def carbon_footprint(
    filtration_power_kw: float,
    bw_power_kw: float,
    blower_power_kw: float,
    operating_hours: float,
    grid_intensity_kg_kwh: float,
    weight_steel_kg: float,
    steel_carbon_kg_kg: float,
    weight_concrete_kg: float,
    concrete_carbon_kg_kg: float,
    media_mass_by_type_kg: dict,
    media_carbon_by_type: dict,
    design_life_years: int,
    total_flow_m3h: float,
) -> dict:
    """
    Returns lifecycle carbon footprint. Construction CO₂ is one-time;
    operational CO₂ is per year and over the design life.
    """
    total_power_kw = filtration_power_kw + bw_power_kw + blower_power_kw
    co2_operational_kg_yr = total_power_kw * operating_hours * grid_intensity_kg_kwh

    co2_steel_kg    = weight_steel_kg * steel_carbon_kg_kg
    co2_concrete_kg = weight_concrete_kg * concrete_carbon_kg_kg
    co2_media_kg    = sum(mass * media_carbon_by_type.get(mtype, 0.0)
                          for mtype, mass in media_mass_by_type_kg.items())
    co2_construction = co2_steel_kg + co2_concrete_kg + co2_media_kg

    co2_lifecycle_kg = co2_construction + co2_operational_kg_yr * design_life_years

    annual_flow_m3 = total_flow_m3h * operating_hours
    life_flow_m3   = annual_flow_m3 * design_life_years

    return {
        "co2_operational_kg_yr":  round(co2_operational_kg_yr),
        "co2_construction_kg":    round(co2_construction),
        "co2_steel_kg":           round(co2_steel_kg),
        "co2_concrete_kg":        round(co2_concrete_kg),
        "co2_media_kg":           round(co2_media_kg),
        "co2_lifecycle_kg":       round(co2_lifecycle_kg),
        "co2_per_m3_operational": round(co2_operational_kg_yr / max(annual_flow_m3, 1.0), 4),
        "co2_per_m3_lifecycle":   round(co2_lifecycle_kg / max(life_flow_m3, 1.0), 4),
        "annual_flow_m3":         round(annual_flow_m3),
        "design_life_years":      design_life_years,
    }


def global_benchmark_comparison(
    capex_total_usd: float,
    opex_usd_year: float,
    total_flow_m3h: float,
    n_filters: int,
    design_life_years: int,
    co2_per_m3: float,
    electricity_tariff: float,
    operating_hours: float,
    discount_rate_pct: float = 5.0,
) -> dict:
    """
    Compare project metrics against global benchmarks for horizontal MMF
    (SWRO / brackish pre-treatment, Middle East / Mediterranean basis).

    Benchmarks:
      CAPEX:  15–35 USD/m³/d capacity
      OPEX:   0.02–0.06 USD/m³ treated
      Carbon: 0.010–0.025 kgCO₂/m³ (operational only)
      LCOW:   0.03–0.08 USD/m³

    Traffic light: 🟢 within range · 🟡 borderline · 🔴 outside range
    """
    annual_flow_m3 = total_flow_m3h * operating_hours
    daily_flow_m3d = total_flow_m3h * 24.0

    capex_per_m3d = capex_total_usd / max(daily_flow_m3d, 1.0)
    opex_per_m3   = opex_usd_year   / max(annual_flow_m3, 1.0)

    crf  = capital_recovery_factor(discount_rate_pct, design_life_years)
    lcow = (capex_total_usd * crf + opex_usd_year) / max(annual_flow_m3, 1.0)

    def _light(val, lo, hi):
        if val <= lo:
            return "🟢"
        if val <= hi:
            return "🟡"
        return "🔴"

    return {
        "capex_per_m3d":       round(capex_per_m3d, 2),
        "opex_per_m3":         round(opex_per_m3, 4),
        "lcow":                round(lcow, 4),
        "crf":                 round(crf, 6),
        "co2_per_m3":          round(co2_per_m3, 4),
        "capex_status":        _light(capex_per_m3d, 15, 35),
        "opex_status":         _light(opex_per_m3,   0.02, 0.06),
        "carbon_status":       _light(co2_per_m3,    0.010, 0.025),
        "lcow_status":         _light(lcow,          0.03, 0.08),
        "capex_benchmark":     "15–35 USD/m³/d",
        "opex_benchmark":      "0.02–0.06 USD/m³",
        "carbon_benchmark":    "0.010–0.025 kgCO₂/m³",
        "lcow_benchmark":      "0.03–0.08 USD/m³",
        "daily_flow_m3d":      round(daily_flow_m3d, 1),
        "annual_flow_m3":      round(annual_flow_m3),
    }
