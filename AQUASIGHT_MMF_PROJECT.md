# AQUASIGHT™ MMF — Project Context Document

> **Purpose:** Share this file with Claude.ai chat to discuss enhancements, new features, or design decisions with full project context. For **equations, models, input/display philosophy, and enhancement brainstorming**, see **`AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md`**. For **unit-system gaps & contributor rules**, see **§ Unit system — architecture, gaps & best practices (2026)**. For **roadmap delivery vs backlog**, see **§ Platform status — accomplished vs remaining (2026)**, **§F Phase 4 roadmap**, and **§G What to do next (2026-05-17)** near the end.

---

## What Is This?

**AQUASIGHT™ MMF** is a professional Streamlit web application for designing and evaluating **Horizontal Multi-Media Filters (MMF)** used in seawater desalination pre-treatment (SWRO). It is a full engineering calculation platform — not a simple parameter checker — that covers:

- Hydraulic sizing (filtration velocity, EBCT, pressure drop)
- Vessel mechanical design (ASME VIII Div. 1 thickness, weights)
- Backwash system design (bed expansion, hydraulics, scheduling)
- Economics (CAPEX, OPEX, carbon footprint, LCOW benchmarking) — **intermittent BW** pump & blower duty from the BW step table for annual kWh; OPEX energy and operational CO₂ use **metered-style Σ kWh × tariff / grid** (not 24/7 rated pump power)
- **Lifecycle financials** — discounted cash flows, replacements (media / nozzles / lining), escalation, optional benefit stream for IRR, depreciation (straight-line / declining balance), NPV sensitivity **spider chart**; outputs in `computed["econ_financial"]` (+ legacy `econ_npv` simplified curve)
- Engineering assessment with severity scoring
- **Design comparison** (⚖️ Compare tab): Design A vs B + **design library** (save up to **20** cases, compare **2–12**, paginated metrics table)
- **Explainability** — metric registry with contributor breakdowns (Filtration / Backwash)
- **Design basis & traceability** (schema **1.1**) — assumption IDs, output traceability, Report JSON/PDF/Word
- **Lifecycle degradation curves** — advisory sawtooth condition for media, nozzles, collector (Economics tab)
- **Pressurized underdrain catalogue** — mushroom / wedge-wire screening; salinity-based strainer defaults (Media sidebar)
- Technical report generation (Word .docx + optional PDF) — includes optional **lifecycle financial** and **design basis** sections

**Target users:** Process engineers and filter designers at water treatment / desalination companies.

**Stack:** Python 3.11 · Streamlit · pandas · plotly · python-docx · (optional) reportlab · (optional) FastAPI + uvicorn (`api/` — POST `/compute`)

---

## Architecture (Post-Refactor)

The app was refactored from a 3,059-line monolithic `app.py` into a clean modular structure. `app.py` is now a short thin orchestrator (~195 lines, **9** main content tabs). **`ui/compute_cache.py`** wraps `compute_all` with `st.cache_data` so unchanged inputs do not re-run the full pipeline on every Streamlit rerun (return payload must stay pickleable).

### Data flow

```
app.py
  │
  ├─ consume_deferred_project_actions()          ← New / Load JSON before any widgets (project_toolbar)
  │
  ├─ with ctx:  render_sidebar(...) → inputs: dict   ← display units in, SI out
  │               ├─ merge_feed_hydraulics_into_out() (Pumps tab widgets → out)
  │               └─ convert_inputs(out, unit_system) on return
  │
  ├─ [collapsed inputs] reconcile_si_inputs_with_pump_widgets(mmf_last_inputs)
  │       ← Pumps & power edits still reach compute when sidebar hidden
  │
  ├─ compute_all_cached(inputs) → computed: dict      ← `ui/compute_cache.py`; deep-copy + LRU cache
  │
  ├─ build_design_basis / explainability / lifecycle_degradation  ← `app.py` post-process on full computed
  │
  ├─ with ctx:  status badges (uses inputs + computed)
  │
  └─ with main:
        render_project_toolbar(inputs)             ← Save / Save as / Load JSON (top strip)
        render_tab_*(inputs, computed)               ← fmt()/ulbl()/dv() at display boundary
        (⚖️ Compare: Design B in session as SI; second compute_all)
```

**Unit system rule:** engine always works in SI. Conversion happens only at the UI boundary:
- Input widgets → `si_value()` / `convert_inputs()` before engine
- Computed SI results → `fmt()` / `dv()` / `ulbl()` before displaying
- Project JSON → **SI in file**; `get_widget_state_map()` → display widgets when `unit_system == "imperial"`

### Layout

