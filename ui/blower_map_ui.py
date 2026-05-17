"""Pumps & power — blower map vs adiabatic comparison."""
from __future__ import annotations

import streamlit as st

from engine.blower_maps import (
    LOBE_Q_MAX_NM3H,
    DEFAULT_BLOWER_CURVE_ID,
    ROOTS_LOBE_CURVE_ID,
    blowers_energy_online_count,
    blowers_on_duty_from_inputs,
    build_blower_map_analysis,
    import_custom_curve_from_csv,
    list_blower_curves,
    pick_curve_id,
)
from ui.helpers import fmt, ulbl

_FLAG_LABELS = {
    "map_extrapolated": "Map value **extrapolated** beyond tabulated grid (not clamped).",
    "extrapolated_q_above_grid": "Flow above catalog Q max — extrapolated.",
    "extrapolated_q_below_grid": "Flow below catalog Q min — extrapolated.",
    "extrapolated_dp_above_grid": "ΔP above catalog max — extrapolated.",
    "extrapolated_dp_below_grid": "ΔP below catalog min — extrapolated.",
    "auto_curve_centrifugal": "Auto-selected **centrifugal** map (per-machine Q exceeds lobe max).",
    "large_adiabatic_vs_map_delta": "Map vs adiabatic motor differs by more than 25 %.",
    "vfd_part_load_active": "VFD part-load on centrifugal map.",
    "fleet_duty_split": "Plant air flow split across multiple blowers on duty.",
    "per_machine_q_above_catalog_max": "Per-machine Q still above this curve's catalog maximum.",
}


def _blower_config_from_session(inputs: dict) -> dict:
    """Single source: §3 Hydraulics widgets (installed count + operating mode)."""
    return {
        **inputs,
        "pp_n_blowers": int(st.session_state.get("pp_n_blowers", inputs.get("pp_n_blowers", 1)) or 1),
        "pp_blower_mode": str(
            st.session_state.get("pp_blower_mode", inputs.get("pp_blower_mode", "single_duty"))
        ),
    }


