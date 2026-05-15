"""Sync collector header internal diameter to §4 Backwash inlet/outlet pipe ID."""

from __future__ import annotations

from typing import Any


def user_nozzle_schedule() -> list[dict] | None:
    """§4 table persisted by Mechanical tab — not auto-sized compute preview."""
    import streamlit as st

    sched = st.session_state.get("mmf_nozzle_sched_user")
    if isinstance(sched, list) and sched:
        return list(sched)
    return None


def linked_collector_header_id_si(**flow_kwargs: Any) -> tuple[float, str]:
    """Header ID (m, SI) and note from user §4 schedule or flow preview."""
    from engine.nozzles import suggest_collector_header_id_m

    return suggest_collector_header_id_m(user_nozzle_schedule(), **flow_kwargs)


def sync_linked_collector_header_session(**flow_kwargs: Any) -> float | None:
    """
    Update session display value for linked header from §4 user schedule.
    Returns SI header diameter when linked and a schedule exists.
    """
    import streamlit as st
    from engine.units import display_value

    if not st.session_state.get("collector_header_id_linked", True):
        return None
    if user_nozzle_schedule() is None:
        return None

    _us = st.session_state.get("unit_system", "metric")
    hdr_si, _note = linked_collector_header_id_si(**flow_kwargs)
    disp = display_value(hdr_si, "length_m", _us)
    # Drop stale number_input widget state (key was collector_header_id_m).
    st.session_state.pop("collector_header_id_m", None)
    st.session_state["_collector_header_id_linked_disp"] = disp
    return float(hdr_si)


def patch_inputs_collector_header_si(inputs_si: dict, **flow_kwargs: Any) -> dict:
    """Inject linked header ID (SI) into inputs before compute."""
    import streamlit as st

    if not st.session_state.get("collector_header_id_linked", True):
        return inputs_si
    if user_nozzle_schedule() is None:
        return inputs_si

    hdr_si, _ = linked_collector_header_id_si(**flow_kwargs)
    out = dict(inputs_si)
    out["collector_header_id_m"] = float(hdr_si)
    return out


def persist_nozzle_editor_to_session() -> None:
    """data_editor on_change — save §4 SI rows and sync linked header, then rerun."""
    import streamlit as st

    from ui.helpers import nozzle_schedule_si_from_editor_df

    base = st.session_state.get("_mmf_nozzle_sched_base")
    keys = st.session_state.get("_mmf_nozzle_sched_keys")
    edited = st.session_state.get("mmf_nozzle_editor")
    editor_base_df = st.session_state.get("_mmf_nozzle_editor_df")
    if not isinstance(base, list) or not isinstance(keys, dict) or edited is None:
        return

    sched_si = nozzle_schedule_si_from_editor_df(
        edited, keys, base, editor_base_df=editor_base_df,
    )
    st.session_state["mmf_nozzle_sched_user"] = sched_si
    sync_linked_collector_header_session()
    st.rerun()
