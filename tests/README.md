# AQUASIGHT™ MMF — Test Suite

## Structure

```
tests/
  conftest.py                    Shared fixtures (standard_layers, standard_water, standard_vessel)
  test_water.py                  Water properties (density, viscosity vs Millero/Poisson)
  test_backwash.py               Expansion, u_mf, Ergun ΔP, collector check, air scour auto
  test_mechanical.py             ASME VIII-1 thickness, weight calculations
  test_media.py                  Media database integrity, layer validation
  test_process.py                Filter loading, flow distribution by scenario
  test_economics.py              CAPEX, OPEX, CRF, carbon footprint
  test_integration.py            End-to-end compute_all() smoke test
  test_comparison.py             compare_designs / diff_value / metric matrix
  test_compare.py                engine.compare facade (aliases + severity + summary)
  test_compare_workspace.py      Multi-case library (20), selection (12), pagination slice
  test_compare_units.py          Compare B SI contract + unit toggle
  test_project_db.py             SQLite project_db save/load, snapshots, scenarios
  test_project_revisions.py      B3 cases/revisions, report hash, migration, diff
  test_uncertainty_charts.py     B4 cycle_uncertainty_charts / dp envelope payloads
  test_monte_carlo_lite.py       C1 optional cycle-duration sampling
  test_cfd_import.py             C2 lite external CFD CSV vs 1D orifice network
  test_digital_twin_lite.py      C4 plant telemetry → α calibration suggestion
  test_project_io.py             JSON round-trip, imperial widget map
  test_input_reconcile.py        Collapsed layout: pump widgets → SI before compute
  test_logging.py                engine.logger file output + hooks
  test_fouling.py                Fouling correlations (SDI/TSS/LV)
  test_fouling_workflow.py       5-step workflow helpers + assessment
  test_api.py                    FastAPI /compute + /health + OpenAPI
  test_financial_economics.py    Lifecycle cash flow, NPV/IRR, depreciation
  test_optimisation.py           constraint_check + optimise_design grid
  test_design_basis.py           Design basis v1.1 — ASM/TRC traceability
  test_explainability.py         METRIC_REGISTRY resolution
  test_lifecycle_degradation.py  Sawtooth degradation curves
  test_nozzle_plate_catalogue.py Pressurized catalogue (9 products), legacy ID removal
  test_nozzle_system.py          Underdrain coherence advisory
  test_strainer_materials.py     Salinity-driven strainer defaults
  test_ui_helpers.py             Display helpers (clogging % Arrow-safe strings)
  test_collector_nozzle_plate.py Nozzle plate triangular stagger layout (layout_revision 6)
  test_nozzle_distribution.py   Density-driven N, pitch, full-plate coverage, stagger
  test_collector_hydraulics.py   1D collector header/lateral
  test_distribution_convergence.py  Lateral distribution solver
  test_collector_geometry.py     Lateral reach / screening
  test_collector_manifold.py     Dual-end + CFD export normalize
  test_collector_benchmarks.py   Hand-calc regression pack
  test_collector_envelope.py       Deterministic BW-flow sweep (1D collector)
  test_collector_envelope_cache.py  On-demand sweep kwargs + fingerprint (P5.5)
  test_collector_staged_orifices.py  Staged orifice advisory
  test_bw_scheduler.py           BW scheduler v2 (stream-aware, peak windows) [@pytest.mark.slow]
  test_bw_scheduler_v3.py        BW scheduler v3 (tariff + maintenance blackouts)
  test_bw_scheduler_milp.py      C5 MILP-lite BW schedule export
  test_bw_stagger_compare.py     Cached stagger comparison (duty-chart UX)
  test_media_pricing.py          Region factors (Egypt, Middle East, GCC, …)
  test_equipment_tag_import.py   C3 lite equipment tag CSV import
  test_operating_envelope.py     LV × EBCT feasibility grid (Phase 4 A2)
  test_design_targets.py         Design-to-target caps + grid search (Phase 4 A3)
  test_spatial_distribution.py   Voronoi nozzle loading map (BW + filtration Q basis)
  test_blower_maps.py            Blower Q–ΔP maps, VFD affinity, vs adiabatic (Phase 4 B1)
  test_blower_oem_catalog.py     OEM ROBOX/GRBS motor kW catalog (realistic nameplate)
  test_uncertainty.py            Cycle uncertainty envelopes
  test_uncertainty_economics.py  LCOW band from cycle spread
  test_sensitivity.py            OAT tornado narrative
  test_units.py                  Unit conversion catalogue
  test_validation.py             validators + compute fallback
  test_report_drawing_smoke.py   PDF/Word smoke
  test_pump_performance.py       Pump duty package
  test_pump_datasheet_export.py  RFQ export bundles
```

