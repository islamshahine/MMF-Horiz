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

---

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

- Biofouling / SDI prediction from first principles (fouling module is empirical advisory).
- Automatic global optimiser (grid MVP + manual sweeps only).
- 3D CFD, lateral collector hydraulics, or nozzle manufacturer CFD.
- Live operations / DCS integration (24 h Gantt is schematic duty, not optimised scheduling).

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
    → pump performance package
    → weights, lining, operating weight, saddle design
    → economics + lifecycle financials
    → assessment (severity, robustness, narrative drivers)
    → environment structural (wind/snow hooks)
```

**Dependency rule:** Later stages consume SI dict keys from earlier stages; tabs never re-implement physics.

### 2.2 Caching & performance

- `ui/compute_cache.py` — `st.cache_data` on `compute_all` when inputs hash unchanged.
- Severity classifiers are **module-level functions** (pickle-safe for cache).
- Sensitivity / optimisation call full `compute_all` per perturbation — expensive by design.

### 2.3 Validation strategy

- `engine/validators.py` — structural checks on required keys, positive flows, layer sanity.
- Invalid inputs → compute still runs on **reference fallback** so UI does not blank; banners show errors.
- Validation messages quote **SI** magnitudes (known UX gap for imperial users).

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

13 metrics with % difference and 5% (or metric-specific) significance threshold:

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

- Fouling engine not wired to “Apply” in main flow (only suggestion).
- No wizard / design basis document import (JSON only).
- Limited reverse-solve (“I need LCOW < X → suggest N”).
- Layer threshold widgets not fully round-tripped in project JSON.
- Imperial validation messages use `format_value` when `unit_system=imperial` (geometry errors); Compare B widgets transpose on unit toggle (`ui/compare_units.py`).

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
| 💰 Economics | “What does it cost and emit? Lifecycle cash?” |
| 🎯 Assessment | “Is it safe? What if we lose a filter? What moves NPV?” |
| 📄 Report | “Give me a file for the client.” |
| ⚖️ Compare | “Is B better than A on 13 metrics + incremental NPV?” |

### 7.2 Display rules

- **`computed` stays SI** — never format inside engine.
- **`fmt(si, quantity)`** — human strings in tables/metrics.
- **`dv(si, quantity)`** — numeric values for charts/sliders.
- **`ulbl(quantity)`** — column headers follow unit toggle.
- **Specialised helpers** — `pressure_drop_layers_display_frames`, `fmt_bar_mwc`, `fmt_si_range` for benchmarks.

### 7.3 Progressive disclosure

- Expander for lifecycle financial, tornado, media intelligence, n_filters sweep.
- Status badges in input column — traffic-light summary without opening tabs.
- Validation banners — errors before tabs when inputs invalid.

### 7.4 Content ideas (richer future)

| Idea | Value |
|------|--------|
| **Design basis panel** | Single page: assumptions, limits, codes cited |
| **Traceability** | Click ΔP row → show Ergun term breakdown |
| **Uncertainty bands** | Low/avg/high as shaded regions on charts |
| **Operating envelope chart** | LV vs EBCT feasibility map per scenario |
| **Media life narrative** | Link cycle duration → replacement interval → OPEX |
| **Client mode** | Hide calibration knobs; show only outcomes |
| **Engineer mode** | Expose α, mal-distribution, raw SI in tooltips |

---

## 8. Enhancement compass (for outside-the-box thinking)

Use these prompts with AI or workshops. Each axis is independent — mix and match.

### 8.1 Platform / product ideas

| Direction | Description |
|-----------|-------------|
| **Design library** | SQLite UI for projects, snapshots, named scenarios (engine exists). |
| **Multi-case workspace** | **MVP (≤4 cases):** `engine/compare_workspace.py` + Compare tab canvas; richer 3–10-case UI still aspirational. |
| **Requirements traceability** | Link each input to P&ID tag / DBR line item. |
| **Collaboration** | Comment threads on assessment drivers; revision diff on JSON. |
| **API-first clients** | ERP / estimating tools POST designs; return PDF + metrics only. |
| **Digital twin lite** | Import actual LV, ΔP, BW times → recalibrate α and solid loading. |
| **Regulatory packs** | Pre-built report sections per client (ACWA, SWCC, EU taxonomy). |

### 8.2 Core engineering ideas (deeper physics)

| Direction | Description |
|-----------|-------------|
| **2D / 1D collector model** | Lateral ΔP, orifice discharge → maldistribution factor from physics. |
| **Biofouling module** | Algae/bacterial layer growth tied to temperature, chlorine, run time. |
| **GAC adsorption** | Breakthrough curves for DOC/TOC proxy; mode-dependent EBCT. |
| **Air scour optimiser** | **MVP delivered:** min air-equivalent rate for target expansion; thermo blower kW on `air_scour_solve`. **Still open:** VFD law, real blower maps, multi-objective vs water scour. |
| **Dynamic BW scheduler** | MILP: minimise peak concurrent BW given train rules. |
| **CFD export** | **Delivered (MVP)** — `collector_cfd_export.py` JSON + orifice CSV; `normalize_cfd_export_format()` maps legacy UI labels (e.g. display strings) to internal keys. |
| **Vertical vessel path** | Second geometry kernel (major fork — high effort). |

### 8.3 Content / UX ideas

| Direction | Description |
|-----------|-------------|
| **Guided workflows** | “New SWRO train” wizard: flow → water → media template → auto N. |
| **Explain this number** | LLM tooltip grounded in `computed` JSON + this doc. |
| **Risk storytelling** | One-page executive summary auto from `overall_risk` + drivers. |
| **Benchmark positioning** | Radar chart vs `econ_bench` bands per region/year. |
| **Training mode** | Reference case with locked inputs + quizzes on LV/EBCT. |

### 8.4 Input ideas

| Direction | Description |
|-----------|-------------|
| **Import from Excel template** | Column mapping to `inputs` dict. |
| **P&ID OCR / parser** | Extract N filters, DN, design pressure (aspirational). |
| **Sliders with constraints** | Drag LV → show immediate severity colour on layer sketch. |
| **Fouling panel** | SDI/MFI/TSS → apply loading + show confidence interval. |
| **Unit-aware validation** | Errors in display units. |
| **Inverse solve** | Target LCOW or ΔP → suggest `n_filters` or `nominal_id`. |

### 8.5 Display ideas

| Direction | Description |
|-----------|-------------|
| **Vessel sketch interactivity** | Click layer in drawing → jump to media table row. |
| **Scenario slider** | Animate N → N−1 → N−2 LV/EBCT in one chart. |
| **Sankey: energy** | kWh split feed / BW / blower / parasitic. |
| **Sankey: mass** | TSS capture per layer → cake → BW waste. |
| **Mobile summary** | Read-only dashboard for site visits. |
| **Imperial-native reports** | PDF entirely in ft/psi/gpm without SI footnotes. |

### 8.6 AI-assisted development patterns

When asking Claude/Cursor to extend the platform:

1. State whether the change is **engine**, **UI boundary**, or **display-only**.
2. Specify if JSON/API must remain SI-compatible.
3. Ask for a **test** in `test_units.py` or `test_integration.py` with numeric assertion.
4. Reference the equation section above — avoid duplicate formulas in UI.
5. For new inputs: require `INPUT_QUANTITY_MAP` + widget map entry in same PR.

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

### 11.1 What the external roadmap gets right

- **Collector hydraulics** is the largest *physics gap* vs marketing claims (“full hydraulic design”).
- **`maldistribution_factor` is a calibration knob**, not a model output — replacing it with a derived value (when data exists) is high value.
- **Cycle uncertainty** should be deterministic envelopes first, not Monte Carlo.
- **Fouling must stay advisory** — engine exists (`fouling.py`); UX is the gap.
- **No architecture rewrite** — extend `compute_all`, add `computed` keys, test engine modules.

### 11.2 What to correct or defer

| External claim | Repo reality |
|----------------|--------------|
| Doc name `MODELS_AND_LOGIC.md` | Use **`AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md`** |
| Collector “no hydraulic model” | **Stale** — **1A/1B** in `collector_hydraulics.py` (1D header/lateral); still **no CFD / 3D manifold** |
| Fouling “not wired” | **Partially wired** — sidebar expander + Apply M_max; not a guided workflow |
| Optimisation “future” | **`optimisation.py` + tests exist** — missing Streamlit UX only |
| 1B before 1A validated | **Risky** — iterative manifold solvers are where “magic” appears; do **1A → 1C → 1B** |
| Monte Carlo lite in Phase 2 | **Defer** until 2A is used in production; runtime × Streamlit reruns hurts UX |
| “HIGH” dynamic BW scheduler | **High value, high false-precision risk** — after timeline inputs are stable |

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
| **Cmp+** | Multi-case compare (≤4 designs) | **Done (MVP)** — `engine/compare_workspace.py`, Compare tab; CSV-friendly still A/B-centric in places |
| **Sched** | Dynamic BW scheduler | **Done (MVP)** — multi-day horizon + `optimized_trains`; MILP/DCS out of scope |

#### Phase 3 — Platform scale (10+ weeks)

- Dynamic BW scheduler (train MILP or heuristic — label as *scheduling aid*).
- Multi-design workspace (SQLite UI + `project_db` — engine ready).
- ~~Uncertainty → economics bands~~ **Done (2026-05):** `engine/uncertainty_economics.py` → `cycle_economics` on `compute_all`.
- Media lifecycle degradation curves.
- Monte Carlo lite (**optional**, behind checkbox).

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

### 11.7 Secondary pipeline — honest priority ranks

| Item | Value | Effort | Rank |
|------|-------|--------|------|
| Optimisation UI + Pareto rank | High | Medium | **P1** (with Phase 1) |
| Design basis / traceability | High (enterprise) | Medium | **P1–2** |
| Dynamic BW scheduler | High | High | **P2–3** |
| Multi-design (>2) | Medium | Medium | **P2** — **MVP delivered** (`compare_workspace`, ≤4); full named library UI backlog |
| Uncertainty → economics | Medium | Medium | **P3** |
| Media ageing curves | Medium | High | **P3** |

### 11.8 Implementation checklist (every feature)

1. New logic in `engine/*.py` only.
2. Register outputs on `computed`; SI only.
3. `tests/test_<module>.py` with numeric fixtures.
4. UI: `fmt`/`dv`/`ulbl`; one tab owner.
5. Update this doc §3 equation entry.
6. API: `compute_all` pickling — no lambdas in `computed`.

### 11.9 Prompt to use with AI assistants

```text
You are extending AQUASIGHT MMF. Read AQUASIGHT_MMF_PROJECT.md and
AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md §11.

Implement [FEATURE] following Phase [N]. Do not duplicate Ergun/Ruth in UI.
Propose: engine module, computed keys, inputs added, tests, tab placement,
assumptions, limits, runtime (ms per compute_all call).
```

---

*Document version: 2026-05 — includes §11 reconciled development priorities.*

