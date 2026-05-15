"""Tests for linking collector header ID to Backwash inlet/outlet pipe ID."""

from engine.nozzles import (
    BW_VESSEL_NOZZLE_V_M_S,
    estimate_nozzle_schedule,
    nozzle_dn_mm_for_service,
    pipe_internal_id_mm,
    suggest_collector_header_id_m,
)


def test_bw_inlet_and_outlet_identical():
    sched = estimate_nozzle_schedule(
        q_filter_m3h=1300.0,
        bw_velocity_ms=30.0,
        area_filter_m2=120.0,
    )
    dn_in = nozzle_dn_mm_for_service(sched, "Backwash inlet")
    dn_out = nozzle_dn_mm_for_service(sched, "Backwash outlet")
    assert dn_in == dn_out
    row_in = next(r for r in sched if r["Service"] == "Backwash inlet")
    row_out = next(r for r in sched if r["Service"] == "Backwash outlet")
    assert row_in["Flow (m³/h)"] == row_out["Flow (m³/h)"]
    assert row_in["DN (mm)"] == row_out["DN (mm)"]
    assert row_in["ID (mm)"] == row_out["ID (mm)"]
    assert row_in["Velocity (m/s)"] == row_out["Velocity (m/s)"]


def test_header_id_from_internal_diameter_not_nominal_dn():
    sched = estimate_nozzle_schedule(
        q_filter_m3h=1300.0,
        bw_velocity_ms=30.0,
        area_filter_m2=120.0,
    )
    row = next(r for r in sched if r["Service"] == "Backwash outlet")
    dn = int(row["DN (mm)"])
    id_mm = float(row["ID (mm)"])
    assert id_mm == pipe_internal_id_mm(dn, str(row["Schedule"]))
    assert id_mm < dn  # true ID is less than nominal DN number

    hid, note = suggest_collector_header_id_m(sched)
    assert hid == id_mm / 1000.0
    assert hid != dn / 1000.0 or dn <= 650
    assert "Backwash inlet" in note
    assert "filtrate" in note.lower()


def test_bw_velocity_target_unified():
    assert BW_VESSEL_NOZZLE_V_M_S == 1.5


def test_refresh_nozzle_row_dn_600_internal_id():
    from engine.nozzles import pipe_internal_id_mm, refresh_nozzle_row_hydraulics

    row = refresh_nozzle_row_hydraulics({
        "Service": "Backwash outlet",
        "Flow (m³/h)": 3331.0,
        "DN (mm)": 600,
        "Schedule": "Sch 40",
    })
    assert row["DN (mm)"] == 600
    assert row["ID (mm)"] == round(pipe_internal_id_mm(600, "Sch 40"), 2)
    hid, _ = suggest_collector_header_id_m([row])
    assert hid == row["ID (mm)"] / 1000.0
    assert abs(hid - 0.59) < 0.02
