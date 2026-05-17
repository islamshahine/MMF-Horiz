"""ui/tab_pump_costing.py — Pumps & power: hydraulics, equipment, energy bridge, budgetary CAPEX."""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from engine.pump_datasheet_export import (
    DOCX_OK,
    PDF_OK,
    build_air_blower_datasheet_bundle,
    build_datasheet_export,
    build_pump_datasheet_bundle,
    list_datasheet_export_choices,
)
from engine.pump_performance import (
    _philosophy_capex_bundle,
    apply_cost_multipliers,
    build_pump_performance_package,
    economics_energy_from_pump_configuration,
    feed_bank_iec_motor_kw_each,
    plant_filtration_motor_kw_parallel_feed,
)
from ui.helpers import fmt, ulbl
from engine.units import display_value, format_value, si_value, unit_label
from ui.bw_equipment_datasheet import render_bw_system_equipment_datasheet
from ui.feed_pump_context_inputs import render_hydraulics_and_efficiency_columns
from ui.scroll_markers import inject_anchor

try:
    import plotly.graph_objects as go
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False


def _ab_session_to_si(key: str, default_si: float, quantity: str, unit_system: str) -> float:
    """Blower RFQ widgets store display units when imperial; datasheet / bundle use SI."""
    raw = st.session_state.get(key)
    if raw is None:
        return float(default_si)
    return float(si_value(float(raw), quantity, unit_system))


def _bl_detail_cell(val: Any, quantity: str | None, decimals: int) -> str:
    if val is None or val == "—":
        return "—"
    try:
        fv = float(val)
    except (TypeError, ValueError):
        return str(val)
    if quantity is None:
        return f"{fv:.{decimals}f}"
    return fmt(fv, quantity, decimals)


def _render_datasheet_export_row(
    *,
    bundle: dict[str, Any],
    equipment: str,
    slug: str,
    select_key: str,
    download_key: str,
) -> None:
    """Format selectbox + single download button for pump / blower RFQ exports."""
    choices = list_datasheet_export_choices()
    labels = [lb for _, lb in choices]
    id_by_label = {lb: cid for cid, lb in choices}
    c_fmt, c_dl = st.columns([4, 1])
    with c_fmt:
        picked = st.selectbox(
            "Export format",
            labels,
            key=select_key,
        )
    with c_dl:
        data, fname, mime = build_datasheet_export(
            bundle,
            id_by_label[picked],
            equipment=equipment,
            slug=slug,
        )
        st.download_button(
            "Download",
            data=data,
            file_name=fname,
            mime=mime,
            key=download_key,
            use_container_width=True,
        )
    if not DOCX_OK or not PDF_OK:
        _missing = []
        if not DOCX_OK:
            _missing.append("**python-docx** (`pip install python-docx`) for Word")
        if not PDF_OK:
            _missing.append("**reportlab** (`pip install reportlab`) for PDF")
        st.caption("Optional: " + " · ".join(_missing) + ".")


def _migrate_pump_econ_align_key() -> None:
    """Legacy alignment checkbox was on Economics; canonical session key lives here."""
    if "pp_align_econ_energy" not in st.session_state and "econ_align_pump_tab_energy" in st.session_state:
        st.session_state["pp_align_econ_energy"] = bool(
            st.session_state["econ_align_pump_tab_energy"]
        )


def _fallback_package(inputs: dict, computed: dict) -> dict[str, Any]:
    """If compute did not attach pump_perf (older projects), build on the fly."""
    return build_pump_performance_package(
        inputs=inputs,
        hyd_prof=computed["hyd_prof"],
        energy=computed.get("energy") or {},
        bw_hyd=computed["bw_hyd"],
        bw_seq=computed["bw_seq"],
        bw_sizing=computed.get("bw_sizing") or {},
        q_per_filter=float(computed.get("q_per_filter") or 0.0),
        avg_area=float(computed.get("avg_area") or 0.0),
        total_flow=float(inputs.get("total_flow") or 0.0),
        streams=int(inputs.get("streams") or 1),
        n_filters=int(inputs.get("n_filters") or 1),
        hydraulic_assist=int(inputs.get("hydraulic_assist") or 0),
        rho_feed=float(computed.get("rho_feed") or 1025.0),
        rho_bw=float(computed.get("rho_bw") or 1025.0),
        pump_eta=float(inputs.get("pump_eta") or 0.75),
        motor_eta=float(inputs.get("motor_eta") or 0.955),
        bw_pump_eta=float(inputs.get("bw_pump_eta") or 0.72),
        bw_head_mwc=float(inputs.get("bw_head_mwc") or 15.0),
        bw_velocity=float(inputs.get("bw_velocity") or 30.0),
        bw_cycles_day=float(
            (computed.get("energy") or {}).get("bw_per_day_design")
            or inputs.get("bw_cycles_day")
            or 1.0
        ),
    )


_FEED_ORIENT_OPTS = ("Horizontal", "Vertical dry-installed")
_FEED_STD_OPTS = ("Commercial", "ISO 5199", "API 610 OH2")
_FEED_MAT_OPTS = ("Cast iron", "Carbon steel", "SS316", "Duplex", "Super duplex")
_FEED_SEAL_OPTS = ("Packing", "Single mechanical seal", "Dual seal / API Plan 53")

BLOWER_MODE_LABELS: dict[str, str] = {
    "single_duty": "Annual kWh: 1 × duty online (spares idle)",
    "twin_50_iso": "Annual kWh: all installed online — equal flow split (rough Q³)",
}


def _pp_widget_str(key: str, options: tuple[str, ...], default: str) -> str:
    v = st.session_state.get(key)
    return str(v) if v in options else default


def _pp_widget_bool(key: str, default: bool) -> bool:
    if key not in st.session_state:
        return default
    return bool(st.session_state[key])