def render_blower_map_panel(inputs: dict, computed: dict) -> None:
    cfg = _blower_config_from_session(inputs)
    n_on = blowers_on_duty_from_inputs(cfg)
    n_installed = max(1, int(cfg.get("pp_n_blowers", 1)))
    blower_mode = str(cfg.get("pp_blower_mode", "single_duty"))

    curves = list_blower_curves()
    ids = [c["id"] for c in curves]
    labels = {c["id"]: f"{c['label']} (Q≤{c.get('q_max_nm3h', 0):,.0f} Nm³/h)" for c in curves}

    bw = computed.get("bw_sizing") or {}
    q_hint = float(bw.get("q_air_design_nm3h") or 0.0)
    q_per_hint = q_hint / n_on if q_hint > 0 else 0.0
    suggested, switched, reason = pick_curve_id(
        q_per_hint,
        str(st.session_state.get("blower_map_curve_sel", cfg.get("blower_curve_id", DEFAULT_BLOWER_CURVE_ID))),
        auto=True,
    )
    default_id = suggested if switched else str(
        st.session_state.get("blower_map_curve_sel", cfg.get("blower_curve_id", ROOTS_LOBE_CURVE_ID))
    )
    if default_id not in ids:
        default_id = ids[0]

    with st.expander("4c · Blower performance map vs adiabatic model", expanded=False):
        st.caption(
            "Compare **ideal-gas adiabatic** sizing with a **tabulated map**. "
            f"Lobe catalog to **{LOBE_Q_MAX_NM3H:,.0f} Nm³/h** per machine; centrifugal to **50,000 Nm³/h**. "
            "**Blower count and on-duty split** are set only in **§3 · Hydraulics & plant configuration** "
            "(Air blowers installed + operating mode) — not here."
        )

        st.info(
            f"**{n_installed}** air blower(s) installed → "
            f"Q/machine = Q_plant ÷ **{n_on}** "
            f"(≈ {fmt(q_hint / n_on if q_hint and n_on else 0, 'air_flow_nm3h', 0)} per machine at design)."
        )

        c1, c2 = st.columns(2)
        with c1:
            auto_curve = c1.checkbox(
                "Auto-pick curve from per-machine Q",
                value=bool(st.session_state.get("blower_map_auto_curve", True)),
                key="blower_map_auto_curve",
                help=f"If per-machine Q > **{LOBE_Q_MAX_NM3H:,.0f} Nm³/h**, switch from lobe to centrifugal.",
            )
        with c2:
            speed = c2.slider(
                "VFD speed (fraction of design)",
                min_value=0.25,
                max_value=1.0,
                value=float(cfg.get("blower_vfd_speed_frac", 1.0) or 1.0),
                step=0.05,
                key="blower_map_vfd_speed",
            )

        if switched and reason and auto_curve:
            st.info(reason)

        curve_id = st.selectbox(
            "Blower map",
            options=ids,
            index=ids.index(default_id) if default_id in ids else 0,
            format_func=lambda x: labels.get(x, x),
            key="blower_map_curve_sel",
        )

        merged = {
            **cfg,
            "blower_curve_id": curve_id,
            "blower_vfd_speed_frac": speed,
            "blower_map_auto_curve": auto_curve,
        }

        bm = build_blower_map_analysis(
            merged,
            computed,
            curve_id=curve_id,
            vfd_speed_frac=speed,
        )
        if not bm.get("enabled"):
            st.info(bm.get("note", "Blower map not available."))
            return

        fleet = bm.get("fleet") or {}
        op = bm.get("operating_point") or {}
        cm = bm.get("curve_map") or {}

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Q plant", fmt(fleet.get("q_total_nm3h"), "air_flow_nm3h", 0))
        m2.metric(f"Q / machine ({n_on} on)", fmt(op.get("q_nm3h"), "air_flow_nm3h", 0))
        m3.metric(f"ΔP ({ulbl('pressure_bar')})", fmt(op.get("dp_bar"), "pressure_bar", 3))
        ad = bm.get("adiabatic") or {}
        m4.metric("Adiabatic shaft / machine", fmt(ad.get("shaft_kw_per_machine"), "power_kw", 1))
        map_lbl = "Map motor / machine" if cm.get("power_basis") == "motor" else "Map shaft / machine"
        m5.metric(
            map_lbl,
            fmt(cm.get("motor_kw_per_machine") if cm.get("power_basis") == "motor" else cm.get("shaft_kw"), "power_kw", 1),
        )
        if cm.get("oem_model_hint"):
            st.caption(f"Nearest OEM frame (hint): **{cm.get('oem_model_hint')}**")

        n_kwh = blowers_energy_online_count(cfg)
        kwh_note = (
            f"{n_kwh} blower(s) for annual kWh"
            if blower_mode == "single_duty" and n_installed > 1
            else f"all {n_installed} for annual kWh"
            if blower_mode == "twin_50_iso"
            else f"{n_kwh} for annual kWh"
        )

        fleet_map_shaft = cm.get("shaft_kw_fleet") or (float(cm.get("shaft_kw") or 0) * n_on)
        fleet_ad_shaft = ad.get("shaft_kw_fleet")
        fleet_map_motor = cm.get("motor_kw_fleet")
        fleet_ad_motor = ad.get("motor_kw_fleet")

        if bm.get("comparison_trustworthy"):
            delta_line = (
                f"Per-machine Δ: **{bm.get('delta_map_vs_adiabatic_motor_pct', 0):+.1f} %** (motor) · "
                f"Fleet Δ: **{bm.get('delta_map_vs_adiabatic_fleet_pct', 0):+.1f} %**"
            )
        else:
            delta_line = (
                "**Δ% not shown** — generic screening map diverges from adiabatic "
                "(extrapolation or catalog mismatch; use vendor data)."
            )

        st.caption(
            f"{delta_line} · "
            f"**Fleet shaft (×{n_on}):** map **{fmt(fleet_map_shaft, 'power_kw', 1)}** vs adiabatic "
            f"**{fmt(fleet_ad_shaft, 'power_kw', 1)}** · "
            f"**Fleet motor:** map **{fmt(fleet_map_motor, 'power_kw', 1)}** vs adiabatic "
            f"**{fmt(fleet_ad_motor, 'power_kw', 1)}** · "
            f"VFD @ {speed:.0%}/machine: **{fmt(bm['vfd'].get('motor_kw_per_machine'), 'power_kw', 1)}** · "
            f"**{n_installed} installed** · {kwh_note}"
        )

        for fl in bm.get("advisory_flags") or []:
            msg = _FLAG_LABELS.get(fl, fl.replace("_", " "))
            if fl.startswith("extrapolated") or fl == "map_extrapolated":
                st.warning(msg)
            elif fl == "auto_curve_centrifugal":
                st.info(msg)
            else:
                st.warning(msg)

        if cm.get("extrapolated"):
            st.caption(
                "Values beyond the grid use **linear extrapolation** from the nearest edge — screening only."
            )
        elif not cm.get("in_envelope"):
            st.info("Operating point outside envelope.")

        try:
            import plotly.graph_objects as go

            plot_pts = bm.get("curve_plot") or []
            pts = bm.get("chart_points") or {}
            pm = pts.get("per_machine") or {}
            fl = pts.get("fleet_on_duty") or {}
            if plot_pts:
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=[p["q_nm3h"] for p in plot_pts],
                        y=[p["shaft_kw"] for p in plot_pts],
                        mode="lines",
                        name=f"Map @ {op.get('dp_bar', 0):.2f} bar (per machine)",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=[pm.get("q_nm3h", op.get("q_nm3h"))],
                        y=[pm.get("map_shaft_kw", cm.get("shaft_kw"))],
                        mode="markers",
                        marker=dict(size=12, color="#2563eb"),
                        name=f"Map shaft / machine (n={n_on})",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=[pm.get("q_nm3h", op.get("q_nm3h"))],
                        y=[pm.get("adiabatic_shaft_kw", ad.get("shaft_kw_per_machine"))],
                        mode="markers",
                        marker=dict(size=10, color="#cc5500", symbol="diamond"),
                        name="Adiabatic shaft / machine",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=[fl.get("q_nm3h", fleet.get("q_total_nm3h"))],
                        y=[fl.get("map_shaft_kw", cm.get("shaft_kw_fleet"))],
                        mode="markers",
                        marker=dict(size=13, color="#1d4ed8", symbol="square"),
                        name=f"Map shaft fleet ({n_on} on duty)",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=[fl.get("q_nm3h", fleet.get("q_total_nm3h"))],
                        y=[fl.get("adiabatic_shaft_kw", ad.get("shaft_kw_fleet"))],
                        mode="markers",
                        marker=dict(size=11, color="#ea580c", symbol="star"),
                        name=f"Adiabatic shaft fleet ({n_on} on duty)",
                    )
                )
                fig.update_layout(
                    title=f"Blower map — {bm.get('curve_label', '')}",
                    xaxis_title=ulbl("air_flow_nm3h"),
                    yaxis_title=ulbl("power_kw"),
                    height=420,
                    margin=dict(t=48, b=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig, use_container_width=True, key="blower_map_curve_chart")
        except ImportError:
            st.info("Install **plotly** for blower map chart.")

        with st.expander("Import vendor map (CSV)", expanded=False):
            st.markdown(
                "**CSV format (per blower)** — Header example: "
                "`q_nm3h,0.30,0.45,0.60` "
                "(column 1 = flow label; columns 2+ = **ΔP in bar**). "
                "Each data row: **Nm³/h per machine**, then **shaft kW** at each ΔP. "
                "Use vendor **per-blower** duty points — plant total Q is split using "
                "**§3** installed count and operating mode."
            )
            st.code(
                "# q_nm3h = per-blower flow; headers after col 1 = delta_P (bar)\n"
                "q_nm3h,0.30,0.45,0.60\n"
                "3000,120,165,210\n"
                "6000,220,300,385\n"
                "9000,310,425,540\n",
                language="csv",
            )
            v_id = st.text_input("Curve id (slug)", value="vendor_custom", key="blower_csv_curve_id")
            v_label = st.text_input("Display label", value="Vendor custom map", key="blower_csv_label")
            v_type = st.selectbox(
                "Blower type",
                ["positive_displacement", "centrifugal"],
                key="blower_csv_btype",
            )
            v_aff = st.number_input(
                "VFD affinity exponent",
                min_value=0.5,
                max_value=3.0,
                value=1.0 if v_type == "positive_displacement" else 3.0,
                step=0.1,
                key="blower_csv_aff",
            )
            csv_text = st.text_area("Paste CSV", height=120, key="blower_csv_paste")
            uploaded = st.file_uploader("Or upload .csv", type=["csv"], key="blower_csv_file")
            if uploaded is not None:
                csv_text = uploaded.read().decode("utf-8", errors="replace")

            if st.button("Register vendor curve", key="blower_csv_import_btn"):
                try:
                    import_custom_curve_from_csv(
                        v_id.strip(),
                        v_label.strip(),
                        csv_text,
                        blower_type=v_type,
                        affinity_exponent=float(v_aff),
                    )
                    st.success(f"Registered **{v_id}** — re-open this expander to select it.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
