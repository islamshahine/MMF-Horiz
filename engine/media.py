"""
engine/media.py
Media engineering database for AQUASIGHT™ MMF.
Single source of truth for all media definitions.
"""

MEDIA_DATABASE = {

    "Gravel": {
        "d10": 6.0, "cu": 1.0, "epsilon0": 0.46,
        "rho_p_eff": 2600, "d60": 6.0, "default_depth": 0.20,
        "media_category": "support",
        "density_class": "heavy", "bw_tendency": "low",
        "bio_compatible": False,
        "media_function": "Structural support layer",
        "process_role": "No filtration role — bed support only",
        "lv_min": None, "lv_max": None,
        "ebct_min": None, "ebct_max": None,
        "gac_modes": None,
    },

    "Gravel (2–3 mm)": {
        "d10": 2.5, "cu": 1.2, "epsilon0": 0.44,
        "rho_p_eff": 2650, "d60": 3.0, "default_depth": 0.25,
        "media_category": "support",
        "density_class": "heavy", "bw_tendency": "low",
        "bio_compatible": False,
        "media_function": "Fine gravel support / drainage — 2–3 mm grading",
        "process_role": "Bed support and uniform flow distribution under sand",
        "lv_min": None, "lv_max": None,
        "ebct_min": None, "ebct_max": None,
        "gac_modes": None,
    },

    "Fine Sand": {
        "d10": 0.8, "cu": 1.3, "epsilon0": 0.42,
        "rho_p_eff": 2650, "d60": 1.04, "default_depth": 0.80,
        "media_category": "mechanical_filtration",
        "density_class": "heavy", "bw_tendency": "medium",
        "bio_compatible": False,
        "media_function": "Fine solids polishing",
        "process_role": "Fine filtration — primary solids capture",
        "lv_min": 5, "lv_max": 10,
        "ebct_min": 4, "ebct_max": 8,
        "gac_modes": None,
    },

    "Fine Sand (Extra)": {
        "d10": 0.50, "cu": 1.3, "epsilon0": 0.41,
        "rho_p_eff": 2650, "d60": 0.65, "default_depth": 0.70,
        "media_category": "mechanical_filtration",
        "density_class": "heavy", "bw_tendency": "medium",
        "bio_compatible": False,
        "media_function": "Extra-fine solids polishing",
        "process_role": "Fine filtration — sub-micron solids capture",
        "lv_min": 4, "lv_max": 8,
        "ebct_min": 5, "ebct_max": 10,
        "gac_modes": None,
    },

    "Coarse Sand": {
        "d10": 1.35, "cu": 1.5, "epsilon0": 0.44,
        "rho_p_eff": 2650, "d60": 2.03, "default_depth": 0.60,
        "media_category": "mechanical_filtration",
        "density_class": "heavy", "bw_tendency": "medium",
        "bio_compatible": False,
        "media_function": "Coarse solids filtration",
        "process_role": "Intermediate polishing layer",
        "lv_min": 6, "lv_max": 12,
        "ebct_min": 3, "ebct_max": 6,
        "gac_modes": None,
    },

    "Anthracite": {
        "d10": 1.3, "cu": 1.5, "epsilon0": 0.48,
        "rho_p_eff": 1450, "d60": 1.95, "default_depth": 0.80,
        "media_category": "mechanical_filtration",
        "density_class": "light", "bw_tendency": "high",
        "bio_compatible": False,
        "media_function": "High-rate coarse filtration",
        "process_role": "Upper solids capture layer",
        "lv_min": 8, "lv_max": 15,
        "ebct_min": 2, "ebct_max": 5,
        "gac_modes": None,
    },

    "Garnet": {
        "d10": 0.3, "cu": 1.3, "epsilon0": 0.38,
        "rho_p_eff": 4100, "d60": 0.39, "default_depth": 0.10,
        "media_category": "polishing",
        "density_class": "heavy", "bw_tendency": "low",
        "bio_compatible": False,
        "media_function": "Fine particulate polishing",
        "process_role": "Bottom dense polishing layer",
        "lv_min": 10, "lv_max": 20,
        "ebct_min": 1, "ebct_max": 3,
        "gac_modes": None,
    },

    "MnO2": {
        "d10": 0.5, "cu": 1.4, "epsilon0": 0.40,
        "rho_p_eff": 3500, "d60": 0.70, "default_depth": 0.60,
        "media_category": "catalytic",
        "density_class": "heavy", "bw_tendency": "low",
        "bio_compatible": False,
        "media_function": "Catalytic oxidation of iron and manganese",
        "process_role": "Iron and Manganese removal layer",
        "lv_min": 5, "lv_max": 12,
        "ebct_min": 2, "ebct_max": 6,
        "gac_modes": None,
    },

    "Limestone": {
        "d10": 2.0, "cu": 1.5, "epsilon0": 0.42,
        "rho_p_eff": 2700, "d60": 3.0, "default_depth": 1.00,
        "media_category": "reactive",
        "density_class": "heavy", "bw_tendency": "low",
        "bio_compatible": False,
        "media_function": "Remineralisation by calcite dissolution",
        "process_role": "pH stabilisation and alkalinity addition",
        "lv_min": 5, "lv_max": 12,
        "ebct_min": 8, "ebct_max": 20,
        "gac_modes": None,
    },

    "Medium GAC": {
        "d10": 1.0, "cu": 1.7, "epsilon0": 0.50,
        "rho_p_eff": 500, "d60": 1.70, "default_depth": 1.00,
        "media_category": "adsorption_bio",
        "density_class": "light", "bw_tendency": "high",
        "bio_compatible": True,
        "media_function": "Adsorption + catalytic dechlorination + biological support",
        "process_role": "Organic removal / chlorine reduction / BAC biofiltration",
        "lv_min": 3, "lv_max": 15,
        "ebct_min": 2, "ebct_max": 30,
        "gac_modes": {
            "Dechlorination": {
                "lv_min": 5, "lv_max": 15,
                "ebct_min": 2, "ebct_max": 5,
                "note": "Primarily catalytic reduction of oxidants "
                        "to chloride ions. GAC dechlorination is NOT "
                        "purely adsorption. EBCT of 2-5 min is typically "
                        "sufficient.",
            },
            "Organics Adsorption": {
                "lv_min": 5, "lv_max": 10,
                "ebct_min": 10, "ebct_max": 20,
                "note": "Adsorption capacity governs performance. "
                        "Monitor TOC breakthrough. EBCT is the primary "
                        "design parameter for NOM removal.",
            },
            "BAC Biofiltration": {
                "lv_min": 3, "lv_max": 8,
                "ebct_min": 10, "ebct_max": 30,
                "note": "Biological activity requires acclimation of "
                        "4-8 weeks. Do not use chlorinated backwash. "
                        "EBCT greater than 10 min recommended.",
            },
            "Chloramine Removal": {
                "lv_min": 3, "lv_max": 6,
                "ebct_min": 10, "ebct_max": 20,
                "note": "Chloramine removal is slower than free chlorine. "
                        "Requires higher EBCT. Verify with pilot if "
                        "chloramines exceed 3 mg/L.",
            },
        },
    },

    "Biodagene": {
        "d10": 2.50, "cu": 1.4, "epsilon0": 0.42,
        "rho_p_eff": 1600, "d60": 3.50, "default_depth": 0.60,
        "media_category": "mechanical_filtration",
        "density_class": "medium", "bw_tendency": "medium",
        "bio_compatible": False,
        "media_function": "Coarse mechanical filtration",
        "process_role": "Roughing / pre-filtration layer",
        "lv_min": 5, "lv_max": 12, "ebct_min": 3, "ebct_max": 8,
        "gac_modes": None,
    },

    "Schist": {
        "d10": 3.30, "cu": 1.5, "epsilon0": 0.47,
        "rho_p_eff": 1300, "d60": 4.95, "default_depth": 0.30,
        "media_category": "mechanical_filtration",
        "density_class": "light", "bw_tendency": "high",
        "bio_compatible": False,
        "media_function": "High-rate coarse roughing",
        "process_role": "Upper coarse roughing layer",
        "lv_min": 8, "lv_max": 15, "ebct_min": 2, "ebct_max": 5,
        "gac_modes": None,
    },

    "Pumice": {
        "d10": 1.50, "cu": 1.3, "epsilon0": 0.55,
        "rho_p_eff": 900, "d60": 1.56, "default_depth": 0.60,
        "media_category": "adsorption_bio",
        "density_class": "light", "bw_tendency": "high",
        "bio_compatible": True,
        "media_function": "Porous bio-support and filtration",
        "process_role": "Biological roughing / BOD reduction",
        "lv_min": 5, "lv_max": 10, "ebct_min": 5, "ebct_max": 15,
        "gac_modes": None,
    },

    "FILTRALITE clay": {
        "d10": 1.20, "cu": 1.5, "epsilon0": 0.48,
        "rho_p_eff": 1250, "d60": 1.80, "default_depth": 0.80,
        "media_category": "adsorption_bio",
        "density_class": "light", "bw_tendency": "high",
        "bio_compatible": True,
        "media_function": "Expanded clay bio-support and filtration",
        "process_role": "Biological filtration / NOM reduction",
        "lv_min": 5, "lv_max": 10, "ebct_min": 5, "ebct_max": 15,
        "gac_modes": None,
    },

    "Custom": {
        "d10": 0.0, "cu": 1.0, "epsilon0": 0.40,
        "rho_p_eff": 2650, "d60": 0.0, "default_depth": 0.50,
        "media_category": "custom",
        "density_class": "medium", "bw_tendency": "medium",
        "bio_compatible": False,
        "media_function": "User-defined media",
        "process_role": "User-defined",
        "lv_min": None, "lv_max": None,
        "ebct_min": None, "ebct_max": None,
        "gac_modes": None,
    },
}

