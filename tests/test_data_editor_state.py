"""Tests for Streamlit data_editor session-state → DataFrame conversion."""

import pandas as pd

from ui.helpers import data_editor_value_to_dataframe, nozzle_schedule_si_from_editor_df


def test_editing_state_applied_to_base_df():
    base = pd.DataFrame({
        "Service": ["Backwash outlet"],
        "DN (mm)": [900],
    })
    state = {"edited_rows": {0: {"DN (mm)": 600}}, "added_rows": [], "deleted_rows": []}
    out = data_editor_value_to_dataframe(state, base)
    assert out is not None
    assert int(out.iloc[0]["DN (mm)"]) == 600


def test_nozzle_schedule_from_editing_state():
    base_rows = [{
        "Service": "Backwash outlet",
        "Flow (m³/h)": 3331.0,
        "DN (mm)": 900,
        "Schedule": "Sch 40",
        "Rating": "PN 10",
        "Qty": 1,
    }]
    base_df = pd.DataFrame({"Service": ["Backwash outlet"], "DN (mm)": [900], "Schedule": ["Sch 40"], "Rating": ["PN 10"], "Qty": [1]})
    keys = {"dn": "DN (mm)", "schedule": "Schedule", "rating": "Rating", "qty": "Qty"}
    state = {"edited_rows": {0: {"DN (mm)": 600}}, "added_rows": [], "deleted_rows": []}
    sched = nozzle_schedule_si_from_editor_df(state, keys, base_rows, editor_base_df=base_df)
    assert sched[0]["DN (mm)"] == 600
    assert sched[0]["ID (mm)"] < 600
