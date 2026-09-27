# Development Guide

## Environment

Current development environment:

```text
Python: 3.14.2
Database: SQLite
ORM: SQLAlchemy 2.x
Validation: Pydantic 2.x
Testing: pytest
```

Project virtual environment:

```text
.venv
```

Activate it from the project root:

```bash
source .venv/bin/activate
```

Verify Python:

```bash
which python
python --version
```

The Python executable should come from the project's `.venv`.

---

## Package Management

Always install packages using:

```bash
python -m pip install <package>
```

Do not use bare:

```bash
pip install <package>
```

This ensures packages are installed into the Python environment currently being used by the project.

---

## Running Tests

Run the complete test suite from the project root:

```bash
python -m pytest
```

Current expected result:

```text
152 passed
```

The exact execution time may vary.

Tests must pass before considering a meaningful implementation change complete.

---

## Test Isolation

Automated tests must never write to:

```text
fitness.db
```

Tests use isolated in-memory SQLite databases.

Current test files:

```text
tests/test_database.py
tests/test_tools.py
```

Tool tests replace the application's normal `SessionLocal` with a test session.

The tool test database is reset between tests.

When adding new tests, preserve this isolation.

Never point test configuration at the live fitness database.

---

## Live Database

The development database is:

```text
fitness.db
```

It contains existing development data.

Some older records were created during earlier development before complete test isolation was introduced.

Do not delete, rewrite, or migrate existing data without explicit consideration of data preservation.

Schema changes should include an intentional migration strategy.

---

## Running the Fitness Context

Generate the current compact fitness context with:

```bash
python -m agent.context
```

The command must output valid JSON.

Validate the output with:

```bash
python -m agent.context | python -m json.tool > /dev/null && echo "valid JSON"
```

Expected:

```text
valid JSON
```

## Natural-Language Ingestion Development

The provider-neutral orchestration entry point is:

```python
ingest_fitness_message(raw_text, interpreter, reference=None)
```

Tests should use `StaticInterpreter` or another deterministic implementation of
`FitnessInterpreter`; they must not require network access.

The optional production adapters use the official provider SDKs:

```bash
python -m pip install -r requirements.txt
export OPENAI_API_KEY="..."
# Optional; defaults to gpt-5.4-mini
export OPENAI_MODEL="gpt-5.4-mini"
python -m agent.ingestion "Walked 9000 steps today" --openai

export GEMINI_API_KEY="..."
# Optional; defaults to gemini-3.5-flash-lite
export GEMINI_MODEL="gemini-3.5-flash-lite"
python -m agent.ingestion "Walked 9000 steps today" --gemini
```

`OpenAIFitnessInterpreter` uses Responses API Structured Outputs derived from
`InterpretationResult`, sends `store=False`, and performs no model tool calls.
`GeminiFitnessInterpreter` uses `google-genai`, `generate_content`, and a native
JSON response schema derived from the same Pydantic contract. Gemini supports
only a subset of JSON Schema, so the adapter recursively removes unsupported
value-constraint keywords from its provider-facing schema. The original
`InterpretationResult` model always revalidates the returned JSON and remains
the authoritative validation boundary; provider schema reduction does not
relax application validation. The stable Gemini default is
selected for inexpensive extraction, structured-output support, and free-tier
availability. Provider selection is explicit; no fallback occurs.
Never put credentials in source, configuration files, logs, or test fixtures.
Normal tests inject fake clients and make no live OpenAI or Gemini requests.

Coaching evaluation is a separate, explicitly invoked workflow using synthetic
contexts in `evals/coaching_cases.json`. It distinguishes provider errors,
structural failures, grounding failures, and coaching-quality expectation
failures. The evaluator does not write `fitness.db`; tests use fake coaches and
make no provider calls. A future live run can be invoked with
`python -m evals.run_coaching_eval --provider gemini --limit 1`.

The Gemini coaching adapter is likewise tested with a fake SDK client only.
Production usage must call `generate_grounded_coaching(context,
GeminiFitnessCoach(...))`; a schema-valid provider response is not approved
until deterministic grounding succeeds. No live coaching API call is made by
pytest.

Gemini coaching instructions distinguish general logging guidance from
adherence-dependent recommendations: general guidance never requests an
adherence permission or metric. They also describe food-log presence versus
nutrient availability and logged-session/step observations without
extrapolation. These are provider instructions, not a replacement for
deterministic grounding.

## Live Interpreter Evaluations

Extraction quality must be evaluated before the model is trusted as a
fitness-data ingestion source. The version-controlled cases live in:

```text
evals/fitness_interpreter_cases.json
```

The evaluator calls the selected interpreter directly. It may make live
provider requests, but it does not invoke ingestion and therefore creates no raw
events, structured records, or changes to `fitness.db`. It is never collected
or run by pytest.

Run one case, a small sample, or the full dataset explicitly:

