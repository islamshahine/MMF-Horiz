"""Unified project hydrate — JSON file, SQLite library, and new project (one code path)."""
from __future__ import annotations

import copy
import os
from typing import Any

import streamlit as st

from engine.default_media_presets import DEFAULT_MEDIA_PRESETS
from engine.project_io import (
    PERSISTED_STREAMLIT_KEYS,
    default_filename,
    engine_inputs_dict,
    get_widget_state_map,
    json_to_inputs,
)
from engine.units import UNIT_SYSTEMS
from engine.validators import REFERENCE_FALLBACK_INPUTS

MMF_LINKED_PROJECT_FILENAME = "mmf_linked_project_filename"


def new_project_document() -> dict[str, Any]:
    """SI project document aligned with engineering defaults."""
    doc = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    doc["project_name"] = "New project"
    doc["doc_number"] = "DRAFT-001"
    doc["revision"] = "0"
    doc["client"] = ""
    doc["engineer"] = ""
    return doc


def _clear_persisted_ui_keys() -> None:
    for k in PERSISTED_STREAMLIT_KEYS:
        st.session_state.pop(k, None)


def _clear_derived_session() -> None:
    st.session_state.pop("mmf_last_inputs", None)
    st.session_state.pop("compare_inputs_b", None)
    st.session_state.pop("compare_result", None)
    st.session_state.pop("compare_computed_b", None)
    st.session_state["mmf_ctx_collapsed"] = False


def hydrate_session_from_document(
    doc: dict[str, Any],
    *,
    linked_filename: str | None = None,
) -> None:
    """
    Apply a loaded project document to Streamlit session (widgets + unit system).

    ``doc`` may include ``_ui_session`` (pp_* / ab_*). Uses ``get_widget_state_map`` so
    metric/imperial display matches JSON upload and SQLite library load.
    """
    _clear_persisted_ui_keys()
    us = str(doc.get("unit_system") or "metric")
    if us in UNIT_SYSTEMS:
        st.session_state["unit_system"] = us
        st.session_state["_prev_unit_system"] = us
    wmap = get_widget_state_map(doc)
    for wk, wv in wmap.items():
        st.session_state[wk] = wv
    _clear_derived_session()
    if linked_filename and str(linked_filename).strip():
        st.session_state[MMF_LINKED_PROJECT_FILENAME] = os.path.basename(str(linked_filename).strip())
    else:
        st.session_state[MMF_LINKED_PROJECT_FILENAME] = default_filename(
            str(doc.get("project_name", "project")),
            str(doc.get("doc_number", "")),
        )


def hydrate_session_from_json_text(
    raw: str,
    *,
    linked_filename: str | None = None,
) -> dict[str, Any]:
    """Parse JSON and hydrate session; returns full document (includes ``_ui_session`` when present)."""
    doc = json_to_inputs(raw)
    hydrate_session_from_document(doc, linked_filename=linked_filename)
    return doc


def hydrate_session_new_project() -> None:
    """Reset to reference defaults; keep metric/imperial toggle."""
    _clear_persisted_ui_keys()
    st.session_state.pop("mmf_saveas_pn", None)
    st.session_state.pop("mmf_saveas_dn", None)
    st.session_state.media_presets = DEFAULT_MEDIA_PRESETS.copy()
    doc = new_project_document()
    hydrate_session_from_document(
        doc,
        linked_filename=default_filename("New project", "DRAFT-001"),
    )


def document_for_compute(doc: dict[str, Any]) -> dict[str, Any]:
    """Inputs dict without ``_ui_session`` metadata — safe for ``compute_all``."""
    return engine_inputs_dict(doc)


def queue_deferred_new_project() -> None:
    st.session_state["mmf_deferred_new_project"] = True


def queue_deferred_load_json(raw: str, *, source_name: str | None = None) -> None:
    st.session_state["mmf_deferred_load_json"] = raw
    if source_name and str(source_name).strip():
        st.session_state["mmf_deferred_load_source_name"] = os.path.basename(str(source_name).strip())


def queue_deferred_load_document(
    doc: dict[str, Any],
    *,
    linked_filename: str | None = None,
    toast: str | None = None,
) -> None:
    """Queue hydrate for next rerun — must run before sidebar widgets (library / snapshots)."""
    st.session_state["mmf_deferred_load_document"] = doc
    if linked_filename and str(linked_filename).strip():
        st.session_state["mmf_deferred_load_source_name"] = os.path.basename(
            str(linked_filename).strip()
        )
    if toast and str(toast).strip():
        st.session_state["mmf_deferred_load_toast"] = str(toast).strip()


def consume_deferred_project_actions() -> None:
    """Run before any sidebar widgets are created (see ``app.py``)."""
    if st.session_state.pop("mmf_deferred_new_project", False):
        hydrate_session_new_project()
        st.session_state["_mmf_project_toast"] = "New project — defaults loaded."
    doc = st.session_state.pop("mmf_deferred_load_document", None)
    if isinstance(doc, dict):
        src = st.session_state.pop("mmf_deferred_load_source_name", None)
        toast = st.session_state.pop("mmf_deferred_load_toast", None)
        try:
            hydrate_session_from_document(
                doc,
                linked_filename=src if isinstance(src, str) else None,
            )
            st.session_state["_mmf_project_toast"] = (
                toast if isinstance(toast, str) and toast.strip()
                else "Project loaded — opening inputs…"
            )
        except Exception as e:
            st.session_state["_mmf_project_load_error"] = f"Load failed: {e}"
        return
    raw = st.session_state.pop("mmf_deferred_load_json", None)
    src = st.session_state.pop("mmf_deferred_load_source_name", None)
    if isinstance(raw, str):
        try:
            hydrate_session_from_json_text(raw, linked_filename=src if isinstance(src, str) else None)
            st.session_state["_mmf_project_toast"] = "Project loaded — opening inputs…"
        except Exception as e:
            st.session_state["_mmf_project_load_error"] = f"Load failed: {e}"