```
st.columns([1, 4])
  ctx (left 1/5)          main (right 4/5)
  ┌──────────────┐        ┌──────────────────────────────────────┐
  │ Sidebar tabs │        │ 9 content tabs                       │
  │ ⚙️ Process   │        │ 💧 Filtration | 🔄 Backwash | ⚙️ Mech│
  │ 🏗️ Vessel    │        │ 🧱 Media | ⚡ Pumps | 💰 Econ | …     │
  │ 🧱 Media     │        │ 🎯 Assess | 📄 Report | ⚖️ Compare    │
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
├── app.py                    # ~195 lines — thin orchestrator (9 `st.tabs` + status column); uses `compute_all_cached`
│
├── api/                      # FastAPI compute layer (optional headless / integration)
│   ├── main.py               # app + /health
│   ├── routes.py             # POST /compute → compute_all (JSON-safe response)
│   └── models.py             # shared HTTP error payload models
│
├── engine/                   # Pure Python calculation modules (no Streamlit)
│   ├── compute.py            # compute_all(inputs) → computed dict; wires BW duty split, timeline stats, metered OPEX/CO₂
│   ├── validators.py         # validate_inputs + REFERENCE_FALLBACK_INPUTS (SI contract)
│   ├── comparison.py         # Design A vs B: diff_value, compare_designs, COMPARISON_METRICS (~110 lines)
│   ├── compare.py            # Public facade: re-exports comparison + compare_numeric, compare_severity, generate_delta_summary
│   ├── units.py              # Unit catalogue: display_value/si_value/unit_label/
│   │                         #   format_value, convert_inputs, transpose_display_value;
│   │                         #   extended qty keys (e.g. pressure_kpa, energy_kwh_m3,
│   │                         #   cost_usd_per_m3/d, co2_intensity_kg_m3, co2_kg_per_kwh,
│   │                         #   linear_density_kg_m, velocity_m_s, flow_m3_min, …)
│   ├── water.py              # Water properties (density, viscosity vs T, S)
│   ├── geometry.py           # segment_area(), dish_volume() for horizontal vessel
│   ├── process.py            # filter_loading() — physical N+1 bank: design N = installed − standby; scenarios N, N−1, …
│   ├── mechanical.py         # ASME VIII thickness, weights, saddle (Zick method)
│   ├── backwash.py           # Bed expansion, Ergun ΔP, BW hydraulics, scheduling, filter_bw_timeline_24h,
│   │                         #   timeline_plant_operating_hours (N / N−1 / below N−1 duty buckets)
│   ├── collector_ext.py      # Collector height check, media carryover risk
│   ├── collector_hydraulics.py  # 1A 1D Darcy + orifice ladder; 1B lateral distribution solver
│   ├── collector_geometry.py    # Lateral reach, spacing, underdrain screening suggestions
│   ├── collector_intelligence.py  # 1C rules: freeboard, nozzle velocities, air header
│   ├── collector_optimisation.py  # Grid search on collector inputs (Backwash / sidebar)
│   ├── design_basis.py       # Assumptions catalog (ASM-*), traceability (TRC-*), schema 1.1
│   ├── design_basis_report.py  # PDF/Word formatters for design basis section
│   ├── explainability.py     # METRIC_REGISTRY — equation contributors for UI tooltips
│   ├── lifecycle_degradation.py  # Sawtooth media/nozzle/collector condition vs year (advisory)
│   ├── nozzle_plate_catalogue.py  # Pressurized MMF underdrain screening (9 products)
│   ├── strainer_materials.py # Salinity-driven SS/duplex/super duplex; polymer bodies
│   ├── nozzle_system.py      # Underdrain coherence advisory (catalogue + strainer + ρ)
│   ├── collector_nozzle_plate.py  # Brick/staggered nozzle layout, open area, plate weight
│   ├── compare_workspace.py  # Multi-case compare: library 20, selection 12, pagination
│   ├── bw_scheduler.py       # Multi-day BW stagger (stream-aware v2, peak windows)
│   ├── collector_staged_orifices.py  # Staged lateral orifice advisory
│   ├── collector_velocity_risk.py    # Erosion/plugging heuristics
│   ├── collector_envelope.py   # BW flow operating envelope sweeps
│   ├── uncertainty_cycle.py  # Cycle driver decomposition (P2)
│   ├── uncertainty.py        # Filtration cycle optimistic / expected / conservative bands
│   ├── coating.py            # Internal surface areas, lining/coating cost
│   ├── cartridge.py          # Cartridge filter design & optimisation
│   ├── nozzles.py            # Nozzle schedule, DN series, flange ratings
│   ├── energy.py             # Hydraulic profile; energy_summary; bw_equipment_hours_per_event()
│   │                         #   (split BW water-pump vs air-scour hours from bw_sequence steps)
│   ├── economics.py          # CAPEX, OPEX, carbon footprint, LCOW; capital_recovery_factor(); npv_lifecycle_cost_profile;
│   │                         #   opex_annual / carbon_footprint accept energy_kwh_yr_by_component (metered annual kWh)
│   │                         #   global_benchmark_comparison() returns SI numeric *bench_si* tuples
│   │                         #   (UI formats ranges via fmt_si_range — no hardcoded unit strings)
│   │                         #   re-exports financial_economics API (NPV, IRR, cash flow builders)
│   ├── financial_economics.py # Lifecycle cash flow, NPV/IRR/payback, depreciation, incremental economics, sensitivity scan
│   ├── drawing.py            # ISO 128 vessel elevation: hatching, centreline, title block
│   ├── media.py              # Media DB (14 types + aliases), get_layer_intelligence()
│   ├── project_io.py         # JSON save/load: inputs_to_json(), get_widget_state_map(),
│   │                         #   widget_display_scalar(), AB_RFQ_SESSION_TO_QUANTITY (SI in JSON)
│   ├── default_media_presets.py  # Single source for DEFAULT_MEDIA_PRESETS (sidebar + new project)
│   ├── pump_performance.py   # Feed/BW pump duty, curves, engineering notes → computed["pump_perf"]
│   ├── pump_datasheet_export.py  # RFQ / datasheet bundles (feed pump, air blower)
│   ├── project_db.py         # SQLite: projects / cases / revisions / snapshots / scenarios (stdlib)
│   ├── project_revisions.py  # report_hash, revision input diff (B3)
│   ├── optimisation.py       # constraint_check, evaluate_candidate, optimise_design (grid MVP)
│   ├── fouling.py            # SDI/MFI/TSS/LV → solids loading, run time, severity, BW interval (empirical)
│   ├── logger.py             # File logging: compute + validation + JSON/DB project events (configure for tests)
│   ├── sensitivity.py        # OAT tornado: run_sensitivity(); OUTPUT_DEFS descriptions; tornado_narrative()
│   └── pdf_report.py         # ReportLab PDF: build_pdf(inputs, computed, sections, unit_system); `financial` section
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
│   ├── compute_cache.py      # st.cache_data wrapper for compute_all (pickle-safe computed)
│   ├── tab_economics.py      # 💰 Economics tab — CAPEX/OPEX/carbon/benchmark; NPV curve; lifecycle financial + Plotly spider
│   ├── tab_assessment.py     # 🎯 Assessment tab + n_filters LV sweep + OAT tornado chart
│   ├── tab_report.py         # 📄 Report tab + JSON save/load; PDF/Word use fmt; PDF passes unit_system
│   ├── tab_compare.py        # ⚖️ Compare — A/B + library (20/12/pagination); incremental `econ_financial`
│   ├── nozzle_catalogue_ui.py  # Unified Media underdrain block (catalogue + strainer)
│   ├── fouling_workflow.py   # 5-step fouling guided workflow
│   ├── bw_distribution_panels.py  # Backwash distribution / collector panels
│   ├── tab_pump_costing.py   # ⚡ Pumps & power — hydraulics, pump selection, RFQ/datasheet export
│   ├── feed_pump_context_inputs.py  # merge_feed_hydraulics_into_out; reconcile_si_inputs_with_pump_widgets
│   ├── project_toolbar.py    # Top strip: New / Save / Save as / Load (deferred before sidebar)
│   ├── project_persistence.py # collect_ui_session_persist_dict() — pp_* / ab_* SI on save
│   ├── layout_enhancements.py # Quick jump, section guide, collapse input column, validation banners
│   └── scroll_markers.py     # Anchor scroll between sidebar tabs and main tabs
│
└── tests/                    # pytest — ~419 collected; ~417 passed, 2 skipped (typical local run)
    ├── conftest.py           # Shared fixtures (standard_layers, …)
    ├── test_water.py         # Water property functions
    ├── test_process.py       # filter_loading(), filter_area()
    ├── test_mechanical.py    # ASME thickness, weight, saddle
    ├── test_backwash.py      # Ergun ΔP, bed expansion, Wen-Yu, BW hydraulics
    ├── test_economics.py     # CRF, CAPEX, OPEX, carbon (incl. metered kWh path)
    ├── test_energy.py        # bw_equipment_hours_per_event from BW steps
    ├── test_sensitivity.py   # tornado_narrative helper
    ├── test_media.py         # Media catalogue, collector_max_height
    ├── test_units.py         # Unit conversion — extended catalogue & convert_inputs coverage
    ├── test_integration.py   # compute_all() end-to-end smoke
    ├── test_comparison.py    # compare_designs, diff_value, COMPARISON_METRICS
    ├── test_compare.py       # engine.compare facade + severity helpers
    ├── test_validation.py    # validators + compute_all validation hook
    ├── test_project_db.py    # SQLite project_db API
    ├── test_logging.py       # logger file output + compute/project hooks
    ├── test_fouling.py       # fouling correlations
    ├── test_api.py           # FastAPI /health, /compute (+ unit_system=imperial), OpenAPI
    ├── test_project_io.py    # JSON round-trip, imperial widget map, widget_display_scalar
    ├── test_input_reconcile.py  # Collapsed layout: pump widgets → SI before compute
    ├── test_pump_performance.py / test_pump_datasheet_export.py
    ├── test_financial_economics.py  # NPV, IRR, payback, depreciation, cash flow, incremental economics
    └── test_optimisation.py  # constraint_check, optimise_design grid MVP
```

