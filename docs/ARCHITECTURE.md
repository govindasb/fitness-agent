# Architecture

## Overview

Fitness Agent is a local-first system that separates AI reasoning from deterministic data storage and analytics.

The high-level architecture is:

```text
Natural-language fitness input
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
Codex / ChatGPT reasoning
        ↓
Recommendation / workout plan
        ↓
Stored plan
        ↓
Dashboard
```

SQLite is the permanent source of truth.

The AI interacts with fitness data through controlled application functions rather than acting as the storage or analytics layer.

---

## Architectural Layers

### 1. AI / Agent Layer

Primary location:

```text
agent/
```

Responsibilities:

* interpret natural-language input
* identify fitness information contained in a message
* call controlled application tools
* request compact historical context
* reason over fitness context
* generate recommendations

The agent should not:

* directly manipulate SQLite when an application function exists
* calculate deterministic historical analytics itself
* invent missing historical data
* use conversation history as permanent storage

---

## 2. Tool Layer

Primary location:

```text
agent/tools.py
```

The tool layer provides the controlled interface between the AI agent and the application.

Current responsibilities include:

* logging weight/body metrics
* logging food
* logging activity
* logging sleep
* logging workouts
* logging mixed inputs
* retrieving recent records
* calculating basic summaries
* generating compact fitness context

The agent should interact with application data through these controlled functions.

This boundary prevents the AI from issuing arbitrary database operations.

---

## 3. Validation Layer

Primary location:

```text
models/
```

Pydantic models validate structured information before persistence.

Current models include:

```text
ParsedBodyMetric
ParsedFoodEntry
ParsedFoodItem
ParsedActivity
ParsedSleep
ParsedWorkout
ParsedExerciseSet
ParsedInput
```

Validation occurs before database writes whenever possible.

Examples of invalid data include:

* negative body weight
* negative steps
* invalid sleep quality ratings
* invalid RPE values
* negative food quantities

Invalid structured input should fail rather than being silently persisted.

---

## 4. Repository Layer

Primary location:

```text
database/repository.py
```

The repository layer owns standard persistence operations.

Examples include:

```text
save_raw_event()
save_body_metric()
save_food_entry()
save_activity_entry()
save_sleep_entry()
save_workout_session()
save_exercise_set()
mark_event_processed()
```

Repository functions support two transaction modes.

### Standalone writes

```text
commit=True
```

The repository function commits its own change.

This is appropriate for independent operations.

### Higher-level transactions

```text
commit=False
```

The repository function flushes the object without committing.

This allows a higher-level operation to own the transaction.

This mechanism is used by mixed-input ingestion.

---

## 5. Persistence Layer

Primary components:

```text
database/connection.py
database/schema.py
fitness.db
```

Technology:

```text
SQLite
SQLAlchemy
```

SQLite is the application's permanent source of truth.

Current tables include:

```text
raw_events
body_metrics
food_entries
activity_entries
sleep_entries
workout_sessions
exercise_sets
```

Structured records are linked to the raw event that produced them where applicable.

---

## Raw Event Architecture

Natural-language input is preserved before structured data derived from it is finalized.

Example:

```text
"I weighed 97 kg and walked 9000 steps."
```

becomes:

```text
raw_events
    │
    ├── body_metrics
    │
    └── activity_entries
```

The same `source_event_id` links derived records to the original message.

The raw event provides:

* auditability
* debugging
* traceability
* future reparsing
* parser-version tracking

Raw events should not be silently modified or deleted.

---

## Mixed Input Transactions

A single user message may contain several categories of fitness information.

Example:

```text
I weigh 97 kg, walked 9000 steps,
ate chicken and rice, and trained chest.
```

The operation should produce:

```text
raw_event
├── body_metric
├── activity_entry
├── food_entries
└── workout_session
    └── exercise_sets
```

Mixed ingestion uses one database transaction.

Conceptually:

```text
BEGIN TRANSACTION

create raw event
validate/persist body metrics
validate/persist food
validate/persist activity
validate/persist sleep
validate/persist workouts
mark raw event processed

COMMIT
```

If any operation fails:

```text
ROLLBACK
```

Partial mixed events must not remain in the database.

---

## Production Natural-Language Ingestion

The production orchestration entry point is:

```text
ingest_fitness_message(raw_text, interpreter, reference=None)
```

Its ordering is intentional:

```text
commit raw event
        ↓
provider-neutral interpretation
        ↓
ParsedInput validation
        ↓
atomic structured persistence
        ↓
processed / failed raw-event status
```

