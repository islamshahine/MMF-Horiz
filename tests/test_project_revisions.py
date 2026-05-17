"""Tests for B3 project revision tree (cases, revisions, report hash)."""
import copy

import pytest

from engine import project_db as pdb
from engine.project_revisions import diff_revision_inputs, revision_report_hash
from engine.validators import REFERENCE_FALLBACK_INPUTS


def _sample_inputs(name: str, doc: str, *, revision: str = "A1") -> dict:
    d = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    d["project_name"] = name
    d["doc_number"] = doc
    d["revision"] = revision
    return d


def test_report_hash_stable(tmp_path):
    inp = _sample_inputs("H", "H1")
    h1 = revision_report_hash(inp, {"overall_risk": "STABLE"})
    h2 = revision_report_hash(inp, {"overall_risk": "STABLE"})
    assert h1 == h2
    assert len(h1) == 16


def test_report_hash_changes_with_inputs(tmp_path):
    a = _sample_inputs("H", "H1")
    b = copy.deepcopy(a)
    b["streams"] = 3
    assert revision_report_hash(a) != revision_report_hash(b)


def test_default_case_and_revisions(tmp_path):
    dbf = str(tmp_path / "rev.db")
    inp = _sample_inputs("Rev", "R1")
    meta = pdb.save_project(dbf, inp)
    cid = pdb.ensure_default_case(dbf, meta["id"])
    cases = pdb.list_cases(dbf, meta["id"])
    assert len(cases) == 1
    assert cases[0]["case_name"] == "Main"
    assert int(cases[0]["id"]) == cid

    r1 = pdb.save_revision(dbf, cid, inputs=inp, label="baseline")
    inp2 = copy.deepcopy(inp)
    inp2["streams"] = 2
    r2 = pdb.save_revision(dbf, cid, inputs=inp2, label="alt streams")

    revs = pdb.list_revisions(dbf, cid)
    assert len(revs) == 2
    assert revs[0]["label"] == "alt streams"
    assert revs[0]["report_hash"]
    assert revs[0]["report_hash"] != revs[1]["report_hash"]

    loaded = pdb.load_revision(dbf, r1["id"])
    assert loaded["inputs"]["streams"] == inp["streams"]


def test_diff_revisions(tmp_path):
    dbf = str(tmp_path / "diff.db")
    inp = _sample_inputs("D", "D1")
    meta = pdb.save_project(dbf, inp)
    cid = pdb.ensure_default_case(dbf, meta["id"])
    ra = pdb.save_revision(dbf, cid, inputs=inp, label="a")
    inp2 = copy.deepcopy(inp)
    inp2["streams"] = 4
    rb = pdb.save_revision(dbf, cid, inputs=inp2, label="b")
    d = pdb.diff_revisions(dbf, ra["id"], rb["id"])
    assert d["report_hash_a"] != d["report_hash_b"]
    keys = {row["key"] for row in d["rows"]}
    assert "streams" in keys


def test_snapshot_writes_revision(tmp_path):
    dbf = str(tmp_path / "snap.db")
    inp = _sample_inputs("Snap", "S1")
    meta = pdb.save_project(dbf, inp)
    pdb.save_snapshot(dbf, meta["id"], inputs=inp, label="v1")
    hist = pdb.project_history(dbf, meta["id"])
    assert len(hist) == 1
    assert hist[0]["report_hash"]
    snap = pdb.load_snapshot(dbf, hist[0]["id"])
    assert snap["inputs"]["project_name"] == "Snap"


def test_migrate_legacy_snapshots(tmp_path):
    """Snapshots-only DB (pre-B3) migrates into revisions on init."""
    import sqlite3

    from engine import project_io as pio

    dbf = str(tmp_path / "legacy.db")
    inp = _sample_inputs("Legacy", "L1")
    meta = pdb.save_project(dbf, inp)
    pid = meta["id"]
    now = "2026-01-01T00:00:00Z"
    conn = sqlite3.connect(dbf)
    conn.execute(
        """INSERT INTO snapshots (project_id, label, notes, inputs_json, computed_json, created_at)
           VALUES (?,?,?,?,?,?)""",
        (pid, "old1", "", pio.inputs_to_json(inp), None, now),
    )
    inp2 = copy.deepcopy(inp)
    inp2["n_filters"] = 6
    conn.execute(
        """INSERT INTO snapshots (project_id, label, notes, inputs_json, computed_json, created_at)
           VALUES (?,?,?,?,?,?)""",
        (pid, "old2", "", pio.inputs_to_json(inp2), None, now),
    )
    conn.execute("DELETE FROM revisions")
    conn.execute("DELETE FROM cases")
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()

    pdb.init_db(dbf)
    cid = pdb.ensure_default_case(dbf, pid)
    revs = pdb.list_revisions(dbf, cid)
    assert len(revs) == 2
    labels = {r["label"] for r in revs}
    assert labels == {"old1", "old2"}


def test_create_case_and_save_revision(tmp_path):
    dbf = str(tmp_path / "cases.db")
    meta = pdb.save_project(dbf, _sample_inputs("Multi", "M1"))
    alt = pdb.create_case(dbf, meta["id"], "Winter duty")
    inp = _sample_inputs("Multi", "M1", revision="B2")
    pdb.save_revision(dbf, alt["id"], inputs=inp, label="winter")
    revs = pdb.list_revisions(dbf, alt["id"])
    assert len(revs) == 1
    assert revs[0]["revision_code"] == "B2"


def test_diff_revision_inputs_helper():
    a = _sample_inputs("X", "1")
    b = copy.deepcopy(a)
    b["total_flow"] = a["total_flow"] * 1.1
    rows = diff_revision_inputs(a, b)
    assert any(r["key"] == "total_flow" for r in rows)
