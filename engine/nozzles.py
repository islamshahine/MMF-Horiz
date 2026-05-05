"""
engine/nozzles.py
─────────────────
Nozzle schedule engine for horizontal pressure-vessel sizing.

Responsibilities
----------------
1. Estimate DN for each service from process flows (feed, BW, air-scour, drain, vent, instruments)
2. Look up pipe wall thickness from DN + schedule (ASME B36.10 / B36.19)
3. Look up flange weight from DN + pressure class (EN 1092-1 or ASME B16.5)
4. Calculate nozzle stub weight (pipe + flange) per nozzle
5. Return a structured nozzle schedule ready for st.data_editor

Design philosophy
-----------------
• All lookup tables are plain Python dicts — easy to extend without touching logic.
• Velocity targets follow water-treatment norms (not general-purpose piping).
• BW flow is always ≥ 2× filtration flow; the function enforces this explicitly.
• Every public function returns a plain dict or list-of-dicts — no Streamlit coupling.
"""

import math

# =============================================================================
# VELOCITY TARGETS  (m/s)  — water-treatment service norms
# =============================================================================
VELOCITY_TARGETS = {
    "Feed inlet":        1.5,   # gravity / low-ΔP feed — kept gentle
    "Filtrate outlet":   1.5,
    "Backwash inlet":    2.0,   # BW runs for minutes, higher velocity OK
    "Backwash outlet":   1.5,   # expansion water exits — same as filtrate
    "Air scour":         15.0,  # air line — m/s in pipe (volumetric basis)
    "Drain":             1.2,   # gravity drain — conservative
    "Vent":              8.0,   # air vent
    "Sample / instrument": 0.5, # small connection, low velocity irrelevant
}

# =============================================================================
# NOMINAL BORE (DN) SERIES  — standard sizes (mm)
# =============================================================================
DN_SERIES = [
    15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200,
    250, 300, 350, 400, 450, 500, 600, 700, 800, 900, 1000,
]

# =============================================================================
# PIPE SCHEDULE — wall thickness (mm)
# Source: ASME B36.10M (carbon steel) / B36.19M (stainless)
# Keys: DN (mm), Values: {schedule: wall_mm}
# Only the schedules relevant to pressure-vessel nozzles are included.
# =============================================================================
PIPE_SCHEDULE = {
    15:   {"Sch 40": 2.77,  "Sch 80": 3.73,  "Sch 160": 4.78},
    20:   {"Sch 40": 2.87,  "Sch 80": 3.91,  "Sch 160": 5.56},
    25:   {"Sch 40": 3.38,  "Sch 80": 4.55,  "Sch 160": 6.35},
    32:   {"Sch 40": 3.56,  "Sch 80": 4.85,  "Sch 160": 7.14},
    40:   {"Sch 40": 3.68,  "Sch 80": 5.08,  "Sch 160": 7.92},
    50:   {"Sch 40": 3.91,  "Sch 80": 5.54,  "Sch 160": 8.74},
    65:   {"Sch 40": 5.16,  "Sch 80": 7.01,  "Sch 160": 9.53},
    80:   {"Sch 40": 5.49,  "Sch 80": 7.62,  "Sch 160": 11.13},
    100:  {"Sch 40": 6.02,  "Sch 80": 8.56,  "Sch 160": 13.49},
    125:  {"Sch 40": 6.55,  "Sch 80": 9.53,  "Sch 160": 15.88},
    150:  {"Sch 40": 7.11,  "Sch 80": 10.97, "Sch 160": 18.26},
    200:  {"Sch 40": 8.18,  "Sch 80": 12.70, "Sch 160": 23.01},
    250:  {"Sch 40": 9.27,  "Sch 80": 15.09, "Sch 160": 28.58},
    300:  {"Sch 40": 9.53,  "Sch 80": 15.88, "Sch 160": 33.32},
    350:  {"Sch 40": 9.53,  "Sch 80": 17.48, "Sch 160": 35.71},
    400:  {"Sch 40": 9.53,  "Sch 80": 19.05, "Sch 160": 40.49},
    450:  {"Sch 40": 9.53,  "Sch 80": 19.05, "Sch 160": 45.24},
    500:  {"Sch 40": 9.53,  "Sch 80": 19.05, "Sch 160": 50.01},
    600:  {"Sch 40": 9.53,  "Sch 80": 17.48, "Sch 160": 59.54},
    700:  {"Sch 20": 7.92,  "Sch 40": 11.13, "Sch 80": 19.05},
    800:  {"Sch 20": 7.92,  "Sch 40": 12.70, "Sch 80": 20.62},
    900:  {"Sch 20": 7.92,  "Sch 40": 14.27, "Sch 80": 23.83},
    1000: {"Sch 20": 9.53,  "Sch 40": 15.88, "Sch 80": 25.40},
}

