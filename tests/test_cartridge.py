"""Cartridge replacement interval vs rating (mass-balance path)."""
from engine.cartridge import cartridge_design


def test_replacement_interval_increases_with_coarser_rating():
    """Finer absolute rating must not imply longer life than 10 µm for the same TSS duty."""
    Q = 500.0
    kwargs = dict(
        design_flow_m3h=Q,
        element_size='60"',
        mu_cP=1.0,
        n_elem_per_housing=36,
        is_CIP_system=False,
        cf_inlet_tss_mg_l=2.0,
        cf_outlet_tss_mg_l=0.5,
    )
    d1 = cartridge_design(**kwargs, rating_um=1)
    d5 = cartridge_design(**kwargs, rating_um=5)
    d10 = cartridge_design(**kwargs, rating_um=10)
    assert d1["interval_h"] < d5["interval_h"] < d10["interval_h"]


def test_vendor_dhc_override_replaces_model_and_extends_life():
    kwargs = dict(
        design_flow_m3h=400.0,
        element_size='40"',
        rating_um=5,
        mu_cP=1.0,
        n_elem_per_housing=36,
        is_CIP_system=False,
        cf_inlet_tss_mg_l=3.0,
        cf_outlet_tss_mg_l=0.5,
    )
    d0 = cartridge_design(**kwargs)
    d1 = cartridge_design(**kwargs, dhc_g_element_override=800.0)
    assert d0["dhc_basis"] == "model_table"
    assert d1["dhc_basis"] == "vendor_override"
    assert d1["dhc_g_element"] == 800.0
    assert d1["interval_h"] >= d0["interval_h"]


def test_dhc_rating_multiplier_applied_in_optimise_rows():
    from engine.cartridge import cartridge_optimise

    r1 = next(r for r in cartridge_optimise(400.0, 1) if r["size"] == '40"')
    r10 = next(r for r in cartridge_optimise(400.0, 10) if r["size"] == '40"')
    assert r1["dhc_g"] < r10["dhc_g"]