```bash
python -m evals.run_interpreter_eval --provider openai --case body_weight_today
python -m evals.run_interpreter_eval --provider gemini --limit 5
python -m evals.run_interpreter_eval --provider gemini --delay-seconds 5 --json-report
```

`--provider` defaults explicitly to `openai`; specify it in recorded comparison
runs for clarity. Use `--model <model-name>` for a provider-specific override.
Both providers use the same 34 cases and comparator. Add `--json-report` to
write a report under the ignored `evals/results/` directory.

Provider quotas can affect live evaluation runs. Gemini uses a conservative
5-second default delay between cases for the observed free-tier request limit;
OpenAI defaults to no delay. Override either with `--delay-seconds <float>`.
The evaluator retries transient rate-limit responses at most twice, honoring a
provider retry delay when available or using bounded fallback backoff. Pacing
and retries are evaluator-only and do not change production interpreter
semantics.

The latest recorded Gemini (`gemini-3.5-flash-lite`) full run passed 33/34
cases (97.1%), with 0.9808 exact structured-field accuracy and zero
hallucinations, API errors, or retries. The only miss was
`mixed_body_activity_food`, which passed on an isolated rerun; this is treated
as normal provider/model variability rather than deterministic 34/34 accuracy.

The report emphasizes hallucination rate, exact structured-field accuracy,
missed/incorrect fields, missing/unexpected domains, API failures, per-tag pass
rates, latency, and token usage. Provider failures are reported separately and
are not graded as hallucinations. Warnings require presence only when specified;
their prose is not compared exactly.

The deterministic CLI requires an explicitly supplied `ParsedInput` JSON
payload and does not claim to perform AI interpretation:

```bash
python -m agent.ingestion "Walked 9000 steps today" \
  --parsed-json '{"activities":[{"steps":9000}]}'
```

Production ingestion commits the raw event before interpretation. Failed
interpretation or validation preserves that event with status `failed`;
structured persistence remains atomic.

`RelativeTimeResolver` deliberately supports only `today`, `yesterday`,
`this morning`, `tonight`, and `last night`. Unsupported language must remain
unresolved rather than being guessed. Both provider adapters return these labels;
the deterministic application resolver—not the model—assigns their datetimes.

---

## Development Workflow

Prefer small, testable changes.

For each meaningful change:

1. Understand the relevant architecture and decision documentation.
2. Make the smallest coherent implementation change.
3. Add or update tests when behavior changes.
4. Run the relevant tests.
5. Run the complete test suite.
6. Verify that the live database was not unintentionally modified.
7. Update documentation when architecture, schema, or project direction changes.

Avoid combining unrelated refactors and feature changes.

---

## Before Making Architectural Changes

Read:

```text
README.md
AGENTS.md
docs/PROJECT_CONTEXT.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/DATA_MODEL.md
```

Architecture changes should respect existing decisions unless there is a clear reason to revise them.

If an accepted decision changes, update:

```text
docs/DECISIONS.md
```

rather than silently changing implementation behavior.

---

## Database Access

Application code should prefer repository or controlled tool functions over arbitrary direct database writes.

Repository functions are located in:

```text
database/repository.py
```

Agent-facing application functions are located primarily in:

```text
agent/tools.py
```

The AI agent should use controlled application interfaces rather than issuing arbitrary SQL.

---

## Transactions

Repository functions support:

```python
commit=True
```

for standalone operations.

They also support:

```python
commit=False
```

when a higher-level operation owns the transaction.

Mixed-input ingestion owns one transaction across the complete user message.

Do not introduce commits inside an atomic workflow unless the transaction design is intentionally being changed.

The expected pattern is:

```text
open session
    ↓
perform writes with commit=False
    ↓
mark event processed
    ↓
commit once
```

On failure:

```text
rollback
```

---

## Validation

Structured input should pass through Pydantic validation before persistence.

Current validation models are located in:

```text
models/
```

Do not rely on the AI agent to guarantee valid structured values.

Validation belongs in deterministic application code.

---

## Raw Event Rule

Every natural-language fitness input must be preserved in:

```text
raw_events
```

before its structured representation is finalized.

One natural-language message should create one raw event.

Multiple structured records may reference that event.

Do not introduce ingestion paths that silently bypass raw-event preservation.

---

## Missing and Estimated Data

Do not invent missing fitness information.

If calories, protein, body measurements, or other values are unknown, preserve them as missing values.

For example:

```text
null
```

is preferable to an unsupported estimate.

If a value is estimated, it must be identifiable as an estimate.

---

## Analytics

Deterministic calculations belong in Python or SQL.

Examples include:

```text
daily totals
averages
rolling averages
weight trends
step trends
nutrition totals
workout volume
exercise progression
sleep trends
adherence
```

The AI should reason about analytics rather than recreate deterministic calculations from raw history.