# Default schedule per service (conservative for pressure-vessel nozzles)
DEFAULT_SCHEDULE = {
    "Feed inlet":          "Sch 40",
    "Filtrate outlet":     "Sch 40",
    "Backwash inlet":      "Sch 40",
    "Backwash outlet":     "Sch 40",
    "Air scour":           "Sch 40",
    "Drain":               "Sch 80",
    "Vent":                "Sch 80",
    "Sample / instrument": "Sch 80",
}

# =============================================================================
# WELD-NECK FLANGE WEIGHT (kg)  — EN 1092-1, PN 10 / PN 16 / PN 25
# Approximate values; actual weights vary by manufacturer ± 5–10%.
# Source: Armaturen catalogue averages, rounded to 0.5 kg.
# =============================================================================
FLANGE_WEIGHT = {
    #  DN:  {PN10, PN16, PN25}  kg  (weld-neck, one flange)
    15:   {"PN 10": 0.5,   "PN 16": 0.5,   "PN 25": 0.5},
    20:   {"PN 10": 0.5,   "PN 16": 0.5,   "PN 25": 1.0},
    25:   {"PN 10": 0.5,   "PN 16": 1.0,   "PN 25": 1.0},
    32:   {"PN 10": 1.0,   "PN 16": 1.0,   "PN 25": 1.5},
    40:   {"PN 10": 1.0,   "PN 16": 1.5,   "PN 25": 1.5},
    50:   {"PN 10": 1.5,   "PN 16": 2.0,   "PN 25": 2.5},
    65:   {"PN 10": 2.0,   "PN 16": 2.5,   "PN 25": 3.5},
    80:   {"PN 10": 2.5,   "PN 16": 3.5,   "PN 25": 4.5},
    100:  {"PN 10": 3.5,   "PN 16": 5.0,   "PN 25": 6.5},
    125:  {"PN 10": 5.0,   "PN 16": 7.0,   "PN 25": 9.5},
    150:  {"PN 10": 7.0,   "PN 16": 9.5,   "PN 25": 13.0},
    200:  {"PN 10": 11.0,  "PN 16": 15.0,  "PN 25": 21.0},
    250:  {"PN 10": 17.0,  "PN 16": 22.0,  "PN 25": 31.0},
    300:  {"PN 10": 23.0,  "PN 16": 31.0,  "PN 25": 44.0},
    350:  {"PN 10": 30.0,  "PN 16": 40.0,  "PN 25": 57.0},
    400:  {"PN 10": 38.0,  "PN 16": 52.0,  "PN 25": 74.0},
    450:  {"PN 10": 48.0,  "PN 16": 65.0,  "PN 25": 93.0},
    500:  {"PN 10": 60.0,  "PN 16": 81.0,  "PN 25": 117.0},
    600:  {"PN 10": 87.0,  "PN 16": 119.0, "PN 25": 172.0},
    700:  {"PN 10": 120.0, "PN 16": 164.0, "PN 25": 237.0},
    800:  {"PN 10": 158.0, "PN 16": 216.0, "PN 25": 313.0},
    900:  {"PN 10": 202.0, "PN 16": 276.0, "PN 25": 400.0},
    1000: {"PN 10": 252.0, "PN 16": 344.0, "PN 25": 499.0},
}

