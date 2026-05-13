# AQUASIGHT™ MMF — Test Suite

## Structure

```
tests/
  conftest.py           Shared fixtures (standard_layers, standard_water, standard_vessel)
  test_water.py         Water properties (density, viscosity vs Millero/Poisson)
  test_backwash.py      Expansion, u_mf, Ergun ΔP, collector check
  test_mechanical.py    ASME VIII-1 thickness, weight calculations
  test_media.py         Media database integrity, layer validation
  test_process.py       Filter loading, flow distribution by scenario
  test_economics.py     CAPEX, OPEX, CRF, carbon footprint
  test_integration.py   End-to-end compute_all() smoke test
  test_comparison.py    compare_designs / diff_value / metric matrix
  test_compare.py       engine.compare facade (aliases + severity + summary)
  test_project_db.py     SQLite project_db save/load, snapshots, scenarios
  test_logging.py        engine.logger file output + compute/project_io hooks
```

## Running tests

```bash
pytest tests/ -v                     # all tests, verbose
pytest tests/test_backwash.py -v     # one module
pytest tests/ -k "TestDensity"       # one class
pytest tests/ --cov=engine           # with coverage report
```

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
