"""
tests/test_units.py
───────────────────
Pure-Python regression tests for engine/units.py.

All expected values are hand-calculated from the exact conversion factors
defined in QUANTITIES — no external reference needed for multiplicative cases.
Temperature °C↔°F uses the textbook formula (×9/5 + 32 / ×5/9 − 32×5/9).

Tolerances
----------
rel=1e-6  for exact multiplicative round-trips (factor × back_factor ≈ 1)
rel=1e-9  for exact formula results (no floating-point accumulation)
abs=1e-10 for zero / near-zero values
"""
import pytest
from engine.units import (
    UNIT_SYSTEMS,
    QUANTITIES,
    display_value,
    si_value,
    unit_label,
    format_value,
    convert_inputs,
    INPUT_QUANTITY_MAP,
)


# ─────────────────────────────────────────────────────────────────────────────
# Catalogue sanity
# ─────────────────────────────────────────────────────────────────────────────

class TestCatalogue:

    def test_unit_systems_list(self):
        assert UNIT_SYSTEMS == ["metric", "imperial"]

    def test_quantities_not_empty(self):
        assert len(QUANTITIES) >= 10

    def test_every_quantity_has_four_fields(self):
        for key, entry in QUANTITIES.items():
            assert len(entry) == 4, f"{key}: expected 4-tuple"

    def test_metric_labels_are_strings(self):
        for key, (metric_lbl, _, _, _) in QUANTITIES.items():
            assert isinstance(metric_lbl, str), f"{key} metric label not str"

    def test_imperial_labels_are_strings(self):
        for key, (_, imperial_lbl, _, _) in QUANTITIES.items():
            assert isinstance(imperial_lbl, str), f"{key} imperial label not str"

    def test_dimensionless_factors_are_one(self):
        _, _, fwd, back = QUANTITIES["dimensionless"]
        assert fwd == 1.0 and back == 1.0

    def test_cost_factors_are_one(self):
        _, _, fwd, back = QUANTITIES["cost_usd"]
        assert fwd == 1.0 and back == 1.0

    def test_temperature_factors_are_none(self):
        _, _, fwd, back = QUANTITIES["temperature_c"]
        assert fwd is None and back is None


# ─────────────────────────────────────────────────────────────────────────────
# display_value — metric passthrough
# ─────────────────────────────────────────────────────────────────────────────

class TestDisplayValueMetric:

    def test_flow_metric_passthrough(self):
        assert display_value(1312.5, "flow_m3h", "metric") == 1312.5

    def test_pressure_metric_passthrough(self):
        assert display_value(7.0, "pressure_bar", "metric") == 7.0

    def test_length_metric_passthrough(self):
        assert display_value(5.5, "length_m", "metric") == 5.5

    def test_temperature_metric_passthrough(self):
        assert display_value(27.0, "temperature_c", "metric") == 27.0

    def test_none_value_returns_none(self):
        assert display_value(None, "flow_m3h", "metric") is None

    def test_none_value_imperial_returns_none(self):
        assert display_value(None, "flow_m3h", "imperial") is None

    def test_unknown_quantity_passthrough(self):
        assert display_value(99.9, "no_such_qty", "imperial") == 99.9


# ─────────────────────────────────────────────────────────────────────────────
# display_value — imperial conversions (hand-calculated)
# ─────────────────────────────────────────────────────────────────────────────

class TestDisplayValueImperial:

    def test_flow_m3h_to_gpm(self):
        # 1 m³/h × 4.40287 = 4.40287 gpm
        assert display_value(1.0, "flow_m3h", "imperial") == pytest.approx(4.40287, rel=1e-6)

    def test_flow_21000_m3h_to_gpm(self):
        # 21 000 m³/h × 4.40287 = 92 460.27 gpm
        assert display_value(21000.0, "flow_m3h", "imperial") == pytest.approx(92460.27, rel=1e-4)

    def test_velocity_m_h_to_gpm_ft2(self):
        # 30 m/h × 0.40746 = 12.2238 gpm/ft²
        assert display_value(30.0, "velocity_m_h", "imperial") == pytest.approx(12.2238, rel=1e-4)

    def test_pressure_bar_to_psi(self):
        # 7 bar × 14.5038 = 101.5266 psi
        assert display_value(7.0, "pressure_bar", "imperial") == pytest.approx(101.5266, rel=1e-4)

    def test_pressure_mwc_to_ft_wc(self):
        # 15 mWC × 3.28084 = 49.2126 ft WC
        assert display_value(15.0, "pressure_mwc", "imperial") == pytest.approx(49.2126, rel=1e-4)

    def test_length_m_to_ft(self):
        # 5.5 m × 3.28084 = 18.04462 ft
        assert display_value(5.5, "length_m", "imperial") == pytest.approx(18.04462, rel=1e-5)

    def test_length_mm_to_in(self):
        # 25.4 mm × 0.039370 = 1.0000 in
        assert display_value(25.4, "length_mm", "imperial") == pytest.approx(1.0, rel=1e-4)

    def test_area_m2_to_ft2(self):
        # 1 m² × 10.7639 = 10.7639 ft²
        assert display_value(1.0, "area_m2", "imperial") == pytest.approx(10.7639, rel=1e-5)

    def test_mass_kg_to_lb(self):
        # 1 kg × 2.20462 = 2.20462 lb
        assert display_value(1.0, "mass_kg", "imperial") == pytest.approx(2.20462, rel=1e-5)

    def test_power_kw_to_hp(self):
        # 100 kW × 1.34102 = 134.102 hp
        assert display_value(100.0, "power_kw", "imperial") == pytest.approx(134.102, rel=1e-5)

    def test_temperature_0c_to_32f(self):
        assert display_value(0.0, "temperature_c", "imperial") == pytest.approx(32.0, abs=1e-10)

    def test_temperature_100c_to_212f(self):
        assert display_value(100.0, "temperature_c", "imperial") == pytest.approx(212.0, abs=1e-10)

    def test_temperature_27c_to_80p6f(self):
        # 27 × 9/5 + 32 = 80.6 °F
        assert display_value(27.0, "temperature_c", "imperial") == pytest.approx(80.6, abs=1e-9)

    def test_concentration_mg_l_unchanged(self):
        assert display_value(10.0, "concentration_mg_l", "imperial") == 10.0

    def test_cost_usd_unchanged(self):
        assert display_value(1000.0, "cost_usd", "imperial") == 1000.0


