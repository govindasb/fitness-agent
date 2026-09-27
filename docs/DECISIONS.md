# Architecture Decisions

This document records important technical and product decisions for Fitness Agent.

These decisions should be reviewed before making significant architectural changes.

---

## ADR-001 — SQLite Is the Source of Truth

**Status:** Accepted

### Decision

All permanent fitness history is stored locally in SQLite.

ChatGPT, Codex, and conversation history are not permanent fitness storage.

### Why

SQLite provides:

* durable local storage
* structured queries
* portability
* simple backups
* no external infrastructure requirement

This also allows the application to operate independently of any individual AI conversation.

---

## ADR-002 — Preserve Raw Natural-Language Input

**Status:** Accepted

### Decision

Every natural-language fitness input must be stored verbatim in `raw_events`.

Structured records derived from that message should reference the original event.

### Why

Natural-language interpretation is probabilistic and may improve over time.

Preserving the original message enables:

* auditing
* debugging
* reparsing
* parser-version comparison
* recovery from extraction errors

Raw events must not be silently modified or deleted.

---

## ADR-003 — Structured Data Must Be Validated Before Persistence

**Status:** Accepted

### Decision

Pydantic models form the validation boundary between interpreted input and structured database writes.

### Why

AI-generated structured data cannot automatically be assumed valid.

Validation prevents obviously invalid values such as:

* negative weight
* negative steps
* invalid sleep ratings
* invalid RPE values
* negative food quantities

Invalid data should fail explicitly rather than silently entering fitness history.

---

## ADR-004 — Separate AI Reasoning From Deterministic Computation

**Status:** Accepted

### Decision

Python and SQL perform deterministic calculations.

Codex / ChatGPT performs language interpretation and contextual reasoning.

### Deterministic responsibilities

Examples:

* averages
* totals
* rolling trends
* workout volume
* nutrition aggregation
* activity aggregation
* historical comparisons
* adherence calculations

### AI responsibilities

Examples:

* interpreting natural language
* deciding which controlled tools to call
* understanding fitness context
* generating recommendations
* explaining trends

### Why

Calculations should be reproducible and testable.

The same database state should produce the same analytics regardless of AI behavior.

---

## ADR-005 — AI Uses Controlled Application Tools

**Status:** Accepted

### Decision

The AI agent should interact with application data through controlled Python functions rather than arbitrary SQL or direct database manipulation.

### Why

Controlled tools provide:

* validation
* predictable behavior
* transaction boundaries
* easier testing
* safer database access
* stable interfaces for the agent

Application functions should be preferred whenever an appropriate function exists.

---

## ADR-006 — One User Message Produces One Raw Event

**Status:** Accepted

### Decision

A single natural-language message creates one `raw_events` record even when the message contains multiple categories of fitness information.

Example:

```text id="f55mmd"
"I weighed 97 kg, walked 9000 steps and trained chest."
```

should produce:

```text id="z1eb6p"
raw_event
├── body_metric
├── activity_entry
└── workout_session
```

All derived records should remain traceable to the same source event.

### Why

The raw event represents the original user interaction, not each individual extracted field.

---

## ADR-007 — Mixed Input Must Be Atomic

**Status:** Accepted

### Decision

Mixed-input ingestion occurs inside one database transaction.

Repository operations used within the transaction support:

```text id="rr3pdx"
commit=False
```

so the higher-level operation owns the transaction.

If any structured record fails, the entire transaction is rolled back.

### Why

A message should not leave partially persisted fitness history.

For example, if a message contains weight, food, activity, and a workout, failure while saving the workout must not leave the other portions silently committed.

---

## ADR-008 — Repository Functions Support Transaction Ownership

**Status:** Accepted

### Decision

Repository functions support both:

```text id="wyyumk"
commit=True
```

for standalone operations and:

```text id="rdmksu"
commit=False
```

for higher-level transactions.

With `commit=False`, repository functions flush but do not commit.

### Why

This allows repository functions to remain reusable while supporting atomic workflows such as mixed ingestion.

---

## ADR-009 — Tests Must Never Use the Live Fitness Database

**Status:** Accepted

### Decision

Automated tests use isolated in-memory SQLite databases.

