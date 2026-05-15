"""Tests for plant optimisation patch → session mapping."""

import copy

from engine.optimisation import optimise_design
from ui.design_optim_apply import (
    objective_metric_key,
    plant_patch_to_session_updates,
)
from tests.test_integration import _INPUTS


def test_plant_patch_session_updates_n_filters():
    u = plant_patch_to_session_updates({"n_filters": 18}, "metric")
    assert u["n_filters"] == 18


def test_plant_patch_imperial_nominal_id():
    base = copy.deepcopy(_INPUTS)
    si_id = float(base["nominal_id"])
    u = plant_patch_to_session_updates({"nominal_id": si_id}, "imperial")
    assert u["nominal_id"] != si_id or si_id < 10


def test_optimise_design_aliases_for_ui():
    base = copy.deepcopy(_INPUTS)
    out = optimise_design(
        base,
        [{"n_filters": 16}, {"n_filters": 20}],
        objective="capex",
        top_k=2,
    )
    assert out["feasible_count"] == out["n_feasible"]
    assert out["evaluated"] == out["n_evaluated"]
    assert out["top"] == out["ranked"]
    if out["best"]:
        assert out["best"]["patch"]["n_filters"] == out["top"][0]["patch"]["n_filters"]
    assert len(out.get("all") or []) == 2


def test_objective_metric_key():
    assert objective_metric_key("capex") == "total_capex_usd"