def _pump_screening_capex_bundle(
    *,
    pp: dict[str, Any],
    auto: dict[str, Any],
    motor_eta: float,
    pump_eta_cap: float,
    n_feed_parallel_per_stream: int,
    n_bw_dol_trains: int,
    n_bw_vfd_trains: int,
    n_blower_units: int,
    feed_orient: str,
    feed_pump_standard: str,
    feed_material: str,
    feed_seal: str,
    feed_use_vfd: bool,
    bw_orient: str,
    bw_pump_standard: str,
    bw_material: str,
    bw_seal: str,
    bw_vfd_allowance: bool,
) -> dict[str, Any]:
    """Same screening CAPEX as **6 · Budgetary equipment costing** (skid-level USD, ±25 % model)."""
    bw0 = pp["bw_pump"]
    bl = pp["blower"]
    streams = max(1, int(auto["streams"]))
    total_flow = float(auto["total_flow_m3h"])
    q_stream = total_flow / streams
    n_par = max(1, int(n_feed_parallel_per_stream))
    n_feed_total = streams * n_par
    iec_each = feed_bank_iec_motor_kw_each(
        q_stream_m3h=q_stream,
        n_parallel_pumps=n_par,
        head_mwc=float(auto["head_dirty_mwc"]),
        rho_kg_m3=float(auto["rho_feed_kg_m3"]),
        motor_eta=motor_eta,
        pump_eta_user_cap=pump_eta_cap,
    )
    feed_mult = apply_cost_multipliers(
        material=feed_material,
        pump_standard=feed_pump_standard,
        seal=feed_seal,
        use_vfd=feed_use_vfd,
        vertical=feed_orient.startswith("Vertical"),
    )
    feed_cpx = feed_mult["material"] * feed_mult["standard"] * feed_mult["seal"] * feed_mult["vertical"]
    feed_vfd_m = float(feed_mult["vfd"])
    bw_mult = apply_cost_multipliers(
        material=bw_material,
        pump_standard=bw_pump_standard,
        seal=bw_seal,
        use_vfd=False,
        vertical=bw_orient.startswith("Vertical"),
    )
    bw_cpx = bw_mult["material"] * bw_mult["standard"] * bw_mult["seal"] * bw_mult["vertical"]
    bw_vfd_train_m = 1.35 * (1.0 if bw_vfd_allowance else 1.0)
    return _philosophy_capex_bundle(
        bw_motor_iec_kw_dol_train=float(bw0["motor_iec_kw_dol_half"]),
        bw_motor_iec_kw_vfd_train=float(bw0["motor_iec_kw_vfd_full"]),
        blower_motor_kw=float(bl["p_motor_kw"]),
        feed_motor_kw_each=float(iec_each),
        n_feed_pumps_total=n_feed_total,
        n_bw_dol_trains=n_bw_dol_trains,
        n_bw_vfd_trains=n_bw_vfd_trains,
        n_blower_units=n_blower_units,
        feed_complex_mult=feed_cpx,
        feed_vfd_budget_mult=feed_vfd_m,
        bw_complex_mult=bw_cpx,
        bw_vfd_train_budget_mult=bw_vfd_train_m,
    )


def _pump_screening_capex_from_session(
    pp: dict[str, Any],
    auto: dict[str, Any],
    motor_eta: float,
    pump_eta_cap: float,
    n_feed_parallel_per_stream: int,
    n_bw_dol_trains: int,
    n_bw_vfd_trains: int,
    n_blower_units: int,
) -> dict[str, Any]:
    return _pump_screening_capex_bundle(
        pp=pp,
        auto=auto,
        motor_eta=motor_eta,
        pump_eta_cap=pump_eta_cap,
        n_feed_parallel_per_stream=n_feed_parallel_per_stream,
        n_bw_dol_trains=n_bw_dol_trains,
        n_bw_vfd_trains=n_bw_vfd_trains,
        n_blower_units=n_blower_units,
        feed_orient=_pp_widget_str("pp_feed_orient", _FEED_ORIENT_OPTS, "Horizontal"),
        feed_pump_standard=_pp_widget_str("pp_feed_std", _FEED_STD_OPTS, "ISO 5199"),
        feed_material=_pp_widget_str("pp_feed_mat", _FEED_MAT_OPTS, "SS316"),
        feed_seal=_pp_widget_str("pp_feed_seal", _FEED_SEAL_OPTS, "Single mechanical seal"),
        feed_use_vfd=_pp_widget_bool("pp_feed_vfd", False),
        bw_orient=_pp_widget_str("pp_bw_orient", _FEED_ORIENT_OPTS, "Horizontal"),
        bw_pump_standard=_pp_widget_str("pp_bw_std", _FEED_STD_OPTS, "ISO 5199"),
        bw_material=_pp_widget_str("pp_bw_mat", _FEED_MAT_OPTS, "SS316"),
        bw_seal=_pp_widget_str("pp_bw_seal", _FEED_SEAL_OPTS, "Single mechanical seal"),
        bw_vfd_allowance=_pp_widget_bool("pp_bw_vfd_allow", True),
    )


