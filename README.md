# Fitness Agent

A local-first personal fitness tracking and AI coaching system.

The project is designed to maintain reliable long-term fitness history, calculate deterministic fitness analytics, and provide an AI agent with compact, structured context for personalized recommendations.

It is also being developed as a production-style AI/software engineering portfolio project.

## Goals

The system should help with:

* fat-loss tracking
* strength maintenance and progression
* cardiovascular endurance
* food and nutrition tracking
* daily activity tracking
* sleep tracking
* workout tracking
* historical fitness analysis
* personalized workout and fitness recommendations

Current primary goal:

**98.1 kg → 90 kg while maintaining or increasing strength and improving cardiovascular endurance.**

## Architecture

```text
Natural-language fitness input
        ↓
Codex / ChatGPT
        ↓
Controlled Python tools
        ↓
Raw event + validated structured records
        ↓
SQLite
        ↓
Python / SQL analytics
        ↓
Compact fitness context
        ↓
Codex / ChatGPT reasoning
        ↓
Fitness recommendation / workout plan
        ↓
Stored plan
        ↓
Dashboard
```

## Core Principles

### SQLite is the source of truth

Chat history is not used as the permanent fitness record.

All long-term fitness data is stored locally in SQLite.

### Preserve original input

Every natural-language fitness input must be stored verbatim in `raw_events`.

Structured records reference the raw event that produced them.

This provides an audit trail and allows future reparsing or debugging.

### Validate before persistence

Pydantic models form the validation boundary between interpreted input and database writes.

Invalid fitness data should be rejected before persistence.

### Keep deterministic work outside the LLM

Python and SQL handle:

* persistence
* calculations
* aggregation
* historical queries
* trends
* fitness metrics

The AI agent handles:

* natural-language interpretation
* reasoning
* recommendations

### Use compact AI context

The AI should not receive the entire fitness database or conversation history.

Python/SQL produces a compact fitness context containing the information required for reasoning.

### Atomic mixed input

One natural-language message may contain several types of information.

For example:

```text
I weighed 97 kg, walked 9,000 steps, ate chicken and rice,
and completed a chest workout.
```

This creates:

```text
1 raw_event
    ├── body metric
    ├── activity entry
    ├── food entries
    └── workout
```

The entire operation occurs in one database transaction.

If any part fails, the transaction is rolled back.

## Data Model

Current SQLite tables:

```text
raw_events
body_metrics
food_entries
activity_entries
sleep_entries
workout_sessions
exercise_sets
```

Structured fitness records are linked back to their source raw event where applicable.

## Current Capabilities

The system currently supports:

* body-weight logging
* food logging
* activity logging
* sleep logging
* workout and exercise-set logging
* raw-first natural-language event persistence
* optional OpenAI and Gemini interpretation with Structured Outputs
* Pydantic validation
* atomic database transactions
* isolated test databases
* recent weight queries
* activity summaries
* food summaries
* sleep summaries
* workout summaries
* compact fitness context generation
* machine-readable JSON context output

The current test suite has **152 passing tests**.

## Compact Fitness Context

The current context contains:

```text
profile
weight
activity
food
sleep
workouts
```

Generate it with:

```bash
python -m agent.context
```

The command outputs valid JSON suitable for consumption by Codex or another AI agent.

## Technology

* Python 3.14
* SQLite
* SQLAlchemy
* Pydantic
* pytest
* Codex / ChatGPT

## Development

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Run tests:

```bash
python -m pytest
```

Generate fitness context:

```bash
python -m agent.context
```

Install Python dependencies using:

```bash
python -m pip install -r requirements.txt
```

Deterministic ingestion remains available without a model provider:

```bash
python -m agent.ingestion "Walked 9000 steps today" \
  --parsed-json '{"activities":[{"steps":9000}]}'
```

For real natural-language extraction, set `OPENAI_API_KEY`; optionally set
`OPENAI_MODEL` (the default is `gpt-5.4-mini`), then run:

```bash
python -m agent.ingestion \
  "I weighed 96.2 kg this morning and walked 9000 steps today" --openai
```

The OpenAI request disables provider-side response storage with `store=False`.
The API key is read only from the environment and is never persisted.

Gemini is available through the same provider-neutral ingestion contract. Set
`GEMINI_API_KEY`; optionally set `GEMINI_MODEL` (the default is
`gemini-3.5-flash-lite`), then run:

```bash
python -m agent.ingestion \
  "I weighed 96.2 kg this morning and walked 9000 steps today" --gemini
```

Provider selection is explicit. There is no automatic routing or fallback.

Tests must never write to the live `fitness.db`.

## Current Limitation

The production context and natural-language ingestion boundary are ready, but
AI coaching/recommendations and model-quality evaluation are not implemented.
Legacy latest-N summaries remain available only for backwards compatibility.

## Next Direction

The next major stages are:

1. Evaluate real-model extraction behavior with representative inputs.
2. Generate recommendations from compact fitness context.
3. Store workout plans.
4. Compare planned workouts with actual performance.
5. Build the fitness dashboard.
6. Add reliable local backups.

## Documentation

Project-specific AI development rules are defined in:

```text
AGENTS.md
```

Additional architecture, decisions, data-model, roadmap, and development documentation belongs under:

```text
docs/
```
