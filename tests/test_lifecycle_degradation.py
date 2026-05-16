"""Lifecycle degradation advisory curves."""

import copy

from engine.lifecycle_degradation import (
    build_lifecycle_degradation,
    degradation_curve,
)
from engine.compute import compute_all
from tests.test_integration import _INPUTS


def test_degradation_curve_sawtooth():
    curve, eff = degradation_curve(10, 5.0, 1.0)
    assert eff == 5.0
    assert curve[0]["condition_pct"] == 100.0
    assert curve[4]["condition_pct"] == 20.0
    assert curve[5]["condition_pct"] == 100.0
    assert curve[6]["condition_pct"] == 80.0


def test_stress_shortens_effective_interval():
    _c1, e1 = degradation_curve(20, 10.0, 1.0)
    _c2, e2 = degradation_curve(20, 10.0, 1.5)
    assert e2 < e1


def test_build_lifecycle_degradation_structure():
    inp = copy.deepcopy(_INPUTS)
    comp = compute_all(inp)
    out = build_lifecycle_degradation(inp, comp)
    assert out["schema_version"] == "1.0"
    assert "media" in out["components"]
    assert "nozzles" in out["components"]
    assert "collector" in out["components"]
    assert len(out["components"]["media"]["curve"]) == out["horizon_years"] + 1
    assert out["components"]["media"]["nominal_interval_years"] > 0


def test_high_bw_raises_nozzle_stress():
    inp = copy.deepcopy(_INPUTS)
    inp["bw_velocity"] = 55.0
    comp = compute_all(inp)
    base = build_lifecycle_degradation(inp, comp)
    inp2 = copy.deepcopy(_INPUTS)
    inp2["bw_velocity"] = 28.0
    comp2 = compute_all(inp2)
    low = build_lifecycle_degradation(inp2, comp2)
    assert base["components"]["nozzles"]["stress_factor"] >= low["components"]["nozzles"]["stress_factor"]
