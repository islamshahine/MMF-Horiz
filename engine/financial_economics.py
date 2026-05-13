"""Lifecycle financial & techno-economic analysis (engineering-linked cash flows).

Cash flows are built from CAPEX, metered-style OPEX components, replacement events,
escalation, optional benefit stream (e.g. avoided cost / contract water value), tax,
and salvage. All structures are JSON-serialisable (no callables, no DataFrames).
"""
from __future__ import annotations

import math
from typing import Any


def generate_depreciation_schedule(
    capex_depreciable_usd: float,
    depreciation_years: int,
    salvage_value_usd: float,
    method: str,
) -> list[dict[str, Any]]:
    """Yearly depreciation and book value (straight-line or double-declining balance)."""
    n = max(int(depreciation_years), 1)
    capex = float(capex_depreciable_usd)
    salvage = max(float(salvage_value_usd), 0.0)
    basis = max(capex - salvage, 0.0)
    m = (method or "straight_line").lower().replace("-", "_").replace(" ", "_")
    rows: list[dict[str, Any]] = []
    if basis <= 1e-6:
        for y in range(1, n + 1):
            rows.append({"year": y, "depreciation_usd": 0.0, "book_value_usd": round(capex, 2)})
        return rows

    book = capex
    if m in ("straight_line", "straightline", "sl"):
        ann = basis / n
        for y in range(1, n + 1):
            dep = min(ann, max(book - salvage, 0.0))
            book -= dep
            rows.append({"year": y, "depreciation_usd": round(dep, 2), "book_value_usd": round(book, 2)})
        return rows

    # Double declining balance (default for declining_balance / ddb)
    rate = 2.0 / n
    for y in range(1, n + 1):
        allowable = max(book - salvage, 0.0)
        dep = min(book * rate, allowable)
        book -= dep
        rows.append({"year": y, "depreciation_usd": round(dep, 2), "book_value_usd": round(book, 2)})
    return rows


def calculate_npv(discount_rate_pct: float, cash_flows: list[float]) -> float:
    i = float(discount_rate_pct) / 100.0
    s = 0.0
    for t, cf in enumerate(cash_flows):
        if abs(i) < 1e-15:
            s += float(cf)
        else:
            s += float(cf) / ((1.0 + i) ** t)
    return round(s, 2)


