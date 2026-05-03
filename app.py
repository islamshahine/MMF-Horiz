import streamlit as st
import math
import pandas as pd

from engine.geometry import segment_area, dish_volume
from engine.process import filter_loading
from engine.mechanical import (
    thickness, empty_weight, MATERIALS, RADIOGRAPHY_OPTIONS,
    JOINT_EFFICIENCY, STEEL_DENSITY_KG_M3
)

# =========================
# PRESETS
# =========================
default_media_presets = {
    "Custom":       {"d10": 0.0,  "cu": 1.0, "epsilon0": 0.40, "rho_p_eff": 2650, "d60": 0.0},
    "Gravel":       {"d10": 6,    "cu": 0,   "epsilon0": 0.46, "rho_p_eff": 2600, "d60": None},
    "Coarse Sand":  {"d10": 1.35, "cu": 1.5, "epsilon0": 0.44, "rho_p_eff": 2650, "d60": 2.03},
    "Fine Sand":    {"d10": 0.8,  "cu": 1.3, "epsilon0": 0.42, "rho_p_eff": 2650, "d60": 1.2},
    "Anthracite":   {"d10": 1.3,  "cu": 1.5, "epsilon0": 0.48, "rho_p_eff": 1450, "d60": 2.25},
}

if "media_presets" not in st.session_state:
    st.session_state.media_presets = default_media_presets.copy()

st.set_page_config(page_title="AQUASIGHT™ MMF", layout="wide")

# =========================
# SIDEBAR
# =========================
with st.sidebar:

    st.header("📥 Process")
    total_flow = st.number_input("Total Flow (m³/h)", value=21000.0)
    streams    = int(st.number_input("Streams", value=1))
    n_filters  = int(st.number_input("Filters/Stream", value=16))
    redundancy = int(st.selectbox("Redundancy", [0, 1, 2, 3]))

    st.header("🏗️ Geometry")
    diameter     = st.number_input("Diameter (m)", value=5.5)
    total_length = st.number_input("Length (m)", value=24.3)
    end_geometry = st.selectbox("End Geometry", ["Elliptic 2:1", "Torispherical 10%"])

    st.header("🧱 Media Layers")
    nozzle_plate_height = st.number_input("Nozzle Plate Height (m)", value=0.0)
    n_layers = st.selectbox("Layers", [1, 2, 3, 4, 5, 6], index=2)

    layers = []
    for i in range(n_layers):
        with st.expander(f"Layer {i+1}"):
            m_type = st.selectbox(
                f"Type L{i+1}",
                list(st.session_state.media_presets.keys()),
                key=f"type_{i}"
            )
            depth = st.number_input(f"Depth L{i+1} (m)", value=0.5, key=f"depth_{i}")
            data  = st.session_state.media_presets[m_type].copy()

            if m_type == "Custom":
                data["rho_p_eff"] = st.number_input(f"Density L{i+1}", value=2650, key=f"rho_{i}")
                data["epsilon0"]  = st.number_input(f"Voidage L{i+1}",  value=0.42, key=f"eps_{i}")

            layers.append({**data, "Type": m_type, "Depth": depth})

    # ─────────────────────────────────────────────
    # MECHANICAL (enhanced)
    # ─────────────────────────────────────────────
    st.header("⚙️ Mechanical")

    material_name = st.selectbox("Material of Shell/Head", list(MATERIALS.keys()),
                                  index=3)   # default: ASTM A516-70
    mat_info = MATERIALS[material_name]
    st.caption(f"*{mat_info['description']}*")

    design_pressure = st.number_input("Design Pressure (bar)", value=7.0)
    design_temp     = st.number_input("Design Temperature (°C)", value=50.0)
    corrosion       = st.number_input("Corrosion Allowance (mm)", value=1.5)
    internal_lining = st.number_input("Internal Lining (mm)", value=4.0,
                                       help="Lining or cladding that reduces usable ID")

    st.markdown("**Radiography (ASME UW-11)**")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        shell_radio = st.selectbox("Shell", RADIOGRAPHY_OPTIONS, index=2,
                                    key="shell_radio")
        st.caption(f"E = {JOINT_EFFICIENCY[shell_radio]:.2f}")
    with col_r2:
        head_radio = st.selectbox("Head", RADIOGRAPHY_OPTIONS, index=2,
                                   key="head_radio")
        st.caption(f"E = {JOINT_EFFICIENCY[head_radio]:.2f}")

    steel_density = st.number_input(
        "Steel Density (kg/m³)", value=STEEL_DENSITY_KG_M3,
        help="7850 for carbon steel · 7900 for 304/316 SS"
    )

    st.header("⚠️ Performance Thresholds")
    velocity_threshold = st.number_input("Max Velocity (m/h)", value=12.0)
    ebct_threshold     = st.number_input("Min EBCT (min)", value=5.0)

