# Roadmap

## Current Status

Fitness Agent currently has a working persistence, validation, transaction, testing, basic analytics, and compact-context foundation.

Current automated test status:

```text id="12bhfp"
152 passed
```

The deterministic data foundation, provider-neutral ingestion orchestration,
and natural-language interpretation evaluation milestone are complete enough to
proceed. Real OpenAI and Gemini adapters are implemented and evaluated through
the shared 34-case harness.

---

## Phase 1 — Core Data Foundation

**Status: Complete**

* [x] Create Python project structure
* [x] Configure virtual environment
* [x] Add SQLite persistence
* [x] Add SQLAlchemy models
* [x] Add repository layer
* [x] Create `raw_events`
* [x] Create body metric storage
* [x] Create food storage
* [x] Create activity storage
* [x] Create sleep storage
* [x] Create workout session storage
* [x] Create exercise-set storage
* [x] Link structured records to raw events
* [x] Preserve original natural-language input

---

## Phase 2 — Validation and Safe Ingestion

**Status: Complete**

* [x] Add Pydantic body-metric validation
* [x] Add food validation
* [x] Add activity validation
* [x] Add sleep validation
* [x] Add workout validation
* [x] Add combined `ParsedInput` model
* [x] Support mixed fitness input
* [x] Ensure one user message creates one raw event
* [x] Add transaction ownership to repository functions
* [x] Make mixed ingestion atomic
* [x] Roll back the entire mixed event on failure

---

## Phase 3 — Testing Foundation

**Status: Complete**

* [x] Add repository tests
* [x] Add tool tests
* [x] Use isolated in-memory SQLite databases
* [x] Prevent tests from modifying `fitness.db`
* [x] Reset tool-test database between tests
* [x] Test mixed-event raw-event behavior
* [x] Test transaction rollback
* [x] Test validation failures
* [x] Test basic read/summary behavior
* [x] Test compact fitness context

Current suite:

```text id="ftk1vh"
152 passing tests
```

---

## Phase 4 — Basic Read and Analytics Layer

**Status: Initial version complete**

Implemented:

* [x] Recent weight retrieval
* [x] Weight summary
* [x] Recent activity retrieval
* [x] Activity summary
* [x] Recent food retrieval
* [x] Food summary
* [x] Recent sleep retrieval
* [x] Sleep summary
* [x] Recent workout retrieval
* [x] Workout summary
* [x] Workout volume calculation

### Known Limitation

The original analytics APIs operate on the latest N records.

They are not yet true calendar-based analytics.

This phase should not be considered production-quality coaching analytics until the date-aware work below is complete.

---

## Phase 5 — Compact Fitness Context

**Status: Initial version complete**

* [x] Load user profile
* [x] Include profile in fitness context
* [x] Include weight summary
* [x] Include activity summary
* [x] Include food summary
* [x] Include sleep summary
* [x] Include workout summary
* [x] Add `agent.context`
* [x] Produce machine-readable JSON
* [x] Verify JSON validity

Current command:

```bash id="w4ps4i"
python -m agent.context
```

---

## Phase 6 — Timestamp Correctness

**Status: Complete**

Resolved datetimes now propagate through the ingestion layer without replacing
existing ORM defaults when timestamps are omitted.

* [x] Audit all domain timestamps
* [x] Propagate `measured_at` when storing body metrics
* [x] Propagate `consumed_at` when storing food
* [x] Propagate `recorded_at` when storing activity
* [x] Propagate `started_at` when storing workouts
* [x] Correctly persist sleep start/end
* [x] Define the role of `raw_events.event_time`
* [x] Distinguish event time from insertion time
* [x] Support historical entries with already-resolved datetimes
* [x] Add timestamp-specific tests
* [x] Define `America/New_York` as the application timezone
* [x] Normalize domain timestamps to UTC at the persistence boundary
* [x] Migrate legacy domain timestamps after a DST audit
* [x] Reject new naive explicit domain timestamps

Required behavior:

```text id="gjl3ye"
"Yesterday I walked 8500 steps."
```

must eventually be represented as activity for yesterday rather than the time the message was inserted into SQLite.

Relative-time language resolution remains part of the future natural-language
integration. This phase guarantees correct persistence once a datetime has been
resolved.

---

## Phase 7 — Date-Aware Analytics

**Status: Complete**

