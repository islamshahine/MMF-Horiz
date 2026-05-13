"""
tests/test_mechanical.py
────────────────────────
Tests for engine/mechanical.py — ASME VIII-1 thickness and geometry.

Reference: ASME Section VIII Division 1, UG-27(c)(1)
  Cylindrical shell:
    t_min = P × R / (S × E − 0.6 × P)
  where:
    P = design pressure   [kgf/cm²]   7 bar = 7.138 kgf/cm²
    R = inside radius     [mm]         5500 / 2 = 2750 mm
    S = allowable stress  [kgf/cm²]   1200 (ASTM A516-70 at design temp)
    E = joint efficiency  [-]          1.0 (full radiography)

  Hand calculation:
    t_min = 7.138 × 2750 / (1200 × 1.0 − 0.6 × 7.138)
          = 19 629.5 / (1200 − 4.28)
          = 19 629.5 / 1195.72
          = 16.42 mm  ← engine confirms this value

Geometry:
  real_id = nominal_id − 2 × lining_mm / 1000
  OD      = real_id + 2 × t_shell_design_mm / 1000

Tolerances:
  rel=0.02 (2%) for correlation/rounding in S value
  rel=0.001 (0.1%) for exact geometry formulas
"""
import pytest
from engine.mechanical import thickness, apply_thickness_override


# ── Helpers ───────────────────────────────────────────────────────────────────

def _t(**kwargs):
    """Convenience wrapper with common defaults."""
    defaults = dict(
        diameter_m=5.5, design_pressure_bar=7.0,
        material_name="ASTM A516-70",
        shell_radio="FULL", head_radio="FULL",
        corrosion_mm=1.5, internal_lining_mm=0.0,
    )
    defaults.update(kwargs)
    return thickness(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# ASME UG-27 thickness
# ═════════════════════════════════════════════════════════════════════════════

class TestASMEThickness:

    def test_shell_thickness_basic(self):
        """
        ASTM A516-70, P=7 bar, ID=5.5 m, FULL radiography, CA=1.5 mm.
        Hand calc (UG-27): t_min = 16.42 mm.
        Engine uses S=1200 kgf/cm², E=1.0 → t_min=16.42 mm.
        """
        r = _t()
        assert r["t_shell_min_mm"] == pytest.approx(16.42, rel=0.02)

    def test_pressure_conversion(self):
        """
        7 bar × (1/0.0980665) = 7.138 kgf/cm².
        Engine p_kgf_cm2 must match within 0.1%.
        """
        r = _t()
        assert r["p_kgf_cm2"] == pytest.approx(7.138, rel=0.001)

    def test_higher_pressure_gives_thicker_shell(self):
        """t_shell_min increases monotonically with design pressure."""
        r5  = _t(design_pressure_bar=5.0)
        r7  = _t(design_pressure_bar=7.0)
        r10 = _t(design_pressure_bar=10.0)
        assert r5["t_shell_min_mm"] < r7["t_shell_min_mm"] < r10["t_shell_min_mm"]

    def test_spot_radiography_gives_thicker_shell(self):
        """
        SPOT radiography: E=0.85 < 1.0 (FULL).
        Lower E → larger denominator denominator shrinks → thicker wall.
        Engine: FULL=16.42 mm, SPOT=19.33 mm.
        """
        r_full = _t(shell_radio="FULL")
        r_spot = _t(shell_radio="SPOT")
        assert r_spot["t_shell_min_mm"] > r_full["t_shell_min_mm"]
        assert r_spot["shell_E"] == pytest.approx(0.85, rel=0.001)
        assert r_full["shell_E"] == pytest.approx(1.00, rel=0.001)

    def test_design_thickness_includes_corrosion(self):
        """
        t_shell_design >= t_shell_min + corrosion_allowance.
        CA=3.0 mm: t_min=16.42, t_min+CA=19.42, engine rounds up to 20 mm.
        """
        r = _t(corrosion_mm=3.0)
        assert r["t_shell_design_mm"] >= r["t_shell_min_mm"] + 3.0

    def test_design_thickness_ge_min_thickness(self):
        """t_shell_design must always be at least t_shell_min."""
        r = _t()
        assert r["t_shell_design_mm"] >= r["t_shell_min_mm"]

    def test_lining_reduces_hydraulic_id(self):
        """
        Internal lining reduces hydraulic ID.
        lining=4 mm → id_with_lining = 5.5 − 2×0.004 = 5.492 m.
        """
        r = _t(internal_lining_mm=4.0)
        assert r["id_with_lining_m"] == pytest.approx(5.492, rel=0.001)

    def test_no_lining_hydraulic_id_equals_nominal(self):
        """Zero lining → hydraulic ID = nominal ID."""
        r = _t(internal_lining_mm=0.0)
        assert r["id_with_lining_m"] == pytest.approx(5.5, rel=0.001)


# ═════════════════════════════════════════════════════════════════════════════
# apply_thickness_override — geometry derivation
# ═════════════════════════════════════════════════════════════════════════════

class TestThicknessOverride:

    def test_real_id_with_lining(self):
        """
        real_id = nominal_id − 2 × lining_mm / 1000.
        5.5 − 2 × 0.004 = 5.492 m.
        """
        mech = _t(internal_lining_mm=4.0)
        r = apply_thickness_override(mech, 0.0, 0.0, 4.0, 5.5)
        assert r["real_id_m"] == pytest.approx(5.492, rel=0.001)

    def test_real_id_no_lining_equals_nominal(self):
        """Zero lining → real_id = nominal_id = 5.5 m."""
        mech = _t(internal_lining_mm=0.0)
        r = apply_thickness_override(mech, 0.0, 0.0, 0.0, 5.5)
        assert r["real_id_m"] == pytest.approx(5.5, rel=0.001)

    def test_od_formula(self):
        """
        OD = real_id + 2 × t_shell_design_mm / 1000.
        No lining: real_id = 5.5 m, t_design = 18 mm.
        OD = 5.5 + 2 × 0.018 = 5.536 m.
        """
        mech = _t(internal_lining_mm=0.0)
        r = apply_thickness_override(mech, 0.0, 0.0, 0.0, 5.5)
        expected_od = r["real_id_m"] + 2 * r["t_shell_design_mm"] / 1000.0
        assert r["od_m"] == pytest.approx(expected_od, rel=0.001)

    def test_override_shell_replaces_min(self):
        """
        When override_shell_mm > 0, t_shell_design is set to the override
        and shell_overridden flag is True.
        """
        mech = _t()
        r = apply_thickness_override(mech, 25.0, 0.0, 0.0, 5.5)
        assert r["t_shell_design_mm"] == 25.0
        assert r["shell_overridden"] is True

    def test_no_override_flag_false(self):
        """Without override, shell_overridden and head_overridden are False."""
        mech = _t()
        r = apply_thickness_override(mech, 0.0, 0.0, 0.0, 5.5)
        assert r["shell_overridden"] is False
        assert r["head_overridden"] is False
