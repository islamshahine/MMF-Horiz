"""HTTP API tests — FastAPI TestClient (no duplicated engineering logic)."""

import copy

import pytest
from fastapi.testclient import TestClient

from api.main import app
from engine.validators import REFERENCE_FALLBACK_INPUTS


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
