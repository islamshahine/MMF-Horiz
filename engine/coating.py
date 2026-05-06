"""
engine/coating.py
─────────────────
Internal surface area calculation and lining / coating cost estimation
for horizontal pressure vessels.

Protection types
----------------
1. None         — bare steel (or external paint only)
2. Rubber       — bonded rubber lining; affects hydraulic ID (2 × thickness)
3. Epoxy        — paint-grade or high-build epoxy; negligible ID impact
4. Ceramic      — ceramic-filled or tile lining; negligible ID impact

Surface areas covered
---------------------
• Cylinder (shell)
• Two dish ends
• Nozzle plate (internal face, exposed to process fluid)
"""

import math

# ── Rubber lining types ──────────────────────────────────────────────────────
RUBBER_TYPES = {
    "Natural rubber":  {"density_kg_m3": 1100, "default_cost_m2": 35, "hardness": "40–50 Shore A"},
    "EPDM":            {"density_kg_m3": 1150, "default_cost_m2": 45, "hardness": "45–55 Shore A"},
    "Neoprene":        {"density_kg_m3": 1230, "default_cost_m2": 55, "hardness": "50–60 Shore A"},
    "Butyl rubber":    {"density_kg_m3": 1200, "default_cost_m2": 65, "hardness": "40–55 Shore A"},
    "Ebonite (hard)":  {"density_kg_m3": 1300, "default_cost_m2": 80, "hardness": "85–90 Shore A"},
}

# ── Epoxy coating types ───────────────────────────────────────────────────────
EPOXY_TYPES = {
    "Standard epoxy (2-pack)": {
        "density_kg_m3": 1400,
        "default_dft_um": 250,
        "default_coats": 2,
        "default_cost_m2": 8,
        "note": "General service; BS 6920 / NSF 61 potable water approved variants available.",
    },
    "High-build epoxy": {
        "density_kg_m3": 1450,
        "default_dft_um": 350,
        "default_coats": 2,
        "default_cost_m2": 12,
        "note": "DFT 300–500 µm; good for seawater service and mildly abrasive slurries.",
    },
    "Novolac epoxy": {
        "density_kg_m3": 1480,
        "default_dft_um": 400,
        "default_coats": 2,
        "default_cost_m2": 18,
        "note": "High chemical resistance; suitable for brine / sour service.",
    },
    "Coal tar epoxy": {
        "density_kg_m3": 1500,
        "default_dft_um": 400,
        "default_coats": 2,
        "default_cost_m2": 10,
        "note": "Excellent seawater resistance; not for potable water.",
    },
    "Glass-flake epoxy": {
        "density_kg_m3": 1550,
        "default_dft_um": 500,
        "default_coats": 2,
        "default_cost_m2": 22,
        "note": "Glass flake reinforcement; enhanced barrier and abrasion resistance.",
    },
}

# ── Ceramic coating types ─────────────────────────────────────────────────────
# Applied in multiple coats like epoxy; characterised by DFT per coat (µm).
CERAMIC_TYPES = {
    "Ceramic-filled epoxy": {
        "density_kg_m3": 1900,
        "default_dft_um": 500,
        "default_coats": 2,
        "default_cost_m2": 80,
        "note": "Ceramic particle-reinforced epoxy; excellent abrasion resistance up to 90 °C.",
    },
    "Alumina-filled epoxy": {
        "density_kg_m3": 2100,
        "default_dft_um": 600,
        "default_coats": 2,
        "default_cost_m2": 100,
        "note": "High alumina content; enhanced hardness and chemical resistance.",
    },
    "Silicon carbide coating": {
        "density_kg_m3": 2200,
        "default_dft_um": 750,
        "default_coats": 2,
        "default_cost_m2": 150,
        "note": "Extreme abrasion / erosion service; high hardness (Mohs 9).",
    },
    "Polyurea-ceramic hybrid": {
        "density_kg_m3": 1200,
        "default_dft_um": 1000,
        "default_coats": 1,
        "default_cost_m2": 90,
        "note": "Rapid-cure elastomeric ceramic hybrid spray; flexible, seamless, corrosion-barrier.",
    },
}

PROTECTION_TYPES = ["None", "Rubber lining", "Epoxy coating", "Ceramic coating"]

# Default application labor rates (USD/m²)
DEFAULT_LABOR_RUBBER_M2  = 25.0
DEFAULT_LABOR_EPOXY_M2   = 15.0
DEFAULT_LABOR_CERAMIC_M2 = 45.0


# ─────────────────────────────────────────────────────────────────────────────
# 1. INTERNAL SURFACE AREAS
# ─────────────────────────────────────────────────────────────────────────────

