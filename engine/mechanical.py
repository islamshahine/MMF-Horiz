import math

# =============================================================================
# MATERIAL LIBRARY
# =============================================================================
MATERIALS = {
    "ASTM A283-C": {
        "standard": "ASTM",
        "allowable_stress": 1000,
        "description": "Atmospheric and low-pressure tanks; non-critical shells and plates",
    },
    "ASTM A285-C": {
        "standard": "ASTM",
        "allowable_stress": 1000,
        "description": "Welded pressure vessels for low-to-moderate pressure service (legacy material)",
    },
    "ASTM A516-60": {
        "standard": "ASTM",
        "allowable_stress": 1150,
        "description": "General pressure-vessel shells, heads, and nozzles",
    },
    "ASTM A516-70": {
        "standard": "ASTM",
        "allowable_stress": 1200,
        "description": "Primary pressure-vessel material for moderate-to-high pressure service",
    },
    "JIS SB450": {
        "standard": "JIS",
        "allowable_stress": 1150,
        "description": "Pressure-vessel shells and heads; Japanese equivalent to ASTM A516-60",
    },
    "JIS SM490A / SM490B": {
        "standard": "JIS",
        "allowable_stress": 1100,
        "description": "Pressure-retaining shells, skirts, and load-bearing vessel structures",
    },
    "AISI 304 (SA-240 TP304)": {
        "standard": "ASTM",
        "allowable_stress": 1250,
        "description": "Corrosion-resistant pressure vessels for mildly aggressive services (yield-controlled)",
    },
    "AISI 316 (SA-240 TP316)": {
        "standard": "ASTM",
        "allowable_stress": 1200,
        "description": "Pressure vessels exposed to chlorides, marine environments, or chemical service",
    },
}

# =============================================================================
# RADIOGRAPHY (ASME VIII-1 UW-11 / UW-12)
# Key: (shell_radio, head_radio)  →  joint efficiency E
# Shell options: None=1, SPOT=2, FULL=3
# Head options : None=1, SPOT=2, FULL=3
# =============================================================================
RADIOGRAPHY_OPTIONS = ["None", "SPOT", "FULL"]

JOINT_EFFICIENCY = {
    "None": 0.70,
    "SPOT": 0.85,
    "FULL": 1.00,
}

# Head geometric factor K (ASME VIII-1 Appendix 1-4)
# For standard 2:1 semi-ellipsoidal head K = 1.0
HEAD_GEOMETRIC_FACTOR = 1.0


def get_material_info(material_name: str) -> dict:
    return MATERIALS.get(material_name, {})


def thickness(
    diameter_m: float,
    design_pressure_bar: float,
    material_name: str,
    shell_radio: str,
    head_radio: str,
    corrosion_mm: float,
    internal_lining_mm: float = 0.0,
) -> dict:
    """
    ASME Section VIII Division 1 minimum wall thickness.

    Parameters
    ----------
    diameter_m          : Internal diameter in metres (before lining)
    design_pressure_bar : Design pressure in bar
    material_name       : Key from MATERIALS dict
    shell_radio         : Radiography level for shell  ("None" | "SPOT" | "FULL")
    head_radio          : Radiography level for head   ("None" | "SPOT" | "FULL")
    corrosion_mm        : Corrosion allowance in mm
    internal_lining_mm  : Internal lining thickness in mm (reduces usable ID)

    Returns
    -------
    dict with keys:
        allowable_stress    kgf/cm²
        shell_E             joint efficiency (shell)
        head_E              joint efficiency (head)
        p_kgf_cm2           design pressure in kgf/cm²
        t_shell_min_mm      minimum shell thickness (mm, no CA)
        t_shell_design_mm   design shell thickness (mm, rounded up + CA)
        t_head_min_mm       minimum head thickness (mm, no CA)
        t_head_design_mm    design head thickness (mm, rounded up + CA)
        id_with_lining_m    internal diameter after lining
        od_m                outside diameter
    """
    mat = MATERIALS.get(material_name)
    if mat is None:
        raise ValueError(f"Unknown material: {material_name}")

    S = mat["allowable_stress"]          # kgf/cm²
    E_shell = JOINT_EFFICIENCY[shell_radio]
    E_head  = JOINT_EFFICIENCY[head_radio]
    K = HEAD_GEOMETRIC_FACTOR

    # Convert units
    p = design_pressure_bar * 1.01972    # bar → kgf/cm²
    R = diameter_m * 100 / 2            # internal radius, cm

    # ASME VIII-1 UG-27(c)(1)  — Cylindrical shell
    t_shell = (p * R) / (S * E_shell - 0.6 * p)          # cm
    t_shell_mm = t_shell * 10                              # mm

    # ASME VIII-1 Appendix 1-4(c) — 2:1 Ellipsoidal head
    # t = (P * D * K) / (2*S*E - 0.2*P),  D = diameter in cm
    D_cm = diameter_m * 100
    t_head = (p * D_cm * K) / (2 * S * E_head - 0.2 * p)  # cm
    t_head_mm = t_head * 10                                 # mm

    t_shell_design = math.ceil(t_shell_mm + corrosion_mm)
    t_head_design  = math.ceil(t_head_mm  + corrosion_mm)

    # Diameters accounting for lining
    id_with_lining = diameter_m - 2 * internal_lining_mm / 1000
    od = diameter_m + 2 * t_shell_design / 1000

    return {
        "allowable_stress":   S,
        "shell_E":            E_shell,
        "head_E":             E_head,
        "p_kgf_cm2":          round(p, 4),
        "t_shell_min_mm":     round(t_shell_mm, 2),
        "t_shell_design_mm":  t_shell_design,
        "t_head_min_mm":      round(t_head_mm, 2),
        "t_head_design_mm":   t_head_design,
        "id_with_lining_m":   round(id_with_lining, 4),
        "od_m":               round(od, 4),
    }


