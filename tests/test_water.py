"""
tests/test_water.py
───────────────────
Tests for engine/water.py — density and viscosity of water and
seawater validated against published reference values.

References
----------
Density  : Kell (1975) pure water; Millero & Poisson (1981) seawater
Viscosity: Korson et al. (1969) pure water;
           Sharqawy, Lienhard & Zubair (2010) seawater correction

Tolerance policy
----------------
  rel=0.001 (0.1%) for published correlation values
  rel=0.002 (0.2%) where the Millero polynomial has wider fit scatter
  rel=0.01  (1.0%) for viscosity (empirical correlation)
  Monotonicity checks: exact > / < only
"""
import pytest
from engine.water import water_properties


class TestDensity:

    def test_pure_water_4c(self):
        """
        Pure water at 4°C has maximum density ≈ 999.97 kg/m³.
        Engine (Kell 1975): 999.975 kg/m³  → within 0.005% of ref.
        Reference: CRC Handbook of Chemistry and Physics.
        """
        r = water_properties(temp_c=4.0, salinity_ppt=0.0)
        assert r["density_kg_m3"] == pytest.approx(999.97, rel=0.001)

    def test_pure_water_20c(self):
        """
        Pure water at 20°C: 998.20 kg/m³.
        Engine (Kell 1975): 998.206 kg/m³  → within 0.001%.
        Reference: Kell (1975).
        """
        r = water_properties(temp_c=20.0, salinity_ppt=0.0)
        assert r["density_kg_m3"] == pytest.approx(998.20, rel=0.001)

    def test_seawater_standard(self):
        """
        Standard seawater at 25°C, 35 ppt: 1023.3 kg/m³.
        Engine (Millero & Poisson 1981): 1023.343 kg/m³.
        Reference: Millero & Poisson (1981) Table 2.
        """
        r = water_properties(temp_c=25.0, salinity_ppt=35.0)
        assert r["density_kg_m3"] == pytest.approx(1023.3, rel=0.002)

    def test_density_increases_with_salinity(self):
        """Higher salinity → higher density at the same temperature."""
        r_low  = water_properties(27.0, 10.0)
        r_high = water_properties(27.0, 40.0)
        assert r_high["density_kg_m3"] > r_low["density_kg_m3"]

    def test_density_decreases_with_temperature(self):
        """Higher temperature → lower density (above 4°C for seawater)."""
        r_cold = water_properties(15.0, 35.0)
        r_warm = water_properties(35.0, 35.0)
        assert r_cold["density_kg_m3"] > r_warm["density_kg_m3"]

    def test_ro_reject_denser_than_feed(self):
        """
        SWRO reject (65 ppt, 29°C) must be denser than seawater feed
        (35 ppt, 27°C): higher salinity outweighs the slight temperature rise.
        """
        r_feed   = water_properties(27.0, 35.0)
        r_reject = water_properties(29.0, 65.0)
        assert r_reject["density_kg_m3"] > r_feed["density_kg_m3"]

    def test_tds_is_salinity_times_density(self):
        """
        TDS (mg/L) = salinity_ppt × density_kg_m3.
        Exact by definition of the engine formula: tds = round(S × rho, 1).
        Checked with S=35, T=27°C: tds = 35 × 1022.72 = 35795.2 mg/L.
        Tolerance 0.1% covers rounding of density to 3 decimal places.
        """
        r = water_properties(27.0, 35.0)
        expected_tds = 35.0 * r["density_kg_m3"]
        assert r["tds_mg_l"] == pytest.approx(expected_tds, rel=0.001)

    def test_fresh_water_tds_is_zero(self):
        """Zero salinity → TDS = 0 mg/L."""
        r = water_properties(25.0, 0.0)
        assert r["tds_mg_l"] == 0.0


class TestViscosity:

    def test_pure_water_20c(self):
        """
        Pure water at 20°C: μ = 1.002 mPa·s = 1.002 cP.
        Engine (Korson et al.): 1.0018 cP  → within 0.02%.
        Reference: Korson, Drost-Hansen & Millero (1969).
        """
        r = water_properties(20.0, 0.0)
        assert r["viscosity_cp"] == pytest.approx(1.002, rel=0.01)

    def test_viscosity_decreases_with_temperature(self):
        """Higher temperature → lower dynamic viscosity (liquid water)."""
        r_cold = water_properties(15.0, 35.0)
        r_warm = water_properties(35.0, 35.0)
        assert r_cold["viscosity_pa_s"] > r_warm["viscosity_pa_s"]

    def test_viscosity_increases_with_salinity(self):
        """Higher salinity → slightly higher viscosity at same temperature."""
        r_fresh = water_properties(27.0, 0.0)
        r_salt  = water_properties(27.0, 35.0)
        assert r_salt["viscosity_pa_s"] > r_fresh["viscosity_pa_s"]

    def test_cp_vs_pa_s_consistency(self):
        """
        viscosity_cp = viscosity_pa_s × 1000.
        Checked at 27°C, 35 ppt: 0.000900 Pa·s = 0.9000 cP (±rounding).
        """
        r = water_properties(27.0, 35.0)
        assert r["viscosity_cp"] == pytest.approx(
            r["viscosity_pa_s"] * 1000.0, rel=0.001)

    def test_viscosity_always_positive(self):
        """Viscosity must be positive for all valid T and S combinations."""
        for T in [0, 15, 27, 40]:
            for S in [0, 35, 65]:
                r = water_properties(T, S)
                assert r["viscosity_pa_s"] > 0, f"Non-positive μ at T={T}, S={S}"

    def test_output_keys_present(self):
        """All expected keys must be present in the returned dict."""
        r = water_properties(27.0, 35.0)
        for k in ["temp_c", "salinity_ppt", "density_kg_m3",
                  "viscosity_pa_s", "viscosity_cp", "tds_mg_l"]:
            assert k in r, f"Missing key: {k}"

    def test_input_passthrough(self):
        """Returned temp_c and salinity_ppt must match inputs."""
        r = water_properties(27.0, 35.0)
        assert r["temp_c"] == 27.0
        assert r["salinity_ppt"] == 35.0