Daily aggregation and period summaries use `America/New_York` calendar dates,
include missing requested days, and preserve unknown values distinctly from
zero.

### Weight

* [x] Daily weight measurements
* [x] Configurable-window average weight
* [x] Weight change within the requested window
* [ ] Progress toward target weight
* [x] Configurable longer-term weight trend

### Activity

* [x] Daily activity aggregation by `America/New_York` calendar day
* [x] Daily step totals
* [x] 7-day average steps on days with known step data
* [x] Preserve missing days and unknown values distinctly from zero
* [ ] Step-target adherence
* [x] Daily active-minute aggregation

### Nutrition

* [x] Daily calorie totals
* [x] Daily protein totals
* [x] Daily carbohydrate totals
* [x] Daily fat totals
* [x] Daily fiber totals
* [x] Per-nutrient data-availability counts
* [ ] Compare intake against targets

### Sleep

* [x] Daily sleep duration
* [x] Configurable-window sleep average
* [x] Period sleep-quality average
* [ ] Recovery context

### Workouts

* [x] Configurable-period workout frequency
* [x] Daily and period set counts
* [x] Calculable workout volume
* [x] Duration aggregation
* [x] Workout-type session counts
* [ ] Volume by exercise
* [ ] Volume by workout/body-part category
* [ ] Exercise load progression
* [ ] Rep progression
* [ ] RPE trends
* [ ] Strength-retention indicators

Advanced goal comparison, adherence, recovery, and exercise-progression
analytics remain later enhancements; they are not required for the foundational
calendar-aware aggregation phase.

---

## Phase 8 — Production Fitness Context

**Status: Complete**

The production context uses date-aware analytics and one shared reference for
all domain windows.

The compact context includes:

```text id="n4qkqt"
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

Weight uses 14 days; the other event domains use 7 days. Compact daily series
retain missing dates and null values. The result is directly JSON serializable
and is the deterministic input contract for future AI coaching.

---

## Phase 9 — Codex Natural-Language Integration

**Status: Complete enough to proceed**

Use Codex as the natural-language reasoning and tool-selection layer.

* [ ] Verify Codex CLI integration
* [x] Define provider-neutral interpreter interface
* [x] Define raw-first ingestion workflow
* [x] Provide controlled logging tools
* [x] Provide controlled read/analytics tools
* [x] Interpret natural-language fitness input through OpenAI or Gemini
* [x] Validate interpreter output as `ParsedInput`
* [x] Persist against one existing raw event without duplication
* [x] Preserve raw events across interpretation/persistence failures
* [x] Retrieve compact fitness context
* [x] Prevent arbitrary database writes through controlled boundaries
* [x] Test provider-neutral end-to-end ingestion
* [x] Add real OpenAI Responses API provider adapter
* [x] Add real Gemini provider adapter using the official Google Gen AI SDK
* [x] Use Structured Outputs derived from the production Pydantic contract
* [x] Disable provider-side response storage for extraction requests
* [x] Keep relative-time resolution application-owned
* [x] Add representative real-model extraction evaluation harness and dataset
* [x] Run both providers against the same evaluation cases and comparator
* [x] Keep live provider evaluations separate from pytest and database persistence
* [x] Report deterministic hallucination, accuracy, domain, latency, and token metrics
* [x] Run and review the live extraction dataset

Latest recorded live review (Gemini `gemini-3.5-flash-lite`): 33/34 passed
(97.1%), exact structured-field accuracy 0.9808, zero hallucinations (0.0%),
one missed field, one incorrect value, zero unexpected/missing domains, zero
API errors, and zero retries. Safety cases passed 8/8; workout, relative-time,
difficult, and sleep cases all passed. The sole full-run miss,
`mixed_body_activity_food`, passed on an isolated rerun with 1.0 exact accuracy
and no errors. This is normal provider/model variability, not deterministic
34/34 accuracy and not a confirmed interpreter defect.

Safeguards completed in this phase include raw-event-first ingestion, Pydantic
validation, provider-neutral empty-record and unsupported-time handling,
deterministic lexical normalization with the controlled `run` → `running`
alias, Gemini schema sanitization, evaluator pacing, bounded evaluator-only
rate-limit retries, and explicit provider selection without automatic fallback.

Target interaction:

```text id="p2jzby"
User:
"I weighed 96.4 kg this morning,
walked 9200 steps and trained chest."

        ↓

