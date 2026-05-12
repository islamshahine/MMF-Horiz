"""ui/config.py — Page configuration for AQUASIGHT™ MMF."""
import streamlit as st


def setup_page() -> None:
    st.set_page_config(
        page_title="AQUASIGHT™ MMF",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
