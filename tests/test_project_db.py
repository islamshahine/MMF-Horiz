"""Tests for engine/project_db.py — SQLite persistence."""
import copy

import pytest

from engine import project_db as pdb
from engine.project_io import inputs_to_json, json_to_inputs
from engine.validators import REFERENCE_FALLBACK_INPUTS


def _sample_inputs(name: str, doc: str) -> dict:
    d = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    d["project_name"] = name
    d["doc_number"] = doc
    return d


def test_init_db_creates_file(tmp_path):
    dbf = tmp_path / "aquasight.db"
    pdb.init_db(str(dbf))
    assert dbf.is_file()


def test_save_load_roundtrip(tmp_path):
    dbf = tmp_path / "t.db"
    inp = _sample_inputs("Alpha", "A-1")
    meta = pdb.save_project(str(dbf), inp, computed=None, notes="n1")
    assert meta["created"] is True
    assert meta["project_key"] == "Alpha_A_1"

    row = pdb.load_project(str(dbf), project_id=meta["id"])
    assert row["notes"] == "n1"
    assert row["inputs"]["project_name"] == "Alpha"
    assert row["inputs"]["doc_number"] == "A-1"
    assert row["inputs"]["total_flow"] == pytest.approx(inp["total_flow"])
    assert row["computed"] is None


def test_save_load_by_project_key(tmp_path):
    dbf = tmp_path / "t.db"
    inp = _sample_inputs("Beta", "B2")
    pdb.save_project(str(dbf), inp)
    row = pdb.load_project(str(dbf), project_key="Beta_B2")
    assert row["inputs"]["nominal_id"] == pytest.approx(inp["nominal_id"])


def test_computed_strips_callables(tmp_path):
    dbf = tmp_path / "t.db"
    inp = _sample_inputs("Gamma", "G")

    def _fn():
        return None

    comp = {"overall_risk": "STABLE", "lv_severity_fn": _fn, "nominal_id": 5.5}
    pdb.save_project(str(dbf), inp, computed=comp)
    row = pdb.load_project(str(dbf), project_key="Gamma_G")
    assert "lv_severity_fn" not in (row["computed"] or {})
    assert row["computed"]["overall_risk"] == "STABLE"


def test_overwrite_updates_same_row(tmp_path):
    dbf = tmp_path / "t.db"
    inp = _sample_inputs("Delta", "D")
    m1 = pdb.save_project(str(dbf), inp, notes="first")
    inp2 = copy.deepcopy(inp)
    inp2["streams"] = 3
    m2 = pdb.save_project(str(dbf), inp2, notes="second", overwrite=True)
    assert m2["created"] is False
    assert m2["id"] == m1["id"]
    row = pdb.load_project(str(dbf), project_id=m1["id"])
    assert row["notes"] == "second"
    assert row["inputs"]["streams"] == 3


def test_overwrite_false_raises(tmp_path):
    dbf = tmp_path / "t.db"
    inp = _sample_inputs("Epsilon", "E")
    pdb.save_project(str(dbf), inp)
    with pytest.raises(FileExistsError):
        pdb.save_project(str(dbf), inp, overwrite=False)


def test_list_projects_multiple(tmp_path):
    dbf = tmp_path / "t.db"
    pdb.save_project(str(dbf), _sample_inputs("P1", "01"))
    pdb.save_project(str(dbf), _sample_inputs("P2", "02"))
    lst = pdb.list_projects(str(dbf))
    assert len(lst) == 2
    keys = {r["project_key"] for r in lst}
    assert keys == {"P1_01", "P2_02"}


def test_snapshot_history_and_load(tmp_path):
    dbf = tmp_path / "t.db"
    inp = _sample_inputs("Snap", "S1")
    meta = pdb.save_project(str(dbf), inp)
    pid = meta["id"]

    pdb.save_snapshot(str(dbf), pid, inputs=inp, label="v1", notes="first")
    inp2 = copy.deepcopy(inp)
    inp2["streams"] = 2
    pdb.save_snapshot(str(dbf), pid, inputs=inp2, label="v2", notes="second")

    hist = pdb.project_history(str(dbf), pid)
    assert len(hist) == 2
    assert hist[0]["label"] == "v2"
    assert hist[1]["label"] == "v1"
    assert hist[0]["has_inputs"] is True

    snap = pdb.load_snapshot(str(dbf), hist[1]["id"])
    assert snap["inputs"]["streams"] == 1
    snap_new = pdb.load_snapshot(str(dbf), hist[0]["id"])
    assert snap_new["inputs"]["streams"] == 2


