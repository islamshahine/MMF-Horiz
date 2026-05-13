def filter_loading(
    total_flow,
    streams,
    n_filters,
    redundancy,
    hydraulic_assist: int = 0,
):
    """
    Flow per filter for redundancy scenarios N, N-1, …

    ``n_filters`` = **physical** filters installed per stream (includes any spares).

    ``hydraulic_assist`` (0–4) = **standby / spare** physical filters per stream that
    are **not** counted in the design **N** hydraulic split (classic **N+1** when
    ``hydraulic_assist=1``: one spare so design **N = n_filters − 1** paths carry flow).

    Active paths for scenario ``x`` (``x`` additional installed units offline)::

        active = n_filters - hydraulic_assist - x

    BW duty timelines use **physical** ``n_filters`` only (``streams × n_filters`` rows).
    """
    ha = max(0, int(hydraulic_assist))
    rows = []
    for x in range(redundancy + 1):
        active = n_filters - ha - x
        q_filter = (total_flow / streams) / active if active > 0 else 0
        rows.append((x, active, q_filter))
    return rows