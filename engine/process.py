def filter_loading(total_flow, streams, n_filters, redundancy):
    rows = []
    for x in range(redundancy + 1):
        active = n_filters - x
        q_filter = (total_flow / streams) / active if active > 0 else 0
        rows.append((x, active, q_filter))
    return rows