# ─────────────────────────────────────────────────────────────────────────────
# si_value — back-conversions
# ─────────────────────────────────────────────────────────────────────────────

class TestSiValue:

    def test_metric_passthrough(self):
        assert si_value(1312.5, "flow_m3h", "metric") == 1312.5

    def test_gpm_to_m3h(self):
        # 4.40287 gpm × 0.22712 = 1.0 m³/h (approx)
        assert si_value(4.40287, "flow_m3h", "imperial") == pytest.approx(1.0, rel=1e-3)

    def test_psi_to_bar(self):
        # 14.5038 psi × 0.068948 ≈ 1.0 bar
        assert si_value(14.5038, "pressure_bar", "imperial") == pytest.approx(1.0, rel=1e-3)

    def test_ft_to_m(self):
        # 3.28084 ft × 0.30480 ≈ 1.0 m
        assert si_value(3.28084, "length_m", "imperial") == pytest.approx(1.0, rel=1e-4)

    def test_temperature_32f_to_0c(self):
        assert si_value(32.0, "temperature_c", "imperial") == pytest.approx(0.0, abs=1e-10)

    def test_temperature_212f_to_100c(self):
        assert si_value(212.0, "temperature_c", "imperial") == pytest.approx(100.0, abs=1e-9)

    def test_temperature_80p6f_to_27c(self):
        assert si_value(80.6, "temperature_c", "imperial") == pytest.approx(27.0, abs=1e-9)

    def test_none_returns_none(self):
        assert si_value(None, "flow_m3h", "imperial") is None

    def test_unknown_quantity_passthrough(self):
        assert si_value(42.0, "no_such_qty", "imperial") == 42.0


# ─────────────────────────────────────────────────────────────────────────────
# Round-trip accuracy (display → SI → display)
# ─────────────────────────────────────────────────────────────────────────────

