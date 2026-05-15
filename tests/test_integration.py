"""
tests/test_integration.py
─────────────────────────
End-to-end smoke test for engine/compute.py::compute_all().

Runs a single full computation with representative inputs and verifies that
the output dict is self-consistent and matches key reference values derived
from the individual engine module tests.

Reference values
----------------
Inputs: 16 filters, 1 stream, 21 000 m³/h, ID=5.5 m, L=24.3 m,
        Elliptic 2:1, FULL radiography, P=7 bar, CA=1.5 mm, lining=4 mm,
        3-layer bed (Gravel 0.20 m / Fine sand 0.80 m / Anthracite 0.80 m),
        BW=30 m/h, α=1×10¹² m/kg, feed 27°C/35 ppt.

Derived:
  q_per_filter      = 21 000 / 16 = 1 312.5 m³/h  (N scenario)
  t_shell_design_mm ≥ t_shell_min = 16.42 mm (ASME UG-27)
  od_m              = real_id + 2 × t_design/1000 = 5.492 + 2×0.018 = 5.528 m
  rho_feed (27°C, 35 ppt) ≈ 1 022.7 kg/m³ (Millero & Poisson)
  settled bed        = 0.20 + 0.80 + 0.80 = 1.80 m

Tolerances: rel=0.001 for exact arithmetic, rel=0.01 for correlations.
"""
import pytest
from engine.compute import compute_all


MATERIALS = {
    "ASTM A516-70": {"S_kgf_cm2": 1200, "T_max_c": 350, "rho": 7850},
}

_LAYERS = [
    {"Type": "Gravel",     "Depth": 0.20, "epsilon0": 0.46, "d10": 6.0,  "cu": 1.0,
     "rho_p_eff": 2600, "psi": 0.90, "is_porous": False, "is_support": True},
    {"Type": "Fine sand",  "Depth": 0.80, "epsilon0": 0.42, "d10": 0.8,  "cu": 1.3,
     "rho_p_eff": 2650, "psi": 0.80, "is_porous": False, "is_support": False},
    {"Type": "Anthracite", "Depth": 0.80, "epsilon0": 0.48, "d10": 1.3,  "cu": 1.5,
     "rho_p_eff": 1450, "psi": 0.70, "is_porous": False, "is_support": False},
]

