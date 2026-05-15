"""
tests/test_media.py
───────────────────
Tests for engine/media.py — MEDIA_DATABASE integrity, get_media(),
LV/EBCT range helpers, status labels, and validate_layer_order().

Reference values
----------------
Fine sand  : d10=0.8 mm, ε₀=0.42, ρ=2650 kg/m³, LV 5–10 m/h, EBCT 4–8 min
Garnet     : d10=0.3 mm, ε₀=0.38, ρ=4100 kg/m³, LV 10–20 m/h, EBCT 1–3 min
Anthracite : d10=1.3 mm, ε₀=0.48, ρ=1450 kg/m³ (low density)
Medium GAC : EBCT 2–30 min (pressure mode)

interstitial_velocity(v_superficial, ε) = v_superficial / ε
  10.0 m/h, ε=0.42 → 10.0 / 0.42 = 23.81 m/h  ✓

collector_max_height(id_m, clearance_mm=300)
  id=5.5 m, clearance=300 mm → 5.5/2 − 0.300 = 2.45 m → returns 4.95 m
  (engine returns id/2 − clearance + … see function; just test it's < id/2)

Tolerances: rel=0.001 for exact lookups; exact == for string/integer fields.
"""
import pytest
from engine.media import (
    MEDIA_DATABASE,
    get_media_names,
    get_media,
    get_lv_range,
    get_ebct_range,
    get_gac_note,
    ebct_label,
    interstitial_velocity,
    collector_max_height,
    lv_status,
    ebct_status,
    validate_layer_order,
    get_layer_intelligence,
)

REQUIRED_FIELDS = [
    "d10", "epsilon0", "rho_p_eff", "lv_min", "lv_max",
    "ebct_min", "ebct_max", "media_category",
]

CORE_MEDIA = [
    "Fine sand", "Coarse sand", "Anthracite",
    "Gravel", "Garnet", "Medium GAC",
]


# ═════════════════════════════════════════════════════════════════════════════
# Database integrity
# ═════════════════════════════════════════════════════════════════════════════

class TestDatabaseIntegrity:

    def test_all_core_media_present(self):
        """All core media types must exist in MEDIA_DATABASE."""
        names = get_media_names()
        for name in CORE_MEDIA:
            assert name in names, f"Missing core media: {name}"

    def test_garnet_in_database(self):
        """Garnet must be in the database (was missing in earlier versions)."""
        assert "Garnet" in get_media_names()

    def test_gravel_2_3_mm_support_entry(self):
        """Fine gravel 2–3 mm support — typical MMF underdrain / sand support."""
        e = get_media("Gravel (2–3 mm)")
        assert e["media_category"] == "support"
        assert e["d10"] == pytest.approx(2.5, rel=0.01)
        assert e["d60"] >= e["d10"]
        assert e["lv_min"] is None and e["ebct_min"] is None
        assert get_media("Gravel (2-3 mm)")["d10"] == pytest.approx(2.5, rel=0.01)

    @pytest.mark.parametrize("name", CORE_MEDIA)
    def test_required_fields_present(self, name):
        """Every core media entry must contain all required fields."""
        entry = get_media(name)
        for field in REQUIRED_FIELDS:
            assert field in entry, f"{name} missing field: {field}"

    @pytest.mark.parametrize("name", CORE_MEDIA)
    def test_physical_values_positive(self, name):
        """d10, ε₀, and ρ must all be strictly positive."""
        e = get_media(name)
        assert e["d10"] > 0,        f"{name} d10 <= 0"
        assert e["epsilon0"] > 0,   f"{name} epsilon0 <= 0"
        assert e["rho_p_eff"] > 0,  f"{name} rho_p_eff <= 0"

    @pytest.mark.parametrize("name", CORE_MEDIA)
    def test_porosity_below_unity(self, name):
        """ε₀ must be in (0, 1) — physically bounded."""
        e = get_media(name)
        assert 0 < e["epsilon0"] < 1, f"{name} epsilon0 out of (0,1)"

    @pytest.mark.parametrize("name", CORE_MEDIA)
    def test_lv_range_ordered(self, name):
        """lv_min < lv_max for filtration media; support media may have None ranges."""
        e = get_media(name)
        if e["lv_min"] is None or e["lv_max"] is None:
            pytest.skip(f"{name} is support media — no LV design range")
        assert e["lv_min"] < e["lv_max"], f"{name} lv_min >= lv_max"

    @pytest.mark.parametrize("name", CORE_MEDIA)
    def test_ebct_range_ordered(self, name):
        """ebct_min < ebct_max for filtration media; support media may have None ranges."""
        e = get_media(name)
        if e["ebct_min"] is None or e["ebct_max"] is None:
            pytest.skip(f"{name} is support media — no EBCT design range")
        assert e["ebct_min"] < e["ebct_max"], f"{name} ebct_min >= ebct_max"

    def test_d60_ge_d10_when_present(self):
        """
        When d60 is present, d60 >= d10 (by grain-size distribution definition).
        """
        for name, entry in MEDIA_DATABASE.items():
            if "d60" in entry and "d10" in entry:
                assert entry["d60"] >= entry["d10"], \
                    f"{name}: d60={entry['d60']} < d10={entry['d10']}"