The raw event is committed before the interpreter runs. Interpretation or
validation failure leaves that event marked `failed`. Structured writes use a
separate transaction: any failure rolls back all derived records while the raw
event remains available for auditing.

This differs from `log_mixed_input()`, whose raw and structured writes share
one transaction. Both APIs remain supported for their distinct use cases.

`FitnessInterpreter` is provider-neutral:

```text
FitnessInterpreter
├── StaticInterpreter
├── JsonInterpreter
├── OpenAIFitnessInterpreter
└── GeminiFitnessInterpreter
```

`OpenAIFitnessInterpreter` uses the official OpenAI SDK and Responses API with
native Pydantic Structured Outputs and `store=False`.
`GeminiFitnessInterpreter` uses the official Google Gen AI SDK and Gemini's
native Pydantic response schema. Both return and revalidate the same existing
`InterpretationResult` contract. Ingestion contains no provider-specific
parsing logic, and provider selection is explicit with no routing or fallback.

The model emits one of the supported relative-time labels rather than choosing
a date. Application code resolves that label against the same fixed request
reference used by ingestion, then revalidates the final result with Pydantic.
Provider, refusal/blocked/incomplete-output, schema, and configuration failures cross
the boundary as interpretation failures, preserving the already-committed raw
event without structured rows.

Provider output passes through shared deterministic normalization before
structured persistence: empty records are removed, records tied to explicitly
unsupported time expressions are withheld while their warning and source
fragment are preserved, and a small auditable lexical normalization handles
case/whitespace plus `run` → `running`. Gemini receives a reduced
provider-compatible JSON Schema; the original Pydantic contract remains the
authoritative validation boundary. Evaluation pacing and bounded rate-limit
retries exist only in the live evaluator and never alter production ingestion.

The natural-language interpretation milestone is complete enough to proceed.
The latest Gemini `gemini-3.5-flash-lite` full evaluation scored 33/34 (97.1%)
with 0.9808 exact structured-field accuracy and zero hallucinations. The sole
miss, `mixed_body_activity_food`, passed on an isolated rerun, so the result is
treated as normal model variability rather than a deterministic defect. AI
coaching/recommendation generation is the next phase.

`RelativeTimeResolver` supports only `today`, `yesterday`, `this morning`,
`tonight`, and `last night`, using one `America/New_York` reference. Morning
and tonight use deterministic 08:00 and 20:00 anchors; last night uses the
previous day at 22:00 through the current day at 07:00. Unsupported expressions
remain unresolved.

---

## Analytics Layer

Primary location:

```text
analytics/
```

Some early analytics functions currently remain in:

```text
agent/tools.py
```

As analytics become more sophisticated, deterministic calculations should move into the dedicated analytics layer.

The analytics layer is responsible for calculations such as:

* weight trends
* rolling averages
* daily step totals
* activity averages
* daily nutrition totals
* protein intake
* sleep trends
* workout volume
* exercise progression
* training frequency
* adherence
* planned-vs-actual comparisons

Analytics should be deterministic.

Given the same database state, they should produce the same result.

---

## Compact Context Layer

Current entry point:

```text
get_fitness_context(reference=None)
```

Command-line interface:

```bash
python -m agent.context
```

The command produces machine-readable JSON.

Current context structure:

```text
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

The context builder resolves one reference instant for the complete context.
Weight uses a 14-day local-calendar window. Activity, nutrition, sleep, and
training use 7-day windows. Each section contains a compact period summary and
a short daily series that retains missing days and null measurements.

`generated_at` is a UTC-aware ISO string. `data_quality` contains objective
logging coverage counts and the nutrition estimation ratio; it does not invent
a subjective confidence score.

The builder returns JSON primitives directly. Serialization does not rely on
fallback conversion of ORM or datetime objects.

The purpose of this layer is to prevent the AI from loading the complete fitness database into its context.

Instead:

```text
SQLite
   ↓
deterministic queries
   ↓
summaries
   ↓
compact context
   ↓
