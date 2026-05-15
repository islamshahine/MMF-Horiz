"""Tests for collector intelligence rules."""

from engine.collector_intelligence import analyse_collector_performance


def test_collector_intel_velocity_risk_penalty_reduces_score():
    """Internal distributor advisory score should reduce collector_intel performance score."""
    base = analyse_collector_performance(
        bw_col={
            "status": "OK",
            "freeboard_m": 0.5,
            "min_freeboard_m": 0.1,
            "max_safe_bw_m_h": 40.0,
            "proposed_bw_m_h": 30.0,
            "collector_h_m": 4.0,
            "media_loss_risk": False,
        },
        bw_hyd={"bw_lv_actual_m_h": 30.0},
        nozzle_sched=[
            {"Service": "Filtrate outlet", "Velocity (m/s)": 2.0},
            {"Service": "Backwash inlet", "Velocity (m/s)": 2.1},
        ],
        air_header_dn_mm=250,
        air_scour_rate_m_h=50.0,
        nominal_id_m=5.5,
    )
    stressed = analyse_collector_performance(
        bw_col={
            "status": "OK",
            "freeboard_m": 0.5,
            "min_freeboard_m": 0.1,
            "max_safe_bw_m_h": 40.0,
            "proposed_bw_m_h": 30.0,
            "collector_h_m": 4.0,
            "media_loss_risk": False,
        },
        bw_hyd={"bw_lv_actual_m_h": 30.0},
        nozzle_sched=[
            {"Service": "Filtrate outlet", "Velocity (m/s)": 2.0},
            {"Service": "Backwash inlet", "Velocity (m/s)": 2.1},
        ],
        air_header_dn_mm=250,
        air_scour_rate_m_h=50.0,
        nominal_id_m=5.5,
        collector_velocity_risk={
            "active": True,
            "severity_score": 60,
            "findings": [],
        },
    )
    assert stressed["score"] < base["score"]


def test_collector_intel_ok_case():
    out = analyse_collector_performance(
        bw_col={
            "status": "OK",
            "freeboard_m": 0.5,
            "min_freeboard_m": 0.1,
            "max_safe_bw_m_h": 40.0,
            "proposed_bw_m_h": 30.0,
            "collector_h_m": 4.0,
            "media_loss_risk": False,
        },
        bw_hyd={"bw_lv_actual_m_h": 30.0},
        nozzle_sched=[
            {"Service": "Filtrate outlet", "Velocity (m/s)": 2.0},
            {"Service": "Backwash inlet", "Velocity (m/s)": 2.1},
        ],
        air_header_dn_mm=250,
        air_scour_rate_m_h=50.0,
        nominal_id_m=5.5,
    )
    assert out["score"] >= 70
    assert out["grade"] in ("Good", "Acceptable")
    assert out["peak_nozzle_velocity_water_m_s"] == 2.1
    assert out["peak_nozzle_velocity_air_m_s"] == 0.0


def test_nozzle_schedule_by_service_breakdown():
    from engine.collector_intelligence import summarize_nozzle_schedule_velocities

    peaks = summarize_nozzle_schedule_velocities([
        {"Service": "Backwash inlet", "Velocity (m/s)": 1.84},
        {"Service": "Backwash outlet", "Velocity (m/s)": 1.45},
        {"Service": "Air scour", "Velocity (m/s)": 13.5},
    ])
    assert peaks["backwash_inlet_velocity_m_s"] == 1.84
    assert peaks["backwash_outlet_velocity_m_s"] == 1.45
    assert peaks["air_scour_nozzle_velocity_m_s"] == 13.5
    assert peaks["peak_bw_path_water_m_s"] == 1.84
    assert peaks["peak_nozzle_velocity_air_m_s"] == 13.5


def test_collector_intel_air_13_5_not_water_warning():
    """Air scour ~15 m/s design must not trip the water nozzle limit."""
    out = analyse_collector_performance(
        bw_col={
            "status": "OK",
            "freeboard_m": 0.5,
            "min_freeboard_m": 0.1,
            "max_safe_bw_m_h": 40.0,
            "proposed_bw_m_h": 30.0,
            "collector_h_m": 4.0,
            "media_loss_risk": False,
        },
        bw_hyd={},
        nozzle_sched=[
            {"Service": "Filtrate outlet", "Velocity (m/s)": 1.5},
            {"Service": "Air scour", "Velocity (m/s)": 13.5},
            {"Service": "Sample / instrument", "Velocity (m/s)": 0.0},
        ],
        air_header_dn_mm=250,
        air_scour_rate_m_h=55.0,
        nominal_id_m=5.5,
    )
    assert out["peak_nozzle_velocity_air_m_s"] == 13.5
    assert out["peak_nozzle_velocity_water_m_s"] == 1.5
    assert not any(f["topic"] == "Nozzle velocity (water)" for f in out["findings"])
    assert not any(f["topic"] == "Nozzle velocity (air)" for f in out["findings"])


def test_collector_intel_air_23_5_no_erosion_warning():
    out = analyse_collector_performance(
        bw_col={
            "status": "OK",
            "freeboard_m": 0.5,
            "min_freeboard_m": 0.1,
            "max_safe_bw_m_h": 40.0,
            "proposed_bw_m_h": 30.0,
            "collector_h_m": 4.0,
            "media_loss_risk": False,
        },
        bw_hyd={},
        nozzle_sched=[
            {"Service": "Filtrate outlet", "Velocity (m/s)": 1.5},
            {"Service": "Air scour", "Velocity (m/s)": 23.5},
        ],
        air_header_dn_mm=250,
        air_scour_rate_m_h=55.0,
        nominal_id_m=5.5,
    )
    assert out["peak_nozzle_velocity_air_m_s"] == 23.5
    assert not any(f["topic"] == "Nozzle velocity (water)" for f in out["findings"])
    assert not any(f["topic"] == "Nozzle velocity (air)" for f in out["findings"])


def test_collector_intel_water_high_velocity_warns():
    out = analyse_collector_performance(
        bw_col={
            "status": "OK",
            "freeboard_m": 0.5,
            "min_freeboard_m": 0.1,
            "max_safe_bw_m_h": 40.0,
            "proposed_bw_m_h": 30.0,
            "collector_h_m": 4.0,
            "media_loss_risk": False,
        },
        bw_hyd={},
        nozzle_sched=[{"Service": "Backwash inlet", "Velocity (m/s)": 4.2}],
        air_header_dn_mm=250,
        air_scour_rate_m_h=50.0,
        nominal_id_m=5.5,
    )
    assert any(f["topic"] == "Nozzle velocity (water)" for f in out["findings"])


def test_collector_intel_critical_freeboard():
    out = analyse_collector_performance(
        bw_col={
            "status": "CRITICAL — media loss risk",
            "freeboard_m": 0.02,
            "min_freeboard_m": 0.1,
            "max_safe_bw_m_h": 30.0,
            "proposed_bw_m_h": 35.0,
            "collector_h_m": 4.0,
            "media_loss_risk": True,
        },
        bw_hyd={},
        nozzle_sched=[],
        air_header_dn_mm=150,
        air_scour_rate_m_h=55.0,
        nominal_id_m=5.5,
    )
    assert out["score"] < 70
    assert any(f["severity"] == "critical" for f in out["findings"])
