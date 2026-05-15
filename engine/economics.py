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
    working_weight_kg: float,
    n_vessels: int,
    steel_cost_usd_kg: float,
    erection_usd_per_kg_steel: float,
    labor_usd_per_kg_steel: float,
    piping_usd: float,
    instrumentation_usd: float,
    civil_usd_per_kg_working: float,
    engineering_pct: float,
    contingency_pct: float,
) -> dict:
    """
    Returns CAPEX breakdown for the complete filter station.

    Direct costs: steel + **erection** + **field labor** (both scaled by **dry
    installed steel kg / vessel**) + piping + instrumentation + **civil**
    (scaled by **operating / working weight kg / vessel** — water, media, steel,
    lining in service).

    Indirect: engineering % of direct, then contingency % of (direct + eng).

    ``piping_usd`` and ``instrumentation_usd`` remain **per-vessel lump sums**
    (× ``n_vessels``).
    """
    w_s = max(0.0, float(weight_total_kg))
    w_op = max(0.0, float(working_weight_kg))
    n = max(0, int(n_vessels))

    steel_cost = w_s * steel_cost_usd_kg * n
    erection_usd = max(0.0, float(erection_usd_per_kg_steel)) * w_s * n
    labor_usd = max(0.0, float(labor_usd_per_kg_steel)) * w_s * n
    civil_usd = max(0.0, float(civil_usd_per_kg_working)) * w_op * n
    piping_total = max(0.0, float(piping_usd)) * n
    instr_total = max(0.0, float(instrumentation_usd)) * n

    direct_installed = (
        steel_cost + erection_usd + labor_usd + piping_total + instr_total + civil_usd
    )
    engineering_cost = direct_installed * engineering_pct / 100.0
    contingency_cost = (direct_installed + engineering_cost) * contingency_pct / 100.0
    total_capex = direct_installed + engineering_cost + contingency_cost

    return {
        "steel_cost_usd":         round(steel_cost),
        "erection_usd":           round(erection_usd),
        "labor_usd":              round(labor_usd),
        "piping_usd":             round(piping_total),
        "instrumentation_usd":    round(instr_total),
        "civil_usd":              round(civil_usd),
        "direct_installed_usd":   round(direct_installed),
        "engineering_usd":        round(engineering_cost),
        "contingency_usd":        round(contingency_cost),
        "total_capex_usd":        round(total_capex),
        "capex_per_vessel_usd":   round(total_capex / n) if n else 0,
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
    *,
    energy_kwh_yr_by_component: dict[str, float] | None = None,
) -> dict:
    """
    Returns annual OPEX breakdown (USD/year).

    If ``energy_kwh_yr_by_component`` is provided (filtration / bw_pump / blower annual kWh),
    energy cost uses that **metered-style** total × tariff. Otherwise falls back to
    ``(filtration_power_kw + bw_power_kw + blower_power_kw) × operating_hours`` (legacy;
    misstates intermittent BW loads).
    """
    if energy_kwh_yr_by_component is not None:
        ek = energy_kwh_yr_by_component
        e_f = float(ek.get("filtration", 0.0))
        e_b = float(ek.get("bw_pump", 0.0))
        e_l = float(ek.get("blower", 0.0))
        energy_kwh_yr = e_f + e_b + e_l
        energy_cost_yr = energy_kwh_yr * electricity_tariff
    else:
        total_power_kw = filtration_power_kw + bw_power_kw + blower_power_kw
        energy_kwh_yr = total_power_kw * operating_hours
        energy_cost_yr = energy_kwh_yr * electricity_tariff
        e_f = e_b = e_l = None

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
        "energy_kwh_yr":        round(energy_kwh_yr),
        **(
            {
                "energy_kwh_filtration_yr": round(e_f),
                "energy_kwh_bw_pump_yr": round(e_b),
                "energy_kwh_blower_yr": round(e_l),
            }
            if e_f is not None
            else {}
        ),
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
    *,
    energy_kwh_yr_by_component: dict[str, float] | None = None,
) -> dict:
    """
    Returns lifecycle carbon footprint. Construction CO₂ is one-time;
    operational CO₂ is per year and over the design life.

    If ``energy_kwh_yr_by_component`` is set, operational CO₂ uses Σ kWh × grid intensity
    (aligned with ``opex_annual``). Otherwise legacy ``Σ power × hours``.
    """
    if energy_kwh_yr_by_component is not None:
        ek = energy_kwh_yr_by_component
        energy_kwh_yr = (
            float(ek.get("filtration", 0.0))
            + float(ek.get("bw_pump", 0.0))
            + float(ek.get("blower", 0.0))
        )
        co2_operational_kg_yr = energy_kwh_yr * grid_intensity_kg_kwh
    else:
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

    Benchmarks (stored as SI numeric pairs in return dict; UI formats by unit system):
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
        # SI numeric bounds for UI formatting (metric / imperial labels via fmt_si_range)
        "capex_bench_si":      (15.0, 35.0),
        "opex_bench_si":       (0.02, 0.06),
        "co2_bench_si":        (0.010, 0.025),
        "lcow_bench_si":       (0.03, 0.08),
        "daily_flow_m3d":      round(daily_flow_m3d, 1),
        "annual_flow_m3":      round(annual_flow_m3),
    }


def npv_lifecycle_cost_profile(
    capex_total_usd: float,
    annual_opex_usd: float,
    discount_rate_pct: float,
    design_life_years: int,
) -> dict:
    """Cumulative present value of **costs** (owner cash out; negative NPV).

    Year 0: total installed CAPEX. Years 1…N: constant annual OPEX matching the
    levelized totals from ``opex_annual`` (media/nozzle already spread to USD/yr).

    ``npv_total_usd`` is the sum of discounted flows through the last year
    (same as the final point on the cumulative curve).
    """
    n = max(int(design_life_years), 1)
    i = float(discount_rate_pct) / 100.0
    capex = float(capex_total_usd)
    opex = float(annual_opex_usd)

    flows = [-capex] + [-opex] * n
    years = list(range(n + 1))

    def _df(t: int) -> float:
        if i <= 0.0:
            return 1.0
        return 1.0 / ((1.0 + i) ** t)

    raw_pv: list[float] = []
    for t, cf in enumerate(flows):
        raw_pv.append(cf * _df(t))
    total_pv = sum(raw_pv)
    cumulative = [round(sum(raw_pv[: k + 1]), 2) for k in range(len(raw_pv))]
    annual_discounted_usd = [round(x, 2) for x in raw_pv]

    return {
        "npv_total_usd": round(total_pv, 2),
        "design_life_years": n,
        "discount_rate_pct": float(discount_rate_pct),
        "years": years,
        "cumulative_pv_usd": cumulative,
        "annual_discounted_usd": annual_discounted_usd,
    }


from engine.financial_economics import (  # noqa: E402
    build_econ_financial,
    calculate_cash_flow,
    calculate_discounted_payback,
    calculate_incremental_economics,
    calculate_irr,
    calculate_lifecycle_cost,
    calculate_npv,
    calculate_roi,
    calculate_simple_payback,
    generate_depreciation_schedule,
)
