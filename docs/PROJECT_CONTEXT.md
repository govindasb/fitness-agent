# Project Context

## What We Are Building

Fitness Agent is a local-first personal fitness tracking and AI coaching system.

The goal is to allow fitness information to be entered naturally instead of requiring manual interaction with multiple forms, spreadsheets, or tracking applications.

A user should eventually be able to write:

> I weighed 96.8 kg this morning, walked 9,200 steps, ate chicken and rice for lunch, and completed a chest workout.

The system should understand the message, preserve the original input, validate the extracted information, store structured fitness records, update historical analytics, and use that information when generating future recommendations.

The long-term interaction should feel conversational while the underlying data system remains structured and reliable.

---

## Why We Are Building It

The project has two purposes.

### Personal Fitness System

The primary purpose is to build a fitness system that can maintain long-term history and provide increasingly useful recommendations as more data is collected.

The current fitness objective is:

**Reduce body weight from 98.1 kg to 90 kg while maintaining or increasing strength and improving cardiovascular endurance.**

The system should eventually help answer questions such as:

* What should I train today?
* Am I losing weight at an appropriate rate?
* Is my strength being maintained while losing weight?
* Am I consistently reaching my activity target?
* Am I eating enough protein?
* How has my sleep affected training?
* Should today's workout intensity be adjusted?
* Am I progressing compared with previous weeks?

Recommendations should be based on stored data rather than conversational memory.

### Software Engineering / AI Portfolio Project

The project is also intended to demonstrate production-oriented AI and software engineering skills.

Important engineering concepts include:

* LLM integration
* structured tool calling
* data validation
* relational data modeling
* transactional persistence
* deterministic analytics
* AI context construction
* automated testing
* auditability
* separation of deterministic and probabilistic systems
* local-first application architecture

The project should therefore prioritize correctness and maintainability rather than functioning only as an AI demo.

---

## User Profile

Current baseline profile:

* Age: 27
* Sex: male
* Height: 170.18 cm
* Starting weight: 98.1 kg
* Target weight: 90 kg
* Primary goal: fat loss
* Secondary goal: maintain or increase strength
* Secondary goal: improve cardiovascular endurance
* Historical activity level: approximately 10,000 steps per day
* Intended strength-training frequency: approximately 4 sessions per week

These values provide baseline context for future analytics and recommendations.

They should not be treated as immutable. Targets may change as progress is evaluated.

---

## Intended User Experience

Fitness information should primarily be entered through natural language.

Examples:

> I weighed 96.5 kg this morning.

> Walked 10,500 steps today.

> Slept 7 hours and felt good.

> Bench press: 50 kg for 10 reps, then 50 kg for 8 reps.

A message may also contain several categories simultaneously.

The system should convert these messages into validated structured data without requiring the user to manually specify database fields.

The original message must still be preserved.

---

## Long-Term Data Ownership

Fitness history must not depend on ChatGPT or Codex conversation history.

SQLite is the permanent source of truth for the application.

Conversation history is temporary interaction context.

This distinction allows the fitness history to remain:

* durable
* queryable
* portable
* auditable
* independent of a particular AI conversation

The AI should retrieve the information it needs through controlled application interfaces.

---

## Raw Input Preservation

Every natural-language fitness input should be preserved verbatim before structured information derived from it is persisted.

For example:

```text
Raw input:

"I weighed 96.8 kg, walked 9000 steps and trained chest."
```

may produce:

```text
raw_event
├── body_metric
├── activity_entry
└── workout_session
```

All derived records should remain traceable to the original input.

This allows future improvements to parsing without losing what the user actually said.

It also provides an audit trail when structured data appears incorrect.

---

## Role of the AI Agent

Codex / ChatGPT is the reasoning layer of the system.

The AI should primarily handle tasks that benefit from language understanding or reasoning, including:

* interpreting natural-language fitness input
* identifying relevant information
* deciding which controlled tools to call
* understanding fitness context
* generating recommendations
* explaining trends
* adapting workout suggestions

