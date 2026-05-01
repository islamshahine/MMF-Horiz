import streamlit as st
import math

default_media_presets = {
    "Custom": {
        "d10": 0.0,
        "cu": 1.0,
        "epsilon0": 0.0,
        "rho_p_eff": 0,
        "d60": 0.0,
        "psi": 0.0,
        "phi": 0,
    },
    "Gravel": {
        "d10": 6,
        "cu": 0,
        "epsilon0": 0.46,
        "rho_p_eff": 2600,
        "d60": None,
        "psi": 0.9,
        "phi": 35,
    },
    "Coarse Sand": {
        "d10": 1.35,
        "cu": 1.5,
        "epsilon0": 0.44,
        "rho_p_eff": 2650,
        "d60": 2.03,
        "psi": 0.85,
        "phi": 35,
    },
    "Fine Sand": {
        "d10": 0.8,
        "cu": 1.3,
        "epsilon0": 0.42,
        "rho_p_eff": 2650,
        "d60": 1.2,
        "psi": 0.8,
        "phi": 35,
    },
    "Fine Sand (extra)": {
        "d10": 0.5,
        "cu": 1.3,
        "epsilon0": 0.41,
        "rho_p_eff": 2650,
        "d60": 0.9,
        "psi": 0.75,
        "phi": 35,
    },
    "MnO2": {
        "d10": 1,
        "cu": 2.4,
        "epsilon0": 0.5,
        "rho_p_eff": 4200,
        "d60": 2.4,
        "psi": 0.65,
        "phi": 35,
    },
    "Medium GAC": {
        "d10": 1,
        "cu": 1.6,
        "epsilon0": 0.55,
        "rho_p_eff": 1000,
        "d60": 1.44,
        "psi": 0.65,
        "phi": 35,
    },
    "Anthracite": {
        "d10": 1.3,
        "cu": 1.5,
        "epsilon0": 0.48,
        "rho_p_eff": 1450,
        "d60": 2.25,
        "psi": 0.7,
        "phi": 35,
    },
    "Biodagene": {
        "d10": 2.5,
        "cu": 1.4,
        "epsilon0": 0.42,
        "rho_p_eff": 1600,
        "d60": 3.5,
        "psi": 0.8,
        "phi": 35,
    },
    "Schist": {
        "d10": 3.3,
        "cu": 1.5,
        "epsilon0": 0.47,
        "rho_p_eff": 1300,
        "d60": 4.95,
        "psi": 0.65,
        "phi": 35,
    },
    "Limestone": {
        "d10": 3,
        "cu": 1.4,
        "epsilon0": 0.55,
        "rho_p_eff": 2700,
        "d60": 4.2,
        "psi": 0.6,
        "phi": 35,
    },
    "Pumice": {
        "d10": 1.5,
        "cu": 1.3,
        "epsilon0": 0.55,
        "rho_p_eff": 900,
        "d60": 1.56,
        "psi": 0.55,
        "phi": 35,
    },
    "FILTRALITE clay": {
        "d10": 1.2,
        "cu": 1.5,
        "epsilon0": 0.48,
        "rho_p_eff": 1250,
        "d60": 1.8,
        "psi": 0.5,
        "phi": 35,
    },
}

if "media_presets" not in st.session_state:
    st.session_state.media_presets = default_media_presets.copy()

# 1. PAGE SETUP
st.set_page_config(page_title="VWT Process & Mechanical Calculator", layout="wide")