# =========================
# GEOMETRY ENGINE
# =========================
h_dish  = (diameter / 4) if end_geometry == "Elliptic 2:1" else (0.2 * diameter)
cyl_len = total_length - 2 * h_dish

# =========================
# TABS
# =========================
tab1, tab2, tab3 = st.tabs(["💧 Process", "🛠️ Mechanical", "🧪 Media"])

# =========================
# PROCESS
# =========================
with tab1:
    st.subheader("Process Load Distribution")

    data = filter_loading(total_flow, streams, n_filters, redundancy)

    df = pd.DataFrame([{
        "Scenario":          f"N-{x}" if x > 0 else "Normal (N)",
        "Active Filters":    a,
        "Flow/Filter (m³/h)": q
    } for x, a, q in data])

    st.table(df)

# =========================
# MECHANICAL  (enhanced)
# =========================
with tab2:
    st.subheader("Vessel Mechanical Sizing — ASME Section VIII Div. 1")

    mech = thickness(
        diameter_m=diameter,
        design_pressure_bar=design_pressure,
        material_name=material_name,
        shell_radio=shell_radio,
        head_radio=head_radio,
        corrosion_mm=corrosion,
        internal_lining_mm=internal_lining,
    )

    # ── Material & design parameters panel ──
    st.markdown("### Material Specifications")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Material Specifications**")
        df_mat = pd.DataFrame([
            ["Material of Shell/Head", material_name],
            ["Standard",               mat_info["standard"]],
            ["Allowable Stress (S)",   f"{mech['allowable_stress']} kg/cm²"],
            ["Description",            mat_info["description"]],
        ], columns=["Parameter", "Value"])
        st.table(df_mat)

        st.markdown("**Material & Joint Efficiency**")
        df_je = pd.DataFrame([
            ["Head Geometric Factor (K)", "1.0"],
            ["Radiography — Shell",       shell_radio],
            ["Shell Joint Efficiency (E)", f"{mech['shell_E']:.2f}"],
            ["Radiography — Head",        head_radio],
            ["Head Joint Efficiency (E)",  f"{mech['head_E']:.2f}"],
        ], columns=["Parameter", "Value"])
        st.table(df_je)

    with c2:
        st.markdown("**Design Parameters**")
        df_dp = pd.DataFrame([
            ["Design Pressure",      f"{design_pressure:.2f} bar  ({mech['p_kgf_cm2']:.2f} kg/cm²)"],
            ["Design Temperature",   f"{design_temp:.2f} °C"],
            ["Corrosion Allowance",  f"{corrosion:.1f} mm"],
            ["Internal Lining / R-L", f"{internal_lining:.1f} mm"],
        ], columns=["Parameter", "Value"])
        st.table(df_dp)

        st.markdown("**Design Thickness & Diameters**")
        df_th = pd.DataFrame([
            ["Cylinder min. Thickness",  f"{mech['t_shell_min_mm']:.2f} mm"],
            ["Shell Selected (+CA)",     f"{mech['t_shell_design_mm']} mm"],
            ["Head min. Thickness",      f"{mech['t_head_min_mm']:.2f} mm"],
            ["Head Selected (+CA)",      f"{mech['t_head_design_mm']} mm"],
            ["Internal Diameter (lined)", f"{mech['id_with_lining_m']:.4f} m"],
            ["Outside Diameter",          f"{mech['od_m']:.4f} m"],
        ], columns=["Parameter", "Value"])
        st.table(df_th)

    # ── Key metrics strip ──
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Shell t_min",    f"{mech['t_shell_min_mm']:.2f} mm")
    m2.metric("Shell t_design", f"{mech['t_shell_design_mm']} mm")
    m3.metric("Head t_min",     f"{mech['t_head_min_mm']:.2f} mm")
    m4.metric("Head t_design",  f"{mech['t_head_design_mm']} mm")

    # ── Empty weight — body ──────────────────────────────────────────────────
    st.divider()
    st.markdown("### ⚖️ Empty Weight — Vessel Body")
    st.caption("Shell plate + 2 dish ends · Nozzles, nozzle plate, strainers, legs and supports to be added in subsequent steps.")

    wt = empty_weight(
        diameter_m=diameter,
        straight_length_m=cyl_len,
        end_geometry=end_geometry,
        t_shell_mm=mech["t_shell_design_mm"],
        t_head_mm=mech["t_head_design_mm"],
        density_kg_m3=steel_density,
    )

    wa, wb = st.columns(2)

    with wa:
        st.markdown("**Cylindrical Shell**")
        df_ws = pd.DataFrame([
            ["Mean diameter",      f"{wt['d_mean_shell_m']:.4f} m"],
            ["Wall thickness",     f"{mech['t_shell_design_mm']} mm"],
            ["Lateral surface area", f"{wt['area_shell_m2']:.3f} m²"],
            ["Metal volume",       f"{wt['vol_shell_m3']:.4f} m³"],
            ["Shell weight",       f"{wt['weight_shell_kg']:,.1f} kg"],
        ], columns=["Item", "Value"])
        st.table(df_ws)

    with wb:
        st.markdown(f"**Dish Ends × 2  ({end_geometry})**")
        df_wh = pd.DataFrame([
            ["Mean diameter",          f"{wt['d_mean_head_m']:.4f} m"],
            ["Wall thickness",         f"{mech['t_head_design_mm']} mm"],
            ["Surface area (one head)", f"{wt['area_one_head_m2']:.3f} m²"],
            ["Metal volume (one head)", f"{wt['vol_one_head_m3']:.4f} m³"],
            ["Both heads weight",       f"{wt['weight_two_heads_kg']:,.1f} kg"],
        ], columns=["Item", "Value"])
        st.table(df_wh)

    # summary strip
    s1, s2, s3 = st.columns(3)
    s1.metric("Shell",       f"{wt['weight_shell_kg']:,.0f} kg")
    s2.metric("2 × Heads",   f"{wt['weight_two_heads_kg']:,.0f} kg")
    s3.metric("Body Total",  f"{wt['weight_body_t']:.3f} t",
              delta=f"{wt['weight_body_kg']:,.0f} kg", delta_color="off")