_INPUTS = {
    "total_flow": 21000.0, "streams": 1, "n_filters": 16, "hydraulic_assist": 0, "redundancy": 1,
    "feed_temp": 27.0, "feed_sal": 35.0,
    "temp_low": 15.0, "temp_high": 35.0,
    "tss_low": 5.0, "tss_avg": 10.0, "tss_high": 20.0,
    "bw_temp": 27.0, "bw_sal": 35.0,
    "velocity_threshold": 12.0, "ebct_threshold": 5.0,
    "nominal_id": 5.5, "total_length": 24.3, "end_geometry": "Elliptic 2:1",
    "lining_mm": 4.0, "material_name": "ASTM A516-70",
    "mat_info": MATERIALS["ASTM A516-70"],
    "shell_radio": "FULL", "head_radio": "FULL",
    "design_pressure": 7.0, "corrosion": 1.5, "steel_density": 7850.0,
    "ov_shell": 0.0, "ov_head": 0.0,
    "nozzle_plate_h": 1.0, "np_bore_dia": 50.0, "np_density": 50.0,
    "np_beam_sp": 500.0, "np_override_t": 0.0, "np_slot_dp": 0.03,
    "collector_h": 4.2, "freeboard_mm": 200,
    "layers": _LAYERS,
    "solid_loading": 1.5, "captured_solids_density": 1020.0,
    "solid_loading_scale": 1.0, "maldistribution_factor": 1.0,
    "use_calculated_maldistribution": False,
    "collector_header_id_m": 0.25, "n_bw_laterals": 4,
    "lateral_dn_mm": 50.0, "lateral_spacing_m": 0.0, "lateral_length_m": 0.0,
    "lateral_orifice_d_mm": 0.0, "n_orifices_per_lateral": 0, "lateral_discharge_cd": 0.62,
    "alpha_calibration_factor": 1.0, "tss_capture_efficiency": 1.0,
    "expansion_calibration_scale": 1.0,
    "alpha_specific": 1e12, "dp_trigger_bar": 1.0,
    "bw_velocity": 30.0, "air_scour_rate": 55.0,
    "air_scour_mode": "manual", "air_scour_target_expansion_pct": 20.0,
    "airwater_step_water_m_h": 12.5,
    "bw_timeline_stagger": "feasibility_trains",
    "bw_schedule_horizon_days": 7,
    "bw_cycles_day": 1,
    "bw_s_drain": 10, "bw_s_air": 1, "bw_s_airw": 5,
    "bw_s_hw": 10, "bw_s_settle": 2, "bw_s_fill": 10, "bw_total_min": 38,
    "vessel_pressure_bar": 4.0, "blower_air_delta_p_bar": 0.15, "blower_eta": 0.70, "blower_inlet_temp_c": 30.0,
    "tank_sf": 1.5, "bw_head_mwc": 15.0,
    "default_rating": "150#", "nozzle_stub_len": 350, "strainer_mat": "SS 316L",
    "air_header_dn": 200, "manhole_dn": 600, "n_manholes": 1,
    "support_type": "Saddle", "saddle_h": 0.8, "saddle_contact_angle": 120.0,
    "leg_h": 1.2, "leg_section": 150.0, "base_plate_t": 20.0, "gusset_t": 12.0,
    "protection_type": "Rubber lining",
    "external_environment": "Non-marine (industrial / inland)",
    "seismic_design_category": "Not evaluated",
    "seismic_importance_factor": 1.0,
    "spectral_accel_sds": 0.0,
    "site_class_asce": "B",
    "basic_wind_ms": 0.0,
    "wind_exposure": "C",
    "rubber_type_sel": "EPDM", "rubber_layers": 2,
    "rubber_cost_m2": 0.0, "rubber_labor_m2": 0.0,
    "epoxy_type_sel": "High-build epoxy", "epoxy_dft_um": 350.0,
    "epoxy_coats": 2, "epoxy_cost_m2": 0.0, "epoxy_labor_m2": 0.0,
    "ceramic_type_sel": "Ceramic-filled epoxy", "ceramic_dft_um": 500.0,
    "ceramic_coats": 2, "ceramic_cost_m2": 0.0, "ceramic_labor_m2": 0.0,
    "cart_flow": 21000.0, "cart_size": '40"', "cart_rating": 10,
    "cart_housing": 40, "cart_cip": False,
    "cart_dhc_override_g": 0.0,
    "cf_sync_feed_tss": False, "cf_sync_tss_band": "avg",
    "cf_inlet_tss": 10.0, "cf_outlet_tss": 1.5,
    "dp_dist": 0.02, "dp_inlet_pipe": 0.30, "dp_outlet_pipe": 0.20,
    "p_residual": 0.5, "static_head": 0.0,
    "pump_eta": 0.75, "bw_pump_eta": 0.72, "motor_eta": 0.95,
    "elec_tariff": 0.10, "op_hours_yr": 8400,
    "design_life_years": 20, "discount_rate": 5.0,
    "project_life_years": 20,
    "inflation_rate": 2.0,
    "escalation_energy_pct": 2.5,
    "escalation_maintenance_pct": 3.0,
    "tax_rate": 0.0,
    "depreciation_method": "straight_line",
    "depreciation_years": 20,
    "salvage_value_pct": 5.0,
    "maintenance_pct_capex": 2.0,
    "replacement_interval_media": 7.0,
    "replacement_interval_nozzles": 10.0,
    "replacement_interval_lining": 15.0,
    "annual_benefit_usd": 0.0,
    "steel_cost_usd_kg": 3.5,
    "erection_usd_per_kg_steel": 0.625, "labor_usd_per_kg_steel": 0.25,
    "piping_usd_vessel": 80000.0,
    "instrumentation_usd_vessel": 30000.0, "civil_usd_per_kg_working": 0.10,
    "engineering_pct": 12.0, "contingency_pct": 10.0,
    "media_replace_years": 7.0,
    "econ_media_gravel": 80.0, "econ_media_sand": 150.0,
    "econ_media_anthracite": 400.0,
    "nozzle_replace_years": 10.0, "nozzle_unit_cost": 15.0,
    "labour_usd_filter_yr": 5000.0, "chemical_cost_m3": 0.005,
    "grid_intensity": 0.45, "steel_carbon_kg": 1.85, "concrete_carbon_kg": 0.13,
    "media_co2": {"Fine sand": 0.006, "Anthracite": 0.150},
}


@pytest.fixture(scope="module")
def result():
    """Run compute_all once; share across all tests in this module."""
    return compute_all(_INPUTS)


# ═════════════════════════════════════════════════════════════════════════════
# Smoke — compute_all runs without error
# ═════════════════════════════════════════════════════════════════════════════

class TestSmoke:

    def test_no_exception(self, result):
        """compute_all must complete without raising any exception."""
        assert result is not None

    def test_returns_dict(self, result):
        """compute_all must return a dict."""
        assert isinstance(result, dict)

    def test_output_not_empty(self, result):
        """Result dict must have at least 30 keys (full pipeline executed)."""
        assert len(result) >= 30

    def test_required_top_level_keys_present(self, result):
        """Core output sections must all be present in the result dict."""
        for key in ["mech", "bw_exp", "bw_dp", "bw_hyd", "bw_col",
                    "load_data", "econ_capex", "econ_opex", "econ_carbon",
                    "econ_npv", "econ_financial", "feed_wp", "rho_feed", "q_per_filter", "env_structural"]:
            assert key in result, f"Missing key: {key}"

    def test_env_structural_wind_zero_when_no_wind(self, result):
        es = result["env_structural"]
        assert es["basic_wind_ms"] == 0.0
        assert es["wind_dynamic_pressure_pa"] == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# Process — filter loading
