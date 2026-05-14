"""Tests for engine/pump_performance.py."""
import copy

import pytest

from engine.pump_performance import (
    build_pump_performance_package,
    motor_electrical_kw,
    snap_iec_motor_kw,
    _pump_shaft_power_kw,
    _dol_pumps_running,
)
from tests.test_integration import _INPUTS


def _minimal_computed(work: dict):
    """Lightweight hyd_prof / energy / bw stubs for unit tests."""
    rho = 1025.0
    return {
        "hyd_prof": {
            "clean": {"total_mwc": 12.0},
            "dirty": {"total_mwc": 18.0},
        },
        "energy": {
            "e_filt_kwh_yr": 1e6,
            "e_bw_pump_kwh_yr": 5e4,
            "e_blower_kwh_yr": 2e4,
            "e_total_kwh_yr": 1.07e6,
            "total_flow_m3_yr": 5e7,
            "bw_events_yr": 10000.0,
            "bw_per_day_design": 2.0,
        },
        "bw_hyd": {
            "q_bw_design_m3h": 4000.0,
            "q_air_design_m3h": 8000.0,
            "p_blower_est_kw": 120.0,
        },
        "bw_seq": {
            "steps": [
                {
                    "Step": "High water rate",
                    "Dur avg (min)": 10.0,
                    "Water rate (m/h)": 30.0,
                    "Source": "Brine",
                },
            ],
        },
        "bw_sizing": {"p_blower_motor_kw": 130.0, "pressure_ratio": 1.12},
        "q_per_filter": 1312.5,
        "avg_area": 120.0,
        "rho_feed": rho,
        "rho_bw": rho,
    }


def test_shaft_power_positive():
    p = _pump_shaft_power_kw(100.0, 20.0, 1025.0, 0.75)
    assert p > 5.0
    assert motor_electrical_kw(p, 0.95) > p


def test_snap_iec_monotonic():
    assert snap_iec_motor_kw(10.1) >= snap_iec_motor_kw(10.0)


def test_dol_two_pumps_above_half_design():
    assert _dol_pumps_running(100.0, 400.0) == 1
    assert _dol_pumps_running(250.0, 400.0) == 2


def test_build_pump_performance_package_smoke():
    work = copy.deepcopy(_INPUTS)
    comp = _minimal_computed(work)
    out = build_pump_performance_package(
        inputs=work,
        hyd_prof=comp["hyd_prof"],
        energy=comp["energy"],
        bw_hyd=comp["bw_hyd"],
        bw_seq=comp["bw_seq"],
        bw_sizing=comp["bw_sizing"],
        q_per_filter=comp["q_per_filter"],
        avg_area=comp["avg_area"],
        total_flow=work["total_flow"],
        streams=work["streams"],
        n_filters=work["n_filters"],
        hydraulic_assist=int(work.get("hydraulic_assist", 0)),
        rho_feed=comp["rho_feed"],
        rho_bw=comp["rho_bw"],
        pump_eta=float(work["pump_eta"]),
        motor_eta=float(work["motor_eta"]),
        bw_pump_eta=float(work["bw_pump_eta"]),
        bw_head_mwc=float(work["bw_head_mwc"]),
        bw_velocity=float(work["bw_velocity"]),
        bw_cycles_day=2.0,
    )
    assert "feed_pump" in out
    assert out["philosophy"]["DOL"]["kwh_total_per_cycle"] >= 0.0
    assert out["capex_baseline_usd"]["dol_grand_total_usd"] > 0
    assert "feed_pumps_all_usd" in out["capex_baseline_usd"]