def calculate_irr(cash_flows: list[float]) -> float | None:
    """IRR as **annual %** (e.g. 12.5 means 12.5 %/yr). Bisection on NPV(r)=0."""
    flows = [float(x) for x in cash_flows]
    if len(flows) < 2:
        return None

    def npv_r(r: float) -> float:
        rr = max(r, -0.9999)
        return sum(cf / ((1.0 + rr) ** t) for t, cf in enumerate(flows))

    lo, hi = -0.85, 3.0
    f_lo, f_hi = npv_r(lo), npv_r(hi)
    if f_lo * f_hi > 0:
        hi = 20.0
        f_hi = npv_r(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(120):
        mid = 0.5 * (lo + hi)
        f_mid = npv_r(mid)
        if abs(f_mid) < 1e-8 * (1.0 + abs(flows[0])):
            return round(mid * 100.0, 4)
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return round(0.5 * (lo + hi) * 100.0, 4)


def calculate_simple_payback(cash_flows: list[float]) -> float | None:
    """Years until cumulative **undiscounted** net cash flow reaches ≥ 0 (linear intra-year)."""
    flows = [float(x) for x in cash_flows]
    if not flows or flows[0] >= 0:
        return 0.0 if flows and flows[0] >= 0 else None
    cum = 0.0
    for t, cf in enumerate(flows):
        prev = cum
        cum += cf
        if cum >= 0 and t > 0:
            if abs(cf) < 1e-12:
                return float(t)
            frac = max(0.0, min(1.0, (0.0 - prev) / cf))
            return round(float(t - 1) + frac, 3)
    return None


def calculate_discounted_payback(discount_rate_pct: float, cash_flows: list[float]) -> float | None:
    """Years until cumulative discounted net ≥ 0."""
    i = float(discount_rate_pct) / 100.0
    flows = [float(x) for x in cash_flows]
    cum = 0.0
    for t, cf in enumerate(flows):
        prev = cum
        pv = cf if abs(i) < 1e-15 else cf / ((1.0 + i) ** t)
        cum += pv
        if cum >= 0 and t > 0:
            if abs(pv) < 1e-12:
                return float(t)
            frac = max(0.0, min(1.0, (0.0 - prev) / pv))
            return round(float(t - 1) + frac, 3)
    return None


def calculate_roi(cash_flows: list[float], capex_magnitude_usd: float) -> float | None:
    """Lifecycle ROI % ≈ (sum of net flows after year 0) / |initial CAPEX| × 100."""
    capex = abs(float(capex_magnitude_usd))
    if capex < 1e-9:
        return None
    tail = sum(float(x) for x in cash_flows[1:])
    return round(tail / capex * 100.0, 2)


def calculate_lifecycle_cost(cash_flows: list[float]) -> float:
    """Undiscounted algebraic sum of all cash flows (costs negative, salvage/benefit positive)."""
    return round(sum(float(x) for x in cash_flows), 2)


def calculate_cash_flow(
    *,
    project_life_years: int,
    capex_total_usd: float,
    econ_opex: dict[str, Any],
    media_interval_years: float,
    nozzle_interval_years: float,
    lining_interval_years: float,
    lining_replacement_cost_usd: float,
    media_full_replace_usd: float,
    nozzle_full_replace_usd: float,
    inflation_rate_pct: float,
    escalation_energy_pct: float,
    escalation_maintenance_pct: float,
    maintenance_pct_capex: float,
    annual_benefit_usd: float,
    salvage_value_pct: float,
    tax_rate_pct: float,
    depreciation_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build annual cash flow table (year 0 … N)."""
    n = max(int(project_life_years), 1)
    inf = float(inflation_rate_pct) / 100.0
    esc_e = float(escalation_energy_pct) / 100.0
    esc_m = float(escalation_maintenance_pct) / 100.0
    maint_frac = float(maintenance_pct_capex) / 100.0
    tax_r = max(float(tax_rate_pct) / 100.0, 0.0)
    capex = float(capex_total_usd)
    salvage_gross = capex * max(float(salvage_value_pct), 0.0) / 100.0

    e0 = float(econ_opex.get("energy_cost_usd_yr", 0.0))
    c0 = float(econ_opex.get("chemical_cost_usd_yr", 0.0))
    l0 = float(econ_opex.get("labour_cost_usd_yr", 0.0))
    m_base = maint_frac * capex
    ben0 = max(float(annual_benefit_usd), 0.0)

    mi = max(1, int(round(float(media_interval_years))))
    ni = max(1, int(round(float(nozzle_interval_years))))
    li = max(1, int(round(float(lining_interval_years))))

    dep_by_year = {int(r["year"]): float(r["depreciation_usd"]) for r in depreciation_rows}

    table: list[dict[str, Any]] = []
    net_cf: list[float] = []

    for y in range(0, n + 1):
        if y == 0:
            row = {
                "year": 0,
                "benefit_usd": 0.0,
                "energy_usd": 0.0,
                "chemical_usd": 0.0,
                "labour_usd": 0.0,
                "maintenance_usd": 0.0,
                "media_replace_usd": 0.0,
                "nozzle_replace_usd": 0.0,
                "lining_replace_usd": 0.0,
                "depreciation_usd": 0.0,
                "tax_usd": 0.0,
                "capex_usd": -capex,
                "salvage_usd": 0.0,
                "net_cash_flow_usd": -capex,
            }
            table.append(row)
            net_cf.append(-capex)
            continue

        infl = (1.0 + inf) ** (y - 1)
        energy = e0 * ((1.0 + esc_e) ** (y - 1)) * infl
        chemical = c0 * infl
        labour = l0 * infl
        maintenance = m_base * ((1.0 + esc_m) ** (y - 1)) * infl
        benefit = ben0 * infl

        media_rep = media_full_replace_usd if (y % mi == 0 and mi > 0) else 0.0
        nozzle_rep = nozzle_full_replace_usd if (y % ni == 0 and ni > 0) else 0.0
        lining_rep = lining_replacement_cost_usd if (y % li == 0 and li > 0 and lining_replacement_cost_usd > 0) else 0.0

        dep = dep_by_year.get(y, 0.0)
        opex_cash = energy + chemical + labour + maintenance + media_rep + nozzle_rep + lining_rep
        taxable = benefit - opex_cash - dep
        tax = tax_r * max(taxable, 0.0) if tax_r > 0 else 0.0
        salvage = salvage_gross if y == n else 0.0
        net = benefit - opex_cash - tax + salvage

        table.append({
            "year": y,
            "benefit_usd": round(benefit, 2),
            "energy_usd": round(energy, 2),
            "chemical_usd": round(chemical, 2),
            "labour_usd": round(labour, 2),
            "maintenance_usd": round(maintenance, 2),
            "media_replace_usd": round(media_rep, 2),
            "nozzle_replace_usd": round(nozzle_rep, 2),
            "lining_replace_usd": round(lining_rep, 2),
            "depreciation_usd": round(dep, 2),
            "tax_usd": round(tax, 2),
            "capex_usd": 0.0,
            "salvage_usd": round(salvage, 2),
            "net_cash_flow_usd": round(net, 2),
        })
        net_cf.append(net)

    return {"years": list(range(0, n + 1)), "net_cash_flow_usd": net_cf, "cashflow_table": table}


def calculate_incremental_economics(fin_a: dict[str, Any], fin_b: dict[str, Any]) -> dict[str, Any]:
    """Design B vs A using pre-built ``econ_financial`` payloads."""
    cap_a = float((fin_a or {}).get("capex_total_usd") or 0.0)
    cap_b = float((fin_b or {}).get("capex_total_usd") or 0.0)
    npv_a = float((fin_a or {}).get("npv") or 0.0)
    npv_b = float((fin_b or {}).get("npv") or 0.0)
    oa = float((fin_a or {}).get("first_year_operating_cash_usd") or 0.0)
    ob = float((fin_b or {}).get("first_year_operating_cash_usd") or 0.0)
    na = float((fin_a or {}).get("first_year_net_cash_flow_usd") or 0.0)
    nb = float((fin_b or {}).get("first_year_net_cash_flow_usd") or 0.0)
    roi_a = (fin_a or {}).get("roi_pct")
    roi_b = (fin_b or {}).get("roi_pct")
    return {
        "delta_capex_usd": round(cap_b - cap_a, 2),
        "delta_first_year_operating_cash_usd": round(ob - oa, 2),
        "delta_first_year_net_cash_usd": round(nb - na, 2),
        "delta_npv_usd": round(npv_b - npv_a, 2),
        "incremental_roi_pct": (
            None
            if roi_a is None or roi_b is None
            else round(float(roi_b) - float(roi_a), 2)
        ),
        "economic_summary": (
            f"ΔCAPEX (B−A) = USD {cap_b - cap_a:,.0f}; ΔNPV = USD {npv_b - npv_a:,.0f} "
            f"(discount to each design's own assumptions)."
        ),
    }


def _npv_sensitivity_drivers(
    *,
    base_discount: float,
    project_life_years: int,
    capex_total_usd: float,
    econ_opex: dict[str, Any],
    media_interval_years: float,
    nozzle_interval_years: float,
    lining_interval_years: float,
    lining_replacement_cost_usd: float,
    media_full_replace_usd: float,
    nozzle_full_replace_usd: float,
    inflation_rate_pct: float,
    escalation_energy_pct: float,
    escalation_maintenance_pct: float,
    maintenance_pct_capex: float,
    annual_benefit_usd: float,
    salvage_value_pct: float,
    tax_rate_pct: float,
    depreciation_method: str,
    depreciation_years: int,
) -> dict[str, float]:
    """One-at-a-time perturbations on NPV (coarse driver ranking)."""

    def _flows_for(
        *,
        life: int,
        capex: float,
        esc_e: float,
    ) -> list[float]:
        salvage_usd = capex * max(salvage_value_pct, 0.0) / 100.0
        dep_rows = generate_depreciation_schedule(
            capex, depreciation_years, salvage_usd, depreciation_method,
        )
        cfp = calculate_cash_flow(
            project_life_years=life,
            capex_total_usd=capex,
            econ_opex=econ_opex,
            media_interval_years=media_interval_years,
            nozzle_interval_years=nozzle_interval_years,
            lining_interval_years=lining_interval_years,
            lining_replacement_cost_usd=lining_replacement_cost_usd,
            media_full_replace_usd=media_full_replace_usd,
            nozzle_full_replace_usd=nozzle_full_replace_usd,
            inflation_rate_pct=inflation_rate_pct,
            escalation_energy_pct=esc_e,
            escalation_maintenance_pct=escalation_maintenance_pct,
            maintenance_pct_capex=maintenance_pct_capex,
            annual_benefit_usd=annual_benefit_usd,
            salvage_value_pct=salvage_value_pct,
            tax_rate_pct=tax_rate_pct,
            depreciation_rows=dep_rows,
        )
        return cfp["net_cash_flow_usd"]

    base_flows = _flows_for(
        life=project_life_years,
        capex=capex_total_usd,
        esc_e=escalation_energy_pct,
    )
    base_npv = calculate_npv(base_discount, base_flows)

    out: dict[str, float] = {"base_npv_usd": base_npv}
    f_hi = _flows_for(
        life=project_life_years,
        capex=capex_total_usd,
        esc_e=escalation_energy_pct * 1.1,
    )
    out["energy_escalation_plus10pct"] = calculate_npv(base_discount, f_hi)
    f_cap = _flows_for(
        life=project_life_years,
        capex=capex_total_usd * 1.1,
        esc_e=escalation_energy_pct,
    )
    out["capex_plus10pct"] = calculate_npv(base_discount, f_cap)
    f_life = _flows_for(
        life=project_life_years + 1,
        capex=capex_total_usd,
        esc_e=escalation_energy_pct,
    )
    out["life_plus1yr"] = calculate_npv(base_discount, f_life)
    out["discount_plus10pct"] = calculate_npv(base_discount * 1.1, base_flows)
    return {k: round(v, 2) for k, v in out.items()}


def build_econ_financial(
    *,
    inputs: dict[str, Any],
    econ_capex: dict[str, Any],
    econ_opex: dict[str, Any],
    econ_carbon: dict[str, Any],
    econ_bench: dict[str, Any],
    lining_result: dict[str, Any],
    n_vessels: int,
) -> dict[str, Any]:
    """Assemble ``computed['econ_financial']`` from engineering results and financial inputs."""
    capex = float(econ_capex.get("total_capex_usd", 0.0))
    project_life = int(inputs.get("project_life_years") or inputs.get("design_life_years") or 20)
    discount = float(inputs.get("discount_rate", 5.0))
    inflation = float(inputs.get("inflation_rate", 2.0))
    esc_e = float(inputs.get("escalation_energy_pct", 2.5))
    esc_m = float(inputs.get("escalation_maintenance_pct", 3.0))
    tax_r = float(inputs.get("tax_rate", 0.0))
    maint_pct = float(inputs.get("maintenance_pct_capex", 2.0))
    salvage_pct = float(inputs.get("salvage_value_pct", 5.0))
    dep_method = str(inputs.get("depreciation_method", "straight_line"))
    dep_years = int(inputs.get("depreciation_years") or project_life)
    annual_benefit = float(inputs.get("annual_benefit_usd", 0.0))

    media_int = float(inputs.get("replacement_interval_media") or inputs.get("media_replace_years") or 7.0)
    noz_int = float(inputs.get("replacement_interval_nozzles") or inputs.get("nozzle_replace_years") or 10.0)
    lin_int = float(inputs.get("replacement_interval_lining", 15.0))

    lining_unit = float(lining_result.get("total_cost_usd") or 0.0)
    lining_replace = lining_unit * max(n_vessels, 1) if lining_result.get("protection_type") not in (None, "None", "") else 0.0

    media_annual = float(econ_opex.get("media_cost_usd_yr", 0.0))
    noz_annual = float(econ_opex.get("nozzle_cost_usd_yr", 0.0))
    mi = max(1.0, media_int)
    ni = max(1.0, noz_int)
    media_full = media_annual * mi
    nozzle_full = noz_annual * ni

    salvage_usd = capex * max(salvage_pct, 0.0) / 100.0
    dep_rows = generate_depreciation_schedule(capex, dep_years, salvage_usd, dep_method)

    cf_pack = calculate_cash_flow(
        project_life_years=project_life,
        capex_total_usd=capex,
        econ_opex=econ_opex,
        media_interval_years=media_int,
        nozzle_interval_years=noz_int,
        lining_interval_years=lin_int,
        lining_replacement_cost_usd=lining_replace,
        media_full_replace_usd=media_full,
        nozzle_full_replace_usd=nozzle_full,
        inflation_rate_pct=inflation,
        escalation_energy_pct=esc_e,
        escalation_maintenance_pct=esc_m,
        maintenance_pct_capex=maint_pct,
        annual_benefit_usd=annual_benefit,
        salvage_value_pct=salvage_pct,
        tax_rate_pct=tax_r,
        depreciation_rows=dep_rows,
    )
    flows = cf_pack["net_cash_flow_usd"]
    npv_val = calculate_npv(discount, flows)
    irr_val = calculate_irr(flows)
    roi_val = calculate_roi(flows, capex)
    spb = calculate_simple_payback(flows)
    dpb = calculate_discounted_payback(discount, flows)
    lc = calculate_lifecycle_cost(flows)
    annual_flow = float(econ_bench.get("annual_flow_m3", 0.0) or econ_opex.get("annual_flow_m3", 0.0))
    lcow = float(econ_bench.get("lcow", 0.0))
    annualized = round(lcow * annual_flow, 2) if annual_flow > 0 else None

    tbl = cf_pack["cashflow_table"]
    y1 = next((r for r in tbl if r["year"] == 1), None)
    first_y_net = float(y1["net_cash_flow_usd"]) if y1 else 0.0
    op_cash_y1 = (
        float(y1.get("benefit_usd", 0.0))
        - float(y1.get("energy_usd", 0.0))
        - float(y1.get("chemical_usd", 0.0))
        - float(y1.get("labour_usd", 0.0))
        - float(y1.get("maintenance_usd", 0.0))
        if y1
        else 0.0
    )

    undisc = [float(r["year"]) for r in tbl]
    cum_cost: list[float] = []
    run = 0.0
    for r in tbl:
        y = int(r["year"])
        if y == 0:
            run += capex
        else:
            run += (
                float(r["energy_usd"])
                + float(r["chemical_usd"])
                + float(r["labour_usd"])
                + float(r["maintenance_usd"])
                + float(r["media_replace_usd"])
                + float(r["nozzle_replace_usd"])
                + float(r["lining_replace_usd"])
            )
        cum_cost.append(round(run, 2))

    co2_yr = float(econ_carbon.get("co2_operational_kg_yr", 0.0))
    co2_cum = []
    c2 = 0.0
    for r in tbl:
        y = int(r["year"])
        if y == 0:
            co2_cum.append(round(float(econ_carbon.get("co2_construction_kg", 0.0)), 2))
        else:
            c2 += co2_yr
            co2_cum.append(round(float(econ_carbon.get("co2_construction_kg", 0.0)) + c2, 2))

    npv_scan = _npv_sensitivity_drivers(
        base_discount=discount,
        project_life_years=project_life,
        capex_total_usd=capex,
        econ_opex=econ_opex,
        media_interval_years=media_int,
        nozzle_interval_years=noz_int,
        lining_interval_years=lin_int,
        lining_replacement_cost_usd=lining_replace,
        media_full_replace_usd=media_full,
        nozzle_full_replace_usd=nozzle_full,
        inflation_rate_pct=inflation,
        escalation_energy_pct=esc_e,
        escalation_maintenance_pct=esc_m,
        maintenance_pct_capex=maint_pct,
        annual_benefit_usd=annual_benefit,
        salvage_value_pct=salvage_pct,
        tax_rate_pct=tax_r,
        depreciation_method=dep_method,
        depreciation_years=dep_years,
    )

    repl_schedule: list[dict[str, Any]] = []
    for r in tbl:
        if r["year"] == 0:
            continue
        ev = []
        if r.get("media_replace_usd", 0) > 0:
            ev.append("media")
        if r.get("nozzle_replace_usd", 0) > 0:
            ev.append("nozzle")
        if r.get("lining_replace_usd", 0) > 0:
            ev.append("lining")
        if ev:
            spend = (
                float(r["media_replace_usd"])
                + float(r["nozzle_replace_usd"])
                + float(r["lining_replace_usd"])
            )
            repl_schedule.append(
                {"year": r["year"], "events": ev, "replacement_spend_usd": round(spend, 2)}
            )

    summary_lines = [
        f"NPV @ {discount:.2f} %/yr = USD {npv_val:,.0f}",
        f"Lifecycle net (undiscounted sum of cash flows) = USD {lc:,.0f}",
    ]
    if irr_val is not None:
        summary_lines.append(f"IRR ≈ {irr_val:.2f} %/yr")
    if spb is not None:
        summary_lines.append(f"Simple payback ≈ {spb:.2f} yr")
    if dpb is not None:
        summary_lines.append(f"Discounted payback ≈ {dpb:.2f} yr")

    return {
        "npv": npv_val,
        "irr_pct": irr_val,
        "roi_pct": roi_val,
        "simple_payback_years": spb,
        "discounted_payback_years": dpb,
        "lifecycle_cost": lc,
        "annualized_cost": annualized,
        "cashflow_table": tbl,
        "depreciation_table": dep_rows,
        "replacement_schedule": repl_schedule,
        "economic_summary": " · ".join(summary_lines),
        "capex_total_usd": round(capex, 2),
        "first_year_net_cash_flow_usd": round(first_y_net, 2),
        "first_year_operating_cash_usd": round(op_cash_y1, 2),
        "cumulative_undiscounted_cost_curve": [{"year": int(u), "usd": v} for u, v in zip(undisc, cum_cost)],
        "co2_vs_cost_scatter": [{"year": int(u), "co2_kg_cumulative": c, "undiscounted_cost_usd": v}
                               for u, v, c in zip(undisc, cum_cost, co2_cum)],
        "npv_sensitivity": npv_scan,
        "discounted_pv_by_year": [
            round(
                sum(
                    flows[k] / ((1.0 + discount / 100.0) ** k)
                    for k in range(t + 1)
                ),
                2,
            )
            if abs(discount) > 1e-12
            else round(sum(flows[: t + 1]), 2)
            for t in range(len(flows))
        ],
        "annual_opex_escalation_curve": [
            {
                "year": int(r["year"]),
                "total_opex_components_usd": round(
                    float(r["energy_usd"])
                    + float(r["chemical_usd"])
                    + float(r["labour_usd"])
                    + float(r["maintenance_usd"])
                    + float(r["media_replace_usd"])
                    + float(r["nozzle_replace_usd"])
                    + float(r["lining_replace_usd"]),
                    2,
                ),
            }
            for r in tbl
            if int(r["year"]) > 0
        ],
        "undiscounted_cumulative_net_usd": [
            round(sum(flows[: t + 1]), 2) for t in range(len(flows))
        ],
    }