FLANGE_RATINGS = ["PN 10", "PN 16", "PN 25"]
SCHEDULES      = ["Sch 20", "Sch 40", "Sch 80", "Sch 160"]

# =============================================================================
# NOZZLE SERVICE DEFINITIONS
# =============================================================================
# Each entry: (service_label, default_qty, notes)
NOZZLE_SERVICES = [
    ("Feed inlet",           1, "Process feed water"),
    ("Filtrate outlet",      1, "Filtered water to downstream"),
    ("Backwash inlet",       1, "BW pump supply — sized for BW flow"),
    ("Backwash outlet",      1, "BW waste to drain/recovery"),
    ("Air scour",            1, "Blower air supply"),
    ("Drain",                1, "Vessel drain — bottom"),
    ("Vent",                 1, "Top vent / air release"),
    ("Sample / instrument",  4, "LT × 1, PT × 2, FT × 1"),
]

STEEL_DENSITY = 7850.0  # kg/m³


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def round_up_dn(dn_calc_mm: float) -> int:
    """Round a calculated bore up to the nearest standard DN."""
    for dn in DN_SERIES:
        if dn >= dn_calc_mm:
            return dn
    return DN_SERIES[-1]


def flow_to_dn(flow_m3h: float, velocity_ms: float) -> int:
    """
    Calculate minimum DN from volumetric flow and target velocity.
    Returns the next standard DN above the calculated bore.

    flow_m3h   : m³/h
    velocity_ms: m/s
    """
    if velocity_ms <= 0 or flow_m3h <= 0:
        return DN_SERIES[0]
    q_m3s = flow_m3h / 3600.0
    area   = q_m3s / velocity_ms          # m²
    d_calc = math.sqrt(4 * area / math.pi) * 1000  # mm (internal bore)
    return round_up_dn(d_calc)


def nozzle_stub_weight(
    dn_mm: int,
    schedule: str,
    stub_length_mm: float,
    rating: str,
    qty: int,
    density: float = STEEL_DENSITY,
) -> dict:
    """
    Weight of one nozzle assembly = pipe stub + one weld-neck flange.
    Stub length is a reasonable engineering assumption (300 mm for small,
    400 mm for large — caller may override).

    Returns dict with weight_per_nozzle_kg and weight_total_kg.
    """
    # Wall thickness
    sched_data = PIPE_SCHEDULE.get(dn_mm, {})
    # Fall back to nearest available schedule
    if schedule not in sched_data:
        schedule = list(sched_data.keys())[0] if sched_data else "Sch 40"
    t_wall = sched_data.get(schedule, 6.0)  # mm

    # Pipe stub: thin-walled cylinder, mid-wall diameter
    od_pipe   = dn_mm + 2 * t_wall                   # mm OD
    d_mid     = (dn_mm + od_pipe) / 2 / 1000         # m, mid-wall
    L_stub    = stub_length_mm / 1000                 # m
    vol_stub  = math.pi * d_mid * t_wall / 1000 * L_stub  # m³
    w_stub    = vol_stub * density                    # kg

    # Flange
    flange_data  = FLANGE_WEIGHT.get(dn_mm, {})
    w_flange     = flange_data.get(rating, 10.0)      # kg, one flange

    w_per_nozzle = w_stub + w_flange
    return {
        "dn_mm":              dn_mm,
        "schedule":           schedule,
        "rating":             rating,
        "stub_length_mm":     stub_length_mm,
        "t_wall_mm":          t_wall,
        "weight_stub_kg":     round(w_stub, 2),
        "weight_flange_kg":   round(w_flange, 2),
        "weight_per_nozzle_kg": round(w_per_nozzle, 2),
        "qty":                qty,
        "weight_total_kg":    round(w_per_nozzle * qty, 2),
    }