AI
```

This keeps AI context size bounded as fitness history grows.

This structure is the deterministic input contract for future AI coaching.

---

## AI Reasoning Boundary

The system intentionally separates probabilistic and deterministic responsibilities.

### AI responsibilities

```text
language interpretation
contextual reasoning
recommendation generation
explanation
```

### Application responsibilities

```text
validation
persistence
transactions
historical queries
aggregation
calculations
```

For example, Python should calculate a 7-day average weight.

The AI may then reason about what that trend means for the user's fitness goal.

The AI should not independently reconstruct the average from raw database history when a deterministic calculation is available.

---

## Timestamp Architecture

Fitness records contain domain-specific timestamps such as:

```text
measured_at
consumed_at
recorded_at
sleep_start
sleep_end
started_at
event_time
```

These timestamps represent when the fitness event actually occurred.

They must remain distinct from database insertion time.

The application timezone is `America/New_York`. Explicit timestamps must be
timezone-aware. The `UTCDateTime` persistence type normalizes them to UTC-naive
values for SQLite and restores UTC awareness when they are loaded.

Before calendar-day grouping, application code must convert loaded UTC values
to `America/New_York`.

For example:

```text
User message:
"Yesterday I walked 8500 steps."
```

The eventual structured activity should represent yesterday as the activity date.

Timestamp propagation and UTC normalization are complete. Relative-time parsing
and date-aware analytics remain separate future work.

---

## Testing Architecture

Tests must be isolated from the live database.

Production:

```text
fitness.db
```

Tests:

```text
in-memory SQLite
```

Tests use separate SQLAlchemy engines and sessions.

The tool test database is reset between tests.

This ensures:

* repeatable tests
* no production-data pollution
* independent test cases
* safe transaction testing

Current test suite:

```text
152 passing tests
```

---

## Configuration

User profile information is stored separately from fitness event history.

Current location:

```text
config/profile.json
```

It contains baseline information such as:

```text
age
sex
height
starting weight
target weight
fitness goals
activity baseline
training frequency
```

Profile information is included in the compact fitness context.

Current coaching targets are a separate typed configuration loaded from
`config/coaching_targets.json` through `load_coaching_targets()` and validated
by `CoachingTargets`. The profile describes identity and baseline; targets
describe the behavioral values currently used for coaching. Future work will
combine the production fitness context with these targets for deterministic
adherence calculations, then provide that result to the AI coach.

`analytics/adherence.py` provides this comparison as an independent,
deterministic layer. Missing data remains unknown (neither zero nor evidence
of target failure). Weekly training targets scale by `days / 7`. Explicit
strength labels include generic labels (`strength`, `weights`, `weight
training`, `resistance`, `bodybuilding`, `powerlifting`) and common body-part
or lifting-split labels (`chest`, `back`, `legs`, `shoulders`, `arms`, `biceps`,
`triceps`, `push`, `pull`, `upper body`, `lower body`). Cardio labels are
`cardio`, `running`, `cycling`, `swimming`, `walking`, `rowing`, and
`elliptical`. Other workout types remain unclassified.

Adherence distinguishes record presence from metric availability and
completeness: a logged food day can have unavailable calories or protein, and
partial nutrient coverage does not produce a target percentage. A logged
activity record can likewise lack steps. Missing data is never converted to
zero, and absence of a logged record is not evidence that the behavior did not
occur.

`agent/coaching_context.py` composes a compact coaching context from the
production fitness context, `CoachingTargets`, and adherence coverage. It
exposes conservative permission flags: nutrition and steps require at least
`ceil(days / 2)` available days; training additionally requires at least one
logged session and 100% classification coverage. However, classification
completeness only answers whether the workout records we have can be classified;
it does not establish that logging is complete for the period. Until a
deterministic workout-log completeness signal exists,
`can_assess_training_adherence` remains false with reason
`workout_log_completeness_unknown`. This is deterministic input for a future
provider-neutral coach; the LLM does not decide whether missing evidence
constitutes target failure.

Coaching coverage also includes `weight_days_logged` and
`weight_days_requested` for the production 14-day weight window. This is an
evidence-quality signal, not weight-target adherence: one logged weight can be
reported as an observation, while incomplete coverage can support a weight
data-gap report.

The next provider-neutral boundary is `CoachingResponse` in
`models/coaching_response.py`. A future coach will receive `CoachingContext`
and must return this strictly typed structure (summary, factual observations,
bounded recommendations, data gaps, and safety). Pydantic guarantees shape and
controlled vocabularies only; a separate deterministic grounding and safety
validator must later verify that claims and adherence-dependent actions are
permitted by the context.

The provider-neutral coaching boundary is:

```text
CoachingContext
      ↓
FitnessCoach
      ↓
CoachingResponse
      ↓
deterministic grounding validator
      ↓
approved CoachingResponse
```

`generate_grounded_coaching()` first validates the provider result as a
`CoachingResponse`, then applies deterministic grounding. Structural validation
failures (`CoachingStructureError`) remain distinct from grounding failures
(`CoachingGroundingError`); neither is silently repaired or filtered. Future
`GeminiFitnessCoach` and `OpenAIFitnessCoach` implementations will use this
same interface and downstream validation path, so provider selection cannot
change grounding behavior.

The coaching response boundary is therefore:

```text
CoachingContext
      ↓
