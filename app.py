import streamlit as st
import math

# 1. Page Configuration
st.set_page_config(page_title="VWT Process Calculator", layout="centered")

st.title("??? Secure MMF Sizing Tool")
st.write("Enter your parameters below to calculate filtration rates.")

# 2. Inputs (Mimicking your Sheet1)
with st.sidebar:
    st.header("Input Parameters")
    total_flow = st.number_input("Total Flow (m3/h)", value=21000.0)
    streams = st.number_input("Number of Streams", value=1)
    filters_per_stream = st.number_input("Filters per Stream", value=16)
    diameter = st.number_input("Vessel Diameter (m)", value=5.5)

# 3. The "Secret" Calculations (Locked inside the app)
# These represent the logic found in 'Sheet1' and 'Media1_calc'
flow_per_stream = total_flow / streams
normal_flow = flow_per_stream / filters_per_stream
area_center = (math.pi * (diameter**2)) / 4
filtration_rate = normal_flow / area_center

# 4. Results Display
st.subheader("Calculation Results")
col1, col2 = st.columns(2)

with col1:
    st.metric("Normal Flow per Filter", f"{normal_flow:.2f} m3/h")
    st.metric("Filtration Area", f"{area_center:.2f} m2")

with col2:
    st.metric("Filtration Rate (N)", f"{filtration_rate:.2f} m/h")
    
# Warning if rate is too high (Engineering safety)
if filtration_rate > 12:
    st.error("?? Warning: Filtration rate exceeds standard limits!")