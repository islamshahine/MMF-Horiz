"""On-demand staged orifice drill schedule — not inside ``compute_all``."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import streamlit as st

from engine.collector_staged_orifices import recommend_staged_orifice_schedule
from ui.collector_envelope_cache import envelope_model_fingerprint


def staged_model_fingerprint(work: dict[str, Any], computed: dict[str, Any], n_groups: int) -> str:
    """Collector geometry + band count — invalidate cache when plant model changes."""
    base = envelope_model_fingerprint(work, computed)
    ch = computed.get("collector_hyd") or {}
    net_n = len(ch.get("orifice_network") or [])
    return hashlib.sha256(
        json.dumps(
            {"base": base, "n_groups": int(n_groups), "net_n": net_n},
            sort_keys=True,
        ).encode(),
    ).hexdigest()[:24]


@st.cache_data(show_spinner=False)
def recommend_staged_orifice_schedule_cached(
    collector_hyd_json: str,
    n_groups: int,
) -> dict[str, Any]:
    ch = json.loads(collector_hyd_json)
    return recommend_staged_orifice_schedule(ch, n_groups=int(n_groups))


def _collector_hyd_cache_blob(computed: dict[str, Any]) -> str:
    ch = computed.get("collector_hyd")
    if not isinstance(ch, dict):
        return "{}"
    slim = {
        "orifice_network": ch.get("orifice_network"),
        "lateral_construction": ch.get("lateral_construction"),
        "lateral_orifice_d_mm": ch.get("lateral_orifice_d_mm"),
        "n_laterals": ch.get("n_laterals"),
    }
    return json.dumps(slim, sort_keys=True, default=str)


def refresh_collector_staged_in_computed(
    work: dict[str, Any],
    computed: dict[str, Any],
) -> dict[str, Any] | None:
    applied = st.session_state.get("_collector_staged_applied")
    if not isinstance(applied, dict):
        applied = {"collector_staged_orifice_groups": 0}
    n_groups = int(applied.get("collector_staged_orifice_groups", 0) or 0)
    ch = computed.get("collector_hyd")
    if not isinstance(ch, dict):
        computed["collector_staged_orifices"] = {
            "active": False,
            "advisory_only": True,
            "note": "No collector hydraulics — run **Apply** first.",
        }
        return computed["collector_staged_orifices"]

    blob = _collector_hyd_cache_blob(computed)
    stg = recommend_staged_orifice_schedule_cached(blob, n_groups)
    computed["collector_staged_orifices"] = stg
    if n_groups >= 2:
        fp = staged_model_fingerprint(work, computed, n_groups)
        st.session_state["mmf_collector_staged_orifices"] = stg
        st.session_state["mmf_collector_staged_fp"] = fp
        st.session_state["mmf_collector_staged_n_groups"] = n_groups
    else:
        st.session_state.pop("mmf_collector_staged_orifices", None)
        st.session_state.pop("mmf_collector_staged_fp", None)
        st.session_state.pop("mmf_collector_staged_n_groups", None)
    if isinstance(st.session_state.get("mmf_last_computed"), dict):
        st.session_state["mmf_last_computed"]["collector_staged_orifices"] = stg
    return stg


def restore_collector_staged_if_valid(
    work: dict[str, Any],
    computed: dict[str, Any],
) -> None:
    stg = st.session_state.get("mmf_collector_staged_orifices")
    fp_saved = st.session_state.get("mmf_collector_staged_fp")
    n_saved = st.session_state.get("mmf_collector_staged_n_groups")
    if not isinstance(stg, dict) or not fp_saved or n_saved is None:
        return
    if int(n_saved) < 2:
        return
    if staged_model_fingerprint(work, computed, int(n_saved)) != fp_saved:
        computed["collector_staged_orifices"] = None
        return
    computed["collector_staged_orifices"] = stg
