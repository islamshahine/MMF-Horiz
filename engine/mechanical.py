import math

# =============================================================================
# SADDLE CATALOGUE  (capacity t, section label, kg/m, piece length m, paint m²/m)
# =============================================================================
SADDLE_CATALOGUE = [
    (  5, "L-65×65×6",     5.91,  1.0, 0.26),
    ( 10, "L-75×75×9",     9.96,  1.0, 0.30),
    ( 20, "L-90×90×10",   13.30,  1.0, 0.36),
    ( 30, "L-100×100×10", 14.90,  1.0, 0.40),
    ( 40, "H-125×6.5/9",  23.80,  1.5, 0.75),
    ( 50, "H-150×7/10",   31.50,  1.5, 0.90),
    ( 75, "H-200×8/12",   49.90,  1.6, 1.20),
    (120, "H-250×9/14",   72.40,  1.8, 1.50),
    (250, "H-300×10/15",  94.00,  2.1, 1.80),
    (350, "H-350×12/19", 137.00,  2.3, 2.10),
]

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


def apply_thickness_override(
    mech: dict,
    override_shell_mm: float = 0.0,
    override_head_mm:  float = 0.0,
    internal_lining_mm: float = 0.0,
    nominal_id_m: float = 0.0,
) -> dict:
    """
    Apply user thickness overrides (must be >= t_min + CA).
    Recompute real hydraulic ID and OD from the overridden values.

    The nominal ID chosen by the user IS the internal diameter before lining.
    Real hydraulic ID = nominal ID - 2 × lining thickness.
    This real ID feeds ALL hydraulic calculations downstream.
    """
    result = dict(mech)

    # Shell override — floor at t_design (already includes CA)
    if override_shell_mm > 0:
        if override_shell_mm < mech["t_shell_min_mm"] + (mech.get("corrosion_mm", 1.5)):
            override_shell_mm = mech["t_shell_design_mm"]   # silently enforce floor
        result["t_shell_design_mm"] = math.ceil(override_shell_mm)
        result["shell_overridden"]  = True
    else:
        result["shell_overridden"]  = False

    # Head override
    if override_head_mm > 0:
        if override_head_mm < mech["t_head_min_mm"] + (mech.get("corrosion_mm", 1.5)):
            override_head_mm = mech["t_head_design_mm"]
        result["t_head_design_mm"] = math.ceil(override_head_mm)
        result["head_overridden"]  = True
    else:
        result["head_overridden"]  = False

    # Real hydraulic ID (used in ALL hydraulic calculations)
    real_id = nominal_id_m - 2.0 * internal_lining_mm / 1000.0
    result["real_id_m"]    = round(real_id, 4)
    result["nominal_id_m"] = round(nominal_id_m, 4)
    result["lining_mm"]    = internal_lining_mm

    # OD from real ID + 2 × shell thickness
    result["od_m"] = round(real_id + 2.0 * result["t_shell_design_mm"] / 1000.0, 4)

    return result


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


# =============================================================================
# NOZZLE PLATE — GEOMETRY, BORE LAYOUT, THICKNESS DESIGN, AND WEIGHT
# =============================================================================

# Nozzle density range (nozzles/m²) — water-treatment industry standard
NOZZLE_DENSITY_MIN     = 45.0
NOZZLE_DENSITY_MAX     = 55.0
NOZZLE_DENSITY_DEFAULT = 50.0

_KGF_CM2_TO_PA = 98_066.5   # 1 kgf/cm² in Pa


def nozzle_plate_area(
    h_m: float,
    vessel_id_m: float,
    cyl_len_m: float,
    h_dish_m: float,
    n_integration: int = 5000,
) -> dict:
    """
    Horizontal nozzle (strainer support) plate area at height h from vessel bottom.

    The plate is a HORIZONTAL flat shelf running the full length of the vessel.
    It is NOT a cross-sectional disk — it lies flat at elevation h.

    Three components
    ----------------
    1. Cylindrical section : chord(h) × cyl_len
       where chord(h) = 2 × sqrt(R² − (R−h)²)

    2. Each dish end (×2)  : ∫₀^h_dish  chord(h, R_z) dz
       where R_z = R × sqrt(1 − (z/h_dish)²)  (ellipsoidal radius at axial pos z)
       The plate is flat — height h is fixed in space.  As z increases into the
       dish, the local vessel radius R_z shrinks, so the chord narrows and
       eventually reaches zero where the dish wall drops below h.

    Integration is numerical (5 000 steps, error < 0.01 %).

    Parameters
    ----------
    h_m          : Plate height from vessel bottom, m
    vessel_id_m  : Vessel internal diameter, m
    cyl_len_m    : Straight (tangent-to-tangent) cylindrical length, m
    h_dish_m     : Dish depth (h_dish = D/4 for 2:1 ellipsoidal), m
    n_integration: Number of integration steps for dish end

    Returns
    -------
    dict with keys:
        chord_m            plate width at vessel centreline, m
        theta_deg          subtended half-angle, degrees
        area_cyl_m2        plate area in cylindrical section, m²
        area_one_dish_m2   plate area in one dish end, m²
        area_both_dish_m2  plate area in both dish ends, m²
        area_total_m2      total plate face area, m²
    """
    R = vessel_id_m / 2.0

    def _chord(R_z: float, h: float) -> float:
        if h <= 0 or R_z <= 0 or h >= 2 * R_z:
            return 0.0
        return 2.0 * math.sqrt(max(0.0, R_z**2 - (R_z - h)**2))

    chord_at_h = _chord(R, h_m)
    area_cyl   = chord_at_h * cyl_len_m

    dz = h_dish_m / n_integration
    area_one_dish = sum(
        _chord(R * math.sqrt(max(0.0, 1.0 - (i * dz / h_dish_m)**2)), h_m) * dz
        for i in range(n_integration)
    )

    # Half-angle (θ) for reference
    if chord_at_h > 0 and R > 0:
        val   = max(-1.0, min(1.0, (R - h_m) / R))
        theta = math.degrees(2 * math.acos(val))
    else:
        theta = 0.0

    return {
        "chord_m":           round(chord_at_h,        4),
        "theta_deg":         round(theta,              2),
        "area_cyl_m2":       round(area_cyl,           4),
        "area_one_dish_m2":  round(area_one_dish,      4),
        "area_both_dish_m2": round(2 * area_one_dish,  4),
        "area_total_m2":     round(area_cyl + 2 * area_one_dish, 4),
    }


