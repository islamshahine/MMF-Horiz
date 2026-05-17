"""Underdrain / nozzle plate (1D screening) — Backwash tab panel."""
import pandas as pd
import streamlit as st
from ui.helpers import (
    fmt,
    ulbl,
    localize_engine_message,
    collector_hyd_profile_display_df,
    orifice_network_display_df,
    nozzle_plate_hole_display_df,
    staged_orifice_bands_display_df,
    staged_orifice_hole_display_df,
    fmt_si_range,
)
from ui.collector_hyd_schematic import (
    build_collector_elevation_figure,
    build_collector_underdrain_figure,
    build_nozzle_plate_plan_figure,
)
from ui.spatial_loading_panel import render_spatial_loading_panel


def render_collector_design_panel(computed: dict, inputs: dict) -> None:
    """Vessel intelligence, nozzle-plate BW hydraulics, legacy lateral surrogate, studies."""
    _np = computed.get("collector_nozzle_plate") or {}
    _uda = computed.get("underdrain_system_advisory") or {}
    if _np.get("active"):
        with st.expander("Nozzle plate — BW hydraulics (primary)", expanded=True):
            if _uda:
                from engine.strainer_materials import strainer_material_label

                st.caption(
                    f"**Media inputs:** {_uda.get('catalogue_label', '—')} · "
                    f"ρ **{float(_uda.get('np_density_per_m2', 0)):.0f} /m²** · "
                    f"bore **{float(inputs.get('np_bore_dia', 0)):.0f} mm** · "
                    f"strainer **{strainer_material_label(inputs.get('strainer_mat', ''))}**"
                )
            st.caption(localize_engine_message(str(_np.get("screening_note", ""))))
            _basis = localize_engine_message(str(_np.get("design_basis", "")))
            if _basis:
                st.info(
                    f"**Design basis:** {_basis} — from sidebar **🧱 Media** "
                    f"(height, bore, density /m², **rows across chord**) and **🔄 Backwash** "
                    f"(BW hydraulics)."
                )
            st.caption(_np.get("method", ""))
            d1, d2, d3, d4 = st.columns(4)
            d1.metric(
                "Plate area",
                fmt(float(_np.get("nozzle_plate_area_m2", 0)), "area_m2", 2),
            )
            _ch = _np.get("chord_m")
            d2.metric(
                "Plate chord",
                fmt(float(_ch), "length_m", 2) if _ch else "—",
            )
            d3.metric("Density (input)", f"{float(_np.get('np_density_per_m2', 0)):.0f} /m²")
            _act_d = float(_np.get("actual_density_per_m2", 0) or 0)
            d4.metric(
                "Density (as-built)",
                f"{_act_d:.1f} /m²" if _act_d > 0 else "—",
            )
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("BW flow", fmt(_np.get("q_bw_m3h", 0), "flow_m3h", 1))
            p2.metric("Plate holes (total)", str(int(_np.get("n_holes_total", 0))))
            for _ladv in _np.get("layout_advisories") or []:
                st.warning(str(_ladv))
            p3.metric(
                f"Open area ({'%'})",
                f"{float(_np.get('open_area_fraction_pct', 0)):.1f}",
            )
            p4.metric(
                "Distribution factor (1D)",
                f"{float(_np.get('distribution_factor_calc', 1)):.3f}",
            )
            p5, p6, p7, p8 = st.columns(4)
            _holes_early = list(_np.get("hole_network") or [])
            _n_rows_ch = int(_np.get("n_rows_across_chord", 0) or 0)
            if _n_rows_ch < 1 and _holes_early:
                _n_rows_ch = len({
                    int(h.get("row_index", h.get("lateral_index", 0)) or 0)
                    for h in _holes_early
                })
            p5.metric("Rows (across chord)", str(_n_rows_ch))
            _n_rows_in = int(inputs.get("n_nozzle_rows", 0) or 0)
            if _n_rows_in > 0:
                p5.caption(f"Override: {_n_rows_in} (Media)")
            if _n_rows_ch <= 1 and int(_np.get("n_holes_total", 0) or 0) > 50:
                st.error(
                    "Layout has only **1 row** across chord — expected a brick grid. "
                    "Set **🧱 Media → Nozzle rows across chord** (e.g. **7**), or **0** for auto, "
                    "then **Clear cache** (⋮ menu) and **Rerun**."
                )
            p6.metric(
                "P_long (along drum)",
                f"{float(_np.get('pitch_long_mm', 0) or 0):.0f} mm",
            )
            p7.metric(
                "Nozzles / row",
                str(int(_np.get("n_per_row_along_drum") or _np.get("holes_per_row", 0) or 0)),
            )
            _rsp = float(_np.get("row_spacing_m", 0) or 0)
            p8.metric(
                "Row spacing (Δstation)",
                fmt(_rsp, "length_m", 2) if _rsp > 0 else "—",
            )
            p9, p10, p11, p12 = st.columns(4)
            p9.metric(
                f"V hole mean ({ulbl('velocity_m_s')})",
                fmt(_np.get("orifice_velocity_uniform_m_s", 0), "velocity_m_s", 2),
            )
            p10.metric(
                f"V hole max ({ulbl('velocity_m_s')})",
                fmt(_np.get("orifice_velocity_max_m_s", 0), "velocity_m_s", 2),
            )
            p11.metric("Flow imbalance", f"{float(_np.get('flow_imbalance_pct', 0)):.1f}%")
            p12.metric(
                "Hole Ø",
                fmt(float(_np.get("hole_d_mm", 0)), "length_mm", 0),
            )
            for _adv in _np.get("advisories") or []:
                _sev = str(_adv.get("severity", "advisory"))
                _msg = localize_engine_message(
                    f"**{_adv.get('topic', '')}:** {_adv.get('detail', '')}"
                )
                if _sev == "warning":
                    st.warning(_msg)
                else:
                    st.info(_msg)
            render_spatial_loading_panel(
                computed.get("spatial_distribution") or {},
                _np,
                chart_key="spatial_loading_heatmap_bw",
                phase_label="backwash",
                expanded=False,
            )
            _holes = list(_np.get("hole_network") or [])
            _layout_rev = int(_np.get("layout_revision", 0) or 0)
            if _holes and _layout_rev < 6:
                st.warning(
                    "Nozzle plate layout is from an **older cached run**. "
                    "Click **Apply** or change **hole density** slightly, or use **Clear cache** "
                    "→ **Rerun** to refresh the full-plate stagger layout."
                )
            if _holes:
                _n_rows = int(_np.get("n_rows_along_drum", 0) or 0)
                with st.expander("Hole / row detail (sample)", expanded=False):
                    _pch = float(_np.get("pitch_chord_mm", 0) or 0)
                    _edg = float(_np.get("edge_clearance_mm", 0) or 0)
                    st.caption(
                        f"**Brick layout:** **{int(_np.get('n_rows_across_chord', 0))}** rows across "
                        f"chord (P_trans **{_pch:.0f} mm**), **"
                        f"{int(_np.get('n_per_row_along_drum', 0))}** nozzles/row along drum "
                        f"(P_long **{float(_np.get('pitch_long_mm', 0) or _pch):.0f} mm**; "
                        f"odd rows +½P_long). Field "
                        f"{fmt(float(_np.get('field_x_start_m', 0)), 'length_m', 2)}–"
                        f"{fmt(float(_np.get('field_x_end_m', 0)), 'length_m', 2)} × chord. "
                        f"**{int(_np.get('n_holes_total', 0))}** holes — plan = layout only."
                    )
                    st.dataframe(
                        nozzle_plate_hole_display_df(_holes[:120]),
                        use_container_width=True,
                        hide_index=True,
                    )
                    if len(_holes) > 120:
                        st.caption(f"Showing 120 of {len(_holes)} holes.")
                    # Longitudinal = straight vessel length; transverse = plate chord
                    _cyl = float(
                        _np.get("cyl_len_m")
                        or inputs.get("total_length")
                        or computed.get("total_length")
                        or 0
                    )
                    _chord = float(_np.get("chord_m") or 0.0)
                    if _chord <= 0:
                        _chord = float((computed.get("wt_np") or {}).get("chord_m", 0) or 0)
                    _fig_np = build_nozzle_plate_plan_figure(
                        cyl_len_m=_cyl,
                        chord_m=_chord,
                        hole_network=_holes,
                        n_rows_across=int(_np.get("n_rows_across_chord", 0) or 0),
                        n_per_row=int(_np.get("n_per_row_along_drum", 0) or 0),
                        n_holes_placed=int(_np.get("n_holes_total", 0) or len(_holes)),
                        pitch_long_mm=float(_np.get("pitch_long_mm", 100) or 100),
                        pitch_trans_mm=float(_np.get("pitch_trans_mm", 100) or 100),
                        edge_margin_mm=float(_np.get("edge_clearance_mm", 50) or 50),
                        field_x_start_m=float(_np.get("field_x_start_m", 0) or 0),
                        field_x_end_m=float(_np.get("field_x_end_m", 0) or 0),
                        field_y_plot_start_m=float(
                            _np.get("field_y_plot_start_m", 0) or 0
                        ),
                        field_y_plot_end_m=float(
                            _np.get("field_y_plot_end_m", 0) or 0
                        ),
                        head_inset_m=float(_np.get("head_inset_m", 0) or 0),
                        bore_d_mm=float(_np.get("hole_d_mm", 50) or 50),
                        open_area_pct=float(_np.get("open_area_fraction_pct", 0) or 0),
                        v_max=float(_np.get("orifice_velocity_max_m_s", 0) or 0),
                        plate_outline_x_m=_np.get("plate_outline_x_m"),
                        plate_outline_y_top_m=_np.get("plate_outline_y_top_m"),
                        plate_outline_y_bot_m=_np.get("plate_outline_y_bot_m"),
                        x_cyl_start_m=float(_np.get("x_cyl_start_m", 0) or 0),
                        x_cyl_end_m=float(_np.get("x_cyl_end_m", 0) or 0),
                    )
                    if _fig_np is not None:
                        st.plotly_chart(
                            _fig_np,
                            use_container_width=True,
                            key="nozzle_plate_bw_plan",
                        )
                    else:
                        st.caption(
                            "Install **plotly** for the nozzle-plate plan illustration."
                        )

    _ci = computed.get("collector_intel") or {}
    if _ci:
        from engine.collector_intelligence import summarize_nozzle_schedule_velocities
        with st.expander("Collector intelligence — distribution & freeboard screening", expanded=False):
            st.caption(
                "Quick checks on **bed freeboard** and **BW velocity**, plus **vessel-wall nozzle** "
                "velocities from §4 (not the internal collector header/laterals). "
                "For distributor geometry and lateral hydraulics, use **Collector hydraulics** below. "
                "**Internal** header/lateral/orifice jets — **Velocity & erosion screening** expander "
                "inside Collector hydraulics."
            )
            st.metric("Collector performance score", f"{_ci.get('score', 0)}/100 — {_ci.get('grade', '—')}")
            _peaks = summarize_nozzle_schedule_velocities(computed.get("nozzle_sched") or [])
            _lim_w = float(_ci.get("nozzle_velocity_limit_water_m_s", 3.5) or 3.5)
            _lim_a = float(_ci.get("nozzle_velocity_limit_air_m_s", 28.0) or 28.0)
            _v_in = float(
                _peaks.get("backwash_inlet_velocity_m_s")
                or _ci.get("backwash_inlet_velocity_m_s", 0) or 0
            )
            _v_out = float(
                _peaks.get("backwash_outlet_velocity_m_s")
                or _ci.get("backwash_outlet_velocity_m_s", 0) or 0
            )
            _v_air = float(
                _peaks.get("air_scour_nozzle_velocity_m_s")
                or _ci.get("air_scour_nozzle_velocity_m_s", 0) or 0
            )
            st.markdown("**Vessel nozzles (§4 schedule)** — not internal collector pipework")
            nv1, nv2, nv3 = st.columns(3)
            nv1.metric(
                f"BW inlet nozzle ({ulbl('velocity_m_s')})",
                fmt(_v_in, "velocity_m_s", 2) if _v_in > 0 else "—",
                delta=f"water erosion screen {fmt(_lim_w, 'velocity_m_s', 1)}",
                delta_color="inverse" if _v_in > _lim_w else "off",
                help="Vessel connection for BW supply — separate from internal header ID.",
            )
            nv2.metric(
                f"BW outlet nozzle ({ulbl('velocity_m_s')})",
                fmt(_v_out, "velocity_m_s", 2) if _v_out > 0 else "—",
                delta="pairs with collector DN",
                delta_color="off",
                help="Vessel connection at the collector zone — internal header may match this DN.",
            )
            nv3.metric(
                f"Air scour nozzle ({ulbl('velocity_m_s')})",
                fmt(_v_air, "velocity_m_s", 2) if _v_air > 0 else "—",
                delta=f"high-air flag {fmt(_lim_a, 'velocity_m_s', 0)}",
                delta_color="inverse" if _v_air > _lim_a else "off",
                help="Separate air line through the vessel shell — not the BW collector lateral velocity.",
            )
            if _ci.get("nozzle_velocity_note_air"):
                st.caption(localize_engine_message(str(_ci["nozzle_velocity_note_air"])))
            if _ci.get("nozzle_velocity_note_vessel"):
                st.caption(localize_engine_message(str(_ci["nozzle_velocity_note_vessel"])))
            for _rec in _ci.get("recommendations") or []:
                st.markdown(f"- {localize_engine_message(str(_rec))}")
            for _f in _ci.get("findings") or []:
                _topic = str(_f.get("topic", ""))
                if _topic in ("Nozzle velocity", "Nozzle spread"):
                    continue
                _sev = str(_f.get("severity", "advisory"))
                _msg = localize_engine_message(
                    f"**{_topic}:** {_f.get('detail', '')}"
                )
                if _sev == "critical":
                    st.error(_msg)
                elif _sev == "warning":
                    st.warning(_msg)
                else:
                    st.info(_msg)

    _ch = computed.get("collector_hyd") or {}
    if _ch:
        with st.expander(
            "Legacy pipe-lateral surrogate (optional — not your nozzle-plate layout)",
            expanded=False,
        ):
            st.caption(
                "Screening model with **pipe laterals** and perforations. "
                "For this project use **Nozzle plate — BW hydraulics** above. "
                + str(_ch.get("method", ""))
            )
            _mal_used = float(computed.get("maldistribution_factor", 1.0) or 1.0)
            _mal_calc = float(_ch.get("maldistribution_factor_calc", 1.0) or 1.0)
            _from_model = bool(computed.get("maldistribution_from_collector_model"))
            hc1, hc2, hc3, hc4 = st.columns(4)
            hc1.metric("Filtration mal factor (in ΔP)", f"{_mal_used:.3f}")
            hc2.metric(
                "Distribution factor (1D)",
                f"{_mal_calc:.3f}",
                help="max/mean flow across 1D orifice stations (nozzle-plate screening surrogate; not §4 shell nozzles).",
            )
            hc3.metric(
                "Flow imbalance (1D stations)",
                f"{_ch.get('flow_imbalance_pct', 0):.1f}%",
                help="Spread across equivalent orifice stations — not pipe lateral count.",
            )
            hc4.metric(
                "Filtration mal source",
                "1D screening" if _from_model else "Manual",
            )
            if _ch.get("tee_loss_enabled"):
                st.caption(
                    localize_engine_message(
                        f"**Branch tee losses on** — K = **{_ch.get('k_tee_branch', '—')}** "
                        f"(Δh = K·V²/2g per lateral). Cumulative tee loss ≈ "
                        f"**{_ch.get('tee_loss_total_kpa', 0):.2f} kPa** on this case "
                        "(screening; sidebar **Underdrain / nozzle plate (1D)**)."
                    )
                )
            from engine.collector_hydraulics import (
                DISTRIBUTION_TOL_REL,
                distribution_metadata_available,
                distribution_residual_rel,
                distribution_solver_converged,
            )

            _dist_meta = distribution_metadata_available(_ch)
            _dist_res = distribution_residual_rel(_ch)
            _dist_ok = distribution_solver_converged(_ch)
            hd1, hd2, hd3 = st.columns(3)
            hd1.metric("Distribution iterations", int(_ch.get("distribution_iterations", 0)))
            if not _dist_meta:
                hd2.metric(
                    "Solver status",
                    "Stale",
                    delta="change any input to refresh",
                    delta_color="off",
                )
            else:
                hd2.metric(
                    "Solver status",
                    "Converged" if _dist_ok else "Not converged",
                    delta=(
                        f"residual {_dist_res:.4f} (≤ {DISTRIBUTION_TOL_REL:.3f})"
                        if _dist_res is not None
                        else ""
                    ),
                    delta_color="normal" if _dist_ok else "inverse",
                )
            hd3.metric(
                f"Max header V ({ulbl('velocity_m_s')})",
                fmt(_ch.get("header_velocity_max_m_s", 0), "velocity_m_s", 2),
            )
            from ui.collector_apply import apply_collector_suggested_design

            def _apply_collector_suggested() -> None:
                apply_collector_suggested_design(computed)

            st.button(
                "Apply suggested collector design",
                key="collector_apply_suggested",
                help=(
                    "Writes screening suggestions to sidebar BW collector inputs "
                    "(N laterals, DN, spacing, perforations; optional link to filtration mal factor). "
                    "Does not change §4 vessel nozzles or linked header ID."
                ),
                on_click=_apply_collector_suggested,
            )
            st.caption(
                "Apply is explicit — review advisories above before accepting. "
                "Header ID follows §4 when **Link** is on (Mechanical §4 / sidebar BW)."
            )
            g1, g2, g3, g4, g5 = st.columns(5)
            g1.metric("θ (lateral)", f"{float(_ch.get('theta_deg', 0)):.1f}°")
            g2.metric("L lateral max (pipe)", fmt(float(_ch.get("lateral_length_max_m", 0)), "length_m", 2))
            g2.caption(
                f"Plan reach {fmt(float(_ch.get('lateral_horiz_reach_m', 0)), 'length_m', 2)}"
            )
            g3.metric("Header spacing max", fmt(float(_ch.get("lateral_spacing_max_m", 0)), "length_m", 2))
            g4.metric(
                f"Perf. pitch ({ulbl('length_mm')})",
                fmt(
                    float(_ch.get("perforation_pitch_used_mm")
                          or _ch.get("perforation_pitch_min_mm") or 0),
                    "length_mm",
                    0,
                ),
            )
            _is_wedge = str(_ch.get("screening_model", "")) == "wedge_wire"
            g5.metric(
                "Openings / lateral" if _is_wedge else "Perforations / lateral",
                int(_ch.get("n_orifices_per_lateral") or 0) if not _is_wedge else "—",
            )
            st1, st2, st3 = st.columns(3)
            st1.metric(
                "Open area (screening)",
                f"{float(_ch.get('open_area_fraction_pct', 0)):.1f}%",
                delta=f"typical {_ch.get('lateral_material_open_area_range_pct', '—')}",
                delta_color=(
                    "inverse"
                    if float(_ch.get("open_area_fraction_pct", 0))
                    > float(_ch.get("open_area_limit_pct", 60))
                    else "off"
                ),
            )
            if _is_wedge:
                st2.metric("Screening model", "Wedge wire", delta="collapse / OEM")
                st3.metric(
                    f"Target slot V ({ulbl('velocity_m_s')})",
                    fmt(_ch.get("target_opening_velocity_m_s", 0), "velocity_m_s", 1),
                )
            else:
                st2.metric("Max perf. / lateral (struct.)", int(_ch.get("n_perforations_max_structural") or 0))
                st3.metric("Pipe schedule (advisory)", str(_ch.get("lateral_schedule_suggest", "—")))
            st.caption(
                f"**{_ch.get('lateral_construction', '—')}** · **{_ch.get('lateral_material', '—')}** · "
                f"water **{_ch.get('water_service', '—')}** · "
                f"Cd **{float(_ch.get('discharge_coefficient', 0.62)):.2f}** · "
                f"headloss factor **{float(_ch.get('hydraulic_headloss_factor', 1)):.2f}**"
            )
            for _wrec in _ch.get("water_material_recommendations") or []:
                st.caption(localize_engine_message(str(_wrec)))
            _des = _ch.get("design") or {}
            if _des.get("lateral_dn_suggest_mm"):
                st.caption(
                    f"Screening: lateral DN ≥ **{fmt(_des['lateral_dn_suggest_mm'], 'length_mm', 0)}** · "
                    f"perforation Ø ≥ **{fmt(_des.get('perforation_d_suggest_mm', 0), 'length_mm', 1)}** "
                    f"(velocity targets)."
                )
            _pmin = _ch.get("perforation_pitch_min_mm")
            _pmax = _ch.get("perforation_pitch_max_mm")
            if isinstance(_pmin, (int, float)) and isinstance(_pmax, (int, float)):
                _pitch_lim = fmt_si_range(float(_pmin), float(_pmax), "length_mm", 0, 0)
            else:
                _pitch_lim = localize_engine_message(
                    f"{_pmin}–{_pmax} mm"
                )
            st.caption(
                f"Lateral length from **nozzle-plate axis → shell @ collector height** when geometry auto is on. "
                f"Pitch limits **{_pitch_lim}**. "
                f"Perforation source: {_ch.get('perforation_auto_source', '—')}."
            )
            for _gn in _des.get("notes") or []:
                st.info(localize_engine_message(str(_gn)))
            for _adv in _ch.get("advisories") or []:
                _sev = str(_adv.get("severity", "advisory"))
                _msg = localize_engine_message(
                    f"**{_adv.get('topic', '')}:** {_adv.get('detail', '')}"
                )
                if _sev == "critical":
                    st.error(_msg)
                elif _sev == "warning":
                    st.warning(_msg)
                else:
                    st.info(_msg)
            _vrisk = computed.get("collector_velocity_risk") or {}
            if _vrisk.get("active"):
                with st.expander(
                    "Velocity & erosion screening (internal distributor, advisory)",
                    expanded=False,
                ):
                    st.caption(
                        localize_engine_message(
                            str(_vrisk.get("method", ""))
                            + " — **advisory heuristics** on 1D model velocities; not wear-rate CFD."
                        )
                    )
                    v1, v2 = st.columns(2)
                    v1.metric(
                        "Advisory score",
                        f"{int(_vrisk.get('severity_score', 0))}/100",
                        delta=str(_vrisk.get("grade", "")),
                        delta_color="inverse"
                        if int(_vrisk.get("severity_score", 100) or 100) < 70
                        else "off",
                    )
                    v2.metric(
                        "Peak opening / slot " + f"({ulbl('velocity_m_s')})",
                        fmt(_vrisk.get("orifice_velocity_max_m_s", 0), "velocity_m_s", 2),
                        delta=f"imbalance {_vrisk.get('flow_imbalance_pct', 0):.1f}%",
                        delta_color="off",
                    )
                    _hs = list(_vrisk.get("hotspots") or [])
                    if _hs:
                        st.markdown("**Hotspots** (peaks + top holes from 1B network)")
                        _df_h = pd.DataFrame(_hs)
                        st.dataframe(_df_h, use_container_width=True, hide_index=True)
                    for _vf in _vrisk.get("findings") or []:
                        _topic = str(_vf.get("topic", ""))
                        _sev = str(_vf.get("severity", "advisory"))
                        _msg = localize_engine_message(
                            f"**{_topic}:** {_vf.get('detail', '')}"
                        )
                        if _sev == "warning":
                            st.warning(_msg)
                        else:
                            st.info(_msg)
                    if _vrisk.get("plugging_hint"):
                        st.info(localize_engine_message(str(_vrisk["plugging_hint"])))
                    if _vrisk.get("sand_carryover_hint"):
                        st.warning(localize_engine_message(str(_vrisk["sand_carryover_hint"])))
            _bw_env = computed.get("collector_bw_envelope")
            if isinstance(_bw_env, dict) and _bw_env.get("active"):
                with st.expander(
                    "BW flow operating envelope (1D sweep)",
                    expanded=False,
                ):
                    st.caption(localize_engine_message(str(_bw_env.get("note", ""))))
                    _qx = list(_bw_env.get("q_bw_m3h") or [])
                    _pref = f"({ulbl('flow_m3h')})"
                    if not _qx:
                        st.info("No sweep points returned.")
                    else:
                        try:
                            import plotly.graph_objects as go

                            _imb = list(_bw_env.get("flow_imbalance_pct") or [])
                            _hv = list(_bw_env.get("header_velocity_max_m_s") or [])
                            _ov = list(_bw_env.get("orifice_velocity_max_m_s") or [])
                            _feas = list(_bw_env.get("feasible") or [])
                            fig1 = go.Figure()
                            _imb_y = [float(x) if x is not None else None for x in _imb]
                            fig1.add_trace(
                                go.Scatter(
                                    x=_qx,
                                    y=_imb_y,
                                    mode="lines+markers",
                                    name="Lateral imbalance %",
                                )
                            )
                            fig1.update_layout(
                                title="BW flow vs lateral imbalance",
                                xaxis_title=f"BW flow {_pref}",
                                yaxis_title="Imbalance %",
                                template="plotly_white",
                                height=320,
                            )
                            st.plotly_chart(fig1, use_container_width=True, key="collector_bw_env_imb")
                            fig2 = go.Figure()
                            fig2.add_trace(
                                go.Scatter(
                                    x=_qx,
                                    y=[float(x) if x is not None else None for x in _hv],
                                    mode="lines+markers",
                                    name=f"Header Vmax ({ulbl('velocity_m_s')})",
                                )
                            )
                            fig2.add_trace(
                                go.Scatter(
                                    x=_qx,
                                    y=[float(x) if x is not None else None for x in _ov],
                                    mode="lines+markers",
                                    name=f"Orifice Vmax ({ulbl('velocity_m_s')})",
                                )
                            )
                            fig2.update_layout(
                                title="BW flow vs peak velocities",
                                xaxis_title=f"BW flow {_pref}",
                                yaxis_title=f"Velocity ({ulbl('velocity_m_s')})",
                                template="plotly_white",
                                height=320,
                            )
                            st.plotly_chart(fig2, use_container_width=True, key="collector_bw_env_vel")
                            if any(bool(f) for f in _feas):
                                _ok = sum(1 for f in _feas if f)
                                st.caption(
                                    localize_engine_message(
                                        f"**Feasible** points (converged, imbalance cap): **{_ok}** / **{len(_feas)}**."
                                    )
                                )
                        except Exception:
                            st.info("Install **plotly** for BW envelope charts.")
                            st.dataframe(pd.DataFrame(_bw_env.get("sweep_rows") or []), hide_index=True)
            _stg = computed.get("collector_staged_orifices")
            if isinstance(_stg, dict) and _stg.get("active"):
                with st.expander(
                    "Staged perforation Ø (advisory drill schedule)",
                    expanded=False,
                ):
                    st.caption(localize_engine_message(str(_stg.get("method", ""))))
                    for _n in _stg.get("notes") or []:
                        st.caption(localize_engine_message(str(_n)))
                    _groups = _stg.get("groups") or []
                    if _groups:
                        st.markdown("**Bands (per lateral)**")
                        st.dataframe(
                            staged_orifice_bands_display_df(_groups),
                            use_container_width=True,
                            hide_index=True,
                        )
                    v0 = _stg.get("estimated_velocity_spread_baseline_m_s")
                    v1 = _stg.get("estimated_velocity_spread_after_snap_m_s")
                    if isinstance(v0, dict) and isinstance(v1, dict):
                        st.caption(
                            localize_engine_message(
                                f"Estimated jet **v** span (model split): "
                                f"{v0.get('min_m_s', '—')}–{v0.get('max_m_s', '—')} **m/s** → "
                                f"after snap (frozen **Q**): "
                                f"{v1.get('min_m_s', '—')}–{v1.get('max_m_s', '—')} **m/s**."
                            )
                        )
                    _ph = _stg.get("per_hole") or []
                    if _ph and st.checkbox("Show per-hole detail", key="collector_staged_show_holes"):
                        st.dataframe(
                            staged_orifice_hole_display_df(_ph),
                            use_container_width=True,
                            hide_index=True,
                        )
            elif isinstance(_stg, dict) and (_stg.get("note") or ""):
                with st.expander(
                    "Staged perforation Ø (advisory) — unavailable for this case",
                    expanded=False,
                ):
                    st.warning(localize_engine_message(str(_stg.get("note", ""))))
            for _rec in _ch.get("recommendations") or []:
                st.markdown(f"- {localize_engine_message(str(_rec))}")
            with st.expander("1A/1B regression benchmarks", expanded=False):
                from engine.collector_benchmarks import (
                    check_collector_hyd_sanity,
                    run_collector_benchmark_suite,
                    suite_all_passed,
                )

                st.caption(
                    "Hand-calc style checks on the **1D** header/lateral model "
                    "(not CFD). Sanity runs on this design; full suite is eight reference cases."
                )
                _san = [
                    {
                        **row,
                        "detail": localize_engine_message(str(row.get("detail", ""))),
                    }
                    for row in check_collector_hyd_sanity(_ch)
                ]
                st.dataframe(
                    _san,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "check": st.column_config.TextColumn("Check"),
                        "ok": st.column_config.TextColumn("OK"),
                        "detail": st.column_config.TextColumn("Detail", width="large"),
                    },
                )
                if st.button("Run full benchmark suite", key="collector_run_benchmarks"):
                    _bench = run_collector_benchmark_suite()
                    st.session_state["collector_benchmark_results"] = _bench
                _bench_res = st.session_state.get("collector_benchmark_results")
                if _bench_res:
                    _n_pass = sum(1 for r in _bench_res if r.get("passed"))
                    st.caption(
                        f"**{_n_pass}/{len(_bench_res)}** passed · "
                        f"{'All OK' if suite_all_passed(_bench_res) else 'Review failures'}"
                    )
                    st.dataframe(
                        [
                            {
                                "Benchmark": r["title"],
                                "Pass": "✓" if r["passed"] else "✗",
                                "Detail": localize_engine_message(str(r["detail"])),
                            }
                            for r in _bench_res
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
            _chk = _ch.get("design_checklist") or []
            if _chk:
                with st.expander("Design checklist — collector & expansion", expanded=False):
                    for _line in _chk:
                        st.markdown(f"- {localize_engine_message(str(_line))}")
            _fig_el = build_collector_elevation_figure(
                vessel_id_m=float(computed.get("nominal_id") or inputs.get("nominal_id", 1.0)),
                collector_hyd=_ch,
                layers=inputs.get("layers"),
                bw_exp=computed.get("bw_exp"),
            )
            if _fig_el is not None:
                st.plotly_chart(_fig_el, use_container_width=True, key="collector_hyd_elevation")
            hc5, hc6 = st.columns(2)
            hc5.metric(
                f"Header V max ({ulbl('velocity_m_s')})",
                fmt(_ch.get("header_velocity_max_m_s", 0), "velocity_m_s", 2),
            )
            hc6.metric(
                f"Perforation V max ({ulbl('velocity_m_s')})",
                fmt(_ch.get("orifice_velocity_max_m_s", 0), "velocity_m_s", 2),
            )
            for _w in _ch.get("warnings") or []:
                st.warning(localize_engine_message(str(_w)))
            _prof = _ch.get("profile") or []
            if _prof:
                st.dataframe(
                    collector_hyd_profile_display_df(_prof),
                    use_container_width=True,
                    hide_index=True,
                )
            _fig_col = build_collector_underdrain_figure(
                cyl_len_m=float(computed.get("cyl_len") or inputs.get("total_length", 1.0)),
                vessel_id_m=float(computed.get("nominal_id") or inputs.get("nominal_id", 1.0)),
                collector_hyd=_ch,
                inputs=inputs,
            )
            if _fig_col is not None:
                st.plotly_chart(_fig_col, use_container_width=True, key="collector_hyd_schematic")
            else:
                st.info("Install **plotly** to show the collector plan schematic.")

            with st.expander("1B+ Manifold screening (per-hole table)", expanded=False):
                st.caption(
                    "**1B+** compares **one-end vs dual-end** header feed and lists each perforation "
                    "flow/velocity in your selected unit system. Use this for design review — "
                    "no external CFD software required."
                )
                _feed = str(_ch.get("header_feed_mode") or "one_end")
                _feed_lbl = (
                    "One end (standard 1B)"
                    if _feed == "one_end"
                    else "Dual end (centre-fed screening)"
                )
                st.markdown(f"**Header feed:** {_feed_lbl}")
                _cmp = _ch.get("feed_mode_comparison")
                if _cmp:
                    c1, c2, c3 = st.columns(3)
                    c1.metric(
                        "Mal. (one end)",
                        f"{_cmp.get('one_end', {}).get('mal', 1):.3f}",
                    )
                    c2.metric(
                        "Mal. (dual end)",
                        f"{_cmp.get('dual_end', {}).get('mal', 1):.3f}",
                    )
                    c3.metric(
                        "Imbalance Δ (pp)",
                        f"{_cmp.get('imbalance_improvement_pct_pts', 0):.1f}",
                        help="Positive = dual-end reduced lateral spread vs one-end on this case.",
                    )
                _orn = _ch.get("orifice_network") or []
                if _orn:
                    st.markdown(f"**Perforation network** — {len(_orn)} holes")
                    _show = _orn[:80]
                    st.dataframe(
                        orifice_network_display_df(_show),
                        use_container_width=True,
                        hide_index=True,
                    )
                    if len(_orn) > 80:
                        st.caption(f"Showing 80 of {len(_orn)} holes.")
                _cfd = computed.get("collector_cfd_bundle")
                if _cfd:
                    with st.expander(
                        "Optional — export for external CFD (OpenFOAM / Fluent)",
                        expanded=False,
                    ):
                        st.caption(
                            "Only needed if a consultant runs CFD. You can ignore this "
                            "if you do not have CFD software."
                        )
                        from engine.collector_cfd_export import build_cfd_export_bytes

                        _cfd_fmt = st.selectbox(
                            "Export format",
                            options=["json", "csv_orifices"],
                            format_func=lambda x: (
                                "JSON (full boundary package)"
                                if x == "json"
                                else "CSV (orifice table only)"
                            ),
                            key="collector_cfd_export_fmt",
                        )
                        _data, _fname, _mime = build_cfd_export_bytes(_cfd, _cfd_fmt)
                        st.download_button(
                            "Download for external CFD",
                            data=_data,
                            file_name=_fname,
                            mime=_mime,
                            key="collector_cfd_download",
                        )
                from ui.cfd_import_panel import render_cfd_import_panel

                render_cfd_import_panel(computed, key_prefix="collector_cfd_import")
