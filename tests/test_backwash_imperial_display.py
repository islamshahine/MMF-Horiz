"""Backwash / collector UI display helpers — imperial formatting."""

from engine.collector_hydraulics import compute_collector_hydraulics
from ui.helpers import (
    collector_hyd_profile_display_df,
    localize_engine_message,
    orifice_network_display_df,
)


def test_localize_flow_message_imperial(monkeypatch):
    import streamlit as st

    monkeypatch.setattr(st, "session_state", {"unit_system": "imperial"}, raising=False)
    out = localize_engine_message("Header velocity up to 1.89 m/s — Q=3311.18 m³/h.")
    assert "m/s" not in out
    assert "m³/h" not in out


def test_localize_velocity_message_imperial(monkeypatch):
    import streamlit as st

    monkeypatch.setattr(st, "session_state", {"unit_system": "imperial"}, raising=False)
    out = localize_engine_message("Lateral pipe velocity 3.25 m/s > 3.0 m/s — suggest DN ≥ 156 mm.")
    assert "m/s" not in out
    assert "ft/s" in out or "in" in out


def test_profile_display_df_imperial_headers(monkeypatch):
    import streamlit as st

    monkeypatch.setattr(st, "session_state", {"unit_system": "imperial"}, raising=False)
    hyd = compute_collector_hydraulics(
        q_bw_m3h=150.0,
        filter_area_m2=28.0,
        cyl_len_m=22.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=45.0,
        collector_header_id_m=0.16,
        n_laterals=6,
        lateral_dn_mm=50.0,
        lateral_spacing_m=3.0,
        lateral_length_m=2.4,
    )
    df = collector_hyd_profile_display_df(hyd["profile"])
    cols = " ".join(df.columns)
    assert "ft/s" in cols or "gpm" in cols
    assert "header_velocity_m_s" not in cols


def test_orifice_network_display_df_imperial(monkeypatch):
    import streamlit as st

    monkeypatch.setattr(st, "session_state", {"unit_system": "imperial"}, raising=False)
    rows = [
        {
            "lateral_index": 1,
            "hole_index": 1,
            "station_m": 1.268,
            "y_along_lateral_m": 0.507,
            "flow_m3h": 0.511,
            "velocity_m_s": 1.347,
            "orifice_d_mm": 50.0,
            "construction": "Drilled perforated pipe",
        },
    ]
    df = orifice_network_display_df(rows)
    cols = " ".join(df.columns)
    assert "ft/s" in cols or "gpm" in cols
    assert "flow_m3h" not in cols
    assert "orifice_d_mm" not in cols