def nozzle_plate_design(
    vessel_id_m: float,
    cyl_len_m: float,
    h_dish_m: float,
    h_plate_m: float,
    design_dp_bar: float,
    media_layers: list,
    water_density_kg_m3: float   = 1025.0,
    nozzle_density_per_m2: float = NOZZLE_DENSITY_DEFAULT,
    bore_diameter_mm: float      = 50.0,
    beam_spacing_mm: float       = 500.0,
    allowable_stress_kgf_cm2: float = 1200.0,
    corrosion_allowance_mm: float   = 1.5,
    density_kg_m3: float         = STEEL_DENSITY_KG_M3,
    override_thickness_mm: float = 0.0,
) -> dict:
    """
    Full nozzle plate design: geometry -> loads -> plate thickness -> support
    beams -> bore layout -> weight.

    STRUCTURAL MODEL
    ----------------
    The nozzle plate assembly consists of two components:

    1. FLAT PLATE  — thin steel plate carrying distributed pressure.
       Spans between support beams (effective span = beam_spacing).
       Formula: Roark Table 11.4, case 10b (long plate, simply supported):
           t = b_eff * sqrt(q / (2 * S_allow))
       where b_eff = beam_spacing_mm.

    2. SUPPORT BEAMS (stiffener ribs) — carry the plate load to the vessel shell.
       Span = chord at plate elevation (simply supported at shell wall welds).
       Line load on one beam = q_total * beam_spacing.
       Required section modulus: Z = M_max / S_allow = (q_line * chord²/8) / S_allow.
       Closest standard IPE section is selected; its unit weight * chord * n_beams
       gives total beam weight.

    LOADING
    -------
    q_dp    = design_dp_bar * 1e5              [Pa]  — BW hydraulic, upward
    q_media = sum(rho_sat_i * g * depth_i)    [Pa]  — saturated media, downward
    q_total = q_dp + q_media                         — worst-case envelope
    """
    g = 9.81

    # ── Geometry ──────────────────────────────────────────────────────────────
    geo = nozzle_plate_area(
        h_m=h_plate_m,
        vessel_id_m=vessel_id_m,
        cyl_len_m=cyl_len_m,
        h_dish_m=h_dish_m,
    )
    area_total = geo["area_total_m2"]
    chord      = geo["chord_m"]

    # ── Loads ─────────────────────────────────────────────────────────────────
    q_dp = design_dp_bar * 1e5
    q_media = sum(
        (L.get("rho_p_eff", 2650) * (1 - L.get("epsilon0", 0.42))
         + water_density_kg_m3 * L.get("epsilon0", 0.42))
        * g * L.get("Depth", 0.0)
        for L in media_layers
    )
    q_total = q_dp + q_media

    # ── Plate thickness (beam spacing is the effective span) ───────────────────
    S_pa           = allowable_stress_kgf_cm2 * _KGF_CM2_TO_PA
    b_eff_m        = beam_spacing_mm / 1000.0
    t_calc_mm      = b_eff_m * math.sqrt(q_total / (2 * S_pa)) * 1000
    t_calc_mm     *= 1.10          # 10 % bore-opening stress concentration
    t_min_mm       = t_calc_mm
    t_design_mm    = math.ceil(t_calc_mm + corrosion_allowance_mm)
    t_used_mm      = override_thickness_mm if override_thickness_mm > 0 else float(t_design_mm)
    thickness_src  = "User override" if override_thickness_mm > 0                      else "Calculated (Roark long plate, simply supported)"

    # ── Support beams ─────────────────────────────────────────────────────────
    # Standard IPE sections: {name: (Z_cm3, unit_weight_kg_m)}
    IPE = {
        "IPE 160": (123,  15.8),
        "IPE 200": (194,  22.4),
        "IPE 240": (324,  30.7),
        "IPE 270": (395,  36.1),
        "IPE 300": (557,  42.2),
        "IPE 330": (713,  49.1),
        "IPE 360": (904,  57.1),
        "IPE 400": (1156, 66.3),
        "IPE 450": (1500, 77.6),
        "IPE 500": (1928, 90.7),
    }
    b_sp_m   = beam_spacing_mm / 1000.0
    q_line   = q_total * b_sp_m             # N/m  (line load per beam)
    M_max    = q_line * chord**2 / 8        # N·m
    Z_req_cm3 = M_max / S_pa * 1e6         # cm³

    # Select lightest adequate section
    beam_name, beam_Z, beam_w = "IPE 500", 1928, 90.7  # default to heaviest if none fits
    for name, (Z, w) in IPE.items():
        if Z >= Z_req_cm3:
            beam_name, beam_Z, beam_w = name, Z, w
            break

    n_beams       = math.ceil(cyl_len_m / b_sp_m) + 1
    weight_beams  = n_beams * chord * beam_w          # kg

    # ── Plate weight ──────────────────────────────────────────────────────────
    # Bore layout
    n_bores_min  = math.ceil(NOZZLE_DENSITY_MIN * area_total)
    n_bores_max  = math.floor(NOZZLE_DENSITY_MAX * area_total)
    n_bores      = max(n_bores_min,
                       min(n_bores_max, round(nozzle_density_per_m2 * area_total)))
    bore_a_each  = math.pi / 4 * (bore_diameter_mm / 1000) ** 2
    bores_area   = bore_a_each * n_bores
    net_area     = max(area_total - bores_area, 0.0)
    open_ratio   = bores_area / area_total if area_total > 0 else 0.0
    act_density  = n_bores / area_total if area_total > 0 else 0.0

    t_plate_m    = t_used_mm / 1000.0
    vol_plate    = net_area * t_plate_m
    weight_plate = vol_plate * density_kg_m3

    weight_total = weight_plate + weight_beams

    return {
        # Geometry
        "h_plate_m":              round(h_plate_m,          3),
        "chord_m":                geo["chord_m"],
        "theta_deg":              geo["theta_deg"],
        "area_cyl_m2":            geo["area_cyl_m2"],
        "area_one_dish_m2":       geo["area_one_dish_m2"],
        "area_both_dish_m2":      geo["area_both_dish_m2"],
        "area_total_m2":          round(area_total,          4),
        # Bore layout
        "n_bores":                n_bores,
        "n_bores_min":            n_bores_min,
        "n_bores_max":            n_bores_max,
        "bore_diameter_mm":       bore_diameter_mm,
        "bore_area_each_m2":      round(bore_a_each,         6),
        "bores_total_area_m2":    round(bores_area,          4),
        "net_area_m2":            round(net_area,            4),
        "open_ratio_pct":         round(open_ratio * 100,    2),
        "actual_density_per_m2":  round(act_density,         1),
        # Loads
        "q_dp_kpa":               round(q_dp    / 1000,      2),
        "q_media_kpa":            round(q_media / 1000,      2),
        "q_total_kpa":            round(q_total / 1000,      2),
        # Plate thickness
        "beam_spacing_mm":        beam_spacing_mm,
        "t_min_mm":               round(t_min_mm,            2),
        "t_design_mm":            t_design_mm,
        "t_used_mm":              t_used_mm,
        "thickness_source":       thickness_src,
        "allowable_stress_kgf_cm2": allowable_stress_kgf_cm2,
        # Support beams
        "beam_section":           beam_name,
        "beam_Z_cm3":             beam_Z,
        "beam_Z_req_cm3":         round(Z_req_cm3,           1),
        "beam_unit_weight_kg_m":  beam_w,
        "n_beams":                n_beams,
        "M_max_kNm":              round(M_max / 1000,        2),
        "weight_beams_kg":        round(weight_beams,        1),
        # Weight
        "weight_plate_kg":        round(weight_plate,        1),
        "weight_total_kg":        round(weight_total,        1),
        "plate_vol_m3":           round(vol_plate,           5),
    }



