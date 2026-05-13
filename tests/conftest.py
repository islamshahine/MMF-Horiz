"""
tests/conftest.py
─────────────────
Shared pytest fixtures for AQUASIGHT™ MMF test suite.
Provides reference inputs and computed values for
use across all test modules.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def standard_layers():
    """Three-layer MMF: Gravel / Fine Sand / Anthracite."""
    return [
        {
            "Type": "Gravel",     "Depth": 0.20, "epsilon0": 0.46,
            "d10": 6.0, "cu": 1.0, "rho_p_eff": 2600,
            "psi": 0.90, "is_porous": False, "is_support": True,
        },
        {
            "Type": "Fine Sand",  "Depth": 0.80, "epsilon0": 0.42,
            "d10": 0.8, "cu": 1.3, "rho_p_eff": 2650,
            "psi": 0.80, "is_porous": False, "is_support": False,
        },
        {
            "Type": "Anthracite", "Depth": 0.80, "epsilon0": 0.48,
            "d10": 1.3, "cu": 1.5, "rho_p_eff": 1450,
            "psi": 0.70, "is_porous": False, "is_support": False,
        },
    ]


@pytest.fixture
def standard_water():
    """Seawater at 27°C, 35 ppt."""
    return {"temp_c": 27.0, "salinity_ppt": 35.0}


@pytest.fixture
def standard_vessel():
    """Typical horizontal MMF vessel."""
    return {
        "nominal_id":   5.5,
        "total_length": 24.3,
        "cyl_len":      21.55,
        "h_dish":       1.375,
        "lining_mm":    4.0,
        "real_id":      5.492,
        "end_geometry": "Elliptic 2:1",
    }
