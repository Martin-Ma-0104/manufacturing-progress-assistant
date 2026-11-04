# Manufacturing AI Agent: Harry Yang milestone

This is a small, reproducible engineering pilot for two read-only questions:
planned versus actual **input mother rolls**, and machine ranking by known
**recorded abnormality event-minutes**. It reuses the production application's
SQLite schemas, read-only snapshot adapter, production diagnostics and abnormality
functions. The frozen research algorithms and general chat remain independent. The current
Next.js AI page also provides a thin local analysis view over these same tools;
see the application README for its filters and API. It makes no model request.

The user's existing database is supported for local read-only demonstrations and
dashboard agreement checks. Entirely invented A/B databases provide independently
checkable answers and changed-ranking controls. No real business records are copied
into the sample data or frozen questions.

## Architecture and safety

```text
Question + approved scope + fixed business clock
  -> GPT-6 Sol via existing OpenAI Agents SDK
     -> one of two validated read-only tools, OR a clarification code
  -> Python/SQLite calculation (mode=ro, query_only, parameterized filters)
  -> compact local evidence
  -> LLM selects evidence IDs
  -> local factual sentences + full numerical result + mandatory warnings
```

The model cannot select database paths, execute SQL, write production records or
access the application's other tools. Dates, machines and shifts cannot exceed
the approved scope. A question permits at most one business-tool invocation and
two model requests. Storage/tracing and automatic client retries are disabled.
The API key is read from the process environment only after explicit live permission.
Real aggregates have an additional permission gate; the frozen live benchmark uses
synthetic data only. No `.env` or Streamlit secrets file is copied or loaded by the research entry points.
The dashboard baseline locally suppresses the existing backend dotenv initializer;
regression commands also disable dotenv explicitly.

Explanations use **LLM-selected fact IDs and locally worded sentences**, rather
than unconstrained model prose. A missing/unknown/duplicate fact ID is a failed
answer. All result rows and warnings remain visible regardless of fact ordering.
Clarification text is also rendered locally from validated target codes. This
design tests routing, arguments and evidence selection; it does **not** establish
the model's ability to generate unrestricted factual explanations. Manual review
still checks relevance and limitations.

## Data dictionary and calculations

| Existing field | Meaning | Unit |
|---|---|---|
| `planned_rolls` | Planned mother-roll input | input mother rolls |
| `input_rolls` | Actual mother-roll input | input mother rolls |
| `qualified_rolls` | Qualified finished rolls | finished rolls |
| `actual_output_m2` | Actual output area | m² |
| `qualified_output_m2` | Qualified output area | m² |
| `reported_minutes` | Original reported abnormality duration | event-minutes |
| `started_at`, `ended_at` | Explicit local timestamps, including overnight dates | local date/time |
| `status` | Open/Closed/Unknown event resolution | not machine state |

The exact SDK function schemas are in `tool_definitions.json`.

`compare_production_inputs(start_date, end_date, machine_id=null, shift=All)`:

- Planned/actual input are summed only from matching production observations.
- Difference = actual − planned.
- Shortfall = sum of `max(planned_i − actual_i, 0)` per production record.
- Net period shortfall = `max(total planned − total actual, 0)`.
- Excess is summed separately. For 10/8 and 10/12, net shortfall is 0 but
  record-level shortfall is 2. These are input gaps, not finished-output losses.
- Missing observations return unavailable; an explicit zero remains zero.
  Nullable production counts are not permitted by the established schema;
  malformed legacy values fail explicitly instead of being coerced to zero.

`rank_abnormality_duration(start_date, end_date, machine_id=null, shift=All)`:

- Primary metric is the sum of **known source `reported_minutes`** per machine.
  It matches the dashboard's event-minute convention.
- Inclusive ranges use the recorded `production_date`; an overnight event is
  included once according to that date. This is not clock-window clipping.
- Overlapping events remain separate additive recorded events; overlap counts
  and incomplete timestamps are disclosed. Do not interpret sums as union time.
- A known reported duration remains usable when the end is missing, with a warning.
  Missing minutes remain missing even if a timestamp interval can be calculated.
- Open events are not extended to now. Source-vs-interval discrepancies are flagged.
- Partial totals are labelled partial. All-unknown/no-event machines are unranked.
  Explicit zero is rankable. Ties share competition ranks such as 1,1,3; machine
  ID ordering only makes display deterministic.
- This is not measured net downtime, utilization, the dashboard's assumption-based
  12h/2h runtime estimate, or evidence of a production-loss cause.

