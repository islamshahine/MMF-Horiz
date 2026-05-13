"""
tests/test_backwash.py
──────────────────────
Tests for engine/backwash.py — bed expansion, minimum fluidisation
velocity, Ergun pressure drop, BW hydraulics, and collector check.

Reference calculations
----------------------
Wen & Yu (1966) u_mf:
  Ar = d10³ × ρ_f × (ρ_p − ρ_f) × g / μ²
  Re_mf = √(33.7² + 0.0408 × Ar) − 33.7
  u_mf = Re_mf × μ / (ρ_f × d10)

Fine sand (d10=0.8 mm, ρ_p=2650, ρ_f=1025, μ=0.000851 Pa·s at 27°C):
  Ar = (8e-4)³ × 1025 × 1625 × 9.81 / (8.51e-4)²
     = 5.12e-10 × 16,343,963 / 7.242e-7 = 11 546
  Re_mf = √(1135.7 + 471.1) − 33.7 = 40.1 − 33.7 = 6.38
  u_mf = 6.38 × 8.51e-4 / (1025 × 8e-4) = 6.63e-3 m/s = 23.9 m/h  ✓

Richardson–Zaki mass balance:
  L₀(1 − ε₀) = Lf(1 − εf)  [solid volume conserved]

Ergun bar / mWC consistency:
  1 bar = 10⁵ Pa = 10⁵ / (ρ × g) m H₂O
  ratio = ρ × g / 10⁵ = 1025 × 9.81 / 10⁵ = 0.10055

Tolerances: rel=0.05 for u_mf (Wen & Yu curve fit ±5%),
            rel=0.02 for Ergun/R-Z, rel=0.001 for exact formulas.
"""
import pytest
from engine.backwash import (
    layer_expansion,
    bed_expansion,
    pressure_drop,
    backwash_hydraulics,
    collector_check,
    solve_equivalent_velocity_for_target_expansion_pct,
    actual_m3m2h_to_nm3_m2h,
    filter_bw_timeline_24h,
)


# ── Shared layer kwargs ───────────────────────────────────────────────────────

def _sand_kwargs(bw_m_h=30.0):
    return dict(depth_m=0.80, epsilon0=0.42, d10_mm=0.8, rho_p=2650,
                bw_velocity_m_h=bw_m_h, cu=1.3,
                water_temp_c=27.0, rho_water=1025.0)

def _gravel_kwargs(bw_m_h=30.0):
    return dict(depth_m=0.20, epsilon0=0.46, d10_mm=6.0, rho_p=2600,
                bw_velocity_m_h=bw_m_h, cu=1.0,
                water_temp_c=27.0, rho_water=1025.0)

def _anthracite_kwargs(bw_m_h=30.0):
    return dict(depth_m=0.80, epsilon0=0.48, d10_mm=1.3, rho_p=1450,
                bw_velocity_m_h=bw_m_h, cu=1.5,
                water_temp_c=27.0, rho_water=1025.0)


# ═════════════════════════════════════════════════════════════════════════════
# Minimum fluidisation velocity (Wen & Yu 1966)
# ═════════════════════════════════════════════════════════════════════════════

class TestMinimumFluidisation:

    def test_sand_umf_value(self):
        """
        Fine sand u_mf (Wen & Yu) at 27°C ≈ 23.9 m/h.
        Hand calc: Ar=11 546, Re_mf=6.38 → u_mf=23.9 m/h.
        Engine: 23.86 m/h — within 5% tolerance.
        """
        r = layer_expansion(**_sand_kwargs())
        assert r["u_mf_m_h"] == pytest.approx(23.9, rel=0.05)

    def test_sand_umf_below_bw_rate(self):
        """BW=30 m/h > u_mf=23.9 m/h → sand must fluidise."""
        r = layer_expansion(**_sand_kwargs())
        assert r["u_mf_m_h"] < 30.0
        assert r["fluidised"] is True

    def test_gravel_not_fluidised_at_30_mh(self):
        """
        Gravel d10=6 mm: u_mf >> 30 m/h (engine: 202.5 m/h).
        Gravel never fluidises at typical BW rates.
        """
        r = layer_expansion(**_gravel_kwargs())
        assert r["u_mf_m_h"] > 100.0
        assert r["fluidised"] is False
        assert r["expansion_pct"] == 0.0

    def test_anthracite_umf_value(self):
        """
        Anthracite d10=1.3 mm, ρ=1450 kg/m³ (low density).
        u_mf ≈ 16.3 m/h — fluidises easily at 30 m/h.
        Engine: 16.32 m/h — within 10% tolerance.
        """
        r = layer_expansion(**_anthracite_kwargs())
        assert r["u_mf_m_h"] == pytest.approx(16.3, rel=0.10)
        assert r["u_mf_m_h"] < 30.0
        assert r["fluidised"] is True


# ═════════════════════════════════════════════════════════════════════════════
# Bed expansion (Richardson–Zaki)
# ═════════════════════════════════════════════════════════════════════════════

