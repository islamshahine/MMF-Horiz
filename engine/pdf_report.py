"""engine/pdf_report.py — PDF generation via ReportLab Platypus.
Exports: PDF_OK (bool), build_pdf(inputs, computed, sections) -> bytes.
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


def build_pdf(inputs: dict, computed: dict, sections: dict) -> bytes:
    """Build PDF. Returns raw bytes for st.download_button."""
    if not PDF_OK:
        raise RuntimeError("Install reportlab: pip install reportlab")
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
        _add([["Total flow",f"{tf:,.0f} m³/h"],
              ["Streams × filters",f"{ns} × {nf} = {ns*nf} vessels"],
              ["Redundancy",f"N-{inputs['redundancy']} per stream"],
              ["Flow / filter (N)",f"{q:.1f} m³/h"],
              ["Filtration rate (N)",f"{q/ar:.2f} m/h"],
              ["Filter cross-section",f"{ar:.3f} m²"]])

    if sections.get("water"):
        rf=computed.get("rho_feed",0); rb=computed.get("rho_bw",0)
        mf=computed.get("mu_feed",0);  mb=computed.get("mu_bw",0)
        _h("B2 · Water Properties")
        _add([[""," Feed"," Backwash"],
              ["Salinity",f"{inputs['feed_sal']:.2f} ppt",f"{inputs['bw_sal']:.2f} ppt"],
              ["Temp.",f"{inputs['feed_temp']:.1f} °C",f"{inputs['bw_temp']:.1f} °C"],
              ["Density",f"{rf:.3f} kg/m³",f"{rb:.3f} kg/m³"],
              ["Viscosity",f"{mf*1000:.4f} cP",f"{mb*1000:.4f} cP"]], w0=50*mm)

    if sections.get("media"):
        _h("B3 · Media Configuration")
        _add([["Media","Sup.","Depth m","d10 mm","CU","ε₀","ρp kg/m³"]] +
             [[b["Type"],"✓"if b.get("is_support")else"",f"{b['Depth']:.3f}",
               f"{b['d10']:.2f}",f"{b['cu']:.2f}",
               f"{b.get('epsilon0',0):.3f}",f"{b['rho_p_eff']:.0f}"]
              for b in computed.get("base",[])], w0=35*mm)

    if sections.get("dp"):
        dp=computed.get("bw_dp",{})
        _h("B4 · Filtration Pressure Drop")
        _add([["Clean-bed ΔP (Ergun)",f"{dp.get('dp_clean_bar',0):.4f} bar"],
              ["Dirty-bed ΔP",f"{dp.get('dp_dirty_bar',0):.4f} bar"],
              ["BW trigger",f"{inputs.get('dp_trigger_bar',0):.2f} bar"]])

    if sections.get("vessel"):
        rid=computed.get("real_id",0); cyl=computed.get("cyl_len",0)
        _h("C1 · Vessel Dimensions (ASME VIII Div. 1)")
        _add([["Nominal / Real ID",f"{inputs['nominal_id']:.3f} / {rid:.4f} m"],
              ["OD",f"{mc.get('od_m',0):.4f} m"],
              ["Total length T/T",f"{inputs['total_length']:.3f} m"],
              ["Cylinder length",f"{cyl:.3f} m"],
              ["End geometry",computed.get("end_geometry","")],
              ["Material",computed.get("material_name","")],
              ["Design pressure",f"{inputs['design_pressure']:.2f} bar g"],
              ["Shell t_req/nom",f"{mc.get('t_shell_min_mm',0):.2f}/{mc.get('t_shell_design_mm',0)} mm"],
              ["Head  t_req/nom",f"{mc.get('t_head_min_mm',0):.2f}/{mc.get('t_head_design_mm',0)} mm"]])

    if sections.get("bw_hyd"):
        bwc=computed.get("bw_col",{})
        _h("D1 · Backwash Hydraulics")
        _add([["BW velocity (proposed)",f"{inputs.get('bw_velocity',0):.1f} m/h"],
              ["Max safe BW velocity",f"{bwc.get('max_safe_bw_m_h',0):.1f} m/h"],
              ["Freeboard (actual)",f"{bwc.get('freeboard_m',0)*1000:.0f} mm"],
              ["Status",bwc.get("status","—")]])

    if sections.get("bw_equip"):
        sz=computed.get("bw_sizing",{})
        _h("D2 · BW Equipment Sizing")
        _add([["BW pump flow",f"{sz.get('q_bw_design_m3h',0):,.1f} m³/h"],
              ["BW pump head",f"{sz.get('bw_head_mwc',0):.2f} mWC"],
              ["BW pump motor",f"{sz.get('p_pump_motor_kw',0):.1f} kW"],
              ["Blower flow",f"{sz.get('q_air_design_m3h',0):,.1f} Am³/h"],
              ["Blower motor",f"{sz.get('p_blower_motor_kw',0):.1f} kW"],
              ["BW tank",f"{sz.get('v_tank_m3',0):.1f} m³"]])

    if sections.get("energy"):
        en=computed.get("energy",{})
        _h("F · Energy Summary")
        _add([["Filtration pump (dirty, /filter)",f"{en.get('p_filt_dirty_kw',0):.1f} kW"],
              ["BW pump power",f"{en.get('p_bw_kw',0):.1f} kW"],
              ["Blower power (elec.)",f"{en.get('p_blower_elec_kw',0):.1f} kW"],
              ["Annual energy",f"{en.get('e_total_kwh_yr',0)/1e3:,.0f} MWh/yr"],
              ["Specific energy",f"{en.get('kwh_per_m3',0):.4f} kWh/m³"]])

    story += [Spacer(1,6*mm), HRFlowable(width="100%", thickness=0.5, color=_BLUE),
              Paragraph(f"{eg} · AQUASIGHT™ · {dn} Rev {rv} · {_date.today()}",
                        stl["Normal"])]
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
