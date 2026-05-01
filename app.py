import streamlit as st
import math

default_media_presets = {
    "Custom": {"d10": 0.0, "cu": 1.0},
    "Fine Sand": {"d10": 0.25, "cu": 1.6},
    "Medium Sand": {"d10": 0.50, "cu": 1.8},
    "Coarse Sand": {"d10": 0.85, "cu": 2.0},
    "Anthracite": {"d10": 1.20, "cu": 1.5},
    "Gravel": {"d10": 2.50, "cu": 1.4},
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
            preset = st.selectbox(
                f"Media Preset for layer {layer_index + 1}",
                list(media_presets.keys()),
                index=0,
                key=f"preset_{layer_index}"
            )
            if preset == "Custom":
                media_type = st.text_input(
                    f"Custom Media Type {layer_index + 1}",
                    value=f"Custom Layer {layer_index + 1}",
                    key=f"media_type_{layer_index}"
                )
            else:
                media_type = preset

            default_d10 = media_presets[preset]["d10"]
            default_cu = media_presets[preset]["cu"]

            d10 = st.number_input(
                f"d10 (mm) for layer {layer_index + 1}",
                min_value=0.0,
                value=default_d10,
                step=0.01,
                key=f"d10_{layer_index}"
            )
            cu = st.number_input(
                f"Uniformity Coefficient (Cu) for layer {layer_index + 1}",
                min_value=1.0,
                value=default_cu,
                step=0.1,
                key=f"cu_{layer_index}"
            )
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
                "Cu": cu,
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
media_layer_tops = []
current_top = nozzle_plate_height
for depth in media_depths:
    media_layer_tops.append(current_top)
    current_top += depth

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
        for i, layer in enumerate(media_layers_data):
            details.append({
                "Layer": layer["Layer"],
                "Type": layer["Type"],
                "Top from Plate (m)": f"{media_layer_tops[i]:.2f}",
                "Depth (m)": f"{layer['Depth (m)']:.2f}",
                "d10 (mm)": f"{layer['d10 (mm)']:.2f}",
                "Cu": f"{layer['Cu']:.2f}",
            })
        st.table(details)

    st.info(f"Design based on Diameter: {diameter}m, Total Length: {total_length}m, End Geometry: {end_geometry} at {design_pressure} bar using {allowable_stress} kg/cm² allowable stress.")

# 5. FOOTER & SECURITY
st.markdown("---")
st.caption("Proprietary Tool © Islam Shahine | Process Expert | Veolia. Unauthorized distribution of results is prohibited.")
