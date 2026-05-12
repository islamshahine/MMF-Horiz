# AQUASIGHT™ MMF — Project Context Document

> **Purpose:** Share this file with Claude.ai chat to discuss enhancements, new features, or design decisions with full project context.

---

## What Is This?

**AQUASIGHT™ MMF** is a professional Streamlit web application for designing and evaluating **Horizontal Multi-Media Filters (MMF)** used in seawater desalination pre-treatment (SWRO). It is a full engineering calculation platform — not a simple parameter checker — that covers:

- Hydraulic sizing (filtration velocity, EBCT, pressure drop)
- Vessel mechanical design (ASME VIII Div. 1 thickness, weights)
- Backwash system design (bed expansion, hydraulics, scheduling)
- Economics (CAPEX, OPEX, carbon footprint, LCOW benchmarking)
- Engineering assessment with severity scoring
- Technical report generation (Word .docx download)

**Target users:** Process engineers and filter designers at water treatment / desalination companies.

**Stack:** Python 3.11 · Streamlit · pandas · plotly · python-docx

---

## Architecture (Post-Refactor)

The app was refactored from a 3,059-line monolithic `app.py` into a clean modular structure. `app.py` is now **182 lines** — a pure thin orchestrator.

### Data flow

```
app.py
  │
  ├─ with ctx:  render_sidebar(...) → inputs: dict
  │
  ├─ compute_all(inputs) → computed: dict
  │
  ├─ with ctx:  status badges (uses inputs + computed)
  │
  └─ with main:
        render_tab_filtration(inputs, computed)
        render_tab_backwash(inputs, computed)
        render_tab_mechanical(inputs, computed)
        render_tab_media(inputs, computed)
        render_tab_economics(inputs, computed)
        render_tab_assessment(inputs, computed)
        render_tab_report(inputs, computed)
```

### Layout

```
st.columns([1, 4])
  ctx (left 1/5)          main (right 4/5)
  ┌──────────────┐        ┌──────────────────────────────────────┐
  │ Sidebar tabs │        │ 7 content tabs                       │
  │ ⚙️ Process   │        │ 💧 Filtration | 🔄 Backwash | ⚙️ Mech│
  │ 🏗️ Vessel    │        │ 🧱 Media | 💰 Economics | 🎯 Assess  │
  │ 🧱 Media     │        │ 📄 Report                            │
  │ 🔄 BW        │        └──────────────────────────────────────┘
  │ 💰 Econ      │
  ├──────────────┤
  │ Status badges│
  │ 🟢 Project   │
  │ 🟢 Process   │
  │ ⚪ Geometry  │
  └──────────────┘
```

**Important:** The app does NOT use `st.sidebar`. It uses `st.columns([1, 4])` — the left column acts as the sidebar.

---

## File Structure

```
MMF-Horiz/
├── app.py                    # 182 lines — thin orchestrator
│
├── engine/                   # Pure Python calculation modules (no Streamlit)
│   ├── compute.py            # compute_all(inputs) → computed dict (816 lines)
│   ├── water.py              # Water properties (density, viscosity vs T, S)
│   ├── geometry.py           # segment_area(), dish_volume() for horizontal vessel
│   ├── process.py            # filter_loading() — flow per filter per scenario
│   ├── mechanical.py         # ASME VIII thickness, weights, saddle (Zick method)
│   ├── backwash.py           # Bed expansion, Ergun ΔP, BW hydraulics, scheduling
│   ├── collector_ext.py      # Collector height check, media carryover risk
│   ├── coating.py            # Internal surface areas, lining/coating cost
│   ├── cartridge.py          # Cartridge filter design & optimisation
│   ├── nozzles.py            # Nozzle schedule, DN series, flange ratings
│   ├── energy.py             # Hydraulic profile, pump/blower energy summary
│   ├── economics.py          # CAPEX, OPEX, carbon footprint, LCOW; capital_recovery_factor()
│   ├── drawing.py            # ISO 128 vessel elevation: hatching, centreline, title block
│   ├── media.py              # Media DB (14 types + aliases), get_layer_intelligence()
│   ├── project_io.py         # JSON save/load: inputs_to_json(), get_widget_state_map()
│   ├── sensitivity.py        # OAT tornado analysis: run_sensitivity() — 9 params × 4 outputs
│   └── pdf_report.py         # ReportLab PDF generation: build_pdf() (requires reportlab)
│
└── ui/                       # Streamlit rendering modules
    ├── sidebar.py            # render_sidebar(...) → inputs dict (439 lines, all widgets keyed)
    ├── helpers.py            # show_alert() severity box
    ├── tab_filtration.py     # 💧 Filtration tab (226 lines)
    ├── tab_backwash.py       # 🔄 Backwash tab (225 lines)
    ├── tab_mechanical.py     # ⚙️ Mechanical tab (513 lines)
    ├── tab_media.py          # 🧱 Media tab (174 lines) + intelligence expander
    ├── tab_economics.py      # 💰 Economics tab (199 lines)
    ├── tab_assessment.py     # 🎯 Assessment tab (210 lines) + OAT tornado chart
    └── tab_report.py         # 📄 Report tab (693 lines) + JSON save/load + PDF download
```

