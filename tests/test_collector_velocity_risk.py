"""Advisory internal collector velocity screening (1D model post-process)."""

from engine.collector_velocity_risk import (
    HEADER_V_WARNING_M_S,
    analyse_collector_velocity_risk,
)


def test_velocity_risk_inactive_without_profile():
    out = analyse_collector_velocity_risk({})
    assert out["active"] is False

    out2 = analyse_collector_velocity_risk({"profile": []})
    assert out2["active"] is False


def test_velocity_risk_header_warn_hotspot():
    ch = {
        "profile": [
            {
                "station_m": 0.0,
                "lateral_index": 1,
                "header_velocity_m_s": HEADER_V_WARNING_M_S + 0.5,
                "lateral_velocity_m_s": 1.0,
                "orifice_velocity_m_s": 2.0,
            },
        ],
        "orifice_velocity_min_m_s": 2.0,
        "orifice_velocity_max_m_s": 2.0,
        "flow_imbalance_pct": 5.0,
        "target_opening_velocity_m_s": 2.0,
        "lateral_construction": "Drilled perforated pipe",
        "orifice_network": [],
    }
    out = analyse_collector_velocity_risk(ch)
    assert out["active"] is True
    assert out["header_velocity_max_m_s"] >= HEADER_V_WARNING_M_S
    assert any("header" in (h.get("zone") or "").lower() for h in out["hotspots"])
    assert any(
        "internal header" in str(f.get("topic", "")).lower()
        for f in out["findings"]
    )


def test_velocity_risk_plugging_ratio_finding():
    ch = {
        "profile": [
            {
                "station_m": 0.0,
                "lateral_index": 1,
                "header_velocity_m_s": 1.0,
                "lateral_velocity_m_s": 1.0,
                "orifice_velocity_m_s": 6.0,
            },
            {
                "station_m": 1.0,
                "lateral_index": 2,
                "header_velocity_m_s": 0.9,
                "lateral_velocity_m_s": 1.0,
                "orifice_velocity_m_s": 2.0,
            },
        ],
        "orifice_velocity_min_m_s": 2.0,
        "orifice_velocity_max_m_s": 6.0,
        "flow_imbalance_pct": 10.0,
        "target_opening_velocity_m_s": 2.0,
        "lateral_construction": "Drilled perforated pipe",
        "orifice_network": [],
    }
    out = analyse_collector_velocity_risk(ch)
    assert out["orifice_velocity_ratio"] is not None
    assert out["orifice_velocity_ratio"] >= 2.5
    assert out["plugging_hint"]
    assert any("spread" in str(f.get("topic", "")).lower() for f in out["findings"])


def test_velocity_risk_sand_carryover_hint():
    ch = {
        "profile": [
            {
                "station_m": 0.0,
                "lateral_index": 1,
                "header_velocity_m_s": 1.0,
                "lateral_velocity_m_s": 1.0,
                "orifice_velocity_m_s": 3.0,
            },
        ],
        "orifice_velocity_min_m_s": 3.0,
        "orifice_velocity_max_m_s": 3.0,
        "flow_imbalance_pct": 30.0,
        "target_opening_velocity_m_s": 2.0,
        "lateral_construction": "Drilled perforated pipe",
        "orifice_network": [],
    }
    out = analyse_collector_velocity_risk(ch)
    assert out["sand_carryover_hint"]
    assert any("carryover" in str(f.get("topic", "")).lower() for f in out["findings"])


def test_velocity_risk_includes_top_holes_from_network():
    ch = {
        "profile": [
            {
                "station_m": 0.0,
                "lateral_index": 1,
                "header_velocity_m_s": 0.5,
                "lateral_velocity_m_s": 0.5,
                "orifice_velocity_m_s": 1.0,
            },
        ],
        "orifice_velocity_min_m_s": 1.0,
        "orifice_velocity_max_m_s": 9.0,
        "flow_imbalance_pct": 5.0,
        "target_opening_velocity_m_s": 2.0,
        "lateral_construction": "Drilled perforated pipe",
        "orifice_network": [
            {
                "lateral_index": 1,
                "hole_index": 1,
                "station_m": 0.0,
                "y_along_lateral_m": 0.1,
                "flow_m3h": 1.0,
                "velocity_m_s": 9.0,
                "orifice_d_mm": 4.0,
                "construction": "Drilled perforated pipe",
            },
            {
                "lateral_index": 1,
                "hole_index": 2,
                "station_m": 0.0,
                "y_along_lateral_m": 0.2,
                "flow_m3h": 0.5,
                "velocity_m_s": 3.0,
                "orifice_d_mm": 4.0,
                "construction": "Drilled perforated pipe",
            },
        ],
    }
    out = analyse_collector_velocity_risk(ch)
    holes = [h for h in out["hotspots"] if h.get("zone") == "orifice_hole"]
    assert holes
    assert max(h["velocity_m_s"] for h in holes) >= 9.0
