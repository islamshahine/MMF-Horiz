# AQUASIGHT™ MMF — Project Context Document

> **Purpose:** Share this file with Claude.ai chat to discuss enhancements, new features, or design decisions with full project context. For a **dated snapshot of roadmap delivery vs backlog**, see **§ Platform status — accomplished vs remaining (2026)** near the end of this document.

---

## What Is This?

**AQUASIGHT™ MMF** is a professional Streamlit web application for designing and evaluating **Horizontal Multi-Media Filters (MMF)** used in seawater desalination pre-treatment (SWRO). It is a full engineering calculation platform — not a simple parameter checker — that covers:

- Hydraulic sizing (filtration velocity, EBCT, pressure drop)
- Vessel mechanical design (ASME VIII Div. 1 thickness, weights)
- Backwash system design (bed expansion, hydraulics, scheduling)
- Economics (CAPEX, OPEX, carbon footprint, LCOW benchmarking) — **intermittent BW** pump & blower duty from the BW step table for annual kWh; OPEX energy and operational CO₂ use **metered-style Σ kWh × tariff / grid** (not 24/7 rated pump power)
- **Lifecycle financials** — discounted cash flows, replacements (media / nozzles / lining), escalation, optional benefit stream for IRR, depreciation (straight-line / declining balance), NPV sensitivity **spider chart**; outputs in `computed["econ_financial"]` (+ legacy `econ_npv` simplified curve)
- Engineering assessment with severity scoring
- **Design comparison** (⚖️ Compare tab): sidebar design vs editable alternative, second `compute_all`, 13-metric diff table, CSV export
- Technical report generation (Word .docx + optional PDF) — includes optional **lifecycle financial** section (NPV / IRR summary, cash-flow excerpt, replacement table) and matching **PDF** section (`financial`)

**Target users:** Process engineers and filter designers at water treatment / desalination companies.

**Stack:** Python 3.11 · Streamlit · pandas · plotly · python-docx · (optional) reportlab · (optional) FastAPI + uvicorn (`api/` — POST `/compute`)

---

## Architecture (Post-Refactor)

The app was refactored from a 3,059-line monolithic `app.py` into a clean modular structure. `app.py` is now a short thin orchestrator (~205 lines, 8 main content tabs). **`ui/compute_cache.py`** wraps `compute_all` with `st.cache_data` so unchanged inputs do not re-run the full pipeline on every Streamlit rerun (return payload must stay pickleable).

### Data flow

