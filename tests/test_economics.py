"""
tests/test_economics.py
───────────────────────
Tests for engine/economics.py — CRF, CAPEX, OPEX, and carbon footprint.

Reference calculations
----------------------
CRF(8 %, 20 y):
  i = 0.08,  CRF = 0.08 × 1.08²⁰ / (1.08²⁰ − 1) = 0.101852  ✓

CAPEX (all costs are per-vessel × n_vessels):
  steel_cost = weight × steel_cost_usd_kg × n_vessels
             = 500 000 × 3.5 × 2 = 3 500 000 USD
  direct = steel + erection×2 + piping×2 + instr×2 + civil×2
         = 3 500 000 + 400 000 + 300 000 + 200 000 + 240 000 = 4 640 000 USD
  engineering  = direct × 0.10 = 464 000 USD
  contingency  = (direct + eng) × 0.05 = 5 104 000 × 0.05 = 255 200 USD
  total_capex  = 4 640 000 + 464 000 + 255 200 = 5 359 200 USD
  per_vessel   = 5 359 200 / 2 = 2 679 600 USD

OPEX (annual):
  energy_kw      = filtration + bw = 50 + 20 = 70 kW
  energy_cost    = 70 × 0.10 × 8 760 = 61 320 USD/yr
  annual_flow    = 21 000 × 8 760 = 183 960 000 m³/yr
  chemical_cost  = 0.005 × 183 960 000 = 919 800 USD/yr
  media sand/yr  = 50 000 × 0.50 / 10 = 2 500 USD/yr
  media anth/yr  = 20 000 × 3.00 / 10 = 6 000 USD/yr
  labour/yr      = 15 000 × 16 = 240 000 USD/yr
  nozzle/yr      = 100 × 25 / 5 = 500 USD/yr

Carbon footprint:
  co2_op/yr    = (50+20) × 8 760 × 0.4 = 245 280 kg CO₂/yr
  co2_steel    = 500 000 × 1.8 = 900 000 kg CO₂
  co2_concrete = 200 000 × 0.15 = 30 000 kg CO₂
  co2_media    = 50 000×0.006 + 20 000×0.150 = 300 + 3 000 = 3 300 kg CO₂
  co2_construction = 933 300 kg CO₂
  co2_lifecycle = 933 300 + 245 280 × 20 = 5 838 900 kg CO₂
  per_m3_lifecycle = 5 838 900 / (183 960 000 × 20) = 0.00159 ≈ 0.0016

Tolerances: rel=0.001 for exact arithmetic, rel=0.01 for rounded integer outputs.
"""
import math
import pytest
from engine.economics import (
    capital_recovery_factor,
    capex_breakdown,
    opex_annual,
    carbon_footprint,
)


# ── Shared test fixtures ──────────────────────────────────────────────────────

def _capex(**kwargs):
    defaults = dict(
        weight_total_kg=500_000, n_vessels=2, steel_cost_usd_kg=3.5,
        erection_usd=200_000, piping_usd=150_000,
        instrumentation_usd=100_000, civil_usd=120_000,
        engineering_pct=10.0, contingency_pct=5.0,
    )
    defaults.update(kwargs)
    return capex_breakdown(**defaults)


def _opex(**kwargs):
    defaults = dict(
        filtration_power_kw=50.0, bw_power_kw=20.0, blower_power_kw=0.0,
        n_vessels=2, electricity_tariff=0.10, operating_hours=8_760.0,
        media_inventory_kg_by_type={"Fine sand": 50_000, "Anthracite": 20_000},
        media_costs_by_type={"Fine sand": 0.50, "Anthracite": 3.00},
        media_interval_years=10.0,
        n_strainer_nozzles=100, nozzle_cost_usd=25.0, nozzle_interval_years=5.0,
        labour_usd_per_filter_year=15_000.0, n_filters_total=16,
        chemical_cost_usd_m3=0.005, total_flow_m3h=21_000.0,
    )
    defaults.update(kwargs)
    return opex_annual(**defaults)