# =============================================================================
# VESSEL INTERNALS WEIGHT
# =============================================================================

# Standard pipe weight per metre (kg/m) — carbon steel Sch 40
# Source: ASME B36.10M
PIPE_WEIGHT_KG_M = {
    50:  3.23,  80:  5.31,  100: 7.09,  150: 12.15,
    200: 20.10, 250: 28.26, 300: 36.69, 400: 55.87,
}

# Strainer nozzle unit weights (one nozzle body, no base)
STRAINER_WEIGHT_KG = {
    "SS316":  0.35,   # stainless steel — pressure service
    "HDPE":   0.08,   # high-density polyethylene — standard duty
    "PP":     0.06,   # polypropylene — low pressure
}

# Manhole standard weights (cover + neck stub, DN 600)
MANHOLE_WEIGHT_KG = {
    "DN 600": 130,
    "DN 800": 210,
}


def internals_weight(
    n_strainer_nozzles: int,
    strainer_material: str      = "SS316",
    air_header_dn_mm: int       = 200,
    air_header_length_m: float  = 0.0,    # = cyl_len if not overridden
    cyl_len_m: float            = 21.55,
    manhole_dn: str             = "DN 600",
    n_manholes: int             = 1,
) -> dict:
    """
    Weight of internal components:
      - Strainer lateral nozzles (screwed into nozzle plate bores)
      - Air scour distribution header pipe
      - Manhole(s) with cover

    Parameters
    ----------
    n_strainer_nozzles  : Number of strainer nozzles (= n_bores from nozzle plate)
    strainer_material   : "SS316" | "HDPE" | "PP"
    air_header_dn_mm    : Air scour header pipe DN, mm
    air_header_length_m : Header length (defaults to cyl_len if 0)
    cyl_len_m           : Vessel cylindrical length, m
    manhole_dn          : Manhole size key
    n_manholes          : Number of manholes per vessel
    Returns
    -------
    dict with individual and total weights, kg and tonnes
    """
    # Strainer nozzles
    w_per_nozzle   = STRAINER_WEIGHT_KG.get(strainer_material, 0.35)
    w_strainers    = n_strainer_nozzles * w_per_nozzle

    # Air scour header
    L_header       = air_header_length_m if air_header_length_m > 0 else cyl_len_m
    # Get nearest DN from table
    dn_options     = sorted(PIPE_WEIGHT_KG_M.keys())
    dn_actual      = min(dn_options, key=lambda d: abs(d - air_header_dn_mm))
    w_per_m        = PIPE_WEIGHT_KG_M[dn_actual]
    w_air_header   = w_per_m * L_header

    # Manhole
    w_manhole_each = MANHOLE_WEIGHT_KG.get(manhole_dn, 130)
    w_manholes     = w_manhole_each * n_manholes

    w_total        = w_strainers + w_air_header + w_manholes

    return {
        # Strainers
        "n_strainer_nozzles":     n_strainer_nozzles,
        "strainer_material":      strainer_material,
        "weight_per_strainer_kg": round(w_per_nozzle, 3),
        "weight_strainers_kg":    round(w_strainers, 1),
        # Air header
        "air_header_dn_mm":       dn_actual,
        "air_header_length_m":    round(L_header, 3),
        "air_header_kg_per_m":    w_per_m,
        "weight_air_header_kg":   round(w_air_header, 1),
        # Manholes
        "manhole_dn":             manhole_dn,
        "n_manholes":             n_manholes,
        "weight_per_manhole_kg":  w_manhole_each,
        "weight_manholes_kg":     round(w_manholes, 1),
        # Total
        "weight_internals_kg":    round(w_total, 1),
        "weight_internals_t":     round(w_total / 1000, 4),
    }

