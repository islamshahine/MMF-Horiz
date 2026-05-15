"""Optimisation Pareto helper."""

import copy

from engine.optimisation import optimise_design, pareto_front_min2

from tests.test_integration import _INPUTS


def test_pareto_front_three_points():
    rows = [
        {"feasible": True, "metrics": {"total_capex_usd": 10.0, "total_opex_usd_yr": 5.0}},
        {"feasible": True, "metrics": {"total_capex_usd": 8.0, "total_opex_usd_yr": 7.0}},
        {"feasible": True, "metrics": {"total_capex_usd": 12.0, "total_opex_usd_yr": 3.0}},
        {"feasible": False, "metrics": {"total_capex_usd": 1.0, "total_opex_usd_yr": 1.0}},
    ]
    nd = pareto_front_min2(rows, "total_capex_usd", "total_opex_usd_yr")
    assert len(nd) == 3
    caps = {round(r["metrics"]["total_capex_usd"]) for r in nd}
    assert caps == {8, 10, 12}


def test_optimise_design_includes_pareto_key():
    base = copy.deepcopy(_INPUTS)
    patches = [{"n_filters": n} for n in (6, 7, 8, 9, 10)]
    res = optimise_design(base, patches, objective="capex", top_k=3)
    assert "pareto_capex_opex" in res
    assert isinstance(res["pareto_capex_opex"], list)
