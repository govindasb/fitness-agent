# Development Handoff

## Current State

Fitness Agent has a working foundation for:

* SQLite persistence
* raw natural-language event storage
* Pydantic validation
* body metrics
* food entries
* activity entries
* sleep entries
* workout sessions
* exercise sets
* atomic mixed-input ingestion
* isolated automated tests
* basic deterministic summaries
* compact fitness context
* JSON context output
* complete domain timestamp propagation
* conservative raw-event event-time propagation
* UTC-normalized domain timestamp persistence
* local-calendar daily aggregation for all five fitness domains
* date-aware period summaries for activity, food, weight, sleep, and workouts
* production AI-facing fitness context
* deterministic data-quality coverage indicators
* provider-neutral natural-language ingestion orchestration
* raw-first failure-safe ingestion semantics
* deterministic common relative-time resolution
* optional OpenAI Responses API interpreter adapter
* optional Gemini interpreter using the official Google Gen AI SDK
* Pydantic Structured Outputs with provider storage disabled
* a shared 34-case, explicitly invoked cross-provider evaluation harness

The natural-language interpretation/evaluation milestone is complete enough to
proceed. The latest full live evaluation used Gemini
(`gemini-3.5-flash-lite`) and passed 33/34 cases (97.1%), with exact
structured-field accuracy 0.9808, zero hallucinated fields (0.0%), one missed
field, one incorrect value, zero unexpected or missing domains, zero API
errors, and zero retries. Safety cases passed 8/8; all workout, relative-time,
difficult, and sleep cases passed. The only miss was
`mixed_body_activity_food`; an isolated rerun passed with exact accuracy 1.0
and no misses, incorrect values, hallucinations, or API errors. This indicates
normal provider/model variability, not a confirmed deterministic defect or a
claim of deterministic 34/34 accuracy.

Interpreter safeguards now include raw-event-first persistence, Pydantic
validation, provider-neutral empty-record removal and unsupported-time safety,
deterministic lexical normalization (including `run` → `running`), Gemini
schema sanitization, evaluator pacing, bounded evaluator-only rate-limit
retries, and no automatic provider fallback.

Current automated test status:

```text id="o2lv0p"
152 passed
```

---

## Current Architecture

```text id="6tzj5q"
Natural-language input
        ↓
Codex / ChatGPT
        ↓
Controlled Python tools
        ↓
Pydantic validation
        ↓
Raw event + structured records
        ↓
SQLite
        ↓
Python / SQL analytics
        ↓
Compact fitness context
        ↓
AI reasoning
        ↓
Recommendation / workout plan
```

SQLite is the permanent source of truth.

AI handles interpretation and reasoning.

Python/SQL handles validation, persistence, transactions, queries, and deterministic analytics.

---

## Current Fitness Context

The compact context currently contains:

```text id="rvpf6p"
generated_at
timezone
profile
weight
activity
nutrition
sleep
training
data_quality
```

Weight uses a 14-day window. Activity, nutrition, sleep, and training use
7-day windows. A supplied `reference` controls every window consistently.
The output contains only directly JSON-serializable primitives.

Generate it with:

```bash id="48plc2"
python -m agent.context
```

The command currently produces valid JSON.

Validate it with:

```bash id="y87mmh"
python -m agent.context | python -m json.tool > /dev/null && echo "valid JSON"
```

Expected:

```text id="wvlq08"
valid JSON
```

---

## Current Tests

Run:

```bash id="gqtgbi"
python -m pytest
```

Expected current result:

```text id="ibc6av"
152 passed
```

Tests use isolated in-memory SQLite databases.

Tests must never write to the live:

```text id="0zuc2l"
fitness.db
```

---

## Important Known Limitation

The production context uses date-aware analytics for all current fitness
domains. Legacy latest-N functions remain available only for compatibility.

For example:

```python id="trq10q"
get_weight_summary(7)
```

means the latest seven weight measurements, not necessarily the last seven calendar days.

The context does not yet include targets, adherence, exercise progression, or
recommendations. Real OpenAI and Gemini extraction adapters and the shared
evaluation harness are available; live evaluation is explicit and separate
from pytest. Deterministic static and JSON interpreters remain supported.

---

## Timestamp Semantics

Already-resolved domain timestamps are preserved through standalone and mixed
ingestion:

```text id="fcyvje"
body metric → measured_at
food        → consumed_at
activity    → recorded_at
sleep       → sleep_start / sleep_end
workout     → started_at
```