def estimate_nozzle_schedule(
    q_filter_m3h: float,
    bw_velocity_ms: float   = 30.0,   # m/h — BW superficial velocity through vessel
    area_filter_m2: float   = 120.0,  # avg filter cross-section area
    default_rating: str     = "PN 10",
    stub_length_mm: float   = 350.0,
    air_scour_ms: float     = 15.0,   # air velocity in pipe, m/s
) -> list[dict]:
    """
    Auto-generate a nozzle schedule from process parameters.

    Parameters
    ----------
    q_filter_m3h    : Normal (N-scenario) flow per filter, m³/h
    bw_velocity_ms  : BW superficial velocity through vessel, m/h
                      (converted to pipe flow — BW pipe flow = bw_velocity × filter_area)
    area_filter_m2  : Average filter cross-section area, m²
    default_rating  : Pressure rating for all nozzles
    stub_length_mm  : Nozzle stub projection from vessel wall, mm
    air_scour_ms    : Air velocity in the air-scour pipe, m/s

    Returns
    -------
    List of dicts, one per service, suitable for pd.DataFrame and st.data_editor.
    """
    # BW flow — must be ≥ 2× filtration flow; use actual BW rate calculation
    q_bw_m3h = max(bw_velocity_ms * area_filter_m2, 2.0 * q_filter_m3h)

    # Air scour flow: typical 55 m/h superficial → convert to volumetric m³/h
    q_air_m3h = 55.0 * area_filter_m2  # m³/h of air (at vessel conditions)

    # Flow map per service
    service_flows = {
        "Feed inlet":           q_filter_m3h,
        "Filtrate outlet":      q_filter_m3h,
        "Backwash inlet":       q_bw_m3h,
        "Backwash outlet":      q_bw_m3h,
        "Air scour":            q_air_m3h,
        "Drain":                q_filter_m3h * 0.5,   # gravity drain — half filtration rate
        "Vent":                 q_air_m3h * 0.1,      # small vent
        "Sample / instrument":  0.0,                   # no flow basis — use min DN
    }

    schedule = []
    for service, default_qty, notes in NOZZLE_SERVICES:

        q    = service_flows.get(service, q_filter_m3h)
        v_t  = VELOCITY_TARGETS.get(service, 1.5)

        # For air scour the flow is in m³/h of air, velocity target is m/s
        if service == "Air scour":
            dn = flow_to_dn(q, air_scour_ms)
        elif service == "Sample / instrument":
            dn = 25   # fixed: 1" instrument nozzle
        else:
            dn = flow_to_dn(q, v_t)

        sched_key = DEFAULT_SCHEDULE.get(service, "Sch 40")
        # Ensure schedule exists for this DN
        avail = list(PIPE_SCHEDULE.get(dn, {"Sch 40": 6.0}).keys())
        if sched_key not in avail:
            sched_key = avail[0]

        # Actual velocity through the chosen DN
        if q > 0 and service != "Sample / instrument":
            id_m  = dn / 1000
            v_act = (q / 3600) / (math.pi / 4 * id_m ** 2)
        else:
            v_act = 0.0

        wt = nozzle_stub_weight(dn, sched_key, stub_length_mm, default_rating, default_qty)

        schedule.append({
            "Service":            service,
            "Flow (m³/h)":        round(q, 1),
            "DN (mm)":            dn,
            "Schedule":           sched_key,
            "Rating":             default_rating,
            "Velocity (m/s)":     round(v_act, 2),
            "Qty":                default_qty,
            "Stub L (mm)":        int(stub_length_mm),
            "t wall (mm)":        wt["t_wall_mm"],
            "Wt/nozzle (kg)":     wt["weight_per_nozzle_kg"],
            "Total wt (kg)":      wt["weight_total_kg"],
            "Notes":              notes,
        })

    return schedule


def schedule_total_weight(schedule: list[dict]) -> float:
    """Sum of all nozzle total weights in the schedule, kg."""
    return sum(row.get("Total wt (kg)", 0) for row in schedule)