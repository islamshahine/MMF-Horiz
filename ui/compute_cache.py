"""Streamlit cache for ``compute_all`` — avoids re-running the full model on every widget rerun."""

from __future__ import annotations

import copy

import streamlit as st


# Bump when computed dict shape / collector rules change (invalidates Streamlit LRU cache).
_COMPUTE_CACHE_VERSION = 28  # spatial_distribution_filtration (P5.4)


@st.cache_data(show_spinner=True, max_entries=48)
def compute_all_cached(inputs: dict, _cache_version: int = _COMPUTE_CACHE_VERSION) -> dict:
    """Return ``compute_all(inputs)``; identical inputs hit the LRU cache.

    Inputs are deep-copied so the engine cannot mutate the caller's dict.
    First run (or new inputs) can take a few seconds — a spinner shows while the model runs.
    """
    del _cache_version  # only used to bust cache after engine/UI contract changes
    from engine.compute import compute_all

    result = compute_all(copy.deepcopy(inputs))
    try:
        from engine.collector_hydraulics import refresh_collector_distribution_metadata

        refresh_collector_distribution_metadata(inputs, result)
    except Exception:
        pass
    try:
        st.session_state["mmf_last_nozzle_sched"] = list(result.get("nozzle_sched") or [])
        st.session_state["mmf_last_avg_area"] = float(result.get("avg_area") or 0.0)
        st.session_state["mmf_last_q_per_filter"] = float(result.get("q_per_filter") or 0.0)
        st.session_state["mmf_last_cyl_len"] = float(result.get("cyl_len") or 0.0)
        st.session_state["mmf_last_nominal_id"] = float(result.get("nominal_id") or 0.0)
        from ui.nozzle_header_sync import sync_linked_collector_header_session
        from engine.units import si_value

        _us = st.session_state.get("unit_system", "metric")
        sync_linked_collector_header_session(
            q_filter_m3h=float(st.session_state.get("mmf_last_q_per_filter") or 0),
            bw_velocity_m_h=si_value(
                float(st.session_state.get("bw_velocity", 30)),
                "velocity_m_h", _us,
            ),
            area_filter_m2=float(st.session_state.get("mmf_last_avg_area") or 25),
        )
    except Exception:
        pass
    return result
