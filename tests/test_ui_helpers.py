"""UI helper display utilities (no Streamlit runtime)."""

from ui.helpers import clogging_pct_display, pressure_drop_layers_display_frames


def test_clogging_pct_display_mixed_types():
    assert clogging_pct_display("—") == "—"
    assert clogging_pct_display(12.34) == "12.3"
    assert clogging_pct_display(None) == "—"


def test_pressure_drop_clogging_column_is_string():
    rows = [
        {
            "Media": "Gravel",
            "Support": "Yes",
            "Capture (%)": 0,
            "Solid load (kg/m²)": 0.0,
            "Solid vol (m³/m²)": 0.0,
            "ΔεF": 0.0,
            "Clogging (%)": "—",
            "Depth (m)": 0.3,
            "LV (m/h)": 0.0,
            "ε clean": 0.4,
            "ΔP clean (bar)": 0.01,
            "Cake ΔP mod (bar)": 0.0,
            "Cake ΔP dirty (bar)": 0.0,
            "ΔP mod total (bar)": 0.01,
            "ΔP dirty total (bar)": 0.02,
        },
        {
            "Media": "Sand",
            "Support": "No",
            "Capture (%)": 100,
            "Solid load (kg/m²)": 1.0,
            "Solid vol (m³/m²)": 0.001,
            "ΔεF": 0.01,
            "Clogging (%)": 15.2,
            "Depth (m)": 0.5,
            "LV (m/h)": 8.0,
            "ε clean": 0.42,
            "ΔP clean (bar)": 0.05,
            "Cake ΔP mod (bar)": 0.02,
            "Cake ΔP dirty (bar)": 0.03,
            "ΔP mod total (bar)": 0.07,
            "ΔP dirty total (bar)": 0.08,
        },
    ]
    _full, clog = pressure_drop_layers_display_frames(rows)
    assert clog["Clogging (%)"].dtype == object
    assert clog["Clogging (%)"].tolist() == ["—", "15.2"]