# ═════════════════════════════════════════════════════════════════════════════

class TestProcessIntegration:

    def test_n_scenario_flow(self, result):
        """N scenario: q_per_filter = 21 000 / 16 = 1 312.5 m³/h."""
        assert result["q_per_filter"] == pytest.approx(1312.5, rel=0.001)

    def test_load_data_n_scenario(self, result):
        """load_data[0] is the N scenario: 0 standby, 16 active, 1312.5 m³/h."""
        n_row = result["load_data"][0]
        assert n_row[0] == 0
        assert n_row[1] == 16
        assert n_row[2] == pytest.approx(1312.5, rel=0.001)

    def test_load_data_n_minus_1_scenario(self, result):
        """load_data[1] is the N-1 scenario: 1 standby, 15 active, 1400.0 m³/h."""
        n1_row = result["load_data"][1]
        assert n1_row[0] == 1
        assert n1_row[1] == 15
        assert n1_row[2] == pytest.approx(1400.0, rel=0.001)


# ═════════════════════════════════════════════════════════════════════════════
# Water properties propagated correctly
# ═════════════════════════════════════════════════════════════════════════════

class TestWaterPropertiesIntegration:

    def test_feed_density(self, result):
        """Feed water density (27°C, 35 ppt) ≈ 1 022.7 kg/m³."""
        assert result["rho_feed"] == pytest.approx(1022.7, rel=0.001)

    def test_feed_viscosity_positive(self, result):
        """Feed viscosity must be strictly positive."""
        assert result["mu_feed"] > 0

    def test_feed_wp_keys(self, result):
        """feed_wp sub-dict must contain density and viscosity keys."""
        wp = result["feed_wp"]
        assert "density_kg_m3" in wp
        assert "viscosity_pa_s" in wp


# ═════════════════════════════════════════════════════════════════════════════
# Mechanical — shell and geometry
# ═════════════════════════════════════════════════════════════════════════════

class TestMechanicalIntegration:

    def test_shell_min_thickness(self, result):
        """t_shell_min = 16.42 mm (ASME UG-27, consistent with test_mechanical)."""
        assert result["mech"]["t_shell_min_mm"] == pytest.approx(16.42, rel=0.02)

    def test_design_thickness_ge_min(self, result):
        """t_shell_design >= t_shell_min (corrosion allowance always applied)."""
        m = result["mech"]
        assert m["t_shell_design_mm"] >= m["t_shell_min_mm"]

    def test_od_formula_consistency(self, result):
        """OD = real_id + 2 × t_design / 1000."""
        m = result["mech"]
        expected_od = m["real_id_m"] + 2 * m["t_shell_design_mm"] / 1000.0
        assert m["od_m"] == pytest.approx(expected_od, rel=0.001)

    def test_real_id_with_lining(self, result):
        """lining=4 mm → real_id = 5.5 − 2×0.004 = 5.492 m."""
        assert result["mech"]["real_id_m"] == pytest.approx(5.492, rel=0.001)

    def test_cyl_len_plus_dishes(self, result):
        """
        Elliptic 2:1 head: h_dish = ID/4 = 5.5/4 = 1.375 m.
        Total O/O = cyl_len + 2×h_dish = 21.55 + 2×1.375 = 24.3 m.
        """
        assert result["cyl_len"] == pytest.approx(21.55, rel=0.001)
        assert result["h_dish"]  == pytest.approx(1.375, rel=0.001)


# ═════════════════════════════════════════════════════════════════════════════
# Backwash — bed expansion
# ═════════════════════════════════════════════════════════════════════════════