---

## Key Contracts

### `inputs` dict — keys produced by `render_sidebar()`

| Category | Key examples |
|---|---|
| Project metadata | `project_name`, `doc_number`, `revision`, `client`, `engineer` |
| Process | `total_flow`, `streams`, `n_filters`, `redundancy` |
| Water quality | `feed_temp`, `feed_sal`, `bw_temp`, `bw_sal`, `tss_low/avg/high`, `temp_low/high` |
| Vessel geometry | `nominal_id`, `total_length`, `end_geometry`, `lining_mm` |
| Mechanical | `material_name`, `design_pressure`, `corrosion`, `shell_radio`, `head_radio`, `ov_shell`, `ov_head` |
| Nozzle plate | `nozzle_plate_h`, `np_bore_dia`, `np_density`, `np_beam_sp`, `np_override_t`, `np_slot_dp` |
| Collector | `collector_h`, `freeboard_mm` |
| Media layers | `layers` — list of dicts with `{Type, Depth, d10, cu, epsilon0, rho_p_eff, psi, d60, is_porous, is_support, capture_pct}` |
| Backwash | `bw_velocity`, `air_scour_rate`, `bw_cycles_day`, `bw_s_*` (step durations), `bw_total_min` |
| Energy | `pump_eta`, `bw_pump_eta`, `motor_eta`, `elec_tariff`, `op_hours_yr` |
| Economics | `steel_cost_usd_kg`, `erection_usd_vessel`, `engineering_pct`, `contingency_pct`, `media_replace_years`, etc. |
| Carbon | `grid_intensity`, `steel_carbon_kg`, `media_co2_gravel/sand/anthracite` |
| Design limits | `velocity_threshold`, `ebct_threshold`, `dp_trigger_bar`, `solid_loading` |

### `computed` dict — keys produced by `compute_all(inputs)`

| Category | Keys |
|---|---|
| Water | `feed_wp`, `bw_wp`, `rho_feed`, `mu_feed`, `rho_bw`, `mu_bw` |
| Geometry | `real_id`, `cyl_len`, `h_dish`, `nominal_id`, `total_length`, `end_geometry`, `lining_mm` |
| Mechanical | `mech` (thickness dict), `wt_body`, `mat_info` |
| Media | `geo_rows`, `base`, `avg_area`, `q_per_filter` |
| Pressure drop | `bw_dp` (Ergun + cake), `np_dp_auto` |
| Nozzle plate | `wt_np` (weight + n_bores + area) |
| Nozzles | `nozzle_sched` (list of nozzle rows) |
| Supports | `wt_sup`, `wt_int`, `wt_saddle` |
| Backwash | `bw_hyd`, `bw_col`, `bw_exp`, `bw_seq`, `bw_sizing`, `n_bw_systems` |
| TSS balance | `m_sol_low/avg/high`, `w_tss_low/avg/high`, `m_daily_low/avg/high` |
| Filtration cycles | `filt_cycles`, `cycle_matrix`, `load_data`, `tss_labels/vals`, `temp_labels`, `feasibility_matrix` |
| Cartridge | `cart_result`, `cart_optim` |
| Hydraulics & energy | `hyd_prof`, `energy` |
| Weight | `w_noz`, `w_total`, `vessel_areas`, `lining_result`, `wt_oper` |
| Economics | `econ_capex`, `econ_opex`, `econ_carbon`, `econ_bench` |
| Assessment | `overall_risk`, `risk_color/border/icon`, `drivers`, `impacts`, `recommendations`, `n_criticals/warnings/advisories`, `all_lv_issues`, `all_ebct_issues`, `rob_rows` |
| Severity fns | `lv_severity_fn`, `ebct_severity_fn` (callables passed to tabs) |

---

## Engineering Calculation Methods

| Domain | Method |
|---|---|
| Shell thickness | ASME VIII Div. 1 — UG-27 cylindrical shell + elliptical/torispherical heads |
| Pressure drop (clean) | Ergun equation (Kozeny–Carman for laminar, Burke–Plummer for turbulent) |
| Pressure drop (dirty) | Ruth cake filtration model: ΔP_cake = α × μ × LV × M |
| Bed expansion | Richardson–Zaki correlation (u/u_t = ε^n) + Wen-Yu for u_mf |
| Saddle design | Zick method (longitudinal bending + shear at saddle) |
| Water properties | UNESCO-EOS80 approximation for seawater density; viscosity vs T, S |
| Filtration cycle | DP-trigger based: solve t_cycle from α, TSS, LV, dp_trigger |
| BW feasibility | Availability = t_cycle/(t_cycle + t_BW); simultaneous BW demand → n_trains |
| LCOW | CRF = 8 % annualisation × CAPEX + OPEX / annual throughput |
| Carbon | Scope 2 (grid × energy) + Scope 3 (steel + media + concrete) |

---

## Assessment Severity Levels

