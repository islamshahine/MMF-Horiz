"""engine/sensitivity.py — One-at-a-time (OAT) sensitivity analysis for tornado charts.

Exports:
  PARAM_DEFS    list[dict]   — default input parameters to perturb
  OUTPUT_DEFS   list[dict]   — output metrics tracked
  run_sensitivity(inputs, param_defs=None) -> dict[output_key -> list[row_dict]]

Each row_dict: {param, base, lo, hi, swing, lo_label, hi_label}
Rows within each output are sorted by abs(swing) descending.
No Streamlit imports — pure Python only.
"""
import copy
from engine.compute import compute_all

# ── Inputs to perturb ────────────────────────────────────────────────────────
# "pct"  → vary by ±pct% of current value
# "abs"  → vary by ±abs (integer step, e.g. for n_filters)
# "dtype"→ coerce result to int after perturbing
PARAM_DEFS: list[dict] = [
    {"key": "total_flow",        "label": "Total flow",           "pct": 20.0},
    {"key": "n_filters",         "label": "No. of filters",       "abs": 2,   "dtype": int},
    {"key": "nominal_id",        "label": "Vessel ID",            "pct": 10.0},
    {"key": "bw_velocity",       "label": "BW velocity",          "pct": 20.0},
    {"key": "solid_loading",     "label": "Solid loading",        "pct": 30.0},
    {"key": "design_pressure",   "label": "Design pressure",      "pct": 15.0},
    {"key": "feed_temp",         "label": "Feed temperature",     "pct": 15.0},
    {"key": "elec_tariff",       "label": "Electricity tariff",   "pct": 30.0},
    {"key": "steel_cost_usd_kg", "label": "Steel fabrication",    "pct": 20.0},
]


# ── Output extractors (pure functions of computed dict + inputs) ──────────────
def _lv(c: dict, inp: dict) -> float:
    """Peak filtration velocity (m/h) at the N scenario."""
    area = c.get("avg_area", 1.0) or 1.0
    return c.get("q_per_filter", 0.0) / area


def _ebct(c: dict, inp: dict) -> float:
    """Minimum EBCT (min) across non-support layers at the N scenario."""
    area = c.get("avg_area", 1.0) or 1.0
    lv   = c.get("q_per_filter", 0.0) / area
    if lv <= 0:
        return 0.0
    ebcts = [
        L["Depth"] / lv * 60
        for L in inp.get("layers", [])
        if not L.get("is_support") and L.get("Depth", 0) > 0
    ]
    return min(ebcts) if ebcts else 0.0


def _capex(c: dict, inp: dict) -> float:
    """Total installed CAPEX (M USD)."""
    return c.get("econ_capex", {}).get("total_capex_usd", 0.0) / 1e6


def _dp_dirty(c: dict, inp: dict) -> float:
    """Dirty-bed media pressure drop (bar)."""
    return c.get("bw_dp", {}).get("dp_dirty_bar", 0.0)


OUTPUT_DEFS: list[dict] = [
    {"key": "lv",    "label": "Peak LV (m/h)",        "fn": _lv},
    {"key": "ebct",  "label": "Min EBCT (min)",        "fn": _ebct},
    {"key": "capex", "label": "Total CAPEX (M USD)",   "fn": _capex},
    {"key": "dp",    "label": "Dirty media ΔP (bar)",  "fn": _dp_dirty},
]


# ── Perturbation helper ───────────────────────────────────────────────────────
def _perturb(inputs: dict, pdef: dict, sign: int) -> dict:
    inp = copy.deepcopy(inputs)
    key      = pdef["key"]
    base_val = inp[key]
    if "abs" in pdef:
        new_val = base_val + sign * pdef["abs"]
    else:
        new_val = base_val * (1.0 + sign * pdef["pct"] / 100.0)
    if pdef.get("dtype") == int:
        new_val = max(1, int(round(new_val)))
    inp[key] = new_val
    return inp


# ── Main analysis function ────────────────────────────────────────────────────
def run_sensitivity(inputs: dict, param_defs: list | None = None) -> dict:
    """Run OAT sensitivity analysis.

    Returns dict mapping output_key → list of row_dicts, each sorted by
    abs(swing) descending so the largest driver is at the top.
    """
    if param_defs is None:
        param_defs = PARAM_DEFS
    active = [p for p in param_defs if p["key"] in inputs]

    c_base   = compute_all(inputs)
    base_out = {od["key"]: od["fn"](c_base, inputs) for od in OUTPUT_DEFS}

    rows: dict[str, list] = {od["key"]: [] for od in OUTPUT_DEFS}

    for pdef in active:
        inp_hi = _perturb(inputs, pdef, +1)
        inp_lo = _perturb(inputs, pdef, -1)
        c_hi   = compute_all(inp_hi)
        c_lo   = compute_all(inp_lo)
        lo_lbl = (f"−{pdef['abs']}"      if "abs"  in pdef
                  else f"−{pdef['pct']:.0f}%")
        hi_lbl = (f"+{pdef['abs']}"      if "abs"  in pdef
                  else f"+{pdef['pct']:.0f}%")
        for od in OUTPUT_DEFS:
            ok   = od["key"]
            bv   = base_out[ok]
            hi_v = od["fn"](c_hi, inp_hi)
            lo_v = od["fn"](c_lo, inp_lo)
            rows[ok].append({
                "param":    pdef["label"],
                "base":     bv,
                "lo":       lo_v,
                "hi":       hi_v,
                "swing":    hi_v - lo_v,
                "lo_label": lo_lbl,
                "hi_label": hi_lbl,
            })

    for ok in rows:
        rows[ok].sort(key=lambda r: abs(r["swing"]), reverse=True)

    return rows