class TestBackwashIntegration:

    def test_settled_bed_equals_layer_sum(self, result):
        """Total settled = Gravel(0.20) + Fine sand(0.80) + Anthracite(0.80) = 1.80 m."""
        assert result["bw_exp"]["total_settled_m"] == pytest.approx(1.80, rel=0.001)

    def test_expanded_ge_settled(self, result):
        """Expanded bed height must be >= settled height."""
        assert result["bw_exp"]["total_expanded_m"] >= result["bw_exp"]["total_settled_m"]

    def test_bw_hydraulics_present(self, result):
        """BW hydraulics sub-dict must be computed."""
        assert result["bw_hyd"] is not None
        assert "q_bw_m3h" in result["bw_hyd"]

    def test_bw_q_positive(self, result):
        """BW flow must be positive."""
        assert result["bw_hyd"]["q_bw_m3h"] > 0

    def test_bw_hyd_air_nm3h_present(self, result):
        """Air blower flows reported as Nm³/h (normal) for SI display."""
        assert "q_air_nm3h" in result["bw_hyd"]
        assert "q_air_design_nm3h" in result["bw_hyd"]
        assert result["bw_hyd"]["q_air_nm3h"] > 0
        assert result["bw_sizing"]["q_air_design_nm3h"] == result["bw_hyd"]["q_air_design_nm3h"]

    def test_bw_timeline_present(self, result):
        """Duty window = bw_schedule_horizon_days × 24 h; feasibility trains; filter count."""
        tl = result["bw_timeline"]
        expected_h = float(_INPUTS["bw_schedule_horizon_days"]) * 24.0
        assert tl["horizon_h"] == pytest.approx(expected_h, rel=0.01)
        assert len(tl["filters"]) == 16
        assert tl.get("stagger_model") == "feasibility_trains"
        kt = int(tl.get("bw_trains") or 1)
        assert tl["peak_concurrent_bw"] >= 1
        assert tl["peak_concurrent_bw"] <= kt + 1


def test_air_scour_auto_expansion_solve():
    """Auto mode solves air rate from target expansion and sizes blower consistently."""
    inp = dict(_INPUTS)
    inp["air_scour_mode"] = "auto_expansion"
    inp["air_scour_target_expansion_pct"] = 12.0
    r = compute_all(inp)
    sol = r["air_scour_solve"]
    assert sol is not None
    assert sol["ok"] is True
    assert "nm3_m2_h" in sol
    assert "expansion_water_only_pct" in sol
    assert "combined_superficial_m_h" in sol
    assert 5.0 <= sol["expansion_at_velocity_pct"] <= 16.0
    assert r["bw_hyd"]["air_scour_rate_m_h"] == pytest.approx(sol["velocity_m_h"], rel=0.02)
    assert sol.get("objective") == "min_air_equivalent_at_target_expansion"
    assert "p_blower_motor_kw" in sol
    assert float(sol["p_blower_motor_kw"]) >= 0.0


def test_hydraulic_standby_n_plus_one_bank_and_timeline():
    """N+1 physical bank: q uses design N; duty chart has one row per physical filter."""
    inp = dict(_INPUTS)
    inp["n_filters"] = 17
    inp["hydraulic_assist"] = 1
    r = compute_all(inp)
    assert r["q_per_filter"] == pytest.approx(1312.5, rel=1e-4)
    assert len(r["bw_timeline"]["filters"]) == 17
    assert "hours_operating_ge_design_n_h" in r["bw_timeline"]
    assert "hours_operating_eq_design_n_h" in r["bw_timeline"]
    hsum = (
        r["bw_timeline"]["hours_operating_eq_design_n_h"]
        + r["bw_timeline"]["hours_operating_gt_design_n_h"]
        + r["bw_timeline"]["hours_operating_eq_n_minus_1_h"]
        + r["bw_timeline"]["hours_operating_below_n_minus_1_h"]
    )
    assert hsum == pytest.approx(float(r["bw_timeline"]["horizon_h"]), abs=0.1)


# ═════════════════════════════════════════════════════════════════════════════
# Economics — CAPEX, OPEX, carbon
# ═════════════════════════════════════════════════════════════════════════════

class TestEconomicsIntegration:

    def test_capex_total_positive(self, result):
        """Total CAPEX must be strictly positive."""
        assert result["econ_capex"]["total_capex_usd"] > 0

    def test_capex_total_gt_direct(self, result):
        """Total CAPEX > direct installed (indirect costs add to it)."""
        cap = result["econ_capex"]
        assert cap["total_capex_usd"] > cap["direct_installed_usd"]

    def test_opex_total_positive(self, result):
        """Annual OPEX must be strictly positive."""
        assert result["econ_opex"]["total_opex_usd_yr"] > 0

    def test_carbon_lifecycle_positive(self, result):
        """Lifecycle CO₂ must be strictly positive."""
        assert result["econ_carbon"]["co2_lifecycle_kg"] > 0

    def test_carbon_lifecycle_gt_construction(self, result):
        """
        For a 20-year life, operational CO₂ dominates construction CO₂.
        Lifecycle total must exceed the one-time construction component.
        """
        car = result["econ_carbon"]
        assert car["co2_lifecycle_kg"] > car["co2_construction_kg"]

    def test_capex_sum_of_parts(self, result):
        """total_capex = direct + engineering + contingency (consistency check)."""
        cap = result["econ_capex"]
        expected = (cap["direct_installed_usd"]
                    + cap["engineering_usd"]
                    + cap["contingency_usd"])
        assert cap["total_capex_usd"] == pytest.approx(expected, rel=0.001)
