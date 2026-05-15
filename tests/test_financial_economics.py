"""Tests for engine/financial_economics.py — lifecycle cash flow, NPV, IRR, depreciation."""
import pytest

from engine.financial_economics import (
    build_econ_financial,
    calculate_cash_flow,
    calculate_incremental_economics,
    calculate_irr,
    calculate_lifecycle_cost,
    calculate_npv,
    calculate_simple_payback,
    generate_depreciation_schedule,
)


def _minimal_econ_opex():
    return {
        "energy_cost_usd_yr": 100_000.0,
        "chemical_cost_usd_yr": 10_000.0,
        "labour_cost_usd_yr": 20_000.0,
        "media_cost_usd_yr": 5_000.0,
        "nozzle_cost_usd_yr": 1_000.0,
        "total_opex_usd_yr": 136_000.0,
        "annual_flow_m3": 1_000_000.0,
    }


def test_straight_line_depreciation():
    rows = generate_depreciation_schedule(1000.0, 4, 200.0, "straight_line")
    assert len(rows) == 4
    assert sum(r["depreciation_usd"] for r in rows) == pytest.approx(800.0, rel=1e-6)


def test_ddb_depreciation_positive():
    rows = generate_depreciation_schedule(1000.0, 5, 50.0, "declining_balance")
    assert len(rows) == 5
    assert all(r["depreciation_usd"] >= 0 for r in rows)


def test_npv_zero_discount_sum():
    flows = [-1000.0, -100.0, -100.0]
    assert calculate_npv(0.0, flows) == pytest.approx(-1200.0, rel=1e-9)


def test_irr_simple_investment():
    """−1000 + 600 + 600 → IRR exists and is positive."""
    flows = [-1000.0, 600.0, 600.0]
    irr = calculate_irr(flows)
    assert irr is not None
    assert 10.0 < irr < 20.0


def test_irr_all_negative_returns_none():
    flows = [-1000.0, -100.0, -50.0]
    assert calculate_irr(flows) is None


def test_simple_payback():
    assert calculate_simple_payback([-100, 30, 40, 50]) == pytest.approx(2.6, rel=1e-6)


def test_cash_flow_escalation_increases_energy():
    dep = generate_depreciation_schedule(1_000_000.0, 10, 50_000.0, "straight_line")
    opex = _minimal_econ_opex()
    cf = calculate_cash_flow(
        project_life_years=3,
        capex_total_usd=1_000_000.0,
        econ_opex=opex,
        media_interval_years=10,
        nozzle_interval_years=10,
        lining_interval_years=20,
        lining_replacement_cost_usd=0.0,
        media_full_replace_usd=50_000.0,
        nozzle_full_replace_usd=10_000.0,
        inflation_rate_pct=10.0,
        escalation_energy_pct=0.0,
        escalation_maintenance_pct=0.0,
        maintenance_pct_capex=0.0,
        annual_benefit_usd=0.0,
        salvage_value_pct=0.0,
        tax_rate_pct=0.0,
        depreciation_rows=dep,
    )
    y1 = next(r for r in cf["cashflow_table"] if r["year"] == 1)
    y2 = next(r for r in cf["cashflow_table"] if r["year"] == 2)
    assert y2["energy_usd"] > y1["energy_usd"]


def test_replacement_schedule_has_events():
    dep = generate_depreciation_schedule(500_000.0, 10, 0.0, "straight_line")
    opex = _minimal_econ_opex()
    cf = calculate_cash_flow(
        project_life_years=10,
        capex_total_usd=500_000.0,
        econ_opex=opex,
        media_interval_years=2,
        nozzle_interval_years=5,
        lining_interval_years=10,
        lining_replacement_cost_usd=20_000.0,
        media_full_replace_usd=10_000.0,
        nozzle_full_replace_usd=5_000.0,
        inflation_rate_pct=0.0,
        escalation_energy_pct=0.0,
        escalation_maintenance_pct=0.0,
        maintenance_pct_capex=1.0,
        annual_benefit_usd=500_000.0,
        salvage_value_pct=0.0,
        tax_rate_pct=0.0,
        depreciation_rows=dep,
    )
    years_media = [r["year"] for r in cf["cashflow_table"] if r.get("media_replace_usd", 0) > 0]
    assert 2 in years_media
    assert 4 in years_media


