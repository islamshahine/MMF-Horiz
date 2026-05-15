"""Tests for §4 → collector header sync (no Streamlit)."""

from engine.nozzles import pipe_internal_id_mm, refresh_nozzle_row_hydraulics, suggest_collector_header_id_m


def test_user_schedule_beats_auto_preview():
    """User §4 DN 600 must not be overridden by auto-sized DN ~900 preview."""
    user_row = refresh_nozzle_row_hydraulics({
        "Service": "Backwash outlet",
        "Flow (m³/h)": 3331.0,
        "DN (mm)": 600,
        "Schedule": "Sch 40",
    })
    user_sched = [user_row]

    hid_user, _ = suggest_collector_header_id_m(user_sched)
    hid_preview, _ = suggest_collector_header_id_m(
        None,
        q_filter_m3h=1312.5,
        bw_velocity_m_h=30.0,
        area_filter_m2=120.0,
    )

    assert hid_user < 0.62
    assert hid_preview > 0.85
    assert hid_user != hid_preview
    assert hid_user == pipe_internal_id_mm(600, "Sch 40") / 1000.0