# Aliases to match sidebar name variants (case differences + Unicode subscript)
for _k, _v in [("Fine Sand", "Fine sand"), ("Fine Sand (Extra)", "Fine sand (extra)"),
                ("Coarse Sand", "Coarse sand"), ("MnO2", "MnO₂"),
                ("Gravel (2–3 mm)", "Gravel (2-3 mm)")]:
    MEDIA_DATABASE[_v] = MEDIA_DATABASE[_k]


def get_media_names():
    return list(MEDIA_DATABASE.keys())


def get_media(name):
    return MEDIA_DATABASE.get(name, MEDIA_DATABASE["Custom"])


def get_lv_range(name, gac_mode=None):
    m = get_media(name)
    if gac_mode and m.get("gac_modes") and gac_mode in m["gac_modes"]:
        mo = m["gac_modes"][gac_mode]
        return mo["lv_min"], mo["lv_max"]
    return m["lv_min"], m["lv_max"]


def get_ebct_range(name, gac_mode=None):
    m = get_media(name)
    if gac_mode and m.get("gac_modes") and gac_mode in m["gac_modes"]:
        mo = m["gac_modes"][gac_mode]
        return mo["ebct_min"], mo["ebct_max"]
    return m["ebct_min"], m["ebct_max"]


def get_gac_note(name, gac_mode):
    m = get_media(name)
    if m.get("gac_modes") and gac_mode in m["gac_modes"]:
        return m["gac_modes"][gac_mode].get("note", "")
    return ""