# =============================================================================
# STEEL DENSITY
# =============================================================================
STEEL_DENSITY_KG_M3 = 7850.0   # kg/m³ — carbon & low-alloy steel (ASME materials)
# For stainless (304/316) this is ~7900; keep one value, close enough for empty-weight est.


def empty_weight(
    diameter_m: float,
    straight_length_m: float,
    end_geometry: str,
    t_shell_mm: float,
    t_head_mm: float,
    density_kg_m3: float = STEEL_DENSITY_KG_M3,
) -> dict:
    """
    Empty (bare) weight of the pressure-vessel body shell + two dish ends.

    Geometry
    --------
    Shell  : thin-walled cylinder, mean diameter used for surface area.
    Heads  : surface-area method using standard closed-form approximations.
             • 2:1 Ellipsoidal  — SA ≈ 0.8727 × D_mean²  (exact for a=1, b=0.5a)
             • Torispherical    — SA ≈ 0.9286 × D_mean²  (crown r=D, knuckle r=0.06D)

    Parameters
    ----------
    diameter_m        : Internal diameter, m
    straight_length_m : Tangent-to-tangent (T/T) cylindrical length, m
                        = total_length − 2 × h_dish
    end_geometry      : "Elliptic 2:1" | "Torispherical 10%"
    t_shell_mm        : Design shell wall thickness, mm  (selected, incl. CA)
    t_head_mm         : Design head wall thickness, mm   (selected, incl. CA)
    density_kg_m3     : Steel density, kg/m³

    Returns
    -------
    dict with keys:
        t_shell_m           shell thickness, m
        t_head_m            head thickness, m
        d_mean_shell_m      mean shell diameter, m
        d_mean_head_m       mean head diameter, m  (same as shell for same t)
        area_shell_m2       lateral surface area of cylindrical shell, m²
        vol_shell_m3        metal volume of cylindrical shell, m³
        weight_shell_kg     mass of shell plate, kg
        area_one_head_m2    surface area of one dish end, m²
        vol_one_head_m3     metal volume of one dish end, m³
        weight_two_heads_kg mass of both heads combined, kg
        weight_body_kg      total bare body weight (shell + 2 heads), kg
        weight_body_t       same in metric tons
    """
    t_s = t_shell_mm / 1000.0   # m
    t_h = t_head_mm  / 1000.0   # m

    # Mean diameters (mid-wall)
    D_ms = diameter_m + t_s          # shell mid-wall diameter
    D_mh = diameter_m + t_h          # head  mid-wall diameter

    # ── Cylindrical shell ─────────────────────────────────────────────────────
    # Lateral surface area of a thin-walled cylinder (mid-wall circumference × length)
    area_shell = math.pi * D_ms * straight_length_m
    vol_shell  = area_shell * t_s
    w_shell    = vol_shell * density_kg_m3

    # ── Dish ends (×2) ────────────────────────────────────────────────────────
    # Surface area of one head (mid-wall diameter)
    if end_geometry == "Elliptic 2:1":
        # Exact closed-form for 2:1 oblate spheroid:
        # SA = π/2 * a² * (1 + (1-e²)/e * arctanh(e))
        # where a = D/2, b = a/2, e = eccentricity = sqrt(1-(b/a)²) = sqrt(3)/2
        a = D_mh / 2
        b = a / 2
        e = math.sqrt(1 - (b / a) ** 2)          # = √3/2 ≈ 0.8660
        area_one_head = (math.pi / 2) * a**2 * (1 + (1 - e**2) / e * math.atanh(e))
    else:
        # Torispherical (crown R=D, knuckle r=0.06D):
        # Standard approximation: SA ≈ π/4 * (0.5*D + 2r)² where r = knuckle radius
        # More precise: SA ≈ 0.9286 * D_mean²  (Megyesy / Pressure Vessel Handbook)
        area_one_head = 0.9286 * D_mh**2

    vol_one_head     = area_one_head * t_h
    w_two_heads      = 2 * vol_one_head * density_kg_m3

    # ── Totals ────────────────────────────────────────────────────────────────
    w_body = w_shell + w_two_heads

    return {
        "t_shell_m":            round(t_s, 6),
        "t_head_m":             round(t_h, 6),
        "d_mean_shell_m":       round(D_ms, 4),
        "d_mean_head_m":        round(D_mh, 4),
        "area_shell_m2":        round(area_shell, 3),
        "vol_shell_m3":         round(vol_shell, 4),
        "weight_shell_kg":      round(w_shell, 1),
        "area_one_head_m2":     round(area_one_head, 3),
        "vol_one_head_m3":      round(vol_one_head, 4),
        "weight_two_heads_kg":  round(w_two_heads, 1),
        "weight_body_kg":       round(w_body, 1),
        "weight_body_t":        round(w_body / 1000, 3),
    }