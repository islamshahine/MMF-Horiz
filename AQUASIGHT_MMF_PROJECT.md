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
- **Design comparison** (⚖️ Compare tab): sidebar design vs editable alternative, second `compute_all`, 13-metric diff table, CSV export
- Technical report generation (Word .docx + optional PDF)

**Target users:** Process engineers and filter designers at water treatment / desalination companies.

**Stack:** Python 3.11 · Streamlit · pandas · plotly · python-docx · (optional) reportlab · (optional) FastAPI + uvicorn (`api/` — POST `/compute`)

---

## Architecture (Post-Refactor)

The app was refactored from a 3,059-line monolithic `app.py` into a clean modular structure. `app.py` is now a short thin orchestrator (~190 lines, 8 main content tabs).

### Data flow

```
app.py
  │
  ├─ with ctx:  render_sidebar(...) → inputs: dict   ← display units in, SI out
  │               └─ convert_inputs(out, unit_system) converts widget values to SI
  │
  ├─ compute_all(inputs) → computed: dict             ← always receives SI
  │
  ├─ with ctx:  status badges (uses inputs + computed)
  │
  └─ with main:
        render_tab_*(inputs, computed)               ← fmt()/ulbl()/dv() at display boundary
        (includes ⚖️ Compare: compute_all on session copy of Design B inputs)
```

**Unit system rule:** engine always works in SI. Conversion happens only at the UI boundary:
- Input widgets → `si_value()` / `convert_inputs()` before engine
- Computed SI results → `fmt()` / `dv()` / `ulbl()` before displaying

### Layout

