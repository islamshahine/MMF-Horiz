"""Default media catalogue for layer presets (Streamlit session seed).

Used by ``app.py`` and ``ui/sidebar.py`` so preset keys and physics defaults stay in sync.
"""

from __future__ import annotations


def eps0_from_psi(psi: float) -> float:
    """Empirical estimate: ε₀ ≈ 0.4 + 0.1·(1−ψ)/ψ  (Kozeny-based, random packing)."""
    return round(0.4 + 0.1 * (1.0 - psi) / max(psi, 0.01), 3)


def rho_eff_porous(rho_dry: float, eps_p: float, rho_water: float = 1025.0) -> float:
    """Water-saturated particle density for porous media.

    ρ_eff = ρ_dry + ρ_water × ε_p
    where ρ_dry is apparent dry-particle density and ε_p is internal particle porosity.
    """
    return rho_dry + rho_water * eps_p


# Fields: d10 (mm), cu (CU=d60/d10), epsilon0, rho_p_eff (kg/m³), d60 (mm),
#         psi (sphericity), is_porous, default_depth (m)
DEFAULT_MEDIA_PRESETS: dict[str, dict] = {
    "Gravel":            {"d10": 6.0,  "cu": 1.0, "epsilon0": 0.46, "psi": 0.90,
                          "rho_p_eff": 2600, "d60": 6.00, "is_porous": False, "default_depth": 0.20},
    "Coarse sand":       {"d10": 1.35, "cu": 1.5, "epsilon0": 0.44, "psi": 0.85,
                          "rho_p_eff": 2650, "d60": 2.03, "is_porous": False, "default_depth": 0.60},
    "Fine sand":         {"d10": 0.80, "cu": 1.3, "epsilon0": 0.42, "psi": 0.80,
                          "rho_p_eff": 2650, "d60": 1.04, "is_porous": False, "default_depth": 0.80},
    "Fine sand (extra)": {"d10": 0.50, "cu": 1.3, "epsilon0": 0.41, "psi": 0.75,
                          "rho_p_eff": 2650, "d60": 0.65, "is_porous": False, "default_depth": 0.70},
    "Anthracite":        {"d10": 1.30, "cu": 1.5, "epsilon0": 0.48, "psi": 0.70,
                          "rho_p_eff": 1450, "d60": 2.25, "is_porous": False, "default_depth": 0.80},
    "Garnet":            {"d10": 0.30, "cu": 1.3, "epsilon0": 0.38, "psi": 0.80,
                          "rho_p_eff": 4100, "d60": 0.39, "is_porous": False, "default_depth": 0.10},
    "MnO₂":             {"d10": 1.00, "cu": 2.4, "epsilon0": 0.50, "psi": 0.65,
                          "rho_p_eff": 4200, "d60": 2.40, "is_porous": False, "default_depth": 0.40},
    "Medium GAC":        {"d10": 1.00, "cu": 1.6, "epsilon0": 0.55, "psi": 0.65,
                          "rho_p_eff": 1000, "d60": 1.44, "is_porous": True,  "default_depth": 1.00},
    "Biodagene":         {"d10": 2.50, "cu": 1.4, "epsilon0": 0.42, "psi": 0.80,
                          "rho_p_eff": 1600, "d60": 3.50, "is_porous": False, "default_depth": 0.60},
    "Schist":            {"d10": 3.30, "cu": 1.5, "epsilon0": 0.47, "psi": 0.65,
                          "rho_p_eff": 1300, "d60": 4.95, "is_porous": False, "default_depth": 0.30},
    "Limestone":         {"d10": 3.00, "cu": 1.4, "epsilon0": 0.55, "psi": 0.60,
                          "rho_p_eff": 2700, "d60": 4.20, "is_porous": False, "default_depth": 0.50},
    "Pumice":            {"d10": 1.50, "cu": 1.3, "epsilon0": 0.55, "psi": 0.55,
                          "rho_p_eff":  900, "d60": 1.56, "is_porous": True,  "default_depth": 0.60},
    "FILTRALITE clay":   {"d10": 1.20, "cu": 1.5, "epsilon0": 0.48, "psi": 0.50,
                          "rho_p_eff": 1250, "d60": 1.80, "is_porous": True,  "default_depth": 0.80},
    "Custom":            {"d10": 0.0,  "cu": 1.5, "epsilon0": 0.42, "psi": 0.80,
                          "rho_p_eff": 2650, "d60": 0.0,  "is_porous": False, "default_depth": 0.50},
}
