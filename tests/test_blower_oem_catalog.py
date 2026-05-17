"""OEM blower motor catalog — realistic nameplate kW."""
from engine.blower_maps import curve_map_power_kw, OEM_VENDOR_CURVE_ID


def test_oem_motor_at_6k_flow():
    motor, in_env, _, extrap, _, basis, tag = curve_map_power_kw(
        OEM_VENDOR_CURVE_ID, 6186.0, 0.43,
    )
    assert basis == "motor"
    assert 90.0 <= motor <= 250.0, f"motor={motor} tag={tag}"


def test_oem_motor_at_10k_flow():
    motor, _, _, _, _, _, _ = curve_map_power_kw(OEM_VENDOR_CURVE_ID, 10000.0, 0.50)
    assert 200.0 <= motor <= 400.0
