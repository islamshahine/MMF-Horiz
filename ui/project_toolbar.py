"""Top-of-page project file strip: new, save, save as, load (JSON + library)."""

from __future__ import annotations

import copy
import os
from typing import Any

import streamlit as st

from engine.project_io import default_filename, inputs_to_json
from ui.project_library import render_project_library_panel
from ui.project_persistence import collect_ui_session_persist_dict
from ui.project_session import (
    MMF_LINKED_PROJECT_FILENAME,
    consume_deferred_project_actions,
    queue_deferred_load_document,
    queue_deferred_load_json,
    queue_deferred_new_project,
)


def _commit_save_as_linked_filename() -> None:
    """Remember Save-as slug for the next **Save** download (``on_click``)."""
    _p = str(st.session_state.get("mmf_saveas_pn", "project"))
    _d = str(st.session_state.get("mmf_saveas_dn", ""))
    st.session_state[MMF_LINKED_PROJECT_FILENAME] = default_filename(_p, _d)


def _export_json(inputs: dict) -> str:
    return inputs_to_json(inputs, ui_session_overrides=collect_ui_session_persist_dict())


def render_project_toolbar(inputs: dict, computed: dict | None = None) -> None:
    """Render compact project controls (expects the same ``inputs`` dict as ``compute_all``)."""
    _msg = st.session_state.pop("_mmf_project_toast", None)
    if isinstance(_msg, str) and hasattr(st, "toast"):
        st.toast(_msg)
    _err = st.session_state.pop("_mmf_project_load_error", None)
    if isinstance(_err, str):
        st.error(_err)

    if "mmf_saveas_pn" not in st.session_state:
        st.session_state["mmf_saveas_pn"] = str(inputs.get("project_name", "project"))
    if "mmf_saveas_dn" not in st.session_state:
        st.session_state["mmf_saveas_dn"] = str(inputs.get("doc_number", ""))
    try:
        outer = st.container(border=True)
    except TypeError:
        outer = st.container()
    with outer:
        st.caption(
            "**Project file** — JSON download/upload and optional **local library** use the same load path "
            "(inputs + pump/blower UI snapshot + imperial/metric widgets). "
            "**Save** reuses the filename from your last **Load** or **Save as** when set."
        )
        c0, c1, c2, c3 = st.columns([1.15, 1.0, 1.35, 2.1])
        with c0:
            with st.expander("New project", expanded=False):
                st.caption("Reset to engineering defaults. Unit system is kept.")
                if st.button("Reset all inputs to defaults", type="primary", key="mmf_toolbar_new_go"):
                    queue_deferred_new_project()
                    st.rerun()
        with c1:
            _json = _export_json(inputs)
            _linked = st.session_state.get(MMF_LINKED_PROJECT_FILENAME)
            _fallback = default_filename(
                str(inputs.get("project_name", "project")),
                str(inputs.get("doc_number", "")),
            )
            _save_fn = (
                _linked.strip()
                if isinstance(_linked, str) and _linked.strip()
                else _fallback
            )
            st.download_button(
                "Save",
                data=_json,
                file_name=_save_fn,
                mime="application/json",
                use_container_width=True,
                key="mmf_toolbar_dl_save",
            )
        with c2:
            with st.expander("Save as…", expanded=False):
                st.text_input("Project name (in file)", key="mmf_saveas_pn")
                st.text_input("Document no. (in file)", key="mmf_saveas_dn")
                _pn = str(st.session_state.get("mmf_saveas_pn", inputs.get("project_name", "project")))
                _dn = str(st.session_state.get("mmf_saveas_dn", inputs.get("doc_number", "")))
                _export = copy.deepcopy(inputs)
                _export["project_name"] = _pn
                _export["doc_number"] = _dn
                _json_as = inputs_to_json(
                    _export, ui_session_overrides=collect_ui_session_persist_dict()
                )
                st.download_button(
                    "Save as…",
                    data=_json_as,
                    file_name=default_filename(_pn, _dn),
                    mime="application/json",
                    use_container_width=True,
                    key="mmf_toolbar_dl_saveas",
                    on_click=_commit_save_as_linked_filename,
                )
        with c3:
            st.markdown("**Load JSON file**")
            _nonce = int(st.session_state.get("mmf_upload_widget_nonce", 0))
            _up = st.file_uploader(
                "Project JSON",
                type=["json"],
                key=f"mmf_toolbar_upload_{_nonce}",
                label_visibility="collapsed",
            )
            if _up is not None:
                try:
                    queue_deferred_load_json(
                        _up.read().decode("utf-8"),
                        source_name=getattr(_up, "name", None),
                    )
                    st.session_state["mmf_upload_widget_nonce"] = _nonce + 1
                    st.rerun()
                except Exception as err:
                    st.error(f"Load failed: {err}")

        from ui.ui_profile import is_engineer_mode

        if is_engineer_mode():
            with st.expander("Project library", expanded=False):
                render_project_library_panel(inputs, computed)


# Re-export for app.py import compatibility
__all__ = [
    "consume_deferred_project_actions",
    "queue_deferred_load_document",
    "render_project_toolbar",
    "MMF_LINKED_PROJECT_FILENAME",
]
