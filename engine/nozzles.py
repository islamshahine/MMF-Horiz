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
# BW vessel nozzles: same Q — size inlet & outlet identically (not filtrate DN).
BW_VESSEL_NOZZLE_V_M_S = 1.5
BW_VESSEL_SERVICES = frozenset({"Backwash inlet", "Backwash outlet"})

VELOCITY_TARGETS = {
    "Feed inlet":        1.5,   # gravity / low-ΔP feed — kept gentle
    "Filtrate outlet":   1.5,
    "Backwash inlet":    BW_VESSEL_NOZZLE_V_M_S,
    "Backwash outlet":   BW_VESSEL_NOZZLE_V_M_S,
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

# ASME B36.10M nominal outside diameter (mm) for NPS ↔ DN mapping.
NPS_OD_MM: dict[int, float] = {
    15: 21.3, 20: 26.9, 25: 33.7, 32: 42.4, 40: 48.3, 50: 60.3,
    65: 73.0, 80: 88.9, 100: 114.3, 125: 141.3, 150: 168.3, 200: 219.1,
    250: 273.0, 300: 323.8, 350: 355.6, 400: 406.4, 450: 457.0, 500: 508.0,
    600: 610.0, 700: 711.0, 800: 813.0, 900: 914.0, 1000: 1016.0,
}

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


def nominal_od_mm(dn_mm: int) -> float:
    """Nominal pipe OD (mm) for standard DN / NPS."""
    return float(NPS_OD_MM.get(int(dn_mm), float(dn_mm)))


def pipe_internal_id_mm(dn_mm: int, schedule: str) -> float:
    """Calculate internal diameter (mm): OD − 2× wall from schedule table."""
    dn = int(dn_mm)
    sched_data = PIPE_SCHEDULE.get(dn, {"Sch 40": 9.53})
    sched_key = schedule if schedule in sched_data else next(iter(sched_data), "Sch 40")
    t_wall = float(sched_data.get(sched_key, 9.53))
    return max(1.0, nominal_od_mm(dn) - 2.0 * t_wall)


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
    air_scour_rate_m_h: float | None = None,  # superficial m/h — overrides 55 default
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

    _air_sup_m_h = float(air_scour_rate_m_h) if air_scour_rate_m_h is not None else 55.0
    q_air_m3h = _air_sup_m_h * area_filter_m2  # m³/h of air (at vessel conditions)

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

    # BW inlet & outlet: one size for the same Q (not filtrate / separate targets).
    dn_bw = flow_to_dn(q_bw_m3h, BW_VESSEL_NOZZLE_V_M_S)
    sched_bw = DEFAULT_SCHEDULE.get("Backwash outlet", "Sch 40")
    avail_bw = list(PIPE_SCHEDULE.get(dn_bw, {"Sch 40": 6.0}).keys())
    if sched_bw not in avail_bw:
        sched_bw = avail_bw[0]
    id_bw_mm = pipe_internal_id_mm(dn_bw, sched_bw)
    v_bw = (
        (q_bw_m3h / 3600.0) / (math.pi / 4.0 * (id_bw_mm / 1000.0) ** 2)
        if q_bw_m3h > 0 else 0.0
    )

    schedule = []
    for service, default_qty, notes in NOZZLE_SERVICES:

        q = service_flows.get(service, q_filter_m3h)

        if service in BW_VESSEL_SERVICES:
            dn, sched_key, id_mm, v_act = dn_bw, sched_bw, id_bw_mm, v_bw
        elif service == "Air scour":
            dn = flow_to_dn(q, air_scour_ms)
            sched_key = DEFAULT_SCHEDULE.get(service, "Sch 40")
            avail = list(PIPE_SCHEDULE.get(dn, {"Sch 40": 6.0}).keys())
            if sched_key not in avail:
                sched_key = avail[0]
            id_mm = pipe_internal_id_mm(dn, sched_key)
            v_act = (q / 3600.0) / (math.pi / 4.0 * (id_mm / 1000.0) ** 2) if q > 0 else 0.0
        elif service == "Sample / instrument":
            dn, sched_key, id_mm, v_act = 25, DEFAULT_SCHEDULE[service], pipe_internal_id_mm(25, "Sch 80"), 0.0
        else:
            v_t = VELOCITY_TARGETS.get(service, 1.5)
            dn = flow_to_dn(q, v_t)
            sched_key = DEFAULT_SCHEDULE.get(service, "Sch 40")
            avail = list(PIPE_SCHEDULE.get(dn, {"Sch 40": 6.0}).keys())
            if sched_key not in avail:
                sched_key = avail[0]
            id_mm = pipe_internal_id_mm(dn, sched_key)
            v_act = (q / 3600.0) / (math.pi / 4.0 * (id_mm / 1000.0) ** 2) if q > 0 else 0.0

        wt = nozzle_stub_weight(dn, sched_key, stub_length_mm, default_rating, default_qty)

        schedule.append({
            "Service":            service,
            "Flow (m³/h)":        round(q, 1),
            "DN (mm)":            dn,
            "ID (mm)":            round(id_mm, 2),
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


def nozzle_row_for_service(schedule: list[dict] | None, service: str) -> dict | None:
    """Return the schedule row for a named service."""
    key = str(service or "").strip()
    for row in schedule or []:
        if str(row.get("Service", "")).strip() == key:
            return row
    return None


def nozzle_internal_id_m_from_row(row: dict | None) -> float | None:
    """Internal diameter (m) from schedule row — calculated ID, not nominal DN."""
    if not row:
        return None
    for col in ("ID (mm)", "id_mm"):
        if col in row and row[col] is not None:
            try:
                return max(0.001, float(row[col]) / 1000.0)
            except (TypeError, ValueError):
                pass
    try:
        dn = int(round(float(row.get("DN (mm)", 0))))
    except (TypeError, ValueError):
        dn = 0
    if dn > 0:
        sched = str(row.get("Schedule", "Sch 40"))
        return pipe_internal_id_mm(dn, sched) / 1000.0
    return None


def nozzle_dn_mm_for_service(schedule: list[dict] | None, service: str) -> int | None:
    """Read nominal DN (mm) for a named service from a nozzle schedule."""
    key = str(service or "").strip()
    for row in schedule or []:
        if str(row.get("Service", "")).strip() != key:
            continue
        for col in ("DN (mm)", "DN_mm", "dn_mm"):
            if col in row and row[col] is not None:
                try:
                    return int(round(float(row[col])))
                except (TypeError, ValueError):
                    pass
    return None


def suggest_collector_header_id_m(
    nozzle_sched: list[dict] | None = None,
    *,
    q_filter_m3h: float = 0.0,
    bw_velocity_m_h: float = 30.0,
    area_filter_m2: float = 1.0,
    default_rating: str = "PN 10",
    stub_length_mm: float = 350.0,
    air_scour_rate_m_h: float | None = None,
) -> tuple[float, str]:
    """
    Internal collector header ID (m) from §4 **Backwash inlet & outlet** pipe ID.

    Uses calculated internal diameter (OD − 2× wall), not nominal DN. Ignores filtrate /
    feed nozzles.
    """

    def _from_sched(sched: list[dict]) -> tuple[float, str] | None:
        ids: list[float] = []
        dns: list[int] = []
        for svc in ("Backwash inlet", "Backwash outlet"):
            row = nozzle_row_for_service(sched, svc)
            id_m = nozzle_internal_id_m_from_row(row)
            if id_m:
                ids.append(id_m)
            dn = nozzle_dn_mm_for_service(sched, svc)
            if dn:
                dns.append(dn)
        if not ids:
            return None
        hid = max(ids)
        dn_note = f"DN {dns[0]}" if dns and len(set(dns)) == 1 else "matched BW nozzles"
        return (
            hid,
            f"Internal ID from §4 **Backwash inlet & outlet** ({dn_note}, "
            f"ID = OD − 2× wall, **not** filtrate DN).",
        )

    # 1) User / §4 table schedule first (Mechanical tab DN edits must beat auto-size preview).
    linked = _from_sched(nozzle_sched or [])
    if linked:
        return linked[0], linked[1]

    # 2) Live preview from current flows when no §4 rows passed in.
    if q_filter_m3h > 0 and area_filter_m2 > 0:
        preview = estimate_nozzle_schedule(
            q_filter_m3h=float(q_filter_m3h),
            bw_velocity_ms=float(bw_velocity_m_h),
            area_filter_m2=float(area_filter_m2),
            default_rating=str(default_rating),
            stub_length_mm=float(stub_length_mm),
            air_scour_rate_m_h=air_scour_rate_m_h,
        )
        linked = _from_sched(preview)
        if linked:
            return (
                linked[0],
                linked[1] + " (auto-sized from flows — edit §4 DN to override).",
            )

    return 0.25, "Default 250 mm — link after compute or enter manually."


def refresh_nozzle_row_hydraulics(row: dict) -> dict:
    """Recalculate ID (mm) and velocity after DN / schedule edit in §4 table."""
    out = dict(row)
    try:
        dn = int(round(float(out.get("DN (mm)", 0))))
    except (TypeError, ValueError):
        return out
    sched = str(out.get("Schedule", "Sch 40"))
    id_mm = pipe_internal_id_mm(dn, sched)
    out["DN (mm)"] = dn
    out["ID (mm)"] = round(id_mm, 2)
    q = float(out.get("Flow (m³/h)", 0) or 0)
    if q > 0 and id_mm > 0:
        v = (q / 3600.0) / (math.pi / 4.0 * (id_mm / 1000.0) ** 2)
        out["Velocity (m/s)"] = round(v, 2)
    return out