# =============================================================================
# SADDLE / LEG SUPPORT WEIGHT
# =============================================================================

# Saddle geometry constants (Zick / industry standard proportions)
# Width of saddle web plate = 1/6 of vessel OD (typical)
# Saddle contact arc = 120° (standard; 2-saddle horizontal vessel)
_SADDLE_ARC_DEG   = 120.0
_SADDLE_WIDTH_RATIO = 1 / 6      # saddle width ≈ OD / 6

# Leg support: square hollow section or pipe leg — approximated as solid square bar
# for weight estimation purposes

SUPPORT_TYPES = ["Saddle (2-support)",
                 "Saddle (3-support)",
                 "Leg (3-leg)",
                 "Leg (4-leg)"]


def saddle_weight(
    vessel_od_m: float,
    support_type: str                 = "Saddle (2-support)",
    saddle_height_m: float            = 0.8,
    leg_height_m: float               = 1.2,
    leg_section_mm: float             = 150.0,
    base_plate_thickness_mm: float    = 20.0,
    gusset_thickness_mm: float        = 12.0,
    density_kg_m3: float              = STEEL_DENSITY_KG_M3,
    n_supports_override: int | None   = None,
) -> dict:
    """
    Estimate support structure weight for a horizontal pressure vessel.

    Two configurations:

    SADDLE SUPPORTS (Zick saddle)
    ─────────────────────────────
    Each saddle is made of three components:
      1. Web plate  — curved plate conforming to the vessel OD over 120°
                     thickness ≈ vessel wall thickness proxy (use shell t);
                     estimated here as 16 mm flat equivalent.
      2. Base plate — rectangular steel plate sitting on the foundation.
                     Width = saddle width (OD/6), Length = OD × 0.8.
      3. Two gusset plates — triangular stiffeners on each side.

    LEG SUPPORTS
    ─────────────
    Each leg assembly = one vertical leg (hollow square section) +
    one base plate + two gusset plates welded to the vessel shell.

    Parameters
    ----------
    vessel_od_m            : Vessel outside diameter, m
    vessel_length_m        : Total vessel length (T/T), m
    support_type           : One of SUPPORT_TYPES
    saddle_height_m        : Height from foundation to vessel centreline minus R, m
    leg_height_m           : Leg height from foundation to vessel bottom, m
    leg_section_mm         : Leg hollow section outer dimension, mm (square)
    base_plate_thickness_mm: Thickness of base plate under each saddle/leg, mm
    gusset_thickness_mm    : Thickness of each triangular gusset plate, mm
    density_kg_m3          : Steel density, kg/m³
    n_supports_override    : If set and support_type is **Saddle**, use this count
                             instead of parsing the support_type string.

    Returns
    -------
    dict with keys (all weights in kg):
        support_type
        n_supports
        weight_web_or_leg_kg    weight of web plates (saddle) or leg columns (legs)
        weight_base_plates_kg   weight of all base plates
        weight_gussets_kg       weight of all gusset plates
        weight_per_support_kg   total weight of one support assembly
        weight_all_supports_kg  total weight (all supports)
        weight_all_supports_t   same in metric tons
        notes                   brief engineering note
    """
    R   = vessel_od_m / 2.0
    t_b = base_plate_thickness_mm / 1000.0
    t_g = gusset_thickness_mm     / 1000.0

    # Number of supports
    if n_supports_override is not None and "Saddle" in support_type:
        n = max(1, min(int(n_supports_override), 12))
    elif "2-support" in support_type or "2-saddle" in support_type.lower():
        n = 2
    elif "3-support" in support_type or "3-saddle" in support_type.lower():
        n = 3
    elif "3-leg" in support_type:
        n = 3
    else:
        n = 4

    if "Saddle" in support_type:
        # ── SADDLE ───────────────────────────────────────────────────────────
        # 1. Web plate: curved, arc = 120°, height = saddle_height, t ≈ 16 mm
        arc_rad      = math.radians(_SADDLE_ARC_DEG)
        arc_length   = arc_rad * R                          # half arc on one side, m
        web_t        = 0.016                                # m — standard 16 mm web plate
        saddle_width = max(vessel_od_m * _SADDLE_WIDTH_RATIO, 0.15)  # m, min 150 mm
        web_area     = arc_length * 2 * saddle_height_m    # 2 sides × arc × height
        vol_web      = web_area * web_t
        w_web        = vol_web * density_kg_m3

        # 2. Base plate: width × length × thickness
        base_w       = saddle_width + 0.10                 # 50 mm overhang each side
        base_l       = vessel_od_m * 0.80
        vol_base     = base_w * base_l * t_b
        w_base       = vol_base * density_kg_m3

        # 3. Gusset plates (2 per saddle): right-triangle, legs = saddle_height × saddle_width/2
        gusset_leg_v = saddle_height_m
        gusset_leg_h = saddle_width / 2
        area_gusset  = 0.5 * gusset_leg_v * gusset_leg_h  # one triangle
        vol_gussets  = 2 * area_gusset * t_g
        w_gussets    = vol_gussets * density_kg_m3

        note = (f"Zick saddle, 120° arc, web t=16 mm, "
                f"base {base_w*1000:.0f}×{base_l*1000:.0f} mm, "
                f"2 gussets t={gusset_thickness_mm:.0f} mm per saddle")

    else:
        # ── LEGS ─────────────────────────────────────────────────────────────
        # 1. Leg column: hollow square section, outer dim = leg_section_mm,
        #    wall ≈ section/10 (typical for SHS), height = leg_height
        s    = leg_section_mm / 1000.0                     # m, outer side
        t_w  = s / 10.0                                    # m, wall thickness
        area_outer = s ** 2
        area_inner = (s - 2 * t_w) ** 2
        area_shs   = area_outer - area_inner               # hollow section area
        vol_leg    = area_shs * leg_height_m
        w_web      = vol_leg * density_kg_m3               # reuse key name for consistency

        # 2. Base plate: square, 2× leg section, standard thickness
        base_side  = s * 2.0
        vol_base   = base_side ** 2 * t_b
        w_base     = vol_base * density_kg_m3

        # 3. Gussets (2 per leg): triangular, leg_section × leg_section / 2
        area_gusset = 0.5 * s * s
        vol_gussets = 2 * area_gusset * t_g
        w_gussets   = vol_gussets * density_kg_m3

        note = (f"Hollow square section {leg_section_mm:.0f}×{leg_section_mm:.0f} mm, "
                f"t_wall={t_w*1000:.1f} mm, h={leg_height_m:.2f} m, "
                f"base {base_side*1000:.0f}×{base_side*1000:.0f} mm, "
                f"2 gussets t={gusset_thickness_mm:.0f} mm per leg")

    w_per    = w_web + w_base + w_gussets
    w_total  = w_per * n

    return {
        "support_type":             support_type,
        "n_supports":               n,
        "weight_web_or_leg_kg":     round(w_web    * n, 1),
        "weight_base_plates_kg":    round(w_base   * n, 1),
        "weight_gussets_kg":        round(w_gussets * n, 1),
        "weight_per_support_kg":    round(w_per,  1),
        "weight_all_supports_kg":   round(w_total, 1),
        "weight_all_supports_t":    round(w_total / 1000, 4),
        "notes":                    note,
    }


