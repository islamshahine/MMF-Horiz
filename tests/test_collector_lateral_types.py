"""Tests for lateral construction types and water-service guidance."""

from engine.collector_geometry import lateral_structural_screening
from engine.collector_lateral_types import (
    is_wedge_wire_construction,
    water_service_class,
    water_service_material_guidance,
    wedge_wire_screening,
)


def test_wedge_wire_skips_ligament_rules():
    r = wedge_wire_screening(
        lateral_dn_mm=150.0,
        lateral_length_m=2.5,
        open_area_fraction=0.35,
    )
    assert r["screening_model"] == "wedge_wire"
    assert r["ligament_check_applies"] is False
    assert r["open_area_range_pct"] == "20–60%"


def test_drilled_keeps_ligament():
    r = lateral_structural_screening(
        lateral_construction="Drilled perforated pipe",
        lateral_dn_mm=50.0,
        lateral_length_m=2.0,
        orifice_d_mm=10.0,
        n_perforations=10,
        lateral_material="PVC",
    )
    assert r["screening_model"] == "drilled_perforated"
    assert r["ligament_check_applies"] is True


def test_seawater_warns_generic_ss():
    w = water_service_material_guidance(
        salinity_ppt=35.0,
        lateral_construction="Drilled perforated pipe",
        lateral_material="Stainless steel",
    )
    assert water_service_class(35.0) == "seawater"
    assert any("seawater" in f["topic"].lower() for f in w["findings"])


def test_is_wedge_wire():
    assert is_wedge_wire_construction("Wedge wire screen")
