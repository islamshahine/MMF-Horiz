"""ui/tab_report.py — Report tab for AQUASIGHT™ MMF."""
import streamlit as st
from engine.project_io import (
    inputs_to_json, json_to_inputs, get_widget_state_map, default_filename,
)

try:
    from docx import Document as _DocxDocument
    from docx.enum.text import WD_ALIGN_PARAGRAPH as _WD_ALIGN
    _DOCX_OK = True
except ImportError:
    _DOCX_OK = False


def render_tab_report(inputs: dict, computed: dict):
    wt_body       = computed["wt_body"]
    w_noz         = computed["w_noz"]
    wt_np         = computed["wt_np"]
    wt_sup        = computed["wt_sup"]
    wt_int        = computed["wt_int"]
    lining_result = computed["lining_result"]
    q_per_filter  = computed["q_per_filter"]
    avg_area      = computed["avg_area"]
    rho_feed      = computed["rho_feed"]
    mu_feed       = computed["mu_feed"]
    rho_bw        = computed["rho_bw"]
    mu_bw         = computed["mu_bw"]
    base          = computed["base"]
    bw_dp         = computed["bw_dp"]
    filt_cycles   = computed["filt_cycles"]
    bw_col        = computed["bw_col"]
    bw_sizing     = computed["bw_sizing"]
    hyd_prof      = computed["hyd_prof"]
    energy        = computed["energy"]
    cart_result   = computed["cart_result"]
    nominal_id    = computed["nominal_id"]
    real_id       = computed["real_id"]
    mech          = computed["mech"]
    total_length  = computed["total_length"]
    cyl_len       = computed["cyl_len"]
    end_geometry  = computed["end_geometry"]
    material_name = computed["material_name"]
    wt_oper       = computed["wt_oper"]
    wt_saddle     = computed["wt_saddle"]
    w_total       = computed["w_total"]

    project_name    = inputs["project_name"]
    doc_number      = inputs["doc_number"]
    revision        = inputs["revision"]
    client          = inputs["client"]
    engineer        = inputs["engineer"]
    total_flow      = inputs["total_flow"]
    streams         = inputs["streams"]
    n_filters       = inputs["n_filters"]
    redundancy      = inputs["redundancy"]
    feed_sal        = inputs["feed_sal"]
    bw_sal          = inputs["bw_sal"]
    feed_temp       = inputs["feed_temp"]
    bw_temp         = inputs["bw_temp"]
    dp_trigger_bar  = inputs["dp_trigger_bar"]
    solid_loading   = inputs["solid_loading"]
    bw_total_min    = inputs["bw_total_min"]
    bw_s_drain      = inputs["bw_s_drain"]
    bw_s_air        = inputs["bw_s_air"]
    bw_s_airw       = inputs["bw_s_airw"]
    bw_s_hw         = inputs["bw_s_hw"]
    bw_s_settle     = inputs["bw_s_settle"]
    bw_s_fill       = inputs["bw_s_fill"]
    design_pressure = inputs["design_pressure"]
    corrosion       = inputs["corrosion"]
    shell_radio     = inputs["shell_radio"]
    head_radio      = inputs["head_radio"]
    nozzle_plate_h  = inputs["nozzle_plate_h"]
    np_density      = inputs["np_density"]
    np_bore_dia     = inputs["np_bore_dia"]
    bw_velocity     = inputs["bw_velocity"]
    freeboard_mm    = inputs["freeboard_mm"]
    air_scour_rate  = inputs["air_scour_rate"]

    w_total_rep = (wt_body["weight_body_kg"] + w_noz
                   + wt_np["weight_total_kg"]
                   + wt_sup["weight_all_supports_kg"]
                   + wt_int["weight_internals_kg"])
    _has_lining = lining_result["protection_type"] != "None"

    # ── Project Save / Load ──────────────────────────────────────────────────
    with st.expander("💾 Project Save / Load", expanded=False):
        io_c1, io_c2 = st.columns(2)
        with io_c1:
            st.markdown("**Save current project**")
            _json_str  = inputs_to_json(inputs)
            _fname     = default_filename(inputs.get("project_name", "project"),
                                          inputs.get("doc_number", ""))
            st.download_button(
                label="⬇ Download project JSON",
                data=_json_str,
                file_name=_fname,
                mime="application/json",
                use_container_width=True,
            )
            st.caption("Saves all inputs. Load the file in a future session to restore.")
        with io_c2:
            st.markdown("**Load project from file**")
            _uploaded = st.file_uploader("Upload .mmf.json", type=["json"],
                                          label_visibility="collapsed")
            if _uploaded is not None:
                try:
                    _loaded  = json_to_inputs(_uploaded.read().decode("utf-8"))
                    _wgt_map = get_widget_state_map(_loaded)
                    for _wk, _wv in _wgt_map.items():
                        st.session_state[_wk] = _wv
                    st.success("Project loaded — refreshing…")
                    st.rerun()
                except Exception as _err:
                    st.error(f"Load failed: {_err}")
    st.divider()

    st.markdown("### Report builder")
    st.caption(
        "Select the sections to include. "
        "Identification (cover, project info, sign-off) is always present."
    )

    sel_c1, sel_c2, sel_c3, sel_c4 = st.columns(4)
    with sel_c1:
        st.markdown("**B · Process Design**")
        s_process = st.checkbox("Process basis",                   value=True, key="rs_proc")
        s_water   = st.checkbox("Water properties",                value=True, key="rs_water")
        s_media   = st.checkbox("Media configuration",             value=True, key="rs_media")
        s_dp      = st.checkbox("Filtration ΔP",                  value=True, key="rs_dp")
        s_cycle   = st.checkbox("Filtration cycle & BW feasibility",
                                 value=True, key="rs_cycle")
    with sel_c2:
        st.markdown("**C · Mechanical & Structural**")
        s_vessel   = st.checkbox("Vessel dimensions & ASME thickness",
                                  value=True, key="rs_vessel")
        s_nzpl     = st.checkbox("Nozzle plate design",    value=True, key="rs_nzpl")
        s_wt_empty = st.checkbox("Empty weight breakdown", value=True, key="rs_wtempty")
        s_wt_oper  = st.checkbox("Operating weight & support loads",
                                  value=True, key="rs_wtoper")
        s_saddle   = st.checkbox("Saddle design",          value=True, key="rs_saddle")
    with sel_c3:
        st.markdown("**D · Backwash System**")
        s_bw_hyd   = st.checkbox("BW hydraulics & collector",
                                  value=True, key="rs_bwhyd")
        s_bw_equip = st.checkbox("BW equipment sizing\n(pump / blower / tank)",
                                  value=True, key="rs_bweq")
        st.markdown("**E · Internal Protection**")
        _lining_label = (f"Lining / coating  ({lining_result['protection_type']})"
                         if _has_lining else "Lining / coating  *(None — skipped)*")
        s_lining = st.checkbox(_lining_label, value=_has_lining,
                               disabled=not _has_lining, key="rs_lining")
    with sel_c4:
        st.markdown("**F · Energy & Economics**")
        s_hyd_prof = st.checkbox("Hydraulic head profile", value=True, key="rs_hyd")
        s_energy   = st.checkbox("Energy & OPEX",          value=True, key="rs_energy")
        st.markdown("**G · Post-treatment**")
        s_cart     = st.checkbox("Cartridge filter",       value=True, key="rs_cart")

    st.divider()

    def _build_docx() -> bytes:
        import io as _io
        doc = _DocxDocument()

        def _tbl(rows_data, cols=("Parameter", "Value")):
            tbl = doc.add_table(rows=len(rows_data), cols=len(cols))
            tbl.style = "Table Grid"
            for i, row_vals in enumerate(rows_data):
                for j, v in enumerate(row_vals):
                    tbl.rows[i].cells[j].text = str(v)
            doc.add_paragraph("")
            return tbl

        def _h(text, lvl=2):
            doc.add_heading(text, lvl)

        t = doc.add_heading("AQUASIGHT™  Horizontal Multi-Media Filter", 0)
        t.alignment = _WD_ALIGN.CENTER
        t2 = doc.add_heading("Calculation Report", 1)
        t2.alignment = _WD_ALIGN.CENTER
        doc.add_paragraph("")
        _h("Project Information")
        _tbl([
            ("Project",       project_name),
            ("Document No.",  f"{doc_number}  ·  Rev {revision}"),
            ("Client",        client or "—"),
            ("Prepared by",   engineer),
            ("Date",          str(__import__("datetime").date.today())),
        ])

        _sn = [1]
        def _sec(title):
            _sn[0] += 1
            _h(f"{_sn[0]}. {title}")

        if s_process:
            _sec("Process Basis")
            _tbl([
                ("Total plant flow",     f"{total_flow:,.0f} m³/h"),
                ("Streams",              str(streams)),
                ("Filters / stream",     str(n_filters)),
                ("Redundancy",           f"N-{redundancy} per stream"),
                ("Flow / filter (N)",    f"{q_per_filter:.1f} m³/h"),
                ("Filtration rate (N)",  f"{q_per_filter/avg_area:.2f} m/h"),
                ("Cross-sectional area", f"{avg_area:.3f} m²"),
            ])

        if s_water:
            _sec("Water Properties")
            _tbl([
                ("",            "Feed",                    "Backwash"),
                ("Salinity",    f"{feed_sal:.2f} ppt",    f"{bw_sal:.2f} ppt"),
                ("Temperature", f"{feed_temp:.1f} °C",    f"{bw_temp:.1f} °C"),
                ("Density",     f"{rho_feed:.3f} kg/m³",  f"{rho_bw:.3f} kg/m³"),
                ("Viscosity",   f"{mu_feed*1000:.4f} cP", f"{mu_bw*1000:.4f} cP"),
            ], cols=("Property", "Feed", "Backwash"))

        if s_media:
            _sec("Media Configuration")
            _m_hdr = ("Media", "Support", "Depth (m)", "d10 (mm)", "CU",
                       "ε₀", "ρp,eff (kg/m³)", "ψ", "Vol (m³)")
            _m_rows = [_m_hdr] + [
                (b["Type"],
                 "✓" if b.get("is_support") else "",
                 f"{b['Depth']:.3f}", f"{b['d10']:.2f}", f"{b['cu']:.2f}",
                 f"{b.get('epsilon0', 0):.3f}", f"{b['rho_p_eff']:.0f}",
                 f"{b.get('psi', '—')}", f"{b['Vol']:.4f}",
                ) for b in base]
            _tbl(_m_rows, cols=_m_hdr)

        if s_dp:
            _sec("Filtration Pressure Drop")
            _tbl([
                ("Clean-bed ΔP (Ergun)",  f"{bw_dp['dp_clean_bar']:.4f} bar"),
                ("50 % loaded ΔP",
                 f"{(bw_dp['dp_clean_bar']+bw_dp['dp_dirty_bar'])/2:.4f} bar"),
                ("Dirty ΔP (M_max)",      f"{bw_dp['dp_dirty_bar']:.4f} bar"),
                ("BW trigger setpoint",   f"{dp_trigger_bar:.2f} bar"),
                ("Superficial LV (N)",    f"{bw_dp['u_m_h']:.2f} m/h"),
                ("Specific resistance α",
                 f"{filt_cycles['N']['alpha_used_m_kg']/1e9:.1f} × 10⁹ m/kg  "
                 f"({filt_cycles['N']['alpha_source']})"),
            ])

        if s_cycle:
            _sec("Filtration Cycle & BW Feasibility")
            _tbl([
                ("Max solid loading", f"{solid_loading:.2f} kg/m²"),
                ("BW total duration", f"{bw_total_min} min"),
                ("BW sequence",
                 f"Drain {bw_s_drain}' · Air {bw_s_air}' · Air+W {bw_s_airw}' · "
                 f"HW {bw_s_hw}' · Settle {bw_s_settle}' · Fill {bw_s_fill}'"),
            ])

        if s_vessel:
            _sec("Vessel Dimensions & ASME Thickness")
            _tbl([
                ("Nominal ID",               f"{nominal_id:.3f} m"),
                ("Real hydraulic ID",        f"{real_id:.4f} m"),
                ("Outside diameter",         f"{mech['od_m']:.4f} m"),
                ("Total length T/T",         f"{total_length:.3f} m"),
                ("Cylindrical shell length", f"{cyl_len:.3f} m"),
                ("End geometry",             end_geometry),
                ("Material",                 material_name),
                ("Design pressure",          f"{design_pressure:.2f} bar g"),
                ("Corrosion allowance",      f"{corrosion:.1f} mm"),
                ("Shell t_required",         f"{mech['t_shell_min_mm']:.2f} mm"),
                ("Shell t_design",           f"{mech['t_shell_design_mm']} mm"),
                ("Head t_required",          f"{mech['t_head_min_mm']:.2f} mm"),
                ("Head t_design",            f"{mech['t_head_design_mm']} mm"),
                ("Shell radiography",        f"{shell_radio}  (E={mech['shell_E']:.2f})"),
                ("Head radiography",         f"{head_radio}  (E={mech['head_E']:.2f})"),
            ])

        if s_nzpl:
            _sec("Nozzle Plate Design")
            _tbl([
                ("Plate height",
                 f"{nozzle_plate_h:.3f} m"),
                ("Plate t_min / t_design",
                 f"{wt_np['t_min_mm']:.2f} / {wt_np['t_design_mm']} mm"),
                ("Nozzle density",         f"{np_density:.0f} /m²"),
                ("Nozzle bore",            f"{np_bore_dia:.1f} mm"),
                ("Total nozzles",          f"{wt_np['n_bores']}"),
                ("Plate area",             f"{wt_np['area_total_m2']:.4f} m²"),
                ("Open area ratio",        f"{wt_np['open_ratio_pct']:.2f} %"),
                ("Design ΔP (nozzle)",     f"{wt_np['q_dp_kpa']:.2f} kPa"),
                ("Beam section",
                 f"{wt_np['beam_section']}  ({wt_np['n_beams']} beams)"),
                ("Plate + beam weight",    f"{wt_np['weight_total_kg']:,.1f} kg"),
            ])

        if s_wt_empty:
            _sec("Empty Weight Breakdown")
            _tbl([
                ("Cylindrical shell",     f"{wt_body['weight_shell_kg']:,.1f} kg"),
                ("2 × Dish ends",         f"{wt_body['weight_two_heads_kg']:,.1f} kg"),
                ("Nozzles",               f"{w_noz:,.1f} kg"),
                ("Nozzle plate assembly", f"{wt_np['weight_total_kg']:,.1f} kg"),
                (f"Supports ({wt_sup['support_type']})",
                 f"{wt_sup['weight_all_supports_kg']:,.1f} kg"),
                ("Strainer nozzles",      f"{wt_int['weight_strainers_kg']:,.1f} kg"),
                ("Air scour header",      f"{wt_int['weight_air_header_kg']:,.1f} kg"),
                ("Manholes",              f"{wt_int['weight_manholes_kg']:,.1f} kg"),
                ("TOTAL EMPTY WEIGHT",
                 f"{w_total_rep:,.1f} kg  =  {w_total_rep/1000:.3f} t"),
            ])

        if s_wt_oper:
            _sec("Operating Weight & Support Loads")
            _tbl([
                ("Empty vessel",
                 f"{wt_oper['w_empty_kg']:,.1f} kg"),
                (f"Internal {lining_result['protection_type'].lower() or 'lining'}",
                 f"{wt_oper['w_lining_kg']:,.1f} kg"),
                ("Media — dry solid",    f"{wt_oper['w_media_kg']:,.1f} kg"),
                ("Process water (full)", f"{wt_oper['w_water_kg']:,.1f} kg"),
                ("OPERATING WEIGHT",
                 f"{wt_oper['w_operating_kg']:,.1f} kg  =  {wt_oper['w_operating_t']:.3f} t"),
                ("Number of supports",   str(wt_oper["n_supports"])),
                ("Load per support",
                 f"{wt_oper['load_per_support_kg']:,.1f} kg  "
                 f"= {wt_oper['load_per_support_t']:.3f} t  "
                 f"= {wt_oper['load_per_support_kN']:.1f} kN"),
            ])

        if s_saddle:
            _sec("Saddle Design (Zick Method)")
            _sd = wt_saddle
            _tbl([
                ("Saddle spacing factor α",
                 f"{_sd['alpha']:.2f}"),
                ("Saddle 1 position",
                 f"{_sd['saddle_1_from_left_m']:.3f} m from left T/L"),
                ("Saddle 2 position",
                 f"{_sd['saddle_2_from_left_m']:.3f} m from left T/L"),
                ("Reaction per saddle",       f"{_sd['reaction_t']:.3f} t"),
                ("Section selected",          str(_sd.get("section", "—"))),
                ("Section capacity",          f"{_sd.get('capacity_t', '—')} t"),
                ("Structural weight / saddle",
                 f"{_sd.get('w_one_saddle_kg', 0):,.0f} kg"),
                ("Status",
                 "OVERSTRESSED" if _sd.get("overstressed") else "OK"),
            ])

        if s_bw_hyd:
            _sec("Backwash Hydraulics & Collector Check")
            _tbl([
                ("BW velocity (proposed)",  f"{bw_velocity:.1f} m/h"),
                ("Max safe BW velocity",    f"{bw_col['max_safe_bw_m_h']:.1f} m/h"),
                ("Air scour rate",          f"{air_scour_rate:.1f} m/h"),
                ("Actual freeboard",
                 f"{bw_col['freeboard_m']:.3f} m  ({bw_col['freeboard_pct']:.1f}%)"),
                ("Collector status",        bw_col["status"]),
            ])

        if s_bw_equip:
            _sec("BW Equipment Sizing")
            _bws = bw_sizing
            _tbl([
                ("BW design flow",       f"{_bws['q_bw_design_m3h']:,.1f} m³/h"),
                ("BW pump head",         f"{_bws['bw_head_mwc']:.2f} mWC"),
                ("BW pump shaft power",  f"{_bws['p_pump_shaft_kw']:.1f} kW"),
                ("BW pump motor power",  f"{_bws['p_pump_motor_kw']:.1f} kW"),
                ("Air flow (design)",    f"{_bws['q_air_design_m3h']:,.1f} Am³/h"),
                ("Blower back-pressure", f"{_bws['P2_pa']/1e5:.3f} bar abs"),
                ("Blower shaft power",   f"{_bws['p_blower_shaft_kw']:.1f} kW"),
                ("Blower motor power",   f"{_bws['p_blower_motor_kw']:.1f} kW"),
                ("BW water tank volume", f"{_bws['v_tank_m3']:.1f} m³"),
            ])

        if s_lining and _has_lining:
            _sec(f"Internal Protection — {lining_result['protection_type']}")
            _tbl([
                ("Protection type",
                 lining_result["protection_type"]),
                ("Total area protected",
                 f"{lining_result['a_total_m2']:.2f} m²"),
                ("Lining / coating weight",
                 f"{lining_result['weight_kg']:,.1f} kg"),
                ("Material cost",
                 f"USD {lining_result['material_cost_usd']:,.0f}"),
                ("Application labour",
                 f"USD {lining_result['labor_cost_usd']:,.0f}"),
                ("TOTAL COATING COST",
                 f"USD {lining_result['total_cost_usd']:,.0f}"),
            ] + [(k, v) for k, v in lining_result["detail"].items()
                 if k not in {"Material cost", "Labour cost", "Total cost"}])

        if s_hyd_prof:
            _sec("Hydraulic Head Profile")
            _hp_rows = [("Item", "Clean bed", "Dirty bed")]
            for k in hyd_prof["clean"]["items_bar"]:
                _hp_rows.append((
                    k,
                    f"{hyd_prof['clean']['items_bar'][k]:.4f} bar"
                    f" / {hyd_prof['clean']['items_mwc'][k]:.2f} mWC",
                    f"{hyd_prof['dirty']['items_bar'][k]:.4f} bar"
                    f" / {hyd_prof['dirty']['items_mwc'][k]:.2f} mWC",
                ))
            _hp_rows.append((
                "TOTAL PUMP DUTY",
                f"{hyd_prof['clean']['total_bar']:.4f} bar"
                f" / {hyd_prof['clean']['total_mwc']:.2f} mWC",
                f"{hyd_prof['dirty']['total_bar']:.4f} bar"
                f" / {hyd_prof['dirty']['total_mwc']:.2f} mWC",
            ))
            _tbl(_hp_rows, cols=("Item", "Clean bed", "Dirty bed"))

        if s_energy:
            _sec("Energy Consumption & OPEX")
            _tbl([
                ("Filtration pump power (dirty, per filter)",
                 f"{energy['p_filt_dirty_kw']:.1f} kW"),
                ("BW pump power",            f"{energy['p_bw_kw']:.1f} kW"),
                ("Air blower power (elec.)", f"{energy['p_blower_elec_kw']:.1f} kW"),
                ("Annual total energy",
                 f"{energy['e_total_kwh_yr']/1e3:,.0f} MWh/yr"),
                ("Specific energy",          f"{energy['kwh_per_m3']:.4f} kWh/m³"),
                ("Annual energy OPEX",       f"USD {energy['cost_usd_yr']:,.0f}/yr"),
            ])

        if s_cart:
            _sec("Cartridge Filter")
            _tbl([
                ("Design flow",       f"{cart_result['design_flow_m3h']:,.1f} m³/h"),
                ("Element material",  cart_result["element_material"]),
                ("Element size",      cart_result["element_size"]),
                ("Rating",            f"{cart_result['rating_um']} µm absolute"),
                ("Elements required", str(cart_result["n_elements"])),
                ("Housings required", str(cart_result["n_housings"])),
                ("ΔP BOL / EOL",
                 f"{cart_result['dp_clean_bar']:.4f} / {cart_result['dp_eol_bar']:.4f} bar"),
                ("Annual element cost",
                 f"USD {cart_result['annual_cost_usd']:,.0f}"),
            ])

        doc.add_page_break()
        _h("Sign-off & Revision Record")
        _tbl([
            ("Prepared by",  engineer),
            ("Role",         "Process Expert — AQUASIGHT™"),
            ("Document No.", f"{doc_number}  ·  Rev {revision}"),
            ("Project",      project_name),
            ("Client",       client or "—"),
            ("Date",         str(__import__("datetime").date.today())),
            ("Software",     "AQUASIGHT™ MMF Calculator"),
            ("Checked by",   ""),
            ("Approved by",  ""),
        ])
        doc.add_paragraph(
            "\nThis document was generated automatically. "
            "All calculations are the responsibility of the engineer of record."
        )

        buf = _io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.getvalue()

    _n_sections = sum([
        s_process, s_water, s_media, s_dp, s_cycle,
        s_vessel, s_nzpl, s_wt_empty, s_wt_oper, s_saddle,
        s_bw_hyd, s_bw_equip, s_lining and _has_lining,
        s_hyd_prof, s_energy, s_cart,
    ])
    st.caption(
        f"{_n_sections} section(s) selected + Identification & Sign-off (always included)")

    dl_col, _ = st.columns([2, 3])
    with dl_col:
        if _DOCX_OK:
            st.download_button(
                label="⬇️  Download Word report (.docx)",
                data=_build_docx(),
                file_name=f"{doc_number}_Rev{revision}.docx",
                mime=("application/vnd.openxmlformats-officedocument"
                      ".wordprocessingml.document"),
            )
        else:
            st.warning("Install python-docx:  `pip install python-docx`")

    st.divider()
    st.markdown(f"**{project_name}** · {doc_number} · Rev {revision} · {engineer}")
    st.markdown("")

    if s_process:
        st.markdown("### B1 · Process Basis")
        st.markdown(f"""
| Parameter | Value |
|---|---|
| Total plant flow | {total_flow:,.0f} m³/h |
| Streams × filters / stream | {streams} × {n_filters} |
| Redundancy | N-{redundancy} per stream |
| Flow / filter (N) | {q_per_filter:.1f} m³/h |
| Filtration rate (N) | {q_per_filter/avg_area:.2f} m/h |
| Cross-sectional area | {avg_area:.3f} m² |
""")

    if s_water:
        st.markdown("### B2 · Water Properties")
        st.markdown(f"""
| Property | Feed | Backwash |
|---|---|---|
| Salinity | {feed_sal:.2f} ppt | {bw_sal:.2f} ppt |
| Temperature | {feed_temp:.1f} °C | {bw_temp:.1f} °C |
| Density | {rho_feed:.3f} kg/m³ | {rho_bw:.3f} kg/m³ |
| Viscosity | {mu_feed*1000:.4f} cP | {mu_bw*1000:.4f} cP |
""")

    if s_media:
        st.markdown("### B3 · Media Configuration")
        _med_hdr = "| Media | Sup. | Depth (m) | d10 (mm) | CU | ε₀ | ρp,eff | ψ |"
        _med_sep = "|---|---|---|---|---|---|---|---|"
        _med_rows = "\n".join(
            f"| {b['Type']} | {'✓' if b.get('is_support') else ''} "
            f"| {b['Depth']:.3f} | {b['d10']:.2f} | {b['cu']:.2f} "
            f"| {b.get('epsilon0', 0):.3f} | {b['rho_p_eff']:.0f} "
            f"| {b.get('psi', '—')} |"
            for b in base
        )
        st.markdown(f"{_med_hdr}\n{_med_sep}\n{_med_rows}")

    if s_dp:
        st.markdown("### B4 · Filtration ΔP")
        st.markdown(f"""
| | Value |
|---|---|
| Clean-bed ΔP (Ergun) | {bw_dp['dp_clean_bar']:.4f} bar |
| 50 % loaded ΔP | {(bw_dp['dp_clean_bar']+bw_dp['dp_dirty_bar'])/2:.4f} bar |
| Dirty ΔP (M_max) | {bw_dp['dp_dirty_bar']:.4f} bar |
| BW trigger setpoint | {dp_trigger_bar:.2f} bar |
| Superficial LV (N) | {bw_dp['u_m_h']:.2f} m/h |
""")

    if s_vessel:
        st.markdown("### C1 · Vessel Dimensions & ASME Thickness")
        st.markdown(f"""
| Parameter | Value |
|---|---|
| Nominal ID / Real hyd. ID | {nominal_id:.3f} m / {real_id:.4f} m |
| Outside diameter | {mech['od_m']:.4f} m |
| Total length T/T | {total_length:.3f} m |
| End geometry | {end_geometry} |
| Material | {material_name} |
| Design pressure | {design_pressure:.2f} bar g |
| Shell t_req / t_design | {mech['t_shell_min_mm']:.2f} / {mech['t_shell_design_mm']} mm |
| Head t_req / t_design | {mech['t_head_min_mm']:.2f} / {mech['t_head_design_mm']} mm |
""")

    if s_wt_empty:
        st.markdown("### C3 · Empty Weight")
        st.markdown(f"""
| Component | Weight |
|---|---|
| Shell + 2 heads | {wt_body['weight_body_kg']:,.0f} kg |
| Nozzles | {w_noz:,.0f} kg |
| Nozzle plate assembly | {wt_np['weight_total_kg']:,.0f} kg |
| Supports | {wt_sup['weight_all_supports_kg']:,.0f} kg |
| Internals | {wt_int['weight_internals_kg']:,.0f} kg |
| **TOTAL EMPTY** | **{w_total_rep:,.0f} kg = {w_total_rep/1000:.3f} t** |
""")

    if s_wt_oper:
        st.markdown("### C4 · Operating Weight & Support Loads")
        st.markdown(f"""
| Component | Weight |
|---|---|
| Empty vessel | {wt_oper['w_empty_kg']:,.0f} kg |
| Lining / coating | {wt_oper['w_lining_kg']:,.0f} kg |
| Media (dry) | {wt_oper['w_media_kg']:,.0f} kg |
| Process water | {wt_oper['w_water_kg']:,.0f} kg |
| **OPERATING WEIGHT** | **{wt_oper['w_operating_kg']:,.0f} kg = {wt_oper['w_operating_t']:.3f} t** |
| Load / support ({wt_oper['n_supports']} supports) | {wt_oper['load_per_support_t']:.3f} t = {wt_oper['load_per_support_kN']:.1f} kN |
""")

    if s_saddle:
        _sd2 = wt_saddle
        st.markdown("### C5 · Saddle Design")
        st.markdown(f"""
| Parameter | Value |
|---|---|
| Spacing factor α | {_sd2['alpha']:.2f} |
| Saddle 1 / Saddle 2 position | {_sd2['saddle_1_from_left_m']:.3f} m / {_sd2['saddle_2_from_left_m']:.3f} m from left T/L |
| Reaction per saddle | {_sd2['reaction_t']:.3f} t |
| Section selected | {_sd2.get('section', '—')} — capacity {_sd2.get('capacity_t', '—')} t |
| Status | {"OVERSTRESSED" if _sd2.get('overstressed') else "OK"} |
""")

    if s_bw_hyd:
        st.markdown("### D1 · Backwash Hydraulics & Collector")
        st.markdown(f"""
| Parameter | Value |
|---|---|
| BW velocity (proposed / max safe) | {bw_velocity:.1f} / {bw_col['max_safe_bw_m_h']:.1f} m/h |
| Freeboard (min. req. / actual) | {freeboard_mm:.0f} mm / {bw_col['freeboard_m']*1000:.0f} mm |
| Collector status | {bw_col['status']} |
""")

    if s_bw_equip:
        _bws2 = bw_sizing
        st.markdown("### D2 · BW Equipment Sizing")
        st.markdown(f"""
| Equipment | Key Parameter |
|---|---|
| BW pump flow | {_bws2['q_bw_design_m3h']:,.1f} m³/h |
| BW pump head | {_bws2['bw_head_mwc']:.2f} mWC |
| BW pump motor | {_bws2['p_pump_motor_kw']:.1f} kW |
| Air blower flow | {_bws2['q_air_design_m3h']:,.1f} Am³/h |
| Blower back-pressure | {_bws2['P2_pa']/1e5:.3f} bar abs |
| Blower motor | {_bws2['p_blower_motor_kw']:.1f} kW |
| BW water tank | {_bws2['v_tank_m3']:.1f} m³ |
""")

    if s_lining and _has_lining:
        st.markdown(f"### E · Internal Protection — {lining_result['protection_type']}")
        st.markdown(f"""
| Parameter | Value |
|---|---|
| Total area | {lining_result['a_total_m2']:.2f} m² |
| Weight | {lining_result['weight_kg']:,.0f} kg |
| Material cost | USD {lining_result['material_cost_usd']:,.0f} |
| Labour cost | USD {lining_result['labor_cost_usd']:,.0f} |
| **Total coating cost** | **USD {lining_result['total_cost_usd']:,.0f}** |
""")

    if s_hyd_prof:
        st.markdown("### F1 · Hydraulic Head Profile")
        _hd_hdr = "| Item | Clean bed | Dirty bed |"
        _hd_sep = "|---|---|---|"
        _hd_rows = "\n".join(
            f"| {k} | {hyd_prof['clean']['items_bar'][k]:.4f} bar / "
            f"{hyd_prof['clean']['items_mwc'][k]:.2f} mWC | "
            f"{hyd_prof['dirty']['items_bar'][k]:.4f} bar / "
            f"{hyd_prof['dirty']['items_mwc'][k]:.2f} mWC |"
            for k in hyd_prof["clean"]["items_bar"]
        )
        _hd_tot = (
            f"| **Total** | **{hyd_prof['clean']['total_bar']:.4f} bar / "
            f"{hyd_prof['clean']['total_mwc']:.2f} mWC** | "
            f"**{hyd_prof['dirty']['total_bar']:.4f} bar / "
            f"{hyd_prof['dirty']['total_mwc']:.2f} mWC** |"
        )
        st.markdown(f"{_hd_hdr}\n{_hd_sep}\n{_hd_rows}\n{_hd_tot}")

    if s_energy:
        st.markdown("### F2 · Energy & OPEX")
        st.markdown(f"""
| KPI | Value |
|---|---|
| Filtration pump power (dirty, per filter) | {energy['p_filt_dirty_kw']:.1f} kW |
| BW pump power | {energy['p_bw_kw']:.1f} kW |
| Air blower power (elec.) | {energy['p_blower_elec_kw']:.1f} kW |
| Annual total energy | {energy['e_total_kwh_yr']/1e3:,.0f} MWh/yr |
| Specific energy | {energy['kwh_per_m3']:.4f} kWh/m³ |
| Annual energy OPEX | USD {energy['cost_usd_yr']:,.0f}/yr |
""")

    if s_cart:
        st.markdown("### G · Cartridge Filter")
        st.markdown(f"""
| Parameter | Value |
|---|---|
| Design flow | {cart_result['design_flow_m3h']:,.1f} m³/h |
| Element | {cart_result['element_size']} · {cart_result['rating_um']} µm · {cart_result['element_material']} |
| Elements / Housings | {cart_result['n_elements']} / {cart_result['n_housings']} |
| Flow / element | {cart_result['actual_flow_m3h_element']:.3f} m³/h ({cart_result['q_lpm_element']:.1f} lpm) |
| ΔP BOL / EOL | {cart_result['dp_clean_bar']:.4f} / {cart_result['dp_eol_bar']:.4f} bar |
| Annual element cost | USD {cart_result['annual_cost_usd']:,.0f} |
""")

    st.divider()
    col_sign, _ = st.columns([1, 2])
    with col_sign:
        st.info(f"**{engineer}**  \nProcess Expert — AQUASIGHT™  \n\n"
                f"{doc_number} · Rev {revision}")
