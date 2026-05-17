"""Media budget reference."""

from engine.media_pricing import REGION_FACTOR, estimate_media_inventory_budget


def test_region_factors():
    assert REGION_FACTOR["global"] == 1.0
    assert REGION_FACTOR["gcc"] > 1.0
    assert REGION_FACTOR["egypt"] > 1.0
    assert REGION_FACTOR["middle_east"] > 1.0
    assert "egypt" in REGION_FACTOR
    assert "middle_east" in REGION_FACTOR


def test_estimate_positive():
    base = [
        {"Type": "Gravel", "Vol": 2.0},
        {"Type": "Fine sand", "Vol": 5.0},
    ]
    inp = {"econ_media_gravel": 100.0, "econ_media_sand": 200.0}
    out = estimate_media_inventory_budget(
        base_layers=base,
        n_filters=4,
        streams=2,
        inputs=inp,
        region="global",
    )
    assert out["filters_plant_wide"] == 8
    assert out["total_fill_usd"] > 0
    assert len(out["lines"]) == 2


def test_gcc_raises_total_vs_global():
    base = [{"Type": "Anthracite", "Vol": 1.0}]
    inp = {"econ_media_anthracite": 400.0}
    g = estimate_media_inventory_budget(
        base_layers=base, n_filters=1, streams=1, inputs=inp, region="global",
    )
    gcc = estimate_media_inventory_budget(
        base_layers=base, n_filters=1, streams=1, inputs=inp, region="gcc",
    )
    assert gcc["total_fill_usd"] >= g["total_fill_usd"]