The AI should not become the database or analytics engine.

---

## Role of Python and SQL

Deterministic operations belong in Python and SQL.

Examples include:

* storing records
* retrieving historical records
* calculating averages
* calculating daily totals
* calculating weight trends
* calculating workout volume
* calculating adherence
* aggregating nutrition
* comparing planned and completed workouts

These calculations should produce the same result given the same underlying data.

This makes them testable and avoids unnecessary dependence on probabilistic AI reasoning.

---

## AI Context Strategy

The full fitness database should not be sent to the AI every time a recommendation is requested.

Instead:

```text
SQLite
    ↓
Python / SQL analytics
    ↓
Compact fitness context
    ↓
AI reasoning
```

The compact context should contain only information relevant to the current decision.

The current implementation includes:

* profile
* weight summary
* activity summary
* food summary
* sleep summary
* workout summary

This strategy keeps AI context small while allowing the underlying fitness history to grow indefinitely.

---

## Data Integrity

Natural-language interpretation is probabilistic.

Database persistence should not be.

Pydantic models therefore act as a validation boundary before structured data is persisted.

Invalid values should be rejected rather than silently accepted.

Mixed messages should also be processed atomically.

If a single message generates multiple structured records and one part fails, the entire operation should roll back rather than leaving partially stored information.

---

## Recommendations

Future recommendations should combine several sources of information rather than relying on one measurement.

Examples may include:

* recent weight trend
* activity level
* nutrition
* protein intake
* sleep
* workout history
* previous exercise performance
* training frequency
* recovery
* current goals

The system should distinguish between:

1. measured information,
2. deterministic calculations,
3. estimates,
4. AI recommendations.

Estimated values must be identified as estimates rather than presented as measured facts.

---

## Workout Planning

The system should eventually generate daily workout recommendations based on historical performance and current fitness context.

Workout plans should be stored.

Completed workouts should also be stored separately.

This enables:

```text
planned workout
        ↓
actual workout
        ↓
comparison
        ↓
future recommendation
```

Over time, this should allow recommendations to adapt to actual performance rather than repeatedly generating independent workouts.

---

## Dashboard

The dashboard is a presentation layer, not the source of truth.

It should read from the same SQLite database and deterministic analytics used by the AI system.

Potential dashboard information includes:

* weight trend
* progress toward target weight
* daily steps
* nutrition
* protein intake
* sleep
* workout frequency
* exercise progression
* training volume
* planned vs actual workouts

The dashboard should remain independent from AI reasoning.

---

## Current State

The project currently has working support for:

* SQLite persistence
* raw event storage
* structured fitness records
* Pydantic validation
* body metrics
* food
* activity
* sleep
* workouts
* exercise sets

Natural-language interpretation is now an evaluated production milestone. The
current reference provider is Gemini (`gemini-3.5-flash-lite`). The latest full
34-case live run passed 33/34 cases (97.1%), with exact structured-field
accuracy 0.9808, zero hallucinated fields (0.0% hallucination rate), one missed
field, one incorrect value, zero unexpected or missing domains, zero API
errors, and zero retries. All 8/8 safety cases, workout, relative-time,
difficult, and sleep cases passed. The only full-run miss was
`mixed_body_activity_food`; an isolated rerun passed with 1.0 exact accuracy
and no misses, incorrect values, hallucinations, or API errors. This is normal
provider/model variability, not evidence of a deterministic 34/34 guarantee or
a confirmed interpreter defect.

The production safeguards include raw-event-first ingestion, Pydantic
validation, provider-neutral empty-record and unsupported-time handling,
deterministic lexical normalization (including the controlled `run` →
`running` alias), Gemini schema sanitization, evaluator pacing, bounded
evaluator-only rate-limit retries, and explicit provider selection without
automatic fallback. The next major phase is the AI coaching/recommendation
layer using the existing production fitness context.