---

## Key Contracts

### `inputs` dict — keys produced by `render_sidebar()`

| Category | Key examples |
|---|---|
| Project metadata | `project_name`, `doc_number`, `revision`, `client`, `engineer` |
| Process | `total_flow`, `streams`, `n_filters` (total **physical** / stream), `hydraulic_assist` (standby / stream), `redundancy` |
| Water quality | `feed_temp`, `feed_sal`, `bw_temp`, `bw_sal`, `tss_low/avg/high`, `temp_low/high` |
| Vessel geometry | `nominal_id`, `total_length`, `end_geometry`, `lining_mm` |
| Mechanical | `material_name`, `design_pressure`, `corrosion`, `shell_radio`, `head_radio`, `ov_shell`, `ov_head` |
| Nozzle plate | `nozzle_plate_h`, `np_bore_dia`, `np_density`, `np_beam_sp`, `np_override_t`, `np_slot_dp`, `nozzle_catalogue_id`, `strainer_mat`, `n_nozzle_rows` |
| Collector | `collector_h`, `freeboard_mm` |
| Media layers | `layers` — list of dicts with `{Type, Depth, d10, cu, epsilon0, rho_p_eff, psi, d60, is_porous, is_support, capture_pct}` |
| Backwash | `bw_velocity`, `air_scour_rate`, `bw_cycles_day`, `bw_s_*` (step durations), `bw_total_min` |
| Energy | `pump_eta`, `bw_pump_eta`, `motor_eta`, `elec_tariff`, `op_hours_yr` |
| Economics | `steel_cost_usd_kg`, `erection_usd_vessel`, `engineering_pct`, `contingency_pct`, `media_replace_years`, `design_life_years`, `discount_rate`, etc. |
| Financial lifecycle | `project_life_years`, `inflation_rate`, `escalation_energy_pct`, `escalation_maintenance_pct`, `tax_rate`, `depreciation_method`, `depreciation_years`, `salvage_value_pct`, `maintenance_pct_capex`, `replacement_interval_media` / `_nozzles` / `_lining`, `annual_benefit_usd` (optional IRR driver) |
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
| Hydraulics & energy | `hyd_prof`, `energy` (incl. `h_bw_pump_plant_day`, `h_blower_plant_day`, annual kWh split) |
| BW timeline | `bw_timeline` — filters[], peak_concurrent_bw, hours at N / N−1 / below N−1, optional N+1 margin split |
| Weight | `w_noz`, `w_total`, `vessel_areas`, `lining_result`, `wt_oper` |
| Economics | `econ_capex`, `econ_opex`, `econ_carbon`, `econ_bench` (includes `*_bench_si` tuples; `econ_opex` may include `energy_kwh_*_yr` when metered); `econ_npv` (simplified cost PV profile); **`econ_financial`** (NPV, IRR, payback, cashflow_table, depreciation_table, replacement_schedule, npv_sensitivity, CO₂–cost path, JSON-serialisable) |
| Assessment | `overall_risk`, `risk_color/border/icon`, `drivers`, `impacts`, `recommendations`, `n_criticals/warnings/advisories`, `all_lv_issues`, `all_ebct_issues`, `rob_rows` |
| Post-process (app.py) | **`design_basis`** (v1.1), **`explainability`**, **`lifecycle_degradation`** |
| Collector extras | `collector_staged_orifices`, `collector_velocity_risk`, `collector_bw_envelope`, `collector_nozzle_plate`, `underdrain_system_advisory` |
| Cycle uncertainty | `cycle_uncertainty`, `cycle_economics` |
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
| Carbon | Scope 2 (**grid × annual kWh** from `energy` breakdown when wired) + Scope 3 (steel + media + concrete) |

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
| 🔄 Backwash | Collector / carryover check · bed expansion · BW hydraulics · TSS mass balance · BW scheduling feasibility matrix (scenario × temperature × TSS) · BW system sizing (pumps, blower, tank) · **24 h duty Gantt** (Plotly) with plant-wide **N / N−1** hour buckets and dynamic readout |
| ⚙️ Mechanical | Vessel drawing (ISO 128 style) · ASME thickness · nozzle plate · nozzle schedule · saddle design (Zick) · weight summary · lining/coating |
| 🧱 Media | Geometric volumes · media properties · pressure drop all scenarios · media inventory · clogging analysis · **Media Engineering Intelligence** (arrangement validation + per-layer role/BW/bio cards) |
| ⚡ Pumps & power | Feed-path pressure budget · pump/BW/blower duty · performance curves · alignment with economics energy · RFQ / datasheet export (feed pump, air blower) · widgets merged into sidebar SI `inputs` |
| 💰 Economics | CAPEX / OPEX / carbon · BW pump/blower h/day · benchmark CRF · **NPV** expander · **Lifecycle financial** (§6) · **Lifecycle degradation** (§7) — sawtooth condition curves |
| 🎯 Assessment | Risk banner · drivers · robustness · n_filters sweep · OAT tornado · **design basis** sample (assumptions + traceability) |
| 📄 Report | JSON save/load · PDF/Word · **design basis** section (assumptions catalog + traceability table + JSON download) |
| ⚖️ Compare | **A vs B** (13 metrics, incremental NPV) · **library** save **20** / compare **2–12** · paginated table (**4**/page) · CSV |
| 🧱 Media | Underdrain catalogue reference table · **fouling workflow** (5 steps) · media intelligence |
| 🔄 Backwash | Collector hydraulics · BW scheduler v2 · staged orifices · velocity risk · envelope · distribution panels |
| 💧 Filtration | **Explainability** expander — how key numbers are built |

