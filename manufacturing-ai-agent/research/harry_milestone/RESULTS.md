# Offline milestone results — November 2, 2026

Status: **offline implementation completed; live-model evaluation and human timing pending**.
No paid model request was made. The existing production database was used locally
through read-only connections. These results describe the offline research milestone. A subsequent local web
adapter is documented in the application README; it leaves the frozen benchmark
unchanged. Its tests and deployment checks are reported separately.

## What was verified

| Check | Actual result | Interpretation |
|---|---|---|
| Research tests | 37 passed | Tool math, strict scopes, unknown/zero, overnight, overlaps, ties, missing minutes, read-only, mock SDK orchestration and scoring |
| Existing enterprise tests | 111 passed | Existing backend behavior remains covered |
| Existing data regressions | 61 passed | Production/dashboard/abnormality/cloud/diagnostics/AI data tests |
| Existing trend-layout tests | 14 passed | Existing date/point/label layout logic |
| Total automated tests | **223 passed** | Deterministic/mocked tests, not LLM accuracy |
| Frozen hand-answer checks | **22/22** | 16 answerable A questions plus six B controls; expected arguments injected |
| Synthetic dashboard comparisons | **54/54 agree** | Same dataset, units, machine/shift/date filters |
| Real dashboard comparisons | **63/63 agree** | Existing user database; local read-only comparison |
| Independent real SQL checks | Passed | Separate production aggregate and event GROUP BY; no production/event join |
| Scripted end-to-end demonstration | Passed; explicitly mode=mock | Actual SDK tool binding and SQLite calculation, scripted decisions |
| Actual SDK HTTP serialization | Two offline transport tests passed | Correct Responses request shapes and no automatic retry on simulated 503; no external HTTP |
| Data/source protection | 84 original data files and 53 original Python files unchanged | Byte hashes checked, not only row counts; real SQLite integrity check is OK |
| Static checks | Ruff F checks and new-code formatting passed | No dependency installation |

Known benign test notices were the existing Streamlit bare-mode ScriptRunContext
warning and Node module-type warning. The first nullable-production test exposed
a TypeError in the reused snapshot path; the wrapper now fails explicitly on
malformed source data, and the test was rerun successfully. Failed tests were not
counted as passes. No existing shared calculation source was modified.

A final audit found that importing the existing backend initializes dotenv.
The calculation-only research baseline now suppresses that loader locally, with
an independent subprocess test that removes the inherited disable flag and
blocks actual file parsing. Full regression commands also set
`PYTHON_DOTENV_DISABLED=1`. Early baseline/regression runs did trigger the existing
initializer; no environment values were copied into reports or sent externally.
The original backend source is unchanged. The initial manifest is preserved as
`manifest.v1.0.json`; v1.1 records this offline safety correction and UTC timestamps,
with no live evaluation between versions. Final golden and dashboard checks were
rerun and their v1.1 reports retained separately.

## Independent examples

| Scope / measure | Fixture A | Fixture B |
|---|---|---|
| Jan 5–7 input mother rolls | plan 70, actual 56, difference −14 | unchanged |
| Record-level / net shortfall | 18 / 14 | unchanged |
| Known abnormality subtotal | 345 event-minutes | 495 event-minutes |
| Highest known recorded subtotal | FX1: 180 | FX2: 300 |
| Other ranked machines | FX2: 150 (partial), FX4: 15 | FX1: 180, FX4: 15 |

This deliberate change checks calculations and fixture sensitivity. It is not
proof that an untested model responds to changed data. FX5 remains unranked with
unknown minutes; FX8 has no event records. The tiny canonical source rows and
hand arithmetic are in `fixtures_source.json` and `QA.md`.

The development demo asks for FX1 input mother rolls on Jan 5–6. Scripted routing
invokes the actual function with both dates. SQLite returns plan 32, actual 29,
difference −3, record-level shortfall 5 and net shortfall 3. A scripted evidence
selection produces local factual sentences plus the full result and warnings.
Its output explicitly identifies the mock mode.

## Frozen experiment and reproducibility

`manifest.json` version 1.1 was written before any live request. It freezes the
20 questions (16 answerable, four clarification), six B controls, both sample DB
byte/logical hashes, hand oracle, source/prompt/tool schemas, shared calculation
files, Python/SQLite and installed SDK versions. Verification rejects a changed
input instead of silently accepting it. The manifest SHA-256 at delivery is:

`816f0e9c5258df40b228caa443e0a6815ebd4b06e939a2c0ecd3ed25dbaf8aa5`

