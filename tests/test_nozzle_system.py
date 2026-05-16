"""Underdrain system coherence tests."""

from engine.nozzle_system import build_underdrain_system_advisory


def test_pp_mushroom_strainer_mismatch_flags():
    adv = build_underdrain_system_advisory(
        {
            "nozzle_catalogue_id": "pp_mushroom_fine_0.2",
            "np_density": 60.0,
            "np_bore_dia": 20.0,
            "strainer_mat": "Super_duplex_2507",
            "feed_sal": 35.0,
        },
        salinity_ppt=35.0,
    )
    assert adv["product_type"] == "mushroom"
    assert any("Polymer" in f.get("topic", "") for f in adv.get("findings") or [])


def test_stale_catalogue_id_cleared_in_summary():
    adv = build_underdrain_system_advisory(
        {
            "nozzle_catalogue_id": "leopold_imt_2mm",
            "np_density": 48.0,
            "strainer_mat": "Duplex_2205",
            "feed_sal": 35.0,
        },
        salinity_ppt=35.0,
    )
    assert adv.get("catalogue_id") is None
    assert any("removed" in f.get("topic", "").lower() for f in adv.get("findings") or [])


def test_johnson_metal_override_not_polymer_warning():
    adv = build_underdrain_system_advisory(
        {
            "nozzle_catalogue_id": "johnson_slot_0.25mm",
            "np_density": 80.0,
            "strainer_mat": "Duplex_2205",
            "feed_sal": 35.0,
        },
        salinity_ppt=35.0,
    )
    assert not any("Polymer" in f.get("topic", "") for f in adv.get("findings") or [])