---

## Known Constraints & Design Decisions

- **Horizontal vessel only** — geometry uses `segment_area()` and `dish_volume()` for a horizontal cylinder. Not applicable to vertical pressure filters.
- **Single lining thickness** — rubber/epoxy/ceramic lining is uniform; no zone-specific lining.
- **BW frequency is user-input** (`bw_cycles_day`), not auto-derived from the cycle model. The feasibility matrix shows whether the chosen frequency is achievable.
- **Cartridge filter is post-treatment** — sized for `cart_flow` (separate input from the MMF total flow).
- **Economics are order-of-magnitude** — vendor quotes not included; benchmarks are 2024 Middle East / Mediterranean basis.
- **Project library (SQLite)** — `engine/project_db.py` persists projects, **cases**, and **revisions** (report hash per revision; legacy snapshots migrated); the **Project file** toolbar expander (`ui/project_library.py`) provides search, open/update/export/delete, case/revision tree with diff/export, and duplicate — same hydrate path as JSON upload (`ui/project_session.py`). Media properties remain hardcoded presets in `engine/media.py` with user-editable overrides via `st.session_state`.
- **No multi-page routing** — single-page Streamlit app; state is preserved in `st.session_state`.
- **Compare tab scope** — Design **B** exposes a fixed subset of inputs (process, key vessel geometry, nozzle plate height, selected BW fields); all other keys are copied from Design **A** at init/reset. **`compare_inputs_b` is kept in SI** (editable fields converted with `si_value` after widgets); do not run `convert_inputs` on the whole B dict. Comparison uses `engine/comparison.py` only (no change to `compute_all` internals).
- **Input validation (SI engine, display messages)** — `validate_inputs` runs on the post-`convert_inputs` dict; geometry errors use `format_value` with `inputs["unit_system"]` so imperial users see ft/gpm-style thresholds. The engine still computes in SI.
- **Pump hydraulics split across columns** — Feed-path ΔP and η live on **Pumps & power** (`np_slot`, `p_res`, …) but merge into the sidebar `out` dict each rerun; collapsed-input mode uses `reconcile_si_inputs_with_pump_widgets` on cached `mmf_last_inputs`.
- **Project load ordering** — `consume_deferred_project_actions()` must run **before** sidebar widgets so loaded values can set `st.session_state` without “cannot modify after widget instantiated” errors.

---

## Unit system — architecture, gaps & best practices (2026)

### Architecture (single source of truth)

| Layer | Responsibility |
|--------|----------------|
| `engine/units.py` | `QUANTITIES`, `INPUT_QUANTITY_MAP`, `convert_inputs`, `display_value` / `si_value`, `SESSION_WIDGET_QUANTITIES`, `transpose_display_value` |
| `ui/helpers.py` | `fmt`, `ulbl`, `dv` — read `st.session_state.unit_system` |
| `ui/sidebar.py` | Widgets in **display** units; `_reconvert_session_units` on toggle; `convert_inputs` on return |
| `engine/project_io.py` | JSON stores **SI**; `get_widget_state_map` → display for imperial; `collect_ui_session_persist_dict` → SI for `ab_*` RFQ keys |
| `api/routes.py` | `POST /compute?unit_system=imperial` runs `convert_inputs` then `compute_all` |
| Result tabs | Never call `convert_inputs` on `computed` — only `fmt` / `dv` |

**Round-trip invariant:** for every key in `INPUT_QUANTITY_MAP`,  
`si_value(display_value(x, qty, imperial), qty, imperial) ≈ x` (within float tolerance).

### Best practices (for contributors)

1. **New numeric input** — Add quantity to `QUANTITIES` if missing → map in `INPUT_QUANTITY_MAP` → sidebar widget uses `display_value` / `si_value` / `unit_label` → never pass display values into `compute_all`.
2. **New Streamlit widget key** — If it differs from the `inputs` dict key, add to `WIDGET_KEY_MAP` in `project_io.py` so save/load works; ensure `SESSION_WIDGET_QUANTITIES` includes the widget key (via map or `_build_session_widget_quantities`).
3. **Dynamic layer keys** (`ld_0`, `d10_0`, `lv_thr_0`, …) — Toggle uses prefix rules in `_reconvert_session_units`; load uses `_LAYER_WIDGET_PREFIX_QTY` in `project_io.py`; layer dict in `inputs["layers"]` stays **SI** after `convert_inputs` (Depth in m, `lv_threshold_m_h` in m/h).
4. **Session-only UI** (`pp_*`, `ab_*`) — Persist under `_ui_session` in JSON; always **SI on disk**; imperial display only in `st.session_state`.
5. **Tables & charts** — Format with `fmt(si, quantity)` or build display frames via helpers; do not embed `"m/h"` / `"bar"` literals unless intentional (e.g. DN mm, µm rating).
6. **Compare / what-if copies** — Store **SI** in session copies; convert only the keys the user edits, or use `dv()` for widget `value=` only.
7. **Tests** — Add cases in `test_units.py` for new `INPUT_QUANTITY_MAP` keys; imperial API parity in `test_api.py`; project load in `test_project_io.py`.

### Intentionally not converted

| Item | Reason |
|------|--------|
| USD, USD/kWh, USD/vessel, % | Currency / finance, not physical units |
| kWh, MWh/yr (billing labels) | Energy billing; engine uses SI internally where mapped |
| DN / ISO pipe tables | Industry convention — integer **mm** in nozzle editor |
| Cartridge rating (µm) | Filtration standard |
| Media type $/t in sidebar | Often quoted per tonne; not yet in `QUANTITIES` (see gaps) |
| Dimensionless (CU, ψ, ε, capture %) | No quantity key |

### Potential gaps (known / residual)