def internal_surface_areas(
    vessel_id_m: float,
    cyl_len_m: float,
    h_dish_m: float,
    end_type: str,
    nozzle_plate_area_m2: float = 0.0,
) -> dict:
    """
    Internal wetted surface areas of a horizontal pressure vessel.

    Cylinder
    --------
    A_cyl = π × ID × L_cyl

    Dish ends (per head)
    --------------------
    Elliptic 2:1  (exact oblate-spheroid surface integral):
        e   = √(1 − (b/a)²),   a = ID/2,  b = h_dish
        A   = π × a² × [1 + (1−e²)/e × arctanh(e)]

    Torispherical (approximation):
        A ≈ 0.9 × π × a²  (≈ 9 % larger than a flat disc)

    Nozzle plate
    ------------
    Passed in directly from nozzle_plate_design() output key "area_total_m2".
    """
    R = vessel_id_m / 2.0

    # Cylinder
    a_cyl = math.pi * vessel_id_m * cyl_len_m

    # Dish ends
    if end_type == "Elliptic 2:1":
        a  = R
        b  = h_dish_m
        ratio = b / a
        if ratio < 1.0:
            e = math.sqrt(1.0 - ratio ** 2)
            # Oblate spheroid half-shell area
            a_one_head = math.pi * a**2 * (1.0 + (1.0 - e**2) / e * math.atanh(e))
        else:
            a_one_head = math.pi * R**2   # degenerate: flat disc
    else:
        # Torispherical — standard Kloepper approximation
        a_one_head = math.pi * R**2 * 0.9

    a_two_heads   = 2.0 * a_one_head
    a_shell_total = a_cyl + a_two_heads
    a_total       = a_shell_total + nozzle_plate_area_m2

    return {
        "a_cylinder_m2":      round(a_cyl,            2),
        "a_one_head_m2":      round(a_one_head,        2),
        "a_two_heads_m2":     round(a_two_heads,       2),
        "a_shell_m2":         round(a_shell_total,     2),
        "a_nozzle_plate_m2":  round(nozzle_plate_area_m2, 2),
        "a_total_m2":         round(a_total,           2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. LINING / COATING COST & WEIGHT
# ─────────────────────────────────────────────────────────────────────────────

def lining_cost(
    protection_type: str,
    areas: dict,
    # ── Rubber ────────────────────────────────────────────────────────────────
    rubber_type: str         = "EPDM",
    rubber_thickness_mm: float = 4.0,
    rubber_layers: int       = 2,
    rubber_density_kg_m3: float = 0.0,    # 0 → use catalogue default
    rubber_cost_m2: float    = 0.0,       # 0 → use catalogue default
    rubber_labor_m2: float   = DEFAULT_LABOR_RUBBER_M2,
    # ── Epoxy ─────────────────────────────────────────────────────────────────
    epoxy_type: str          = "High-build epoxy",
    epoxy_dft_um: float      = 0.0,       # 0 → use catalogue default
    epoxy_coats: int         = 2,
    epoxy_density_kg_m3: float = 0.0,
    epoxy_cost_m2: float     = 0.0,
    epoxy_labor_m2: float    = DEFAULT_LABOR_EPOXY_M2,
    # ── Ceramic ───────────────────────────────────────────────────────────────
    ceramic_type: str          = "Ceramic-filled epoxy",
    ceramic_dft_um: float      = 0.0,     # 0 → use catalogue default
    ceramic_coats: int         = 2,
    ceramic_density_kg_m3: float = 0.0,
    ceramic_cost_m2: float     = 0.0,
    ceramic_labor_m2: float    = DEFAULT_LABOR_CERAMIC_M2,
) -> dict:
    """
    Weight and cost of internal vessel lining / coating.

    Weight
    ------
    Rubber  : area × layers × thickness × density
    Epoxy   : area × coats × DFT [m] × density
    Ceramic : area × coats × DFT [m] × density  (same model as epoxy)

    Cost
    ----
    Material cost = area × cost_per_m²
    Labour cost   = area × labour_per_m²
    Total cost    = material + labour
    """
    a_total = areas["a_total_m2"]
    a_shell = areas["a_shell_m2"]
    a_plate = areas["a_nozzle_plate_m2"]

    result = {
        "protection_type":   protection_type,
        "a_total_m2":        a_total,
        "a_shell_m2":        a_shell,
        "a_plate_m2":        a_plate,
        "thickness_mm":      0.0,
        "id_deduction_mm":   0.0,    # only rubber affects ID
        "weight_kg":         0.0,
        "material_cost_usd": 0.0,
        "labor_cost_usd":    0.0,
        "total_cost_usd":    0.0,
        "detail":            {},
    }

    if protection_type == "None" or protection_type is None:
        return result

    # ── Rubber lining ─────────────────────────────────────────────────────────
    if protection_type == "Rubber lining":
        cat = RUBBER_TYPES.get(rubber_type, RUBBER_TYPES["EPDM"])
        rho  = rubber_density_kg_m3 if rubber_density_kg_m3 > 0 else cat["density_kg_m3"]
        cost = rubber_cost_m2       if rubber_cost_m2 > 0       else cat["default_cost_m2"]
        t_m  = rubber_thickness_mm / 1000.0

        vol_kg  = a_total * t_m * rubber_layers * rho
        mat_usd = a_total * cost * rubber_layers
        lab_usd = a_total * rubber_labor_m2

        result.update({
            "thickness_mm":      rubber_thickness_mm,
            "id_deduction_mm":   2.0 * rubber_thickness_mm,  # both sides
            "weight_kg":         round(vol_kg, 1),
            "material_cost_usd": round(mat_usd, 0),
            "labor_cost_usd":    round(lab_usd, 0),
            "total_cost_usd":    round(mat_usd + lab_usd, 0),
            "detail": {
                "Type":               rubber_type,
                "Hardness":           cat["hardness"],
                "Thickness / layer":  f"{rubber_thickness_mm:.1f} mm",
                "Layers":             rubber_layers,
                "Total thickness":    f"{rubber_thickness_mm * rubber_layers:.1f} mm",
                "Density":            f"{rho} kg/m³",
                "Area lined":         f"{a_total:.1f} m²",
                "Lining weight":      f"{vol_kg:.1f} kg",
                "Material cost":      f"USD {mat_usd:,.0f}  ({cost:.1f}/m² × {rubber_layers} layers)",
                "Labour cost":        f"USD {lab_usd:,.0f}  ({rubber_labor_m2:.1f}/m²)",
                "Total cost":         f"USD {mat_usd + lab_usd:,.0f}",
            },
        })

    # ── Epoxy coating ─────────────────────────────────────────────────────────
    elif protection_type == "Epoxy coating":
        cat  = EPOXY_TYPES.get(epoxy_type, EPOXY_TYPES["High-build epoxy"])
        rho  = epoxy_density_kg_m3 if epoxy_density_kg_m3 > 0 else cat["density_kg_m3"]
        cost = epoxy_cost_m2       if epoxy_cost_m2 > 0       else cat["default_cost_m2"]
        dft  = epoxy_dft_um        if epoxy_dft_um > 0        else cat["default_dft_um"]
        t_m  = dft / 1e6 * epoxy_coats   # total DFT in metres

        wt_kg   = a_total * t_m * rho
        mat_usd = a_total * cost * epoxy_coats
        lab_usd = a_total * epoxy_labor_m2

        result.update({
            "thickness_mm":      round(t_m * 1000, 3),
            "id_deduction_mm":   0.0,
            "weight_kg":         round(wt_kg, 1),
            "material_cost_usd": round(mat_usd, 0),
            "labor_cost_usd":    round(lab_usd, 0),
            "total_cost_usd":    round(mat_usd + lab_usd, 0),
            "detail": {
                "Type":                epoxy_type,
                "Note":                cat["note"],
                "DFT per coat":        f"{dft:.0f} µm",
                "Number of coats":     epoxy_coats,
                "Total DFT":           f"{t_m*1000:.0f} µm  ({t_m*1000:.3f} mm)",
                "Density":             f"{rho} kg/m³",
                "Area coated":         f"{a_total:.1f} m²",
                "Coating weight":      f"{wt_kg:.1f} kg",
                "Material cost":       f"USD {mat_usd:,.0f}  ({cost:.1f}/m² × {epoxy_coats} coats)",
                "Labour cost":         f"USD {lab_usd:,.0f}  ({epoxy_labor_m2:.1f}/m²)",
                "Total cost":          f"USD {mat_usd + lab_usd:,.0f}",
            },
        })

    # ── Ceramic coating ───────────────────────────────────────────────────────
    elif protection_type == "Ceramic coating":
        cat  = CERAMIC_TYPES.get(ceramic_type, CERAMIC_TYPES["Ceramic-filled epoxy"])
        rho  = ceramic_density_kg_m3 if ceramic_density_kg_m3 > 0 else cat["density_kg_m3"]
        cost = ceramic_cost_m2       if ceramic_cost_m2 > 0       else cat["default_cost_m2"]
        dft  = ceramic_dft_um        if ceramic_dft_um > 0        else cat["default_dft_um"]
        t_m  = dft / 1e6 * ceramic_coats   # total DFT in metres

        wt_kg   = a_total * t_m * rho
        mat_usd = a_total * cost * ceramic_coats
        lab_usd = a_total * ceramic_labor_m2

        result.update({
            "thickness_mm":      round(t_m * 1000, 3),
            "id_deduction_mm":   0.0,
            "weight_kg":         round(wt_kg, 1),
            "material_cost_usd": round(mat_usd, 0),
            "labor_cost_usd":    round(lab_usd, 0),
            "total_cost_usd":    round(mat_usd + lab_usd, 0),
            "detail": {
                "Type":            ceramic_type,
                "Note":            cat["note"],
                "DFT per coat":    f"{dft:.0f} µm",
                "Number of coats": ceramic_coats,
                "Total DFT":       f"{dft * ceramic_coats:.0f} µm  ({t_m*1000:.3f} mm)",
                "Density":         f"{rho} kg/m³",
                "Area coated":     f"{a_total:.1f} m²",
                "Coating weight":  f"{wt_kg:.1f} kg",
                "Material cost":   f"USD {mat_usd:,.0f}  ({cost:.1f}/m² × {ceramic_coats} coats)",
                "Labour cost":     f"USD {lab_usd:,.0f}  ({ceramic_labor_m2:.1f}/m²)",
                "Total cost":      f"USD {mat_usd + lab_usd:,.0f}",
            },
        })

    return result