Both tools use an inclusive range of at most 30 dates and an optional Day/Night
filter. Unknown-shift events appear only in All. Production and events are read
and aggregated separately, avoiding many-to-many join multiplication.

## Synthetic data and hand checks

`fixtures_source.json` and `fixtures.py` define **8 production observations and
10 events** across fictitious FX identifiers. `QA.md` contains the full 20-row
question/argument/answer/explanation table; `evaluation_cases.json` is its
machine-readable equivalent. The oracle is hand-authored and is not generated
from tool outputs.

Primary fixture A, January 5–7:

- Planned inputs = 70; actual = 56; difference = −14 mother rolls.
- Record-level shortfall = 18; excess = 4; net shortfall = 14.
- Known recorded abnormality totals: FX1 = 180, FX2 = 150 (partial), FX4 = 15.
  FX5 has unknown duration; FX8 has no event records.
- January 5 produces a 120/120/0 tie test with ranks 1/1/3.

Fixture B changes only E4 and E5. FX2's known subtotal becomes 300, ahead of
FX1's 180; the primary input comparison is unchanged. Six repeated questions
verify the ranking changes and unchanged controls. The fixed evaluation clock
is January 12, 2026 in America/New_York. “Last week” means January 5–11.

## Reproduce the offline work

Run commands from the repository root using the existing Python 3.12 environment.
No new dependencies are needed.

```bash
# Create new sample databases. Existing files are never overwritten.
backend/.venv/bin/python -B -m research.harry_milestone.fixtures --output local_data/plan034-samples

# Check tools, orchestration with fake SDK responses, scoring, and data protection.
PYTHON_DOTENV_DISABLED=1 backend/.venv/bin/python -B -m pytest tests/research tests/enterprise -q -p no:cacheprovider

# Verify frozen inputs, then check deterministic tools against hand answers.
backend/.venv/bin/python -B -m research.harry_milestone.evaluation --mode tools --data-dir local_data/plan034-samples --output local_data/plan034-tools.json

# A development example with scripted selection and real local SQL calculation.
# The output explicitly says mode=mock; this is not a live-model result.
backend/.venv/bin/python -B -m research.harry_milestone.demo --sample-db local_data/plan034-samples/sample_a.db --start 2026-01-01 --end 2026-01-30 --mock

# Compare the existing dashboard's calculation path on exactly the same fixture.
backend/.venv/bin/python -B -m research.harry_milestone.evaluation --mode baseline --data-dir local_data/plan034-samples --output local_data/plan034-dashboard.json
```

Generated `*.db` files and `local_data/` outputs retain existing Git exclusions.
The sample binaries are deliverable locally; source records and the generator
make them reproducible. The current v1.1 manifest preserves the earlier freeze as `manifest.v1.0.json`.
It includes an offline correction isolating backend dotenv initialization.
The frozen manifest stores byte and logical data hashes,
source/prompt/schema hashes, model/configuration and installed SDK versions.
Verify it before live tests. If a runtime produces different binary hashes,
inspect the logical data and record a new version; do not silently overwrite the
frozen experiment. `case_design.py` is an authoring utility and must not be run
to change an already evaluated question set.

## Use the existing database locally

Supply the path explicitly; there is no production fallback and no database copy:

```bash
backend/.venv/bin/python -B -m research.harry_milestone.demo --real-db manufacturing.db --start 2026-01-05 --end 2026-01-07 --tool compare_production_inputs
backend/.venv/bin/python -B -m research.harry_milestone.demo --real-db manufacturing.db --start 2026-01-05 --end 2026-01-07 --tool rank_abnormality_duration
backend/.venv/bin/python -B -m research.harry_milestone.evaluation --mode baseline --real-db manufacturing.db --output local_data/plan034-real-dashboard.json
```

These commands make **zero model requests**. Keep real aggregate reports in
ignored local storage. The real database, source notes, identifiers, credentials
and private reports must not be committed or included in the advisor's public demo.
Existing production services are not repointed or restarted by these commands.

## Evaluation protocol

The frozen set contains 16 answerable cases and four clarification cases. Before
live evaluation, separately record the exact model/configuration, date, source
hashes, machine catalogue, request limits and budget. Gold answers and case IDs
never enter the model-facing request. Development mock examples are separate.