# ═════════════════════════════════════════════════════════════════════════════
# Specific media properties
# ═════════════════════════════════════════════════════════════════════════════

class TestMediaProperties:

    def test_fine_sand_properties(self):
        """Fine sand: d10=0.8 mm, ε₀=0.42, ρ=2650 kg/m³."""
        e = get_media("Fine sand")
        assert e["d10"]        == pytest.approx(0.8,  rel=0.001)
        assert e["epsilon0"]   == pytest.approx(0.42, rel=0.001)
        assert e["rho_p_eff"]  == 2650

    def test_garnet_properties(self):
        """Garnet: d10=0.3 mm, ε₀=0.38, ρ=4100 kg/m³ (heavy polishing layer)."""
        e = get_media("Garnet")
        assert e["d10"]       == pytest.approx(0.3,  rel=0.001)
        assert e["epsilon0"]  == pytest.approx(0.38, rel=0.001)
        assert e["rho_p_eff"] == 4100

    def test_garnet_denser_than_sand(self):
        """Garnet (4100 kg/m³) must be denser than fine sand (2650 kg/m³)."""
        assert get_media("Garnet")["rho_p_eff"] > get_media("Fine sand")["rho_p_eff"]

    def test_anthracite_lighter_than_sand(self):
        """Anthracite (~1450 kg/m³) is lighter than fine sand (~2650 kg/m³)."""
        assert get_media("Anthracite")["rho_p_eff"] < get_media("Fine sand")["rho_p_eff"]

    def test_fine_sand_lv_range(self):
        """Fine sand design LV range: 5–10 m/h."""
        lv_min, lv_max = get_lv_range("Fine sand")
        assert lv_min == 5
        assert lv_max == 10

    def test_garnet_lv_range(self):
        """Garnet design LV range: 10–20 m/h."""
        lv_min, lv_max = get_lv_range("Garnet")
        assert lv_min == 10
        assert lv_max == 20

    def test_gac_ebct_range_pressure(self):
        """Medium GAC in pressure mode: EBCT 2–30 min."""
        ebct_min, ebct_max = get_ebct_range("Medium GAC", "pressure")
        assert ebct_min == 2
        assert ebct_max == 30


# ═════════════════════════════════════════════════════════════════════════════
# Derived calculations
# ═════════════════════════════════════════════════════════════════════════════

class TestDerivedCalculations:

    def test_interstitial_velocity_formula(self):
        """
        v_i = v_s / ε₀.
        10.0 m/h / 0.42 = 23.810 m/h.
        """
        v_i = interstitial_velocity(10.0, 0.42)
        assert v_i == pytest.approx(23.81, rel=0.001)

    def test_interstitial_velocity_increases_with_superficial(self):
        """Higher superficial velocity → higher interstitial velocity."""
        assert interstitial_velocity(15.0, 0.42) > interstitial_velocity(10.0, 0.42)

    def test_interstitial_velocity_lower_with_higher_porosity(self):
        """Higher porosity → lower interstitial velocity (more void space)."""
        assert interstitial_velocity(10.0, 0.48) < interstitial_velocity(10.0, 0.42)

    def test_collector_max_below_vessel_diameter(self):
        """
        collector_max_height = min(id − clearance, id × 0.90).
        For ID=5.5 m, clearance=300 mm:
          min(5.5 − 0.3, 5.5 × 0.90) = min(5.2, 4.95) = 4.95 m.
        Result must be positive and less than the full vessel diameter.
        """
        h = collector_max_height(5.5)
        assert h == pytest.approx(4.95, rel=0.001)
        assert 0 < h < 5.5


