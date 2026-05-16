"""Multi-design comparison workspace (3+ cases) — pure Python."""
from __future__ import annotations

import copy
from typing import Any

from engine.comparison import COMPARISON_METRICS, _get_value

# Saved named cases in session library (full SI inputs per row).
MAX_LIBRARY_CASES = 20
# Cases computed and shown in one multi-case table run.
MAX_COMPARE_SELECTION = 12
# Columns per results page (wide tables paginate in the UI).
COMPARE_TABLE_PAGE_SIZE = 4

# Backward-compatible alias used by UI/tests.
MAX_COMPARE_CASES = MAX_COMPARE_SELECTION


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
    if len(cases) > MAX_COMPARE_SELECTION:
        raise ValueError(
            f"At most {MAX_COMPARE_SELECTION} cases per comparison run "
            f"(save up to {MAX_LIBRARY_CASES} in the library)."
        )

    labels = [str(lbl) for lbl, _ in cases]
    rows: list[dict[str, Any]] = []
    for label, key, sub, qty, dec, _hb, _thresh in COMPARISON_METRICS:
        row: dict[str, Any] = {
            "metric": label,
            "unit_quantity": qty,
            "decimals": dec,
        }
        vals: list[float] = []
        for _lbl, comp in cases:
            v = _get_value(comp, key, sub)
            row[_lbl] = v
            if v is not None:
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    pass
        if len(vals) >= 2:
            base = vals[0]
            row["spread_pct"] = (
                (max(vals) - min(vals)) / abs(base) * 100.0
                if base != 0
                else None
            )
        else:
            row["spread_pct"] = None
        rows.append(row)

    return {
        "labels": labels,
        "n_cases": len(cases),
        "metrics": rows,
        "page_size": COMPARE_TABLE_PAGE_SIZE,
        "n_pages": max(1, (len(labels) + COMPARE_TABLE_PAGE_SIZE - 1) // COMPARE_TABLE_PAGE_SIZE),
    }


def slice_compare_result(
    result: dict[str, Any],
    page: int,
    *,
    page_size: int = COMPARE_TABLE_PAGE_SIZE,
) -> dict[str, Any]:
    """Return one page of a multi-case result (subset of case columns)."""
    labels = list(result.get("labels") or [])
    if not labels:
        return {**result, "labels": [], "n_cases": 0, "metrics": [], "page": 0, "n_pages": 1}

    n_pages = max(1, (len(labels) + page_size - 1) // page_size)
    page = max(0, min(int(page), n_pages - 1))
    chunk = labels[page * page_size : (page + 1) * page_size]

    metrics_out: list[dict[str, Any]] = []
    for row in result.get("metrics") or []:
        new_row: dict[str, Any] = {
            "metric": row.get("metric"),
            "unit_quantity": row.get("unit_quantity"),
            "decimals": row.get("decimals"),
        }
        vals: list[float] = []
        for lbl in chunk:
            v = row.get(lbl)
            new_row[lbl] = v
            if v is not None:
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    pass
        if len(vals) >= 2:
            base = vals[0]
            new_row["spread_pct"] = (
                (max(vals) - min(vals)) / abs(base) * 100.0
                if base != 0
                else None
            )
        else:
            new_row["spread_pct"] = None
        metrics_out.append(new_row)

    return {
        "labels": chunk,
        "n_cases": len(chunk),
        "metrics": metrics_out,
        "page": page,
        "n_pages": n_pages,
        "all_labels": labels,
        "page_size": page_size,
    }
