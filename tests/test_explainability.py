"""Tests for engine/explainability.py."""

from engine.explainability import (
    METRIC_REGISTRY,
    build_explainability_index,
    get_metric_explanation,
    metric_help_text,
)


def test_registry_has_core_metrics():
    assert "q_per_filter" in METRIC_REGISTRY
    assert "dp_dirty" in METRIC_REGISTRY
    assert "peak_concurrent_bw" in METRIC_REGISTRY


def test_get_metric_explanation_resolves_paths():
    inputs = {"total_flow": 4000.0, "streams": 2, "n_filters": 8, "redundancy": 1}
    computed = {
        "q_per_filter": 250.0,
        "bw_dp": {"dp_dirty_bar": 0.42},
        "cycle_uncertainty": {
            "N": {
                "cycle_optimistic_h": 20.0,
                "cycle_expected_h": 24.0,
                "cycle_conservative_h": 30.0,
                "spread_pct": 25.0,
            },
        },
    }
    ex = get_metric_explanation("q_per_filter", inputs, computed)
    assert ex is not None
    assert "Q_filter" in ex["equation"]
    assert any(c["label"] == "Plant flow" for c in ex["contributors"])


def test_metric_help_text_non_empty():
    text = metric_help_text(
        "dp_dirty",
        {"dp_trigger_bar": 1.0, "alpha_specific": 1e10},
        {"solid_loading_effective_kg_m2": 1.2, "maldistribution_factor": 1.05,
         "bw_dp": {"dp_dirty_bar": 0.5}},
    )
    assert "ΔP" in text
    assert len(text) > 20


def test_build_explainability_index():
    idx = build_explainability_index({}, {"q_per_filter": 100.0})
    assert "metrics" in idx
    assert "q_per_filter" in idx["metrics"]