As analytics grow, prefer moving analytics-specific logic into:

```text
analytics/
```

rather than allowing `agent/tools.py` to become the permanent analytics implementation.

---

## Current Analytics Limitation

Current summary functions primarily operate on the latest N records.

For example:

```python
get_weight_summary(7)
```

currently represents the latest seven measurements rather than a true seven-day period.

Do not assume these functions represent calendar windows.

Date-aware analytics are the next major correctness improvement.

---

## Timestamp Handling

Domain timestamps include:

```text
event_time
measured_at
consumed_at
recorded_at
sleep_start
sleep_end
started_at
```

These timestamps represent when the real-world event occurred.

The application timezone is `America/New_York`. New explicit domain timestamps
must include timezone information. The persistence layer converts them to
UTC-naive values for SQLite and restores UTC awareness when loading them.

Use `database.timezone.to_application_timezone()` before future local
calendar-day grouping.

They must not automatically be treated as equivalent to database insertion time.

Historical language such as:

```text
"yesterday"
"last night"
"Monday"
"this morning"
```

must eventually resolve to appropriate event timestamps before persistence.

Relative-time language resolution remains future work; timestamp propagation
and storage normalization are complete.

---

## Codex Development

Codex should operate on this repository using the documented architecture and controlled application boundaries.

Before implementing a task, Codex should understand:

```text
AGENTS.md
docs/PROJECT_CONTEXT.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/DATA_MODEL.md
docs/ROADMAP.md
docs/HANDOFF.md
```

when those files are available.

Codex should not infer architectural intent solely from existing code.

The documentation records decisions that may not be obvious from implementation alone.

---

## Obsolete Local LLM Code

An earlier Ollama/Qwen experiment was abandoned.

Ollama and the associated Python package have been removed from the active environment.

Some obsolete files may still exist, including:

```text
config/llm.py
agent/llm.py
agent/parser.py
```

Do not build new functionality on these files.

They may be removed after confirming that no active code depends on them.

---

## Project Structure

Current major directories:

```text
fitness-agent/
├── agent/
├── analytics/
├── config/
├── database/
├── docs/
├── models/
└── tests/
```

Responsibilities:

```text
agent/
    Agent-facing tools and context interfaces.

analytics/
    Deterministic fitness analytics.

config/
    User profile and application configuration.

database/
    SQLAlchemy connection, schema, and repositories.

docs/
    Architecture and development documentation.

models/
    Pydantic validation models.

tests/
    Automated isolated tests.
```

---

## Documentation Maintenance

Update documentation when implementation changes its meaning.

Use:

```text
README.md
```

for the project overview.

Use:

```text
docs/PROJECT_CONTEXT.md
```

for what is being built and why.

Use:

```text
docs/ARCHITECTURE.md
```

for system structure and data flow.

Use:

```text
docs/DECISIONS.md
```

for important architectural decisions and their reasoning.

Use:

```text
docs/DATA_MODEL.md
```

for database semantics and invariants.

Use:

```text
docs/DEVELOPMENT.md
```

for development procedures.

Use:

```text
docs/ROADMAP.md
```

for completed and planned work.

Use:

```text
docs/HANDOFF.md
```

for the current development checkpoint.

---

## Development Priorities

When choosing between implementation approaches, prioritize:

1. Data integrity
2. Correctness
3. Traceability
4. Testability
5. Clear component boundaries
6. Maintainability
7. Efficient AI context usage
8. Convenience

The project should remain understandable and maintainable without depending on the history of the ChatGPT conversation.
Synthetic coaching contexts should include explicit weight coverage. Use
`weight_days_logged` and `weight_days_requested` to distinguish sparse weight
evidence from an omitted or ambiguous fixture field.
Live coaching evaluation identified a repeated omission where Gemini described
missing sleep logging in prose but omitted the corresponding structured
`data_gaps` entry. The provider instruction now requires explicitly established
missing domains to be represented consistently in `data_gaps`; this does not
replace or weaken deterministic grounding.
The provider-neutral application service is `agent/service.py`:
`FitnessAgentService.log()` delegates to existing ingestion, while
`get_context()`/`get_coaching()` own read-session lifecycle and the grounded
coaching pipeline. Dependencies are injected, so tests do not require Gemini
or OpenAI. Logging success does not depend on a coaching provider.
Run `python app.py` for the interactive CLI. Ordinary natural-language input is
logged through the application service; enter `coach` explicitly to request
grounded coaching. `coach` is a command, not fitness data, and is never saved
as a `RawEvent`. Tests inject fake services and do not call providers.

Sparse weight coverage can support deterministic facts about recorded
measurements, including an endpoint change when that change is supplied by the
context. It does not establish a reliable longitudinal trend. Current grounding
uses structured evidence status and deterministic context; it does not attempt
arbitrary prose semantic verification.
