"""Design comparison for AQUASIGHT MMF: compare_designs, diff_value, COMPARISON_METRICS. Pure Python."""

# (label, key_path, sub_key, unit_quantity, decimals, higher_is_better, threshold_pct)
COMPARISON_METRICS = [
    ("Flow / filter (N)", "q_per_filter", None, "flow_m3h", 1, False, 5.0),
    ("Filtration rate LV (N)", "filt_cycles", ("N", "lv_m_h"), "velocity_m_h", 2, False, 5.0),
    ("Real hydraulic ID", "real_id", None, "length_m", 4, True, 1.0),
    ("Cylindrical length", "cyl_len", None, "length_m", 3, True, 2.0),
    ("ΔP clean (N)", "bw_dp", "dp_clean_bar", "pressure_bar", 5, False, 10.0),
    ("ΔP dirty (N)", "bw_dp", "dp_dirty_bar", "pressure_bar", 5, False, 10.0),
    ("BW pump flow", "bw_hyd", "q_bw_m3h", "flow_m3h", 1, False, 5.0),
    ("Max safe BW velocity", "bw_col", "max_safe_bw_m_h", "velocity_m_h", 1, True, 5.0),
    ("Bed expansion net %", "bw_exp", "total_expansion_pct", "dimensionless", 1, False, 10.0),
    ("Collector freeboard", "bw_col", "freeboard_m", "length_m", 3, True, 10.0),
    ("Total empty weight", "w_total", None, "mass_kg", 0, False, 5.0),
    ("CAPEX total", "econ_capex", "total_capex_usd", "cost_usd", 0, False, 5.0),
    ("OPEX annual", "econ_opex", "total_opex_usd_yr", "cost_usd", 0, False, 5.0),
]


def _get_value(computed: dict, key_path: str, sub_key):
    val = computed.get(key_path)
    if val is None:
        return None
    if sub_key is None:
        return val
    if isinstance(sub_key, tuple):
        cur = val
        for k in sub_key:
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(k)
            else:
                return None
        return cur
    if isinstance(val, dict):
        return val.get(sub_key)
    return None


def diff_value(
    val_a,
    val_b,
    threshold_pct: float = 5.0,
    higher_is_better: bool = False,
) -> dict:
    """Compare scalars; returns val_a/b, abs_diff, pct_diff, is_significant, direction, favours."""
    result = {
        "val_a": val_a, "val_b": val_b, "abs_diff": None, "pct_diff": None,
        "is_significant": False, "direction": "same", "favours": "equal",
    }
    if val_a is None or val_b is None:
        return result
    try:
        abs_diff = float(val_b) - float(val_a)
        result["abs_diff"] = abs_diff
        pct_diff = (abs_diff / abs(float(val_a)) * 100) if float(val_a) != 0 else 0.0
        result["pct_diff"] = pct_diff
        result["is_significant"] = abs(pct_diff) > threshold_pct
        if abs(pct_diff) <= threshold_pct:
            result["direction"] = "same"
            result["favours"] = "equal"
        elif abs_diff > 0:
            result["direction"] = "higher"
            result["favours"] = "B" if higher_is_better else "A"
        else:
            result["direction"] = "lower"
            result["favours"] = "A" if higher_is_better else "B"
    except (TypeError, ValueError):
        pass
    return result


def compare_designs(
    computed_a: dict,
    computed_b: dict,
    label_a: str = "Design A",
    label_b: str = "Design B",
) -> dict:
    """Compare two computed dicts across COMPARISON_METRICS."""
    rows, n_sig, n_fav_a, n_fav_b = [], 0, 0, 0
    for (label, key, sub, qty, dec, higher_better, thresh) in COMPARISON_METRICS:
        val_a = _get_value(computed_a, key, sub)
        val_b = _get_value(computed_b, key, sub)
        diff = diff_value(val_a, val_b, thresh, higher_better)
        rows.append({
            "label": label, "unit_quantity": qty, "decimals": dec,
            "higher_is_better": higher_better, "threshold_pct": thresh, **diff,
        })
        if diff["is_significant"]:
            n_sig += 1
        if diff["favours"] == "A":
            n_fav_a += 1
        elif diff["favours"] == "B":
            n_fav_b += 1
    if n_fav_a > n_fav_b:
        overall = "A"
    elif n_fav_b > n_fav_a:
        overall = "B"
    else:
        overall = "equal"
    summary = (
        f"{n_sig} significant differences found. "
        f"{label_a} favoured on {n_fav_a} metrics, {label_b} on {n_fav_b}."
    )
    return {
        "label_a": label_a, "label_b": label_b, "metrics": rows,
        "n_significant": n_sig, "n_favours_a": n_fav_a, "n_favours_b": n_fav_b,
        "overall_winner": overall, "summary": summary,
    }
