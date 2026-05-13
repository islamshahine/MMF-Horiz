"""engine/sensitivity.py — One-at-a-time (OAT) sensitivity analysis for tornado charts.

Exports:
  PARAM_DEFS    list[dict]   — default input parameters to perturb
  OUTPUT_DEFS   list[dict]   — output metrics tracked (each may include ``description`` for UI)
  run_sensitivity(inputs, param_defs=None) -> dict[output_key -> list[row_dict]]
  tornado_narrative(rows, output_label=...) -> str  — markdown summary after a chart

Each row_dict: {param, base, lo, hi, swing, lo_label, hi_label}.
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
    {
        "key": "lv",
        "label": "Peak LV (m/h)",
        "fn": _lv,
        "description": (
            "Filtration **loading velocity** at the rated **N** scenario: "
            "**flow per filter ÷ average filter plan area**. "
            "The chart ranks which inputs (when nudged low vs high, one at a time) "
            "move LV most from the base case — useful vs hydraulic / media envelopes."
        ),
    },
    {
        "key": "ebct",
        "label": "Min EBCT (min)",
        "fn": _ebct,
        "description": (
            "**Shortest empty-bed contact time** among non-support media layers at **N**, "
            "from settled depth ÷ LV (converted to minutes). "
            "The tornado shows what drives the **tightest** EBCT layer first — "
            "often the same inputs that push LV or bed depth."
        ),
    },
    {
        "key": "capex",
        "label": "Total CAPEX (M USD)",
        "fn": _capex,
        "description": (
            "**Total installed capital** (million USD) from the project economics stack. "
            "Bars show how much total CAPEX shifts when each input is perturbed alone — "
            "steel, flow, pressure, etc. — within the **± bands** defined for this tornado run."
        ),
    },
    {
        "key": "dp",
        "label": "Dirty media ΔP (bar)",
        "fn": _dp_dirty,
        "description": (
            "**Media pressure drop at dirty loading** (bar) for the **N** hydraulic case. "
            "Indicates head across the loaded bed for filtration pump / energy context. "
            "The tornado highlights inputs that most move dirty-bed ΔP in this model."
        ),
    },
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


def tornado_narrative(
    rows: list[dict],
    *,
    output_label: str,
    top_k: int = 3,
    rel_floor: float = 1e-4,
) -> str:
    """Build a markdown summary of one OAT tornado result (after ``run_sensitivity``).

    ``rows`` must be the list for a single output, already sorted by |swing| descending.
    Interprets red bars as (low perturbation − base) and green as (high perturbation − base).
    """
    if not rows:
        return ""
    base = float(rows[0]["base"])
    swings = [abs(float(r["swing"])) for r in rows]
    max_sw = max(swings) if swings else 0.0
    floor = max(1e-18, rel_floor * max_sw) if max_sw > 0 else 0.0
    thresh = max(floor, 1e-12)

    active = [r for r in rows if abs(float(r["swing"])) > thresh]
    negligible = [r for r in rows if abs(float(r["swing"])) <= thresh]

    δ = max(1e-12, 1e-9 * (abs(base) + 1.0))

    intro = (
        f"**Chart readout (this run):** Base-case **{output_label}** = **{base:.4g}**. "
        f"Each bar pair is deviation from that base when **one** input is set to its **low** "
        f"(red) or **high** (green) sensitivity band while all others stay at the base case."
    )
    if not active:
        return intro + "\n\nAll listed inputs show negligible swing on this output for the configured OAT bands."

    lines = [intro, "**Strongest drivers** (by |high−low| swing on the output):"]
    for i, r in enumerate(active[: max(0, int(top_k))], 1):
        lo_d = float(r["lo"]) - base
        hi_d = float(r["hi"]) - base
        if hi_d > δ and lo_d < -δ:
            sense = (
                "increasing the input (high band) tends to **raise** this output vs base, "
                "and the low band tends to **lower** it."
            )
        elif hi_d < -δ and lo_d > δ:
            sense = (
                "increasing the input (high band) tends to **lower** this output vs base, "
                "and the low band tends to **raise** it."
            )
        else:
            sense = "low vs high bands move the output **asymmetrically** vs base (check hover for exact values)."
        lines.append(
            f"- **{r['param']}** — low ({r['lo_label']}): **{lo_d:+.4g}**; "
            f"high ({r['hi_label']}): **{hi_d:+.4g}** vs base. *{sense}*"
        )

    if negligible:
        names = ", ".join(f"**{r['param']}**" for r in negligible)
        lines.append(f"**Near-zero effect** in these OAT bands: {names}.")

    return "\n\n".join(lines)