## Running tests

```bash
pytest tests/ -v                     # all tests, verbose
pytest tests/test_lifecycle_degradation.py -v
pytest tests/test_compare_workspace.py -v   # includes compute_all — slower
pytest tests/ -k "not compare_workspace"    # skip slow multi-compute cases
pytest tests/ -m "not slow"               # same as GitHub Actions CI (skips test_bw_scheduler.py)
pytest tests/ --cov=engine             # coverage on engine package
```

**Note:** `test_compare_workspace.py` and some integration tests call `compute_all()` multiple times and may take tens of seconds.

**CI:** `.github/workflows/ci.yml` runs `pytest -m "not slow"` on push/PR. The multi-day timeline suite (`test_bw_scheduler.py`) is marked `@pytest.mark.slow` (~25 min); run locally or via **workflow_dispatch** full job.

## Reference values

All expected values are derived from:

1. **Hand calculations** documented in each test docstring
2. **Published correlations**: Wen & Yu (1966) u_mf, Richardson-Zaki expansion,
   Ergun (1952) pressure drop, ASME Section VIII Division 1 UG-27
3. **Literature**: Millero & Poisson (1981) seawater density,
   Korson et al. (1969) water viscosity

## Tolerance policy

| Type | Tolerance | Rationale |
|------|-----------|-----------|
| Published correlation | `rel=0.02` (2%) | Curve-fit uncertainty |
| Exact formula | `rel=0.001` (0.1%) | Rounding only |
| Integer result | `==` exact | Counts, indices |
| Monotonicity | `>` / `<` | Direction only |

## Adding tests

- Never mock engine functions — test real calculations
- Document the hand calculation in the test docstring
- Use `pytest.approx()` for all floating-point comparisons
- Keep each test focused on a single physical assertion
- New `computed` keys: add smoke coverage in `test_integration.py` when practical

## Related documentation

| File | Role |
|------|------|
| `AQUASIGHT_MMF_PROJECT.md` | Architecture, file map, `inputs` / `computed` contracts; **§G What to do next** |
| `AQUASIGHT_MMF_MODELS_AND_STRATEGIES.md` | Equations, models, enhancement compass; **§12 What to do next** |

## What to do next (2026-05-17)

| # | Action | Status |
|---|--------|--------|
| 1 | Nozzle/BW smoke after layout or scheduler edits | **Baseline passed** — `pytest tests/test_nozzle_distribution.py tests/test_collector_nozzle_plate.py tests/test_media_pricing.py tests/test_spatial_distribution.py -q` (24 passed, 2026-05-17) |
| 2 | Full CI locally (matches GitHub Actions) | `pytest tests/ -m "not slow"` |
| 3 | Slow BW timeline suite (optional) | `pytest tests/test_bw_scheduler.py` (~25 min, `@pytest.mark.slow`) |
| 4 | New test module | Add to structure list above + row in **§12** / **§G** of both MD files |

**Release:** sprint shipped on `main` as **`ad49e3d`** (triangular nozzles, BW duty cache, Tier B/C lite, CI).