# =============================================================================
# OPERATING (WORKING) WEIGHT
# =============================================================================

def operating_weight(
    layers: list,
    avg_area_m2: float,
    vessel_id_m: float,
    cyl_len_m: float,
    h_dish_m: float,
    end_type: str,
    w_empty_kg: float,
    n_supports: int,
    rho_water_kg_m3: float = 1025.0,
    w_lining_kg: float = 0.0,
) -> dict:
    """
    Operating (working) weight of a filled horizontal MMF vessel.

    Components
    ----------
    1. Empty vessel (steel structure)   — passed in as w_empty_kg
    2. Internal lining / coating        — passed in as w_lining_kg
    3. Media (dry solid mass)           — layer depth × area × rho_p × (1−ε₀)
    4. Water                            — (total internal volume − media solid volume) × rho_water

    Total internal volume
    ---------------------
    V_total = V_cylinder + V_two_heads
            = π/4 × ID² × L_cyl  +  2 × dish_volume(ID, ID, h_dish, end_type)

    Water volume (vessel running full, pressure)
    ────────────────────────────────────────────
    V_water = V_total − Σ(depth_i × area × (1−ε₀_i))

    Support load
    ─────────────
    Operating load per support = (empty + lining + media + water) / n_supports
    """
    from engine.geometry import dish_volume

    # ── Total internal volume ─────────────────────────────────────────────
    v_cyl   = math.pi / 4.0 * vessel_id_m**2 * cyl_len_m
    v_heads = dish_volume(vessel_id_m, vessel_id_m, h_dish_m, end_type) * 2.0
    v_total = v_cyl + v_heads

    # ── Media: solid volume and dry mass per layer ────────────────────────
    media_rows = []
    v_solid_total = 0.0
    w_media_total = 0.0

    for L in layers:
        depth   = L.get("Depth",    0.0)
        eps0    = L.get("epsilon0", 0.42)
        rho_p   = L.get("rho_p_eff", 2650.0)
        is_sup  = L.get("is_support", False)

        v_bulk   = depth * avg_area_m2              # m³ bulk (solid + pores)
        v_solid  = v_bulk * (1.0 - eps0)            # m³ pure solid
        w_dry    = v_solid * rho_p                   # kg dry mass

        v_solid_total += v_solid
        w_media_total += w_dry

        media_rows.append({
            "Media":           L.get("Type", "—"),
            "Support layer":   "✓" if is_sup else "",
            "Depth (m)":       round(depth,  3),
            "Area (m²)":       round(avg_area_m2, 2),
            "V bulk (m³)":     round(v_bulk, 3),
            "ε₀":              round(eps0,   3),
            "ρ particle (kg/m³)": round(rho_p, 0),
            "V solid (m³)":    round(v_solid, 4),
            "Dry mass (kg)":   round(w_dry,  1),
        })

    # ── Water volume and mass ─────────────────────────────────────────────
    v_water  = v_total - v_solid_total
    w_water  = v_water * rho_water_kg_m3

    # ── Operating totals ──────────────────────────────────────────────────
    w_operating = w_empty_kg + w_lining_kg + w_media_total + w_water
    load_per_support = w_operating / max(n_supports, 1)

    return {
        # volumes
        "v_cylinder_m3":        round(v_cyl,          3),
        "v_heads_m3":           round(v_heads,         3),
        "v_total_internal_m3":  round(v_total,         3),
        "v_solid_media_m3":     round(v_solid_total,   4),
        "v_water_m3":           round(v_water,         3),
        # masses
        "w_empty_kg":           round(w_empty_kg,      1),
        "w_lining_kg":          round(w_lining_kg,     1),
        "w_media_kg":           round(w_media_total,   1),
        "w_water_kg":           round(w_water,         1),
        "w_operating_kg":       round(w_operating,     1),
        "w_operating_t":        round(w_operating / 1000, 3),
        # support loads
        "n_supports":           n_supports,
        "load_per_support_kg":  round(load_per_support, 1),
        "load_per_support_t":   round(load_per_support / 1000, 3),
        "load_per_support_kN":  round(load_per_support * 9.81 / 1000, 2),
        # detail
        "media_rows":           media_rows,
        "rho_water_kg_m3":      rho_water_kg_m3,
    }


