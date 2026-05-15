"""Unified project hydrate — JSON and document round-trip."""

import copy
import json

from engine.project_db import load_project, save_project
from engine.project_io import get_widget_state_map, inputs_to_json, json_to_inputs
from engine.validators import REFERENCE_FALLBACK_INPUTS
from ui.project_session import (
    document_for_compute,
    hydrate_session_from_document,
    new_project_document,
)


def test_new_project_document_has_identity():
    doc = new_project_document()
    assert doc["project_name"] == "New project"
    assert doc["doc_number"] == "DRAFT-001"


def test_hydrate_path_matches_json_round_trip():
    base = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    base["project_name"] = "HydrateTest"
    ui = {"pp_n_feed_parallel": 3, "ab_elevation_amsl_m": 42.0}
    raw = inputs_to_json(base, ui_session_overrides=ui)
    doc_a = json_to_inputs(raw)
    doc_b = json_to_inputs(raw)
    w_a = get_widget_state_map(doc_a)
    w_b = get_widget_state_map(doc_b)
    assert w_a == w_b
    assert w_a["pp_n_feed_parallel"] == 3
    assert document_for_compute(doc_a)["project_name"] == "HydrateTest"
    assert "_ui_session" not in document_for_compute(doc_a)


def test_db_load_returns_document_with_ui_session():
    import tempfile
    import os

    base = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    base["project_name"] = "DBDoc"
    base["doc_number"] = "D-99"
    ui = {"pp_align_econ_energy": True}
    with tempfile.TemporaryDirectory() as td:
        dbf = os.path.join(td, "t.db")
        meta = save_project(str(dbf), base, ui_session_overrides=ui)
        row = load_project(str(dbf), project_id=meta["id"])
    doc = row["document"]
    assert row["inputs"]["project_name"] == "DBDoc"
    assert doc.get("_ui_session", {}).get("pp_align_econ_energy") is True
    wmap = get_widget_state_map(doc)
    assert wmap["pp_align_econ_energy"] is True
