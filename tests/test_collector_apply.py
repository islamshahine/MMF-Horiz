"""Tests for applying collector screening suggestions to inputs."""

from ui.collector_apply import suggested_collector_inputs_si


def test_suggested_patch_from_collector_hyd():
    ch = {
        "n_laterals": 6,
        "lateral_dn_mm": 50.0,
        "lateral_spacing_m": 1.2,
        "lateral_orifice_d_mm": 8.0,
        "n_orifices_per_lateral": 12,
        "maldistribution_factor_calc": 1.12,
        "collector_header_id_m": 0.59,
        "design": {
            "lateral_dn_suggest_mm": 80.0,
            "n_laterals_suggested": 8,
            "perforation_d_suggest_mm": 10.0,
        },
    }
    patch = suggested_collector_inputs_si(ch)
    assert patch["n_bw_laterals"] == 8
    assert patch["lateral_dn_mm"] == 80.0
    assert patch["use_calculated_maldistribution"] is True
    assert patch["maldistribution_factor"] == 1.12
    assert patch["lateral_length_m"] == 0.0
