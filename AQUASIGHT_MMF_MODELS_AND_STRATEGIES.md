# AQUASIGHT™ MMF — Models, Logic, Strategies & Enhancement Compass

> **Purpose:** A technical reference for *how the platform thinks* — equations, assumptions, input/display philosophy, and structured ideas for future enhancement. Share this file (with `AQUASIGHT_MMF_PROJECT.md`) when brainstorming with Claude, Cursor, or a process team.
>
> **Audience:** Process engineers, product owners, and AI assistants evaluating new features without re-reading the whole codebase.

---

## Table of contents

1. [Platform philosophy](#1-platform-philosophy)
2. [Calculation strategy & pipeline](#2-calculation-strategy--pipeline)
3. [Domain models & equations](#3-domain-models--equations)
4. [Assessment & decision logic](#4-assessment--decision-logic)
5. [Economics & financial models](#5-economics--financial-models)
6. [Input strategy](#6-input-strategy-how-we-collect-design-intent)
7. [Display & content strategy](#7-display--content-strategy-how-we-present-results)
8. [Enhancement compass](#8-enhancement-compass-for-outside-the-box-thinking)
9. [Epistemic limits & honesty](#9-epistemic-limits--honesty)
10. [Quick reference — correlations](#10-quick-reference--correlations)
11. [Development priorities — reconciled view](#11-development-priorities--reconciled-view-vs-external-roadmap) *(end of §11: **Shipped deltas (2026-05)**)*

**Also in §3:** multi-case compare (**§3.15**), CFD BC export (**§3.16**), collector schematic (**§3.17**), pressurized underdrain catalogue (**§3.18**), explainability registry (**§3.19**), lifecycle degradation curves (**§3.20**), design basis traceability v1.1 (**§3.21**), spatial hydraulic distribution — spec (**§3.22**), operating envelope map (**§3.23**), design-to-target search (**§3.24**).

## 1. Platform philosophy

### 1.1 Core idea

**AQUASIGHT MMF** is a *design-time engineering notebook* for horizontal multi-media filters in SWRO pre-treatment — not a real-time SCADA tool, not a CFD substitute, and not a vendor guarantee engine.

| Principle | Meaning |
|-----------|---------|
| **Single physics core** | One `compute_all(inputs)` path feeds Streamlit, PDF/Word, API, comparison, sensitivity, and optimisation grid. |
| **SI inside, units at the glass** | All engineering math uses SI; metric/imperial is a presentation and widget layer. |
| **Scenario-first hydraulics** | Plant duty is split across **N, N−1, …** redundancy paths, not a single “average filter.” |
| **Layer-resolved media** | Each bed layer has geometry, ΔP, LV, EBCT, capture share, and optional per-layer setpoints. |
| **Honest order-of-magnitude economics** | CAPEX/OPEX/LCOW/benchmarks support optioneering; they are not bid-ready BOQs. |
| **Explainability over black boxes** | Tables show Ergun terms, cake loading, expansion %, and severity drivers — users can challenge assumptions. |

### 1.2 What the platform is *for*

- Size filters and vessels for a given SWRO train flow and water quality band.
- Check whether backwash, expansion, collector freeboard, and BW scheduling are *feasible*.
- Compare mechanical weight, energy, cost, and risk between design variants.
- Produce client-facing reports (Word/PDF) from the same numbers as the UI.

### 1.3 What it is *not* (yet)

- Biofouling / SDI prediction from first principles (fouling module is empirical advisory; 5-step workflow is screening only).
- MILP / gradient global optimiser or DCS-linked scheduling (grid ranker + heuristic BW scheduler v2 only).
- In-app CFD solve, 3D manifold FEA, or nozzle-manufacturer CFD validation.
- **Local hydraulic loading map** on the underdrain plate (geometric stagger exists; Voronoi / per-nozzle loading is **§3.22 — spec only** until Phase 4 A4).
- **Target-driven inverse design UX** (“LCOW < X → suggest N and ID”) — engine grid exists (`optimisation.py`); dedicated Assessment workflow is Phase 4 A3.
- Live operations / digital twin (24 h Gantt is schematic duty, not optimised plant control).

---

## 2. Calculation strategy & pipeline

### 2.1 Orchestration (`engine/compute.py`)

```
validate_inputs → (fallback REFERENCE_FALLBACK_INPUTS if invalid)
    → water properties (feed + BW)
    → vessel geometry (ID after lining, dish, cylindrical length)
    → mechanical thickness & empty weight
    → media geometry (chordal areas/volumes per layer in horizontal drum)
    → pressure drop (Ergun + Ruth cake) + nozzle plate structural ΔP
    → nozzle schedule & supports
    → backwash (hydraulics, expansion, collector, sequence, timeline)
    → TSS mass balance → filtration cycles & feasibility matrix
    → cartridge (parallel path)
    → energy (hydraulic budget + annual kWh from metered BW duty)
    → BW equipment sizing (pump/blower/tank)
    → merge thermo blower screening into ``air_scour_solve`` (motor/shaft kW, objective — after sizing)
    → pump performance package
    → weights, lining, operating weight, saddle design
    → economics + lifecycle financials
    → assessment (severity, robustness, narrative drivers)
    → environment structural (wind/snow hooks)
```

**Post-compute enrichment (`app.py`, after `compute_all_cached`):**

```
build_design_basis(inputs, computed)      → computed["design_basis"]     (schema 1.1)
build_explainability_index(...)         → computed["explainability"]
build_lifecycle_degradation(...)        → computed["lifecycle_degradation"]
```

These bundles read the **full** `computed` dict (not a partial snapshot). They are advisory / traceability layers — they do not change Ergun, collector solve, or cash flows.

**Dependency rule:** Later stages consume SI dict keys from earlier stages; tabs never re-implement physics.

### 2.2 Caching & performance

- `ui/compute_cache.py` — `st.cache_data` on `compute_all` when inputs hash unchanged.
- Severity classifiers are **module-level functions** (pickle-safe for cache).
- Sensitivity / optimisation call full `compute_all` per perturbation — expensive by design.

### 2.3 Validation strategy

- `engine/validators.py` — structural checks on required keys, positive flows, layer sanity.
- Invalid inputs → compute still runs on **reference fallback** so UI does not blank; banners show errors.
- **Display units in errors:** Many geometry and duty checks format magnitudes in **metric or imperial** when `unit_system` is available (`format_value` path). Compare **B** stays consistent on unit toggle via `ui/compare_units.py`. **Residual gap:** not every validation branch is imperial-aware; engine math remains SI.

---

## 3. Domain models & equations

### 3.1 Process hydraulics (`engine/process.py`)

**Design loading per redundancy scenario:**

```
active_filters = n_filters_physical − hydraulic_assist − outage_depth
q_per_filter   = (total_flow / streams) / active_filters
```

- `n_filters` = physical filters per stream (includes spares in the bank).
- `hydraulic_assist` = standby units excluded from *design* hydraulic split (N+1 bank logic).
- `redundancy` = outage depth (0…4) for scenarios N, N−1, N−2, …

**Driving inputs:** `total_flow`, `streams`, `n_filters`, `hydraulic_assist`, `redundancy`

---

### 3.2 Water properties (`engine/water.py`)

| Property | Model |
|----------|--------|
| Density | Kell (1975) pure water + Millero & Poisson (1981) seawater term in salinity |
| Viscosity | Korson-style pure water + Sharqawy et al. (2010) seawater multiplier |
| TDS | ≈ salinity × density |

Three-band properties: min / avg / max / design from `temp_low`, `temp_high`, `feed_temp`, salinity presets.

**Note:** `backwash.py` uses a simpler Vogel viscosity for some internal BW helpers; feed path uses `water_properties` from compute.

---

### 3.3 Horizontal geometry (`engine/geometry.py`)

- **Chordal segment area** in a horizontal cylinder for each media layer top elevation.
- **Dish volume** — elliptic 2:1 or torispherical 10% head.
- Yields per-layer `Area`, `Vol`, and `avg_area` for LV and EBCT.

**EBCT (per layer):**

```
EBCT_min = (layer_volume_m3 / q_filter_m3h) × 60
LV_m_h   = q_filter_m3h / layer_area_m2   (or local area if layer_areas_m2 used)
```

---

### 3.4 Media catalogue (`engine/media.py`)

- Fixed catalogue (~14 types + aliases): `d10`, `cu`, `epsilon0`, `rho_p_eff`, LV/EBCT envelopes, GAC modes.
- **Interstitial velocity:** `v_int = LV / ε₀`
- **Arrangement intelligence:** support layer at bottom, density ordering warnings, garnet-on-top checks.
- Per-layer thresholds: `lv_threshold_m_h`, `ebct_threshold_min` (defaults from catalogue if unset).

**Custom layer:** user `d10`, `cu`, `ψ` → `ε₀ = f(ψ)`, porous vs solid particle density.

---

### 3.5 Filtration pressure drop (`engine/backwash.py` — `pressure_drop`)

**Clean bed — Ergun (1952):**

```
ΔP_layer = [(150·μ·(1−ε)²·u)/(φ²·d²·ε³)) + (1.75·ρ·(1−ε)·u²)/(φ·d·ε³))] × depth
```

- `u` = superficial velocity (m/s) from `q/A` (local chordal area optional).
- `d` = `d10×cu` if `cu > 1`, else `d10` (mm → m).
- `φ` = sphericity `psi` per layer.

**Cake — Ruth (1935):**

```
ΔP_cake = α × μ × LV × M
```

- `M` = solids loading on layer [kg/m²] from `solid_loading × capture_frac`.
- `α` user (`alpha_specific`) or **auto-calibrated** so dirty bed ΔP = `dp_trigger_bar` at full load × `alpha_calibration_factor`.
- Moderate = 50% of max cake; dirty = 100%.

**Capture distribution:**

1. Explicit `capture_frac` per non-support layer (normalised to 100%).
2. Else depth-proportional among filterable layers.
3. Support layers: zero capture.

**Calibration knobs:** `solid_loading_scale`, `maldistribution_factor`, `tss_capture_efficiency`, `alpha_calibration_factor`.

---

### 3.6 Filtration cycle duration (`filtration_cycle`)

```
accumulation_rate = (TSS_eff / 1000) × LV_m_h     [kg/(m²·h)]
cycle_duration_h  = m_trigger / accumulation_rate
```

- `m_trigger` derived from solids mass at trigger ΔP.
- Matrix: TSS (low/avg/high) × temperature (low/avg/high) × redundancy scenarios.

**Assumption:** Surface cake model — not bulk pore filling.

---

### 3.7 Backwash hydraulics & expansion

**BW flow:**

```
q_bw = max(bw_velocity × filter_area, 2 × q_filtration)
q_bw_design = q_bw × safety_factor (1.10)
```

**Bed expansion — Richardson–Zaki:**

```
ε_fluidised = (u_bw / u_terminal)^(1/n)
L_expanded  = L₀ × (1 − ε₀) / (1 − ε_fluidised)
```

- `u_terminal` from Stokes / intermediate regime (Archimedes → Re).
- `u_mf` — Wen & Yu (1966) for fluidisation onset.
- `n` — Richardson–Zaki exponent from Re_mf.

**Air scour:** manual rate, or **auto** (`air_scour_mode` = `auto_expansion`) — bisection to find **minimum** air-equivalent superficial velocity for target net bed expansion (Richardson–Zaki stack). After `bw_system_sizing`, `air_scour_solve` carries **`p_blower_motor_kw` / `p_blower_shaft_kw`** (thermo screening on fixed ΔP and η); Compare **B** mirrors sidebar controls.

**Collector check:** expanded bed top vs `collector_h`; freeboard vs `freeboard_mm` (via `collector_ext`).

---

### 3.8 Backwash sequence & plant timeline

**Steps:** drain → air → air/water → high-rate water → settle → fill (durations in minutes).

**Multi-day Gantt (`filter_bw_timeline_24h`, horizon 1–14 d):**

- Per-filter operate / BW segments from `bw_cycles_day` and step total.
- Stagger modes: **feasibility_trains**, **optimized_trains** (heuristic in `engine/bw_scheduler.py`), **uniform** (legacy).
- Plant buckets: hours at ≥N, =N, N−1, below N−1 online (`timeline_plant_operating_hours`).

**BW equipment sizing:**

- Pump: `P = ρ·g·Q·H / (η_pump·η_motor)`
- Blower: adiabatic ideal-gas compression (γ=1.4), inlet conditions from RFQ environment.

---

### 3.9 Mechanical — ASME VIII Div. 1 (`engine/mechanical.py`)

**Cylindrical shell (UG-27):**

```
t_shell = (P·R) / (S·E − 0.6·P) + corrosion
```

**2:1 elliptical head:**

```
t_head = (P·D·K) / (2·S·E − 0.2·P) + corrosion,   K = 1
```

- `P` in kgf/cm² (from bar × 1.01972); `S` = allowable stress from material library.
- Joint efficiency `E` from radiography map (None 0.70 / Spot 0.85 / Full 1.00).

**Nozzle plate (Roark-style plate on distributed load):**

```
t_plate = b_eff × √(q_total / (2·S_allow))
q_total = q_pressure_design + q_media_static
q_media = Σ (ρ_sat × g × layer_depth)   per layer column
```

**Operating weight:**

```
W_operating = W_empty + W_lining + W_media_dry + W_water_fill
```

**Saddle:** Zick-inspired layout — spacing factor from L/D, reactions, catalogue escalation.

---

### 3.10 Energy (`engine/energy.py`)

**Filtration pump head budget:**

```
H_pump = P_residual + ΔP_outlet + ΔP_nozzle_slot + ΔP_media + ΔP_dist + ΔP_inlet + ρg·ΔZ_static
P_kW   = (Q·m³/s × ρ × g × H) / (η_pump × η_motor × 1000)
```

**Annual energy:**

- Filtration: mean of clean/dirty hydraulic power × filters × `op_hours_yr`.
- BW pump & blower: `events_yr = bw_cycles_day × 365 × n_filters_total` × **metered hours per event** from step table (`bw_equipment_hours_per_event`).

**Philosophy:** OPEX uses **Σ kWh × tariff**, not 24/7 nameplate pump power.

---

### 3.11 Cartridge filter (`engine/cartridge.py`)

Parallel post-treatment path (not MMF vessel):

- Capacity curve vs viscosity (cp) and rating (µm).
- ΔP = quadratic in element flow (vendor-tied coefficients).
- DHC life from mass loading: `(CF_in − CF_out) × Q` vs dirt-holding capacity (g).

---

### 3.12 Fouling advisor (`engine/fouling.py`) — *not in main compute path*

Empirical correlations for sidebar suggestions:

```
solid_loading ≈ 0.28 × (TSS/10)^0.6 × (LV/10)^0.4 × f(SDI) × f(MFI)
severity      = weighted score on normalised SDI, MFI, TSS, LV
run_time_h    ≈ base_hours × (55 / (15 + severity))
```

**Use:** “Apply suggested solid loading” — order-of-magnitude only.

---

### 3.13 Optimisation MVP (`engine/optimisation.py`)

```
for patch in candidate_patches:
    inputs' = merge(base_inputs, patch)
    computed = compute_all(inputs')
    feasible = constraint_check(computed, constraints)
rank feasible by objective ∈ {capex, opex, steel, carbon}
```

Default constraints: LV ≤ cap, EBCT ≥ 0.8×floor, optional max dirty ΔP, BW flow, freeboard, steel mass.

---

### 3.14 Sensitivity (`engine/sensitivity.py`)

One-at-a-time ±% on: `total_flow`, `n_filters`, `nominal_id`, `bw_velocity`, `solid_loading`, `design_pressure`, `feed_temp`, `elec_tariff`, `steel_cost_usd_kg`.

Outputs: peak LV, min EBCT, CAPEX, dirty ΔP → tornado chart + narrative.

---

### 3.15 Multi-case compare workspace (`engine/compare_workspace.py`)

Pure-Python matrix on top of existing `compute_all` outputs — no second physics path.

| Constant | Value | Role |
|----------|-------|------|
| `MAX_LIBRARY_CASES` | 20 | Saved named designs in session (`compare_library`). |
| `MAX_COMPARE_SELECTION` | 12 | Cases computed in one **Run multi-case comparison** (`MAX_COMPARE_CASES` alias). |
| `COMPARE_TABLE_PAGE_SIZE` | 4 | Columns per results page in the UI. |

| Function | Role |
|----------|------|
| `snapshot_case_inputs(inputs, label)` | Serializable `{ "label", "inputs" }` (deep-copied SI). |
| `compare_many_designs(cases)` | `cases` = `list[(label, computed)]`; rows from **`COMPARISON_METRICS`** (`engine/comparison.py`); **`spread_pct`** = `(max − min) / \|first case\| × 100`. |
| `slice_compare_result(result, page)` | Subset of case columns for paginated table + per-page spread. |

**UI (`ui/tab_compare.py`):**

- **Design A vs B** — unchanged: editable B subset, second `compute_all`, 13 metrics, incremental `econ_financial`, CSV.
- **Design library** — save current sidebar design (up to 20 labels); multiselect **2–12** cases; **Prev / Next** when more than four columns; **CSV** includes **all** selected cases (full-width export).

**Tests:** `tests/test_compare_workspace.py` (incl. five-case run and pagination slice).

---

### 3.16 CFD boundary-condition export (`engine/collector_cfd_export.py`)

**Not** an in-app CFD solve — exports **1D / 1B+ screening** boundary data for external mesh tools (OpenFOAM, Fluent, etc.).

| Artifact | Contents |
|----------|----------|
| `build_collector_cfd_bundle(inputs, computed)` | Dict with `schema_version` (`aquasight.collector_cfd.v1`), `export_timestamp_utc`, **`disclaimer`** (screening-only), **`project`**, **`fluid`** (`rho_kg_m3`, `mu_pa_s` from BW properties in `computed`, temperature, phase label), **`geometry_si`** (vessel length/ID, header ID, lateral DN/length/orifice pitch counts, `header_feed_mode`). |
| `hydraulics_screening` | `q_bw_m3h`, `maldistribution_factor`, `flow_imbalance_pct`, header/orifice velocity caps, distribution residual, optional dual-end comparison blob. |
| `boundaries` | Screening velocity inlet(s) on header(s); per-hole **`mass_flow_outlet`** entries built from `orifice_network` (**first 500** holes also listed here for patch-style BCs; full list remains under `orifice_network`). |
| `lateral_profile`, `orifice_network` | Copies from `computed["collector_hyd"]`. |
| `openfoam_hints`, `ansys_fluent_hints` | Non-executable workflow notes. |

**Serialisation:**

- `bundle_to_json(bundle)` — pretty-printed UTF-8 JSON.
- `orifice_network_to_csv(rows)` — header `lateral_index,hole_index,station_m,y_along_lateral_m,flow_m3h,velocity_m_s,orifice_d_mm` then one row per hole.

**Format selection (UI-safe):** `normalize_cfd_export_format(fmt)` maps arbitrary session strings to **`json`** or **`csv_orifices`** (heuristic: substring `csv` + `orifice` → CSV; `json` → JSON; default **json**). `build_cfd_export_bytes(bundle, fmt)` **always** normalises before encoding and returns `(bytes, filename, mime)`.

---

### 3.17 Collector hydraulics schematic (UI)

- **Module:** `ui/collector_hyd_schematic.py` — Matplotlib **plan** and **elevation** from `inputs` + `computed["collector_hyd"]`.
- **Layout:** Longitudinal dimensions and figure captions are placed **below** the vessel outline to free the drawing window; legend and label positions tuned to reduce overlap with internals.
- **Scope:** Engineering communication and QA of the 1A/1B model — **not** a fabrication drawing.

---

### 3.18 Pressurized underdrain catalogue (`engine/nozzle_plate_catalogue.py`)

**Scope:** Screening references for **pressurized horizontal MMF** media-bed nozzle plates only.

| Excluded from catalogue | Reason |
|-------------------------|--------|
| Leopold IMT–style caps | **Gravity filters** — wrong application for this vessel type. |
| Drilled orifices labelled “collector” | **Feed / BW-out lateral** references — belong in §4 collector inputs, not the media false-bottom picker. |

**Catalogue (9 products, 2026-05):** Johnson wedge-wire (0.25 / 0.50 mm slot), Hansen Aquaflow-type insert, PP mushrooms (0.2–2.0 mm slot), HDPE mushrooms (0.5 / 2.0 mm slot). Each row stores bore, slot, Cd, typical ρ (/m²), body material, strainer family.

| Module | Role |
|--------|------|
| `nozzle_plate_catalogue.py` | `NOZZLE_PLATE_CATALOGUE`, `catalogue_patch_for_product`, `list_catalogue_products_sorted` |
| `strainer_materials.py` | Salinity-driven metal default (SS316 → duplex → super duplex); polymer bodies → PP/HDPE |
| `nozzle_system.py` | `build_underdrain_system_advisory` — coherence of ρ, strainer, catalogue |
| `ui/nozzle_catalogue_ui.py` | Unified **Media** sidebar block: plate geometry + catalogue + strainer; **Apply catalogue** via `on_click` (Streamlit-safe session patch) |
| `collector_nozzle_plate.py` | Brick/staggered layout, open area %, mechanical weight; `layout_revision` for cache busting |

**Inputs:** `nozzle_catalogue_id`, `np_density` (35–100 /m² input range; drilled false-bottom band 45–55 only for manual drilled plate), `strainer_mat`, plate geometry keys.

**Legacy IDs** (`generic_drilled_*`, `leopold_imt_2mm`, …) resolve to `None` with a one-time UI warning — users must re-pick a valid product or **Custom (manual)**.

---

### 3.19 Explainability registry (`engine/explainability.py`)

Deterministic **metric → equation → contributors** map for tooltips and review panels (not a second solver).

| Piece | Role |
|-------|------|
| `METRIC_REGISTRY` | ~10 metrics: `q_per_filter`, `solid_loading_effective`, `maldistribution_factor`, `dp_dirty`, cycle uncertainty, BW scheduler, collector imbalance, bed expansion, strainer, nozzle open area |
| `get_metric_explanation(metric_id, inputs, computed)` | Resolves `inputs.*` / `computed.*` paths to live values |
| `build_explainability_index` | Attached in `app.py` → `computed["explainability"]` |
| `ui/helpers.render_metric_explain_panel` | Filtration / Backwash expanders — plain numeric values (no code-styled paths) |

**Doc cross-links:** each registry entry includes `doc_section` (e.g. §3 Process basis, §11.4 Collector).

---

### 3.20 Lifecycle degradation advisory (`engine/lifecycle_degradation.py`)

**Sawtooth condition index** (100 % = fresh after replacement, 0 % = end of cycle) vs project year — **not** wear-rate CFD or FEA.

| Component | Nominal interval (inputs) | Stress drivers (examples) |
|-----------|---------------------------|---------------------------|
| Media bed | `media_replace_years` / `replacement_interval_media` | Short `cycle_expected_h`, high `solid_loading_effective_kg_m2`, mal_f, high `bw_velocity` |
| Nozzles / underdrain | `nozzle_replace_years` / `replacement_interval_nozzles` | BW velocity, `collector_velocity_risk`, underdrain advisory tone, nozzle orifice velocity |
| Feed / BW collector | Default 15 yr (`replacement_interval_collector` optional) | `flow_imbalance_pct`, collector mal_f calc, velocity risk flags, staged-orifice advisory |

```
effective_interval = nominal_interval / stress_factor    (stress capped 0.55–2.0)
condition(year)      = 100 × (1 − (year mod eff_interval) / eff_interval)
```

**Output:** `computed["lifecycle_degradation"]` — `components`, `findings`, `tone`, `replacement_threshold_pct` (35 %).

**UI:** Economics tab expander **「7 · Lifecycle degradation (advisory)」** — Plotly overlay + summary table + driver bullets.

**Note:** Discrete replacement cash events remain in `econ_financial.replacement_schedule`; curves are operating-stress commentary only.

---

### 3.21 Design basis & traceability (`engine/design_basis.py` v1.1)

Built **after** full `compute_all` in `app.py` (schema **`1.1`**).

| Block | Contents |
|-------|----------|
| `assumptions_catalog` | Stable IDs **`ASM-*`** (process, media, BW, collector, internals, fouling) |
| `traceability` | Rows **`TRC-*`**: label, resolved value, unit, source, doc §, linked assumption IDs |
| `underdrain` | Catalogue label, ρ, strainer, advisory tone |
| `collector` | 1D method, distribution convergence, screening suggestions |
| `explainability_metrics` | Cross-link to `METRIC_REGISTRY` ids |
| `exclusions` | CFD, 3D manifold, MILP scheduler, gravity/leopold/collector-drilled catalogue scope |

**Report formatters:** `design_basis_report.py` — assumptions table, traceability table, underdrain summary; PDF/Word section **Design basis & traceability**.

**UI:** Report tab expander + JSON download; Assessment tab sample assumptions / trace rows.

---

### 3.22 Spatial hydraulic distribution — specification (Phase 4 A4, not yet coded)

> **Status (2026-05):** **Specification only** — connects to delivered **geometric** layout in `engine/collector_nozzle_plate.py` (`staggered_plate_layout`, `build_staggered_nozzle_hole_network`). Implementation planned as **post-compute enrichment** (same pattern as `lifecycle_degradation`, `design_basis`).

#### Purpose

Move from **average** nozzle-plate quantities (density → count → open area %) toward **local hydraulic loading** on a 2D plan projection — advisory screening for nozzle optimisation, erosion risk, media utilisation, and CFD export enrichment. **Not** a substitute for 3D bed CFD or manufacturer orifice testing.

#### Scope boundaries

| In scope | Out of scope |
|----------|----------------|
| 2D plan view of pressurized underdrain / nozzle plate active area | 3D bed CFD, channeling in media |
| Voronoi (or equivalent) **service area** per hole centre | Full coupled nozzle ↔ lateral ↔ header network solve |
| Lumped **approach-flow split** by service area | DCS / real-time spatial sensing |
| Uniformity index + dead-zone **heuristic** near walls / large spacing | Guarantee of uniform filtration performance |

#### Inputs (reuse existing — no duplicate layout UI)

| Source | Keys / objects |
|--------|----------------|
| `computed["collector_nozzle_plate"]` | `holes_xy[]`, `layout_revision`, `n_holes`, `open_area_fraction`, plate dimensions |
| `inputs` | `nozzle_plate_enable`, BW / filtration flows as needed for velocity basis |
| Optional flag | `spatial_distribution_enable` (default off until module ships) |

#### Proposed `computed["spatial_distribution"]` (SI)

```json
{
  "enabled": true,
  "layout_revision": 3,
  "method": "voronoi_lumped_v1",
  "n_nozzles": 142,
  "nozzle_xy_m": [[x, y], ...],
  "nozzle_service_area_m2": [0.012, ...],
  "nozzle_open_area_m2": [1.2e-5, ...],
  "nozzle_local_velocity_m_h": [38.2, ...],
  "nozzle_loading_factor": [1.05, ...],
  "dead_zone_probability": [0.02, ...],
  "hydraulic_uniformity_index": 0.91,
  "max_loading_factor": 1.18,
  "min_loading_factor": 0.84,
  "advisory_flags": ["edge_nozzle_high_loading"],
  "assumption_ids": ["ASM-SPATIAL-001", "ASM-SPATIAL-002"],
  "note": "2D plan screening; lumped Q split by Voronoi area."
}
```

| Field | Definition (v1 screening) |
|-------|---------------------------|
| `nozzle_service_area_m2[i]` | Voronoi cell area for hole *i*, clipped to plate **active** rectangle (arc segment or full rectangle per layout mode). |
| `nozzle_local_velocity_m_h[i]` | `Q_basis × (A_service_i / Σ A_service) / A_open_i` with `Q_basis` = filtration or BW flow through plate (document which in ASM). |
| `nozzle_loading_factor[i]` | `v_local_i / mean(v_local)` (dimensionless). |
| `dead_zone_probability[i]` | Heuristic 0–1: elevated near vessel wall clip, spacing > 1.5× pitch, or service area > 2× median. |
| `hydraulic_uniformity_index` | e.g. `1 − std(loading_factor) / mean(loading_factor)` capped [0, 1]. |

#### Planned engine & integration

| Piece | Location |
|-------|----------|
| Core | `engine/spatial_distribution.py` (new) |
| Hook | `app.py` after `compute_all` + `collector_nozzle_plate` available |
| Tests | `tests/test_spatial_distribution.py` — uniform grid → ~uniform loading; edge holes flagged |
| UI owner | **Mechanical** or **Backwash** — plan heatmap of `nozzle_loading_factor`; link to existing stagger plot |
| CFD | Optional columns on `collector_cfd_export` orifice CSV: `service_area_m2`, `local_velocity_m_h` |
| Governance | `ASM-SPATIAL-*` in `design_basis`; explainability contributors on uniformity index |

#### Applications

- Nozzle plate **density / pitch** optioneering before fabrication.
- Cross-check with `collector_intelligence` erosion velocity advisories.
- **Media utilisation** narrative (advisory): high local loading → earlier cake localisation risk.
- External CFD: richer per-hole BC table without re-deriving geometry in the mesh tool.

---

### 3.23 Operating envelope map (`engine/operating_envelope.py`) — **Delivered (Phase 4 A2)**

Post-compute in `app.py` (before `build_design_basis` so traceability can resolve paths).

| Block | Contents |
|-------|----------|
| Method | `lv_ebct_grid_v1` — 2D grid of plant LV vs hypothetical min EBCT; per-layer threshold checks (`lv_severity_classify`, `ebct_severity_classify`) |
| `lv_axis_m_h`, `ebct_axis_min` | SI grid axes |
| `region_matrix` | `stable` \| `marginal` \| `elevated` \| `critical` per cell |
| `severity_rank_matrix` | 0–3 numeric mirror for charts |
| `scenario_points[]` | `N`, `N−1`, … from `load_data`: actual `lv_m_h`, `ebct_min_min`, `region`, `worst_layer` |
| Governance | `ASM-ENV-01`; explainability id `operating_envelope_n`; `TRC-*` for N region |

**UI:** Filtration tab expander — Plotly heatmap + scenario slider (N → N−k).

**Limits:** Screening map only — grid cells decouple LV and EBCT; not RTD, breakthrough, or guarantee of uniform bed utilisation.

---

### 3.24 Design-to-target search (`engine/design_targets.py`) — **Delivered (Phase 4 A3)**

| Block | Contents |
|-------|----------|
| Method | Grid over `n_filters` × optional `nominal_id` × `bw_velocity`; each row = `compute_all` via `evaluate_candidate` |
| Targets | `max_dp_dirty_bar`, `max_lcow_usd_m3`, `max_q_bw_m3h`, `max_capex_usd` (any subset) |
| `computed["design_targets"]` | `baseline` (current design vs caps); `search` filled from Assessment UI session |
| Ranking | Feasible + `meets_targets` → sort by normalized slack + CAPEX tie-break |
| UI | Assessment expander — caps, grid, **Run search**, ranked table, **Apply** per row |
| Governance | `ASM-DTARGET-01`; explainability `design_targets_lcow` |

**Limits:** MVP grid only (no MILP). Dirty ΔP from Ruth/Ergun screening — may exceed trigger; set caps accordingly. Explicit Apply — no auto-write to sidebar.

---

## 4. Assessment & decision logic

### 4.1 Per-layer severity (`compute.py`)

| Class | LV trigger | EBCT trigger |
|-------|------------|--------------|
| Advisory | 0–5% over cap | 0–10% under floor |
| Warning | 5–15% over | 10–25% under |
| Critical | >15% over | >25% under |

Caps/floors from layer dict or catalogue defaults (`thresholds.py`).

### 4.2 Overall risk rating

Aggregates counts across **all scenarios × all non-support layers**:

| Rating | Typical rule (simplified) |
|--------|---------------------------|
| **STABLE** | No critical/warning; ≤1 advisory |
| **MARGINAL** | N-scenario warning or isolated critical |
| **ELEVATED** | N-scenario critical or ≥3 warnings |
| **CRITICAL** | Multiple scenario criticals or critical+warnings |

Plus templated **drivers**, **impacts**, **recommendations** keyed by rating.

### 4.3 Design Robustness Index

For each scenario N, N−1, …:

- Worst LV severity and EBCT severity across layers.
- Labels: Stable / Marginal / Sensitive / Critical.

Stored as `rob_rows` with **SI** `lv_m_h` (not pre-formatted strings).

### 4.4 Design comparison (`engine/comparison.py`)

**14** rows in `COMPARISON_METRICS` — per-metric % difference and 5% (or metric-specific) significance threshold:

- Hydraulics, ΔP, BW, weight, CAPEX, OPEX.
- `favours` A or B when difference exceeds threshold and direction matches `higher_is_better`.

---

## 5. Economics & financial models

### 5.1 CAPEX (`capex_breakdown`)

```
Steel $ = w_steel × $/kg × n_vessels
+ erection, labor, piping lump per vessel, I&C lump
+ engineering % × direct
+ contingency % × subtotal
Civil $ = w_operating × $/kg_working × n
```

### 5.2 OPEX (`opex_annual`)

- Energy: prefer component kWh breakdown × `elec_tariff`.
- Media replacement, nozzle replacement, labour/filter-yr, chemicals per m³ treated.

### 5.3 LCOW & simple NPV profile

```
CRF = i(1+i)^n / ((1+i)^n − 1)
LCOW = (CAPEX × CRF + OPEX_annual) / annual_flow_m3
```

`npv_lifecycle_cost_profile` — cumulative discounted cost curve (simplified).

### 5.4 Lifecycle financial (`financial_economics.py`)

- Multi-year cash flow with inflation, energy/maintenance escalation, tax, depreciation (SL or DDB).
- Replacements: media, nozzles, lining on intervals.
- NPV, IRR, payback, ROI; NPV sensitivity spider (±10% drivers).
- Compare tab: incremental ΔCAPEX, ΔNPV, Δ year-1 operating cash.

### 5.5 Carbon

```
Operational CO₂ = Σ (kWh_yr_component × grid_intensity)
Embodied       = steel + concrete + media factors (user kgCO₂/kg)
```

---

## 6. Input strategy (how we collect design intent)

### 6.1 Layered input model

| Layer | Where | What |
|-------|-------|------|
| **Project** | Sidebar top + toolbar | Name, doc no., client, unit system |
| **Process** | Sidebar tab | Flow, streams, N+1, redundancy, water, TSS bands, cartridge |
| **Vessel** | Sidebar tab | ID, length, heads, material, ASME inputs, lining |
| **Media** | Sidebar tab | Dynamic layers (type, depth, capture %, custom d10/ρ) |
| **Backwash** | Sidebar tab | Velocities, step times, cycles/day, air scour mode |
| **Economics** | Sidebar tab | Costs, life, discount, financial lifecycle, carbon |
| **Pumps** | Main tab (merged) | ΔP budget, η, motor class, RFQ metadata → merged to SI `inputs` |
| **Design B** | Compare tab | Subset override; rest copied from A (SI storage) |

### 6.2 SI contract rules

1. Widget shows `display_value(SI_default)`.
2. On Apply: `convert_inputs(out, unit_system)` → engine dict.
3. JSON file stores **SI**; load → `get_widget_state_map` → display widgets if imperial.
4. Session-only RFQ keys (`ab_*`, some `pp_*`) → SI in `_ui_session` on save.

### 6.3 Calibration & “engineering judgement” inputs

These let experienced users tune models without forking code:

| Input | Effect |
|-------|--------|
| `solid_loading` / `solid_loading_scale` | Cake mass basis |
| `alpha_specific` / `alpha_calibration_factor` | Cake resistance |
| `maldistribution_factor` | LV/ΔP non-ideality |
| `tss_capture_efficiency` | Effective TSS for cycle matrix |
| `expansion_calibration_scale` | Bed expansion display |
| `dp_trigger_bar` | Dirty ΔP endpoint / auto-α |
| Per-layer `lv_threshold_m_h`, `ebct_threshold_min` | Assessment setpoints |

### 6.4 Input UX patterns that work

- **Presets** — water (Red Sea, Mediterranean, …), media types from catalogue.
- **Derived readouts** — “Calculated N filters/stream”, q/filter preview.
- **Normalize capture weights** button — keeps cake split honest.
- **Deferred project load** — before widgets instantiate (Streamlit constraint).
- **Collapsed input column** — results full-width; pump reconcile preserves SI merge.

### 6.5 Input gaps (enhancement fodder)

| Gap | Status |
|-----|--------|
| Fouling guided workflow | **Delivered** — `ui/fouling_workflow.py`; Apply buttons for selected suggestions only |
| Design basis import | JSON project + built basis export; no DBR/P&ID import wizard |
| **Target-driven inverse design** | **Partial** — `optimise_design` grid + Assessment sweep/Pareto exist; no “target LCOW / ΔP / Q_BW → ranked recommendations” UX (**Phase 4 A3**) |
| Layer threshold round-trip | Per-layer setpoints in session; not all keys in `project_io` JSON |
| **Imperial edge cases** | Compare B uses `compare_units.py`; rare SI-only strings in validators — see §2.3 |

---

## 7. Display & content strategy (how we present results)

### 7.1 Tab = engineering concern (not calculation order)

| Tab | User question answered |
|-----|-------------------------|
| 💧 Filtration | “What are LV/EBCT and cycles across scenarios?” |
| 🔄 Backwash | “Will beds expand safely? Is BW scheduling feasible?” |
| ⚙️ Mechanical | “Is the vessel buildable? How heavy? Nozzles?” |
| 🧱 Media | “What’s in the bed? ΔP breakdown? Intelligence warnings?” |
| ⚡ Pumps & power | “What head and kW? Pump/datasheet narrative?” |
| 💰 Economics | “What does it cost and emit? Lifecycle cash? **Degradation curves** (media / nozzles / collector)?” |
| 🎯 Assessment | “Is it safe? What if we lose a filter? What moves NPV?” |
| 📄 Report | “Give me a file for the client.” |
| ⚖️ Compare | “Is **B vs A** better on **13** `COMPARISON_METRICS` + incremental NPV? **Library:** save up to **20** cases, compare **2–12**, paginated table (**4**/page), full CSV.” |

### 7.2 Display rules

- **`computed` stays SI** — never format inside engine.
- **`fmt(si, quantity)`** — human strings in tables/metrics.
- **`dv(si, quantity)`** — numeric values for charts/sliders.
- **`ulbl(quantity)`** — column headers follow unit toggle.
- **Specialised helpers** — `pressure_drop_layers_display_frames`, `fmt_bar_mwc`, `fmt_si_range` for benchmarks.

### 7.3 Progressive disclosure

- Expanders for lifecycle financial, **lifecycle degradation (§7)**, explainability (Filtration), tornado, media intelligence, fouling workflow, n_filters sweep.
- Status badges in input column — traffic-light summary without opening tabs.
- Validation banners — errors before tabs when inputs invalid.

### 7.4 Content ideas — delivered vs backlog

| Idea | Status | Notes |
|------|--------|-------|
| **Design basis panel** | **Delivered** | v1.1 — `ASM-*` / `TRC-*` on Report + Assessment |
| **Traceability / explainability** | **Delivered** | `METRIC_REGISTRY` + contributor panels (Filtration / Backwash) |
| **Lifecycle degradation** | **Delivered** | Economics expander §7 — advisory sawtooth curves |
| **Uncertainty bands on charts** | **Backlog (B4)** | `cycle_uncertainty` exists; shaded Plotly regions not wired |
| **Operating envelope chart** | **Delivered (A2)** | `operating_envelope.py`; Filtration heatmap + scenario slider |
| **Design-to-target inverse UX** | **Delivered (A3)** | `design_targets.py`; Assessment caps + Apply |
| **Spatial loading heatmap** | **Backlog (A4)** | §3.22 spec — `spatial_distribution` post-compute |
| **Media life narrative** | **Backlog** | Link cycle → replacement → OPEX in one caption block |
| **Client / engineer modes** | **Backlog** | Hide calibration vs expose raw SI |

### 7.5 Collector schematic presentation

Plan/elevation figures live on **Backwash** (collector hydraulics). Layout and annotation rules are in **§3.17** — bottom-heavy dimensions and caption placement for readability.

---

## 8. Enhancement compass (for outside-the-box thinking)

Use these prompts with AI or workshops. Each axis is independent — mix and match.

### 8.1 Platform / product ideas

| Direction | Status | Description |
|-----------|--------|-------------|
| **Design library** | **Delivered (MVP)** | `engine/project_db.py` + `ui/project_library.py` — SQLite projects / snapshots |
| **Multi-case workspace** | **Delivered** | Library **20**, run **12**, pagination **4**/page (`compare_workspace.py`) |
| **Project revision tree** | **Backlog (B3)** | Projects → Cases → Revisions → report hash; diff/export |
| **Requirements traceability** | **Backlog** | Link inputs to P&ID tag / DBR line item beyond `TRC-*` |
| **Collaboration** | **Backlog** | Comments on assessment drivers; JSON revision diff |
| **API-first clients** | **Partial** | FastAPI `POST /compute`; no PDF-only ERP contract |
| **Digital twin lite** | **Backlog (C4)** | Import ops LV, ΔP, BW times → recalibrate α |
| **Regulatory packs** | **Backlog** | Client-specific report section templates |

### 8.2 Core engineering ideas (deeper physics)

| Direction | Status | Description |
|-----------|--------|-------------|
| **1D collector hydraulics (1A/1B/1B+)** | **Delivered** | `collector_hydraulics.py`, manifold, auto maldistribution, CFD BC export |
| **Spatial nozzle loading (2D plan)** | **Spec (§3.22)** | Voronoi service area + lumped velocity — **Phase 4 A4** |
| **Biofouling / GAC breakthrough** | **Backlog** | First-principles growth or adsorption curves |
| **Air scour + blower** | **MVP delivered** | `auto_expansion`, thermo kW; **Backlog (B1):** vendor maps, VFD affinity |
| **BW scheduler** | **MVP delivered (v2)** | Heuristic stream-aware; **Backlog:** MILP/DCS (C5), peak-tariff v3 (B2) |
| **CFD export** | **Delivered (MVP)** | JSON + orifice CSV; in-app solve **backlog (C2)** |
| **Vertical vessel path** | **Backlog** | Second geometry kernel — major fork |

### 8.3 Content / UX ideas

| Direction | Status | Description |
|-----------|--------|-------------|
| **Fouling guided workflow** | **Delivered** | 5-step UI + `build_fouling_assessment` |
| **Explainability panels** | **Delivered** | Metric contributors — not LLM-generated |
| **Guided “new train” wizard** | **Backlog** | Flow → water → media template → auto N |
| **Risk storytelling / benchmark radar** | **Backlog** | Executive one-pager; regional econ bands |
| **Training mode** | **Backlog** | Locked reference case + quizzes |

### 8.4 Input ideas

| Direction | Status | Description |
|-----------|--------|-------------|
| **Excel import** | **Backlog** | Column mapping to `inputs` |
| **P&ID OCR** | **Backlog (C3)** | Aspirational |
| **Fouling panel** | **Delivered** | SDI/MFI/TSS workflow with Apply pattern |
| **Design-to-target inverse** | **Backlog (A3)** | LCOW / ΔP / Q_BW targets → ranked design patches |
| **Unit-aware validation** | **Partial** | Imperial messages in validators; edge cases remain |

### 8.5 Display ideas

| Direction | Status | Description |
|-----------|--------|-------------|
| **Operating envelope map** | **Backlog (A2)** | LV vs EBCT heatmap + severity regions |
| **Scenario N animation** | **Backlog (A2)** | N → N−1 → N−2 on one chart |
| **Spatial loading heatmap** | **Backlog (A4)** | Plan view of `nozzle_loading_factor` |
| **Vessel sketch interactivity** | **Backlog** | Click layer → media row |
| **Sankey energy/mass** | **Backlog** | kWh and TSS flow diagrams |
| **Imperial-native PDF** | **Backlog** | Reports without SI footnotes |

### 8.6 AI-assisted development patterns

When asking Claude/Cursor to extend the platform:

1. Read **`AQUASIGHT_MMF_PROJECT.md`** and this file (**§3**, **§11**).
2. **Preserve** single `compute_all` physics path; **SI internally only**; no duplicate equations in UI.
3. **Prefer post-compute enrichment** in `app.py` when core physics is unchanged.
4. **New features** must attach to `computed[]`; avoid a second calculation path without explicit Phase approval.
5. State **engine vs UI vs display-only**; require `tests/test_<module>.py` with numeric assertions.
6. Wire **design basis** (`ASM-*`) + **explainability** for any new published metric.
7. **Update §3 and §11** in the same PR; report **runtime impact** (ms per `compute_all` or post-hook).
8. New inputs: `INPUT_QUANTITY_MAP` + `project_io` widget map when persisted.

---

## 9. Epistemic limits & honesty

Statements the platform should *not* overclaim:

| Topic | Limit |
|-------|--------|
| Ergun + Ruth | Packed-bed correlations; not validated per site without pilot data. |
| BW expansion | Richardson–Zaki with calibrated scale; air/water interaction simplified. |
| ASME thickness | Screening thickness; full code compliance needs qualified engineer + MDMT + nozzles FEA. |
| Economics | 2024 ME/Med benchmark bands; excludes freight, duties, local content rules. |
| Fouling | Empirical; SDI/MFI not standardised across labs. |
| Cartridge | Generic vendor curves; confirm with supplier datasheet. |
| Assessment severity | Rule-based thresholds; not probabilistic reliability. |

**Recommended disclaimer in reports:** “Indicative engineering calculation for optioneering — site-specific validation required.”

---

## 10. Quick reference — correlations

| Domain | Primary correlation | Module |
|--------|---------------------|--------|
| Water ρ | Kell + Millero & Poisson | `water.py` |
| Water μ | Korson + Sharqawy | `water.py` |
| Clean ΔP | Ergun | `backwash.py` |
| Cake ΔP | Ruth | `backwash.py` |
| Fluidisation | Wen & Yu, Richardson–Zaki | `backwash.py` |
| Shell/head t | ASME VIII-1 UG-27 / App. 1-4 | `mechanical.py` |
| Nozzle plate t | Roark plate | `mechanical.py` |
| Saddle | Zick (simplified) | `mechanical.py` |
| LCOW | CRF × CAPEX + OPEX | `economics.py` |
| NPV/IRR | DCF standard | `financial_economics.py` |
| Cartridge ΔP | Quadratic in q | `cartridge.py` |
| Fouling hint | Power-law on TSS/LV/SDI/MFI | `fouling.py` |

---

## Related documents

| File | Role |
|------|------|
| `AQUASIGHT_MMF_PROJECT.md` | Architecture, file map, roadmap, unit-system gaps |
| `engine/validators.py` | `REFERENCE_FALLBACK_INPUTS` — canonical SI example dict |
| `tests/test_integration.py` | End-to-end smoke for `compute_all` |

---

## 11. Development priorities — reconciled view (vs external roadmap)

> External prompts (e.g. ChatGPT) often align on *direction* but mis-order *dependencies* or underestimate *existing code*. This section is the **repo-informed** sequencing for the next phase. Philosophy unchanged: single SI core, explainable physics, no black-box ML.

### 11.1 What the external roadmap gets right (2026-05)

- **Single compute core + governance layer** (design basis, explainability, lifecycle) increases credibility without forking physics.
- **Collector hydraulics** was the largest gap — **1A/1B/1B+** now delivered; remaining gap is **spatial loading** (§3.22) and in-app CFD.
- **Deterministic uncertainty** before Monte Carlo — **2A delivered** (`cycle_uncertainty`, `cycle_economics`).
- **Decision intelligence** (envelope maps, target-driven inverse, spatial maps) is the next product shift — not more isolated equations.
- **No architecture rewrite** — post-compute enrichment + `computed[]` keys.

### 11.2 What to correct or defer

| External claim | Repo reality (updated) |
|----------------|------------------------|
| Doc name `MODELS_AND_LOGIC.md` | Use **`AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md`** |
| Collector “no hydraulic model” | **Stale** — 1A/1B/1B+ delivered; no in-app CFD |
| Fouling “not wired” | **Stale** — 5-step `fouling_workflow.py` delivered |
| Optimisation “missing UX” | **Stale** — Assessment grid + Pareto + apply; **missing:** target-driven inverse (A3) |
| Multi-case “≤4 only” | **Stale** — library 20 / run 12 / pagination |
| Spatial nozzle loading | **Spec only** — §3.22; geometric stagger delivered |
| Monte Carlo lite | **Defer (C1)** — envelope preferred for Streamlit UX |
| MILP BW scheduler | **Defer (C5)** — heuristic v2 delivered |

### 11.3 Recommended phasing (execution order)

#### Phase 0 — Stabilise the platform (1–2 weeks, parallel) — **DELIVERED (2026-05)**

- Unit/project/compare hardening (imperial load, Compare SI, toolbar, library hydrate).
- **Design basis & traceability** in Report PDF/Word (`engine/design_basis.py`).
- Collector **1A/1B input schema** agreed and wired (sidebar BW collector + `project_io`).

#### Phase 1 — High leverage, low risk (4–6 weeks) — **DELIVERED (2026-05)**

| # | Item | Status |
|---|------|--------|
| **2A** | `engine/uncertainty.py` + Filtration chart + Assessment driver | **Done** — `computed["cycle_uncertainty"]` |
| **3** | Fouling guided workflow | **Done** — `ui/fouling_workflow.py`, `engine/fouling.py` helpers |
| **1C** | Collector intelligence (rules) | **Done** — `engine/collector_intelligence.py`, Backwash expander |
| **Opt-UI** | `optimise_design` ranker UI | **Done** — Assessment tab expander |

#### Phase 2 — Core physics extension — **DELIVERED (2026-05)** except optional follow-ups

| # | Item | Status |
|---|------|--------|
| **1A** | `engine/collector_hydraulics.py` — 1D Darcy + orifice ladder | **Done** — `computed["collector_hyd"]`, profile[], velocity flags, `collector_geometry` / lateral types, Backwash UI + schematics |
| **1A→ΔP** | Optional auto `maldistribution_factor` | **Done** — `use_calculated_maldistribution`; feeds Ergun when enabled |
| **1B** | Lateral distribution solver (1D, one-end header) | **Done** — fixed-point balance (≤64 iter, rel. tol 0.002); `flow_imbalance_pct`, residual + iterations in Backwash expander; **not** CFD / 3D manifold |
| **Basis** | Design basis & traceability export | **Done** — `design_basis_report.py`, PDF/Word section, `build_design_basis()` |
| **1B+** | Dual-end feed + orifice network + CFD BC export | **Done (MVP)** — `collector_manifold.py`, `collector_cfd_export.py`; in-app CFD backlog |
| **Bench** | Collector hand-calc regression suite | **Done** — `engine/collector_benchmarks.py` (8 cases); Backwash expander |
| **Cmp+** | Multi-case compare (library 20 / run 12) | **Done** — `compare_workspace.py`, pagination, `slice_compare_result` |
| **Sched** | Dynamic BW scheduler | **Done (MVP)** — multi-day horizon + `optimized_trains`; MILP/DCS out of scope |

#### Phase 3 — Platform scale — **partially delivered (2026-05)**

| Item | Status |
|------|--------|
| BW scheduler v2 (stream-aware, peak windows) | **Done (MVP)** — `engine/bw_scheduler.py`, Backwash UI |
| Multi-design workspace scale-up | **Done** — library 20 / compare 12 / pagination |
| Design basis traceability v1.1 | **Done** — `build_design_basis` post-compute in `app.py` |
| Explainability registry | **Done** — `engine/explainability.py` |
| Lifecycle degradation curves | **Done (advisory)** — `engine/lifecycle_degradation.py`, Economics §7 |
| Pressurized underdrain catalogue | **Done** — 9 products; gravity/collector rows removed |
| Uncertainty → economics bands | **Done** — `uncertainty_economics.py` → `cycle_economics` |
| Monte Carlo lite | **Backlog** — optional, behind checkbox |
| MILP / DCS BW optimiser | **Backlog** — heuristic scheduler only |

#### Phase 4 — Decision intelligence (2026+) — **NEXT**

> **Goal:** Move from “calculator” to **engineering decision platform** without breaking the single `compute_all` path. Recommended build order: **A2 → A3 → A4**.

| ID | Item | Engine / UI | `computed[]` key | Status |
|----|------|-------------|------------------|--------|
| **A2** | Operating envelope map | `operating_envelope.py`; Filtration heatmap | `operating_envelope` | **Done** |
| **A3** | Design-to-target inverse | `design_targets.py`; Assessment expander | `design_targets` | **Done** |
| **A4** | Spatial hydraulic distribution | `spatial_distribution.py`; Mechanical/Backwash heatmap | `spatial_distribution` | **Spec §3.22** |

**Tier B (after A2–A4 or parallel when resourced)**

| ID | Item | Status |
|----|------|--------|
| **B1** | Real blower maps (vendor curves, VFD affinity) | Backlog |
| **B2** | BW scheduler v3 (peak tariff, maintenance windows) | Backlog |
| **B3** | Project revision tree on SQLite | Backlog |
| **B4** | Shaded uncertainty bands on Filtration charts | Backlog |

**Tier C (defer — document only)**

| ID | Item |
|----|------|
| **C1** | Monte Carlo lite |
| **C2** | In-app CFD / 3D manifold |
| **C3** | P&ID OCR |
| **C4** | Digital twin lite |
| **C5** | MILP / gradient optimiser + DCS scheduler |

### 11.4 Priority 1 — collector package (refined)

> **Delivery status (2026-05):** **1A**, **1B** (scoped), and **1C** are implemented.  
> **In scope for 1B:** iterative lateral flow balance on a **one-end-fed header** with Darcy losses + orifice discharge; UI shows **iterations**, **relative residual**, and **imbalance %**.  
> **1B+ (MVP, 2026-05):** dual-end header balance (`collector_header_feed_mode`), per-hole `orifice_network[]`, external CFD BC export (`collector_cfd_export.py`).  
> **Still out of scope:** in-app CFD solve, 3D tee FEA, full nozzle-plate network — see `build_design_basis()` exclusions.

**1A — delivered** — minimum viable physics:

```
Inputs (new)     → collector_header_id_m, n_bw_laterals, lateral_dn_mm, lateral_spacing_m,
                   lateral_length_m?, lateral_orifice_d_mm, lateral_discharge_cd, construction type
Existing         → collector_h, nozzle_plate_h, bw_velocity, q_bw, layers, nominal_id
Outputs          → computed["collector_hyd"]: profile[], mal_factor_calc, velocity flags
Integration      → pressure_drop(..., maldistribution_factor= mal_user or mal_calc)
Files            → engine/collector_hydraulics.py, collector_geometry.py, ui/tab_backwash.py,
                   ui/collector_hyd_schematic.py, engine/collector_optimisation.py
```

**1C — delivered** — rule engine on:

- `bw_col` freeboard / `max_safe_bw_m_h`
- Nozzle schedule max/min velocity vs erosion/heuristics
- Air header DN vs scour flow  
- `engine/collector_intelligence.py`, Backwash advisories expander

**1B — delivered (scoped)** — lateral distribution on the 1A ladder:

- Fixed-point solve capped at 64 iterations; `distribution_residual_rel` ≤ 0.002 ⇒ converged
- `flow_imbalance_pct`, `maldistribution_factor_calc` → Ergun when `use_calculated_maldistribution`
- Backwash **Collector hydraulics** expander: iterations, solver status, imbalance %, profile plots
- Tests: `tests/test_collector_hydraulics.py`, `tests/test_distribution_convergence.py`

### 11.5 Priority 2 — uncertainty (refined)

**2A envelope** — explicit scenarios, not statistics:

```text
optimistic  = min(cycle_duration | α_low, TSS_low, capture_high, mal_low)
expected    = base case (current)
conservative= max(cycle_duration | α_high, TSS_high, capture_low, mal_high)
```

Add `computed["cycle_uncertainty"]` and Filtration band chart. Assessment: widen risk if `(conservative − optimistic) / expected > threshold`.

**Do not** claim “95% confidence” — use **optimistic / expected / conservative** only.

### 11.6 Priority 3 — fouling workflow (refined)

Steps 1–4 from external prompt are good; map to **existing** sidebar keys:

| Step | Implementation |
|------|----------------|
| 1 Feed characterisation | Extend expander; add algae/season/chlorine as **qualitative enums** (not in compute) |
| 2 Consequences | Narrative from `estimate_run_time` + severity + link to **2A spread** when built |
| 3 Suggestions | Bullet list + **Apply** buttons (existing pattern for M_max only) |
| 4 Honesty | Fixed caption + confidence from input completeness score |

**Never** auto-write `n_filters` or `bw_velocity` without explicit Apply.

### 11.7 Secondary pipeline — honest priority ranks (updated)

| Item | Value | Effort | Status |
|------|-------|--------|--------|
| Optimisation UI + Pareto rank | High | Medium | **Done** — Assessment expander |
| Design basis / traceability v1.1 | High | Medium | **Done** |
| Dynamic BW scheduler v2 | High | High | **Done (MVP)** |
| Multi-design workspace | Medium | Medium | **Done** — library 20, run 12 |
| Uncertainty → economics | Medium | Medium | **Done** — `cycle_economics` |
| Lifecycle degradation curves | Medium | High | **Done (advisory)** |
| Operating envelope map (A2) | High | Medium | **Done** |
| Design-to-target inverse (A3) | High | Medium | **Done** |
| Spatial distribution (A4) | High | High | **After A2/A3** — §3.22 |

### 11.8 Implementation checklist (every feature)

1. New logic in `engine/*.py` only.
2. Register outputs on `computed`; SI only.
3. `tests/test_<module>.py` with numeric fixtures.
4. UI: `fmt`/`dv`/`ulbl`; one tab owner.
5. Update this doc §3 equation entry.
6. API: `compute_all` pickling — no lambdas in `computed`.

### 11.9 Prompt to use with AI assistants

```text
You are extending AQUASIGHT MMF.

Read:
- AQUASIGHT_MMF_PROJECT.md
- AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md (§3 equations, §11 Phase 4)

Rules:
- Preserve single compute_all physics path
- SI internally only
- Do not duplicate equations in UI
- New features must attach to computed[]
- Avoid introducing second calculation paths
- Prefer post-compute enrichment over engine modification when physics is unchanged

Implement [FEATURE] following Phase 4 item [A2|A3|A4|B*|C*].

Return:
1. Engine module(s)
2. Inputs added (with INPUT_QUANTITY_MAP / project_io if persisted)
3. computed[] outputs (SI keys and shapes)
4. tests/test_<module>.py required
5. UI owner tab + expander name
6. assumptions/limits (ASM-* ids) + design_basis + explainability hooks
7. runtime impact (ms per compute_all or post-hook)
8. updates required in §3 and §11 documentation
```

---

### Shipped deltas (2026-05)

Reference changelog aligned with repo behaviour documented in §2.1, §3.7, §3.15–§3.22, §7.1, §7.4–§7.5, §8, and §11 Phase 4:

| Topic | Summary |
|-------|---------|
| **Operating envelope (A2)** | `operating_envelope.py`; LV×EBCT heatmap; scenario slider; `ASM-ENV-01`. |
| **§3.22 spatial spec** | Voronoi service area + lumped local velocity — **spec only**; Phase 4 **A4**. |
| **§8 / §11 refresh** | Delivered vs backlog columns; Phase 4 decision intelligence (A2/A3/A4); updated AI assistant prompt. |
| **Air scour** | `auto_expansion` finds **minimum** air-equivalent superficial velocity for target net expansion; after `bw_system_sizing`, **`air_scour_solve`** includes motor/shaft blower kW and objective; Compare **B** mirrors sidebar air-scour mode widgets. |
| **Multi-case compare** | Library **20**, run **12**, UI pages of **4** columns; full CSV export. |
| **Underdrain catalogue** | Pressurized-only (**9** products); salinity strainers; Apply via `on_click`. |
| **Explainability** | `METRIC_REGISTRY` + Filtration/Backwash panels; plain values in UI. |
| **Design basis** | Schema **1.1**; `ASM-*` / `TRC-*`; post-compute in `app.py`. |
| **Lifecycle degradation** | Sawtooth media / nozzle / collector; Economics expander **§7**. |
| **BW scheduler v2** | Stream-aware phases, peak concurrent windows on all stagger modes. |
| **Fouling workflow** | 5-step UI; `build_fouling_assessment`; cycle cross-check. |
| **CFD export** | Full BC **JSON** bundle + **orifice CSV**; **`normalize_cfd_export_format`** maps legacy UI labels to `json` / `csv_orifices`. |
| **Schematic** | `collector_hyd_schematic` — dimensions below vessel, cleaner legend/captions (§3.17). |
| **Tests (indicative)** | `test_compare_workspace`, `test_explainability`, `test_design_basis`, `test_lifecycle_degradation`, `test_nozzle_plate_catalogue`, `test_nozzle_system`, `test_strainer_materials`, `test_fouling_workflow`, `test_bw_scheduler`, `test_collector_nozzle_plate`. |

---

*Document version: 2026-05-16 (Phase 0) — §3.22 spatial spec, §8 compass refresh, §11 Phase 4 roadmap (A2/A3/A4, Tier B/C).*