provider-neutral coach
      ↓
CoachingResponse (Pydantic structure)
      ↓
deterministic grounding validator
      ↓
approved response
```

`agent/coaching_grounding.py` uses only controlled response fields and context
permissions; it never classifies response prose or uses an LLM judge. A
schema-valid response is not automatically evidence-grounded. Ambiguous
adherence claims are rejected, and insufficient context evidence cannot be
upgraded by the model.

---

## Planned Workout Architecture

Future workout planning should distinguish between:

```text
planned workout
```

and:

```text
completed workout
```

The intended feedback loop is:

```text
historical performance
        ↓
fitness context
        ↓
AI workout recommendation
        ↓
stored workout plan
        ↓
completed workout
        ↓
planned-vs-actual comparison
        ↓
updated analytics
        ↓
future recommendation
```

Plans should be persisted rather than existing only in conversation history.

---

## Dashboard Architecture

The dashboard should be a consumer of the application data and analytics.

It should not become another source of truth.

```text
               SQLite
              /      \
             ↓        ↓
        Analytics   Dashboard
             ↓
      Compact Context
             ↓
            AI
```

Both AI and dashboard features should ultimately depend on the same underlying data and deterministic analytics.

---

## Current Project Structure

```text
fitness-agent/
├── README.md
├── AGENTS.md
├── app.py
│
├── agent/
│   ├── context.py
│   └── tools.py
│
├── analytics/
│
├── config/
│   ├── profile.json
│   └── profile.py
│
├── database/
│   ├── connection.py
│   ├── repository.py
│   └── schema.py
│
├── models/
│   ├── activity.py
│   ├── body_metric.py
│   ├── event.py
│   ├── food.py
│   ├── parsed_input.py
│   ├── sleep.py
│   └── workout.py
│
├── tests/
│   ├── test_database.py
│   └── test_tools.py
│
├── docs/
│   ├── PROJECT_CONTEXT.md
│   └── ARCHITECTURE.md
│
└── fitness.db
```

Some obsolete experimental local-LLM/Ollama files may still exist and should be cleaned up separately once they are confirmed unused.

---

## Architectural Direction

The intended final flow is:

```text
User
 ↓
Natural language
 ↓
Codex / ChatGPT
 ↓
Controlled tools
 ↓
Pydantic validation
 ↓
Transactional persistence
 ↓
SQLite
 ↓
Deterministic analytics
 ↓
Compact context
 ↓
AI reasoning
 ↓
Recommendation
 ↓
Persisted plan
 ↓
Actual performance
 ↓
Feedback loop
```

The architecture should continue to preserve one fundamental separation:

**AI interprets and reasons. The application validates, stores, calculates, and verifies.**

Coaching quality is evaluated separately from schema and grounding validity by
`evals/run_coaching_eval.py` against synthetic `CoachingContext` cases. A
response may be structurally valid and grounded yet fail a quality expectation,
such as overstating sparse weight evidence. Evaluation does not weaken
production grounding rules and never persists data.
`GeminiFitnessCoach` is the first model-backed coaching provider. It receives
only compact `CoachingContext`, requests a sanitized structured
`CoachingResponse`, and leaves approval to the provider-independent grounding
validator. It sends no raw user text, database rows, tools, or retrieval data;
provider failures remain distinct and no fallback is automatic.

The application-service boundary is:

```text
CLI/UI
  ↓
FitnessAgentService
  ├── log() → ingestion
  └── get_coaching() → CoachingContext → FitnessCoach → grounding
```

`FitnessAgentService` injects the interpreter, coach, and session factory. A
successful log is independent of coaching-provider availability; logging never
automatically invokes coaching.

Its instruction explicitly encodes that `general_guidance` must set
`requires_adherence_evidence=false` and `adherence_metric=null`. Adherence
claims require a permitted structured metric; food-log presence is distinct
from calorie/protein availability, and logged workouts or sparse steps are not
extrapolated to real-world adherence. These prompt rules guide the provider;
the deterministic grounding validator remains authoritative.
The CLI composition root wires `GeminiFitnessInterpreter`,
`GeminiFitnessCoach`, and `FitnessAgentService`. Ordinary text follows
`CLI/UI → FitnessAgentService.log() → ingestion`; the exact `coach` command
follows `CLI/UI → FitnessAgentService.get_coaching() → deterministic context →
provider coach → structural validation → deterministic grounding → approved
output`. The `coach` command is not persisted as a raw event, and logging does
not depend on coaching-provider availability.