| Gap | Risk | Mitigation direction |
|-----|------|----------------------|
| **Validator messages** | ~~Errors cite SI while UI is imperial~~ | **Done (2026):** `validate_inputs(..., unit_system=)` formats geometry errors via `format_value` |
| **Layer thresholds on project load** | `lv_thr_{i}` / custom `d10_{i}` only partially restored from `layers[]` in `get_widget_state_map` | Extend widget map for all custom-layer session keys; round-trip test per layer type |
| **Compare + unit toggle** | ~~Compare B widgets stale on toggle~~ | **Done (2026):** `ui/compare_units.reconvert_compare_b_widgets` on sidebar toggle; reset seeds widgets from SI |
| **Economics media $/t** | Sidebar labels may show `/t` while steel uses `cost_usd_per_kg` | Add `cost_usd_per_t` quantity or document as manual conversion |
| **`np_density` label** | May show `/m²` while quantity is `quantity_per_m2` | Align label with `unit_label('quantity_per_m2')` |
| **PDF/Word vs live UI** | Report generation must receive `unit_system` explicitly | Already on PDF path; audit Word builder for any remaining literals |
| **Full-tab audit drift** | New tabs (Pumps) add widgets outside sidebar map | Extend `PERSISTED_STREAMLIT_KEYS` / `INPUT_QUANTITY_MAP` when promoting fields to saved inputs |
| **SQLite vs JSON** | `project_db` may not replay `_ui_session` + imperial hydrate identically to file load | Single hydrate function used by both paths |

### Recent hardening (2026)

- Imperial **project load**: `get_widget_state_map` → `_apply_imperial_widget_display` for all `SESSION_WIDGET_QUANTITIES` + layer prefixes (not only `ab_*`).
- **Compare tab**: `compare_inputs_b` normalized to SI after widgets (avoids double-converting untouched A fields).
- **Project toolbar**: `_apply_loaded_project_to_session`, fixed **New project** seeding, Save-as filename.
- **Collapsed layout**: `reconcile_si_inputs_with_pump_widgets` + imperial pump test in `test_input_reconcile.py`.

---

## Platform status — accomplished vs remaining (2026)

Single place to see **what is done in repo + tests**, what is **engine-only** (no Streamlit UI yet), and what is **still open**.

### Test & quality baseline

| Item | Typical local result |
|------|----------------------|
| pytest | **~419** collected → **~417 passed**, **2 skipped**, **0 failed** |
| `engine/` coverage (`pytest --cov=engine --cov-report=term-missing`) | **~78%** lines — strong on `compute.py`, `economics.py`, `units.py`; modules not hit in that run show **0%** (e.g. `drawing.py`, `pdf_report.py`, `sensitivity.py` when only `engine/` is measured); thinner coverage on `coating.py`, `media.py`, `project_io.py` (widget map branches), `validators.py` |
| Headless API | `uvicorn api.main:app` — `GET /health`, `POST /compute` (SI `inputs` JSON), Open **`/docs`** |
| Baseline milestone | Empty commit **`perf(infrastructure): regression verified platform baseline`** marks a verified test pass on `main` |
| May 2026 sprint release | **`ad49e3d`** on `main` — triangular nozzles (`layout_revision` 6), BW duty timeline cache, Tier B/C lite modules, Egypt/Middle East media regions, `.github/workflows/ci.yml` |

---

### A. Original v2 product (Streamlit + engine)

Core modular app after the monolith split — unchanged intent, see **quick index** table at the end of this section for file pointers.

---

### B. Roadmap / platform hardening — **delivered** (code + tests)