Three-tier system applied to every scenario × layer combination:

| Level | LV trigger | EBCT trigger |
|---|---|---|
| Advisory | 0–5 % over threshold | 0–10 % under threshold |
| Warning | 5–15 % over | 10–25 % under |
| Critical | > 15 % over | > 25 % under |

**Overall rating** (STABLE / MARGINAL / ELEVATED / CRITICAL) derived from counts of criticals and warnings across all scenarios.

**Design Robustness Index** — evaluates every redundancy scenario (N, N-1, N-2, …) and labels each as Stable / Marginal / Sensitive / Critical.

---

## What Each Tab Shows

| Tab | Key content |
|---|---|
| 💧 Filtration | Water properties · flow distribution by scenario · LV and EBCT per layer per scenario · filtration cycle matrix (TSS × temperature) · cartridge filter design |
| 🔄 Backwash | Collector / carryover check · bed expansion · BW hydraulics · TSS mass balance · BW scheduling feasibility matrix (scenario × temperature × TSS) · BW system sizing (pumps, blower, tank) |
| ⚙️ Mechanical | Vessel drawing (ISO 128 style) · ASME thickness · nozzle plate · nozzle schedule · saddle design (Zick) · weight summary · lining/coating |
| 🧱 Media | Geometric volumes · media properties · pressure drop all scenarios · media inventory · clogging analysis · **Media Engineering Intelligence** (arrangement validation + per-layer role/BW/bio cards) |
| 💰 Economics | CAPEX breakdown + pie chart · OPEX breakdown + pie chart · carbon footprint · global benchmark with **proper CRF** (i, n user-inputs) |
| 🎯 Assessment | Overall risk banner · key drivers · operational impacts · violation tables · Design Robustness Index · **OAT Sensitivity tornado chart** (9 inputs × 4 outputs) |
| 📄 Report | **JSON project save/load** · section selector · **PDF download** (ReportLab) · Word .docx download · inline markdown preview |

---

## Known Constraints & Design Decisions

- **Horizontal vessel only** — geometry uses `segment_area()` and `dish_volume()` for a horizontal cylinder. Not applicable to vertical pressure filters.
- **Single lining thickness** — rubber/epoxy/ceramic lining is uniform; no zone-specific lining.
- **BW frequency is user-input** (`bw_cycles_day`), not auto-derived from the cycle model. The feasibility matrix shows whether the chosen frequency is achievable.
- **Cartridge filter is post-treatment** — sized for `cart_flow` (separate input from the MMF total flow).
- **Economics are order-of-magnitude** — vendor quotes not included; benchmarks are 2024 Middle East / Mediterranean basis.
- **No real-time database** — all media properties are hardcoded presets in `engine/media.py` with user-editable overrides via `st.session_state`.
- **No multi-page routing** — single-page Streamlit app; state is preserved in `st.session_state`.

---

## Implemented Enhancements (v2)

Added in the refactor session following the initial modular architecture:

| # | Feature | Files |
|---|---|---|
| 1 | **ISO 128 mechanical drawing** — hatching, centreline, dual dimension lines, 6 nozzle stubs, title block | `engine/drawing.py` |
| 2 | **JSON project save/load** — full session state mapping, 88-key widget map, rerun-on-load | `engine/project_io.py`, `ui/tab_report.py`, `ui/sidebar.py` |
| 3 | **OAT sensitivity / tornado chart** — 9 inputs × 4 outputs, cached in session_state, Plotly diverging bar | `engine/sensitivity.py`, `ui/tab_assessment.py` |
| 4 | **PDF report** — ReportLab Platypus, 8 selectable sections, download alongside Word | `engine/pdf_report.py`, `ui/tab_report.py` |
| 5 | **Media engineering intelligence** — 4 new media types, name aliases (MnO₂/Coarse sand/…), arrangement validation, per-layer role/BW/bio cards | `engine/media.py`, `ui/tab_media.py` |
| 6 | **Proper CRF-based LCOW** — `capital_recovery_factor(i, n)` replaces hardcoded 0.08; discount_rate wired end-to-end | `engine/economics.py`, `engine/compute.py`, `ui/tab_economics.py` |

## Remaining Enhancement Areas

1. **Optimisation mode** — given constraints (LV < threshold, EBCT > threshold), find minimum n_filters or minimum nominal_id
2. **Multi-train comparison** — side-by-side comparison of two design configurations
3. **Vendor nozzle catalogue** — replace estimated nozzle schedule with lookup from real vendor data (e.g., Wavin, Aqseptence)
4. **Live BW scheduler** — Gantt-style chart showing filter availability and BW train allocation over 24 h
5. **Media cost database** — pull current media prices from a configurable data source
6. **Unit toggle** — imperial / metric display toggle (currently metric-only)
7. **Fouling index model** — incorporate SDI/MFI feed water quality index to auto-adjust `solid_loading`
8. **Collector hydraulics** — detailed lateral collector ΔP sizing (currently only height check)
9. **Air scour optimisation** — auto-size air scour rate to achieve target bed expansion