# =============================================================================
# SADDLE DESIGN — positioning, section selection, structural estimate
# =============================================================================

def _n_ribs_from_width(piece_length_m: float, rib_pitch_m: float = 0.45) -> int:
    """
    Number of web stiffener ribs per saddle assembly.

    Ribs are vertical stiffener plates spaced along the saddle width
    (= piece_length_m, i.e. the saddle dimension along the vessel axis).
    Pitch ~450 mm gives the best match to fabricated saddle weights in practice.
    """
    return max(2, round(piece_length_m / rib_pitch_m) + 1)


def _zick_saddle_positions_raw(total_length_m: float, a_m: float, n: int) -> list[float]:
    """Axial centres of saddle supports along shell (tangent x = 0 to x = L), metres."""
    if n <= 0:
        return []
    if n == 1:
        return [round(total_length_m / 2.0, 3)]
    if n == 2:
        return [round(a_m, 3), round(total_length_m - a_m, 3)]
    inner_gap = (total_length_m - 2 * a_m) / (n - 1)
    return [round(a_m + i * inner_gap, 3) for i in range(n)]


def _nudge_saddle_centres_clear_nozzles(
    xs: list[float],
    shell_len: float,
    saddle_half_w_m: float,
) -> list[float]:
    """
    Shift saddle centroids along the shell so they do not sit under the schematic
    vent (≈0.2L) or drain (≈0.8L) nozzle stubs on the GA elevation.
    """
    if shell_len <= 0 or not xs:
        return xs
    clearance = max(0.42, saddle_half_w_m * 1.25)
    zones = [(0.2 * shell_len, clearance), (0.72 * shell_len, clearance)]
    out: list[float] = []
    for xc in sorted(xs):
        xcf = float(xc)
        for cz, cl in zones:
            if abs(xcf - cz) < cl:
                direction = -1.0 if xcf > shell_len * 0.5 else 1.0
                step = max(0.05, 0.015 * shell_len)
                for _ in range(80):
                    xcf += direction * step
                    if xcf < 0.05 * shell_len or xcf > 0.95 * shell_len:
                        xcf = float(xc)
                        break
                    if all(abs(xcf - zc2) >= cl2 for zc2, cl2 in zones):
                        break
        out.append(round(xcf, 3))
    return sorted(out)


