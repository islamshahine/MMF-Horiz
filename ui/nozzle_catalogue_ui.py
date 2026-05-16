"""Underdrain — nozzle plate catalogue, geometry, strainer (Media sidebar + Media tab)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.nozzle_plate_catalogue import (
    DRILLED_DENSITY_TYPICAL_MAX,
    DRILLED_DENSITY_TYPICAL_MIN,
    NOZZLE_DENSITY_INPUT_MAX,
    NOZZLE_DENSITY_INPUT_MIN,
    catalogue_application_warnings,
    catalogue_display_rows,
    catalogue_patch_for_product,
    catalogue_select_label,
    density_input_guidance,
    get_catalogue_product,
    list_catalogue_products_sorted,
    underdrain_inputs_summary,
)
from engine.strainer_materials import (
    STRAINER_MATERIAL_ORDER,
    catalogue_strainer_hint,
    resolve_strainer_for_catalogue,
    strainer_material_advisory,
    strainer_material_label,
    suggested_strainer_material,
)
from engine.units import display_value, unit_label
from ui.helpers import fmt


def render_underdrain_media_sidebar(
    out: dict,
    unit_system: str,
    *,
    nozzle_density_default: float,
) -> dict:
    """
    Single **Media** sidebar block: plate geometry, catalogue, strainer.

    Drives Mechanical weight, Backwash §6 hydraulics, and collector screening.
    """
    _sal = float(out.get("feed_sal", 35.0) or 35.0)

    st.markdown("**Underdrain — nozzle plate & strainers**")
    st.caption(
        "One definition for **Mechanical**, **Backwash §6**, and collector. "
        f"Manual **drilled false-bottom**: typical "
        f"**{DRILLED_DENSITY_TYPICAL_MIN:.0f}–{DRILLED_DENSITY_TYPICAL_MAX:.0f} /m²**. "
        "Metal strainers: **SS316 / duplex / super duplex** by **feed salinity**. "
        "Polymer mushroom: strainer matches body."
    )

    _lbl_nph = f"Plate height ({unit_label('length_m', unit_system)})"
    out["nozzle_plate_h"] = st.number_input(
        _lbl_nph,
        value=float(display_value(1.0, "length_m", unit_system)),
        step=float(display_value(0.05, "length_m", unit_system)),
        key="nozzle_plate_h",
    )
    out["np_bore_dia"] = st.number_input(
        f"Bore / stem Ø ({unit_label('length_mm', unit_system)})",
        value=50.0,
        step=float(display_value(5.0, "length_mm", unit_system)),
        min_value=float(display_value(10.0, "length_mm", unit_system)),
        key="np_bd",
    )
    out["np_density"] = st.number_input(
        "Hole density (/m²)",
        value=float(st.session_state.get("np_den", nozzle_density_default)),
        min_value=NOZZLE_DENSITY_INPUT_MIN,
        max_value=NOZZLE_DENSITY_INPUT_MAX,
        step=1.0,
        key="np_den",
    )
    out["n_nozzle_rows"] = int(
        st.number_input(
            "Rows across chord (0 = auto)",
            value=int(st.session_state.get("n_nozzle_rows", 0) or 0),
            min_value=0,
            max_value=80,
            step=1,
            key="n_nozzle_rows",
        )
    )
    c1, c2 = st.columns(2)
    with c1:
        out["np_beam_sp"] = st.number_input(
            f"Beam spacing ({unit_label('length_mm', unit_system)})",
            value=500.0,
            step=float(display_value(50.0, "length_mm", unit_system)),
            key="np_bs",
        )
    with c2:
        out["np_override_t"] = st.number_input(
            f"Plate t override ({unit_label('length_mm', unit_system)}, 0=calc)",
            value=0.0,
            step=float(display_value(1.0, "length_mm", unit_system)),
            key="np_ov",
        )

    out = _render_catalogue_picker(out, unit_system, _sal)

    for _line in density_input_guidance(
        catalogue_id=out.get("nozzle_catalogue_id"),
        np_density=float(out["np_density"]),
    ):
        st.caption(f"• {_line}")

    out = _render_strainer_picker(out, _sal)
    return out


def _on_apply_catalogue_click(sel_id: str, salinity_ppt: float, unit_system: str) -> None:
    """Run before widgets on the rerun triggered by **Apply catalogue**."""
    patch = catalogue_patch_for_product(sel_id, salinity_ppt=salinity_ppt)
    _apply_catalogue_patch_to_session(patch, unit_system)
    st.session_state["_nozzle_catalogue_applied_msg"] = catalogue_select_label(sel_id)


def _render_catalogue_picker(out: dict, unit_system: str, salinity_ppt: float) -> dict:
    if _applied := st.session_state.pop("_nozzle_catalogue_applied_msg", None):
        st.success(
            f"Applied **{_applied}** — click main **Apply** to recompute."
        )

    products = list_catalogue_products_sorted()
    ids = [""] + [p["id"] for p in products]

    _stale = str(out.get("nozzle_catalogue_id") or st.session_state.get("nozzle_catalogue_sel") or "")
    for _w in catalogue_application_warnings(_stale):
        st.warning(f"**{_w.get('topic', '')}** — {_w.get('detail', '')}")
    if _stale and _stale not in ids:
        out["nozzle_catalogue_id"] = ""
        if "nozzle_catalogue_sel" in st.session_state:
            st.session_state["nozzle_catalogue_sel"] = ""

    sel = st.selectbox(
        "Product catalogue",
        options=ids,
        format_func=catalogue_select_label,
        key="nozzle_catalogue_sel",
    )
    out["nozzle_catalogue_id"] = sel or ""

    if sel:
        p = get_catalogue_product(sel)
        if p:
            _str_hint = catalogue_strainer_hint(p, salinity_ppt)
            st.caption(
                f"**{p['vendor']}** · {p.get('notes', '')}  "
                f"ρ **{p['density_per_m2_typical']:.0f} /m²** · Cd **{p['discharge_cd']:.2f}** · "
                f"body **{p.get('body_material', '—')}** · strainer **{_str_hint}**"
            )
            st.button(
                "Apply catalogue",
                key="nozzle_catalogue_apply",
                type="primary",
                on_click=_on_apply_catalogue_click,
                kwargs={
                    "sel_id": sel,
                    "salinity_ppt": salinity_ppt,
                    "unit_system": unit_system,
                },
            )
    return out


def _render_strainer_picker(out: dict, salinity_ppt: float) -> dict:
    _cat = get_catalogue_product(out.get("nozzle_catalogue_id"))
    _sugg = resolve_strainer_for_catalogue(_cat, salinity_ppt)
    _opts = list(STRAINER_MATERIAL_ORDER)
    _idx = _opts.index(_sugg) if _sugg in _opts else 0

    _svc = "seawater" if salinity_ppt > 15 else ("brackish" if salinity_ppt > 1 else "fresh")
    st.caption(
        f"Default strainer at **{salinity_ppt:.1f} ppt** ({_svc}): "
        f"**{strainer_material_label(_sugg)}**"
        + (
            " — metal underdrain; override to duplex / super duplex per client."
            if not _cat or str(_cat.get("strainer_body_family", "")).lower() == "metal"
            else " — matches polymer catalogue body."
        )
    )
    out["strainer_mat"] = st.selectbox(
        "Strainer material (per nozzle)",
        _opts,
        index=_idx,
        format_func=strainer_material_label,
        key="strainer_mat",
    )
    _adv = strainer_material_advisory(
        salinity_ppt=salinity_ppt,
        strainer_material=out["strainer_mat"],
    )
    for _f in _adv.get("findings") or []:
        _msg = f"**{_f.get('topic', '')}** — {_f.get('detail', '')}"
        if _f.get("severity") == "warning":
            st.warning(_msg)
        else:
            st.info(_msg)
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
    if patch.get("strainer_mat"):
        st.session_state["strainer_mat"] = str(patch["strainer_mat"])
    if patch.get("lateral_orifice_d_mm") is not None:
        st.session_state["lateral_orifice_d_mm"] = display_value(
            float(patch["lateral_orifice_d_mm"]), "length_mm", unit_system,
        )


def render_nozzle_catalogue_media_panel(
    unit_system: str,
    *,
    inputs: dict | None = None,
    salinity_ppt: float = 35.0,
) -> None:
    """Reference catalogue table + active underdrain line on main Media tab."""
    with st.expander("Underdrain product catalogue (reference)", expanded=False):
        st.caption(
            "Pressurized horizontal MMF underdrain — mushroom and wedge-wire references only. "
            f"Metal strainer default at {salinity_ppt:.1f} ppt: "
            f"**{strainer_material_label(suggested_strainer_material(salinity_ppt))}**."
        )
        rows = catalogue_display_rows(salinity_ppt=salinity_ppt)
        if unit_system == "imperial":
            disp = []
            for r in rows:
                row = dict(r)
                bore = fmt(row["bore_mm"], "length_mm", 2) if isinstance(row.get("bore_mm"), (int, float)) else "—"
                slot = fmt(row["slot_mm"], "length_mm", 3) if isinstance(row.get("slot_mm"), (int, float)) else "—"
                disp.append({
                    "Vendor": row["vendor"],
                    "Product": row["product"],
                    "Type": row["type"],
                    "Body": row.get("body", "—"),
                    f"Bore ({unit_label('length_mm', unit_system)})": bore,
                    f"Slot ({unit_label('length_mm', unit_system)})": slot,
                    "ρ typ (/m²)": row["ρ_typ (/m²)"],
                    "Cd": row["Cd"],
                    f"V max": fmt(float(row["V_max (m/s)"]), "velocity_m_s", 1),
                    "Strainer": row.get("strainer", "—"),
                    "Description": row.get("description", ""),
                })
            st.dataframe(pd.DataFrame(disp), use_container_width=True, hide_index=True)
        else:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if inputs:
        _sum = underdrain_inputs_summary(inputs)
        st.caption(
            f"**Active:** {_sum['catalogue_label']} · ρ **{_sum['np_density_per_m2']:.0f} /m²** · "
            f"Ø **{_sum['np_bore_mm']:.0f} mm** · strainer **{strainer_material_label(_sum['strainer_material'])}**"
        )


# Back-compat aliases
render_nozzle_catalogue_sidebar = _render_catalogue_picker
render_strainer_material_block = _render_strainer_picker