def test_incremental_economics():
    a = {"capex_total_usd": 1e6, "npv": -5e6, "first_year_operating_cash_usd": -1e5, "first_year_net_cash_flow_usd": -2e5, "roi_pct": -10.0}
    b = {"capex_total_usd": 1.1e6, "npv": -4.8e6, "first_year_operating_cash_usd": -0.9e5, "first_year_net_cash_flow_usd": -1.5e5, "roi_pct": -8.0}
    inc = calculate_incremental_economics(a, b)
    assert inc["delta_capex_usd"] == pytest.approx(100_000.0, rel=1e-6)
    assert inc["delta_npv_usd"] == pytest.approx(200_000.0, rel=1e-6)


def test_build_econ_financial_smoke():
    inputs = {
        "design_life_years": 5,
        "project_life_years": 5,
        "discount_rate": 8.0,
        "inflation_rate": 0.0,
        "escalation_energy_pct": 0.0,
        "escalation_maintenance_pct": 0.0,
        "tax_rate": 0.0,
        "maintenance_pct_capex": 0.0,
        "salvage_value_pct": 0.0,
        "depreciation_method": "straight_line",
        "depreciation_years": 5,
        "annual_benefit_usd": 0.0,
        "replacement_interval_media": 10,
        "replacement_interval_nozzles": 10,
        "replacement_interval_lining": 20,
    }
    econ_capex = {"total_capex_usd": 2_000_000}
    econ_opex = _minimal_econ_opex()
    econ_carbon = {
        "co2_operational_kg_yr": 1000.0,
        "co2_construction_kg": 50_000.0,
    }
    econ_bench = {"lcow": 0.05, "annual_flow_m3": 1e6}
    lining = {"protection_type": "None", "total_cost_usd": 0.0}
    fin = build_econ_financial(
        inputs=inputs,
        econ_capex=econ_capex,
        econ_opex=econ_opex,
        econ_carbon=econ_carbon,
        econ_bench=econ_bench,
        lining_result=lining,
        n_vessels=4,
    )
    assert "npv" in fin and "cashflow_table" in fin
    assert len(fin["cashflow_table"]) == 6
    assert fin["lifecycle_cost"] == calculate_lifecycle_cost(
        [r["net_cash_flow_usd"] for r in fin["cashflow_table"]]
    )


def test_build_econ_financial_energy_sensitivity_matches_linkage_pattern():
    """Higher annual energy cost → more negative NPV (Economics tab rebuild uses same entry point)."""
    base = {
        "design_life_years": 5,
        "project_life_years": 5,
        "discount_rate": 5.0,
        "inflation_rate": 0.0,
        "escalation_energy_pct": 0.0,
        "escalation_maintenance_pct": 0.0,
        "tax_rate": 0.0,
        "maintenance_pct_capex": 0.0,
        "salvage_value_pct": 0.0,
        "depreciation_method": "straight_line",
        "depreciation_years": 5,
        "annual_benefit_usd": 0.0,
        "replacement_interval_media": 10,
        "replacement_interval_nozzles": 10,
        "replacement_interval_lining": 20,
    }
    econ_capex = {"total_capex_usd": 1_000_000}
    lining = {"protection_type": "None", "total_cost_usd": 0.0}
    econ_carbon = {"co2_operational_kg_yr": 100.0, "co2_construction_kg": 1000.0}
    econ_bench = {"lcow": 0.1, "annual_flow_m3": 1e6}
    o1 = _minimal_econ_opex()
    o2 = {
        **o1,
        "energy_cost_usd_yr": o1["energy_cost_usd_yr"] + 50_000.0,
        "total_opex_usd_yr": o1["total_opex_usd_yr"] + 50_000.0,
    }
    f1 = build_econ_financial(
        inputs=base,
        econ_capex=econ_capex,
        econ_opex=o1,
        econ_carbon=econ_carbon,
        econ_bench=econ_bench,
        lining_result=lining,
        n_vessels=1,
    )
    f2 = build_econ_financial(
        inputs=base,
        econ_capex=econ_capex,
        econ_opex=o2,
        econ_carbon=econ_carbon,
        econ_bench=econ_bench,
        lining_result=lining,
        n_vessels=1,
    )
    assert float(f2["npv"]) < float(f1["npv"])
