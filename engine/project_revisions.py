"""Project revision helpers — report hash and input diffs (B3)."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from engine import project_io as _pio

# Top-level inputs keys compared in library diff (SI engine dict).
DIFF_INPUT_KEYS: Tuple[str, ...] = (
    "project_name",
    "doc_number",
    "revision",
    "total_flow",
    "streams",
    "n_filters",
    "hydraulic_assist",
    "nominal_id",
    "tss_avg",
    "temp_avg_c",
    "bw_velocity",
    "bw_cycles_day",
    "elec_tariff",
    "project_life_years",
    "pp_n_blowers",
    "bw_timeline_stagger",
)

# Key computed metrics for hash fingerprint (optional).
DIFF_COMPUTED_KEYS: Tuple[str, ...] = (
    "overall_risk",
    "nominal_id",
)


def revision_report_hash(
    inputs: dict,
    computed: Optional[dict] = None,
    *,
    length: int = 16,
) -> str:
    """
    Stable SHA-256 fingerprint of canonical project JSON + selected computed fields.
    """
    blob = _pio.inputs_to_json(inputs)
    if computed:
        slim = {
            k: computed[k]
            for k in sorted(computed.keys())
            if k in DIFF_COMPUTED_KEYS and k in computed
        }
        if slim:
            blob += "\n" + json.dumps(slim, sort_keys=True, default=str)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    n = max(8, min(64, int(length)))
    return digest[:n]


def diff_revision_inputs(
    inputs_a: dict,
    inputs_b: dict,
    *,
    keys: Optional[Tuple[str, ...]] = None,
) -> List[dict[str, Any]]:
    """Row-wise diff of selected input keys between two revisions."""
    use = keys or DIFF_INPUT_KEYS
    rows: List[dict[str, Any]] = []
    for k in use:
        va = inputs_a.get(k)
        vb = inputs_b.get(k)
        if va == vb:
            continue
        rows.append({
            "key": k,
            "value_a": va,
            "value_b": vb,
            "changed": True,
        })
    return rows


def diff_revision_summary(rows: List[dict[str, Any]]) -> str:
    n = len(rows)
    if n == 0:
        return "No differences in tracked input keys."
    return f"{n} input field(s) differ."