def interstitial_velocity(superficial_v_m_h, epsilon):
    if epsilon <= 0:
        return 0.0
    return round(superficial_v_m_h / epsilon, 3)


def ebct_label(media_category):
    return {
        "support":               None,
        "mechanical_filtration": "Hydraulic Residence Time (EBCT)",
        "adsorption_bio":        "Empty Bed Contact Time (EBCT)",
        "catalytic":             "Contact Time (EBCT)",
        "reactive":              "Hydraulic Retention Time (EBCT)",
        "polishing":             "Hydraulic Residence Time (EBCT)",
        "custom":                "EBCT",
    }.get(media_category, "EBCT")


def lv_status(lv_actual, lv_min, lv_max):
    if lv_min is None or lv_max is None:
        return "N/A", "ok"
    if lv_min <= lv_actual <= lv_max:
        return "Within envelope", "ok"
    hi = abs(lv_actual - lv_max) / lv_max if lv_actual > lv_max else 0
    lo = abs(lv_min - lv_actual) / lv_min if lv_actual < lv_min else 0
    pct = max(hi, lo)
    if pct <= 0.15:
        return "Approaching limit", "advisory"
    if pct <= 0.30:
        return "Outside envelope", "warning"
    return "Significantly outside envelope", "critical"


def ebct_status(ebct_actual, ebct_min, ebct_max):
    if ebct_min is None or ebct_max is None:
        return "N/A", "ok"
    if ebct_min <= ebct_actual <= ebct_max:
        return "Within envelope", "ok"
    hi = abs(ebct_actual - ebct_max) / ebct_max if ebct_actual > ebct_max else 0
    lo = abs(ebct_min - ebct_actual) / ebct_min if ebct_actual < ebct_min else 0
    pct = max(hi, lo)
    if pct <= 0.15:
        return "Approaching limit", "advisory"
    if pct <= 0.30:
        return "Outside envelope", "warning"
    return "Significantly outside envelope", "critical"