| Capability | Implementation | Tests |
|------------|----------------|-------|
| **Input validation** | `engine/validators.py` — primitives + `validate_layers` + `validate_inputs` → `{valid, errors, warnings}`. `compute_all` integrates hook; invalid inputs → `REFERENCE_FALLBACK_INPUTS` + flags on `computed`. `app.py` surfaces `st.error` / `st.warning` / caption (SI). | `tests/test_validation.py` |
| **SI contract (validation UX)** | `validate_inputs(..., unit_system=)` — geometry errors use `format_value` when imperial; Compare B widgets transpose on toggle (`ui/compare_units.py`). | `tests/test_validation.py`, `tests/test_compare_units.py` |
| **Collector 1A / 1B (1D)** | `collector_hydraulics.py` — header/lateral Darcy + orifice ladder + iterative lateral distribution; optional auto maldistribution; Backwash UI + schematics + optimisation. **Not** CFD / full 3D manifold. | `tests/test_collector_hydraulics.py`, `tests/test_distribution_convergence.py`, `tests/test_collector_geometry.py` |
| **Collector 1C (rules)** | `collector_intelligence.py` — advisories on freeboard, nozzle velocities, air header. | (Backwash expander + manual) |
| **Design basis export (v1.1)** | `design_basis.py` — ASM/TRC IDs; built post-compute in `app.py`; Report + Assessment UI. | `tests/test_design_basis.py` |
| **Explainability registry** | `explainability.py` + `render_metric_explain_panel` on Filtration/Backwash. | `tests/test_explainability.py` |
| **Lifecycle degradation** | `lifecycle_degradation.py` — Economics §7 sawtooth curves. | `tests/test_lifecycle_degradation.py` |
| **Underdrain catalogue** | Pressurized-only 9 products; `strainer_materials`, `nozzle_system`, Media sidebar. | `tests/test_nozzle_plate_catalogue.py`, `test_nozzle_system.py`, `test_strainer_materials.py` |
| **Nozzle plate layout** | `collector_nozzle_plate.py` + `nozzle_plate_distribution.py` — triangular stagger, density-driven **N**, open area. | `tests/test_collector_nozzle_plate.py`, `tests/test_nozzle_distribution.py` |
| **BW scheduler v2** | Stream-aware `optimize_bw_phases`, peak windows. | `tests/test_bw_scheduler.py` |
| **Fouling workflow** | `ui/fouling_workflow.py` + `build_fouling_assessment`. | `tests/test_fouling_workflow.py`, `test_fouling.py` |
| **Multi-case compare scale** | Library 20, selection 12, `slice_compare_result`. | `tests/test_compare_workspace.py` |
| **Cycle uncertainty (2A)** | `uncertainty.py` → `computed["cycle_uncertainty"]`; Filtration band chart. | `tests/test_uncertainty.py` |
| **Uncertainty → economics** | `uncertainty_economics.py` → `computed["cycle_economics"]` LCOW optimistic/expected/conservative; Economics expander. | `tests/test_uncertainty_economics.py` |
| **Fouling guided workflow** | `ui/fouling_workflow.py` + `engine/fouling.py`. | `tests/test_fouling.py` |
| **Optimisation UX** | `ui/design_optim_ui.py` — sweep + `optimise_design` rank/apply; Pareto CAPEX vs OPEX expander. | `tests/test_optimisation.py`, `tests/test_design_optim_apply.py`, `tests/test_optimisation_pareto.py` |
| **Project library UI** | `ui/project_library.py` + deferred hydrate; SQLite `project_db`. | `tests/test_project_db.py`, `tests/test_project_session.py` |
| **Compare public API** | `engine/compare.py` — re-exports `comparison`; `compare_numeric` (= `diff_value`); `compare_severity`; `generate_delta_summary`. | `tests/test_compare.py`, `tests/test_comparison.py` |
| **SQLite persistence** | `engine/project_db.py` — `aquasight.db`; `projects` / `snapshots` / `scenarios`; JSON compatible with `project_io`; logging hooks on save/load. | `tests/test_project_db.py` |
| **Structured logging** | `engine/logger.py` — `logs/aquasight.log`, `configure()` for tests; `compute_all` timing + failures; `project_io` JSON events; `project_db` events. | `tests/test_logging.py` |
| **Fouling (empirical)** | `engine/fouling.py` — SDI / MFI index / TSS / LV → solids loading, severity, run time, BW interval; documented assumptions + warnings. | `tests/test_fouling.py` |
| **FastAPI** | `api/` — `POST /compute` → `compute_all`, optional `unit_system=imperial` (`convert_inputs`); JSON-safe payload; **`econ_financial`**. | `tests/test_api.py` |
| **Unit / project I/O hardening** | Imperial widget hydrate on load; Compare B SI contract; pump reconcile when inputs collapsed; top **project toolbar** (New/Save/Load). | `test_units.py`, `test_project_io.py`, `test_input_reconcile.py` |
| **Pumps & power tab** | `tab_pump_costing.py`, `pump_performance.py`, datasheet export; hydraulics merge + reconcile. | `test_pump_performance.py`, `test_pump_datasheet_export.py` |
| **Lifecycle financial engine** | `engine/financial_economics.py` — cash flows, NPV/IRR/payback, depreciation, incremental economics, NPV driver scan; `build_econ_financial` from `compute_all`. | `tests/test_financial_economics.py` |
| **Streamlit compute cache** | `ui/compute_cache.py` — `st.cache_data` on `compute_all` for snappier reruns. | (integration + manual) |
| **Optimisation (grid MVP)** | `engine/optimisation.py` — `constraint_check`, `evaluate_candidate`, `optimise_design` (merge patches, rank by `capex` / `opex` / `steel` / `carbon`); **`pareto_capex_opex`** (non-dominated feasible subset on CAPEX vs annual OPEX). Uses **`compute_all` only**. Default EBCT rule: **min layer EBCT ≥ 0.8 × `ebct_threshold`** (documented soft band); optional **`max_dp_dirty_bar`**, steel cap, etc. | `tests/test_optimisation.py`, `tests/test_optimisation_pareto.py` |
| **Media fill budget (indicative)** | `engine/media_pricing.py` — plant-wide media inventory USD from layer volumes + economics keys + region factor (**Egypt**, **Middle East**, GCC, …); Media tab expander. | `tests/test_media_pricing.py` |
| **Triangular nozzle-plate layout** | `engine/nozzle_plate_distribution.py` — `N = round(ρ × A_plate)` from sidebar hole density; triangular stagger; `layout_revision` 6; feeds spatial map + schematic. | `tests/test_nozzle_distribution.py`, `tests/test_collector_nozzle_plate.py` |
| **BW duty-chart cache (UX)** | `ui/bw_timeline_cache.py` — duty-only rerun, timeline merge, stagger compare; requires prior **Apply** for `mmf_last_computed`. | `tests/test_bw_stagger_compare.py`, `tests/test_bw_scheduler.py` |

**requirements.txt** (API): `fastapi`, `uvicorn[standard]`, `httpx`. **`.gitignore`:** `aquasight.db`, `logs/`, `__pycache__/`, `.pytest_cache/`, `.coverage`, `htmlcov/` (bytecode and coverage not tracked in git).

---

### C. **Prioritized backlog** (2026-05)

| Priority | Item | Rationale | Status |
|----------|------|-----------|--------|
| **1** | **Collector hand-calc benchmark pack** | Anchors trust in 1A/1B before new physics; fast regression | **Done** — `engine/collector_benchmarks.py`, Backwash expander, `tests/test_collector_benchmarks.py` |
| **2** | **Multi-case compare scale-up** | Consultant optioneering at scale | **Done** — library **20**, run **12**, pagination |
| **3** | **BW scheduler v2** | Ops scheduling | **Done (MVP)** — stream-aware + peak windows in `bw_scheduler.py` |
| **4** | **Pressurized underdrain catalogue** | Media setup | **Done** — 9 products; gravity/collector rows removed |
| **5** | **Explainability + design basis v1.1** | Enterprise review | **Done** — post-compute bundles in `app.py` |
| **6** | **Lifecycle degradation curves** | O&M narrative | **Done (advisory)** — `lifecycle_degradation.py` |

### D. **Other polish / scale-up**

| Item | Done | Missing / next |
|------|------|----------------|
| **Collector 1B+** | Dual-end header screening, per-hole network table, CFD BC export (JSON/CSV; `normalize_cfd_export_format` tolerates legacy UI labels); **triangular nozzle plate** (density-driven, full plate) | In-app CFD solve, 3D tee FEA |
| **Global optimiser** | Grid ranker + Assessment apply; **Pareto CAPEX vs annual OPEX** (non-dominated feasible) in Assessment expander | MILP / gradient search; richer multi-objective UI |

---

### E. **Backlog** — open items (Phases 4+)

| # | Topic | Notes |
|---|--------|--------|
| 1 | **Phase 4 A2 — Operating envelope map** | **Done** — `operating_envelope.py`, Filtration heatmap, scenario slider |
| 2 | **Phase 4 A3 — Design-to-target inverse** | **Done** — `design_targets.py`, Assessment expander, Apply patches |
| 3 | **Phase 4 A4 — Spatial distribution** | **Done** — `spatial_distribution.py`, loading map, CFD CSV enrich |
| 4 | **MILP / gradient global optimiser** | Grid ranker + Pareto delivered; MILP/DCS **Tier C** |
| 5 | **Real blower maps (B1)** | **Done** — `engine/blower_maps.py`, §3.25, Pumps & power 4c |
| 6 | **BW scheduler v3 (B2)** | **Done** — `tariff_aware_v3` stagger + sidebar tariff/blackout inputs |
| 7 | **Project revision tree (B3)** | **Done** — cases/revisions, report hash, library diff (§3.26) |
| 8 | **Collector in-app CFD (C2)** | External BC export **done**; solve in-app deferred |
| 9 | **External media pricing API** | MVP: user USD/m³ + region factor only |
| 10 | **Monte Carlo lite (C1)** | **Done** — optional sidebar flag, `monte_carlo_cycle` (§3.28) |
| 11 | **Shaded uncertainty charts (B4)** | **Done** — `cycle_uncertainty_charts`, Filtration Plotly bands (§3.27) |
| 12 | **Optional CI** | **Done** — `.github/workflows/ci.yml` (`pytest -m "not slow"`) |

