"""Nozzle plate vendor catalogue."""

from engine.nozzle_plate_catalogue import (
    catalogue_patch_for_product,
    get_catalogue_product,
    list_catalogue_products,
)


def test_catalogue_has_products():
    prods = list_catalogue_products()
    assert len(prods) >= 4
    assert all("vendor" in p and "id" in p for p in prods)


def test_drilled_patch_sets_bore():
    patch = catalogue_patch_for_product("generic_drilled_50")
    assert patch["np_bore_dia"] == 50.0
    assert patch["np_density"] == 45.0


def test_slotted_patch_sets_slot():
    patch = catalogue_patch_for_product("johnson_slot_0.25mm")
    assert patch.get("wedge_slot_width_mm") == 0.25
    assert get_catalogue_product("johnson_slot_0.25mm")["type"] == "slotted"
