"""engine/compute.py — Central computation engine for AQUASIGHT™ MMF."""
import math as _math

from engine.geometry   import segment_area, dish_volume
from engine.process    import filter_loading
from engine.water      import water_properties
from engine.mechanical import (
    thickness, apply_thickness_override, empty_weight,
    nozzle_plate_design, saddle_weight, internals_weight,
    operating_weight, saddle_design, MATERIALS,
)
from engine.nozzles    import estimate_nozzle_schedule
from engine.backwash   import (
    backwash_hydraulics, bed_expansion, pressure_drop,
    bw_sequence, filtration_cycle, bw_system_sizing,
    solve_equivalent_velocity_for_target_expansion_pct,
    actual_m3m2h_to_nm3_m2h,
    filter_bw_timeline_24h,
    timeline_plant_operating_hours,
)
from engine.collector_ext import collector_check_ext
from engine.coating    import internal_surface_areas, lining_cost
from engine.cartridge  import cartridge_design, cartridge_optimise
from engine.energy     import hydraulic_profile, energy_summary, bw_equipment_hours_per_event
from engine.economics  import (
    capex_breakdown, opex_annual, carbon_footprint,
    global_benchmark_comparison, npv_lifecycle_cost_profile,
)
from engine.financial_economics import build_econ_financial
from engine.pump_performance import build_pump_performance_package
from engine.validators import REFERENCE_FALLBACK_INPUTS, validate_inputs
from engine.environment_loads import compute_environment_structural
from engine.thresholds import (
    ensure_layer_threshold_defaults,
    layer_ebct_floor_min,
    layer_lv_cap_m_h,
)


def lv_severity_classify(vel: float, threshold: float):
    """Map filtration LV vs envelope threshold → advisory | warning | critical | None."""
    if vel <= threshold:
        return None
    ovr = (vel - threshold) / threshold
    if ovr <= 0.05:
        return "advisory"
    if ovr <= 0.15:
        return "warning"
    return "critical"


def ebct_severity_classify(ebct: float, threshold: float):
    """Map EBCT vs lower limit → advisory | warning | critical | None."""
    if ebct >= threshold:
        return None
    short = (threshold - ebct) / threshold
    if short <= 0.10:
        return "advisory"
    if short <= 0.25:
        return "warning"
    return "critical"


def compute_all(inputs: dict) -> dict:
    import time
    from engine import logger as _log
    t0 = time.perf_counter()
    input_validation = validate_inputs(inputs)
    if not input_validation["valid"]:
        _log.log_validation_errors(input_validation.get("errors", []))
    _work = REFERENCE_FALLBACK_INPUTS if not input_validation["valid"] else inputs
    _log.log_compute_start(
        str(_work.get("project_name", "")),
        str(_work.get("doc_number", "")),
    )
    out = None
    exc = None
    try:
        out = _compute_all_impl(_work, input_validation)
    except BaseException as e:
        exc = e
        raise
    finally:
        nw = None
        if out is not None:
            try:
                nw = int(out.get("n_warnings", 0))
            except (TypeError, ValueError):
                nw = None
        _log.log_compute_end(
            time.perf_counter() - t0,
            valid=bool(input_validation.get("valid")),
            fallback_used=not input_validation["valid"],
            n_validation_warnings=len(input_validation.get("warnings", [])),
            n_output_warnings=nw,
            exc=exc,
        )
    return out