Tests must not write to:

```text id="9md9r5"
fitness.db
```

### Why

Earlier development demonstrated that tests can accidentally pollute real fitness history.

Test isolation provides:

* repeatability
* safety
* independent tests
* reliable rollback testing

---

## ADR-010 — Compact Context Instead of Full Database History

**Status:** Accepted

### Decision

The AI receives a compact fitness context generated from deterministic queries and analytics.

The full fitness database should not be placed into the AI context for every interaction.

Current context categories include:

```text id="1b9w19"
profile
weight
activity
food
sleep
workouts
```

### Why

Fitness history will grow continuously.

Sending full history would:

* consume unnecessary model context
* increase token usage
* increase latency
* introduce irrelevant information
* make reasoning less predictable

The application should summarize historical data before passing it to the AI.

---

## ADR-011 — Fitness Context Must Be Machine-Readable

**Status:** Accepted

### Decision

The context command:

```bash id="eq6r14"
python -m agent.context
```

outputs valid JSON.

### Why

JSON provides a stable machine-readable interface that can be consumed by Codex or other future agent integrations.

It also separates context generation from presentation.

---

## ADR-012 — Event Time and Insertion Time Are Different Concepts

**Status:** Accepted, implementation incomplete

### Decision

The system must distinguish between:

* when the user reports something
* when the fitness event actually occurred

Domain timestamps include values such as:

```text id="9zlv3c"
event_time
measured_at
consumed_at
recorded_at
sleep_start
sleep_end
started_at
```

### Why

Historical natural-language input must be represented correctly.

Example:

```text id="ip9twz"
"Yesterday I walked 8500 steps."
```

must eventually create activity associated with yesterday rather than the database insertion time.

Correct event-time handling is required before reliable date-based analytics can be implemented.

---

## ADR-013 — Analytics Should Be Date-Aware

**Status:** Accepted, implementation pending

### Decision

The current latest-N-record summaries are temporary.

Production fitness analytics should operate on meaningful calendar periods and daily aggregates.

Examples include:

* daily steps
* daily calories
* daily protein
* daily weight measurements
* 7-day weight averages
* weekly workout frequency
* sleep trends

### Why

Seven records are not necessarily seven days.

Fitness coaching should reason about actual time periods rather than arbitrary record counts.

---

## ADR-014 — Missing Nutrition Data Must Remain Missing

**Status:** Accepted

### Decision

The system must not invent calories, protein, carbohydrates, fat, fiber, or other measurements when they are unavailable.

Missing values should remain `None` / `null`.

Estimated nutrition values may be stored only when explicitly identified as estimates.

### Why

Measured, estimated, and unknown information must remain distinguishable.

This prevents false precision from influencing fitness recommendations.

---

## ADR-015 — Estimates Must Be Explicit

**Status:** Accepted

### Decision

Estimated fitness information must be marked as estimated rather than represented as measured fact.

Food entries currently include:

```text id="vsfnw6"
is_estimated
```

The same principle should apply to future estimated data where relevant.

### Why

Recommendations should be able to distinguish data quality and confidence.

---

## ADR-016 — Profile Data Is Separate From Event History

**Status:** Accepted

### Decision

Long-lived user baseline information is stored separately from event-based fitness history.

Current profile configuration:

```text id="u3hmsh"
config/profile.json
```

Examples include:

* age
* sex
* height
* starting weight
* target weight
* goals
* baseline activity
* intended training frequency

### Why

These values describe user context rather than individual fitness events.

They should be available to analytics and AI context without being duplicated across event records.

---

## ADR-017 — Workout Plans Must Eventually Be Persisted

**Status:** Accepted, implementation pending

### Decision

AI-generated workout plans should eventually be stored in the application rather than existing only in conversation history.

The system should distinguish between:

```text id="10i8a4"
planned workout
```

and:

```text id="sm12kt"
completed workout
```

### Why

Persisted plans enable:

* planned-vs-actual comparisons
* adherence tracking
* progression analysis
* better future recommendations

This creates a feedback loop instead of generating isolated workouts.

---

## ADR-018 — Dashboard Is a Consumer, Not a Source of Truth

**Status:** Accepted

### Decision

