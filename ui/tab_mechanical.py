"""ui/tab_mechanical.py — Mechanical tab for AQUASIGHT™ MMF."""
import io
import pandas as pd
import streamlit as st
from engine.drawing import vessel_section_elevation
from engine.nozzles import DN_SERIES, SCHEDULES, FLANGE_RATINGS


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
        g1.metric("Nominal ID",   f"{nominal_id:.3f} m")
        g2.metric("Lining",       f"{lining_mm:.1f} mm")
        g3.metric("Real hyd. ID", f"{real_id:.4f} m",
                  delta=f"−{lining_mm*2:.1f} mm", delta_color="off")
        g4.metric("Cyl. length",  f"{cyl_len:.3f} m")
        g5.metric("Dish depth",   f"{h_dish:.3f} m")
        st.caption(
            f"Real hydraulic ID = {nominal_id:.3f} m − "
            f"2 × {lining_mm:.1f} mm = **{real_id:.4f} m**. "
            "This ID is used in all hydraulic calculations below."
        )

    with st.expander("2 · ASME wall thickness", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Material & radiography**")
            st.table(pd.DataFrame([
                ["Material",             material_name],
                ["Standard",             mat_info["standard"]],
                ["Allowable stress (S)", f"{mech['allowable_stress']} kg/cm²"],
                ["Shell radiography",    f"{shell_radio}  →  E={mech['shell_E']:.2f}"],
                ["Head radiography",     f"{head_radio}  →  E={mech['head_E']:.2f}"],
            ], columns=["Parameter", "Value"]))
        with c2:
            st.markdown("**Thickness results**")
            def fmt_t(t_min, t_des, overridden):
                flag = " ✏️ overridden" if overridden else ""
                return f"{t_des} mm{flag}  (t_min={t_min:.2f} mm)"
            st.table(pd.DataFrame([
                ["Design pressure",
                 f"{design_pressure:.2f} bar ({mech['p_kgf_cm2']:.3f} kg/cm²)"],
                ["Corrosion allowance",  f"{corrosion:.1f} mm"],
                ["Shell t_min",          f"{mech['t_shell_min_mm']:.2f} mm"],
                ["Shell t_design",
                 fmt_t(mech['t_shell_min_mm'], mech['t_shell_design_mm'],
                       mech.get('shell_overridden', False))],
                ["Head t_min",           f"{mech['t_head_min_mm']:.2f} mm"],
                ["Head t_design",
                 fmt_t(mech['t_head_min_mm'], mech['t_head_design_mm'],
                       mech.get('head_overridden', False))],
                ["Nominal ID",           f"{mech['nominal_id_m']:.4f} m"],
                ["Real hydraulic ID",    f"{real_id:.4f} m"],
                ["Outside diameter",     f"{mech['od_m']:.4f} m"],
            ], columns=["Parameter", "Value"]))

    with st.expander("3 · Nozzle plate design", expanded=True):
        st.info(f"Design ΔP auto-wired from Ergun dirty-bed result: "
                f"**{np_dp_auto:.5f} bar** "
                f"({np_dp_auto*1e5/1000:.3f} kPa)")
        l1, l2, l3 = st.columns(3)
        l1.metric("ΔP hydraulic", f"{wt_np['q_dp_kpa']:.3f} kPa")
        l2.metric("Media load",   f"{wt_np['q_media_kpa']:.3f} kPa")
        l3.metric("Total load",   f"{wt_np['q_total_kpa']:.3f} kPa")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Geometry & bore layout**")
            st.table(pd.DataFrame([
                ["Plate height",     f"{wt_np['h_plate_m']:.3f} m"],
                ["Chord at plate",   f"{wt_np['chord_m']:.4f} m"],
                ["Angle θ",         f"{wt_np['theta_deg']:.2f}°"],
                ["Cyl. plate area",  f"{wt_np['area_cyl_m2']:.4f} m²"],
                ["Dish ends area",   f"{wt_np['area_both_dish_m2']:.4f} m²"],
                ["Total plate area", f"{wt_np['area_total_m2']:.4f} m²"],
                ["Number of bores",  str(wt_np["n_bores"])],
                ["Bore diameter",    f"{wt_np['bore_diameter_mm']:.0f} mm"],
                ["Nozzle density",   f"{wt_np['actual_density_per_m2']:.1f} /m²"],
                ["Open area ratio",  f"{wt_np['open_ratio_pct']:.1f} %"],
            ], columns=["Parameter", "Value"]))
        with c2:
            st.markdown("**Thickness & support beams**")
            st.table(pd.DataFrame([
                ["Beam spacing",     f"{wt_np['beam_spacing_mm']:.0f} mm"],
                ["t_min (Roark)",    f"{wt_np['t_min_mm']:.2f} mm"],
                ["t_design",        f"{wt_np['t_design_mm']} mm"],
                ["t used",          f"{wt_np['t_used_mm']} mm  ({wt_np['thickness_source']})"],
                ["Beam M_max",       f"{wt_np['M_max_kNm']:.1f} kN·m"],
                ["Required Z",       f"{wt_np['beam_Z_req_cm3']:.0f} cm³"],
                ["Selected section", wt_np["beam_section"]],
                ["No. of beams",     str(wt_np["n_beams"])],
                ["Plate weight",     f"{wt_np['weight_plate_kg']:,.1f} kg"],
                ["Beams weight",     f"{wt_np['weight_beams_kg']:,.1f} kg"],
                ["Total plate assy.",f"{wt_np['weight_total_kg']:,.1f} kg"],
            ], columns=["Parameter", "Value"]))

    with st.expander("4 · Nozzle schedule", expanded=True):
        df_nozzle = pd.DataFrame(nozzle_sched)
        nozzle_wt_edited_df = st.data_editor(
            df_nozzle, use_container_width=True,
            hide_index=True, num_rows="dynamic",
            column_config={
                "Service":        st.column_config.TextColumn(width=160),
                "DN (mm)":        st.column_config.SelectboxColumn(
                                      options=DN_SERIES, width=85),
                "Schedule":       st.column_config.SelectboxColumn(
                                      options=SCHEDULES, width=90),
                "Rating":         st.column_config.SelectboxColumn(
                                      options=FLANGE_RATINGS, width=80),
                "Qty":            st.column_config.NumberColumn(width=55),
                "Wt/nozzle (kg)": st.column_config.NumberColumn(format="%.1f"),
                "Total wt (kg)":  st.column_config.NumberColumn(format="%.1f"),
            })
        nozzle_wt_edited = (nozzle_wt_edited_df["Total wt (kg)"].sum()
                            if "Total wt (kg)" in nozzle_wt_edited_df.columns else w_noz)

    with st.expander("5 · Vessel body (shell + 2 heads)", expanded=True):
        wa, wb = st.columns(2)
        with wa:
            st.markdown("**Cylindrical shell**")
            st.table(pd.DataFrame([
                ["Mean diameter",  f"{wt_body['d_mean_shell_m']:.4f} m"],
                ["Wall thickness", f"{mech['t_shell_design_mm']} mm"],
                ["Surface area",   f"{wt_body['area_shell_m2']:.3f} m²"],
                ["Metal volume",   f"{wt_body['vol_shell_m3']:.4f} m³"],
                ["Shell weight",   f"{wt_body['weight_shell_kg']:,.1f} kg"],
            ], columns=["Item", "Value"]))
        with wb:
            st.markdown(f"**Dish ends × 2  ({end_geometry})**")
            st.table(pd.DataFrame([
                ["Mean diameter",      f"{wt_body['d_mean_head_m']:.4f} m"],
                ["Wall thickness",     f"{mech['t_head_design_mm']} mm"],
                ["Surface area (one)", f"{wt_body['area_one_head_m2']:.3f} m²"],
                ["Both heads weight",  f"{wt_body['weight_two_heads_kg']:,.1f} kg"],
            ], columns=["Item", "Value"]))

    with st.expander("6 · Consolidated empty weight", expanded=True):
        w_total_final = (wt_body["weight_body_kg"] + nozzle_wt_edited
                         + wt_np["weight_total_kg"]
                         + wt_sup["weight_all_supports_kg"]
                         + wt_int["weight_internals_kg"])
        st.table(pd.DataFrame([
            ["Shell (cylindrical)",
             f"{wt_body['weight_shell_kg']:>12,.1f} kg"],
            ["2 × Dish ends",
             f"{wt_body['weight_two_heads_kg']:>12,.1f} kg"],
            ["Nozzles (stubs + flanges)",
             f"{nozzle_wt_edited:>12,.1f} kg"],
            ["Nozzle plate + IPE beams",
             f"{wt_np['weight_total_kg']:>12,.1f} kg"],
            [f"Supports ({wt_sup['support_type']})",
             f"{wt_sup['weight_all_supports_kg']:>12,.1f} kg"],
            ["Strainer nozzles",
             f"{wt_int['weight_strainers_kg']:>12,.1f} kg"],
            ["Air scour header",
             f"{wt_int['weight_air_header_kg']:>12,.1f} kg"],
            ["Manholes",
             f"{wt_int['weight_manholes_kg']:>12,.1f} kg"],
            ["─" * 30, "─" * 16],
            ["TOTAL EMPTY WEIGHT",
             f"{w_total_final:>12,.1f} kg"],
            ["", f"= {w_total_final/1000:.3f} t"],
        ], columns=["Component", "Weight"]))
        e1, e2, e3, e4, e5, e6 = st.columns(6)
        e1.metric("Shell+heads", f"{wt_body['weight_body_kg']:,.0f} kg")
        e2.metric("Nozzles",     f"{nozzle_wt_edited:,.0f} kg")
        e3.metric("Plate+beams", f"{wt_np['weight_total_kg']:,.0f} kg")
        e4.metric("Supports",    f"{wt_sup['weight_all_supports_kg']:,.0f} kg")
        e5.metric("Internals",   f"{wt_int['weight_internals_kg']:,.0f} kg")
        e6.metric("TOTAL",       f"{w_total_final/1000:.3f} t",
                  delta=f"{w_total_final:,.0f} kg", delta_color="off")
        st.caption(
            "⚠️  Underdrains, platform/walkway, piping manifolds, "
            "and instrument connections not included."
        )

    with st.expander("7 · Operating weight & support loads", expanded=True):
        o1, o2, o3, o4, o5 = st.columns(5)
        o1.metric("Empty vessel",     f"{wt_oper['w_empty_kg']:,.0f} kg")
        o2.metric("Lining / coating", f"{wt_oper['w_lining_kg']:,.0f} kg")
        o3.metric("Media (dry)",      f"{wt_oper['w_media_kg']:,.0f} kg")
        o4.metric("Process water",    f"{wt_oper['w_water_kg']:,.0f} kg")
        o5.metric("Operating total",  f"{wt_oper['w_operating_t']:.3f} t",
                  delta=f"{wt_oper['w_operating_kg']:,.0f} kg", delta_color="off")
        lining_label_op = (f"Internal {lining_result['protection_type'].lower()}"
                           if lining_result['protection_type'] != "None"
                           else "Internal lining / coating")
        st.table(pd.DataFrame([
            ["Empty vessel (steel structure)",
             f"{wt_oper['w_empty_kg']:>12,.1f} kg"],
            [lining_label_op,
             f"{wt_oper['w_lining_kg']:>12,.1f} kg"],
            ["Media — dry solid mass",
             f"{wt_oper['w_media_kg']:>12,.1f} kg"],
            ["Process water (vessel full)",
             f"{wt_oper['w_water_kg']:>12,.1f} kg"],
            ["─" * 30, "─" * 16],
            ["OPERATING WEIGHT",
             f"{wt_oper['w_operating_kg']:>12,.1f} kg  =  {wt_oper['w_operating_t']:.3f} t"],
        ], columns=["Component", "Weight"]))
        st.markdown("**Internal volume breakdown**")
        st.table(pd.DataFrame([
            ["Cylindrical shell (internal)",
             f"{wt_oper['v_cylinder_m3']:.3f} m³"],
            ["Two dish ends (internal)",
             f"{wt_oper['v_heads_m3']:.3f} m³"],
            ["Total internal volume",
             f"{wt_oper['v_total_internal_m3']:.3f} m³"],
            ["Media solid volume  Σ(depth × area × (1−ε₀))",
             f"{wt_oper['v_solid_media_m3']:.4f} m³"],
            ["Water volume  (total − solid media)",
             f"{wt_oper['v_water_m3']:.3f} m³"],
        ], columns=["Item", "Value"]))
        st.markdown("**Media layer detail**")
        st.dataframe(pd.DataFrame(wt_oper["media_rows"]),
                     use_container_width=True, hide_index=True)
        st.markdown("**Support / saddle loads**")
        s1, s2, s3 = st.columns(3)
        s1.metric("Support type",       wt_sup["support_type"])
        s2.metric("Number of supports", str(wt_oper["n_supports"]))
        s3.metric("Load per support",
                  f"{wt_oper['load_per_support_t']:.3f} t",
                  delta=f"{wt_oper['load_per_support_kN']:.1f} kN",
                  delta_color="off")

    with st.expander("8 · Saddle positioning & section selection", expanded=True):
        st.markdown("### Positioning (Zick method)")
        _aov_color = "🟢" if wt_saddle["a_over_R_ok"] else "🔴"
        sp1, sp2, sp3, sp4 = st.columns(4)
        sp1.metric("L / D ratio",        f"{wt_saddle['ld_ratio']:.2f}")
        sp2.metric("Spacing factor α",   f"{wt_saddle['alpha_pct']} %")
        sp3.metric("Saddle 1 from head", f"{wt_saddle['saddle_1_from_left_m']:.3f} m")
        sp4.metric("Saddle 2 from head", f"{wt_saddle['saddle_2_from_left_m']:.3f} m")
        st.table(pd.DataFrame([
            ["Total vessel length (T/T)", f"{total_length:.3f} m"],
            ["Vessel OD",                  f"{mech['od_m']:.4f} m"],
            ["L / D ratio",                f"{wt_saddle['ld_ratio']:.2f}"],
            ["Spacing factor α",          f"{wt_saddle['alpha_pct']} %"],
            ["Saddle 1 — from left head", f"{wt_saddle['saddle_1_from_left_m']:.3f} m"],
            ["Saddle 2 — from left head", f"{wt_saddle['saddle_2_from_left_m']:.3f} m"],
            ["Span between saddles",      f"{wt_saddle['saddle_gap_m']:.3f} m"],
            ["a / R  (Zick parameter)",   f"{wt_saddle['a_over_R']:.3f}  {_aov_color}"],
            ["Contact arc length (120°)", f"{wt_saddle['arc_m']:.3f} m"],
            ["Simplified saddle moment",  f"{wt_saddle['m_saddle_kNm']:.0f} kN·m"],
        ], columns=["Parameter", "Value"]))
        st.markdown("### Vertical reaction & section selection")
        _over = wt_saddle["overstressed"]
        sl1, sl2, sl3, sl4 = st.columns(4)
        sl1.metric("Operating weight",   f"{wt_oper['w_operating_t']:.2f} t")
        sl2.metric("Reaction / saddle",  f"{wt_saddle['reaction_t']:.2f} t",
                   delta=f"{wt_saddle['reaction_kN']:.0f} kN", delta_color="off")
        sl3.metric("Catalogue capacity", f"{wt_saddle['capacity_t']} t",
                   delta="⚠️ exceeds max" if _over else "✅ adequate",
                   delta_color="inverse" if _over else "normal")
        sl4.metric("Selected section",   wt_saddle["section"])
        if _over:
            st.error(
                f"⚠️ **Load exceeds catalogue maximum** — reaction "
                f"{wt_saddle['reaction_t']:.1f} t/saddle > {wt_saddle['capacity_t']} t max.  \n"
                f"Minimum **{wt_saddle['min_n_needed']} supports** required."
            )
        st.markdown("**Support arrangement alternatives**")
        _alt_rows = []
        for a in wt_saddle["alternatives"]:
            _status_a = ("▶ current" if a["is_current"] else
                         ("✅ fits" if a["fits_catalogue"] else "❌ exceeds max"))
            _alt_rows.append({
                "Supports":              a["n_saddles"],
                "Reaction/saddle (t)":   a["reaction_t"],
                "Section":               a["section"],
                "Capacity (t)":          a["capacity_t"],
                "Status":                _status_a,
                "Struct. wt/saddle (kg)":a["struct_wt_ea_kg"],
                "Total struct. wt (kg)": a["struct_wt_total_kg"],
            })
        st.dataframe(pd.DataFrame(_alt_rows), use_container_width=True, hide_index=True)
        st.markdown("### Full catalogue — all section types")
        st.dataframe(pd.DataFrame(wt_saddle["catalogue_rows"]),
                     use_container_width=True, hide_index=True)

    with st.expander("9 · Internal lining / coating", expanded=True):
        st.markdown("### Internal surface areas")
        ia1, ia2, ia3, ia4 = st.columns(4)
        ia1.metric("Cylinder",      f"{vessel_areas['a_cylinder_m2']:.1f} m²")
        ia2.metric("Two dish ends", f"{vessel_areas['a_two_heads_m2']:.1f} m²")
        ia3.metric("Nozzle plate",  f"{vessel_areas['a_nozzle_plate_m2']:.1f} m²")
        ia4.metric("Total to coat", f"{vessel_areas['a_total_m2']:.1f} m²")
        st.table(pd.DataFrame([
            ["Cylinder (shell)",
             f"{vessel_areas['a_cylinder_m2']:.2f} m²",
             f"π × {real_id:.3f} × {cyl_len:.3f}"],
            ["One dish end",
             f"{vessel_areas['a_one_head_m2']:.2f} m²",
             f"{end_geometry}"],
            ["Two dish ends",
             f"{vessel_areas['a_two_heads_m2']:.2f} m²", ""],
            ["Shell total",
             f"{vessel_areas['a_shell_m2']:.2f} m²",  ""],
            ["Nozzle plate (internal)",
             f"{vessel_areas['a_nozzle_plate_m2']:.2f} m²", ""],
            ["Total internal area",
             f"{vessel_areas['a_total_m2']:.2f} m²",  ""],
        ], columns=["Surface", "Area", "Basis"]))
        st.markdown(f"### Protection system — {protection_type}")
        if protection_type == "None":
            st.info("No internal lining or coating selected. Vessel relies on "
                    "corrosion allowance only.")
        else:
            lc1, lc2, lc3, lc4 = st.columns(4)
            lc1.metric("Area protected", f"{lining_result['a_total_m2']:.1f} m²")
            lc2.metric("Lining weight",  f"{lining_result['weight_kg']:,.0f} kg")
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
                ["Operating pressure",    f"{design_pressure * 0.7:.2f} barg  (≈ 70 % design)"],
                ["Design pressure",       f"{design_pressure:.2f} barg"],
                ["Test pressure (hydro)", f"{design_pressure * 1.5:.2f} barg"],
                ["Design temperature",    f"{design_temp:.0f} °C"],
                ["Corrosion allowance",   f"{corrosion:.1f} mm"],
                ["Shell joint eff. E",    f"{mech['shell_E']:.2f}  ({shell_radio})"],
                ["Head joint eff. E",     f"{mech['head_E']:.2f}  ({head_radio})"],
                ["Head shape",            end_geometry],
            ], columns=["Parameter", "Value"]))
            st.markdown("### Material")
            st.table(pd.DataFrame([
                ["Shell & heads",       material_name],
                ["Allowable stress S",  f"{mech['allowable_stress']} kg/cm²"],
                ["Standard",            mat_info["standard"]],
                ["Nozzle plate",        material_name],
                ["Internal protection", protection_type],
            ], columns=["Component", "Specification"]))
            st.markdown("### Dimensional Data")
            st.table(pd.DataFrame([
                ["Internal diameter (ID)",  f"{nominal_id * 1000:.0f} mm"],
                ["Outside diameter (OD)",   f"{mech['od_m'] * 1000:.0f} mm"],
                ["Shell thickness (t_des)", f"{mech['t_shell_design_mm']} mm"],
                ["Head thickness (t_des)",  f"{mech['t_head_design_mm']} mm"],
                ["T/T length",              f"{total_length:.3f} m"],
                ["Cylindrical length",      f"{cyl_len:.3f} m"],
                ["Dish depth",              f"{h_dish * 1000:.0f} mm"],
                ["Nozzle plate height",     f"{nozzle_plate_h * 1000:.0f} mm"],
                ["Nozzle plate thickness",  f"{wt_np['t_design_mm']} mm"],
            ], columns=["Parameter", "Value"]))
            st.markdown("### Capacity & Weight")
            st.table(pd.DataFrame([
                ["Internal volume",
                 f"{wt_oper['v_total_internal_m3']:.2f} m³"],
                ["Empty weight",
                 f"{w_total:,.0f} kg  =  {w_total/1000:.3f} t"],
                ["Internal protection", protection_type],
                ["Operating weight (full)",
                 f"{wt_oper['w_operating_kg']:,.0f} kg  =  {wt_oper['w_operating_t']:.3f} t"],
                ["Load / support",
                 f"{wt_oper['load_per_support_kN']:.1f} kN  ({wt_oper['load_per_support_t']:.3f} t)"],
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
                _media_rows_ds.append({
                    "Layer":       lyr["Type"],
                    "Depth (mm)":  int(lyr["Depth"] * 1000),
                    "Bottom (mm)": int(_cum_ds * 1000),
                    "Top (mm)":    int((_cum_ds + lyr["Depth"]) * 1000),
                    "d10 (mm)":    lyr.get("d10", "—"),
                    "CU":          lyr.get("cu", "—"),
                    "ε₀":          lyr.get("epsilon0", "—"),
                    "ρ (kg/m³)":   lyr.get("rho_p_eff", "—"),
                })
                _cum_ds += lyr["Depth"]
            st.dataframe(pd.DataFrame(_media_rows_ds),
                         use_container_width=True, hide_index=True)
        st.divider()
        st.markdown("### Nomenclature of Nozzles")
        st.dataframe(pd.DataFrame(nozzle_sched),
                     use_container_width=True, hide_index=True)
        st.divider()
        st.markdown("### Vessel Standards")
        st.table(pd.DataFrame([
            ["Design Code",      "ASME Boiler & Pressure Vessel Code Sect. VIII Div. 1"],
            ["Material (shell)", mat_info["standard"]],
            ["Flanges",          "ASME B16.5 / EN 1092-1"],
            ["Nozzles",          "ASME B36.10 / B36.19"],
            ["Welding",          "ASME IX — Welding & Brazing Qualifications"],
            ["NDE",             f"Shell: {shell_radio}   Head: {head_radio}"],
            ["Corrosion allow.", f"{corrosion:.1f} mm"],
            ["Internal coating", protection_type],
        ], columns=["Standard / Item", "Reference / Value"]))

    st.divider()
    mm1, mm2, mm3, mm4 = st.columns(4)
    mm1.metric("Empty weight",     f"{w_total/1000:.3f} t")
    mm2.metric("Operating weight", f"{wt_oper['w_operating_t']:.3f} t")
    mm3.metric("OD",               f"{mech['od_m']*1000:.0f} mm")
    mm4.metric("T/T length",       f"{total_length:.3f} m")