def _carbon(**kwargs):
    defaults = dict(
        filtration_power_kw=50.0, bw_power_kw=20.0, blower_power_kw=0.0,
        operating_hours=8_760.0, grid_intensity_kg_kwh=0.4,
        weight_steel_kg=500_000, steel_carbon_kg_kg=1.8,
        weight_concrete_kg=200_000, concrete_carbon_kg_kg=0.15,
        media_mass_by_type_kg={"Fine sand": 50_000, "Anthracite": 20_000},
        media_carbon_by_type={"Fine sand": 0.006, "Anthracite": 0.150},
        design_life_years=20, total_flow_m3h=21_000.0,
    )
    defaults.update(kwargs)
    return carbon_footprint(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# Capital Recovery Factor
# ═════════════════════════════════════════════════════════════════════════════

class TestCapitalRecoveryFactor:

    def test_standard_crf(self):
        """
        CRF(8%, 20 y) = 0.08 × 1.08²⁰ / (1.08²⁰ − 1) = 0.101852.
        """
        crf = capital_recovery_factor(8.0, 20)
        assert crf == pytest.approx(0.101852, rel=0.001)

    def test_crf_at_zero_rate_equals_inverse_life(self):
        """
        Zero discount rate → CRF = 1/n (simple payback annualisation).
        n=25: CRF = 0.04 exactly.
        """
        crf = capital_recovery_factor(0.0, 25)
        assert crf == pytest.approx(1.0 / 25, rel=0.001)

    def test_higher_rate_gives_higher_crf(self):
        """Higher discount rate → higher annual payment needed."""
        assert capital_recovery_factor(10.0, 20) > capital_recovery_factor(5.0, 20)

    def test_longer_life_gives_lower_crf(self):
        """Longer design life → lower annual payment for same CAPEX."""
        assert capital_recovery_factor(8.0, 30) < capital_recovery_factor(8.0, 20)

    def test_crf_always_positive(self):
        """CRF must be strictly positive for all reasonable inputs."""
        for r in [3.0, 5.0, 8.0, 10.0, 12.0]:
            for n in [10, 15, 20, 25, 30]:
                assert capital_recovery_factor(r, n) > 0


# ═════════════════════════════════════════════════════════════════════════════
# CAPEX breakdown
# ═════════════════════════════════════════════════════════════════════════════

class TestCapexBreakdown:

    def test_total_capex_value(self):
        """
        total_capex = 5 359 200 USD (hand calc: direct 4 640 000,
        engineering 464 000, contingency 255 200).
        """
        r = _capex()
        assert r["total_capex_usd"] == pytest.approx(5_359_200, rel=0.001)

    def test_direct_installed_value(self):
        """
        direct = steel(3.5M) + erection(400k) + piping(300k)
               + instrumentation(200k) + civil(240k) = 4 640 000 USD.
        """
        r = _capex()
        assert r["direct_installed_usd"] == pytest.approx(4_640_000, rel=0.001)

    def test_steel_cost_per_vessel_scaling(self):
        """steel_cost = weight × unit_cost × n_vessels (all costs are per-vessel)."""
        r = _capex()
        assert r["steel_cost_usd"] == pytest.approx(500_000 * 3.5 * 2, rel=0.001)

    def test_contingency_on_direct_plus_engineering(self):
        """
        Contingency applies to (direct + engineering), not just direct.
        5 104 000 × 0.05 = 255 200 USD.
        """
        r = _capex()
        expected_contingency = (r["direct_installed_usd"] + r["engineering_usd"]) * 0.05
        assert r["contingency_usd"] == pytest.approx(expected_contingency, rel=0.001)

    def test_total_equals_sum_of_parts(self):
        """total_capex = direct + engineering + contingency."""
        r = _capex()
        expected = (r["direct_installed_usd"]
                    + r["engineering_usd"]
                    + r["contingency_usd"])
        assert r["total_capex_usd"] == pytest.approx(expected, rel=0.001)

    def test_capex_per_vessel(self):
        """capex_per_vessel = total_capex / n_vessels."""
        r = _capex()
        assert r["capex_per_vessel_usd"] == pytest.approx(
            r["total_capex_usd"] / 2, rel=0.001)

    def test_more_vessels_gives_higher_total(self):
        """More vessels → proportionally higher total CAPEX."""
        r2 = _capex(n_vessels=2)
        r4 = _capex(n_vessels=4)
        assert r4["total_capex_usd"] > r2["total_capex_usd"]

    def test_higher_steel_cost_gives_higher_capex(self):
        """Higher steel unit cost → higher total CAPEX."""
        r_low  = _capex(steel_cost_usd_kg=3.0)
        r_high = _capex(steel_cost_usd_kg=5.0)
        assert r_high["total_capex_usd"] > r_low["total_capex_usd"]

    def test_all_output_keys_present(self):
        """All expected keys must appear in the result dict."""
        r = _capex()
        for key in ["steel_cost_usd", "erection_usd", "piping_usd",
                    "instrumentation_usd", "civil_usd",
                    "direct_installed_usd", "engineering_usd",
                    "contingency_usd", "total_capex_usd",
                    "capex_per_vessel_usd"]:
            assert key in r, f"Missing key: {key}"


# ═════════════════════════════════════════════════════════════════════════════
# Annual OPEX
# ═════════════════════════════════════════════════════════════════════════════

class TestOpexAnnual:

    def test_energy_cost(self):
        """
        energy = (50 + 20) kW × 0.10 USD/kWh × 8 760 h/yr = 61 320 USD/yr.
        """
        r = _opex()
        assert r["energy_cost_usd_yr"] == pytest.approx(61_320, rel=0.001)

    def test_annual_flow(self):
        """annual_flow = 21 000 m³/h × 8 760 h/yr = 183 960 000 m³/yr."""
        r = _opex()
        assert r["annual_flow_m3"] == pytest.approx(183_960_000, rel=0.001)

    def test_chemical_cost(self):
        """chemical_cost = 0.005 USD/m³ × 183 960 000 m³ = 919 800 USD/yr."""
        r = _opex()
        assert r["chemical_cost_usd_yr"] == pytest.approx(919_800, rel=0.001)

    def test_media_cost_by_type(self):
        """
        Sand: 50 000 kg × 0.50 USD/kg / 10 yr = 2 500 USD/yr.
        Anthracite: 20 000 × 3.00 / 10 = 6 000 USD/yr.
        """
        r = _opex()
        assert r["media_detail"]["Fine sand"] == pytest.approx(2_500, rel=0.001)
        assert r["media_detail"]["Anthracite"] == pytest.approx(6_000, rel=0.001)

    def test_media_cost_total(self):
        """Total media cost/yr = sum over all media types."""
        r = _opex()
        assert r["media_cost_usd_yr"] == pytest.approx(8_500, rel=0.001)

    def test_labour_cost(self):
        """labour = 15 000 USD/filter/yr × 16 filters = 240 000 USD/yr."""
        r = _opex()
        assert r["labour_cost_usd_yr"] == pytest.approx(240_000, rel=0.001)

    def test_nozzle_cost(self):
        """nozzle = 100 nozzles × 25 USD/nozzle / 5 yr = 500 USD/yr."""
        r = _opex()
        assert r["nozzle_cost_usd_yr"] == pytest.approx(500, rel=0.001)

    def test_total_opex_equals_sum_of_components(self):
        """
        total_opex = energy + media + nozzle + labour + chemical.
        """
        r = _opex()
        expected = (r["energy_cost_usd_yr"] + r["media_cost_usd_yr"]
                    + r["nozzle_cost_usd_yr"] + r["labour_cost_usd_yr"]
                    + r["chemical_cost_usd_yr"])
        assert r["total_opex_usd_yr"] == pytest.approx(expected, rel=0.001)

    def test_opex_per_m3(self):
        """opex_per_m3 = total_opex / annual_flow (derived, not stored directly)."""
        r = _opex()
        expected = r["total_opex_usd_yr"] / r["annual_flow_m3"]
        assert r["opex_per_m3_usd"] == pytest.approx(expected, rel=0.01)

    def test_higher_tariff_gives_higher_energy_cost(self):
        """Higher electricity tariff → higher energy cost."""
        r_low  = _opex(electricity_tariff=0.08)
        r_high = _opex(electricity_tariff=0.15)
        assert r_high["energy_cost_usd_yr"] > r_low["energy_cost_usd_yr"]


# ═════════════════════════════════════════════════════════════════════════════
# Carbon footprint
# ═════════════════════════════════════════════════════════════════════════════

class TestCarbonFootprint:

    def test_operational_co2_per_year(self):
        """
        co2_op/yr = (50+20) kW × 8 760 h × 0.4 kg/kWh = 245 280 kg CO₂/yr.
        """
        r = _carbon()
        assert r["co2_operational_kg_yr"] == pytest.approx(245_280, rel=0.001)

    def test_steel_co2(self):
        """co2_steel = 500 000 kg × 1.8 kg CO₂/kg = 900 000 kg CO₂."""
        r = _carbon()
        assert r["co2_steel_kg"] == pytest.approx(900_000, rel=0.001)

    def test_concrete_co2(self):
        """co2_concrete = 200 000 kg × 0.15 = 30 000 kg CO₂."""
        r = _carbon()
        assert r["co2_concrete_kg"] == pytest.approx(30_000, rel=0.001)

    def test_media_co2(self):
        """
        co2_media = 50 000×0.006 + 20 000×0.150 = 300 + 3 000 = 3 300 kg CO₂.
        """
        r = _carbon()
        assert r["co2_media_kg"] == pytest.approx(3_300, rel=0.001)

    def test_construction_co2(self):
        """co2_construction = steel + concrete + media = 933 300 kg CO₂."""
        r = _carbon()
        assert r["co2_construction_kg"] == pytest.approx(933_300, rel=0.001)

    def test_lifecycle_co2(self):
        """
        co2_lifecycle = construction + operational × design_life
                      = 933 300 + 245 280 × 20 = 5 838 900 kg CO₂.
        """
        r = _carbon()
        assert r["co2_lifecycle_kg"] == pytest.approx(5_838_900, rel=0.001)

    def test_lifecycle_co2_per_m3(self):
        """
        co2_per_m3_lifecycle = lifecycle / (annual_flow × design_life)
                             = 5 838 900 / (183 960 000 × 20) ≈ 0.001586.
        """
        r = _carbon()
        expected = r["co2_lifecycle_kg"] / (r["annual_flow_m3"] * r["design_life_years"])
        assert r["co2_per_m3_lifecycle"] == pytest.approx(expected, rel=0.01)

    def test_higher_grid_intensity_gives_more_co2(self):
        """Higher grid carbon intensity → higher operational CO₂."""
        r_low  = _carbon(grid_intensity_kg_kwh=0.3)
        r_high = _carbon(grid_intensity_kg_kwh=0.6)
        assert r_high["co2_operational_kg_yr"] > r_low["co2_operational_kg_yr"]

    def test_construction_co2_is_positive(self):
        """Construction CO₂ must be strictly positive."""
        r = _carbon()
        assert r["co2_construction_kg"] > 0

    def test_all_output_keys_present(self):
        """All expected keys must appear in the carbon footprint result."""
        r = _carbon()
        for key in ["co2_operational_kg_yr", "co2_steel_kg", "co2_concrete_kg",
                    "co2_media_kg", "co2_construction_kg", "co2_lifecycle_kg",
                    "co2_per_m3_lifecycle", "co2_per_m3_operational",
                    "annual_flow_m3", "design_life_years"]:
            assert key in r, f"Missing key: {key}"