The future dashboard reads from SQLite and deterministic analytics.

It should not maintain a separate fitness history.

### Why

The AI agent and dashboard should operate from the same underlying information.

This avoids conflicting data stores and duplicated business logic.

---

## ADR-019 — Local LLM Is Not Required

**Status:** Accepted

### Decision

The earlier Ollama/Qwen local-LLM approach was abandoned.

Codex / ChatGPT will provide the primary AI reasoning layer.

### Why

The local model experiment introduced unnecessary latency and reliability problems for the current project.

The valuable local-first requirement applies primarily to ownership and persistence of fitness data, not necessarily to running the reasoning model locally.

Obsolete Ollama-related code should eventually be removed after confirming it is unused.

---

## ADR-020 — Prefer Small, Testable Development Changes

**Status:** Accepted

### Decision

Development should proceed through small changes with validation or tests after meaningful modifications.

### Why

The system manages persistent personal data.

Incremental changes make it easier to:

* identify regressions
* protect data integrity
* understand failures
* maintain architectural boundaries

Significant behavior changes should include corresponding tests.

---

## ADR-021 — Store Domain Timestamps as UTC

**Status:** Accepted

### Decision

The application timezone is `America/New_York`.

New explicit domain timestamps must be timezone-aware. The persistence boundary
rejects naive explicit datetimes, converts aware values to UTC, and stores them
in SQLite as UTC-naive `DATETIME` values. When SQLAlchemy loads those values,
the application restores `timezone.utc`.

Calendar-day logic must convert UTC-aware values to `America/New_York` before
selecting or grouping by a local date.

### Why

SQLite does not preserve timezone offsets in its native `DATETIME` handling.
A single UTC storage convention avoids mixed offsets and handles daylight-saving
transitions as instants rather than ambiguous wall times.

Existing naive domain timestamps were explicitly interpreted as
`America/New_York` wall time and migrated atomically to UTC-naive storage after
a DST ambiguity/nonexistence audit. `raw_events.created_at` was not migrated:
its historical host-time semantics cannot be proven, so guessing would violate
the data-integrity policy.

---

## ADR-022 — Preserve Raw Input Before Interpretation

**Status:** Accepted

### Decision

Production natural-language ingestion commits one verbatim raw event before
calling an interpreter or validating its structured output.

Interpretation and validation failures mark the raw event `failed`. Structured
records are then written atomically in a separate transaction. A structured
write failure rolls back every derived record, preserves the raw event, and
marks it `failed`.

The ingestion orchestrator depends on the provider-neutral
`FitnessInterpreter` protocol and records parser version
`fitness-interpreter-v1`.

### Why

Natural-language input is primary audit evidence even when probabilistic
interpretation or deterministic persistence fails. Keeping the raw-event commit
separate provides that durability without permitting partial fitness history.

---

## ADR-023 — Natural-Language Interpretation Evaluation Gate

**Status:** Accepted

The natural-language interpretation milestone is complete enough to proceed to
AI coaching. Gemini (`gemini-3.5-flash-lite`) passed 33/34 cases (97.1%) in the
latest full live evaluation, with exact structured-field accuracy 0.9808 and
zero hallucinations, API errors, or retries. Safety (8/8), workout,
relative-time, difficult, and sleep cases all passed. The only miss,
`mixed_body_activity_food`, passed in an isolated rerun with 1.0 exact accuracy
and no errors. This is recorded as normal provider/model variability; it is not
a claim of deterministic 34/34 accuracy.

The acceptance gate includes raw-event-first persistence, Pydantic validation,
provider-neutral record and time safety normalization, deterministic lexical
normalization (including `run` → `running`), Gemini schema sanitization,
evaluator pacing, bounded evaluator-only rate-limit retries, and no automatic
provider fallback. Live evaluation remains explicitly separate from pytest and
database persistence.

## Decision Priorities

When future implementation choices conflict, prefer the option that best preserves these priorities:

1. Data integrity
2. Correctness
3. Traceability
4. Testability
5. Clear separation of responsibilities
6. Maintainability
7. Efficient AI context usage
8. Convenience

The central architectural rule remains:

**AI interprets and reasons. Deterministic software validates, stores, calculates, and verifies.**
