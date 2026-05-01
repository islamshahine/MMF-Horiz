import streamlit as st
import math

# 1. PAGE SETUP
st.set_page_config(page_title="VWT Process & Mechanical Calculator", layout="wide")

# Custom CSS to make it look like a professional tool
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
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
    diameter = st.number_input("Inside Diameter (m)", value=5.5, step=0.1)
    straight_length = st.number_input("Straight Length (m)", value=21.55, step=0.1)
    
    st.header("⚙️ Mechanical Design")
    design_pressure = st.number_input("Design Pressure (bar)", value=7.0, step=0.5)
    allowable_stress = st.number_input("Allowable Stress (kg/cm²)", value=1200, help="ASTM Standard Material")
    corrosion_allowance = st.number_input("Corrosion Allowance (mm)", value=1.5, step=0.1)
    joint_efficiency = st.slider("Joint Efficiency (η)", 0.6, 1.0, 0.85)

# 3. CORE LOGIC ENGINE (Hidden from users)
# --- Process Sizing ---
flow_per_stream = total_flow / streams
normal_flow_filter = flow_per_stream / filters_per_stream
area_per_filter = (math.pi * (diameter**2)) / 4
filtration_rate_n = normal_flow_filter / area_per_filter

# Redundancy Calculation (N-1)
filters_online_n_minus_1 = (streams * filters_per_stream) - 1
rate_n_minus_1 = total_flow / (filters_online_n_minus_1 * area_per_filter)

# --- Mechanical Sizing ---
# Formula for shell thickness (P*R)/(S*E - 0.6*P) + Corrosion
p_kg = design_pressure * 1.01972 # bar to kg/cm2
r_cm = (diameter * 100) / 2
t_min_shell = (p_kg * r_cm) / (allowable_stress * joint_efficiency - 0.6 * p_kg)
selected_thickness = math.ceil(t_min_shell * 10 + corrosion_allowance) # converted to mm

# 4. DASHBOARD LAYOUT
tab1, tab2 = st.tabs(["💧 Process Results", "🛠️ Mechanical Design"])

with tab1:
    st.subheader("Filtration Performance")
    col1, col2, col3 = st.columns(3)
    col1.metric("Flow per Filter", f"{normal_flow_filter:.2f} m³/h")
    col2.metric("Filter Area", f"{area_per_filter:.2f} m²")
    col3.metric("Filtration Rate (N)", f"{filtration_rate_n:.2f} m/h")

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
    
    st.info(f"Design based on Diameter: {diameter}m at {design_pressure} bar using {allowable_stress} kg/cm² allowable stress.")

# 5. FOOTER & SECURITY
st.markdown("---")
st.caption("Proprietary Tool © Islam Shahine | Process Expert | Veolia. Unauthorized distribution of results is prohibited.")
