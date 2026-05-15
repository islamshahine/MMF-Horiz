"""Multi-design comparison workspace (3+ cases) — pure Python."""
from __future__ import annotations

import copy
from typing import Any

from engine.comparison import COMPARISON_METRICS, _get_value

MAX_COMPARE_CASES = 4


def snapshot_case_inputs(inputs: dict, *, label: str) -> dict[str, Any]:
    """Serializable case record for session / library storage."""
    return {
        "label": str(label).strip() or "Case",
        "inputs": copy.deepcopy(inputs),
    }


def compare_many_designs(
    cases: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """
    Build a metric × case table from multiple ``compute_all`` results.

    Parameters
    ----------
    cases : list of ``(label, computed)`` in display order.
    """
    if len(cases) < 2:
        raise ValueError("Provide at least two cases to compare.")
    if len(cases) > MAX_COMPARE_CASES:
        raise ValueError(f"At most {MAX_COMPARE_CASES} cases supported.")

    labels = [str(lbl) for lbl, _ in cases]
    rows: list[dict[str, Any]] = []
    for label, key, sub, qty, dec, _hb, _thresh in COMPARISON_METRICS:
        row: dict[str, Any] = {
            "metric": label,
            "unit_quantity": qty,
            "decimals": dec,
        }
        vals: list[float | None] = []
        for _lbl, comp in cases:
            v = _get_value(comp, key, sub)
            row[_lbl] = v
            if v is not None:
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    pass
        if len(vals) >= 2:
            row["spread_pct"] = (
                (max(vals) - min(vals)) / abs(vals[0]) * 100.0
                if vals[0] != 0
                else None
            )
        else:
            row["spread_pct"] = None
        rows.append(row)

    return {
        "labels": labels,
        "n_cases": len(cases),
        "metrics": rows,
    }