```
app.py
  │
  ├─ with ctx:  render_sidebar(...) → inputs: dict   ← display units in, SI out
  │               └─ convert_inputs(out, unit_system) converts widget values to SI
  │
  ├─ compute_all_cached(inputs) → computed: dict      ← `ui/compute_cache.py`; deep-copy + LRU cache
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
├── app.py                    # ~205 lines — thin orchestrator (8 `st.tabs` + status column); uses `compute_all_cached`
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
│   ├── project_io.py         # JSON save/load: inputs_to_json(), get_widget_state_map()
│   ├── project_db.py         # SQLite: init_db, save/load project, snapshots, scenarios (stdlib)
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
│   ├── tab_compare.py        # ⚖️ Compare tab — Design B vs sidebar A, compute_all×2, CSV export; incremental `econ_financial`
│
└── tests/                    # pytest — ~382 collected; ~380 passed, 2 skipped (typical local run)
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
    ├── test_api.py           # FastAPI /health, /compute, OpenAPI
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
| Nozzle plate | `nozzle_plate_h`, `np_bore_dia`, `np_density`, `np_beam_sp`, `np_override_t`, `np_slot_dp` |
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
| 💰 Economics | CAPEX breakdown + pie chart · OPEX breakdown + pie chart · carbon footprint · **BW pump / blower h/day** (plant-wide, from step timing × cycles) · annual kWh split caption · global benchmark with **proper CRF** (i, n user-inputs) · benchmark bands in **active unit system** · **NPV** expander (levelised OPEX curve) · **Lifecycle financial** expander (cash-flow metrics, tables, cumulative / OPEX / CAPEX–OPEX charts, replacement timeline, **NPV sensitivity spider** (Plotly `Scatterpolar`), CO₂ vs cumulative cost) |
| 🎯 Assessment | Overall risk banner · key drivers · operational impacts · violation tables · Design Robustness Index · **n_filters sweep** — columns **Physical / stream** & **Design N** (standby fixed); **OAT tornado** (9×4) with metric **descriptions**, **tornado_narrative** under chart |
| 📄 Report | **JSON project save/load** · section selector · **PDF download** (ReportLab, incl. `financial`) · Word .docx download · optional **lifecycle financial** tables · inline markdown preview |
| ⚖️ Compare | Design **A** (current sidebar) vs **B** (editable subset) · second `compute_all` · **13 key metrics** via `compare_designs` · 🟡 significant diff column · winner summary · **CSV export** · **incremental lifecycle economics** (ΔCAPEX, ΔNPV, Δ year-1 operating cash) when both runs expose `econ_financial` |

---

## Known Constraints & Design Decisions

- **Horizontal vessel only** — geometry uses `segment_area()` and `dish_volume()` for a horizontal cylinder. Not applicable to vertical pressure filters.
- **Single lining thickness** — rubber/epoxy/ceramic lining is uniform; no zone-specific lining.
- **BW frequency is user-input** (`bw_cycles_day`), not auto-derived from the cycle model. The feasibility matrix shows whether the chosen frequency is achievable.
- **Cartridge filter is post-treatment** — sized for `cart_flow` (separate input from the MMF total flow).
- **Economics are order-of-magnitude** — vendor quotes not included; benchmarks are 2024 Middle East / Mediterranean basis.
- **No project library in the Streamlit UI** — `engine/project_db.py` implements optional **SQLite** persistence (`aquasight.db`, projects / snapshots / scenarios); the Report tab still exposes **JSON file** download/upload only. Media properties remain hardcoded presets in `engine/media.py` with user-editable overrides via `st.session_state`.
- **No multi-page routing** — single-page Streamlit app; state is preserved in `st.session_state`.
- **Compare tab scope** — Design **B** exposes a fixed subset of inputs (process, key vessel geometry, nozzle plate height, selected BW fields); all other keys are copied from Design **A** at init/reset. Comparison uses `engine/comparison.py` only (no change to `compute_all` internals).
- **Input validation is SI-only** — `validate_inputs` runs on the same post-`convert_inputs` dict as `compute_all`. Error strings that quote lengths use **m (SI)**; the unit toggle only affects sidebar labels and tab formatting via `engine/units.py` helpers, not validation thresholds.

---

## Platform status — accomplished vs remaining (2026)

Single place to see **what is done in repo + tests**, what is **engine-only** (no Streamlit UI yet), and what is **still open**.

### Test & quality baseline

| Item | Typical local result |
|------|----------------------|
| pytest | **~382** collected → **~380 passed**, **2 skipped**, **0 failed** |
| `engine/` coverage (`pytest --cov=engine --cov-report=term-missing`) | **~78%** lines — strong on `compute.py`, `economics.py`, `units.py`; modules not hit in that run show **0%** (e.g. `drawing.py`, `pdf_report.py`, `sensitivity.py` when only `engine/` is measured); thinner coverage on `coating.py`, `media.py`, `project_io.py` (widget map branches), `validators.py` |
| Headless API | `uvicorn api.main:app` — `GET /health`, `POST /compute` (SI `inputs` JSON), Open **`/docs`** |
| Baseline milestone | Empty commit **`perf(infrastructure): regression verified platform baseline`** marks a verified test pass on `main` |

---

### A. Original v2 product (Streamlit + engine)

Core modular app after the monolith split — unchanged intent, see **quick index** table at the end of this section for file pointers.

---

### B. Roadmap / platform hardening — **delivered** (code + tests)

| Capability | Implementation | Tests |
|------------|----------------|-------|
| **Input validation** | `engine/validators.py` — primitives + `validate_layers` + `validate_inputs` → `{valid, errors, warnings}`. `compute_all` integrates hook; invalid inputs → `REFERENCE_FALLBACK_INPUTS` + flags on `computed`. `app.py` surfaces `st.error` / `st.warning` / caption (SI). | `tests/test_validation.py` |
| **SI contract (validation UX)** | Validators + docs: length errors **m (SI)**; caption that checks are SI regardless of unit toggle. | (behavioural + docs) |
| **Compare public API** | `engine/compare.py` — re-exports `comparison`; `compare_numeric` (= `diff_value`); `compare_severity`; `generate_delta_summary`. | `tests/test_compare.py`, `tests/test_comparison.py` |
| **SQLite persistence** | `engine/project_db.py` — `aquasight.db`; `projects` / `snapshots` / `scenarios`; JSON compatible with `project_io`; logging hooks on save/load. | `tests/test_project_db.py` |
| **Structured logging** | `engine/logger.py` — `logs/aquasight.log`, `configure()` for tests; `compute_all` timing + failures; `project_io` JSON events; `project_db` events. | `tests/test_logging.py` |
| **Fouling (empirical)** | `engine/fouling.py` — SDI / MFI index / TSS / LV → solids loading, severity, run time, BW interval; documented assumptions + warnings. | `tests/test_fouling.py` |
| **FastAPI** | `api/` — `POST /compute` → `compute_all`, JSON-safe payload (drops non-serialisable tab callables); response includes **`econ_financial`**. | `tests/test_api.py` |
| **Lifecycle financial engine** | `engine/financial_economics.py` — cash flows, NPV/IRR/payback, depreciation, incremental economics, NPV driver scan; `build_econ_financial` from `compute_all`. | `tests/test_financial_economics.py` |
| **Streamlit compute cache** | `ui/compute_cache.py` — `st.cache_data` on `compute_all` for snappier reruns. | (integration + manual) |
| **Optimisation (grid MVP)** | `engine/optimisation.py` — `constraint_check`, `evaluate_candidate`, `optimise_design` (merge patches, rank by `capex` / `opex` / `steel` / `carbon`). Uses **`compute_all` only**. Default EBCT rule: **min layer EBCT ≥ 0.8 × `ebct_threshold`** (documented soft band); optional **`max_dp_dirty_bar`**, steel cap, etc. | `tests/test_optimisation.py` |

**requirements.txt** (API): `fastapi`, `uvicorn[standard]`, `httpx`. **`.gitignore`:** `aquasight.db`, `logs/`.

---

### C. **Partially done** — backend exists; **no Streamlit wiring**

| Item | Done | Missing |
|------|------|---------|
| **Project library** | `project_db.py` full API | Report tab UI: browse / load / save / snapshots in-app |
| **Fouling assistant** | `fouling.py` | Sidebar or Process tab: SDI/MFI inputs + “Apply suggested `solid_loading`” (or similar) |
| **Optimisation UX** | Assessment **n_filters sweep** + `optimise_design()` | Single UX that exposes patch grid / objectives, or “apply best to sidebar” (careful with session state) |

---

### D. **Backlog** — not implemented (or not productised)

| # | Topic | Notes |
|---|--------|--------|
| 1 | **Global / automatic optimiser** | No MILP or gradient search; only **manual sweep** (UI) + **grid ranker** (`optimise_design`). Auto-write best design to sidebar is future. |
| 2 | **Multi-case comparison** | Compare tab = **A vs B** + CSV; no 3+ cases, no named library. |
| 3 | **Vendor nozzle catalogue** | Still generic `engine/nozzles.py` estimates. |
| 4 | **Live BW scheduler** | **24 h schematic** Gantt + stagger exists; no multi-day optimiser / ops Gantt tied to plant DCS. |
| 5 | **External media pricing** | No price database or API feed. |
| 6 | **Collector lateral hydraulics** | Height / carryover only; no lateral ΔP network. |
| 7 | **Air scour auto-tune** | User sets `air_scour_rate`; no solver for target expansion. |
| 8 | **Test depth** | Add coverage for drawing/PDF generation paths, sensitivity engine-only tests, deeper `media`/`coating`/`validators` branches. |

**Narrative (same themes)**  
(1) Tighter optimisation + UI integration. (2) More than two saved cases. (3) Real vendor nozzle tables. (4) Extended BW / ops scheduling beyond 24 h schematic. (5) Configurable media costs. (6) Fouling UI wiring (engine ready). (7) Collector detail model. (8) Air scour solver.

---

## Implemented Enhancements (v2) — quick index

Rows **1–11** match **Section A** (original v2). Rows **12–13** are recent hydraulic / energy refinements. For roadmap rows **validation → optimisation**, see **Section B** above.

| # | Feature | Files |
|---|---|---|
| 1 | **ISO 128 mechanical drawing** — hatching, centreline, dual dimension lines, 6 nozzle stubs, title block | `engine/drawing.py` |
| 2 | **JSON project save/load** — full session state mapping, 88-key widget map, rerun-on-load | `engine/project_io.py`, `ui/tab_report.py`, `ui/sidebar.py` |
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
