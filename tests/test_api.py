"""HTTP API tests — FastAPI TestClient (no duplicated engineering logic)."""

import copy

import pytest
from fastapi.testclient import TestClient

from api.main import app
from engine.units import INPUT_QUANTITY_MAP, display_value
from engine.validators import REFERENCE_FALLBACK_INPUTS


def _inputs_imperial_display_from_si(si: dict) -> dict:
    """Build an imperial-unit payload matching ``convert_inputs(..., 'imperial')`` expectations."""
    out = copy.deepcopy(si)
    for key, qty in INPUT_QUANTITY_MAP.items():
        if key not in out or out[key] is None:
            continue
        v = out[key]
        if isinstance(v, (int, float)):
            out[key] = display_value(float(v), qty, "imperial")
    layers = out.get("layers")
    if layers:
        for layer in layers:
            if not layer:
                continue
            d = layer.get("Depth")
            if d is not None and isinstance(d, (int, float)):
                layer["Depth"] = display_value(float(d), "length_m", "imperial")
            lv = layer.get("lv_threshold_m_h")
            if lv is not None and isinstance(lv, (int, float)):
                layer["lv_threshold_m_h"] = display_value(float(lv), "velocity_m_h", "imperial")
    return out


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_compute_valid_returns_engine_outputs(client: TestClient):
    body = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    body["project_name"] = "api-test"
    body["doc_number"] = "AT-1"
    r = client.post("/compute", json=body)
    assert r.status_code == 200
    data = r.json()
    assert "overall_risk" in data
    assert "econ_capex" in data
    assert "econ_npv" in data
    assert "econ_financial" in data
    assert "input_validation" in data
    assert data["input_validation"]["valid"] is True


def test_compute_unit_system_imperial_matches_si(client: TestClient):
    si = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    si["project_name"] = "api-imperial"
    si["doc_number"] = "IM-1"
    imperial = _inputs_imperial_display_from_si(si)
    r_si = client.post("/compute", json=si)
    r_im = client.post("/compute", json=imperial, params={"unit_system": "imperial"})
    assert r_si.status_code == 200, r_si.text
    assert r_im.status_code == 200, r_im.text
    js, ji = r_si.json(), r_im.json()
    assert js["input_validation"]["valid"] is True
    assert ji["input_validation"]["valid"] is True
    assert js["q_per_filter"] == pytest.approx(ji["q_per_filter"], rel=1e-4)


def test_compute_unit_system_metric_explicit_same_as_default(client: TestClient):
    body = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    body["project_name"] = "api-metric-explicit"
    body["doc_number"] = "ME-1"
    r1 = client.post("/compute", json=body)
    r2 = client.post("/compute", json=body, params={"unit_system": "metric"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["q_per_filter"] == pytest.approx(r2.json()["q_per_filter"], rel=1e-9)


def test_compute_unit_system_invalid_returns_422(client: TestClient):
    body = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    body["project_name"] = "api-bad-units"
    body["doc_number"] = "BU-1"
    r = client.post("/compute", json=body, params={"unit_system": "nautical"})
    assert r.status_code == 422


def test_compute_invalid_json_shape_returns_422(client: TestClient):
    r = client.post("/compute", json=[1, 2, 3])
    assert r.status_code == 422


def test_compute_openapi_docs_available(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"].startswith("AQUASIGHT")
    paths = spec.get("paths", {})
    assert "/compute" in paths