def _compute_all_impl(_work: dict, input_validation: dict) -> dict:
        # ── Unpack inputs ──────────────────────────────────────────────────────
        total_flow      = _work["total_flow"]
        streams         = _work["streams"]
        n_filters       = _work["n_filters"]
        redundancy      = _work["redundancy"]
        hydraulic_assist = max(0, min(4, int(_work.get("hydraulic_assist", 0))))
        feed_temp       = _work["feed_temp"]
        feed_sal        = _work["feed_sal"]
        temp_low        = _work["temp_low"]
        temp_high       = _work["temp_high"]
        tss_low         = _work["tss_low"]
        tss_avg         = _work["tss_avg"]
        tss_high        = _work["tss_high"]
        bw_temp         = _work["bw_temp"]
        bw_sal          = _work["bw_sal"]
        nominal_id      = _work["nominal_id"]
        total_length    = _work["total_length"]
        end_geometry    = _work["end_geometry"]
        lining_mm       = _work["lining_mm"]
        material_name   = _work["material_name"]
        mat_info        = _work["mat_info"]
        shell_radio     = _work["shell_radio"]
        head_radio      = _work["head_radio"]
        design_pressure = _work["design_pressure"]
        corrosion       = _work["corrosion"]
        steel_density   = _work["steel_density"]
        ov_shell        = _work["ov_shell"]
        ov_head         = _work["ov_head"]
        nozzle_plate_h  = _work["nozzle_plate_h"]
        np_bore_dia     = _work["np_bore_dia"]
        np_density      = _work["np_density"]
        np_beam_sp      = _work["np_beam_sp"]
        np_override_t   = _work["np_override_t"]
        np_slot_dp      = _work["np_slot_dp"]
        collector_h     = _work["collector_h"]
        freeboard_mm    = _work["freeboard_mm"]
        layers          = _work["layers"]
        ensure_layer_threshold_defaults(_work)
        velocity_threshold = float(_work["velocity_threshold"])
        ebct_threshold     = float(_work["ebct_threshold"])
        layers          = _work["layers"]
        solid_loading   = _work["solid_loading"]
        _sl_scale = max(0.5, min(1.5, float(_work.get("solid_loading_scale", 1.0) or 1.0)))
        solid_loading_eff = float(solid_loading) * _sl_scale
        _mal = max(1.0, float(_work.get("maldistribution_factor", 1.0) or 1.0))
        _acf = max(0.05, min(3.0, float(_work.get("alpha_calibration_factor", 1.0) or 1.0)))
        _tss_cap = max(0.0, min(1.0, float(_work.get("tss_capture_efficiency", 1.0) or 1.0)))
        _exp_scl = max(0.5, min(1.5, float(_work.get("expansion_calibration_scale", 1.0) or 1.0)))
        captured_solids_density = _work["captured_solids_density"]
        alpha_specific  = _work["alpha_specific"]
        dp_trigger_bar  = _work["dp_trigger_bar"]
        bw_velocity     = _work["bw_velocity"]
        air_scour_rate  = _work["air_scour_rate"]
        air_scour_mode  = str(_work.get("air_scour_mode", "manual")).strip().lower()
        air_scour_target_pct = float(_work.get("air_scour_target_expansion_pct", 20.0))
        airwater_step_water_m_h = float(_work.get("airwater_step_water_m_h", 12.5))
        bw_timeline_stagger = str(_work.get("bw_timeline_stagger", "feasibility_trains")).strip().lower()
        bw_cycles_day   = _work["bw_cycles_day"]
        bw_s_drain      = _work["bw_s_drain"]
        bw_s_air        = _work["bw_s_air"]
        bw_s_airw       = _work["bw_s_airw"]
        bw_s_hw         = _work["bw_s_hw"]
        bw_s_settle     = _work["bw_s_settle"]
        bw_s_fill       = _work["bw_s_fill"]
        bw_total_min    = _work["bw_total_min"]
        vessel_pressure_bar  = _work["vessel_pressure_bar"]
        blower_air_delta_p_bar = float(_work.get("blower_air_delta_p_bar", 0.15))
        blower_eta      = _work["blower_eta"]
        blower_inlet_temp_c  = _work["blower_inlet_temp_c"]
        tank_sf         = _work["tank_sf"]
        bw_head_mwc     = _work["bw_head_mwc"]
        default_rating  = _work["default_rating"]
        nozzle_stub_len = _work["nozzle_stub_len"]
        strainer_mat    = _work["strainer_mat"]
        air_header_dn   = _work["air_header_dn"]
        manhole_dn      = _work["manhole_dn"]
        n_manholes      = _work["n_manholes"]
        support_type    = _work["support_type"]
        saddle_h        = _work["saddle_h"]
        leg_h           = _work["leg_h"]
        leg_section     = _work["leg_section"]
        base_plate_t    = _work["base_plate_t"]
        gusset_t        = _work["gusset_t"]
        saddle_contact_angle = _work["saddle_contact_angle"]
        protection_type = _work["protection_type"]
        rubber_type_sel = _work["rubber_type_sel"]
        rubber_layers   = _work["rubber_layers"]
        rubber_cost_m2  = _work["rubber_cost_m2"]
        rubber_labor_m2 = _work["rubber_labor_m2"]
        epoxy_type_sel  = _work["epoxy_type_sel"]
        epoxy_dft_um    = _work["epoxy_dft_um"]
        epoxy_coats     = _work["epoxy_coats"]
        epoxy_cost_m2   = _work["epoxy_cost_m2"]
        epoxy_labor_m2  = _work["epoxy_labor_m2"]
        ceramic_type_sel = _work["ceramic_type_sel"]
        ceramic_dft_um  = _work["ceramic_dft_um"]
        ceramic_coats   = _work["ceramic_coats"]
        ceramic_cost_m2 = _work["ceramic_cost_m2"]
        ceramic_labor_m2 = _work["ceramic_labor_m2"]
        cart_flow       = _work["cart_flow"]
        cart_size       = _work["cart_size"]
        cart_rating     = _work["cart_rating"]
        cart_housing    = _work["cart_housing"]
        cart_cip        = _work["cart_cip"]
        cf_inlet_tss    = _work["cf_inlet_tss"]
        cf_outlet_tss   = _work["cf_outlet_tss"]
        _cart_dhc_ov = float(_work.get("cart_dhc_override_g", 0.0) or 0.0)
        cart_dhc_override = _cart_dhc_ov if _cart_dhc_ov > 1e-9 else None
        dp_dist         = _work["dp_dist"]
        dp_inlet_pipe   = _work["dp_inlet_pipe"]
        dp_outlet_pipe  = _work["dp_outlet_pipe"]
        p_residual      = _work["p_residual"]
        static_head     = _work["static_head"]
        pump_eta        = _work["pump_eta"]
        bw_pump_eta     = _work["bw_pump_eta"]
        motor_eta       = _work["motor_eta"]
        elec_tariff     = _work["elec_tariff"]
        op_hours_yr     = _work["op_hours_yr"]
        design_life_years    = _work["design_life_years"]
        discount_rate        = _work.get("discount_rate", 5.0)
        steel_cost_usd_kg    = _work["steel_cost_usd_kg"]
        erection_usd_vessel  = _work["erection_usd_vessel"]
        piping_usd_vessel    = _work["piping_usd_vessel"]
        instrumentation_usd_vessel = _work["instrumentation_usd_vessel"]
        civil_usd_vessel     = _work["civil_usd_vessel"]
        engineering_pct      = _work["engineering_pct"]
        contingency_pct      = _work["contingency_pct"]
        media_replace_years  = _work["media_replace_years"]
        econ_media_gravel    = _work["econ_media_gravel"]
        econ_media_sand      = _work["econ_media_sand"]
        econ_media_anthracite = _work["econ_media_anthracite"]
        nozzle_replace_years = _work["nozzle_replace_years"]
        nozzle_unit_cost     = _work["nozzle_unit_cost"]
        labour_usd_filter_yr = _work["labour_usd_filter_yr"]
        chemical_cost_m3     = _work["chemical_cost_m3"]
        grid_intensity       = _work["grid_intensity"]
        steel_carbon_kg      = _work["steel_carbon_kg"]
        concrete_carbon_kg   = _work["concrete_carbon_kg"]
        media_co2_by_type    = _work.get("media_co2", {})

        # ── Block 2: Water properties ──────────────────────────────────────────
        feed_wp = water_properties(feed_temp, feed_sal)
        bw_wp   = water_properties(bw_temp,  bw_sal)
        rho_feed = feed_wp["density_kg_m3"]
        mu_feed  = feed_wp["viscosity_pa_s"]
        rho_bw   = bw_wp["density_kg_m3"]
        mu_bw    = bw_wp["viscosity_pa_s"]

        # ── Block 3: Vessel geometry ───────────────────────────────────────────
        h_dish  = (nominal_id / 4) if end_geometry == "Elliptic 2:1" else (0.2 * nominal_id)
        cyl_len = total_length - 2 * h_dish
        real_id = nominal_id - 2.0 * lining_mm / 1000.0

        # ── Block 3: Mechanical ────────────────────────────────────────────────
        mech_base = thickness(
            diameter_m=nominal_id, design_pressure_bar=design_pressure,
            material_name=material_name, shell_radio=shell_radio,
            head_radio=head_radio, corrosion_mm=corrosion,
            internal_lining_mm=lining_mm,
        )
        mech = apply_thickness_override(
            mech_base, override_shell_mm=ov_shell, override_head_mm=ov_head,
            internal_lining_mm=lining_mm, nominal_id_m=nominal_id,
        )
        mech["corrosion_mm"] = corrosion

        wt_body = empty_weight(
            diameter_m=real_id, straight_length_m=cyl_len, end_geometry=end_geometry,
            t_shell_mm=mech["t_shell_design_mm"], t_head_mm=mech["t_head_design_mm"],
            density_kg_m3=steel_density,
        )

        # ── Block 4: Media geometry ────────────────────────────────────────────
        geo_rows, base = [], []
        curr_h = nozzle_plate_h
        if nozzle_plate_h > 0:
            a0 = segment_area(0, real_id)
            a1 = segment_area(nozzle_plate_h, real_id)
            v_c = (a1 - a0) * cyl_len
            v_e = (dish_volume(nozzle_plate_h, real_id, h_dish, end_geometry) -
                   dish_volume(0, real_id, h_dish, end_geometry)) * 2
            tot = v_c + v_e
            geo_rows.append(["Nozzle Plate", nozzle_plate_h,
                             tot / nozzle_plate_h if nozzle_plate_h else 0, v_c, v_e, tot])
        for L in layers:
            h1, h2 = curr_h, curr_h + L["Depth"]
            v_c  = (segment_area(h2, real_id) - segment_area(h1, real_id)) * cyl_len
            v_e  = (dish_volume(h2, real_id, h_dish, end_geometry) -
                    dish_volume(h1, real_id, h_dish, end_geometry)) * 2
            vol  = v_c + v_e
            area = vol / L["Depth"] if L["Depth"] > 0 else 0
            base.append({**L, "Vol": vol, "Area": area})
            geo_rows.append([L["Type"], L["Depth"], area, v_c, v_e, vol])
            curr_h = h2
        avg_area     = sum(b["Area"] for b in base) / len(base) if base else 1.0
        _layer_areas = [float(b["Area"]) for b in base] if base else None
        _n_hyd       = max(1, n_filters - hydraulic_assist)
        q_per_filter = (total_flow / streams) / _n_hyd if _n_hyd > 0 else 0.0

        # ── Block 4: Pressure drop (Ergun) ────────────────────────────────────────
        bw_dp = pressure_drop(
            layers=layers,
            q_filter_m3h=q_per_filter,
            avg_area_m2=avg_area,
            solid_loading_kg_m2=solid_loading_eff,
            captured_density_kg_m3=captured_solids_density,
            water_temp_c=feed_temp,
            rho_water=rho_feed,
            alpha_m_kg=alpha_specific,
            dp_trigger_bar=dp_trigger_bar,
            layer_areas_m2=_layer_areas,
            maldistribution_factor=_mal,
            alpha_calibration_factor=_acf,
        )
        np_dp_auto = bw_dp["dp_dirty_bar"]

        # ── Block 3: Nozzle plate ─────────────────────────────────────────────────
        wt_np = nozzle_plate_design(
            vessel_id_m=real_id,
            cyl_len_m=cyl_len,
            h_dish_m=h_dish,
            h_plate_m=nozzle_plate_h,
            design_dp_bar=np_dp_auto,
            media_layers=layers,
            water_density_kg_m3=rho_feed,
            nozzle_density_per_m2=np_density,
            bore_diameter_mm=np_bore_dia,
            beam_spacing_mm=np_beam_sp,
            allowable_stress_kgf_cm2=float(mech["allowable_stress"]),
            corrosion_allowance_mm=corrosion,
            density_kg_m3=steel_density,
            override_thickness_mm=np_override_t,
        )

        # ── Block 6: Nozzle schedule ──────────────────────────────────────────────
        nozzle_sched = estimate_nozzle_schedule(
            q_filter_m3h=q_per_filter,
            bw_velocity_ms=bw_velocity,
            area_filter_m2=avg_area,
            default_rating=default_rating,
            stub_length_mm=float(nozzle_stub_len),
        )

        # ── Block 6: Supports ─────────────────────────────────────────────────────
        wt_sup = saddle_weight(
            vessel_od_m=mech["od_m"],
            support_type=support_type,
            saddle_height_m=saddle_h,
            leg_height_m=leg_h,
            leg_section_mm=leg_section,
            base_plate_thickness_mm=base_plate_t,
            gusset_thickness_mm=gusset_t,
            density_kg_m3=steel_density,
        )

        # ── Block 5: Backwash ─────────────────────────────────────────────────────
        air_scour_solve = None
        air_scour_used = float(air_scour_rate)
        if air_scour_mode == "auto_expansion":
            air_scour_solve = solve_equivalent_velocity_for_target_expansion_pct(
                layers=layers,
                target_expansion_pct=air_scour_target_pct,
                water_temp_c=bw_temp,
                rho_water=rho_bw,
                low_rate_water_m_h=airwater_step_water_m_h,
            )
            air_scour_used = float(air_scour_solve["velocity_m_h"])
            air_scour_solve = {
                **air_scour_solve,
                "nm3_m2_h": round(
                    actual_m3m2h_to_nm3_m2h(
                        air_scour_used,
                        float(blower_inlet_temp_c),
                        float(vessel_pressure_bar),
                    ),
                    2,
                ),
            }

        bw_hyd = backwash_hydraulics(
            filter_area_m2=avg_area,
            bw_rate_m_h=bw_velocity,
            air_scour_rate_m_h=air_scour_used,
            filtration_flow_m3h=q_per_filter,
        )
        _blower_t = float(blower_inlet_temp_c)
        _vessel_p = float(vessel_pressure_bar)
        bw_hyd = {
            **bw_hyd,
            "q_air_nm3h": round(
                actual_m3m2h_to_nm3_m2h(bw_hyd["q_air_m3h"], _blower_t, _vessel_p), 2),
            "q_air_design_nm3h": round(
                actual_m3m2h_to_nm3_m2h(bw_hyd["q_air_design_m3h"], _blower_t, _vessel_p), 2),
        }
        bw_col = collector_check_ext(
            layers=layers,
            nozzle_plate_h_m=nozzle_plate_h,
            collector_h_m=collector_h,
            bw_velocity_m_h=bw_velocity,
            water_temp_c=bw_temp,
            rho_water=rho_bw,
            min_freeboard_m=freeboard_mm / 1000.0,
        )
        bw_exp = bed_expansion(
            layers=layers,
            bw_velocity_m_h=bw_velocity,
            water_temp_c=bw_temp,
            rho_water=rho_bw,
            expansion_calibration_scale=_exp_scl,
        )
        bw_seq = bw_sequence(
            filter_area_m2=avg_area,
            tss_scenarios=[tss_low, tss_avg, tss_high],
            n_filters_total=streams * n_filters,
            bw_per_day_per_filter=bw_cycles_day,
        )

        # ── Block 6: Internals weight ─────────────────────────────────────────────
        wt_int = internals_weight(
            n_strainer_nozzles=wt_np.get("n_bores", 0),
            strainer_material=strainer_mat,
            air_header_dn_mm=int(air_header_dn),
            cyl_len_m=cyl_len,
            manhole_dn=manhole_dn,
            n_manholes=n_manholes,
        )

        # ── TSS mass balance ──────────────────────────────────────────────────────
        run_time_h = bw_seq.get("run_time_h", 24.0)
        waste_vol  = bw_seq.get("waste_vol_avg_m3", 1.0)

        def _tss_bal(tss_mg_l):
            m_sol = tss_mg_l * q_per_filter * run_time_h / 1000.0
            w_tss = (m_sol * 1e3) / waste_vol if waste_vol > 0 else 0.0
            m_day = m_sol * (streams * n_filters) * bw_cycles_day
            return round(m_sol, 1), round(w_tss, 0), round(m_day, 0)

        m_sol_low,  w_tss_low,  m_daily_low  = _tss_bal(tss_low)
        m_sol_avg,  w_tss_avg,  m_daily_avg  = _tss_bal(tss_avg)
        m_sol_high, w_tss_high, m_daily_high = _tss_bal(tss_high)

        # ── Filtration cycle (DP-trigger based) ───────────────────────────────────
        _load_data_cyc = filter_loading(
            total_flow, streams, n_filters, redundancy, hydraulic_assist,
        )
        filt_cycles: dict = {}
        for _x, _nact, _q in _load_data_cyc:
            _sc = "N" if _x == 0 else f"N-{_x}"
            filt_cycles[_sc] = filtration_cycle(
                layers=layers,
                q_filter_m3h=_q,
                avg_area_m2=avg_area,
                solid_loading_kg_m2=solid_loading_eff,
                captured_density_kg_m3=captured_solids_density,
                water_temp_c=feed_temp,
                rho_water=rho_feed,
                dp_trigger_bar=dp_trigger_bar,
                alpha_m_kg=alpha_specific,
                tss_mg_l_list=[tss_low, tss_avg, tss_high],
                layer_areas_m2=_layer_areas,
                maldistribution_factor=_mal,
                alpha_calibration_factor=_acf,
                tss_capture_efficiency=_tss_cap,
            )

        # ── Filtration cycle matrix: TSS × temperature ────────────────────────────
        _alpha_fixed = filt_cycles["N"]["alpha_used_m_kg"] if filt_cycles else 0.0
        # Stable keys for matrices (UI applies unit labels via fmt/ulbl).
        tss_col_keys = ["tss_low", "tss_avg", "tss_high"]
        tss_vals     = [tss_low, tss_avg, tss_high]
        _temp_vals   = [temp_low, feed_temp, temp_high]
        temp_col_keys = ["temp_min", "temp_design", "temp_max"]
        cycle_matrix: dict = {}
        for _x, _nact, _q in _load_data_cyc:
            _sc = "N" if _x == 0 else f"N-{_x}"
            cycle_matrix[_sc] = {}
            for _tv, _tk in zip(_temp_vals, temp_col_keys):
                cycle_matrix[_sc][_tk] = filtration_cycle(
                    layers=layers,
                    q_filter_m3h=_q,
                    avg_area_m2=avg_area,
                    solid_loading_kg_m2=solid_loading_eff,
                    captured_density_kg_m3=captured_solids_density,
                    water_temp_c=_tv,
                    rho_water=rho_feed,
                    dp_trigger_bar=dp_trigger_bar,
                    alpha_m_kg=_alpha_fixed,
                    tss_mg_l_list=tss_vals,
                    layer_areas_m2=_layer_areas,
                    maldistribution_factor=_mal,
                    alpha_calibration_factor=_acf,
                    tss_capture_efficiency=_tss_cap,
                )

        # ── BW scheduling & feasibility ───────────────────────────────────────────
        _bw_dur_h = bw_total_min / 60.0

        def _feas_kpis(t_cycle_h, bw_dur_h, n_active_per_stream, n_streams):
            t_total   = t_cycle_h + bw_dur_h
            avail_pct = t_cycle_h / t_total * 100 if t_total > 0 else 0.0
            bw_per_day = 24.0 / t_total if t_total > 0 else 0.0
            n_active_total = n_active_per_stream * n_streams
            sim_demand = n_active_total * bw_dur_h / t_total if t_total > 0 else 0.0
            bw_trains  = max(1, _math.ceil(sim_demand))
            if avail_pct >= 90 and bw_trains <= 1 and t_cycle_h >= 6:
                score, flag = "🟢 Good", "OK"
            elif avail_pct >= 80 and bw_trains <= 2 and t_cycle_h >= 3:
                score, flag = "🟡 Caution", "Review"
            else:
                score, flag = "🔴 Critical", "Redesign"
            return {
                "t_cycle_h":       round(t_cycle_h,   2),
                "avail_pct":       round(avail_pct,    1),
                "bw_per_day":      round(bw_per_day,   1),
                "sim_demand":      round(sim_demand,    2),
                "n_active_total":  n_active_total,
                "n_active_stream": n_active_per_stream,
                "bw_trains":       bw_trains,
                "score":           score,
                "flag":            flag,
            }

        feasibility_matrix: dict = {}
        for _x, _nact, _q in _load_data_cyc:
            _sc = "N" if _x == 0 else f"N-{_x}"
            feasibility_matrix[_sc] = {}
            for _t_key in temp_col_keys:
                feasibility_matrix[_sc][_t_key] = {}
                for _tss_key, _tss_v in zip(tss_col_keys, tss_vals):
                    _cyc_t = cycle_matrix[_sc][_t_key]
                    _tr    = next((r for r in _cyc_t["tss_results"]
                                   if r["TSS (mg/L)"] == _tss_v), None)
                    _t_cyc = _tr["Cycle duration (h)"] if _tr else 0.0
                    feasibility_matrix[_sc][_t_key][_tss_key] = _feas_kpis(
                        _t_cyc, _bw_dur_h, _nact, streams
                    )

        _tl_tcyc = 24.0
        try:
            _fc_tr = filt_cycles["N"]["tss_results"]
            _tr_m = next(
                (r for r in _fc_tr if abs(float(r["TSS (mg/L)"]) - float(tss_avg)) < 1e-6),
                None,
            )
            if _tr_m is None and _fc_tr:
                _tr_m = _fc_tr[len(_fc_tr) // 2]
            if _tr_m is not None:
                _v_tc = float(_tr_m["Cycle duration (h)"])
                if _math.isfinite(_v_tc) and _v_tc > 0:
                    _tl_tcyc = _v_tc
        except (KeyError, IndexError, TypeError, ValueError):
            pass
        _bw_trains_tl = 1
        _sim_d_tl = None
        try:
            _cell_tl = feasibility_matrix["N"]["temp_design"]["tss_avg"]
            _bw_trains_tl = int(max(1, int(_cell_tl.get("bw_trains", 1))))
            _sim_d_tl = float(_cell_tl.get("sim_demand", 0.0))
        except (KeyError, TypeError):
            pass
        _stag = bw_timeline_stagger if bw_timeline_stagger in ("uniform", "feasibility_trains") else "feasibility_trains"
        bw_timeline = filter_bw_timeline_24h(
            n_filters_total=int(streams * n_filters),
            t_cycle_h=_tl_tcyc,
            bw_duration_h=_bw_dur_h,
            horizon_h=24.0,
            bw_trains=_bw_trains_tl,
            stagger_model=_stag,
            sim_demand=_sim_d_tl,
        )
        _n_des_paths = streams * max(1, n_filters - hydraulic_assist)
        _tl_stats = timeline_plant_operating_hours(
            bw_timeline.get("filters") or [],
            horizon_h=float(bw_timeline.get("horizon_h", 24.0)),
            n_design_online_total=_n_des_paths,
        )
        bw_timeline = {**bw_timeline, **_tl_stats}

        # ── Cartridge design ──────────────────────────────────────────────────────
        _cart_mu_cP = mu_feed * 1000.0
        cart_result = cartridge_design(
            design_flow_m3h=cart_flow,
            element_size=cart_size,
            rating_um=cart_rating,
            mu_cP=_cart_mu_cP,
            n_elem_per_housing=cart_housing,
            is_CIP_system=cart_cip,
            cf_inlet_tss_mg_l=cf_inlet_tss,
            cf_outlet_tss_mg_l=cf_outlet_tss,
            dhc_g_element_override=cart_dhc_override,
        )
        cart_optim = cartridge_optimise(
            design_flow_m3h=cart_flow,
            rating_um=cart_rating,
            mu_cP=_cart_mu_cP,
            is_CIP_system=cart_cip,
        )

        # ── Hydraulic profile & energy ────────────────────────────────────────────
        hyd_prof = hydraulic_profile(
            dp_media_clean_bar  = bw_dp["dp_clean_bar"],
            dp_media_dirty_bar  = bw_dp["dp_dirty_bar"],
            np_dp_filt_bar      = np_slot_dp,
            distributor_dp_bar  = dp_dist,
            dp_inlet_pipe_bar   = dp_inlet_pipe,
            dp_outlet_pipe_bar  = dp_outlet_pipe,
            p_residual_bar      = p_residual,
            static_head_m       = static_head,
            rho_feed_kg_m3      = rho_feed,
        )

        _n_feas = feasibility_matrix.get("N", {}).get(
            f"Design ({feed_temp:.0f}°C)", {}).get(
            f"Avg ({tss_avg:.0f} mg/L)", {})
        _bw_per_day_design = _n_feas.get("bw_per_day", 24.0 / (bw_total_min/60.0 + 1.0))
        _avail_design      = _n_feas.get("avail_pct",  90.0)
        _n_total_filters   = streams * n_filters

        _pump_evt_h, _blower_evt_h = bw_equipment_hours_per_event(
            bw_seq.get("steps"),
            fallback_total_h=_bw_dur_h,
        )

        energy = energy_summary(
            q_filter_m3h        = q_per_filter,
            n_filters_total     = _n_total_filters,
            filt_head_dirty_mwc = hyd_prof["dirty"]["total_mwc"],
            filt_head_clean_mwc = hyd_prof["clean"]["total_mwc"],
            pump_eta            = pump_eta,
            motor_eta           = motor_eta,
            rho_feed_kg_m3      = rho_feed,
            q_bw_m3h            = bw_hyd["q_bw_design_m3h"],
            bw_head_mwc         = bw_head_mwc,
            bw_pump_eta         = bw_pump_eta,
            bw_motor_eta        = motor_eta,
            rho_bw_kg_m3        = rho_bw,
            p_blower_kw         = bw_hyd["p_blower_est_kw"],
            blower_motor_eta    = motor_eta,
            bw_duration_h       = _bw_dur_h,
            bw_pump_hours_per_event_h=_pump_evt_h,
            blower_hours_per_event_h=_blower_evt_h,
            bw_per_day_design   = _bw_per_day_design,
            availability_pct    = _avail_design,
            elec_tariff_usd_kwh = elec_tariff,
            op_hours_per_year   = float(op_hours_yr),
        )

        # ── BW system equipment sizing ────────────────────────────────────────────
        _n_bw_systems = _n_feas.get("bw_trains", 1)
        bw_sizing = bw_system_sizing(
            q_bw_design_m3h     = bw_hyd["q_bw_design_m3h"],
            bw_head_mwc         = bw_head_mwc,
            bw_pump_eta         = bw_pump_eta,
            motor_eta           = motor_eta,
            q_air_design_m3h    = bw_hyd["q_air_design_m3h"],
            vessel_pressure_bar = vessel_pressure_bar,
            filter_id_m         = real_id,
            blower_inlet_temp_c = blower_inlet_temp_c,
            blower_eta          = blower_eta,
            bw_vol_per_cycle_m3 = bw_seq["total_vol_avg_m3"],
            n_bw_systems        = _n_bw_systems,
            tank_sf             = tank_sf,
            rho_bw_kg_m3        = rho_bw,
            blower_air_delta_p_bar=blower_air_delta_p_bar,
            q_air_design_nm3h=float(bw_hyd["q_air_design_nm3h"]),
        )
        bw_sizing = {**bw_sizing, "q_air_design_nm3h": bw_hyd["q_air_design_nm3h"]}

        # Align annual blower kWh with thermodynamic motor kW (legacy energy_summary input
        # used the 0.5 bar shortcut from backwash_hydraulics).
        _pbm_sz = float(bw_sizing.get("p_blower_motor_kw") or 0.0)
        if _pbm_sz > 0.0:
            _e_b_old = float(energy.get("e_blower_kwh_yr") or 0.0)
            _e_tot_old = float(energy.get("e_total_kwh_yr") or 0.0)
            _bw_ev_yr = float(_bw_per_day_design) * 365.0 * float(_n_total_filters)
            _e_b_new = _pbm_sz * _blower_evt_h * _bw_ev_yr
            _d_e = _e_b_new - _e_b_old
            _tfy = float(energy.get("total_flow_m3_yr") or 0.0)
            _kpm = (_e_tot_old + _d_e) / _tfy if _tfy > 0 else 0.0
            _tariff = float(elec_tariff)
            energy = {
                **energy,
                "p_blower_elec_kw": round(_pbm_sz, 2),
                "e_blower_kwh_yr": round(_e_b_new, 0),
                "e_total_kwh_yr": round(_e_tot_old + _d_e, 0),
                "kwh_per_m3": round(_kpm, 4),
                "cost_usd_yr": round((_e_tot_old + _d_e) * _tariff, 0),
            }

        pump_perf = build_pump_performance_package(
            inputs=_work,
            hyd_prof=hyd_prof,
            energy=energy,
            bw_hyd=bw_hyd,
            bw_seq=bw_seq,
            bw_sizing=bw_sizing,
            q_per_filter=q_per_filter,
            avg_area=avg_area,
            total_flow=total_flow,
            streams=streams,
            n_filters=n_filters,
            hydraulic_assist=hydraulic_assist,
            rho_feed=rho_feed,
            rho_bw=rho_bw,
            pump_eta=pump_eta,
            motor_eta=motor_eta,
            bw_pump_eta=bw_pump_eta,
            bw_head_mwc=bw_head_mwc,
            bw_velocity=bw_velocity,
            bw_cycles_day=float(_bw_per_day_design),
        )

        # ── Consolidated weight ───────────────────────────────────────────────────
        nozzle_wt_total = sum(r.get("Total wt (kg)", 0) for r in nozzle_sched)
        w_body  = wt_body["weight_body_kg"]
        w_np    = wt_np["weight_total_kg"]
        w_sup   = wt_sup["weight_all_supports_kg"]
        w_noz   = nozzle_wt_total
        w_int   = wt_int["weight_internals_kg"]
        w_total = w_body + w_np + w_sup + w_noz + w_int

        # ── Internal surface areas & lining ───────────────────────────────────────
        vessel_areas = internal_surface_areas(
            vessel_id_m          = real_id,
            cyl_len_m            = cyl_len,
            h_dish_m             = h_dish,
            end_type             = end_geometry,
            nozzle_plate_area_m2 = wt_np.get("area_total_m2", 0.0),
        )
        lining_result = lining_cost(
            protection_type      = protection_type,
            areas                = vessel_areas,
            rubber_type          = rubber_type_sel,
            rubber_thickness_mm  = lining_mm if lining_mm > 0 else 4.0,
            rubber_layers        = rubber_layers,
            rubber_cost_m2       = rubber_cost_m2,
            rubber_labor_m2      = rubber_labor_m2,
            epoxy_type           = epoxy_type_sel,
            epoxy_dft_um         = epoxy_dft_um,
            epoxy_coats          = epoxy_coats,
            epoxy_cost_m2        = epoxy_cost_m2,
            epoxy_labor_m2       = epoxy_labor_m2,
            ceramic_type         = ceramic_type_sel,
            ceramic_dft_um       = ceramic_dft_um,
            ceramic_coats        = ceramic_coats,
            ceramic_cost_m2      = ceramic_cost_m2,
            ceramic_labor_m2     = ceramic_labor_m2,
        )

        wt_oper = operating_weight(
            layers          = layers,
            avg_area_m2     = avg_area,
            vessel_id_m     = real_id,
            cyl_len_m       = cyl_len,
            h_dish_m        = h_dish,
            end_type        = end_geometry,
            w_empty_kg      = w_total,
            n_supports      = wt_sup["n_supports"],
            rho_water_kg_m3 = rho_feed,
            w_lining_kg     = lining_result["weight_kg"],
        )
        wt_saddle = saddle_design(
            total_length_m    = total_length,
            vessel_od_m       = mech["od_m"],
            vessel_id_m       = real_id,
            w_operating_kg    = wt_oper["w_operating_kg"],
            n_saddles         = wt_sup["n_supports"],
            contact_angle_deg = saddle_contact_angle,
        )
        n_s_eff = int(wt_saddle.get("n_saddles_effective", wt_sup["n_supports"]))
        n_s_user = int(wt_sup["n_supports"])
        if "Saddle" in str(support_type) and n_s_eff != n_s_user:
            wt_sup = saddle_weight(
                vessel_od_m=mech["od_m"],
                support_type=support_type,
                saddle_height_m=saddle_h,
                leg_height_m=leg_h,
                leg_section_mm=leg_section,
                base_plate_thickness_mm=base_plate_t,
                gusset_thickness_mm=gusset_t,
                density_kg_m3=steel_density,
                n_supports_override=n_s_eff,
            )
            w_sup = wt_sup["weight_all_supports_kg"]
            w_total = w_body + w_np + w_sup + w_noz + w_int
            wt_oper = operating_weight(
                layers=layers,
                avg_area_m2=avg_area,
                vessel_id_m=real_id,
                cyl_len_m=cyl_len,
                h_dish_m=h_dish,
                end_type=end_geometry,
                w_empty_kg=w_total,
                n_supports=n_s_eff,
                rho_water_kg_m3=rho_feed,
                w_lining_kg=lining_result["weight_kg"],
            )
            wt_saddle = saddle_design(
                total_length_m=total_length,
                vessel_od_m=mech["od_m"],
                vessel_id_m=real_id,
                w_operating_kg=wt_oper["w_operating_kg"],
                n_saddles=n_s_eff,
                contact_angle_deg=saddle_contact_angle,
            )

        _mh_n = max(0, int(n_manholes))
        _mh_rec = max(1, min(6, int(_math.ceil(float(cyl_len) / 7.5))))
        manhole_layout = {
            "n_user": _mh_n,
            "n_recommended": _mh_rec,
            "cyl_len_m": round(float(cyl_len), 4),
            "positions_shell_m": [
                round(float(cyl_len) * (i + 1) / (_mh_n + 1), 3)
                for i in range(_mh_n)
            ],
        }

        # ── Economics ─────────────────────────────────────────────────────────────
        _n_total_vessels = streams * n_filters
        _media_inventory: dict = {}
        _media_usd_kg:   dict = {}
        _media_co2_kg:   dict = {}
        for _b in base:
            _mt  = _b["Type"]
            _mkg = _b["Vol"] * _b["rho_p_eff"] * _n_total_vessels
            _media_inventory[_mt] = _media_inventory.get(_mt, 0.0) + _mkg
            _is_grav = "Gravel" in _mt
            _is_anth = "Anthracite" in _mt
            _media_usd_kg[_mt] = (econ_media_gravel if _is_grav
                                  else econ_media_anthracite if _is_anth
                                  else econ_media_sand) / 1000.0
            _media_co2_kg[_mt] = media_co2_by_type.get(_mt, 0.05)

        econ_capex = capex_breakdown(
            weight_total_kg     = w_total,
            n_vessels           = _n_total_vessels,
            steel_cost_usd_kg   = steel_cost_usd_kg,
            erection_usd        = erection_usd_vessel,
            piping_usd          = piping_usd_vessel,
            instrumentation_usd = instrumentation_usd_vessel,
            civil_usd           = civil_usd_vessel,
            engineering_pct     = engineering_pct,
            contingency_pct     = contingency_pct,
        )
        econ_opex = opex_annual(
            filtration_power_kw        = energy["p_filt_avg_kw"],
            bw_power_kw                = energy["p_bw_kw"],
            blower_power_kw            = energy["p_blower_elec_kw"],
            n_vessels                  = _n_total_vessels,
            electricity_tariff         = elec_tariff,
            operating_hours            = float(op_hours_yr),
            media_inventory_kg_by_type = _media_inventory,
            media_costs_by_type        = _media_usd_kg,
            media_interval_years       = media_replace_years,
            n_strainer_nozzles         = wt_np.get("n_bores", 0) * _n_total_vessels,
            nozzle_cost_usd            = nozzle_unit_cost,
            nozzle_interval_years      = nozzle_replace_years,
            labour_usd_per_filter_year = labour_usd_filter_yr,
            n_filters_total            = _n_total_vessels,
            chemical_cost_usd_m3       = chemical_cost_m3,
            total_flow_m3h             = total_flow,
            energy_kwh_yr_by_component={
                "filtration": float(energy["e_filt_kwh_yr"]),
                "bw_pump": float(energy["e_bw_pump_kwh_yr"]),
                "blower": float(energy["e_blower_kwh_yr"]),
            },
        )
        econ_carbon = carbon_footprint(
            filtration_power_kw   = energy["p_filt_avg_kw"],
            bw_power_kw           = energy["p_bw_kw"],
            blower_power_kw       = energy["p_blower_elec_kw"],
            operating_hours       = float(op_hours_yr),
            grid_intensity_kg_kwh = grid_intensity,
            weight_steel_kg       = w_total * _n_total_vessels,
            steel_carbon_kg_kg    = steel_carbon_kg,
            weight_concrete_kg    = 0.0,
            concrete_carbon_kg_kg = concrete_carbon_kg,
            media_mass_by_type_kg = _media_inventory,
            media_carbon_by_type  = _media_co2_kg,
            design_life_years     = int(design_life_years),
            total_flow_m3h        = total_flow,
            energy_kwh_yr_by_component={
                "filtration": float(energy["e_filt_kwh_yr"]),
                "bw_pump": float(energy["e_bw_pump_kwh_yr"]),
                "blower": float(energy["e_blower_kwh_yr"]),
            },
        )
        econ_bench = global_benchmark_comparison(
            capex_total_usd   = econ_capex["total_capex_usd"],
            opex_usd_year     = econ_opex["total_opex_usd_yr"],
            total_flow_m3h    = total_flow,
            n_filters         = _n_total_vessels,
            design_life_years = int(design_life_years),
            co2_per_m3         = econ_carbon["co2_per_m3_operational"],
            electricity_tariff = elec_tariff,
            operating_hours    = float(op_hours_yr),
            discount_rate_pct  = float(discount_rate),
        )
        econ_npv = npv_lifecycle_cost_profile(
            capex_total_usd   = float(econ_capex["total_capex_usd"]),
            annual_opex_usd   = float(econ_opex["total_opex_usd_yr"]),
            discount_rate_pct = float(discount_rate),
            design_life_years = int(design_life_years),
        )
        econ_financial = build_econ_financial(
            inputs=_work,
            econ_capex=econ_capex,
            econ_opex=econ_opex,
            econ_carbon=econ_carbon,
            econ_bench=econ_bench,
            lining_result=lining_result,
            n_vessels=_n_total_vessels,
        )

        # ── Assessment pre-computation ────────────────────────────────────────────
        load_data = _load_data_cyc

        all_lv_issues   = []
        all_ebct_issues = []
        n_criticals  = 0
        n_warnings   = 0
        n_advisories = 0

        for _x, _a, _q in load_data:
            _sc = "N" if _x == 0 else f"N-{_x}"
            for _b in base:
                if _b.get("is_support"):
                    continue
                _vel  = _q / _b["Area"] if _b["Area"] > 0 else 0
                _ebct = (_b["Vol"] / _q) * 60 if _q > 0 else 0
                _lv_cap = layer_lv_cap_m_h(_b, inputs_fallback=_work)
                _eb_floor = layer_ebct_floor_min(_b, inputs_fallback=_work)
                _lv_sev = lv_severity_classify(_vel, _lv_cap)
                _eb_sev = ebct_severity_classify(_ebct, _eb_floor)
                if _lv_sev:
                    all_lv_issues.append((_sc, _b["Type"], _lv_sev, _vel))
                    if _lv_sev == "critical":   n_criticals  += 1
                    elif _lv_sev == "warning":  n_warnings   += 1
                    else:                        n_advisories += 1
                if _eb_sev:
                    all_ebct_issues.append((_sc, _b["Type"], _eb_sev, _ebct))
                    if _eb_sev == "critical":   n_criticals  += 1
                    elif _eb_sev == "warning":  n_warnings   += 1
                    else:                        n_advisories += 1

        _n_scen_crit = sum(1 for s, _, sv, __ in (all_lv_issues + all_ebct_issues)
                           if sv == "critical" and s == "N")
        _n_scen_warn = sum(1 for s, _, sv, __ in (all_lv_issues + all_ebct_issues)
                           if sv == "warning"  and s == "N")

        if n_criticals == 0 and n_warnings == 0 and n_advisories <= 1:
            overall_risk = "STABLE";   risk_color = "#0a2a0a"; risk_border = "#1a7a1a"; risk_icon = "🟢"
        elif _n_scen_crit > 1 or (n_criticals > 0 and n_warnings > 2):
            overall_risk = "CRITICAL"; risk_color = "#2a0000"; risk_border = "#cc0000"; risk_icon = "🔴"
        elif _n_scen_crit > 0 or n_warnings >= 3:
            overall_risk = "ELEVATED"; risk_color = "#2a1200"; risk_border = "#cc5500"; risk_icon = "🟠"
        elif _n_scen_warn > 0 or n_criticals > 0:
            overall_risk = "MARGINAL"; risk_color = "#2a2000"; risk_border = "#b8860b"; risk_icon = "🟡"
        else:
            overall_risk = "STABLE";   risk_color = "#0a2a0a"; risk_border = "#1a7a1a"; risk_icon = "🟢"

        drivers = []
        if all_lv_issues:
            _worst_lv = max(all_lv_issues, key=lambda t: t[3])
            drivers.append(
                f"Filtration velocity reaches {_worst_lv[3]:.2f} m/h "
                f"(layer {_worst_lv[1]} max LV setpoint exceeded vs design) "
                f"in scenario {_worst_lv[0]}."
            )
        if all_ebct_issues:
            _worst_eb = min(all_ebct_issues, key=lambda t: t[3])
            drivers.append(
                f"Contact time reduces to {_worst_eb[3]:.2f} min "
                f"(below min EBCT setpoint for layer {_worst_eb[1]}) "
                f"in scenario {_worst_eb[0]}."
            )
        if not drivers:
            drivers.append("All hydraulic parameters remain within the recommended operating envelope across all evaluated scenarios.")

        impacts = {
            "STABLE":   ["Filter performance expected to be consistent across the full redundancy range.",
                         "Particulate capture efficiency maintains design margin under peak loading.",
                         "No hydraulic adjustments indicated at current configuration."],
            "MARGINAL": ["Performance remains acceptable under normal N-scenario operation.",
                         "One or more standby scenarios approach the hydraulic envelope boundary — review BW cycle frequency.",
                         "Minor adjustments to filter area or media depth may improve N-1 resilience."],
            "ELEVATED": ["Elevated velocity or reduced contact time may compromise particulate capture under peak hydraulic loading.",
                         "Run time between backwash cycles likely shortened by 15–30 % compared to design basis.",
                         "Consider increasing number of operating filters or filter area to restore operating margin."],
            "CRITICAL": ["Hydraulic loading significantly exceeds the recommended operating envelope.",
                         "Risk of particulate breakthrough and accelerated media fouling under sustained operation.",
                         "System redesign recommended — increase filter area, add filter units, or reduce total flow per vessel."],
        }
        recommendations = {
            "STABLE":   "Maintain current configuration. Review again if flow demand increases or media condition degrades.",
            "MARGINAL": "Review N-1 scenario performance with the client and confirm acceptance of reduced margin during filter outage.",
            "ELEVATED": "Increase filter area or reduce per-filter hydraulic loading. Adding one filter unit per stream typically resolves elevated ratings.",
            "CRITICAL": "Redesign required. The current number of filters or vessel area is insufficient for the specified flow. Consult process design basis before proceeding.",
        }

        # Robustness index rows
        rob_rows = []
        _all_scenarios = [("N", 0)] + [(f"N-{i}", i) for i in range(1, redundancy + 1)]
        _eval_set = {("N" if x == 0 else f"N-{x}"): q for x, _, q in load_data}

        def _sev_to_label(s):
            return ("Within envelope" if s is None
                    else "Approaching limit" if s == "advisory"
                    else "Outside envelope")

        for _sc_name, _xr in _all_scenarios:
            if _sc_name not in _eval_set:
                rob_rows.append({"Scenario": _sc_name, "Filtration rate": "—",
                                 "Hydraulic status": "Not evaluated",
                                 "EBCT status": "Not evaluated", "Overall": "Not evaluated"})
                continue
            _q = _eval_set[_sc_name]
            _lv_n = _q / avg_area if avg_area > 0 else 0
            _worst_lv_sev = None
            _worst_eb_sev = None
            _sev_rank = {"critical": 3, "warning": 2, "advisory": 1, None: 0}
            for _b in base:
                if _b.get("is_support"):
                    continue
                _v = _q / _b["Area"] if _b["Area"] > 0 else 0
                _e = (_b["Vol"] / _q) * 60 if _q > 0 else 0
                _lv_cap = layer_lv_cap_m_h(_b, inputs_fallback=_work)
                _eb_floor = layer_ebct_floor_min(_b, inputs_fallback=_work)
                _sv = lv_severity_classify(_v, _lv_cap)
                _se = ebct_severity_classify(_e, _eb_floor)
                if _sev_rank.get(_sv, 0) > _sev_rank.get(_worst_lv_sev, 0): _worst_lv_sev = _sv
                if _sev_rank.get(_se, 0) > _sev_rank.get(_worst_eb_sev, 0): _worst_eb_sev = _se
            _lv_label = _sev_to_label(_worst_lv_sev)
            _eb_label = _sev_to_label(_worst_eb_sev)
            _worst_overall = max(_worst_lv_sev or "", _worst_eb_sev or "",
                                 key=lambda s: {"critical": 3, "warning": 2, "advisory": 1, "": 0}.get(s, 0))
            _overall_label = ("Stable"   if not _worst_overall
                              else "Marginal"  if _worst_overall == "advisory"
                              else "Sensitive" if _worst_overall == "warning"
                              else "Critical")
            rob_rows.append({"Scenario": _sc_name, "Filtration rate": f"{_lv_n:.2f} m/h",
                             "Hydraulic status": _lv_label, "EBCT status": _eb_label,
                             "Overall": _overall_label})

        env_structural = compute_environment_structural(_work)

        # ── Return dict ───────────────────────────────────────────────────────────
        return {
            # water
            "feed_wp": feed_wp, "bw_wp": bw_wp,
            "rho_feed": rho_feed, "mu_feed": mu_feed, "rho_bw": rho_bw, "mu_bw": mu_bw,
            # severity functions (tabs need them as callables)
            "lv_severity_fn": lv_severity_classify,
            "ebct_severity_fn": ebct_severity_classify,
            # geometry
            "h_dish": h_dish, "cyl_len": cyl_len, "real_id": real_id,
            "nominal_id": nominal_id, "total_length": total_length,
            "end_geometry": end_geometry, "lining_mm": lining_mm,
            # mechanical
            "mech": mech, "wt_body": wt_body,
            # media
            "geo_rows": geo_rows, "base": base, "avg_area": avg_area,
            "layer_areas_m2": _layer_areas or [],
            "solid_loading_effective_kg_m2": solid_loading_eff,
            "solid_loading_scale": _sl_scale,
            "maldistribution_factor": _mal,
            "alpha_calibration_factor": _acf,
            "tss_capture_efficiency": _tss_cap,
            "expansion_calibration_scale": _exp_scl,
            "q_per_filter": q_per_filter,
            # pressure drop
            "bw_dp": bw_dp, "np_dp_auto": np_dp_auto,
            # nozzle plate & nozzles
            "wt_np": wt_np, "nozzle_sched": nozzle_sched,
            # supports & internals
            "wt_sup": wt_sup, "wt_int": wt_int,
            # backwash
            "bw_hyd": bw_hyd, "bw_col": bw_col, "bw_exp": bw_exp, "bw_seq": bw_seq,
            "air_scour_solve": air_scour_solve,
            "bw_timeline": bw_timeline,
            # TSS balance
            "m_sol_low": m_sol_low, "w_tss_low": w_tss_low, "m_daily_low": m_daily_low,
            "m_sol_avg": m_sol_avg, "w_tss_avg": w_tss_avg, "m_daily_avg": m_daily_avg,
            "m_sol_high": m_sol_high, "w_tss_high": w_tss_high, "m_daily_high": m_daily_high,
            # filtration cycles & matrices
            "filt_cycles": filt_cycles, "load_data": load_data,
            "cycle_matrix": cycle_matrix,
            "tss_col_keys": tss_col_keys, "tss_vals": tss_vals,
            "temp_col_keys": temp_col_keys,
            "feasibility_matrix": feasibility_matrix,
            # cartridge
            "cart_result": cart_result, "cart_optim": cart_optim,
            # hydraulics & energy
            "hyd_prof": hyd_prof, "energy": energy, "pump_perf": pump_perf,
            # BW sizing
            "bw_sizing": bw_sizing, "n_bw_systems": _n_bw_systems,
            # weight
            "w_noz": w_noz, "w_total": w_total,
            # lining & surfaces
            "vessel_areas": vessel_areas, "lining_result": lining_result,
            # operating weight & saddle
            "wt_oper": wt_oper, "wt_saddle": wt_saddle,
            "manhole_layout": manhole_layout,
            # material (pass-through for tabs)
            "material_name": material_name, "mat_info": mat_info,
            # economics
            "econ_capex": econ_capex, "econ_opex": econ_opex,
            "econ_carbon": econ_carbon, "econ_bench": econ_bench,
            "econ_npv": econ_npv,
            "econ_financial": econ_financial,
            # assessment
            "overall_risk": overall_risk, "risk_color": risk_color,
            "risk_border": risk_border, "risk_icon": risk_icon,
            "drivers": drivers, "impacts": impacts, "recommendations": recommendations,
            "n_criticals": n_criticals, "n_warnings": n_warnings, "n_advisories": n_advisories,
            "all_lv_issues": all_lv_issues, "all_ebct_issues": all_ebct_issues,
            "rob_rows": rob_rows,
            "input_validation": input_validation,
            "compute_used_reference_fallback": (not input_validation["valid"]),
            "env_structural": env_structural,
        }