`raw_events.event_time` uses the canonical time for a standalone event. Sleep
uses `sleep_start`, falling back to `sleep_end`. Mixed ingestion sets
`event_time` only when every contained top-level record has an explicit
canonical timestamp and all timestamps agree. Otherwise it remains null.

`raw_events.created_at` remains the insertion time.

The natural-language adapter delegates the supported labels (`today`,
`yesterday`, `this morning`, `tonight`, and `last night`) to the existing
deterministic application resolver. Arbitrary relative dates remain unsupported.

The application timezone is `America/New_York`. Explicit domain timestamps
must be aware. SQLite stores normalized UTC-naive values, while SQLAlchemy
returns UTC-aware datetimes. Local calendar logic must convert to
`America/New_York` first.

Legacy domain timestamps were migrated from explicitly approved New York wall
time to UTC after a clean DST audit. Historical `raw_events.created_at` values
remain unchanged because their original timezone semantics are uncertain.

---

## Next Development Task

**Implement the AI coaching/recommendation layer using the existing production fitness context.**

The provider-neutral `FitnessCoach` pipeline and Gemini adapter are now in
place: `CoachingContext` → `GeminiFitnessCoach` → `CoachingResponse` →
deterministic grounding → approved response. The adapter sends only compact
context and never self-approves output. Live coaching calls have not been made
in tests.

The synthetic coaching evaluator (`evals/run_coaching_eval.py`) is now the
offline quality gate for future provider runs. It keeps schema, grounding, and
semantic quality failures separate and does not touch `fitness.db`.

Both provider adapters return the existing `InterpretationResult` contract
without bypassing controlled persistence. The 34-case evaluator measures exact fields,
hallucinations, omissions, incorrect values, domains, metadata requirements,
latency, and tokens without writing to the database.

---

## After Timestamp Correctness

Proceed in this order:

```text id="f1h3sl"
date-aware analytics
        ↓
production compact fitness context
        ↓
Codex natural-language integration
        ↓
fitness/workout recommendations
        ↓
persisted workout plans
        ↓
planned-vs-actual analysis
        ↓
dashboard
```

Do not build AI coaching logic on top of unreliable time-based analytics.

---

## Important Development Rules

Do not:

* bypass raw-event preservation
* allow mixed ingestion to partially commit
* invent missing fitness data
* treat estimates as measured facts
* let tests modify `fitness.db`
* use conversation history as permanent fitness storage
* allow the AI to replace deterministic calculations
* make arbitrary direct database writes when controlled application functions exist

Prefer small, tested changes.

---

## Documentation to Read

Before significant development, read:

```text id="gq95na"
README.md
AGENTS.md
docs/PROJECT_CONTEXT.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/DATA_MODEL.md
docs/DEVELOPMENT.md
docs/ROADMAP.md
```

Use this file only as the current development checkpoint.

Update `HANDOFF.md` whenever the current implementation state or immediate next task changes.

---

## Obsolete Code

The earlier Ollama/Qwen experiment was abandoned.

Potential obsolete files include:

```text id="fvdyx5"
agent/llm.py
agent/parser.py
config/llm.py
```

Do not build new functionality on these files.

Remove them later only after confirming they are unused.

---

## Resume Point

The project is ready to continue from:

**Run extraction evaluation → recommendations → persisted plans.**
The coaching context exposes weight coverage (`weight_days_logged` /
`weight_days_requested`) for the 14-day weight window. This supports grounded
sparse-weight data-gap reporting without treating weight coverage as target
adherence.
The live coaching evaluation reproduced a structured-output omission: Gemini
recognized explicitly missing sleep data in prose but omitted `sleep` from
`data_gaps`. The Gemini instruction now requires consistency between
deterministic missingness it recognizes and structured `data_gaps`, without
weakening grounding.
`FitnessAgentService` is now the application-facing composition boundary:
CLI/UI → service → ingestion or coaching. It injects the interpreter, coach,
and session factory; logging and coaching remain separate operations, and
coaching returns only grounded `CoachingResponse` values.

Sparse weight measurements may support a deterministic recorded-measurement
change, but sparse coverage does not establish a reliable longitudinal trend.
Evaluation and grounding rely on structured evidence and deterministic context,
not arbitrary prose keyword or semantic matching.
`app.py` is now the production CLI composition root. It wires Gemini providers
into `FitnessAgentService`; ordinary input calls `log()`, while the exact
`coach` command calls `get_coaching()` and renders only approved output.
Logging and coaching remain independent operations.
