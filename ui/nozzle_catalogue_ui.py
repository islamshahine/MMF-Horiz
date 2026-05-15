"""Nozzle-plate vendor catalogue — sidebar + Media tab."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.nozzle_plate_catalogue import (
    catalogue_display_rows,
    catalogue_patch_for_product,
    get_catalogue_product,
    list_catalogue_products,
)
from engine.units import display_value, unit_label
from ui.helpers import fmt


def render_nozzle_catalogue_sidebar(out: dict, unit_system: str) -> dict:
    """Add catalogue picker to Media sidebar; returns updated ``out``."""
    products = list_catalogue_products()
    ids = [""] + [p["id"] for p in products]
    labels = {"": "Custom (manual entry)"}
    for p in products:
        labels[p["id"]] = f"{p['vendor']} — {p['product']}"

    sel = st.selectbox(
        "Nozzle plate catalogue (optional)",
        options=ids,
        format_func=lambda k: labels.get(k, k),
        key="nozzle_catalogue_sel",
        help="Screening reference only — not a vendor guarantee. Applies bore/density/Cd on **Apply**.",
    )
    out["nozzle_catalogue_id"] = sel or ""

    if sel:
        p = get_catalogue_product(sel)
        if p:
            st.caption(
                f"**{p['vendor']}** · {p['notes']}  "
                f"Typical **Cd {p['discharge_cd']:.2f}**, "
                f"V screen **{fmt(p['max_velocity_m_s'], 'velocity_m_s', 1)}**."
            )
            if st.button("Apply catalogue to nozzle inputs", key="nozzle_catalogue_apply"):
                patch = catalogue_patch_for_product(sel)
                _apply_catalogue_patch_to_session(patch, unit_system)
                st.success(f"Applied **{labels[sel]}** — click main **Apply** to recompute.")
    return out


def _apply_catalogue_patch_to_session(patch: dict, unit_system: str) -> None:
    if patch.get("np_bore_dia") is not None:
        st.session_state["np_bd"] = display_value(
            float(patch["np_bore_dia"]), "length_mm", unit_system,
        )
    if patch.get("np_density") is not None:
        st.session_state["np_den"] = float(patch["np_density"])
    if patch.get("lateral_discharge_cd") is not None:
        st.session_state["lateral_discharge_cd"] = float(patch["lateral_discharge_cd"])
    if patch.get("wedge_slot_width_mm") is not None:
        st.session_state["wedge_slot_width_mm"] = display_value(
            float(patch["wedge_slot_width_mm"]), "length_mm", unit_system,
        )


def render_nozzle_catalogue_media_panel(unit_system: str) -> None:
    """Read-only catalogue table on Media tab."""
    with st.expander("Nozzle plate vendor catalogue (reference)", expanded=False):
        st.caption(
            "Starting points for **bore**, **density**, and **Cd** — confirm with supplier submittal. "
            "Select a row in the **Media** sidebar and use **Apply catalogue to nozzle inputs**."
        )
        rows = catalogue_display_rows()
        if unit_system == "imperial":
            disp = []
            for r in rows:
                row = dict(r)
                if isinstance(r.get("bore_mm"), (int, float)):
                    row["bore"] = fmt(r["bore_mm"], "length_mm", 2)
                else:
                    row["bore"] = r.get("bore_mm")
                if isinstance(r.get("slot_mm"), (int, float)):
                    row["slot"] = fmt(r["slot_mm"], "length_mm", 3)
                else:
                    row["slot"] = r.get("slot_mm")
                row[f"V_max ({unit_label('velocity_m_s', unit_system)})"] = fmt(
                    float(r["V_max (m/s)"]), "velocity_m_s", 1,
                )
                disp.append({
                    "Vendor": row["vendor"],
                    "Product": row["product"],
                    "Type": row["type"],
                    f"Bore ({unit_label('length_mm', unit_system)})": row.get("bore", "—"),
                    f"Slot ({unit_label('length_mm', unit_system)})": row.get("slot", "—"),
                    "ρ typ (/m²)": row["ρ_typ (/m²)"],
                    "Cd": row["Cd"],
                    f"V max": row[f"V_max ({unit_label('velocity_m_s', unit_system)})"],
                })
            st.dataframe(pd.DataFrame(disp), use_container_width=True, hide_index=True)
        else:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