class TestBedExpansion:

    def test_sand_expands_at_30_mh(self):
        """Fine sand at BW=30 m/h expands 7.1% — expanded > settled."""
        r = layer_expansion(**_sand_kwargs())
        assert r["fluidised"] is True
        assert r["expansion_pct"] > 0.0
        assert r["depth_expanded_m"] > r["depth_settled_m"]

    def test_mass_balance_solid_volume_conserved(self):
        """
        Richardson–Zaki invariant: L₀(1−ε₀) = Lf(1−εf).
        Solid volume must be conserved during expansion.
        Checked: settled=0.464 m³/m², expanded=0.4640 m³/m² (±0.1%).
        """
        r = layer_expansion(**_sand_kwargs())
        solid_settled  = r["depth_settled_m"]  * (1.0 - r["epsilon0"])
        solid_expanded = r["depth_expanded_m"] * (1.0 - r["eps_f"])
        assert solid_settled == pytest.approx(solid_expanded, rel=0.001)

    def test_expansion_increases_with_bw_rate(self):
        """Higher BW rate → more expansion once above u_mf."""
        r30 = layer_expansion(**_sand_kwargs(30.0))
        r40 = layer_expansion(**_sand_kwargs(40.0))
        r50 = layer_expansion(**_sand_kwargs(50.0))
        assert r30["expansion_pct"] < r40["expansion_pct"] < r50["expansion_pct"]

    def test_no_expansion_below_umf(self):
        """Gravel: BW=30 m/h < u_mf → expansion exactly 0%."""
        r = layer_expansion(**_gravel_kwargs())
        assert r["expansion_pct"] == 0.0
        assert r["depth_expanded_m"] == pytest.approx(
            r["depth_settled_m"])

    def test_degenerate_zero_d10_no_crash(self):
        """
        d10=0 (Custom preset default) must not raise — returns
        expansion=0% and a non-empty warning string.
        """
        r = layer_expansion(depth_m=0.5, epsilon0=0.42, d10_mm=0.0,
                            rho_p=2650, bw_velocity_m_h=30.0)
        assert r["expansion_pct"] == 0.0
        assert r["warning"] != ""

    def test_bed_expansion_total_settled_equals_sum(self, standard_layers):
        """
        bed_expansion() total settled = sum of individual layer depths.
        Gravel(0.20) + Fine Sand(0.80) + Anthracite(0.80) = 1.80 m.
        """
        result = bed_expansion(standard_layers, 30.0, 27.0, 1025.0)
        assert result["total_settled_m"] == pytest.approx(1.80, rel=0.001)

    def test_bed_expansion_expanded_ge_settled(self, standard_layers):
        """Total expanded bed height >= total settled height."""
        result = bed_expansion(standard_layers, 30.0, 27.0, 1025.0)
        assert result["total_expanded_m"] >= result["total_settled_m"]


# ═════════════════════════════════════════════════════════════════════════════
# Ergun pressure drop
# ═════════════════════════════════════════════════════════════════════════════

class TestErgunPressureDrop:

    def test_dp_all_positive(self, standard_layers):
        """All three DP values (clean, moderate, dirty) must be positive."""
        r = pressure_drop(standard_layers, 1312.5, 120.0)
        assert r["dp_clean_bar"] > 0
        assert r["dp_moderate_bar"] > 0
        assert r["dp_dirty_bar"] > 0

    def test_dirty_gt_moderate_gt_clean(self, standard_layers):
        """
        Clogging reduces voidage → higher resistance.
        dirty (low voidage) > moderate > clean (full voidage).
        """
        r = pressure_drop(standard_layers, 1312.5, 120.0)
        assert r["dp_clean_bar"] < r["dp_moderate_bar"] < r["dp_dirty_bar"]

    def test_dp_increases_with_flow(self, standard_layers):
        """Higher superficial velocity → higher clean-bed Ergun ΔP."""
        r_low  = pressure_drop(standard_layers,  800.0, 120.0)
        r_high = pressure_drop(standard_layers, 1500.0, 120.0)
        assert r_high["dp_clean_bar"] > r_low["dp_clean_bar"]

    def test_mwc_bar_consistency(self, standard_layers):
        """
        ΔP_bar / ΔP_mWC = ρ_water × g / 10⁵.
        At ρ=1025 kg/m³, g=9.81: ratio = 0.10055.
        Engine: 0.0262 bar / 0.261 mWC = 0.10054 — within 0.1%.
        """
        r = pressure_drop(standard_layers, 1312.5, 120.0, rho_water=1025.0)
        ratio = r["dp_clean_bar"] / r["dp_clean_mwc"]
        assert ratio == pytest.approx(1025 * 9.81 / 1e5, rel=0.01)

    def test_dp_outputs_all_units_present(self, standard_layers):
        """Result must contain bar, mWC, and kPa variants."""
        r = pressure_drop(standard_layers, 1312.5, 120.0)
        for key in ["dp_clean_bar", "dp_clean_mwc", "dp_clean_kpa",
                    "dp_moderate_bar", "dp_dirty_bar"]:
            assert key in r, f"Missing key: {key}"


