"""engine/pdf_report.py — PDF generation via ReportLab Platypus.
Exports: PDF_OK (bool), build_pdf(inputs, computed, sections, unit_system) -> bytes.
sections keys: process, water, media, dp, vessel, bw_hyd, bw_equip, energy.
No Streamlit imports — pure Python only.
"""
import io
from datetime import date as _date

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable,
    )
    PDF_OK = True
    _BLUE  = colors.HexColor("#1e3a6e")
    _LGREY = colors.HexColor("#f2f2f2")
    _W     = A4[0] - 28 * mm
    _TS    = TableStyle([
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"), ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7.5), ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.white,_LGREY]),
        ("LEFTPADDING",(0,0),(-1,-1),4), ("RIGHTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),2),  ("BOTTOMPADDING",(0,0),(-1,-1),2),
    ])
except ImportError:
    PDF_OK = False


def _tbl(rows, w0=60*mm):
    nc = max(len(r) for r in rows)
    t  = Table(rows, colWidths=[w0] + [(_W-w0)/max(nc-1,1)]*(nc-1))
    t.setStyle(_TS)
    return t


def build_pdf(
    inputs: dict,
    computed: dict,
    sections: dict,
    unit_system: str = "metric",
) -> bytes:
    """Build PDF. Returns raw bytes for st.download_button."""
    if not PDF_OK:
        raise RuntimeError("Install reportlab: pip install reportlab")
    from engine.units import format_value as _fmt

    def fv(si, qty, dec=2):
        return _fmt(si, qty, unit_system, dec)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=14*mm, bottomMargin=14*mm)
    stl = getSampleStyleSheet()
    story: list = []

    def _h(text):
        story.extend([Spacer(1,3*mm), Paragraph(text, stl["h2"])])

    def _add(rows, w0=60*mm):
        story.extend([_tbl(rows, w0), Spacer(1,2*mm)])

    story += [Paragraph("AQUASIGHT™ — Horizontal Multi-Media Filter", stl["h1"]),
              Paragraph("Engineering Calculation Report", stl["h2"]),
              HRFlowable(width="100%", thickness=1, color=_BLUE), Spacer(1,3*mm)]
    pn=inputs.get("project_name",""); dn=inputs.get("doc_number","")
    rv=inputs.get("revision","");     eg=inputs.get("engineer","")
    _add([["Project",pn],["Document No.",f"{dn}  ·  Rev {rv}"],
          ["Client",inputs.get("client") or "—"],["Prepared by",eg],
          ["Date",str(_date.today())]])

    q  = computed.get("q_per_filter", 0)
    ar = computed.get("avg_area", 1) or 1
    mc = computed.get("mech", {})

    if sections.get("process"):
        tf=inputs["total_flow"]; ns=inputs["streams"]; nf=inputs["n_filters"]
        _h("B1 · Process Basis")
        _add([["Total flow", fv(tf, "flow_m3h", 0)],
              ["Streams × filters",f"{ns} × {nf} = {ns*nf} vessels"],
              ["Redundancy",f"N-{inputs['redundancy']} per stream"],
              ["Flow / filter (N)", fv(q, "flow_m3h", 1)],
              ["Filtration rate (N)", fv(q/ar, "velocity_m_h", 2)],
              ["Filter cross-section", fv(ar, "area_m2", 3)]])

    if sections.get("water"):
        rf=computed.get("rho_feed",0); rb=computed.get("rho_bw",0)
        mf=computed.get("mu_feed",0);  mb=computed.get("mu_bw",0)
        _h("B2 · Water Properties")
        _add([[""," Feed"," Backwash"],
              ["Salinity",f"{inputs['feed_sal']:.2f} ppt",f"{inputs['bw_sal']:.2f} ppt"],
              ["Temp.", fv(inputs["feed_temp"], "temperature_c", 1),
               fv(inputs["bw_temp"], "temperature_c", 1)],
              ["Density", fv(rf, "density_kg_m3", 3), fv(rb, "density_kg_m3", 3)],
              ["Viscosity", fv(mf*1000.0, "viscosity_cp", 4),
               fv(mb*1000.0, "viscosity_cp", 4)]], w0=50*mm)

    if sections.get("media"):
        from engine.units import unit_label as _ulbl
        _h("B3 · Media Configuration")
        _dunit = _ulbl("length_m", unit_system)
        _rhou = _ulbl("density_kg_m3", unit_system)
        _add([["Media", "Sup.", f"Depth ({_dunit})", "d10 (mm)", "CU", "ε₀", f"ρp ({_rhou})"]] +
             [[b["Type"], "✓" if b.get("is_support") else "",
               _fmt(float(b["Depth"]), "length_m", unit_system, 3),
               f"{b['d10']:.2f}", f"{b['cu']:.2f}",
               f"{b.get('epsilon0', 0):.3f}",
               _fmt(float(b["rho_p_eff"]), "density_kg_m3", unit_system, 0)]
              for b in computed.get("base", [])], w0=35*mm)

    if sections.get("dp"):
        dp=computed.get("bw_dp",{})
        _h("B4 · Filtration Pressure Drop")
        _add([["Clean-bed ΔP (Ergun)", fv(dp.get("dp_clean_bar",0), "pressure_bar", 4)],
              ["Dirty-bed ΔP", fv(dp.get("dp_dirty_bar",0), "pressure_bar", 4)],
              ["BW trigger", fv(inputs.get("dp_trigger_bar",0), "pressure_bar", 2)]])

    if sections.get("vessel"):
        rid=computed.get("real_id",0); cyl=computed.get("cyl_len",0)
        _h("C1 · Vessel Dimensions (ASME VIII Div. 1)")
        _add([["Nominal / Real ID",
               f"{fv(inputs['nominal_id'], 'length_m', 3)} / {fv(rid, 'length_m', 4)}"],
              ["OD", fv(mc.get("od_m",0), "length_m", 4)],
              ["Total length T/T", fv(inputs["total_length"], "length_m", 3)],
              ["Cylinder length", fv(cyl, "length_m", 3)],
              ["End geometry",computed.get("end_geometry","")],
              ["Material",computed.get("material_name","")],
              ["Design pressure", fv(inputs["design_pressure"], "pressure_bar", 2) + " g"],
              ["Shell t_req/nom",f"{mc.get('t_shell_min_mm',0):.2f}/{mc.get('t_shell_design_mm',0)} mm"],
              ["Head  t_req/nom",f"{mc.get('t_head_min_mm',0):.2f}/{mc.get('t_head_design_mm',0)} mm"]])

    if sections.get("bw_hyd"):
        bwc=computed.get("bw_col",{})
        _h("D1 · Backwash Hydraulics")
        _add([["BW velocity (proposed)", fv(inputs.get("bw_velocity",0), "velocity_m_h", 1)],
              ["Max safe BW velocity", fv(bwc.get("max_safe_bw_m_h",0), "velocity_m_h", 1)],
              ["Freeboard (actual)", fv(bwc.get("freeboard_m",0), "length_m", 3)],
              ["Status",bwc.get("status","—")]])

    if sections.get("bw_equip"):
        sz=computed.get("bw_sizing",{})
        _h("D2 · BW Equipment Sizing")
        _add([["BW pump flow", fv(sz.get("q_bw_design_m3h",0), "flow_m3h", 1)],
              ["BW pump head", fv(sz.get("bw_head_mwc",0), "pressure_mwc", 2)],
              ["BW pump motor", fv(sz.get("p_pump_motor_kw",0), "power_kw", 1)],
              ["Blower flow", fv(sz.get("q_air_design_m3h",0), "flow_m3h", 1)],
              ["Blower motor", fv(sz.get("p_blower_motor_kw",0), "power_kw", 1)],
              ["BW tank", fv(sz.get("v_tank_m3",0), "volume_m3", 1)]])

    if sections.get("energy"):
        en=computed.get("energy",{})
        _h("F · Energy Summary")
        _add([["Filtration pump (dirty, /filter)", fv(en.get("p_filt_dirty_kw",0), "power_kw", 1)],
              ["BW pump power", fv(en.get("p_bw_kw",0), "power_kw", 1)],
              ["Blower power (elec.)", fv(en.get("p_blower_elec_kw",0), "power_kw", 1)],
              ["Annual energy",f"{en.get('e_total_kwh_yr',0)/1e3:,.0f} MWh/yr"],
              ["Specific energy", fv(en.get("kwh_per_m3",0), "energy_kwh_m3", 4)]])

    story += [Spacer(1,6*mm), HRFlowable(width="100%", thickness=0.5, color=_BLUE),
              Paragraph(f"{eg} · AQUASIGHT™ · {dn} Rev {rv} · {_date.today()}",
                        stl["Normal"])]
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
