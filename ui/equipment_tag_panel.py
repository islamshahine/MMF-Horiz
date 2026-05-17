"""UI — equipment tag CSV registry (C3 lite)."""
from __future__ import annotations

import streamlit as st


def render_equipment_tag_panel(computed: dict) -> None:
    """Upload tag list; show ``computed['equipment_tag_registry']`` (built in app.py)."""
    with st.expander(
        "Equipment tag registry — CSV import (C3 lite)",
        expanded=False,
    ):
        st.caption(
            "Import a **structured tag list** from P&ID tools or a spreadsheet — "
            "not image OCR. Columns: **tag** (required), **equipment_type**, "
            "**parameter**, **design_value**, **unit**. "
            "Rows are compared to the current model (filter count, feed/BW/air flows)."
        )
        st.code(
            "tag,equipment_type,parameter,design_value,unit\n"
            "MMF-101A,mmf_filter,n_filters_total,8,count\n"
            "P-401,feed_pump,q_feed_m3h,1200,m3/h\n"
            "P-402,bw_pump,q_bw_m3h,450,m3/h",
            language="csv",
        )
        _up = st.file_uploader(
            "Equipment tag CSV",
            type=["csv", "txt"],
            key="equipment_tag_uploader",
        )
        if _up is not None:
            st.session_state["mmf_equipment_tag_text"] = _up.getvalue().decode(
                "utf-8", errors="replace",
            )
        if st.button("Clear tag import", key="equipment_tag_clear"):
            st.session_state.pop("mmf_equipment_tag_text", None)
            st.rerun()

        _reg = computed.get("equipment_tag_registry") or {}
        if not st.session_state.get("mmf_equipment_tag_text"):
            st.info("No file loaded — upload a CSV to cross-check tags against the model.")
            return
        if not _reg.get("enabled"):
            st.warning(_reg.get("reason") or "Registry import failed.")
            for w in _reg.get("parse_warnings") or []:
                st.caption(f"Parse: {w}")
            return

        st.caption(_reg.get("disclaimer", ""))
        st.success(_reg.get("summary", ""))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tags", str(_reg.get("n_tags", 0)))
        c2.metric("Match", str(_reg.get("n_match", 0)))
        c3.metric("Mismatch", str(_reg.get("n_mismatch", 0)))
        c4.metric("Unmatched", str(_reg.get("n_unmatched", 0)))

        _rows = _reg.get("tags") or []
        if _rows:
            import pandas as pd

            st.dataframe(
                pd.DataFrame(_rows)[
                    [
                        c
                        for c in (
                            "tag",
                            "equipment_type",
                            "parameter_key",
                            "design_value",
                            "model_value",
                            "delta_pct",
                            "status",
                        )
                        if c in pd.DataFrame(_rows).columns
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