def validate_layer_order(layers):
    warnings = []
    if not layers or len(layers) < 2:
        return warnings
    bottom = layers[0]
    if bottom.get("media_category") not in ("support",):
        warnings.append({
            "level": "advisory",
            "message": (
                f"Bottom layer is {bottom.get('Type', '?')} "
                f"({bottom.get('media_category', '?')}). "
                "Support gravel is conventionally placed at the "
                "bottom to protect the nozzle plate."
            ),
        })
    for i in range(len(layers) - 1):
        lo = layers[i]
        hi = layers[i + 1]
        rlo = lo.get("rho_p_eff", 0)
        rhi = hi.get("rho_p_eff", 0)
        if rhi > rlo * 1.10:
            warnings.append({
                "level": "warning",
                "message": (
                    f"Layer {i+2} ({hi.get('Type', '?')}, "
                    f"{rhi} kg/m³) is denser than layer {i+1} "
                    f"({lo.get('Type', '?')}, {rlo} kg/m³). "
                    "Density inversion may prevent correct "
                    "restratification after backwash."
                ),
            })
    top = layers[-1]
    if top.get("media_category") == "polishing":
        warnings.append({
            "level": "warning",
            "message": (
                f"Polishing media ({top.get('Type', '?')}) is at "
                "the top of the bed. Dense polishing media such "
                "as Garnet should be at the bottom."
            ),
        })
    return warnings


def collector_max_height(vessel_id_m, clearance_mm=300):
    c = clearance_mm / 1000.0
    return min(vessel_id_m - c, vessel_id_m * 0.90)


def get_layer_intelligence(layers: list) -> tuple[list, list]:
    """Return (intelligence_rows, arrangement_warnings) for the current bed.

    intelligence_rows: one dict per layer with function / role / BW / bio fields.
    arrangement_warnings: from validate_layer_order() — level + message dicts.
    Layer dicts from the sidebar are enriched with media_category from the DB
    before arrangement validation so density/category checks work correctly.
    """
    intel = []
    enriched = []
    for i, layer in enumerate(layers):
        m     = get_media(layer.get("Type", "Custom"))
        enriched.append({**layer, "media_category": m.get("media_category", "custom")})
        notes = []
        if m.get("bio_compatible") and layer.get("gac_mode") == "BAC Biofiltration":
            notes.append("BAC mode active — use unchlorinated backwash water only.")
        if m.get("bw_tendency") == "high" and not layer.get("is_support"):
            notes.append("High BW expansion tendency — verify freeboard is adequate.")
        if m.get("bio_compatible") and not layer.get("is_support"):
            notes.append("Bio-compatible media — supports nitrification / BAC activity.")
        intel.append({
            "layer":          i + 1,
            "media":          layer.get("Type", "?"),
            "function":       m.get("media_function", "—"),
            "process_role":   m.get("process_role", "—"),
            "bw_tendency":    m.get("bw_tendency", "—"),
            "bio_compatible": m.get("bio_compatible", False),
            "density_class":  m.get("density_class", "—"),
            "notes":          notes,
        })
    return intel, validate_layer_order(enriched)