def render_tab_pump_costing(inputs: dict, computed: dict):
    inject_anchor("mmf-anchor-main-pumps")
    st.subheader("Pumps & power")
    _us = str(inputs.get("unit_system") or "metric")
    st.caption(
        "Dry-installed centrifugal pumps and air blowers only — **no** submersible, deep-well, "
        "or vertical wet-pit turbine models. **Hydraulics, η, train counts, and Economics linkage** are grouped first; "
        "then equipment choices, energy summary, budgetary CAPEX, and export. Power follows the BW sequence from **Backwash**."
    )

    motor_eta_run = float(inputs.get("motor_eta") or 0.955)
    pump_eta_run = float(inputs.get("pump_eta") or 0.75)
    bw_pump_eta_run = float(inputs.get("bw_pump_eta") or 0.72)

    pp = computed.get("pump_perf")
    if not pp:
        pp = _fallback_package(inputs, computed)

    auto = pp["auto"]
    feed0 = pp["feed_pump"]
    bw0 = pp["bw_pump"]
    bl = pp["blower"]
    phil = pp["philosophy"]
    eb = pp["energy_bridge"]
    capex_bl = pp.get("capex_baseline_usd") or {}
    bl_detail = (bl.get("detail") or {}) if isinstance(bl.get("detail"), dict) else {}
    n_bw_sys = int(computed.get("n_bw_systems") or 1)

    for w in pp.get("warnings") or []:
        st.warning(w)

    _migrate_pump_econ_align_key()

    # ── At-a-glance summary (parallel feed uses session train count) ──────────
    n_feed_summary = int(st.session_state.get("pp_n_feed_parallel", 1))
    fp_summary = plant_filtration_motor_kw_parallel_feed(
        total_flow_m3h=float(auto["total_flow_m3h"]),
        streams=int(auto["streams"]),
        n_feed_pumps_parallel_per_stream=n_feed_summary,
        head_dirty_mwc=float(auto["head_dirty_mwc"]),
        head_clean_mwc=float(auto["head_clean_mwc"]),
        rho_feed_kg_m3=float(auto["rho_feed_kg_m3"]),
        motor_eta=motor_eta_run,
        pump_eta_user_cap=pump_eta_run,
    )
    _en_sum = computed.get("energy") or {}
    _op_h_yr = float(inputs.get("op_hours_yr") or 8400.0)
    _annual_m3 = float(_en_sum.get("total_flow_m3_yr") or 0.0)
    spec_central_filt = float(feed0.get("specific_energy_kwh_m3") or 0.0)
    spec_tab_parallel_filt = (
        (fp_summary["p_filtration_plant_avg_kw"] * _op_h_yr) / _annual_m3
        if _annual_m3 > 1e-9
        else 0.0
    )

    st.markdown("#### At a glance")
    if st.session_state.get("pp_align_econ_energy"):
        st.success(
            "**Economics electricity is linked** to this tab’s pump counts, motor class, BW philosophy, "
            "and blower mode — open **Economics** after **Apply** for OPEX / LCOW / CO₂."
        )
    ag1, ag2, ag3, ag4, ag5, ag6 = st.columns(6)
    ag1.metric(f"Head dirty ({ulbl('pressure_mwc')})", fmt(float(auto["head_dirty_mwc"]), "pressure_mwc", 2))
    ag2.metric(f"Head clean ({ulbl('pressure_mwc')})", fmt(float(auto["head_clean_mwc"]), "pressure_mwc", 2))
    ag3.metric(f"Filtration plant avg ({ulbl('power_kw')})", f"{fp_summary['p_filtration_plant_avg_kw']:.2f}")
    ag4.metric(f"Spec. energy — central ({ulbl('energy_kwh_m3')})", fmt(spec_central_filt, "energy_kwh_m3", 4))
    ag5.metric(f"Spec. energy — this tab ({ulbl('energy_kwh_m3')})", fmt(spec_tab_parallel_filt, "energy_kwh_m3", 4))
    ag6.metric(f"Spec. energy — all loads ({ulbl('energy_kwh_m3')})", fmt(float(eb.get("kwh_per_m3_filtered") or 0), "energy_kwh_m3", 4))
    _capex_gl = _pump_screening_capex_from_session(
        pp,
        auto,
        motor_eta_run,
        pump_eta_run,
        n_feed_summary,
        int(st.session_state.get("pp_n_bw_dol", 3)),
        int(st.session_state.get("pp_n_bw_vfd", 2)),
        int(st.session_state.get("pp_n_blowers", 1)),
    )
    st.markdown("**Screening equipment CAPEX (±25 %)**")
    cx1, cx2, cx3 = st.columns([1.05, 1.05, 1.9])
    cx1.metric("DOL + feed + blowers (USD)", f"{float(_capex_gl['dol_grand_total_usd']):,.0f}")
    cx2.metric("VFD BW + feed + blowers (USD)", f"{float(_capex_gl['vfd_grand_total_usd']):,.0f}")
    with cx3:
        st.caption(
            "Skid / base / coupling screening only — same basis as **6 · Budgetary equipment costing**. "
            "Not site piping, MCC, installation, or margin."
        )
    st.caption(
        f"**Filtration specific energy ({ulbl('energy_kwh_m3')}):** *Central* = plant energy model in **compute**; "
        "*This tab* = parallel feed-pump power × operating hours ÷ annual filtered volume "
        "(uses **Hydraulics & plant configuration**). "
        "Enable **linkage** in **Power & Economics linkage** so **Economics** rescales filtration kWh to this tab’s model."
    )

    # ═══ 1 · Hydraulics & plant configuration ═══════════════════════════════════
    with st.expander("1 · Hydraulics & plant configuration", expanded=True):
        st.markdown("##### ① Feed path, pump η & motor class")
        render_hydraulics_and_efficiency_columns(str(inputs.get("unit_system") or "metric"))
        st.divider()
        st.markdown("##### ② Installed trains & Economics / blower drivers")
        st.markdown(
            "**Feed:** parallel pumps **per stream** (identical duty pumps on a common header). "
            "**BW water:** installed pump **trains** (DOL 50 % philosophy vs VFD 100 % trains). "
            "**Blowers:** installed **units** for CAPEX; operating kWh uses the mode below."
        )
        r1, r2, r3, r4 = st.columns(4)
        n_feed_par = int(
            r1.number_input(
                "Parallel feed pumps / stream",
                min_value=1,
                max_value=8,
                value=int(st.session_state.get("pp_n_feed_parallel", 1)),
                key="pp_n_feed_parallel",
                help="Each stream is served by this many identical duty pumps in parallel.",
            )
        )
        n_bw_dol = int(
            r2.number_input(
                "BW pumps installed (DOL 50 % trains)",
                min_value=1,
                max_value=8,
                value=int(st.session_state.get("pp_n_bw_dol", 3)),
                key="pp_n_bw_dol",
                help="Typical **2 duty + 1 standby** at 50 % of design flow each → 3.",
            )
        )
        n_bw_vfd = int(
            r3.number_input(
                "BW pumps installed (VFD 100 % trains)",
                min_value=1,
                max_value=8,
                value=int(st.session_state.get("pp_n_bw_vfd", 2)),
                key="pp_n_bw_vfd",
                help="Typical **1 duty + 1 standby** full-speed frame with VFD → 2.",
            )
        )
        n_blow = int(
            r4.number_input(
                "Air blowers installed",
                min_value=1,
                max_value=6,
                value=int(st.session_state.get("pp_n_blowers", 1)),
                key="pp_n_blowers",
                help=(
                    "Installed packages (CAPEX = n × unit). **Map Q-split:** "
                    "Q_per_machine = Q_plant ÷ this count (e.g. 3 installed → Q/3). "
                    "**Annual kWh** still follows **operating mode** below."
                ),
            )
        )
        e1, e2 = st.columns(2)
        e1.radio(
            "BW pump annual kWh — **Economics** uses this when linkage is on",
            ["DOL", "VFD"],
            horizontal=True,
            key="pp_econ_bw_phil",
            help="Choose which BW pump philosophy drives the **Economics** tab annual electricity when "
            "**Link Economics electricity to pump model** is enabled (**Power & Economics linkage** below).",
        )
        blower_mode = e2.selectbox(
            "Blower operating mode (annual kWh)",
            ["single_duty", "twin_50_iso"],
            index=0,
            format_func=lambda k: BLOWER_MODE_LABELS[k],
            key="pp_blower_mode",
        )
        st.caption(
            f"Feasibility model: **{n_bw_sys}** BW hydraulic train(s). "
            f"**Map Q-split:** **{n_blow}** installed → Q_plant ÷ **{n_blow}** per machine. "
            f"**Annual kWh** uses operating mode "
            f"({'all {0} online'.format(n_blow) if blower_mode == 'twin_50_iso' and n_blow >= 2 else '1 duty + spares'}). "
            "Set count only here — §4c map reads it automatically."
        )

    streams = int(auto["streams"])
    total_flow = float(auto["total_flow_m3h"])
    q_stream = total_flow / max(1, streams)
    q_each_feed = q_stream / max(1, n_feed_par)
    n_feed_total = streams * n_feed_par

    # ═══ 2 Feed pump ═══════════════════════════════════════════════════════════
    with st.expander("2 · Feed pump design", expanded=False):
        h0, h1, h2 = st.columns(3)
        h0.metric(f"Head dirty ({ulbl('pressure_mwc')})", fmt(float(auto["head_dirty_mwc"]), "pressure_mwc", 2))
        h1.metric(f"Head clean ({ulbl('pressure_mwc')})", fmt(float(auto["head_clean_mwc"]), "pressure_mwc", 2))
        h2.metric(f"ρ feed ({ulbl('density_kg_m3')})", fmt(float(auto["rho_feed_kg_m3"]), "density_kg_m3", 1))
        fo1, fo2, fo3 = st.columns(3)
        orient = fo1.selectbox(
            "Pump orientation",
            ["Horizontal", "Vertical dry-installed"],
            key="pp_feed_orient",
            help="Vertical dry-pit / inline raises CAPEX ~10 % in the budget model.",
        )
        p_std = fo2.selectbox(
            "Pump / quality standard",
            ["Commercial", "ISO 5199", "API 610 OH2"],
            index=1,
            key="pp_feed_std",
        )
        mat = fo3.selectbox(
            "Wetted material",
            ["Cast iron", "Carbon steel", "SS316", "Duplex", "Super duplex"],
            index=2,
            key="pp_feed_mat",
        )
        s1, s2 = st.columns(2)
        seal = s1.selectbox(
            "Seal type",
            ["Packing", "Single mechanical seal", "Dual seal / API Plan 53"],
            index=1,
            key="pp_feed_seal",
        )
        vfd_feed = s2.checkbox("VFD on feed pumps", value=False, key="pp_feed_vfd")

        fp_kw = plant_filtration_motor_kw_parallel_feed(
            total_flow_m3h=total_flow,
            streams=streams,
            n_feed_pumps_parallel_per_stream=n_feed_par,
            head_dirty_mwc=float(auto["head_dirty_mwc"]),
            head_clean_mwc=float(auto["head_clean_mwc"]),
            rho_feed_kg_m3=float(auto["rho_feed_kg_m3"]),
            motor_eta=motor_eta_run,
            pump_eta_user_cap=pump_eta_run,
        )
        iec_each = feed_bank_iec_motor_kw_each(
            q_stream_m3h=q_stream,
            n_parallel_pumps=n_feed_par,
            head_mwc=float(auto["head_dirty_mwc"]),
            rho_kg_m3=float(auto["rho_feed_kg_m3"]),
            motor_eta=motor_eta_run,
            pump_eta_user_cap=pump_eta_run,
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Flow / stream ({ulbl('flow_m3h')})", fmt(q_stream, "flow_m3h", 1))
        c2.metric(f"Flow / pump ({ulbl('flow_m3h')})", fmt(q_each_feed, "flow_m3h", 1))
        c3.metric("Parallel pumps / stream", str(n_feed_par))
        c4.metric("Feed pumps installed", str(n_feed_total))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Plant filtration avg (kW)", f"{fp_kw['p_filtration_plant_avg_kw']:.2f}")
        c2.metric(f"Motor kW / feed pump ({ulbl('power_kw')})", fmt(iec_each, "power_kw", 1))
        c3.metric("Installed motor sum (feed)", fmt(iec_each * n_feed_total, "power_kw", 0))
        c4.metric("Ref. single-pump (base)", fmt(feed0["motor_iec_kw"], "power_kw", 1))
        st.markdown(
            f"**Electrical (plant, dirty bed):** {fmt(fp_kw['p_filtration_plant_dirty_kw'], 'power_kw', 2)}  ·  "
            f"**clean:** {fmt(fp_kw['p_filtration_plant_clean_kw'], 'power_kw', 2)}  ·  "
            f"**Specific energy (filtration, central model):** "
            f"{fmt(float(feed0.get('specific_energy_kwh_m3') or 0), 'energy_kwh_m3', 4)} "
            "(**Economics** rescales this when **linkage** is on — **Power & Economics linkage**)."
        )
        _spec_this = (
            (fp_kw["p_filtration_plant_avg_kw"] * _op_h_yr) / _annual_m3
            if _annual_m3 > 1e-9
            else 0.0
        )
        _iec = str(st.session_state.get("pp_feed_iec") or inputs.get("motor_iec_class") or "IE3")
        st.caption(
            f"**Filtration pump η cap** = {pump_eta_run:.2f} · **Motor class** {_iec} → η = {motor_eta_run:.3f} (same as compute). "
            f"**Specific energy (filtration):** central model **{fmt(float(feed0.get('specific_energy_kwh_m3') or 0), 'energy_kwh_m3', 4)}** · "
            f"this tab (parallel feed) **{fmt(_spec_this, 'energy_kwh_m3', 4)}**. "
            f"Reference single-pump creeping hydraulic η ≈ **{float(feed0.get('eta_pump_est') or 0.0):.2f}**."
        )

    # ═══ 3 Backwash pumps ═════════════════════════════════════════════════════
    with st.expander("3 · Backwash pump design — DOL vs VFD + metallurgy", expanded=False):
        st.markdown(
            "**DOL:** staging uses the sequence table; installed count sets **CAPEX**.  "
            "**VFD:** affinity on rated 100 % frame; installed count sets **CAPEX**."
        )
        with st.expander("DOL vs VFD — screening trade-offs", expanded=False):
            st.markdown(
                "| Theme | DOL / fixed speed | VFD / variable speed |\n"
                "|---|---|---|\n"
                "| **CAPEX** | Lower drive cost | +VFDs, harmonics filters |\n"
                "| **Energy** | Higher BW pump kWh | Lower part-load kWh |\n"
                "| **Operability** | Simple staging | Tuning / DCS logic |\n"
                "| **Redundancy** | 3 × 50 % common | 2 × 100 % + VFD |\n"
            )
        bfo1, bfo2, bfo3 = st.columns(3)
        bw_orient = bfo1.selectbox(
            "BW pump orientation",
            ["Horizontal", "Vertical dry-installed"],
            key="pp_bw_orient",
        )
        bw_std = bfo2.selectbox(
            "BW pump standard",
            ["Commercial", "ISO 5199", "API 610 OH2"],
            index=1,
            key="pp_bw_std",
        )
        bw_mat = bfo3.selectbox(
            "BW wetted material",
            ["Cast iron", "Carbon steel", "SS316", "Duplex", "Super duplex"],
            index=2,
            key="pp_bw_mat",
        )
        bs1, bs2 = st.columns(2)
        bw_seal = bs1.selectbox(
            "BW seal type",
            ["Packing", "Single mechanical seal", "Dual seal / API Plan 53"],
            index=1,
            key="pp_bw_seal",
        )
        bw_vfd_allow = bs2.checkbox(
            "VFD allowance on VFD-philosophy BW trains (drives + filtering)",
            value=True,
            key="pp_bw_vfd_allow",
        )
        st.dataframe(pd.DataFrame(pp["sequence_stages"]), use_container_width=True, hide_index=True)
        b1, b2, b3 = st.columns(3)
        b1.metric("BW pump kWh/cycle (DOL)", f"{phil['DOL']['kwh_bw_pump_per_cycle']:.3f}")
        b2.metric("BW pump kWh/cycle (VFD)", f"{phil['VFD']['kwh_bw_pump_per_cycle']:.3f}")
        b3.metric("BW pump savings (yr)", f"{phil['annual_bw_pump_savings_kwh']:,.0f} kWh")
        st.caption(
            f"Screening: **{phil.get('screening_preference', '—')}**  ·  "
            f"Annual BW pump energy (DOL / VFD): "
            f"{phil['DOL']['kwh_bw_pump_yr']:,.0f} / {phil['VFD']['kwh_bw_pump_yr']:,.0f} kWh/yr  ·  "
            f"Nameplate-style motor kW — DOL half-train: **{bw0['motor_iec_kw_dol_half']:.1f}** kW · "
            f"VFD full: **{bw0['motor_iec_kw_vfd_full']:.1f}** kW"
        )

    _bw_sizing = computed.get("bw_sizing") or {}
    if _bw_sizing:
        render_bw_system_equipment_datasheet(
            bw_sizing=_bw_sizing,
            vessel_pressure_bar=float(inputs.get("vessel_pressure_bar") or 0.0),
            blower_air_delta_p_bar=float(inputs.get("blower_air_delta_p_bar") or 0.15),
            n_bw_systems=n_bw_sys,
            expanded=True,
        )

    # ═══ 4 Blower details ═══════════════════════════════════════════════════════
    with st.expander("4 · Air scour blower — performance & redundancy", expanded=False):
        st.caption(
            "Full blower duty table (ΔP breakdown, shaft/motor power, Nm³/h): "
            "**BW system equipment — pump, blower & storage tank** above."
        )
        if bl_detail.get("blower_dp_warning"):
            st.warning(bl_detail["blower_dp_warning"])
        g1, g2, g3 = st.columns(3)
        g1.metric(
            f"Design flow ({ulbl('air_flow_nm3h')})",
            fmt(float(auto.get("q_air_design_nm3h") or 0.0), "air_flow_nm3h", 0),
        )
        g2.metric(f"Motor ({ulbl('power_kw')})", fmt(bl["p_motor_kw"], "power_kw", 1))
        g3.metric("Pressure ratio P₂/P₁", f"{auto['blower_pressure_ratio']:.3f}")
        st.info(bl["technology_hint"])
        _bm = str(st.session_state.get("pp_blower_mode", blower_mode))
        _bm_disp = BLOWER_MODE_LABELS.get(_bm, _bm)
        _bm_note = (
            "Twin **~50 %** mode applies a rough centrifugal **affinity** (Q³) split across online machines; "
            "**PD** blowers often track closer to actual flow."
            if _bm == "twin_50_iso"
            else "**Single-duty** uses one machine at design air for operating hours; **PD** vs centrifugal still follows the sizing model above."
        )
        st.caption(
            f"**Installed blowers:** {n_blow}  ·  **Operating mode:** {_bm_disp} — {_bm_note}"
        )

    from ui.blower_map_ui import render_blower_map_panel

    render_blower_map_panel(inputs, computed)

    # ═══ 4b Air blower RFQ — site & environment (separate manufacturer datasheet) ═
    with st.expander(
        "4b · Air blower RFQ — site & environment (for blower vendor only)",
        expanded=False,
    ):
        st.caption(
            "These fields are **not** used in MMF hydraulics today — they populate the **standalone air blower "
            "datasheet** export below (different recipients than liquid pump vendors)."
        )
        e0, e1 = st.columns(2)
        with e0:
            st.number_input(
                f"Site elevation AMSL ({unit_label('length_m', _us)})",
                value=float(st.session_state.get(
                    "ab_elevation_amsl_m",
                    display_value(10.0, "length_m", _us),
                )),
                step=float(display_value(1.0, "length_m", _us)),
                format="%.1f",
                key="ab_elevation_amsl_m",
                help="Plant altitude for air density / motor derating discussions with the blower OEM.",
            )
            st.markdown(f"**Ambient dry-bulb temperature ({unit_label('temperature_c', _us)})**")
            t1, t2, t3 = st.columns(3)
            t1.number_input(
                "Min",
                value=float(st.session_state.get(
                    "ab_amb_temp_min_c",
                    display_value(5.0, "temperature_c", _us),
                )),
                step=float(display_value(0.5, "temperature_c", _us)),
                key="ab_amb_temp_min_c",
            )
            t2.number_input(
                "Average",
                value=float(st.session_state.get(
                    "ab_amb_temp_avg_c",
                    display_value(25.0, "temperature_c", _us),
                )),
                step=float(display_value(0.5, "temperature_c", _us)),
                key="ab_amb_temp_avg_c",
            )
            t3.number_input(
                "Max",
                value=float(st.session_state.get(
                    "ab_amb_temp_max_c",
                    display_value(45.0, "temperature_c", _us),
                )),
                step=float(display_value(0.5, "temperature_c", _us)),
                key="ab_amb_temp_max_c",
            )
            st.markdown("**Relative humidity (%)**")
            h1, h2, h3 = st.columns(3)
            h1.number_input("Min RH", value=float(st.session_state.get("ab_rh_min_pct", 20.0)), step=1.0, key="ab_rh_min_pct")
            h2.number_input("Average RH", value=float(st.session_state.get("ab_rh_avg_pct", 60.0)), step=1.0, key="ab_rh_avg_pct")
            h3.number_input("Max RH", value=float(st.session_state.get("ab_rh_max_pct", 95.0)), step=1.0, key="ab_rh_max_pct")
        with e1:
            st.number_input(
                f"Barometric pressure — site / design ({unit_label('pressure_bar', _us)}a)",
                value=float(st.session_state.get(
                    "ab_barometric_bara",
                    display_value(1.01325, "pressure_bar", _us),
                )),
                step=float(display_value(0.001, "pressure_bar", _us)),
                format="%.4f",
                key="ab_barometric_bara",
                help=(
                    "Leave at ~"
                    f"{format_value(1.01325, 'pressure_bar', _us, 3)} for sea level if not adjusted for altitude."
                ),
            )
            _install_opts = ["Indoor", "Outdoor", "Sheltered outdoor", "TBA"]
            _prev_ic = str(st.session_state.get("ab_installation_class", "Outdoor"))
            _ic_idx = _install_opts.index(_prev_ic) if _prev_ic in _install_opts else 1
            st.selectbox(
                "Installation class",
                _install_opts,
                index=_ic_idx,
                key="ab_installation_class",
            )
            st.number_input(
                "Purchaser noise limit dB(A) @ 1 m (typical)",
                value=float(st.session_state.get("ab_noise_limit_dba", 85.0)),
                step=1.0,
                key="ab_noise_limit_dba",
            )
            st.text_input(
                "Electrical / hazardous area classification",
                value=str(st.session_state.get("ab_electrical_area", "Non-hazardous (TBA per project)")),
                key="ab_electrical_area",
            )
        st.text_area(
            "Site location / address notes (optional)",
            value=str(st.session_state.get("ab_site_location_notes", "")),
            height=68,
            key="ab_site_location_notes",
        )
        st.text_area(
            "Dust / salt / sand exposure (ISO category, coastal spray, etc.)",
            value=str(st.session_state.get("ab_dust_salt_notes", "")),
            height=68,
            key="ab_dust_salt_notes",
        )
        st.text_area(
            "Corrosive or chemical atmosphere near blower intake",
            value=str(st.session_state.get("ab_corrosive_notes", "")),
            height=68,
            key="ab_corrosive_notes",
        )

    # ═══ 5 Power summary + Economics electricity linkage ═══════════════════════
    with st.expander("5 · Power & Economics linkage", expanded=True):
        st.markdown("#### Link **Economics** annual electricity to this tab")
        st.checkbox(
            "**Link Economics electricity to pump model** — OPEX energy line, CO₂ operational, "
            "benchmarks, and NPV use parallel feed count, **motor efficiency class** (**Hydraulics & plant configuration** above), "
            "BW philosophy, and blower mode from **here**.",
            key="pp_align_econ_energy",
            help="Matches the former checkbox on the Economics tab. Requires a full compute with pump hydraulics.",
        )
        _en = computed.get("energy") or {}
        _hpd = float(_en.get("h_bw_pump_plant_day", 0) or 0)
        _had = float(_en.get("h_blower_plant_day", 0) or 0)
        st.info(
            "**BW electricity duty (plant-wide, design case)** — hours per day summed over all "
            "filters at rated power: **BW water pump** ≈ "
            f"**{_hpd:.2f}** h/day · **air scour blower** ≈ **{_had:.2f}** h/day "
            "(from BW step durations × feasibility **N** cycles/filter/day). "
            "Annual kWh for BW loads uses **kWh = kW × these hours**, not 24/7 pump power."
        )
        if st.session_state.get("pp_align_econ_energy") and computed.get("pump_perf") and computed.get("hyd_prof"):
            _ek = economics_energy_from_pump_configuration(
                _en,
                pp,
                computed["hyd_prof"],
                total_flow_m3h=float(inputs["total_flow"]),
                streams=int(inputs["streams"]),
                n_feed_pumps_parallel_per_stream=int(st.session_state.get("pp_n_feed_parallel", 1)),
                pump_eta_user=pump_eta_run,
                motor_eta_feed=motor_eta_run,
                rho_feed=float(computed.get("rho_feed") or 1025.0),
                bw_philosophy=str(st.session_state.get("pp_econ_bw_phil", "DOL")),
                blower_operating_mode=str(st.session_state.get("pp_blower_mode", "single_duty")),
                n_blowers_running=int(st.session_state.get("pp_n_blowers", 1)),
            )
            _kwh_t = float(_ek["energy_kwh_yr"])
            _tar = float(inputs.get("elec_tariff") or 0.1)
            st.success(
                f"**Linked model (annual):** filtration **{_ek['energy_kwh_filtration_yr']:,.0f}** kWh/yr · "
                f"BW pump **{_ek['energy_kwh_bw_pump_yr']:,.0f}** · blower **{_ek['energy_kwh_blower_yr']:,.0f}** · "
                f"**total** **{_kwh_t:,.0f}** kWh/yr — open **Economics** for OPEX / LCOW / CO₂."
            )
            st.caption(
                f"**Economics → OPEX → Energy** = **{_kwh_t:,.0f}** kWh/yr × **{_tar:g}** USD/kWh ≈ **USD {_kwh_t * _tar:,.0f}/yr** "
                f"(OPEX lists **USD/yr**; this banner is **kWh/yr** — same total)."
            )
        elif st.session_state.get("pp_align_econ_energy"):
            st.warning("Linkage is on but **pump_perf** or **hyd_prof** is missing — run **Apply** / recompute.")

        dol_inst = float(bw0["motor_iec_kw_dol_half"]) * float(n_bw_dol)
        vfd_inst = float(bw0["motor_iec_kw_vfd_full"]) * float(n_bw_vfd)
        p1, p2, p3, p4 = st.columns(4)
        p1.metric(f"Feed plant avg (recalc.) ({ulbl('power_kw')})", fmt(fp_kw["p_filtration_plant_avg_kw"], "power_kw", 2))
        p2.metric("BW DOL installed (motor sum)", fmt(dol_inst, "power_kw", 1))
        p3.metric("BW VFD installed (motor sum)", fmt(vfd_inst, "power_kw", 1))
        p4.metric("Peak BW stage (est.)", fmt(eb["peak_bw_stage_kw"], "power_kw", 1))
        st.markdown(
            f"**Annual (central model):** filtration **{eb['e_filt_kwh_yr']:,.0f}** kWh/yr · "
            f"BW pump **{eb['e_bw_pump_kwh_yr_model']:,.0f}** · blower **{eb['e_blower_kwh_yr']:,.0f}**  ·  "
            f"**Specific energy — all loads ({ulbl('energy_kwh_m3')}):** "
            f"{fmt(float(eb['kwh_per_m3_filtered']), 'energy_kwh_m3', 4)}"
        )
        st.caption(
            f"Sequence-integrated BW + blower (one filter, one cycle): **{eb['kwh_per_bw_filter_cycle']:.3f}** kWh  ·  "
            f"Plant-day sequence estimate: **{eb['kwh_bw_plant_day_sequence']:,.1f}** kWh/day."
        )
        if _PLOTLY_OK and pp["sequence_stages"]:
            t0 = 0.0
            xs, ys = [], []
            for row in pp["sequence_stages"]:
                dt = float(row["t_min"]) / 60.0
                xs.extend([t0, t0 + dt])
                ptot = float(row["P_total (kW)"])
                ys.extend([ptot, ptot])
                t0 += dt
            fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines", line_shape="hv", name="BW + blower"))
            fig.update_layout(
                title="Backwash sequence — instantaneous electrical load (one filter)",
                xaxis_title="Time from BW start (h)",
                yaxis_title="kW",
                height=360,
                margin=dict(t=50, b=40, l=50, r=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ═══ 6 Budgetary costing ═════════════════════════════════════════════════════
    with st.expander("6 · Budgetary equipment costing (±25 %)", expanded=True):
        capex_live = _pump_screening_capex_from_session(
            pp,
            auto,
            motor_eta_run,
            pump_eta_run,
            n_feed_par,
            n_bw_dol,
            n_bw_vfd,
            n_blow,
        )
        st.table(pd.DataFrame([
            ["Feed pumps (n × unit)", f"USD {capex_live['feed_pumps_all_usd']:,.0f}"],
            ["BW pumps — DOL (n trains)", f"USD {capex_live['dol_bw_total_usd']:,.0f}"],
            ["BW pumps — VFD (n trains)", f"USD {capex_live['vfd_bw_total_usd']:,.0f}"],
            ["Blowers (n × unit)", f"USD {capex_live['blower_package_total_usd']:,.0f}"],
            ["**Subtotal — DOL + blowers + feed**", f"**USD {capex_live['dol_grand_total_usd']:,.0f}**"],
            ["**Subtotal — VFD + blowers + feed**", f"**USD {capex_live['vfd_grand_total_usd']:,.0f}**"],
            ["Baseline package (reference)", f"USD {capex_bl.get('dol_grand_total_usd', 0):,.0f}"],
        ], columns=["Item", "Budgetary"]))
        st.caption(
            "Skid / base / coupling allowance per train. Not site piping, MCC building, installation, margin."
        )

    # ═══ 7 Recommendations ═══════════════════════════════════════════════════════
    with st.expander("7 · Engineering recommendations", expanded=False):
        for note in pp.get("engineering_notes") or []:
            st.markdown(f"- {note}")

    # ═══ 8 Export ═══════════════════════════════════════════════════════════════
    with st.expander("8 · Exportable summary tables", expanded=False):
        _ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        _ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _pname = str(inputs.get("project_name") or "")
        _pdoc = str(inputs.get("doc_number") or "")
        _usys = str(inputs.get("unit_system") or "metric")
        _slug = re.sub(r"[^A-Za-z0-9._-]+", "_", _pname or "MMF").strip("._-")[:48] or "MMF"

        _ui_snap: dict[str, Any] = {
            "pp_n_feed_parallel": n_feed_par,
            "pp_n_bw_dol": int(st.session_state.get("pp_n_bw_dol", 3)),
            "pp_n_bw_vfd": int(st.session_state.get("pp_n_bw_vfd", 2)),
            "pp_n_blowers": int(st.session_state.get("pp_n_blowers", 1)),
            "pp_econ_bw_phil": str(st.session_state.get("pp_econ_bw_phil", "DOL")),
            "pp_blower_mode": str(st.session_state.get("pp_blower_mode", "single_duty")),
            "pp_feed_orient": str(st.session_state.get("pp_feed_orient", "Horizontal")),
            "pp_feed_std": str(st.session_state.get("pp_feed_std", "ISO 5199")),
            "pp_feed_mat": str(st.session_state.get("pp_feed_mat", "SS316")),
            "pp_feed_seal": str(st.session_state.get("pp_feed_seal", "Single mechanical seal")),
            "pp_feed_vfd": bool(st.session_state.get("pp_feed_vfd", False)),
            "pp_bw_orient": str(st.session_state.get("pp_bw_orient", "Horizontal")),
            "pp_bw_std": str(st.session_state.get("pp_bw_std", "ISO 5199")),
            "pp_bw_mat": str(st.session_state.get("pp_bw_mat", "SS316")),
            "pp_bw_seal": str(st.session_state.get("pp_bw_seal", "Single mechanical seal")),
            "pp_bw_vfd_allow": bool(st.session_state.get("pp_bw_vfd_allow", True)),
            "pp_feed_iec": str(st.session_state.get("pp_feed_iec") or inputs.get("motor_iec_class") or "IE3"),
        }
        _bundle = build_pump_datasheet_bundle(inputs, computed, _ui_snap, export_timestamp_utc=_ts_iso)
        summary = pd.DataFrame([
            ["Export timestamp (UTC)", _ts],
            ["Project name", _pname],
            ["Document #", _pdoc],
            ["Unit system", _usys],
            ["", ""],
            ["Total flow", fmt(auto["total_flow_m3h"], "flow_m3h", 1)],
            ["Streams × filters", f"{auto['streams']} × {auto['n_filters']}"],
            ["Filtration pump η cap", f"{pump_eta_run:.3f}"],
            ["BW pump hydraulic η", f"{bw_pump_eta_run:.3f}"],
            ["Motor efficiency class", str(st.session_state.get("pp_feed_iec") or inputs.get("motor_iec_class") or "IE3")],
            ["Motor η (from IEC class)", f"{motor_eta_run:.3f}"],
            ["Parallel feed pumps / stream", str(n_feed_par)],
            ["Feed pumps installed", str(n_feed_total)],
            ["Flow / pump (feed)", fmt(q_each_feed, "flow_m3h", 2)],
            ["Plant feed avg kW (recalc.)", f"{fp_kw['p_filtration_plant_avg_kw']:.3f}"],
            ["Feed motor kW / pump (nameplate-style)", fmt(iec_each, "power_kw", 1)],
            ["BW pumps installed DOL / VFD", f"{n_bw_dol} / {n_bw_vfd}"],
            ["Blowers installed", str(n_blow)],
            ["BW design flow", fmt(auto["q_bw_design_m3h"], "flow_m3h", 1)],
            ["BW head", fmt(auto["bw_head_mwc"], "pressure_mwc", 2)],
            ["Blower motor (duty)", fmt(bl["p_motor_kw"], "power_kw", 1)],
            ["Economics BW philosophy", str(st.session_state.get("pp_econ_bw_phil", "DOL"))],
            [f"Specific energy — all loads ({ulbl('energy_kwh_m3')})", fmt(float(eb["kwh_per_m3_filtered"]), "energy_kwh_m3", 4)],
            ["BW + blower energy / filter-cycle (kWh)", f"{eb['kwh_per_bw_filter_cycle']:.3f}"],
            ["Screening CAPEX — DOL + feed + blowers (USD)", f"{float(_capex_gl['dol_grand_total_usd']):,.0f}"],
            ["Screening CAPEX — VFD BW + feed + blowers (USD)", f"{float(_capex_gl['vfd_grand_total_usd']):,.0f}"],
        ], columns=["Parameter", "Value"])
        st.dataframe(summary, use_container_width=True, hide_index=True)
        csv_buf = io.StringIO()
        summary.to_csv(csv_buf, index=False)
        st.download_button(
            "Download summary CSV",
            data=csv_buf.getvalue().encode("utf-8"),
            file_name="AQUASIGHT_pumps_power_summary.csv",
            mime="text/csv",
        )

        st.markdown("#### Liquid pumps — requisition datasheet (feed + BW water)")
        st.caption(
            "**Duty** = model-filled fields only. **Duty + TBA** adds vendor / site placeholders. "
            "**JSON** is the same bundle for scripts — not a vendor submittal. "
            "Air scour blowers are exported separately below."
        )
        _render_datasheet_export_row(
            bundle=_bundle,
            equipment="liquid",
            slug=_slug,
            select_key="pp_liquid_export_fmt",
            download_key="pp_liquid_export_dl",
        )

        _blower_env_snap: dict[str, Any] = {
            "elevation_amsl_m": _ab_session_to_si("ab_elevation_amsl_m", 10.0, "length_m", _us),
            "ambient_temp_min_c": _ab_session_to_si("ab_amb_temp_min_c", 5.0, "temperature_c", _us),
            "ambient_temp_avg_c": _ab_session_to_si("ab_amb_temp_avg_c", 25.0, "temperature_c", _us),
            "ambient_temp_max_c": _ab_session_to_si("ab_amb_temp_max_c", 45.0, "temperature_c", _us),
            "relative_humidity_min_pct": st.session_state.get("ab_rh_min_pct"),
            "relative_humidity_avg_pct": st.session_state.get("ab_rh_avg_pct"),
            "relative_humidity_max_pct": st.session_state.get("ab_rh_max_pct"),
            "barometric_pressure_bara": _ab_session_to_si("ab_barometric_bara", 1.01325, "pressure_bar", _us),
            "installation_class": st.session_state.get("ab_installation_class"),
            "dust_salt_exposure_notes": (st.session_state.get("ab_dust_salt_notes") or "").strip() or None,
            "corrosive_atmosphere_notes": (st.session_state.get("ab_corrosive_notes") or "").strip() or None,
            "noise_limit_dba": st.session_state.get("ab_noise_limit_dba"),
            "electrical_area_classification": (st.session_state.get("ab_electrical_area") or "").strip() or None,
            "site_location_notes": (st.session_state.get("ab_site_location_notes") or "").strip() or None,
        }
        _air_bundle = build_air_blower_datasheet_bundle(
            inputs, computed, _ui_snap, _blower_env_snap, export_timestamp_utc=_ts_iso,
        )

        st.markdown("#### Air scour blower — manufacturer RFQ (standalone)")
        st.caption(
            "Uses **§4b** site / ambient fields plus the MMF air duty from **§4**. Intended for **blower OEMs** "
            "(different from liquid pump vendors)."
        )
        _render_datasheet_export_row(
            bundle=_air_bundle,
            equipment="air_blower",
            slug=_slug,
            select_key="pp_air_export_fmt",
            download_key="pp_air_export_dl",
        )
