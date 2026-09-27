# Fitness Agent

This project is a local-first personal fitness tracking and coaching system.

## Core Rule

SQLite is the source of truth.

Every natural-language fitness input must be saved verbatim to `raw_events` before any parsing, analysis, or recommendation occurs.

Never silently discard or overwrite raw user input.

If interpretation, validation, or structured persistence fails, keep the raw
event, mark it failed, and do not retain partial structured records.

## Agent Responsibilities

The agent may:

- interpret natural-language fitness input
- call controlled Python functions to store structured data
- query historical fitness data through application functions
- use deterministic analytics produced by Python/SQL
- generate workout and fitness recommendations from those analytics

The agent must not:

- invent historical fitness data
- write arbitrary data directly into SQLite when an application function exists
- treat conversation history as the permanent fitness record
- estimate or invent measurements unless explicitly marked as estimates
- modify or delete raw historical events without explicit user instruction

## Architecture

Natural language
→ agent
→ controlled Python tools
→ raw event + validated structured records
→ SQLite
→ Python/SQL analytics
→ compact fitness context
→ agent recommendation
→ stored plan
→ dashboard

## Development Rules

- Make small, testable changes.
- Do not change database schema without explaining the migration.
- Never fabricate fitness data.
- Preserve raw input before structured persistence.
- Use Pydantic validation before writes.
- Prefer repository/application functions over direct SQL.
- Mixed ingestion must remain atomic.
- Tests must never use the production fitness.db.
- Run the test suite after meaningful changes.

## Context

Before making architectural changes, read:

- docs/PROJECT_CONTEXT.md
- docs/ARCHITECTURE.md
- docs/DECISIONS.md
- docs/ROADMAP.md
