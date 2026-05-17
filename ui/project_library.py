"""Polished Streamlit UI for the local SQLite project library."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from engine.project_db import (
    create_case,
    delete_project,
    diff_revisions,
    init_db,
    list_cases,
    list_projects,
    list_revisions,
    load_project,
    load_revision,
    save_project,
    save_revision,
    update_project_by_id,
)
from engine.project_io import default_filename, engine_inputs_dict, inputs_to_json
from ui.project_persistence import collect_ui_session_persist_dict
from ui.project_session import queue_deferred_load_document

DEFAULT_DB_PATH = "aquasight.db"


def _db_path() -> str:
    return str(st.session_state.get("mmf_project_db_path", DEFAULT_DB_PATH)).strip() or DEFAULT_DB_PATH


def _filter_projects(rows: list[dict], query: str) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return rows
    out = []
    for r in rows:
        blob = " ".join(
            str(r.get(k, ""))
            for k in ("display_name", "doc_number", "project_key", "notes")
        ).lower()
        if q in blob:
            out.append(r)
    return out


def _projects_table_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Project": r.get("display_name", ""),
            "Doc.": r.get("doc_number", ""),
            "Key": r.get("project_key", ""),
            "Updated": (r.get("updated_at") or "")[:10],
            "Notes": (r.get("notes") or "")[:60],
            "_id": int(r["id"]),
        }
        for r in rows
    ])


def _queue_open_document(doc: dict[str, Any], *, toast: str) -> None:
    queue_deferred_load_document(
        doc,
        linked_filename=default_filename(
            str(doc.get("project_name", "project")),
            str(doc.get("doc_number", "")),
        ),
        toast=toast,
    )
    st.rerun()


def render_project_library_panel(inputs: dict, computed: dict | None) -> None:
    """Browse, save, load, snapshot history — uses unified ``project_session`` hydrate."""
    st.markdown("**Local project library**")
    st.caption(
        "Stores the same payload as a JSON project file (inputs + pump/blower UI state). "
        "**Cases** group alternatives; **revisions** are dated checkpoints with a report hash."
    )
    st.text_input("Database file", value=_db_path(), key="mmf_project_db_path")

    db = _db_path()
    try:
        init_db(db)
        all_rows = list_projects(db, limit=200)
    except Exception as ex:
        st.warning(f"Library unavailable: {ex}")
        return

    search = st.text_input("Search projects", placeholder="Name, document no., notes…", key="mmf_lib_search")
    filtered = _filter_projects(all_rows, search)

    if not filtered:
        st.info("No matching projects — save the current design below to create one.")
    else:
        df = _projects_table_df(filtered)
        st.dataframe(
            df.drop(columns=["_id"]),
            use_container_width=True,
            hide_index=True,
            height=min(35 * len(df) + 38, 280),
        )
        labels = [
            f"{r['display_name']} · {r['doc_number']} ({r['project_key']})"
            for r in filtered
        ]
        pick = st.selectbox(
            "Selected project",
            range(len(filtered)),
            format_func=lambda i: labels[i],
            key="mmf_lib_pick",
        )
        sel = filtered[int(pick)]
        pid = int(sel["id"])
        st.session_state["mmf_lib_selected_id"] = pid

        notes = st.text_area(
            "Library notes",
            value=str(sel.get("notes") or ""),
            height=68,
            key=f"mmf_lib_notes_{pid}",
        )

        a1, a2, a3, a4 = st.columns(4)
        with a1:
            if st.button("Open in app", type="primary", use_container_width=True, key="mmf_lib_open"):
                loaded = load_project(db, project_id=pid)
                doc = loaded.get("document") or loaded["inputs"]
                _queue_open_document(doc, toast=f"Opened **{sel['display_name']}** from library.")
        with a2:
            if st.button("Update record", use_container_width=True, key="mmf_lib_update"):
                ui = collect_ui_session_persist_dict()
                try:
                    update_project_by_id(
                        db, pid, inputs, computed=computed,
                        notes=notes.strip(), ui_session_overrides=ui,
                    )
                except ValueError as ex:
                    st.error(str(ex))
                else:
                    st.session_state["_mmf_project_toast"] = (
                        f"Updated **{sel['display_name']}** in library."
                    )
                    st.rerun()
        with a3:
            _loaded = load_project(db, project_id=pid)
            _doc = _loaded.get("document") or {}
            _ui_snap = _doc.get("_ui_session") if isinstance(_doc.get("_ui_session"), dict) else None
            export_json = inputs_to_json(
                engine_inputs_dict(_doc) if _doc else _loaded["inputs"],
                ui_session_overrides=_ui_snap,
            )
            st.download_button(
                "Export JSON",
                data=export_json,
                file_name=default_filename(sel["display_name"], sel["doc_number"]),
                mime="application/json",
                use_container_width=True,
                key="mmf_lib_export",
            )
        with a4:
            if st.button("Delete", use_container_width=True, key="mmf_lib_delete"):
                delete_project(db, pid)
                st.session_state["_mmf_project_toast"] = f"Deleted **{sel['project_key']}**."
                st.rerun()

        st.divider()
        st.markdown("##### Cases & revisions")
        cases = list_cases(db, pid)
        case_labels = [
            f"{c['case_name']}{' (default)' if c.get('is_default') else ''}"
            for c in cases
        ]
        case_pick = st.selectbox(
            "Case",
            range(len(cases)),
            format_func=lambda i: case_labels[i],
            key="mmf_lib_case_pick",
        )
        case_row = cases[int(case_pick)]
        case_id = int(case_row["id"])

        with st.expander("New case", expanded=False):
            new_case_name = st.text_input("Case name", value="", key="mmf_lib_new_case_name")
            if st.button("Create case", key="mmf_lib_new_case_btn"):
                try:
                    create_case(db, pid, new_case_name.strip())
                except (ValueError, KeyError) as ex:
                    st.error(str(ex))
                else:
                    st.session_state["_mmf_project_toast"] = f"Case **{new_case_name.strip()}** created."
                    st.rerun()

        hist = list_revisions(db, case_id, metadata_only=True)
        if not hist:
            st.caption("No revisions yet — save one from the current session below.")
        else:
            rev_labels = [
                f"{h['created_at'][:16]} · {h.get('revision_code') or '—'} · "
                f"{h['label'] or '—'} · hash {h.get('report_hash', '')[:8]}"
                for h in hist
            ]
            rev_pick = st.selectbox(
                "Revision",
                range(len(hist)),
                format_func=lambda i: rev_labels[i],
                key="mmf_lib_rev_pick",
            )
            sh = hist[int(rev_pick)]
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                if st.button("Open revision", use_container_width=True, key="mmf_lib_rev_load"):
                    rev = load_revision(db, int(sh["id"]))
                    doc = rev.get("document")
                    if doc is None:
                        st.error("Revision has no inputs.")
                    else:
                        _queue_open_document(
                            doc,
                            toast=f"Opened revision **{sh.get('label') or sh['id']}**.",
                        )
            with sc2:
                diff_pick = st.selectbox(
                    "Diff vs",
                    range(len(hist)),
                    format_func=lambda i: rev_labels[i],
                    key="mmf_lib_rev_diff_pick",
                    index=min(1, len(hist) - 1),
                )
                if st.button("Show diff", use_container_width=True, key="mmf_lib_rev_diff"):
                    if int(diff_pick) == int(rev_pick):
                        st.warning("Pick a different revision to compare.")
                    else:
                        try:
                            d = diff_revisions(
                                db, int(sh["id"]), int(hist[int(diff_pick)]["id"]),
                            )
                            st.session_state["mmf_lib_diff_rows"] = d["rows"]
                            st.session_state["mmf_lib_diff_summary"] = d["summary"]
                        except (ValueError, KeyError) as ex:
                            st.error(str(ex))
            with sc3:
                rev_full = load_revision(db, int(sh["id"]))
                doc = rev_full.get("document") or {}
                ui_snap = doc.get("_ui_session") if isinstance(doc.get("_ui_session"), dict) else None
                rev_json = inputs_to_json(
                    engine_inputs_dict(doc) if doc else (rev_full.get("inputs") or {}),
                    ui_session_overrides=ui_snap,
                )
                st.download_button(
                    "Export revision JSON",
                    data=rev_json,
                    file_name=default_filename(
                        sel["display_name"],
                        f"{sel['doc_number']}-{sh.get('revision_code') or sh['id']}",
                    ),
                    mime="application/json",
                    use_container_width=True,
                    key="mmf_lib_rev_export",
                )
            st.caption(
                f"Hash `{sh.get('report_hash', '')}` · "
                f"{'Inputs' if sh['has_inputs'] else '—'} · "
                f"{'Computed' if sh['has_computed'] else '—'}"
            )
            diff_rows = st.session_state.get("mmf_lib_diff_rows")
            if diff_rows:
                st.caption(st.session_state.get("mmf_lib_diff_summary", ""))
                st.dataframe(
                    pd.DataFrame(diff_rows)[["key", "value_a", "value_b"]],
                    use_container_width=True,
                    hide_index=True,
                )

        rev_label = st.text_input(
            "Revision label",
            value=(f"Rev {inputs.get('revision', '')}".strip() or "Checkpoint"),
            key="mmf_lib_snap_label",
        )
        if st.button("Save revision (current session)", key="mmf_lib_snap_save", use_container_width=True):
            ui = collect_ui_session_persist_dict()
            save_revision(
                db,
                case_id,
                inputs=inputs,
                computed=computed,
                label=rev_label.strip() or "Revision",
                notes=notes.strip(),
                revision_code=str(inputs.get("revision") or ""),
                ui_session_overrides=ui,
            )
            st.session_state["_mmf_project_toast"] = (
                f"Revision saved for **{sel['project_key']}** / {case_row['case_name']}."
            )
            st.rerun()

    st.divider()
    st.markdown("##### Save current session")
    c_new, c_ovr = st.columns(2)
    new_notes = st.text_input("Notes for new save", key="mmf_lib_new_notes")
    with c_new:
        if st.button("Save as new library project", type="secondary", use_container_width=True, key="mmf_lib_save_new"):
            ui = collect_ui_session_persist_dict()
            meta = save_project(
                db,
                inputs,
                computed=computed,
                overwrite=True,
                notes=new_notes.strip(),
                ui_session_overrides=ui,
            )
            st.session_state["_mmf_project_toast"] = (
                f"Saved new project **{meta['project_key']}**."
            )
            st.rerun()
    with c_ovr:
        if filtered and st.button("Quick update selected", use_container_width=True, key="mmf_lib_quick_upd"):
            qpid = int(st.session_state.get("mmf_lib_selected_id", filtered[0]["id"]))
            ui = collect_ui_session_persist_dict()
            try:
                update_project_by_id(
                    db, qpid, inputs, computed=computed, ui_session_overrides=ui,
                )
            except ValueError as ex:
                st.error(str(ex))
            else:
                st.session_state["_mmf_project_toast"] = "Updated selected project in library."
                st.rerun()

    dup_col1, dup_col2 = st.columns([2, 1])
    with dup_col1:
        dup_doc = st.text_input("Duplicate as new doc. no.", value="", key="mmf_lib_dup_doc")
    with dup_col2:
        if st.button("Duplicate current", use_container_width=True, key="mmf_lib_dup"):
            dup = copy.deepcopy(inputs)
            dup["doc_number"] = dup_doc.strip() or f"{inputs.get('doc_number', 'COPY')}-copy"
            dup["project_name"] = f"{inputs.get('project_name', 'Project')} (copy)"
            ui = collect_ui_session_persist_dict()
            meta = save_project(
                db, dup, computed=None, overwrite=True,
                notes=f"Duplicated {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                ui_session_overrides=ui,
            )
            st.session_state["_mmf_project_toast"] = f"Duplicated as **{meta['project_key']}**."
            st.rerun()
