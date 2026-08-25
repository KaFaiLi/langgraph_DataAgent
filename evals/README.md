# Adversarial evaluation suite

`case_02` through `case_10` are compact, evaluation-only fixtures. Each case
contains a `fixture.json` with source-backed facts and deterministic candidate
signals, plus a sealed `gold_manifest.json` describing expected findings,
contradictions, revisions, and omission rescue. The gold manifests are never
imported by production code or unit tests.

The offline harness reads only completed run artifacts:

```powershell
uv run python -m evals.adversarial_suite --runs-root .\local-eval-runs --output .\evals\reports\latest.json
```

Runs are expected at `local-eval-runs/<case_id>` (or can be supplied through
the Python `run_map` API). The runner does not invoke a provider, read raw
source files, open checkpoints, or require credentials. Generated bundles and
reports are ignored by `evals/.gitignore`.

The report includes finding precision, unsupported-pass rate, true-positive
preservation, contradiction recall, verifier rescue, omission rescue, revision
success, severity calibration, average verification rounds, adversarial tool
calls per finding, token totals by model tier, and telemetry latency.

Run the credential-free harness smoke check with:

```powershell
uv run python -m evals.self_check
```