# =========================
# MEDIA
# =========================
with tab3:

    st.subheader("1️⃣ Geometric Volume Breakdown")

    geo_rows    = []
    base        = []
    curr_h      = nozzle_plate_height
    total_vol   = 0
    total_depth = 0

    if nozzle_plate_height > 0:
        geo_rows.append([
            "Nozzle Plate",
            nozzle_plate_height,
            segment_area(nozzle_plate_height, diameter),
            (segment_area(nozzle_plate_height, diameter) - segment_area(0, diameter)) * cyl_len,
            (dish_volume(nozzle_plate_height, diameter, h_dish, end_geometry) -
             dish_volume(0, diameter, h_dish, end_geometry)) * 2,
            ((segment_area(nozzle_plate_height, diameter) - segment_area(0, diameter)) * cyl_len) +
            ((dish_volume(nozzle_plate_height, diameter, h_dish, end_geometry) -
              dish_volume(0, diameter, h_dish, end_geometry)) * 2)
        ])

    for L in layers:
        h1 = curr_h
        h2 = curr_h + L["Depth"]

        v_cyl = (segment_area(h2, diameter) - segment_area(h1, diameter)) * cyl_len
        v_end = (dish_volume(h2, diameter, h_dish, end_geometry) -
                 dish_volume(h1, diameter, h_dish, end_geometry)) * 2

        vol  = v_cyl + v_end
        area = vol / L["Depth"] if L["Depth"] > 0 else 0

        base.append({**L, "Vol": vol, "Area": area})

        geo_rows.append([L["Type"], L["Depth"], area, v_cyl, v_end, vol])

        total_vol   += vol
        total_depth += L["Depth"]
        curr_h       = h2

    df_geo = pd.DataFrame(geo_rows, columns=[
        "Item", "Depth (m)", "Avg Area (m²)",
        "V_cyl (m³)", "V_ends (m³)", "Total Vol (m³)"
    ])

    st.table(df_geo.style.format({
        "Depth (m)":      "{:.3f}",
        "Avg Area (m²)":  "{:.2f}",
        "V_cyl (m³)":     "{:.2f}",
        "V_ends (m³)":    "{:.2f}",
        "Total Vol (m³)": "{:.2f}"
    }))

    # ── Media properties ──
    st.subheader("2️⃣ Media Properties")
    df = pd.DataFrame(base)
    df = df[["Type", "Depth", "Vol", "Area", "rho_p_eff", "epsilon0", "d10", "cu", "d60"]]
    df = df.rename(columns={
        "Type":      "Media",
        "Depth":     "Depth (m)",
        "Vol":       "Volume (m³)",
        "Area":      "Avg Area (m²)",
        "rho_p_eff": "Density (kg/m³)",
        "epsilon0":  "Voidage",
        "d10":       "d10 (mm)",
        "cu":        "CU",
        "d60":       "d60 (mm)"
    })
    st.table(df.style.format({
        "Depth (m)":      "{:.3f}",
        "Volume (m³)":    "{:.2f}",
        "Avg Area (m²)":  "{:.2f}",
    }))

    # ── Performance ──
    st.subheader("3️⃣ Performance")

    for x in range(redundancy + 1):
        active = n_filters - x
        q = (total_flow / streams) / active if active > 0 else 0

        st.markdown(f"### Scenario {'N' if x==0 else f'N-{x}'}")

        rows = []
        for b in base:
            vel  = q / b["Area"] if b["Area"] > 0 else 0
            ebct = (b["Vol"] / q) * 60 if q > 0 else 0
            rows.append({"Layer": b["Type"], "Velocity (m/h)": vel, "EBCT (min)": ebct})

        st.table(pd.DataFrame(rows))

        warnings_list = []
        for r in rows:
            if r["Velocity (m/h)"] > velocity_threshold:
                warnings_list.append({
                    "Media": r["Layer"], "Parameter": "Velocity",
                    "Value": f"{r['Velocity (m/h)']:.2f} m/h",
                    "Threshold": f"{velocity_threshold:.2f} m/h", "Status": "⚠️ EXCEEDS"
                })
            if r["EBCT (min)"] < ebct_threshold:
                warnings_list.append({
                    "Media": r["Layer"], "Parameter": "EBCT",
                    "Value": f"{r['EBCT (min)']:.2f} min",
                    "Threshold": f"{ebct_threshold:.2f} min", "Status": "⚠️ BELOW"
                })

        if warnings_list:
            st.warning("**Performance Alerts**")
            st.dataframe(pd.DataFrame(warnings_list), use_container_width=True, hide_index=True)

    # ── Inventory ──
    st.divider()
    st.subheader("📦 Final Media Inventory")

    total_vessels      = streams * n_filters
    inv_rows           = []
    total_project_mass = 0

    for b in base:
        mass_per_filter = b["Vol"] * b["rho_p_eff"]
        mass_total      = mass_per_filter * total_vessels
        total_project_mass += mass_total

        inv_rows.append({
            "Media":                 b["Type"],
            "Spec (d10/CU)":         f"{b['d10']} / {b['cu']}",
            "Volume / Filter (m³)":  b["Vol"],
            "Mass / Filter (kg)":    mass_per_filter,
            "Total Mass (kg)":       mass_total
        })

    df_inv = pd.DataFrame(inv_rows)
    st.table(df_inv.style.format({
        "Volume / Filter (m³)": "{:.2f}",
        "Mass / Filter (kg)":   "{:.0f}",
        "Total Mass (kg)":      "{:.0f}"
    }))

    # ── Summary ──
    col1, col2 = st.columns(2)

    with col1:
        st.write("### 🏗️ Project Summary")
        st.write(f"- Total Filters: {total_vessels}")
        st.write(f"- Total Media Weight: {total_project_mass/1000:.2f} Tons")
        st.write(f"- Redundancy: N to N-{redundancy}")

    with col2:
        st.write("### 🖋️ Sign-Off")
        st.info("""
Islam Shahine
Process Expert

AQUASIGHT™
        """)

st.caption("AQUASIGHT™ | Proprietary Tool")