**Narrative (updated 2026-05-17)**  
Phases **0–4** and Tier **B** are **delivered** (envelope map, design-to-target, spatial distribution, blower maps, BW v3, revisions, uncertainty bands). Tier **C lite** is **delivered** (Monte Carlo, CFD CSV compare, tag CSV, digital twin, MILP lite). Sprint **`ad49e3d`** is on **`origin/main`**. **Next:** Phase **5 — UX & layout polish** — see **§G** and **`AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md` §12**. Backlog: C2 full in-app CFD, C3 OCR, C5 DCS, external media API.

---

### F. **Phase 4 roadmap — decision intelligence** (2026+)

> Detailed equations and scope: **`AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md` §3.22, §11 Phase 4**. Build order: **A2 → A3 → A4**.

| ID | Feature | Engine (planned) | `computed[]` | UI owner | Status |
|----|---------|------------------|--------------|----------|--------|
| **A2** | Operating envelope map (LV × EBCT, severity regions) | `operating_envelope.py` | `operating_envelope` | Filtration tab expander | **Done** |
| **A3** | Design-to-target inverse (ΔP, LCOW, Q_BW) | `design_targets.py` | `design_targets` | Assessment — Apply patches | **Done** |
| **A4** | Spatial hydraulic distribution (Voronoi loading) | `spatial_distribution.py` | `spatial_distribution` | Backwash nozzle panel | **Done** |

**Tier B:** ~~B1 blower maps~~ **done** · ~~B2 BW scheduler v3~~ **done** · ~~B3 project revision tree~~ **done** · ~~B4 shaded uncertainty charts~~ **done**. **Tier B complete.**

**Tier C:** ~~C1~~ ~~C2 lite~~ ~~C3 tag CSV~~ ~~C4 twin lite~~ ~~C5 MILP lite~~ **done** · C2 full in-app CFD · C3 P&ID OCR · C5 DCS/MES integration.

**Architecture rule (unchanged):** one `compute_all`; prefer post-compute hooks in `app.py`; register `ASM-*` / explainability for every new metric.

**Phase 4 status:** **Complete** (A2/A3/A4 + Tier B + C lite). Do not re-open A2–A4 unless fixing a regression.

---

### G. **What to do next (2026-05-17)**

> Full checklist with architecture rules: **`AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md` §12**.

#### G.1 This week

| # | Action | Status |
|---|--------|--------|
| 1 | **Git** — commit and push sprint (`engine/`, `ui/`, `tests/`, docs, CI) | **Done** — `ad49e3d` on `origin/main` (2026-05-17) |
| 2 | **Targeted pytest** — nozzle + media + spatial smoke | **Done** — 24 passed (`test_nozzle_distribution`, `test_collector_nozzle_plate`, `test_media_pricing`, `test_spatial_distribution`) |
| 3 | **Smoke UI** — `python -m streamlit run app.py` → **Apply** → Backwash → change stagger → **Update duty chart** (all main tabs visible) | **Verify on your machine** |
| 4 | **Density contract** — sidebar **Hole density (/m²)** is the only source for `N = round(ρ × A_plate)` | **Done** — `test_client_density_regression_pack` at ρ = 40/50/60 |

#### G.2 Short term (2–4 weeks)

| Priority | Work | Files / notes |
|----------|------|----------------|
| **P5.2** | Duty-chart speed | **Done (fast path)** — `_duty_fast` renders Backwash §5 timeline only; post-hooks already skipped on duty-only rerun |
| **P5.3** | Nozzle QA | **Done** — `test_client_density_regression_pack` at ρ = 40/50/60 /m² (axial ≥95%, triangular stagger) |
| **P5.4** | Filtration spatial map | **Done** — `computed["spatial_distribution_filtration"]`; Filtration tab expander; Backwash map unchanged |
| **Docs** | Keep §3 / §11 / §12 aligned after each PR | Both MD files + `tests/README.md` |

#### G.3 Medium-term backlog (non-blocking)

| Item | Status |
|------|--------|
| C2 full in-app CFD | Backlog — lite CSV compare done |
| C3 P&ID OCR | Aspirational — tag CSV lite done |
| C5 DCS / MES export | Backlog — `milp_lite` done |
| External media pricing API | Backlog — region factors only |
| Client vs engineer UI mode | Backlog |

#### G.4 Key files (May 2026 sprint)

| Area | Module |
|------|--------|
| Nozzle layout | `engine/nozzle_plate_distribution.py`, `engine/collector_nozzle_plate.py` |
| Spatial map | `engine/spatial_distribution.py`, `ui/spatial_loading_panel.py` (BW + Filtration) |
| BW duty UX | `ui/bw_timeline_cache.py`, `ui/sidebar.py`, `engine/bw_timeline_build.py` |
| Cache bust | `ui/compute_cache.py` (`_COMPUTE_CACHE_VERSION`) |
| Media regions | `engine/media_pricing.py` (`egypt`, `middle_east`) |

---

## Implemented Enhancements (v2) — quick index

Rows **1–11** match **Section A** (original v2). Rows **12–13** are recent hydraulic / energy refinements. For roadmap rows **validation → optimisation**, see **Section B** above.