The proposed live run is 20 primary cases ×3 plus six B controls ×3 = 78 trials.
The runner records selection and explanation stages, tool trace, validated
arguments, result, evidence IDs, warnings, elapsed time, token usage and cost.
Failed/rejected/timeout attempts stay in the denominator. Missing attempts after
a budget stop are shown explicitly. Metrics are reported separately:

| Metric | Scoring |
|---|---|
| Tool selection | Correct business tool on answerable cases |
| Arguments/filters | Exact normalized dates, machine and shift |
| Numerical/rank accuracy | Integer mother rolls and explicit expected rankings; minute tolerance 1e-6 |
| Explanation consistency | Valid required evidence IDs and unchanged warnings; locally rendered wording |
| Clarification | No tool call plus correct reason and missing-information target |
| End-to-end | All applicable stages successful |
| Time | Total and stage latency, with failures retained |

Also report numerical accuracy conditional on correct arguments to distinguish
calculation from routing failures. Manual review checks whether the clarification
or selected evidence addresses the question and clearly communicates partial
data, units and absence of causal evidence. Record each check as pass/fail with a
short reason. Unperformed manual review stays `not reviewed`.

`tools_only` reports inject expected arguments to check calculations. Their tool
selection/argument/explanation accuracy fields are unavailable. Mocked responses
test wiring only. Neither constitutes live LLM accuracy.

Dashboard comparison runs its existing Python calculation path on the same
database and filters, without changing server configuration. It reports numeric
agreement and service-path timing. Shared-code agreement is not an independent
truth oracle; the small hand calculations are checked separately. It is also not
a human task-time study. The manual protocol is in `dashboard_timing.md`; do not
invent mouse/keyboard or human completion times when no session was observed.

## Model, permissions and estimated cost

The research candidate is **`gpt-6-sol`**, Responses API, Standard processing,
`reasoning.effort=none`. The general application's model is unchanged. The
[official model page](https://developers.openai.com/api/docs/models/gpt-6-sol)
documents function calling, structured outputs and standard prices of $2 per
million input tokens and $10 per million output tokens (checked November 2, 2026).
Only the model alias is documented; there is no invented immutable dated snapshot.
The requested model is recorded; returned-model metadata is unavailable in this
SDK adapter and is reported as null, a reproducibility limitation.

For 78 trials, assuming 3,000–5,000 combined input tokens and 500–1,000 combined
output tokens per trial, the estimate is $0.86–$1.56. This is an assumption, not
measured usage or an account entitlement. Extra pilots, retries, reasoning,
caching, endpoint charges or changed rates alter cost. No cache discount is assumed.

Live execution requires separate approval. Merely configuring a key does not
authorize a request. After approval, the CLI requires both `--allow-paid` and
`--budget-usd`; the key must be in `OPENAI_API_KEY`, never in arguments or logs.
The local budget ledger reserves a conservative byte-based input allowance plus
protocol margin and output cap before each request; unknown usage consumes its
whole reservation. It can stop a run before all planned trials. It controls this
process only, not unrelated account spending. Never silently increase the budget
or substitute a different model after an access/limit failure.

Offline request-admission sizing across the 26 A/B question shapes (three repeats)
requires approximately **$2.85** if every request consumes its full conservative
reservation. This is a byte-based bound, not tokenizer-measured or billed usage.
The previous $2 suggestion might stop early; a **$3 local ceiling** is now proposed
for separate approval. The runner still stops at that ceiling and makes no promise
of completing all trials. No paid calls have been made.

```bash
# AFTER separate live-run approval only. This has NOT been executed for delivery.
backend/.venv/bin/python -B -m research.harry_milestone.evaluation --mode live --data-dir local_data/plan034-samples --output local_data/plan034-live-run-001 --allow-paid --budget-usd 3
```

## Status and limits

See `RESULTS.md` for the actual offline checks and explicitly pending live/manual
measurements. This is an engineering pilot with 20 designed questions, not a
held-out generalization benchmark. Small-sample correctness, synthetic reversal
controls and mocked tests do not establish production reliability, a bottleneck
cause, model superiority or dashboard speedup. Independent review and larger
unseen workloads are future work. No paid model evaluation, cloud publication,
application deployment, or browser visual acceptance is implied by these files.

The current local web adapter is `backend/research.py` plus `frontend/components/research-analysis.tsx`. It leaves the frozen benchmark sources unchanged.


The current production website has been simplified to Dashboard, Production and
AI analysis. Its optional general chat exposes only production and recorded
abnormality tools. The independent frozen research harness, two tool algorithms,
QA set and version 1.1 manifest remain unchanged.