# ═════════════════════════════════════════════════════════════════════════════
# BW hydraulics
# ═════════════════════════════════════════════════════════════════════════════

class TestBackwashHydraulics:

    def test_bw_rate_governs(self):
        """
        BW rate × area = 30 × 120 = 3600 m³/h.
        2 × filtration flow = 2 × 1312.5 = 2625 m³/h.
        Rate governs (3600 > 2625).
        """
        r = backwash_hydraulics(
            filter_area_m2=120.0, bw_rate_m_h=30.0,
            filtration_flow_m3h=1312.5)
        assert r["q_bw_m3h"] == pytest.approx(3600.0)
        assert r["bw_governs"] == "BW rate × area"

    def test_2x_flow_governs(self):
        """
        BW rate × area = 30 × 120 = 3600 m³/h.
        2 × filtration flow = 2 × 2000 = 4000 m³/h.
        2× flow governs (4000 > 3600).
        """
        r = backwash_hydraulics(
            filter_area_m2=120.0, bw_rate_m_h=30.0,
            filtration_flow_m3h=2000.0)
        assert r["q_bw_m3h"] == pytest.approx(4000.0)
        assert r["bw_governs"] == "2 × filtration flow"

    def test_design_flow_includes_safety_factor(self):
        """
        Design flow = governing flow × safety factor.
        3600 × 1.10 = 3960 m³/h.
        """
        r = backwash_hydraulics(120.0, 30.0, 55.0, 1312.5,
                                bw_safety_factor=1.10)
        assert r["q_bw_design_m3h"] == pytest.approx(
            r["q_bw_m3h"] * 1.10, rel=0.001)


# ═════════════════════════════════════════════════════════════════════════════
# Collector height check
# ═════════════════════════════════════════════════════════════════════════════

class TestCollectorCheck:

    def test_generous_freeboard_is_ok(self, standard_layers):
        """
        Nozzle plate at 1.0 m, settled bed top = 1.0 + 1.80 = 2.80 m.
        Collector at 4.5 m → freeboard = 4.5 − 2.884 = 1.616 m >> 200 mm.
        Engine: freeboard=1.616 m, media_loss_risk=False, status='OK'.
        """
        r = collector_check(standard_layers, 1.0, 4.5, 30.0, 27.0, 1025.0)
        assert r["freeboard_m"] > 0.20
        assert r["media_loss_risk"] is False
        assert "OK" in r["status"]

    def test_collector_too_low_triggers_risk(self, standard_layers):
        """
        Collector at 1.5 m < settled bed top 2.8 m.
        Even without expansion, bed is above collector → media loss risk.
        """
        r = collector_check(standard_layers, 1.0, 1.5, 30.0, 27.0, 1025.0)
        assert r["media_loss_risk"] is True

    def test_max_safe_bw_is_positive_for_viable_geometry(self, standard_layers):
        """
        Collector at 4.2 m (> expanded top 2.884 m).
        Binary search for max safe BW must find a positive result.
        Engine: max_safe_bw=119.4 m/h.
        """
        r = collector_check(standard_layers, 1.0, 4.2, 30.0, 27.0, 1025.0)
        assert r["max_safe_bw_m_h"] > 0

    def test_freeboard_decreases_as_bw_increases(self, standard_layers):
        """Higher BW rate → more expansion → less freeboard."""
        r30 = collector_check(standard_layers, 1.0, 4.2, 30.0)
        r50 = collector_check(standard_layers, 1.0, 4.2, 50.0)
        assert r50["freeboard_m"] < r30["freeboard_m"]


# ═════════════════════════════════════════════════════════════════════════════
# Air scour auto-size & duty timeline
# ═════════════════════════════════════════════════════════════════════════════

class TestAirScourSolveAndTimeline:

    def test_solve_hits_target_sand_stack(self, standard_layers):
        tgt = 15.0
        sol = solve_equivalent_velocity_for_target_expansion_pct(
            standard_layers, tgt, water_temp_c=27.0, rho_water=1025.0,
        )
        assert sol["ok"]
        assert sol["velocity_m_h"] > 0
        assert abs(sol["expansion_at_velocity_pct"] - tgt) < 2.5

    def test_nm3_conversion_order_of_magnitude(self):
        q = 55.0
        nm = actual_m3m2h_to_nm3_m2h(q, 30.0, 0.0)
        assert nm > 0
        assert 40.0 < nm < q

    def test_timeline_peak_and_rows(self):
        tl = filter_bw_timeline_24h(4, t_cycle_h=8.0, bw_duration_h=38 / 60.0)
        assert len(tl["filters"]) == 4
        assert tl["peak_concurrent_bw"] >= 1
        assert tl["horizon_h"] == 24.0