Codex

        ↓

validated structured input

        ↓

controlled Python tool

        ↓

SQLite
```

---

## Phase 10 — Fitness Recommendation Engine

**Status: Next**

The provider-neutral coach contract, deterministic grounding validator, and
first Gemini coaching adapter are now implemented. Coaching generation remains
unapproved until it passes grounding; recommendation policy and production
integration are still forthcoming.

Synthetic coaching evaluation cases and a provider-neutral evaluator now cover
schema validity, grounding validity, and separate quality expectations before
any live coaching run is trusted.

Use deterministic analytics plus AI reasoning to generate useful recommendations.

* [ ] Establish initial calorie target
* [ ] Establish protein target
* [ ] Establish activity target
* [ ] Establish training-frequency target
* [ ] Establish cardio target
* [ ] Generate daily fitness recommendations
* [ ] Generate workout recommendations
* [ ] Adjust recommendations based on recovery
* [ ] Adjust recommendations based on weight trend
* [ ] Adjust recommendations based on strength performance
* [ ] Clearly distinguish recommendations from measured facts

Initial targets should remain adjustable rather than permanently hard-coded.

---

## Phase 11 — Workout Planning and Feedback Loop

**Status: Planned**

Add persisted workout plans.

* [ ] Design workout-plan schema
* [ ] Design planned-exercise schema
* [ ] Store AI-generated workout plans
* [ ] Link plans to dates
* [ ] Record completed workouts separately
* [ ] Compare planned vs actual sets
* [ ] Compare planned vs actual load
* [ ] Compare planned vs actual reps
* [ ] Compare planned vs actual RPE
* [ ] Track adherence
* [ ] Feed comparison into future recommendations

Target feedback loop:

```text id="w61mt4"
historical performance
        ↓
workout recommendation
        ↓
stored plan
        ↓
completed workout
        ↓
planned vs actual
        ↓
updated analytics
        ↓
next recommendation
```

---

## Phase 12 — Dashboard

**Status: Planned**

Build a local dashboard reading from SQLite and deterministic analytics.

Potential dashboard sections:

* [ ] Current weight
* [ ] Weight trend
* [ ] Progress toward 90 kg
* [ ] Daily steps
* [ ] Step trend
* [ ] Calories
* [ ] Protein
* [ ] Sleep
* [ ] Workout frequency
* [ ] Training volume
* [ ] Exercise progression
* [ ] Planned vs actual workouts
* [ ] Goal adherence

The dashboard must remain a consumer of the existing data model rather than becoming another source of truth.

---

## Phase 13 — Reliability and Maintenance

**Status: Planned**

* [ ] Add automatic local database backups
* [ ] Define restore procedure
* [ ] Add schema migration strategy
* [ ] Improve error reporting
* [ ] Add structured logging
* [ ] Review database indexes
* [ ] Review analytics performance
* [ ] Add data-export capability
* [ ] Add database integrity checks

---

## Phase 14 — Cleanup

**Status: Planned**

* [ ] Confirm obsolete Ollama/Qwen code is unused
* [ ] Remove obsolete `agent/llm.py`
* [ ] Remove obsolete `agent/parser.py`
* [ ] Remove obsolete `config/llm.py`
* [ ] Review other unused development files
* [ ] Review development/test-like records in live database

Historical data must not be deleted automatically during cleanup.

---

## Phase 15 — Portfolio Readiness

**Status: Planned**

Once the core system is functional:

* [ ] Finalize README
* [ ] Add architecture diagram
* [ ] Add example workflows
* [ ] Add setup instructions
* [ ] Add representative tests
* [ ] Add screenshots/dashboard examples
* [ ] Document engineering tradeoffs
* [ ] Document AI architecture
* [ ] Document safety/data-integrity design
* [ ] Clean repository history and structure
* [ ] Prepare project for GitHub presentation

The portfolio should emphasize the engineering system rather than presenting the project as a simple LLM wrapper.

---

## Immediate Next Priority

The next development sequence is:

```text id="2o4m8s"
AI coaching/recommendations using the production fitness context
        ↓
Persisted workout plans
        ↓
Dashboard
```

Do not rush Codex recommendation integration before the underlying timestamps and analytics are trustworthy.

The quality of AI recommendations depends on the quality of the deterministic context provided to the model.