def test_scenario_upsert(tmp_path):
    dbf = tmp_path / "t.db"
    meta = pdb.save_project(str(dbf), _sample_inputs("Zeta", "Z"))
    pid = meta["id"]
    pdb.save_scenario(str(dbf), pid, "winter", {"tss_avg": 12.0})
    pdb.save_scenario(str(dbf), pid, "winter", {"tss_avg": 15.0})
    lst = pdb.list_scenarios(str(dbf), pid)
    assert len(lst) == 1
    assert lst[0]["scenario_name"] == "winter"


def test_json_export_compatible(tmp_path):
    """Same JSON string shape as file download (project_io)."""
    dbf = tmp_path / "t.db"
    inp = _sample_inputs("JSON", "J1")
    pdb.save_project(str(dbf), inp)
    row = pdb.load_project(str(dbf), project_key="JSON_J1")
    raw = inputs_to_json(row["inputs"])
    again = json_to_inputs(raw)
    assert again["project_name"] == "JSON"
    assert again["total_flow"] == pytest.approx(inp["total_flow"])


def test_delete_project_cascades(tmp_path):
    dbf = tmp_path / "t.db"
    meta = pdb.save_project(str(dbf), _sample_inputs("Del", "D1"))
    pid = meta["id"]
    pdb.save_snapshot(str(dbf), pid, inputs=_sample_inputs("Del", "D1"), label="x")
    pdb.delete_project(str(dbf), pid)
    assert pdb.list_projects(str(dbf)) == []
    hist = pdb.project_history(str(dbf), pid)
    assert hist == []


def test_load_snapshot_returns_document(tmp_path):
    dbf = tmp_path / "t.db"
    inp = _sample_inputs("Snap2", "S2")
    meta = pdb.save_project(
        str(dbf), inp, ui_session_overrides={"pp_n_feed_parallel": 2},
    )
    pdb.save_snapshot(
        str(dbf), meta["id"], inputs=inp, label="v1",
        ui_session_overrides={"pp_n_feed_parallel": 2},
    )
    hist = pdb.project_history(str(dbf), meta["id"])
    snap = pdb.load_snapshot(str(dbf), hist[0]["id"])
    assert snap.get("document", {}).get("_ui_session", {}).get("pp_n_feed_parallel") == 2


def test_update_project_by_id_targets_row(tmp_path):
    dbf = tmp_path / "t.db"
    inp_a = _sample_inputs("Alpha", "A-1")
    inp_b = _sample_inputs("Beta", "B-1")
    ma = pdb.save_project(str(dbf), inp_a)
    mb = pdb.save_project(str(dbf), inp_b)
    session = copy.deepcopy(inp_a)
    session["streams"] = 9
    pdb.update_project_by_id(
        str(dbf), ma["id"], session, notes="from session",
        ui_session_overrides={"pp_n_feed_parallel": 3},
    )
    row_a = pdb.load_project(str(dbf), project_id=ma["id"])
    row_b = pdb.load_project(str(dbf), project_id=mb["id"])
    assert row_a["inputs"]["streams"] == 9
    assert row_a["notes"] == "from session"
    assert row_a["document"]["_ui_session"]["pp_n_feed_parallel"] == 3
    assert row_b["inputs"]["streams"] == inp_b["streams"]


def test_update_project_by_id_key_clash(tmp_path):
    dbf = tmp_path / "t.db"
    ma = pdb.save_project(str(dbf), _sample_inputs("One", "O1"))
    pdb.save_project(str(dbf), _sample_inputs("Two", "T1"))
    clash = _sample_inputs("Two", "T1")
    with pytest.raises(ValueError, match="Another project"):
        pdb.update_project_by_id(str(dbf), ma["id"], clash)


def test_load_project_requires_single_key(tmp_path):
    with pytest.raises(ValueError):
        pdb.load_project(str(tmp_path / "x.db"), project_id=1, project_key="a")