The sample databases are `local_data/plan034-samples/sample_a.db` and `sample_b.db`.
They contain invented records only and remain excluded by existing Git rules.
The generator refuses to replace an existing file. Use fresh output filenames
when rerunning report commands; existing report outputs are also protected.

Actual commands run, from the repository root:

```bash
PYTHON_DOTENV_DISABLED=1 backend/.venv/bin/python -B -m pytest tests/research tests/enterprise -q -p no:cacheprovider
.venv/bin/python -B -m unittest test_production.py test_dashboard.py test_abnormality.py test_cloud_data.py test_production_diagnostics.py test_ai_production_data.py
(cd frontend && node --test tests/trend-layout.test.mjs)
backend/.venv/bin/ruff check --no-cache --select F research tests/research
backend/.venv/bin/python -B -m research.harry_milestone.evaluation --mode tools --data-dir local_data/plan034-samples --output local_data/plan034-tools-v1.1.json
backend/.venv/bin/python -B -m research.harry_milestone.evaluation --mode baseline --data-dir local_data/plan034-samples --output local_data/plan034-dashboard-v1.1.json
backend/.venv/bin/python -B -m research.harry_milestone.evaluation --mode baseline --real-db manufacturing.db --output local_data/plan034-real-dashboard-v1.1.json
```

The real-data demo commands in `README.md` were also executed with zero model
requests. Their complete outputs stay in ignored local files
`local_data/plan034-real-input-demo.json` and
`local_data/plan034-real-abnormality-demo.json`. No real source records or notes
are embedded in the public sample/Q&A. Real-data results disclose missing production dates instead of inventing production. Production and event coverage differ.

## Timing: service paths only

| Dataset | Median two-tool time | Median existing dashboard service time |
|---|---|---|
| A, 54 scopes | 0.385 ms | 0.624 ms |
| Real, 63 scopes | 0.618 ms | 1.269 ms |

These are local, warmed/small-data calculation-path measurements from one run.
They exclude model/network calls, UI actions and user interpretation. Shared
code agreement is not an independent truth oracle. No dashboard speedup or
research finding follows. Human timings and the dashboard-versus-live-agent
comparison remain **not measured**; `dashboard_timing.md` supplies the protocol.

## Proposed live experiment: not executed

- Candidate: `gpt-6-sol`, Responses/Standard, reasoning none, max 700 output
  tokens per request, no tracing/storage or automatic retries. Actual account
  model access is unverified. No different model will be substituted silently.
- Design: 20 A questions ×3, six B controls ×3 = 78 trials, at most two model
  requests per trial. The expected scripted paths contain 144 requests; the
  absolute configured limit is 156. There is no paid pilot result.
- Standard pricing checked on the [official model page](https://developers.openai.com/api/docs/models/gpt-6-sol):
  $2/M input and $10/M output. Assuming 234k–390k input and 39k–78k output across
  the experiment, estimated usage cost is **$0.86–$1.56**. These are assumptions,
  not token measurements; no tokenizer was added or account balance inspected.
- Offline byte-based admission sizing of the planned paths gives **$2.847168**
  if every request consumes its full reservation. The local sizing report is
  `local_data/plan034-budget-estimate.json`; gold arguments were injected for
  sizing only and no model client was constructed. Thus the earlier $2 ceiling
  may stop early. A **$3 process ceiling** is proposed for separate approval;
  it does not guarantee all trials complete or control unrelated account spend.
- Failed/timeout/rejected trials are retained; exact selection, filters, numeric
  answers, restricted evidence consistency and clarification are scored
  separately. Conditional numerical accuracy is also reported. Unattempted
  trials after a budget stop are disclosed. Synthetic-only JSONL traces are kept.

## Pending measurements and limits

| Item | Status |
|---|---|
| Live tool-selection/filter/numerical accuracy | Not evaluated |
| Live restricted-evidence consistency | Not evaluated |
| Live API usage/cost/latency | Not measured; actual model requests 0 |
| Manual explanation review | Not reviewed |
| Human dashboard task time | Not measured |
| Browser visual acceptance | Not performed; no UI change claimed |
| Unrestricted LLM explanation quality | Not implemented/evaluated; sentences are local |
| GitHub publication / deployment | Not performed |

The independent CLI reproduces this frozen milestone. A subsequent local website
view reuses its deterministic tools; the general chat remains independent. Recorded event-minutes can overlap and are not net downtime;
missing values, Open status and source-date semantics remain explicit. No causal
bottleneck finding or inventory/order forecast is claimed. This small designed
20-question pilot requires independent review and unseen questions before any
claim about general model reliability.