| # | Feature | Files |
|---|---|---|
| 1 | **ISO 128 mechanical drawing** — hatching, centreline, dual dimension lines, 6 nozzle stubs, title block | `engine/drawing.py` |
| 2 | **JSON project save/load** — SI in file; widget map + `_ui_session` (pp_* / ab_*); deferred load via `project_toolbar`; imperial hydrate on load | `engine/project_io.py`, `ui/project_toolbar.py`, `ui/tab_report.py` |
| 3 | **OAT sensitivity / tornado chart** — 9×4, OUTPUT_DEFS descriptions, `tornado_narrative()`, Plotly | `engine/sensitivity.py`, `ui/tab_assessment.py` |
| 4 | **PDF report** — ReportLab Platypus, 8 selectable sections, download alongside Word | `engine/pdf_report.py`, `ui/tab_report.py` |
| 5 | **Media engineering intelligence** — 4 new media types, name aliases (MnO₂/Coarse sand/…), arrangement validation, per-layer role/BW/bio cards | `engine/media.py`, `ui/tab_media.py` |
| 6 | **Proper CRF-based LCOW** — `capital_recovery_factor(i, n)` replaces hardcoded 0.08; discount_rate wired end-to-end | `engine/economics.py`, `engine/compute.py`, `ui/tab_economics.py` |
| 7 | **Metric / Imperial unit toggle** — radio at top of sidebar; engine always receives/returns SI; `fmt()`/`ulbl()`/`dv()` at display boundary; `convert_inputs()` + `_reconvert_session_units()` on unit change | `engine/units.py`, `ui/sidebar.py`, `ui/helpers.py`, all tab files |
| 8 | **Regression test suite** — pure pytest (no Streamlit); water, process, mechanical, backwash, economics, media, units, integration | `tests/` |
| 9 | **Output unit alignment (tables & reports)** — backwash/media/economics/mechanical/report/PDF; hydraulic `fmt_bar_mwc`; economics `fmt_si_range` + `co2_kg_per_kwh`; nozzle schedule & saddle catalogue display DFs; DN stays ISO mm in editor | `ui/*.py`, `engine/pdf_report.py`, `engine/economics.py`, `engine/units.py` |
| 10 | **n_filters design sweep (optimisation MVP)** — Assessment tab expander: band sweep with full `compute_all`; **Physical / stream** vs **Design N** columns; N-scenario LV vs velocity threshold | `ui/tab_assessment.py` |
| 11 | **Design comparison tab** — Design A vs B, `engine/comparison.py` + `compute_all` for B, session `compare_inputs_b`, CSV export | `engine/comparison.py`, `ui/tab_compare.py`, `app.py` |
| 12 | **Physical N+1 bank** — `hydraulic_assist` spare/stream; design **N** = installed − spare; BW timeline & loading; sidebar **Calculated N** readout | `engine/process.py`, `engine/compute.py`, `engine/backwash.py`, `engine/validators.py`, `ui/sidebar.py`, `ui/tab_backwash.py`, `ui/tab_compare.py` |
| 13 | **BW duty → energy / OPEX / CO₂** — `bw_equipment_hours_per_event()` from BW steps; `energy_kwh_yr_by_component` in `opex_annual` / `carbon_footprint` | `engine/energy.py`, `engine/economics.py`, `engine/compute.py`, `ui/tab_economics.py` |
| 14 | **NPV cost curve + pickle-safe severity** — `npv_lifecycle_cost_profile`; module-level LV/EBCT classifiers for `st.cache_data` | `engine/economics.py`, `engine/compute.py`, `ui/tab_economics.py`, `ui/compute_cache.py` |
| 15 | **Lifecycle financial + spider** — `econ_financial`, sidebar financial inputs, Economics tab expander 6, Compare incremental, Word/PDF `financial` | `engine/financial_economics.py`, `engine/compute.py`, `ui/sidebar.py`, `ui/tab_economics.py`, `ui/tab_compare.py`, `ui/tab_report.py`, `engine/pdf_report.py`, `tests/test_financial_economics.py` |
| 16 | **Pumps & power + RFQ** — feed/BW hydraulics, pump performance package, datasheet export; merge into sidebar SI dict | `ui/tab_pump_costing.py`, `engine/pump_performance.py`, `engine/pump_datasheet_export.py`, `ui/feed_pump_context_inputs.py` |
| 17 | **Project toolbar + layout** — top strip Save/Load/New; quick jump; hide input column; `consume_deferred_project_actions` before widgets | `ui/project_toolbar.py`, `ui/layout_enhancements.py`, `app.py` |
| 18 | **Imperial load / compare SI contract** — full widget hydrate; Compare B stored in SI; collapsed pump reconcile | `engine/project_io.py`, `ui/tab_compare.py`, `tests/test_project_io.py`, `tests/test_input_reconcile.py` |
| 19 | **Collector 1A + 1B (1D)** — Darcy/orifice ladder, lateral distribution solver, auto maldistribution, Backwash hydraulics UI, schematics, collector optimisation, design-basis traceability | `engine/collector_hydraulics.py`, `collector_geometry.py`, `ui/tab_backwash.py`, `ui/collector_hyd_schematic.py`, `tests/test_collector_hydraulics.py`, `tests/test_distribution_convergence.py` |
| 20 | **Project library + unified hydrate** — SQLite panel (search, snapshots, export); deferred load before widgets | `ui/project_library.py`, `ui/project_session.py`, `engine/project_db.py` |
| 21 | **Design basis in reports** — assumptions, traceability, collector block in PDF/Word | `engine/design_basis.py`, `engine/design_basis_report.py`, `ui/tab_report.py` |
| 22 | **Imperial validation + Compare unit sync** — display-aligned validator messages; Compare B widgets on toggle | `engine/validators.py`, `ui/compare_units.py`, `tests/test_compare_units.py` |
| 23 | **Auto air scour + screening blower kW** — `air_scour_solve` enrichment; Backwash expander; Compare B air mode | `engine/compute.py`, `engine/backwash.py`, `ui/tab_backwash.py`, `ui/tab_compare.py`, `ui/sidebar.py` |
| 24 | **CFD export aliases** + early compare prototype — compare scale-up in row **29** (library **20**, run **12**) | `engine/collector_cfd_export.py`, `engine/compare_workspace.py` |
| 25 | **Explainability registry** — METRIC_REGISTRY, contributor panels, plain-value UI | `engine/explainability.py`, `ui/helpers.py`, `app.py`, `tests/test_explainability.py` |
| 26 | **Design basis v1.1** — ASM/TRC traceability; post-compute; Report/Assessment tables | `engine/design_basis.py`, `design_basis_report.py`, `app.py` |
| 27 | **Pressurized underdrain catalogue** — 9 products, strainer materials, unified Media sidebar; **triangular density-driven nozzle layout** (`layout_revision` 6) | `nozzle_plate_catalogue.py`, `nozzle_plate_distribution.py`, `strainer_materials.py`, `nozzle_catalogue_ui.py`, `collector_nozzle_plate.py` |
| 28 | **Lifecycle degradation (advisory)** — sawtooth media/nozzle/collector | `lifecycle_degradation.py`, `ui/tab_economics.py` |
| 29 | **Multi-case compare scale** — library 20, run 12, pagination | `compare_workspace.py`, `ui/tab_compare.py` |
| 30 | **BW scheduler v2** + **fouling 5-step workflow** | `bw_scheduler.py`, `ui/fouling_workflow.py`, `engine/fouling.py` |
