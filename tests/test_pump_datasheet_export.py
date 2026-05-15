"""Pump / air-blower datasheet export bundle (JSON + Markdown)."""

import copy
import json

from engine.compute import compute_all
from engine.pump_datasheet_export import (
    DATASHEET_TYPE_AIR_BLOWER,
    DATASHEET_TYPE_LIQUID_PUMPS,
    DOCX_OK,
    PDF_OK,
    build_air_blower_datasheet_bundle,
    build_datasheet_export,
    build_pump_datasheet_bundle,
    bundle_to_docx_bytes,
    bundle_to_json,
    bundle_to_markdown,
    bundle_to_pdf_bytes,
    collect_air_blower_datasheet_parts,
    collect_datasheet_parts,
    default_blower_rfq_environment,
    default_ui_snapshot,
    hydraulic_fluid_power_kw,
    list_datasheet_export_choices,
)
from engine.validators import REFERENCE_FALLBACK_INPUTS


def test_hydraulic_fluid_power_kw_seawater_order():
    p = hydraulic_fluid_power_kw(100.0, 10.0, 1025.0)
    assert 2.5 < p < 3.2


def test_bundle_schema_and_equipment_roles_liquid_pumps_only():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    inp["project_name"] = "DS-Test / Case"
    inp["doc_number"] = "TST-001"
    out = compute_all(inp)
    b = build_pump_datasheet_bundle(
        inp, out, default_ui_snapshot(), export_timestamp_utc="2026-01-01T00:00:00Z"
    )
    assert b["schema_version"] == "1.0"
    assert b.get("datasheet_type") == DATASHEET_TYPE_LIQUID_PUMPS
    assert "disclaimer" in b and len(b["disclaimer"]) > 80
    roles = [e["role"] for e in b["equipment"]]
    assert roles == ["filtration_feed_pump", "backwash_liquid_pump"]
    feed = b["equipment"][0]
    assert feed["configuration"]["parallel_pumps_per_stream"] >= 1
    assert len(feed["operating_conditions"]["duty_points"]) == 2
    j = json.loads(bundle_to_json(b))
    assert j["document_control"]["project_name"] == "DS-Test / Case"


def test_markdown_duty_and_full_contain_headers():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    b = build_pump_datasheet_bundle(inp, out, {}, export_timestamp_utc="2026-01-01T00:00:00Z")
    md_d = bundle_to_markdown(b, full_template=False)
    md_f = bundle_to_markdown(b, full_template=True)
    assert "Liquid pumps requisition datasheet" in md_d
    assert "Filtration feed pump" in md_d
    assert "Backwash air blower" not in md_d
    assert "Vendor / site data" not in md_d
    assert "Vendor / site data" in md_f
    assert "TBA" in md_f


def test_collect_parts_covers_liquid_pumps_only():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    b = build_pump_datasheet_bundle(inp, out, default_ui_snapshot(), export_timestamp_utc="2026-01-01T00:00:00Z")
    parts = collect_datasheet_parts(b, full_template=False)
    headings = [p["text"] for p in parts if p["type"] == "heading"]
    assert "3. Filtration feed pump" in headings
    assert "4. Backwash liquid pump" in headings
    assert "5. Backwash air blower" not in headings


def test_docx_and_pdf_magic_bytes_when_optional_libs_installed():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    b = build_pump_datasheet_bundle(inp, out, {}, export_timestamp_utc="2026-01-01T00:00:00Z")
    if DOCX_OK:
        docx = bundle_to_docx_bytes(b, full_template=False)
        assert docx[:2] == b"PK"
    if PDF_OK:
        pdf = bundle_to_pdf_bytes(b, full_template=False)
        assert pdf[:4] == b"%PDF"


def test_air_blower_bundle_and_env_in_markdown():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    env = {**default_blower_rfq_environment(), "elevation_amsl_m": 42.0, "ambient_temp_avg_c": 28.0}
    ab = build_air_blower_datasheet_bundle(
        inp, out, default_ui_snapshot(), env, export_timestamp_utc="2026-01-01T00:00:00Z"
    )
    assert ab.get("datasheet_type") == DATASHEET_TYPE_AIR_BLOWER
    assert len(ab["equipment"]) == 1
    assert ab["equipment"][0]["role"] == "backwash_air_blower"
    assert ab["blower_environment"]["elevation_amsl_m"] == 42.0
    md = bundle_to_markdown(ab, full_template=False)
    assert "Air scour blower requisition datasheet" in md
    assert "Site & ambient environment" in md
    assert "42" in md


def test_air_blower_collect_parts_has_gas_duty():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    ab = build_air_blower_datasheet_bundle(inp, out, {}, {}, export_timestamp_utc="2026-01-01T00:00:00Z")
    parts = collect_air_blower_datasheet_parts(ab, full_template=False)
    assert any(
        p.get("type") == "heading" and "Gas duty" in str(p.get("text", ""))
        for p in parts
    )


def test_air_blower_docx_pdf_when_libs():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    ab = build_air_blower_datasheet_bundle(inp, out, {}, default_blower_rfq_environment())
    if DOCX_OK:
        assert bundle_to_docx_bytes(ab, full_template=False)[:2] == b"PK"
    if PDF_OK:
        assert bundle_to_pdf_bytes(ab, full_template=False)[:4] == b"%PDF"


def test_list_and_build_datasheet_export_choices():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    b = build_pump_datasheet_bundle(inp, out, {}, export_timestamp_utc="2026-01-01T00:00:00Z")
    choices = list_datasheet_export_choices()
    ids = {cid for cid, _ in choices}
    assert "md_duty" in ids and "json" in ids
    data, fname, mime = build_datasheet_export(b, "md_duty", equipment="liquid", slug="test case")
    assert fname.endswith(".md")
    assert mime == "text/markdown"
    assert b"Liquid pumps" in data or len(data) > 100
    _, jname, jmime = build_datasheet_export(b, "json", equipment="liquid", slug="x")
    assert jname.endswith(".json") and jmime == "application/json"
