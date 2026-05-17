"""Equipment tag CSV import (C3 lite)."""
from engine.equipment_tag_import import (
    build_equipment_tag_registry,
    parse_equipment_tag_csv,
)


def test_parse_minimal_csv():
    text = (
        "tag,equipment_type,parameter,design_value,unit\n"
        "MMF-1,mmf_filter,n_filters_total,4,count\n"
    )
    rows, warnings = parse_equipment_tag_csv(text)
    assert len(rows) == 1
    assert rows[0]["tag"] == "MMF-1"
    assert not warnings or len(warnings) == 0


def test_build_registry_match_and_mismatch():
    csv = (
        "tag,equipment_type,parameter,design_value,unit\n"
        "MMF-A,mmf_filter,n_filters_total,8,count\n"
        "MMF-B,mmf_filter,n_filters_total,20,count\n"
    )
    inputs = {"streams": 2, "n_filters": 4}
    computed = {"bw_hyd": {"q_bw_design_m3h": 100.0}, "hyd_prof": {"q_total_m3h": 500.0}}
    reg = build_equipment_tag_registry(csv, inputs, computed)
    assert reg["enabled"]
    assert reg["n_tags"] == 2
    assert reg["n_match"] >= 1
    assert reg["n_mismatch"] >= 1


def test_empty_csv():
    rows, warnings = parse_equipment_tag_csv("")
    assert not rows
    assert warnings
