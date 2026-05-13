"""ui/tab_mechanical.py — Mechanical tab for AQUASIGHT™ MMF."""
import io
import pandas as pd
import streamlit as st
from engine.drawing import vessel_section_elevation
from engine.nozzles import DN_SERIES, SCHEDULES, FLANGE_RATINGS
from ui.helpers import (
    fmt, ulbl, dv, operating_media_rows_display_df,
    nozzle_schedule_display_df, nozzle_schedule_total_weight_kg,
    saddle_catalogue_display_df, saddle_alternatives_display_df,
)


def render_tab_mechanical(inputs: dict, computed: dict):
    nominal_id     = computed["nominal_id"]
    lining_mm      = computed["lining_mm"]
    real_id        = computed["real_id"]
    cyl_len        = computed["cyl_len"]
    h_dish         = computed["h_dish"]
    material_name  = computed["material_name"]
    mat_info       = computed["mat_info"]
    mech           = computed["mech"]
    wt_np          = computed["wt_np"]
    np_dp_auto     = computed["np_dp_auto"]
    nozzle_sched   = computed["nozzle_sched"]
    w_noz          = computed["w_noz"]
    wt_body        = computed["wt_body"]
    end_geometry   = computed["end_geometry"]
    wt_sup         = computed["wt_sup"]
    wt_int         = computed["wt_int"]
    w_total        = computed["w_total"]
    wt_oper        = computed["wt_oper"]
    lining_result  = computed["lining_result"]
    wt_saddle      = computed["wt_saddle"]
    total_length   = computed["total_length"]
    vessel_areas   = computed["vessel_areas"]
    bw_exp         = computed["bw_exp"]

    layers          = inputs["layers"]
    shell_radio     = inputs["shell_radio"]
    head_radio      = inputs["head_radio"]
    design_pressure = inputs["design_pressure"]
    corrosion       = inputs["corrosion"]
    protection_type = inputs["protection_type"]
    project_name    = inputs["project_name"]
    doc_number      = inputs["doc_number"]
    revision        = inputs["revision"]
    client          = inputs["client"]
    engineer        = inputs["engineer"]
    design_temp     = inputs["design_temp"]
    streams         = inputs["streams"]
    n_filters       = inputs["n_filters"]
    redundancy      = inputs["redundancy"]
    nozzle_plate_h  = inputs["nozzle_plate_h"]
    collector_h     = inputs["collector_h"]

    st.subheader("Vessel geometry & mechanical")

    with st.expander("1 · Geometry", expanded=True):
        g1, g2, g3, g4, g5 = st.columns(5)
        g1.metric(f"Nominal ID ({ulbl('length_m')})",   fmt(nominal_id, 'length_m', 3))
        g2.metric(f"Lining ({ulbl('length_mm')})",     fmt(lining_mm, 'length_mm', 1))
        g3.metric(f"Real hyd. ID ({ulbl('length_m')})", fmt(real_id, 'length_m', 4),
                  delta=f"−{fmt(lining_mm * 2, 'length_mm', 1)}", delta_color="off")
        g4.metric(f"Cyl. length ({ulbl('length_m')})", fmt(cyl_len, 'length_m', 3))
        g5.metric(f"Dish depth ({ulbl('length_m')})",  fmt(h_dish, 'length_m', 3))
        st.caption(
            f"Real hydraulic ID = {fmt(nominal_id, 'length_m', 3)} − "
            f"2 × {fmt(lining_mm, 'length_mm', 1)} = **{fmt(real_id, 'length_m', 4)}**. "
            "This ID is used in all hydraulic calculations below."
        )

    with st.expander("2 · ASME wall thickness", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Material & radiography**")
            st.table(pd.DataFrame([
                ["Material",             material_name],
                ["Standard",             mat_info["standard"]],
                ["Allowable stress (S)", fmt(float(mech["allowable_stress"]), "stress_kgf_cm2", 2)],
                ["Shell radiography",    f"{shell_radio}  →  E={mech['shell_E']:.2f}"],
                ["Head radiography",     f"{head_radio}  →  E={mech['head_E']:.2f}"],
            ], columns=["Parameter", "Value"]))
        with c2:
            st.markdown("**Thickness results**")
            def fmt_t(t_min, t_des, overridden):
                flag = " ✏️ overridden" if overridden else ""
                return (
                    f"{fmt(float(t_des), 'length_mm', 0)}{flag}  "
                    f"(t_min={fmt(float(t_min), 'length_mm', 2)})"
                )
            st.table(pd.DataFrame([
                ["Design pressure",
                 f"{fmt(design_pressure, 'pressure_bar', 2)} "
                 f"({fmt(mech['p_kgf_cm2'], 'stress_kgf_cm2', 3)})"],
                ["Corrosion allowance",  fmt(corrosion, "length_mm", 1)],
                ["Shell t_min",          fmt(float(mech["t_shell_min_mm"]), "length_mm", 2)],
                ["Shell t_design",
                 fmt_t(mech['t_shell_min_mm'], mech['t_shell_design_mm'],
                       mech.get('shell_overridden', False))],
                ["Head t_min",           fmt(float(mech["t_head_min_mm"]), "length_mm", 2)],
                ["Head t_design",
                 fmt_t(mech['t_head_min_mm'], mech['t_head_design_mm'],
                       mech.get('head_overridden', False))],
                ["Nominal ID",           fmt(mech["nominal_id_m"], "length_m", 4)],
                ["Real hydraulic ID",    fmt(real_id, "length_m", 4)],
                ["Outside diameter",     fmt(mech["od_m"], "length_m", 4)],
            ], columns=["Parameter", "Value"]))

    with st.expander("3 · Nozzle plate design", expanded=True):
        st.info(f"Design ΔP auto-wired from Ergun dirty-bed result: "
                f"**{fmt(np_dp_auto, 'pressure_bar', 5)}** "
                f"({fmt(np_dp_auto * 100.0, 'pressure_kpa', 3)})")
        l1, l2, l3 = st.columns(3)
        l1.metric("ΔP hydraulic", fmt(wt_np["q_dp_kpa"], "pressure_kpa", 3))
        l2.metric("Media load",   fmt(wt_np["q_media_kpa"], "pressure_kpa", 3))
        l3.metric("Total load",   fmt(wt_np["q_total_kpa"], "pressure_kpa", 3))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Geometry & bore layout**")
            st.table(pd.DataFrame([
                ["Plate height",     fmt(wt_np["h_plate_m"], "length_m", 3)],
                ["Chord at plate",   fmt(wt_np["chord_m"], "length_m", 4)],
                ["Angle θ",         f"{wt_np['theta_deg']:.2f}°"],
                ["Cyl. plate area",  fmt(wt_np["area_cyl_m2"], "area_m2", 4)],
                ["Dish ends area",   fmt(wt_np["area_both_dish_m2"], "area_m2", 4)],
                ["Total plate area", fmt(wt_np["area_total_m2"], "area_m2", 4)],
                ["Number of bores",  str(wt_np["n_bores"])],
                ["Bore diameter",    fmt(wt_np["bore_diameter_mm"], "length_mm", 0)],
                ["Nozzle density",   f"{dv(wt_np['actual_density_per_m2'], 'quantity_per_m2'):.1f} {ulbl('quantity_per_m2')}"],
                ["Open area ratio",  f"{wt_np['open_ratio_pct']:.1f} %"],
            ], columns=["Parameter", "Value"]))
        with c2:
            st.markdown("**Thickness & support beams**")
            st.table(pd.DataFrame([
                ["Beam spacing",     fmt(wt_np["beam_spacing_mm"], "length_mm", 0)],
                ["t_min (Roark)",    fmt(float(wt_np["t_min_mm"]), "length_mm", 2)],
                ["t_design",        fmt(float(wt_np["t_design_mm"]), "length_mm", 0)],
                ["t used",          f"{fmt(float(wt_np['t_used_mm']), 'length_mm', 0)} ({wt_np['thickness_source']})"],
                ["Beam M_max",       fmt(wt_np["M_max_kNm"], "moment_knm", 1)],
                ["Required Z",       f"{wt_np['beam_Z_req_cm3']:.0f} cm³"],
                ["Selected section", wt_np["beam_section"]],
                ["No. of beams",     str(wt_np["n_beams"])],
                ["Plate weight",     fmt(wt_np["weight_plate_kg"], "mass_kg", 1)],
                ["Beams weight",     fmt(wt_np["weight_beams_kg"], "mass_kg", 1)],
                ["Total plate assy.", fmt(wt_np["weight_total_kg"], "mass_kg", 1)],
            ], columns=["Parameter", "Value"]))

    with st.expander("4 · Nozzle schedule", expanded=True):
        df_nozzle, _nk = nozzle_schedule_display_df(nozzle_sched)
        _k = _nk
        nozzle_wt_edited_df = st.data_editor(
            df_nozzle, use_container_width=True,
            hide_index=True, num_rows="dynamic",
            column_config={
                _k["service"]:     st.column_config.TextColumn(width=160),
                _k["flow"]:        st.column_config.NumberColumn(
                    format="%.2f", disabled=True),
                _k["dn"]:          st.column_config.SelectboxColumn(
                    options=DN_SERIES, width=85),
                _k["schedule"]:   st.column_config.SelectboxColumn(
                    options=SCHEDULES, width=90),
                _k["rating"]:      st.column_config.SelectboxColumn(
                    options=FLANGE_RATINGS, width=80),
                _k["velocity"]:   st.column_config.NumberColumn(
                    format="%.2f", disabled=True),
                _k["qty"]:         st.column_config.NumberColumn(width=55),
                _k["stub_l"]:     st.column_config.NumberColumn(
                    format="%.2f", disabled=True),
                _k["t_wall"]:      st.column_config.NumberColumn(
                    format="%.3f", disabled=True),
                _k["wt_ea"]:      st.column_config.NumberColumn(format="%.2f"),
                _k["wt_tot"]:     st.column_config.NumberColumn(format="%.1f"),
                _k["notes"]:      st.column_config.TextColumn(width=200),
            },
        )
        nozzle_wt_edited = nozzle_schedule_total_weight_kg(
            nozzle_wt_edited_df, _k["wt_tot"])
        if nozzle_wt_edited <= 0.0:
            nozzle_wt_edited = w_noz
        st.caption(
            "**DN** stays **integer mm** (ISO pipe tables / schedules). "
            "Flow, velocity, stub length and wall thickness follow the unit system but are "
            "read-only here; edit **weights** if you override vendor data."
        )

    with st.expander("5 · Vessel body (shell + 2 heads)", expanded=True):
        wa, wb = st.columns(2)
        with wa:
            st.markdown("**Cylindrical shell**")
            st.table(pd.DataFrame([
                ["Mean diameter",  fmt(wt_body["d_mean_shell_m"], "length_m", 4)],
                ["Wall thickness", fmt(float(mech["t_shell_design_mm"]), "length_mm", 1)],
                ["Surface area",   fmt(wt_body["area_shell_m2"], "area_m2", 3)],
                ["Metal volume",   fmt(wt_body["vol_shell_m3"], "volume_m3", 4)],
                ["Shell weight",   fmt(wt_body["weight_shell_kg"], "mass_kg", 1)],
            ], columns=["Item", "Value"]))
        with wb:
            st.markdown(f"**Dish ends × 2  ({end_geometry})**")
            st.table(pd.DataFrame([
                ["Mean diameter",      fmt(wt_body["d_mean_head_m"], "length_m", 4)],
                ["Wall thickness",     fmt(float(mech["t_head_design_mm"]), "length_mm", 1)],
                ["Surface area (one)", fmt(wt_body["area_one_head_m2"], "area_m2", 3)],
                ["Both heads weight",  fmt(wt_body["weight_two_heads_kg"], "mass_kg", 1)],
            ], columns=["Item", "Value"]))

    with st.expander("6 · Consolidated empty weight", expanded=True):
        w_total_final = (wt_body["weight_body_kg"] + nozzle_wt_edited
                         + wt_np["weight_total_kg"]
                         + wt_sup["weight_all_supports_kg"]
                         + wt_int["weight_internals_kg"])
        st.table(pd.DataFrame([
            ["Shell (cylindrical)",
             f"{fmt(wt_body['weight_shell_kg'], 'mass_kg', 1):>18}"],
            ["2 × Dish ends",
             f"{fmt(wt_body['weight_two_heads_kg'], 'mass_kg', 1):>18}"],
            ["Nozzles (stubs + flanges)",
             f"{fmt(nozzle_wt_edited, 'mass_kg', 1):>18}"],
            ["Nozzle plate + IPE beams",
             f"{fmt(wt_np['weight_total_kg'], 'mass_kg', 1):>18}"],
            [f"Supports ({wt_sup['support_type']})",
             f"{fmt(wt_sup['weight_all_supports_kg'], 'mass_kg', 1):>18}"],
            ["Strainer nozzles",
             f"{fmt(wt_int['weight_strainers_kg'], 'mass_kg', 1):>18}"],
            ["Air scour header",
             f"{fmt(wt_int['weight_air_header_kg'], 'mass_kg', 1):>18}"],
            ["Manholes",
             f"{fmt(wt_int['weight_manholes_kg'], 'mass_kg', 1):>18}"],
            ["─" * 30, "─" * 20],
            ["TOTAL EMPTY WEIGHT",
             f"{fmt(w_total_final, 'mass_kg', 1):>18}"],
            ["", f"= {fmt(w_total_final / 1000.0, 'mass_t', 3)}"],
        ], columns=["Component", "Weight"]))
        e1, e2, e3, e4, e5, e6 = st.columns(6)
        e1.metric("Shell+heads", fmt(wt_body["weight_body_kg"], "mass_kg", 0))
        e2.metric("Nozzles",     fmt(nozzle_wt_edited, "mass_kg", 0))
        e3.metric("Plate+beams", fmt(wt_np["weight_total_kg"], "mass_kg", 0))
        e4.metric("Supports",    fmt(wt_sup["weight_all_supports_kg"], "mass_kg", 0))
        e5.metric("Internals",   fmt(wt_int["weight_internals_kg"], "mass_kg", 0))
        e6.metric("TOTAL",       fmt(w_total_final / 1000.0, "mass_t", 3),
                  delta=fmt(w_total_final, "mass_kg", 0), delta_color="off")
        st.caption(
            "⚠️  Underdrains, platform/walkway, piping manifolds, "
            "and instrument connections not included."
        )

    with st.expander("7 · Operating weight & support loads", expanded=True):
        o1, o2, o3, o4, o5 = st.columns(5)
        o1.metric("Empty vessel",     fmt(wt_oper["w_empty_kg"], "mass_kg", 0))
        o2.metric("Lining / coating", fmt(wt_oper["w_lining_kg"], "mass_kg", 0))
        o3.metric("Media (dry)",      fmt(wt_oper["w_media_kg"], "mass_kg", 0))
        o4.metric("Process water",    fmt(wt_oper["w_water_kg"], "mass_kg", 0))
        o5.metric("Operating total",  fmt(wt_oper["w_operating_t"], "mass_t", 3),
                  delta=fmt(wt_oper["w_operating_kg"], "mass_kg", 0), delta_color="off")
        lining_label_op = (f"Internal {lining_result['protection_type'].lower()}"
                           if lining_result['protection_type'] != "None"
                           else "Internal lining / coating")
        st.table(pd.DataFrame([
            ["Empty vessel (steel structure)",
             f"{fmt(wt_oper['w_empty_kg'], 'mass_kg', 1):>18}"],
            [lining_label_op,
             f"{fmt(wt_oper['w_lining_kg'], 'mass_kg', 1):>18}"],
            ["Media — dry solid mass",
             f"{fmt(wt_oper['w_media_kg'], 'mass_kg', 1):>18}"],
            ["Process water (vessel full)",
             f"{fmt(wt_oper['w_water_kg'], 'mass_kg', 1):>18}"],
            ["─" * 30, "─" * 20],
            ["OPERATING WEIGHT",
             f"{fmt(wt_oper['w_operating_kg'], 'mass_kg', 1)}  =  "
             f"{fmt(wt_oper['w_operating_t'], 'mass_t', 3)}"],
        ], columns=["Component", "Weight"]))
        st.markdown("**Internal volume breakdown**")
        st.table(pd.DataFrame([
            ["Cylindrical shell (internal)",
             fmt(wt_oper["v_cylinder_m3"], "volume_m3", 3)],
            ["Two dish ends (internal)",
             fmt(wt_oper["v_heads_m3"], "volume_m3", 3)],
            ["Total internal volume",
             fmt(wt_oper["v_total_internal_m3"], "volume_m3", 3)],
            ["Media solid volume  Σ(depth × area × (1−ε₀))",
             fmt(wt_oper["v_solid_media_m3"], "volume_m3", 4)],
            ["Water volume  (total − solid media)",
             fmt(wt_oper["v_water_m3"], "volume_m3", 3)],
        ], columns=["Item", "Value"]))
        st.markdown("**Media layer detail**")
        st.dataframe(operating_media_rows_display_df(wt_oper["media_rows"]),
                     use_container_width=True, hide_index=True)
        st.markdown("**Support / saddle loads**")
        s1, s2, s3 = st.columns(3)
        s1.metric("Support type",       wt_sup["support_type"])
        s2.metric("Number of supports", str(wt_oper["n_supports"]))
        s3.metric("Load per support",
                  fmt(wt_oper["load_per_support_t"], "mass_t", 3),
                  delta=fmt(wt_oper["load_per_support_kN"], "force_kn", 1),
                  delta_color="off")

    with st.expander("8 · Saddle positioning & section selection", expanded=True):
        st.markdown("### Positioning (Zick method)")
        _aov_color = "🟢" if wt_saddle["a_over_R_ok"] else "🔴"
        sp1, sp2, sp3, sp4 = st.columns(4)
        sp1.metric("L / D ratio",        f"{wt_saddle['ld_ratio']:.2f}")
        sp2.metric("Spacing factor α",   f"{wt_saddle['alpha_pct']} %")
        sp3.metric("Saddle 1 from head", fmt(wt_saddle["saddle_1_from_left_m"], "length_m", 3))
        sp4.metric("Saddle 2 from head", fmt(wt_saddle["saddle_2_from_left_m"], "length_m", 3))
        st.table(pd.DataFrame([
            ["Total vessel length (T/T)", fmt(total_length, "length_m", 3)],
            ["Vessel OD",                  fmt(mech["od_m"], "length_m", 4)],
            ["L / D ratio",                f"{wt_saddle['ld_ratio']:.2f}"],
            ["Spacing factor α",          f"{wt_saddle['alpha_pct']} %"],
            ["Saddle 1 — from left head", fmt(wt_saddle["saddle_1_from_left_m"], "length_m", 3)],
            ["Saddle 2 — from left head", fmt(wt_saddle["saddle_2_from_left_m"], "length_m", 3)],
            ["Span between saddles",      fmt(wt_saddle["saddle_gap_m"], "length_m", 3)],
            ["a / R  (Zick parameter)",   f"{wt_saddle['a_over_R']:.3f}  {_aov_color}"],
            ["Contact arc length (120°)", fmt(wt_saddle["arc_m"], "length_m", 3)],
            ["Simplified saddle moment",  fmt(wt_saddle["m_saddle_kNm"], "moment_knm", 0)],
        ], columns=["Parameter", "Value"]))
        st.markdown("### Vertical reaction & section selection")
        _over = wt_saddle["overstressed"]
        sl1, sl2, sl3, sl4 = st.columns(4)
        sl1.metric("Operating weight",   fmt(wt_oper["w_operating_t"], "mass_t", 2))
        sl2.metric("Reaction / saddle",  fmt(wt_saddle["reaction_t"], "mass_t", 2),
                   delta=fmt(wt_saddle["reaction_kN"], "force_kn", 0), delta_color="off")
        _cap_t = wt_saddle["capacity_t"]
        _cap_fmt = fmt(float(_cap_t), "mass_t", 2) if isinstance(_cap_t, (int, float)) else str(_cap_t)
        sl3.metric("Catalogue capacity", _cap_fmt,
                   delta="⚠️ exceeds max" if _over else "✅ adequate",
                   delta_color="inverse" if _over else "normal")
        sl4.metric("Selected section",   wt_saddle["section"])
        if _over:
            _cap_e = wt_saddle["capacity_t"]
            _cap_e_fmt = (
                fmt(float(_cap_e), "mass_t", 1)
                if isinstance(_cap_e, (int, float)) else str(_cap_e))
            st.error(
                f"⚠️ **Load exceeds catalogue maximum** — reaction "
                f"{fmt(wt_saddle['reaction_t'], 'mass_t', 1)}/saddle > {_cap_e_fmt} max.  \n"
                f"Minimum **{wt_saddle['min_n_needed']} supports** required."
            )
        st.markdown("**Support arrangement alternatives**")
        st.dataframe(saddle_alternatives_display_df(wt_saddle["alternatives"]),
                     use_container_width=True, hide_index=True)
        st.markdown("### Full catalogue — all section types")
        st.dataframe(saddle_catalogue_display_df(wt_saddle["catalogue_rows"]),
                     use_container_width=True, hide_index=True)

    with st.expander("9 · Internal lining / coating", expanded=True):
        st.markdown("### Internal surface areas")
        ia1, ia2, ia3, ia4 = st.columns(4)
        ia1.metric("Cylinder",      fmt(vessel_areas["a_cylinder_m2"], "area_m2", 1))
        ia2.metric("Two dish ends", fmt(vessel_areas["a_two_heads_m2"], "area_m2", 1))
        ia3.metric("Nozzle plate",  fmt(vessel_areas["a_nozzle_plate_m2"], "area_m2", 1))
        ia4.metric("Total to coat", fmt(vessel_areas["a_total_m2"], "area_m2", 1))
        st.table(pd.DataFrame([
            ["Cylinder (shell)",
             fmt(vessel_areas["a_cylinder_m2"], "area_m2", 2),
             f"π × {fmt(real_id, 'length_m', 3)} × {fmt(cyl_len, 'length_m', 3)}"],
            ["One dish end",
             fmt(vessel_areas["a_one_head_m2"], "area_m2", 2),
             f"{end_geometry}"],
            ["Two dish ends",
             fmt(vessel_areas["a_two_heads_m2"], "area_m2", 2), ""],
            ["Shell total",
             fmt(vessel_areas["a_shell_m2"], "area_m2", 2),  ""],
            ["Nozzle plate (internal)",
             fmt(vessel_areas["a_nozzle_plate_m2"], "area_m2", 2), ""],
            ["Total internal area",
             fmt(vessel_areas["a_total_m2"], "area_m2", 2),  ""],
        ], columns=["Surface", "Area", "Basis"]))
        st.markdown(f"### Protection system — {protection_type}")
        if protection_type == "None":
            st.info("No internal lining or coating selected. Vessel relies on "
                    "corrosion allowance only.")
        else:
            lc1, lc2, lc3, lc4 = st.columns(4)
            lc1.metric("Area protected", fmt(lining_result["a_total_m2"], "area_m2", 1))
            lc2.metric("Lining weight",  fmt(lining_result["weight_kg"], "mass_kg", 0))
            lc3.metric("Material cost",  f"USD {lining_result['material_cost_usd']:,.0f}")
            lc4.metric("Total cost",     f"USD {lining_result['total_cost_usd']:,.0f}",
                       delta=f"Labour: USD {lining_result['labor_cost_usd']:,.0f}",
                       delta_color="off")
            st.markdown("**Specification & cost breakdown**")
            st.table(pd.DataFrame(
                [[k, v] for k, v in lining_result["detail"].items()],
                columns=["Parameter", "Value"]))

    with st.expander("10 · Theoretical elevation section", expanded=True):
        _show_exp_mech = st.toggle("Show expanded bed (BW condition)", value=True,
                                   key="mech_sec_exp")
        _sec_fig_mech = vessel_section_elevation(
            vessel_id_m      = nominal_id,
            total_length_m   = total_length,
            h_dish_m         = h_dish,
            nozzle_plate_h_m = nozzle_plate_h,
            layers           = layers,
            collector_h_m    = collector_h,
            bw_exp           = bw_exp,
            show_expansion   = _show_exp_mech,
        )
        st.pyplot(_sec_fig_mech, use_container_width=True)
        _sec_buf_mech = io.BytesIO()
        _sec_fig_mech.savefig(_sec_buf_mech, format="png", dpi=180, bbox_inches="tight",
                              facecolor=_sec_fig_mech.get_facecolor())
        _sec_buf_mech.seek(0)
        st.download_button(
            "⬇️ Download PNG",
            data=_sec_buf_mech,
            file_name=f"{project_name or 'MMF'}_section.png",
            mime="image/png",
            key="mech_sec_dl",
        )

    with st.expander("11 · Vessel fabrication data sheet", expanded=False):
        import datetime as _dt
        _today = _dt.date.today().strftime("%d-%b-%Y")
        tb1, tb2, tb3 = st.columns([2, 2, 1])
        with tb1:
            st.markdown("**Document**")
            st.table(pd.DataFrame([
                ["Project",     project_name],
                ["Doc. No.",    doc_number],
                ["Description", "Horizontal Multi-Media Filter"],
                ["Vessel/Tag",  "MMF-001"],
            ], columns=["Field", "Value"]))
        with tb2:
            st.markdown("**Approval**")
            st.table(pd.DataFrame([
                ["Date",        _today],
                ["Revision",    revision],
                ["Client",      client or "—"],
                ["Prepared by", engineer],
            ], columns=["Field", "Value"]))
        with tb3:
            st.metric("Filters",     streams * n_filters)
            st.metric("Active (N)",  streams * n_filters - redundancy * streams)
        st.divider()
        ds_left, ds_right = st.columns([1, 1.1])
        with ds_left:
            st.markdown("### Design Data")
            st.table(pd.DataFrame([
                ["Design Code",           "ASME VIII Div. 1"],
                ["Operating pressure",    f"{fmt(design_pressure * 0.7, 'pressure_bar', 2)} gauge  (≈ 70 % design)"],
                ["Design pressure",       f"{fmt(design_pressure, 'pressure_bar', 2)} gauge"],
                ["Test pressure (hydro)", f"{fmt(design_pressure * 1.5, 'pressure_bar', 2)} gauge"],
                ["Design temperature",    fmt(design_temp, "temperature_c", 0)],
                ["Corrosion allowance",   fmt(corrosion, "length_mm", 1)],
                ["Shell joint eff. E",    f"{mech['shell_E']:.2f}  ({shell_radio})"],
                ["Head joint eff. E",     f"{mech['head_E']:.2f}  ({head_radio})"],
                ["Head shape",            end_geometry],
            ], columns=["Parameter", "Value"]))
            st.markdown("### Material")
            st.table(pd.DataFrame([
                ["Shell & heads",       material_name],
                ["Allowable stress S",  fmt(float(mech["allowable_stress"]), "stress_kgf_cm2", 2)],
                ["Standard",            mat_info["standard"]],
                ["Nozzle plate",        material_name],
                ["Internal protection", protection_type],
            ], columns=["Component", "Specification"]))
            st.markdown("### Dimensional Data")
            st.table(pd.DataFrame([
                ["Internal diameter (ID)",  fmt(nominal_id * 1000.0, "length_mm", 0)],
                ["Outside diameter (OD)",   fmt(mech["od_m"] * 1000.0, "length_mm", 0)],
                ["Shell thickness (t_des)", f"{mech['t_shell_design_mm']} mm"],
                ["Head thickness (t_des)",  f"{mech['t_head_design_mm']} mm"],
                ["T/T length",              fmt(total_length, "length_m", 3)],
                ["Cylindrical length",      fmt(cyl_len, "length_m", 3)],
                ["Dish depth",              fmt(h_dish * 1000.0, "length_mm", 0)],
                ["Nozzle plate height",     fmt(nozzle_plate_h * 1000.0, "length_mm", 0)],
                ["Nozzle plate thickness",  f"{wt_np['t_design_mm']} mm"],
            ], columns=["Parameter", "Value"]))
            st.markdown("### Capacity & Weight")
            st.table(pd.DataFrame([
                ["Internal volume",
                 fmt(wt_oper["v_total_internal_m3"], "volume_m3", 2)],
                ["Empty weight",
                 f"{fmt(w_total, 'mass_kg', 0)}  =  {fmt(w_total / 1000.0, 'mass_t', 3)}"],
                ["Internal protection", protection_type],
                ["Operating weight (full)",
                 f"{fmt(wt_oper['w_operating_kg'], 'mass_kg', 0)}  =  "
                 f"{fmt(wt_oper['w_operating_t'], 'mass_t', 3)}"],
                ["Load / support",
                 f"{fmt(wt_oper['load_per_support_kN'], 'force_kn', 1)}  "
                 f"({fmt(wt_oper['load_per_support_t'], 'mass_t', 3)})"],
            ], columns=["Item", "Value"]))
        with ds_right:
            st.markdown("### Elevation View — Theoretical Section")
            _ds_fig = vessel_section_elevation(
                vessel_id_m      = nominal_id,
                total_length_m   = total_length,
                h_dish_m         = h_dish,
                nozzle_plate_h_m = nozzle_plate_h,
                layers           = layers,
                collector_h_m    = collector_h,
                bw_exp           = bw_exp,
                show_expansion   = True,
                figsize          = (10, 4.5),
            )
            st.pyplot(_ds_fig, use_container_width=True)
            st.markdown("### Media Bed")
            _media_rows_ds = []
            _cum_ds = nozzle_plate_h
            for lyr in layers:
                _d_mm = float(lyr["Depth"]) * 1000.0
                _bot_mm = float(_cum_ds) * 1000.0
                _top_mm = (float(_cum_ds) + float(lyr["Depth"])) * 1000.0
                _rho = lyr.get("rho_p_eff", "—")
                _rho_disp = (
                    round(dv(float(_rho), "density_kg_m3"), 0)
                    if isinstance(_rho, (int, float)) else _rho
                )
                _d10v = lyr.get("d10", "—")
                _d10_disp = (
                    round(dv(float(_d10v), "length_mm"), 2)
                    if isinstance(_d10v, (int, float)) else _d10v
                )
                _media_rows_ds.append({
                    "Layer": lyr["Type"],
                    f"Depth ({ulbl('length_mm')})": round(dv(_d_mm, "length_mm"), 2),
                    f"Bottom ({ulbl('length_mm')})": round(dv(_bot_mm, "length_mm"), 2),
                    f"Top ({ulbl('length_mm')})": round(dv(_top_mm, "length_mm"), 2),
                    f"d10 ({ulbl('length_mm')})": _d10_disp,
                    "CU": lyr.get("cu", "—"),
                    "ε₀": lyr.get("epsilon0", "—"),
                    f"ρ ({ulbl('density_kg_m3')})": _rho_disp,
                })
                _cum_ds += lyr["Depth"]
            st.dataframe(pd.DataFrame(_media_rows_ds),
                         use_container_width=True, hide_index=True)
        st.divider()
        st.markdown("### Nomenclature of Nozzles")
        _df_fab_noz, _ = nozzle_schedule_display_df(nozzle_sched)
        st.dataframe(_df_fab_noz, use_container_width=True, hide_index=True)
        st.divider()
        st.markdown("### Vessel Standards")
        st.table(pd.DataFrame([
            ["Design Code",      "ASME Boiler & Pressure Vessel Code Sect. VIII Div. 1"],
            ["Material (shell)", mat_info["standard"]],
            ["Flanges",          "ASME B16.5 / EN 1092-1"],
            ["Nozzles",          "ASME B36.10 / B36.19"],
            ["Welding",          "ASME IX — Welding & Brazing Qualifications"],
            ["NDE",             f"Shell: {shell_radio}   Head: {head_radio}"],
            ["Corrosion allow.", fmt(corrosion, "length_mm", 1)],
            ["Internal coating", protection_type],
        ], columns=["Standard / Item", "Reference / Value"]))

    st.divider()
    mm1, mm2, mm3, mm4 = st.columns(4)
    mm1.metric(f"Empty weight ({ulbl('mass_kg')})",     fmt(w_total, 'mass_kg', 0))
    mm2.metric(f"Operating weight ({ulbl('mass_kg')})", fmt(wt_oper['w_operating_kg'], 'mass_kg', 0))
    mm3.metric(f"OD ({ulbl('length_mm')})",             fmt(mech['od_m'] * 1000, 'length_mm', 0))
    mm4.metric(f"T/T length ({ulbl('length_m')})",      fmt(total_length, 'length_m', 3))
