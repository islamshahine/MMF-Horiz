"""Tests for engine/strainer_materials.py."""

from engine.mechanical import STRAINER_WEIGHT_KG, internals_weight
from engine.strainer_materials import (
    normalize_strainer_material,
    strainer_material_advisory,
    suggested_strainer_material,
)


def test_normalize_legacy_ss316l():
    assert normalize_strainer_material("SS 316L") == "SS316"
    assert normalize_strainer_material("Super_duplex_2507") == "Super_duplex_2507"


def test_seawater_warns_on_ss316():
    adv = strainer_material_advisory(salinity_ppt=35.0, strainer_material="SS316")
    assert adv["water_service"] == "seawater"
    assert adv["tone"] == "warning"
    assert any("SS316" in f.get("detail", "") for f in adv["findings"])


def test_seawater_suggests_super_duplex():
    assert suggested_strainer_material(35.0) == "Super_duplex_2507"


def test_duplex_advisory_pren_on_seawater():
    adv = strainer_material_advisory(salinity_ppt=36.0, strainer_material="Duplex_2205")
    assert any("PREN" in f.get("detail", "") for f in adv["findings"])


def test_internals_weight_new_materials():
    w = internals_weight(100, strainer_material="Super_duplex_2507")
    assert w["strainer_material"] == "Super_duplex_2507"
    assert w["weight_per_strainer_kg"] == STRAINER_WEIGHT_KG["Super_duplex_2507"]