def saddle_design(
    total_length_m: float,
    vessel_od_m: float,
    vessel_id_m: float,
    w_operating_kg: float,
    n_saddles: int              = 2,
    contact_angle_deg: float    = 120.0,
    rib_plate_factor: float     = 1.10,
) -> dict:
    """
    Zick-based saddle positioning, section selection, and structural weight.

    If the requested ``n_saddles`` produces a reaction above catalogue capacity,
    the model **automatically uses the smallest n** from the alternatives table
    that fits (e.g. 3 saddles when 2 are overstressed).

    Saddle centres are nudged along the shell to reduce overlap with schematic
    vent (≈0.2L) and drain (≈0.72L) locations on the elevation GA.
    """
    # ── Spacing factor ────────────────────────────────────────────────────
    ld_ratio = total_length_m / vessel_od_m if vessel_od_m > 0 else 0.0
    if ld_ratio < 3.0:
        alpha = 0.25
    elif ld_ratio < 5.0:
        alpha = 0.22
    else:
        alpha = 0.20

    a_m = alpha * total_length_m
    R_m = vessel_id_m / 2.0
    arc_m = math.pi * R_m * contact_angle_deg / 180.0

    # ── Alternatives (reaction vs catalogue) ─────────────────────────────
    alternatives: list[dict] = []
    max_catalogue_t = SADDLE_CATALOGUE[-1][0]
    min_n_needed = max(1, math.ceil(w_operating_kg / 1000.0 / max_catalogue_t))

    for alt_n in range(1, 6):
        alt_reaction_t = w_operating_kg / alt_n / 1000.0
        alt_sel = None
        for c_t, c_sec, c_kgm, c_len, c_paint in SADDLE_CATALOGUE:
            if c_t >= alt_reaction_t:
                alt_sel = (c_t, c_sec, c_kgm, c_len, c_paint)
                break
        fits = alt_sel is not None
        if not fits:
            alt_sel = SADDLE_CATALOGUE[-1]

        alt_cap_t, alt_sec, alt_kgm, alt_len, alt_paint = alt_sel
        alt_pw = alt_kgm * alt_len
        alt_n_rib = _n_ribs_from_width(alt_len)
        alt_w_ea = alt_pw * alt_n_rib * rib_plate_factor

        if alt_n == 1:
            alt_positions = [round(total_length_m / 2.0, 3)]
        elif alt_n == 2:
            alt_positions = [round(a_m, 3), round(total_length_m - a_m, 3)]
        else:
            inner_gap = (total_length_m - 2 * a_m) / (alt_n - 1)
            alt_positions = [round(a_m + i * inner_gap, 3) for i in range(alt_n)]

        alternatives.append({
            "n_saddles": alt_n,
            "reaction_t": round(alt_reaction_t, 2),
            "reaction_kN": round(alt_reaction_t * 1000 * 9.81 / 1000, 0),
            "fits_catalogue": fits,
            "capacity_t": alt_cap_t,
            "section": alt_sec,
            "struct_wt_ea_kg": round(alt_w_ea, 0),
            "struct_wt_total_kg": round(alt_w_ea * alt_n, 0),
            "positions_m": alt_positions,
            "is_current": False,
        })

    n_requested = max(1, int(n_saddles))
    user_fits = next(
        (a["fits_catalogue"] for a in alternatives if a["n_saddles"] == n_requested),
        False,
    )
    n_eff = n_requested if user_fits else next(
        (a["n_saddles"] for a in alternatives if a["fits_catalogue"]),
        n_requested,
    )
    auto_escalated_saddles = n_eff != n_requested

    for a in alternatives:
        a["is_current"] = a["n_saddles"] == n_eff

    saddle_hw = max(vessel_od_m * _SADDLE_WIDTH_RATIO * 0.55, total_length_m * 0.012)
    raw_positions = _zick_saddle_positions_raw(total_length_m, a_m, n_eff)
    saddle_positions_m = _nudge_saddle_centres_clear_nozzles(
        raw_positions, total_length_m, saddle_hw,
    )
    saddle_1_m = saddle_positions_m[0]
    saddle_2_m = (
        saddle_positions_m[-1] if len(saddle_positions_m) > 1 else saddle_positions_m[0]
    )
    saddle_spacings_m = [
        round(saddle_positions_m[i + 1] - saddle_positions_m[i], 3)
        for i in range(len(saddle_positions_m) - 1)
    ]
    saddle_gap_m = (
        saddle_spacings_m[0]
        if len(saddle_spacings_m) == 1
        else (min(saddle_spacings_m) if saddle_spacings_m else 0.0)
    )

    a_for_zick = min(saddle_positions_m[0], total_length_m - saddle_positions_m[-1])
    a_over_R = a_for_zick / R_m if R_m > 0 else 0.0

    reaction_kg = w_operating_kg / max(n_eff, 1)
    reaction_t = reaction_kg / 1000.0
    reaction_kN = reaction_kg * 9.81 / 1000.0
    m_saddle_kNm = reaction_kN * a_for_zick

    selected = None
    overstressed = False
    for cap_t, section, kg_m, piece_len, paint_m2m in SADDLE_CATALOGUE:
        if cap_t >= reaction_t:
            selected = (cap_t, section, kg_m, piece_len, paint_m2m)
            break
    if selected is None:
        selected = SADDLE_CATALOGUE[-1]
        overstressed = True

    cap_t, section, kg_m, piece_len, paint_m2m = selected
    piece_wt_kg = kg_m * piece_len
    piece_paint_m2 = paint_m2m * piece_len

    n_ribs = _n_ribs_from_width(piece_len)
    w_ribs_kg = n_ribs * piece_wt_kg
    w_saddle_kg = w_ribs_kg * rib_plate_factor
    w_two_saddles_kg = w_saddle_kg * n_eff

    base_w_m = min(vessel_od_m * 0.8, 3.0)
    base_area_m2 = base_w_m * piece_len
    bearing_kPa = (reaction_kN / base_area_m2) if base_area_m2 > 0 else 0.0

    catalogue_rows = []
    for c_t, c_sec, c_kgm, c_len, c_paint in SADDLE_CATALOGUE:
        c_pw = c_kgm * c_len
        c_n = _n_ribs_from_width(c_len)
        catalogue_rows.append({
            "Capacity (t)": c_t,
            "Section": c_sec,
            "kg/m": c_kgm,
            "Piece L (m)": c_len,
            "Piece wt (kg)": round(c_pw, 1),
            "Ribs/saddle": c_n,
            "Struct. wt/saddle (kg)": round(c_pw * c_n * rib_plate_factor, 1),
            "Paint m²/piece": round(c_paint * c_len, 2),
            "Selected": "✅" if c_sec == section else "",
        })

    return {
        "ld_ratio": round(ld_ratio, 2),
        "alpha": alpha,
        "alpha_pct": int(alpha * 100),
        "saddle_1_from_left_m": round(saddle_1_m, 3),
        "saddle_2_from_left_m": round(saddle_2_m, 3),
        "saddle_gap_m": round(saddle_gap_m, 3),
        "saddle_positions_m": saddle_positions_m,
        "saddle_spacings_m": saddle_spacings_m,
        "n_saddles_requested": n_requested,
        "n_saddles_effective": n_eff,
        "auto_escalated_saddles": auto_escalated_saddles,
        "a_over_R": round(a_over_R, 3),
        "a_over_R_ok": a_over_R <= 0.5,
        "contact_angle_deg": contact_angle_deg,
        "arc_m": round(arc_m, 3),
        "n_saddles": n_eff,
        "w_operating_kg": round(w_operating_kg, 1),
        "reaction_kg": round(reaction_kg, 1),
        "reaction_t": round(reaction_t, 3),
        "reaction_kN": round(reaction_kN, 1),
        "m_saddle_kNm": round(m_saddle_kNm, 1),
        "capacity_t": cap_t,
        "section": section,
        "kg_per_m": kg_m,
        "piece_length_m": piece_len,
        "piece_weight_kg": round(piece_wt_kg, 1),
        "piece_paint_m2": round(piece_paint_m2, 2),
        "n_ribs": n_ribs,
        "overstressed": overstressed,
        "w_ribs_kg": round(w_ribs_kg, 1),
        "w_one_saddle_kg": round(w_saddle_kg, 1),
        "w_two_saddles_kg": round(w_two_saddles_kg, 1),
        "base_width_m": round(base_w_m, 3),
        "base_area_m2": round(base_area_m2, 3),
        "bearing_kPa": round(bearing_kPa, 1),
        "catalogue_rows": catalogue_rows,
        "alternatives": alternatives,
        "min_n_needed": min_n_needed,
    }