```
st.columns([1, 4])
  ctx (left 1/5)          main (right 4/5)
  ┌──────────────┐        ┌──────────────────────────────────────┐
  │ Sidebar tabs │        │ 8 content tabs                       │
  │ ⚙️ Process   │        │ 💧 Filtration | 🔄 Backwash | ⚙️ Mech│
  │ 🏗️ Vessel    │        │ 🧱 Media | 💰 Economics | 🎯 Assess  │
  │ 🧱 Media     │        │ 📄 Report | ⚖️ Compare               │
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
├── app.py                    # ~190 lines — thin orchestrator (8 `st.tabs` + status column)
│
├── api/                      # FastAPI compute layer (optional headless / integration)
│   ├── main.py               # app + /health
│   ├── routes.py             # POST /compute → compute_all (JSON-safe response)
│   └── models.py             # shared HTTP error payload models
│
├── engine/                   # Pure Python calculation modules (no Streamlit)
│   ├── compute.py            # compute_all(inputs) → computed dict (~810 lines)
│   ├── comparison.py         # Design A vs B: diff_value, compare_designs, COMPARISON_METRICS (~110 lines)
│   ├── compare.py            # Public facade: re-exports comparison + compare_numeric, compare_severity, generate_delta_summary
│   ├── units.py              # Unit catalogue: display_value/si_value/unit_label/
│   │                         #   format_value, convert_inputs, transpose_display_value;
│   │                         #   extended qty keys (e.g. pressure_kpa, energy_kwh_m3,
│   │                         #   cost_usd_per_m3/d, co2_intensity_kg_m3, co2_kg_per_kwh,
│   │                         #   linear_density_kg_m, velocity_m_s, flow_m3_min, …)
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
│   ├── economics.py          # CAPEX, OPEX, carbon footprint, LCOW; capital_recovery_factor();
│   │                         #   global_benchmark_comparison() returns SI numeric *bench_si* tuples
│   │                         #   (UI formats ranges via fmt_si_range — no hardcoded unit strings)
│   ├── drawing.py            # ISO 128 vessel elevation: hatching, centreline, title block
│   ├── media.py              # Media DB (14 types + aliases), get_layer_intelligence()
│   ├── project_io.py         # JSON save/load: inputs_to_json(), get_widget_state_map()
│   ├── project_db.py         # SQLite: init_db, save/load project, snapshots, scenarios (stdlib)
│   ├── optimisation.py       # constraint_check, evaluate_candidate, optimise_design (grid MVP)
│   ├── fouling.py            # SDI/MFI/TSS/LV → solids loading, run time, severity, BW interval (empirical)
│   ├── logger.py             # File logging: compute + validation + JSON/DB project events (configure for tests)
│   ├── sensitivity.py        # OAT tornado analysis: run_sensitivity() — 9 params × 4 outputs
│   └── pdf_report.py         # ReportLab PDF: build_pdf(inputs, computed, sections, unit_system)
│
├── ui/                       # Streamlit rendering modules
│   ├── sidebar.py            # render_sidebar(...) → inputs dict (all widgets keyed)
│   │                         #   Unit toggle (metric/imperial); after radio, _reconvert_session_units()
│   │                         #   transposes SESSION_WIDGET_QUANTITIES + media keys; convert_inputs() on return
│   ├── helpers.py            # fmt · ulbl · dv · show_alert · pressure_drop_layers_display_frames
│   │                         #   cycle_matrix_*_title · filtration_dp_curve_display_df · fmt_bar_mwc
│   │                         #   fmt_annual_flow_volume · fmt_si_range · geo/media/saddle/nozzle display helpers
│   ├── tab_filtration.py     # 💧 Filtration tab
│   ├── tab_backwash.py       # 🔄 Backwash tab
│   ├── tab_mechanical.py     # ⚙️ Mechanical tab (nozzle data_editor in display units; DN stays ISO mm)
│   ├── tab_media.py          # 🧱 Media tab + intelligence expander
│   ├── tab_economics.py      # 💰 Economics tab (benchmark column uses fmt_si_range + *bench_si*)
│   ├── tab_assessment.py     # 🎯 Assessment tab + n_filters LV sweep + OAT tornado chart
│   ├── tab_report.py         # 📄 Report tab + JSON save/load; PDF/Word use fmt; PDF passes unit_system
│   ├── tab_compare.py        # ⚖️ Compare tab — Design B vs sidebar A, compute_all×2, CSV export
│
└── tests/                    # pytest — ~285 collected; 283 passed, 2 skipped (includes test_comparison)
    ├── conftest.py           # Shared fixtures (standard_layers)
    ├── test_water.py         # Water property functions
    ├── test_process.py       # filter_loading(), filter_area()
    ├── test_mechanical.py    # ASME thickness, weight, saddle
    ├── test_backwash.py      # Ergun ΔP, bed expansion, Wen-Yu, BW hydraulics
    ├── test_economics.py     # CRF, CAPEX, OPEX, carbon
    ├── test_media.py         # Media catalogue, collector_max_height
    ├── test_units.py         # Unit conversion — extended catalogue & convert_inputs coverage
    ├── test_integration.py   # compute_all() end-to-end smoke (25 tests)
    └── test_comparison.py    # compare_designs, diff_value, metric definitions
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
| Filtration cycles | `filt_cycles`, `cycle_matrix`, `load_data`, `tss_col_keys`/`tss_vals`, `temp_col_keys`, `feasibility_matrix` |
| Cartridge | `cart_result`, `cart_optim` |
| Hydraulics & energy | `hyd_prof`, `energy` |
| Weight | `w_noz`, `w_total`, `vessel_areas`, `lining_result`, `wt_oper` |
| Economics | `econ_capex`, `econ_opex`, `econ_carbon`, `econ_bench` (includes `*_bench_si` tuples for UI ranges) |
| Assessment | `overall_risk`, `risk_color/border/icon`, `drivers`, `impacts`, `recommendations`, `n_criticals/warnings/advisories`, `all_lv_issues`, `all_ebct_issues`, `rob_rows` |
| Severity fns | `lv_severity_fn`, `ebct_severity_fn` (callables passed to tabs) |
| Input validation | `input_validation` (`valid`, `errors`, `warnings` from `engine/validators.py` — **SI magnitudes**, same `inputs` contract as the rest of the engine) · `compute_used_reference_fallback` (bool; when invalid, `compute_all` uses `REFERENCE_FALLBACK_INPUTS` so tabs still render) |

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
| LCOW | User **CRF** (`capital_recovery_factor(discount_rate, design_life_years)`) × CAPEX + annual OPEX, divided by annual throughput (see Economics tab — not a fixed 8 % shortcut) |
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
| 💰 Economics | CAPEX breakdown + pie chart · OPEX breakdown + pie chart · carbon footprint · global benchmark with **proper CRF** (i, n user-inputs) · benchmark bands formatted in **active unit system** |
| 🎯 Assessment | Overall risk banner · key drivers · operational impacts · violation tables · Design Robustness Index · **n_filters sweep (N-scenario LV)** (optimisation roadmap MVP) · **OAT Sensitivity tornado chart** (9 inputs × 4 outputs) |
| 📄 Report | **JSON project save/load** · section selector · **PDF download** (ReportLab) · Word .docx download · inline markdown preview |
| ⚖️ Compare | Design **A** (current sidebar) vs **B** (editable subset) · second `compute_all` · **13 key metrics** via `compare_designs` · 🟡 significant diff column · winner summary · **CSV export** |

---

## Known Constraints & Design Decisions

- **Horizontal vessel only** — geometry uses `segment_area()` and `dish_volume()` for a horizontal cylinder. Not applicable to vertical pressure filters.
- **Single lining thickness** — rubber/epoxy/ceramic lining is uniform; no zone-specific lining.
- **BW frequency is user-input** (`bw_cycles_day`), not auto-derived from the cycle model. The feasibility matrix shows whether the chosen frequency is achievable.
- **Cartridge filter is post-treatment** — sized for `cart_flow` (separate input from the MMF total flow).
- **Economics are order-of-magnitude** — vendor quotes not included; benchmarks are 2024 Middle East / Mediterranean basis.
- **No real-time database** — all media properties are hardcoded presets in `engine/media.py` with user-editable overrides via `st.session_state`.
- **No multi-page routing** — single-page Streamlit app; state is preserved in `st.session_state`.
- **Compare tab scope** — Design **B** exposes a fixed subset of inputs (process, key vessel geometry, nozzle plate height, selected BW fields); all other keys are copied from Design **A** at init/reset. Comparison uses `engine/comparison.py` only (no change to `compute_all` internals).
- **Input validation is SI-only** — `validate_inputs` runs on the same post-`convert_inputs` dict as `compute_all`. Error strings that quote lengths use **m (SI)**; the unit toggle only affects sidebar labels and tab formatting via `engine/units.py` helpers, not validation thresholds.

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
| 7 | **Metric / Imperial unit toggle** — radio at top of sidebar; engine always receives/returns SI; `fmt()`/`ulbl()`/`dv()` at display boundary; `convert_inputs()` + `_reconvert_session_units()` on unit change | `engine/units.py`, `ui/sidebar.py`, `ui/helpers.py`, all tab files |
| 8 | **Regression test suite** — pure pytest (no Streamlit); water, process, mechanical, backwash, economics, media, units, integration | `tests/` |
| 9 | **Output unit alignment (tables & reports)** — backwash/media/economics/mechanical/report/PDF; hydraulic `fmt_bar_mwc`; economics `fmt_si_range` + `co2_kg_per_kwh`; nozzle schedule & saddle catalogue display DFs; DN stays ISO mm in editor | `ui/*.py`, `engine/pdf_report.py`, `engine/economics.py`, `engine/units.py` |
| 10 | **n_filters design sweep (optimisation MVP)** — Assessment tab expander: band sweep with full `compute_all`; N-scenario LV vs velocity threshold | `ui/tab_assessment.py` |
| 11 | **Design comparison tab** — Design A vs B, `engine/comparison.py` + `compute_all` for B, session `compare_inputs_b`, CSV export | `engine/comparison.py`, `ui/tab_compare.py`, `app.py` |

## Remaining Enhancement Areas

High-level backlog (not yet implemented end-to-end unless noted):

| # | Area | Notes |
|---|------|--------|
| 1 | **Optimisation mode** | Auto-search minimum `n_filters` / `nominal_id` under LV & EBCT limits. *Started:* Assessment **n_filters sweep** (manual band, full `compute_all` per step; does not write sidebar). |
| 2 | **Multi-case comparison** | Named presets, JSON load, or 3+ trains side-by-side. *Partial:* **⚖️ Compare** = A (sidebar) vs B (session) + CSV. |
| 3 | **Vendor nozzle catalogue** | Replace / augment estimated nozzle schedule with vendor tables (e.g. Wavin, Aqseptence). |
| 4 | **Live BW scheduler** | Gantt-style 24 h availability + BW train allocation. |
| 5 | **Media cost database** | External / configurable media pricing. |
| 6 | **Fouling index model** | SDI/MFI (or similar) → auto `solid_loading` / risk hints. |
| 7 | **Collector hydraulics** | Lateral ΔP sizing (today: height / carryover check only). |
| 8 | **Air scour optimisation** | Auto air-scour rate for target bed expansion. |

### Detail (same backlog, narrative)

1. **Optimisation mode** — given constraints (LV < threshold, EBCT > threshold), find minimum n_filters or minimum nominal_id  
   - *MVP (started):* Assessment tab — **sweep `n_filters` (per stream)** over a user band; each point runs full `compute_all`; table shows **N-scenario LV** vs velocity threshold (does not auto-write sidebar).
2. **Multi-train / multi-case comparison** — extend beyond two saved cases (e.g. named presets, JSON load side-by-side); current **⚖️ Compare** covers A vs B in one session.
3. **Vendor nozzle catalogue** — replace estimated nozzle schedule with lookup from real vendor data (e.g., Wavin, Aqseptence)
4. **Live BW scheduler** — Gantt-style chart showing filter availability and BW train allocation over 24 h
5. **Media cost database** — pull current media prices from a configurable data source
6. **Fouling index model** — incorporate SDI/MFI feed water quality index to auto-adjust `solid_loading`
7. **Collector hydraulics** — detailed lateral collector ΔP sizing (currently only height check)
8. **Air scour optimisation** — auto-size air scour rate to achieve target bed expansion