# ═════════════════════════════════════════════════════════════════════════════
# Status labels
# ═════════════════════════════════════════════════════════════════════════════

class TestStatusLabels:

    def test_lv_within_envelope(self):
        """LV 12 m/h inside Fine sand range [5–10] — wait, 12 > 10 → warning."""
        status, code = lv_status(7.0, 5.0, 10.0)
        assert code == "ok"

    def test_lv_below_range_is_critical(self):
        """LV 3 m/h below min=5 → critical."""
        _, code = lv_status(3.0, 5.0, 10.0)
        assert code == "critical"

    def test_lv_above_range_is_warning(self):
        """LV 12 m/h above max=10 → warning or critical (outside envelope)."""
        _, code = lv_status(12.0, 5.0, 10.0)
        assert code in ("warning", "critical")

    def test_ebct_within_envelope(self):
        """EBCT 5 min inside Fine sand range [4–8] → ok."""
        _, code = ebct_status(5.0, 4.0, 8.0)
        assert code == "ok"

    def test_ebct_below_range_is_critical(self):
        """EBCT 2 min below min=4 → critical."""
        _, code = ebct_status(2.0, 4.0, 8.0)
        assert code == "critical"

    def test_ebct_above_range_is_critical(self):
        """EBCT 12 min above max=8 → critical."""
        _, code = ebct_status(12.0, 4.0, 8.0)
        assert code == "critical"


# ═════════════════════════════════════════════════════════════════════════════
# Labels & layer intelligence (UI / cards)
# ═════════════════════════════════════════════════════════════════════════════

class TestMediaLabelsAndIntelligence:

    def test_ebct_label_support_is_none(self):
        assert ebct_label("support") is None

    def test_ebct_label_filtration_string(self):
        assert "EBCT" in (ebct_label("mechanical_filtration") or "")

    def test_get_gac_note_pressure_mode(self):
        n = get_gac_note("Medium GAC", "pressure")
        assert isinstance(n, str)

    def test_get_layer_intelligence_shape(self):
        layers = [
            {"Type": "Gravel", "Depth": 0.2, "is_support": True},
            {"Type": "Fine sand", "Depth": 0.8, "is_support": False},
        ]
        intel, warns = get_layer_intelligence(layers)
        assert len(intel) == 2
        assert intel[0]["layer"] == 1
        assert "function" in intel[0]
        assert isinstance(warns, list)
        for w in warns:
            assert "level" in w and "message" in w


# ═════════════════════════════════════════════════════════════════════════════
# Layer order validation
# ═════════════════════════════════════════════════════════════════════════════

class TestLayerOrderValidation:

    def test_returns_list(self):
        """validate_layer_order must return a list."""
        layers = [{"Type": "Fine sand", "Depth": 0.80, "is_support": False}]
        result = validate_layer_order(layers)
        assert isinstance(result, list)

    def test_empty_layers_no_crash(self):
        """Empty layer list must not raise."""
        result = validate_layer_order([])
        assert isinstance(result, list)

    def test_each_warning_has_level_and_message(self):
        """Every item in the result must have 'level' and 'message' keys."""
        layers = [{"Type": "Fine sand", "Depth": 0.80, "is_support": False}]
        for item in validate_layer_order(layers):
            assert "level" in item
            assert "message" in item

    def test_warning_levels_are_valid(self):
        """'level' must be one of the recognised severity strings."""
        valid_levels = {"ok", "advisory", "warning", "critical", "error"}
        layers = [
            {"Type": "Fine sand", "Depth": 0.80, "is_support": False},
            {"Type": "Anthracite", "Depth": 0.80, "is_support": False},
        ]
        for item in validate_layer_order(layers):
            assert item["level"] in valid_levels, \
                f"Unexpected level: {item['level']}"