class TestRoundTrip:

    @pytest.mark.parametrize("qty,val", [
        ("flow_m3h",      21000.0),
        ("velocity_m_h",  30.0),
        ("pressure_bar",  7.0),
        ("pressure_mwc",  15.0),
        ("length_m",      5.5),
        ("length_mm",     25.4),
        ("area_m2",       23.75),
        ("volume_m3",     100.0),
        ("mass_kg",       5000.0),
        ("power_kw",      250.0),
        ("density_kg_m3", 1022.7),
    ])
    def test_si_display_si_roundtrip(self, qty, val):
        disp = display_value(val, qty, "imperial")
        back = si_value(disp, qty, "imperial")
        assert back == pytest.approx(val, rel=1e-3)

    def test_temperature_roundtrip_27c(self):
        f = display_value(27.0, "temperature_c", "imperial")
        c = si_value(f, "temperature_c", "imperial")
        assert c == pytest.approx(27.0, abs=1e-9)

    def test_temperature_roundtrip_minus_10c(self):
        f = display_value(-10.0, "temperature_c", "imperial")
        c = si_value(f, "temperature_c", "imperial")
        assert c == pytest.approx(-10.0, abs=1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# unit_label
# ─────────────────────────────────────────────────────────────────────────────

class TestUnitLabel:

    def test_flow_metric(self):
        assert unit_label("flow_m3h", "metric") == "m³/h"

    def test_flow_imperial(self):
        assert unit_label("flow_m3h", "imperial") == "gpm"

    def test_velocity_metric(self):
        assert unit_label("velocity_m_h", "metric") == "m/h"

    def test_velocity_imperial(self):
        assert unit_label("velocity_m_h", "imperial") == "gpm/ft²"

    def test_pressure_metric(self):
        assert unit_label("pressure_bar", "metric") == "bar"

    def test_pressure_imperial(self):
        assert unit_label("pressure_bar", "imperial") == "psi"

    def test_length_metric(self):
        assert unit_label("length_m", "metric") == "m"

    def test_length_imperial(self):
        assert unit_label("length_m", "imperial") == "ft"

    def test_temperature_metric(self):
        assert unit_label("temperature_c", "metric") == "°C"

    def test_temperature_imperial(self):
        assert unit_label("temperature_c", "imperial") == "°F"

    def test_power_metric(self):
        assert unit_label("power_kw", "metric") == "kW"

    def test_power_imperial(self):
        assert unit_label("power_kw", "imperial") == "hp"

    def test_unknown_quantity_returns_empty(self):
        assert unit_label("no_such_qty", "metric") == ""
        assert unit_label("no_such_qty", "imperial") == ""


# ─────────────────────────────────────────────────────────────────────────────
# format_value
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatValue:

    def test_none_returns_dash(self):
        assert format_value(None, "flow_m3h") == "—"

    def test_metric_flow_default_decimals(self):
        result = format_value(1312.5, "flow_m3h", "metric", 1)
        assert "1,312.5" in result
        assert "m³/h" in result

    def test_imperial_flow_contains_gpm(self):
        result = format_value(1.0, "flow_m3h", "imperial", 2)
        assert "gpm" in result

    def test_metric_pressure_bar(self):
        result = format_value(7.0, "pressure_bar", "metric", 2)
        assert "7.00" in result
        assert "bar" in result

    def test_imperial_pressure_psi(self):
        result = format_value(7.0, "pressure_bar", "imperial", 2)
        assert "psi" in result

    def test_temperature_metric(self):
        result = format_value(27.0, "temperature_c", "metric", 1)
        assert "27.0" in result
        assert "°C" in result

    def test_temperature_imperial(self):
        result = format_value(27.0, "temperature_c", "imperial", 1)
        assert "80.6" in result
        assert "°F" in result

    def test_dimensionless_no_label(self):
        result = format_value(0.75, "dimensionless", "metric", 2)
        assert "0.75" in result


# ─────────────────────────────────────────────────────────────────────────────
# convert_inputs
# ─────────────────────────────────────────────────────────────────────────────

class TestConvertInputs:

    _BASE = {
        "total_flow":         92460.0,   # gpm  → should become ~21 000 m³/h
        "nominal_id":         18.044,    # ft   → should become ~5.5 m
        "feed_temp":          80.6,      # °F   → should become ~27 °C
        "design_pressure":    101.526,   # psi  → should become ~7 bar
        "corrosion":          0.059,     # in   → should become ~1.5 mm
        "lining_mm":          0.157,     # in   → should become ~4 mm
        "bw_velocity":        12.224,    # gpm/ft² → should become ~30 m/h
        "air_scour_rate":     22.410,    # gpm/ft² → should become ~55 m/h
        "n_filters":          16,        # dimensionless — must pass unchanged
        "streams":            1,         # dimensionless — must pass unchanged
        "some_other_key":     "hello",   # non-numeric — must pass unchanged
    }

    def test_metric_returns_copy_unchanged(self):
        result = convert_inputs(self._BASE, "metric")
        assert result["total_flow"] == self._BASE["total_flow"]
        assert result is not self._BASE

    def test_imperial_converts_flow(self):
        result = convert_inputs(self._BASE, "imperial")
        assert result["total_flow"] == pytest.approx(21000.0, rel=0.01)

    def test_imperial_converts_length(self):
        result = convert_inputs(self._BASE, "imperial")
        assert result["nominal_id"] == pytest.approx(5.5, rel=0.01)

    def test_imperial_converts_temperature(self):
        result = convert_inputs(self._BASE, "imperial")
        assert result["feed_temp"] == pytest.approx(27.0, abs=0.1)

    def test_imperial_converts_pressure(self):
        result = convert_inputs(self._BASE, "imperial")
        assert result["design_pressure"] == pytest.approx(7.0, rel=0.01)

    def test_imperial_converts_length_mm(self):
        result = convert_inputs(self._BASE, "imperial")
        assert result["corrosion"] == pytest.approx(1.5, rel=0.01)

    def test_imperial_converts_velocity(self):
        result = convert_inputs(self._BASE, "imperial")
        assert result["bw_velocity"] == pytest.approx(30.0, rel=0.01)

    def test_non_mapped_key_passes_unchanged(self):
        result = convert_inputs(self._BASE, "imperial")
        assert result["n_filters"] == 16
        assert result["streams"] == 1
        assert result["some_other_key"] == "hello"

    def test_does_not_modify_original(self):
        original_flow = self._BASE["total_flow"]
        convert_inputs(self._BASE, "imperial")
        assert self._BASE["total_flow"] == original_flow

    def test_input_quantity_map_completeness(self):
        for key in INPUT_QUANTITY_MAP:
            assert INPUT_QUANTITY_MAP[key] in QUANTITIES, \
                f"{key} maps to {INPUT_QUANTITY_MAP[key]} which is not in QUANTITIES"