# Custom CSS to make it look like a professional tool
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); color: #000000; }
    .stMetric *, .stMetric div, .stMetric span, .stMetric p { color: #000000 !important; }
    .stMetric .css-1v0mbdj.e16nr0p30, .stMetric .css-1v0mbdj.e16nr0p30 span { color: #000000 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ Secure MMF Sizing & Vessel Design Tool")
st.write("Professional Water Treatment Engineering Suite — Proprietary Logic Engine")

# 2. SIDEBAR INPUTS (Based on EXXXX-VWT-PCS-CAL-2001)
with st.sidebar:
    st.header("📥 Process Parameters")
    total_flow = st.number_input("Total Flow (m³/h)", value=21000.0, step=100.0)
    streams = st.number_input("Number of Streams", value=1, min_value=1)
    filters_per_stream = st.number_input("Filters per Stream (N)", value=16, min_value=1)
    
    st.header("🏗️ Vessel Geometry")
    diameter = st.number_input("Filter Diameter (m)", value=5.5, step=0.1)
    total_length = st.number_input("Total Length (m)", value=21.55, step=0.1)
    end_geometry = st.selectbox("End Geometry", ["Elliptic 2:1", "Torispherical 10%"])

    st.header("🧱 Internal Fill")
    nozzle_plate_min_height = 0.8
    nozzle_plate_max_height = diameter / 3
    if nozzle_plate_max_height < nozzle_plate_min_height:
        nozzle_plate_max_height = nozzle_plate_min_height
        nozzle_plate_help = (
            "Diameter is smaller than 2.4 m, so the nozzle plate height is fixed at the minimum 0.8 m."
        )
    else:
        nozzle_plate_help = f"Space for nozzle/strainer plate. Min 0.8 m, max D/3 = {diameter/3:.2f} m."

    nozzle_plate_height = st.number_input(
        "Nozzle Plate Height (m)",
        min_value=nozzle_plate_min_height,
        max_value=nozzle_plate_max_height,
        value=min(1.0, nozzle_plate_max_height),
        step=0.05,
        help=nozzle_plate_help,
    )
    media_layers = st.selectbox("Number of Media Layers", [1, 2, 3, 4, 5, 6], index=0)

    media_layers_data = []
    d10_values = []
    cu_values = []
    media_depths = []

    for layer_index in range(media_layers):
        with st.expander(f"Media Layer {layer_index + 1}"):
            preset_key = f"preset_{layer_index}"
            preset = st.selectbox(
                f"Media Preset for layer {layer_index + 1}",
                list(st.session_state.media_presets.keys()),
                index=0,
                key=preset_key,
            )

            is_custom = preset == "Custom"
            if is_custom:
                media_type = st.text_input(
                    f"Custom Media Type {layer_index + 1}",
                    value=f"Custom Layer {layer_index + 1}",
                    key=f"media_type_{layer_index}"
                )
                st.info("Custom media: edit values below.")
            else:
                media_type = preset
                st.info(f"Preset: {preset}")

            preset_data = st.session_state.media_presets[preset]
            d10 = float(preset_data["d10"])
            cu = float(preset_data["cu"])
            epsilon0 = float(preset_data["epsilon0"])
            rho_p_eff = int(preset_data["rho_p_eff"])
            d60 = float(preset_data["d60"]) if preset_data["d60"] is not None else 0.0
            psi = float(preset_data["psi"])
            phi = int(preset_data["phi"])

            if is_custom:
                col1, col2 = st.columns(2)
                with col1:
                    d10 = st.number_input(
                        f"d10 (mm) for layer {layer_index + 1}",
                        min_value=0.0,
                        value=d10,
                        step=0.01,
                        key=f"d10_input_{layer_index}"
                    )
                    cu = st.number_input(
                        f"Uniformity Coefficient (Cu) for layer {layer_index + 1}",
                        min_value=0.0,
                        value=cu,
                        step=0.1,
                        key=f"cu_input_{layer_index}"
                    )
                    d60 = st.number_input(
                        f"d60 (mm) for layer {layer_index + 1}",
                        min_value=0.0,
                        value=d60,
                        step=0.01,
                        key=f"d60_input_{layer_index}"
                    )
                with col2:
                    epsilon0 = st.number_input(
                        f"Void Fraction (ε₀) for layer {layer_index + 1}",
                        min_value=0.0,
                        max_value=1.0,
                        value=epsilon0,
                        step=0.01,
                        key=f"epsilon0_input_{layer_index}"
                    )
                    rho_p_eff = st.number_input(
                        f"Effective Density ρp,eff (kg/m³) for layer {layer_index + 1}",
                        min_value=0,
                        value=rho_p_eff,
                        step=10,
                        key=f"rho_p_eff_input_{layer_index}"
                    )
                    psi = st.number_input(
                        f"Sphericity (ψ) for layer {layer_index + 1}",
                        min_value=0.0,
                        max_value=1.0,
                        value=psi,
                        step=0.01,
                        key=f"psi_input_{layer_index}"
                    )

                phi = st.number_input(
                    f"Friction Angle φ (°) for layer {layer_index + 1}",
                    min_value=0,
                    max_value=90,
                    value=phi,
                    step=1,
                    key=f"phi_input_{layer_index}"
                )
            else:
                col1, col2 = st.columns(2)
                with col1:
                    col1.markdown(f"<div style='font-size:14px; line-height:1.4;'><strong>d10 (mm)</strong><br>{d10:.2f}</div>", unsafe_allow_html=True)
                    col1.markdown(f"<div style='font-size:14px; line-height:1.4;'><strong>Uniformity Coefficient (Cu)</strong><br>{cu:.2f}</div>", unsafe_allow_html=True)
                    col1.markdown(f"<div style='font-size:14px; line-height:1.4;'><strong>d60 (mm)</strong><br>{d60:.2f}</div>", unsafe_allow_html=True)
                with col2:
                    col2.markdown(f"<div style='font-size:14px; line-height:1.4;'><strong>Void Fraction (ε₀)</strong><br>{epsilon0:.2f}</div>", unsafe_allow_html=True)
                    col2.markdown(f"<div style='font-size:14px; line-height:1.4;'><strong>Effective Density ρp,eff (kg/m³)</strong><br>{rho_p_eff}</div>", unsafe_allow_html=True)
                    col2.markdown(f"<div style='font-size:14px; line-height:1.4;'><strong>Sphericity (ψ)</strong><br>{psi:.2f}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:14px; line-height:1.4;'><strong>Friction Angle φ (°)</strong><br>{phi}</div>", unsafe_allow_html=True)

            depth = st.number_input(
                f"Depth from previous top (m) for layer {layer_index + 1}",
                min_value=0.0,
                value=0.5,
                step=0.05,
                key=f"depth_{layer_index}"
            )

            d10_values.append(d10)
            cu_values.append(cu)
            media_depths.append(depth)
            media_layers_data.append({
                "Layer": layer_index + 1,
                "Type": media_type,
                "d10 (mm)": d10,
                "d60 (mm)": d60,
                "Cu": cu,
                "ε₀": epsilon0,
                "ρp,eff (kg/m³)": rho_p_eff,
                "ψ": psi,
                "φ (°)": phi,
                "Depth (m)": depth,
            })

    st.header("⚙️ Mechanical Design")
    design_pressure = st.number_input("Design Pressure (bar)", value=7.0, step=0.5)
    allowable_stress = st.number_input("Allowable Stress (kg/cm²)", value=1200, help="ASTM Standard Material")
    corrosion_allowance = st.number_input("Corrosion Allowance (mm)", value=1.5, step=0.1)
    joint_efficiency = st.slider("Joint Efficiency (η)", 0.6, 1.0, 0.85)

# 3. CORE LOGIC ENGINE (Hidden from users)
# Calculate cylindrical length based on end geometry
if end_geometry == "Elliptic 2:1":
    h = diameter / 4
    end_area = (math.pi / 2) * (diameter / 2) * h
elif end_geometry == "Torispherical 10%":
    h = 0.2 * diameter
    end_area = 0.2 * (math.pi / 4) * diameter**2
cylindrical_length = total_length - 2 * h

# --- Process Sizing ---
flow_per_stream = total_flow / streams
normal_flow_filter = flow_per_stream / filters_per_stream
filter_area = cylindrical_length * diameter + 2 * end_area
filtration_rate_n = normal_flow_filter / filter_area

# Redundancy Calculation (N-1)
filters_online_n_minus_1 = (streams * filters_per_stream) - 1
rate_n_minus_1 = total_flow / (filters_online_n_minus_1 * filter_area)

# --- Mechanical Sizing ---
# Formula for shell thickness (P*R)/(S*E - 0.6*P) + Corrosion
p_kg = design_pressure * 1.01972 # bar to kg/cm2
r_cm = (diameter * 100) / 2
t_min_shell = (p_kg * r_cm) / (allowable_stress * joint_efficiency - 0.6 * p_kg)
selected_thickness = math.ceil(t_min_shell * 10 + corrosion_allowance) # converted to mm

# Vessel volume
cylindrical_volume = math.pi * (diameter / 2) ** 2 * cylindrical_length

# Internal fill summary
media_total_depth = sum(media_depths)
available_internal_height = cylindrical_length - nozzle_plate_height
remaining_internal_height = available_internal_height - media_total_depth

R = diameter / 2

# theta and area helper functions
def theta_at_height(height_m: float) -> tuple[float, float]:
    value = (R - height_m) / R
    value = max(-1.0, min(1.0, value))
    theta_rad = 2 * math.acos(value)
    return theta_rad, math.degrees(theta_rad)


def circular_segment_area(theta_rad: float) -> float:
    return 0.5 * R**2 * (theta_rad - math.sin(theta_rad))


def elliptical_cap_volume(height_m: float) -> float:
    dish_h = diameter / 4
    h = max(0.0, min(height_m, dish_h))
    a = R
    b = dish_h
    return math.pi * a**2 * b * (1 - (1 - h / b) ** 2 * (2 + h / b)) / 3


def spherical_cap_volume(height_m: float) -> float:
    dish_h = 0.2 * diameter
    h = max(0.0, min(height_m, dish_h))
    return math.pi * h**2 * (R - h / 3)


# 4. DASHBOARD LAYOUT
tab1, tab2 = st.tabs(["💧 Process Results", "🛠️ Mechanical Design"])

with tab1:
    st.subheader("Filtration Performance")
    col1, col2, col3 = st.columns(3)
    col1.metric("Flow per Filter", f"{normal_flow_filter:.2f} m³/h")
    col2.metric("Effective Filtration Area", f"{filter_area:.2f} m²")
    col3.metric("Filtration Rate (N)", f"{filtration_rate_n:.2f} m/h")

    st.markdown(f"**Dish End Area per End:** {end_area:.2f} m² | **Middle length:** {cylindrical_length:.2f} m")

    st.subheader("Redundancy Analysis")
    st.metric("Filtration Rate (N-1)", f"{rate_n_minus_1:.2f} m/h", 
              delta=f"{rate_n_minus_1 - filtration_rate_n:.2f} increase", delta_color="inverse")
    
    if rate_n_minus_1 > 12.0:
        st.warning("⚠️ Warning: N-1 Filtration rate exceeds 12 m/h. Check design limits.")

with tab2:
    st.subheader("Vessel Construction Requirements")
    m_col1, m_col2 = st.columns(2)
    m_col1.metric("Min. Cylinder Thickness", f"{t_min_shell:.2f} mm")
    m_col2.metric("Recommended Thickness", f"{selected_thickness} mm", help="Includes corrosion allowance")
    
    st.subheader("Vessel Dimensions")
    d_col1, d_col2 = st.columns(2)
    d_col1.metric("Cylindrical Length", f"{cylindrical_length:.2f} m")
    d_col2.metric("Cylindrical Volume", f"{cylindrical_volume:.2f} m³")

    st.subheader("Internal Fill Summary")
    f_col1, f_col2 = st.columns(2)
    f_col1.metric("Nozzle Plate Height", f"{nozzle_plate_height:.2f} m")
    f_col2.metric("Available Internal Height", f"{available_internal_height:.2f} m")
    f_col3, f_col4 = st.columns(2)
    f_col3.metric("Total Media Depth", f"{media_total_depth:.2f} m")
    f_col4.metric("Remaining Free Height", f"{remaining_internal_height:.2f} m")

    if remaining_internal_height < 0:
        st.error("Internal fill depth exceeds available internal height. Reduce media depth or nozzle plate height.")

    if media_layers_data:
        st.subheader("Media Layer Details")
        details = []
        current_top = 0.0
        for layer in media_layers_data:
            top = current_top
            depth = layer["Depth (m)"]
            bottom = top + depth
            top_abs = nozzle_plate_height + top
            bottom_abs = nozzle_plate_height + bottom

            theta_bottom_rad, theta_bottom_deg = theta_at_height(bottom_abs)
            theta_top_rad, _ = theta_at_height(top_abs)
            area_bottom = circular_segment_area(theta_bottom_rad)
            area_top = circular_segment_area(theta_top_rad)
            layer_area = max(0.0, area_bottom - area_top)

            v_cyl = layer_area * cylindrical_length

            def dish_volume(depth_mm: float) -> float:
                factor = (1/3) if end_geometry == "Elliptic 2:1" else (4/15)
                return factor * (math.pi / 4) * diameter**2 * depth_mm / 1000

            prev_depth_mm = top_abs * 1000
            curr_depth_mm = bottom_abs * 1000
            v_end = max(0.0, dish_volume(curr_depth_mm) - dish_volume(prev_depth_mm))

            details.append({
                "Layer": layer["Layer"],
                "Type": layer["Type"],
                "Top (m)": f"{top:.2f}",
                "Depth (m)": f"{depth:.2f}",
                "θ (°)": f"{theta_bottom_deg:.2f}",
                "Circ. Area (m²)": f"{layer_area:.2f}",
                "Vsph/Elli (m³)": f"{v_end:.2f}",
                "Vcyl (m³)": f"{v_cyl:.2f}",
                "Vtot (m³)": f"{(v_end + v_cyl):.2f}",
            })
            current_top += depth
        st.table(details)

    st.info(f"Design based on Diameter: {diameter}m, Total Length: {total_length}m, End Geometry: {end_geometry} at {design_pressure} bar using {allowable_stress} kg/cm² allowable stress.")

# 5. FOOTER & SECURITY
st.markdown("---")
st.caption("Proprietary Tool © Islam Shahine | Process Expert |. Unauthorized distribution of results is prohibited.")
