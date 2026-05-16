"""Nozzle plate vendor catalogue."""

from engine.nozzle_plate_catalogue import (
    catalogue_application_warnings,
    catalogue_patch_for_product,
    get_catalogue_product,
    list_catalogue_products,
    uses_drilled_density_band,
)
from engine.strainer_materials import resolve_strainer_for_catalogue


def test_catalogue_has_products():
    prods = list_catalogue_products()
    assert len(prods) >= 8
    assert all("vendor" in p and "id" in p for p in prods)


def test_removed_ids_not_in_catalogue():
    assert get_catalogue_product("leopold_imt_2mm") is None
    assert get_catalogue_product("collector_drilled_50") is None
    assert get_catalogue_product("generic_drilled_50") is None


def test_removed_id_warning():
    warns = catalogue_application_warnings("leopold_imt_2mm")
    assert warns and warns[0]["severity"] == "warning"


def test_slotted_patch_sets_slot():
    patch = catalogue_patch_for_product("johnson_slot_0.25mm", salinity_ppt=35.0)
    assert patch.get("wedge_slot_width_mm") == 0.25
    assert get_catalogue_product("johnson_slot_0.25mm")["type"] == "slotted"


def test_mushroom_pp_strainer():
    patch = catalogue_patch_for_product("pp_mushroom_fine_0.2", salinity_ppt=35.0)
    assert patch["strainer_mat"] == "PP"


def test_hdpe_mushroom_strainer():
    patch = catalogue_patch_for_product("hdpe_mushroom_coarse_2", salinity_ppt=35.0)
    assert patch["strainer_mat"] == "HDPE"
    assert patch["np_bore_dia"] == 24.0


def test_johnson_salinity_drives_metal_strainer():
    p = get_catalogue_product("johnson_slot_0.25mm")
    assert resolve_strainer_for_catalogue(p, 35.0) == "Super_duplex_2507"
    assert resolve_strainer_for_catalogue(p, 5.0) == "Duplex_2205"
    assert resolve_strainer_for_catalogue(p, 0.5) == "SS316"


def test_catalogue_has_nine_products():
    assert len(list_catalogue_products()) == 9


def test_uses_drilled_band():
    assert uses_drilled_density_band("pp_mushroom_fine_0.2") is False
    assert uses_drilled_density_band("johnson_slot_0.25mm") is False
    assert uses_drilled_density_band(None) is True
