"""Tests for engine/validators.py and compute_all input_validation hook."""
import copy

import pytest

from engine.compute import compute_all
from engine.validators import (
    REFERENCE_FALLBACK_INPUTS,
    validate_inputs,
    validate_layers,
    validate_positive,
    validate_range,
    validate_required,
)
from tests.test_integration import _INPUTS


def _base():
    return copy.deepcopy(_INPUTS)


class TestPrimitives:
    def test_validate_positive_rejects_non_positive(self):
        err = []
        validate_positive("x", -1.0, err)
        assert err

    def test_validate_range_inclusive(self):
        err = []
        validate_range("x", 5.0, 0.0, 10.0, err, inclusive=True)
        assert not err
        validate_range("x", 11.0, 0.0, 10.0, err, inclusive=True)
        assert err

    def test_validate_required(self):
        err = []
        validate_required(["a", "b"], {"a": 1}, err)
        assert any("b" in e for e in err)


class TestValidateLayers:
    def test_empty_layers_error(self):
        err, warn = [], []
        validate_layers([], err, warn)
        assert err

    def test_custom_skips_d10_positive_check(self):
        err, warn = [], []
        validate_layers(
            [{"Type": "Custom", "Depth": 0.5, "epsilon0": 0.42, "d10": 0.0}],
            err,
            warn,
        )
        assert not any("d10" in e for e in err)


class TestValidateInputs:
    def test_valid_reference_inputs(self):
        r = validate_inputs(_base())
        assert r["valid"] is True
        assert r["errors"] == []

    def test_invalid_nominal_id(self):
        b = _base()
        b["nominal_id"] = -2.0
        r = validate_inputs(b)
        assert r["valid"] is False
        assert any("nominal_id" in e.lower() for e in r["errors"])

    def test_negative_total_flow(self):
        b = _base()
        b["total_flow"] = -100.0
        r = validate_inputs(b)
        assert r["valid"] is False

    def test_invalid_epsilon0(self):
        b = _base()
        b["layers"] = copy.deepcopy(b["layers"])
        b["layers"][1]["epsilon0"] = 1.2
        r = validate_inputs(b)
        assert r["valid"] is False
        assert any("epsilon0" in e for e in r["errors"])

    def test_missing_layers(self):
        b = _base()
        b["layers"] = []
        r = validate_inputs(b)
        assert r["valid"] is False

    def test_invalid_hydraulic_assist(self):
        b = _base()
        b["hydraulic_assist"] = 5
        r = validate_inputs(b)
        assert r["valid"] is False
        assert any("hydraulic_assist" in e for e in r["errors"])

    def test_standby_must_be_lt_n_filters(self):
        b = _base()
        b["n_filters"] = 3
        b["hydraulic_assist"] = 3
        r = validate_inputs(b)
        assert r["valid"] is False
        assert any("hydraulic_assist" in e for e in r["errors"])

    def test_collector_below_nozzle_plate(self):
        b = _base()
        b["nozzle_plate_h"] = 2.0
        b["collector_h"] = 1.0
        r = validate_inputs(b)
        assert r["valid"] is False
        assert any("collector_h" in e for e in r["errors"])


class TestComputeAllValidationHook:
    def test_input_validation_always_present(self):
        r = compute_all(_base())
        assert "input_validation" in r
        assert r["input_validation"]["valid"] is True
        assert r["compute_used_reference_fallback"] is False

    def test_fallback_when_invalid(self):
        b = _base()
        b["nominal_id"] = -1.0
        r = compute_all(b)
        assert r["input_validation"]["valid"] is False
        assert r["compute_used_reference_fallback"] is True
        assert r["q_per_filter"] == pytest.approx(
            REFERENCE_FALLBACK_INPUTS["total_flow"]
            / REFERENCE_FALLBACK_INPUTS["streams"]
            / max(
                1,
                REFERENCE_FALLBACK_INPUTS["n_filters"]
                - int(REFERENCE_FALLBACK_INPUTS.get("hydraulic_assist", 0)),
            ),
            rel=1e-6,
        )
