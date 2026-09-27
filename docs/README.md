# Fitness Agent Documentation

This directory contains the technical and product context required to understand and continue development of Fitness Agent.

## Start Here

Read the documentation in this order:

1. [Project Context](PROJECT_CONTEXT.md)
   What is being built, why it exists, and the intended product direction.

2. [Architecture](ARCHITECTURE.md)
   System structure, component responsibilities, data flow, transaction boundaries, and AI/application separation.

3. [Architecture Decisions](DECISIONS.md)
   Important technical decisions and the reasoning behind them.

4. [Data Model](DATA_MODEL.md)
   Database entities, relationships, timestamps, and data-integrity rules.

5. [Development Guide](DEVELOPMENT.md)
   Environment, commands, testing rules, development workflow, and Codex guidance.

6. [Roadmap](ROADMAP.md)
   Completed work, planned phases, and implementation order.

7. [Development Handoff](HANDOFF.md)
   Current implementation state, known limitations, and the immediate next task.

## Quick Reference

For a new development or Codex session:

```text id="58l8ys"
AGENTS.md
        ↓
docs/HANDOFF.md
        ↓
docs/ROADMAP.md
        ↓
Relevant architecture/documentation files
        ↓
Code
```

`AGENTS.md` defines the rules the coding agent must follow.

`HANDOFF.md` identifies where development currently stands.

`ROADMAP.md` identifies where the project is going.

The remaining documents explain the reasoning and architecture behind those decisions.

## Documentation Responsibilities

```text id="sc2aw2"
PROJECT_CONTEXT.md → What and why
ARCHITECTURE.md    → How the system works
DECISIONS.md       → Why technical choices were made
DATA_MODEL.md      → What the stored data means
DEVELOPMENT.md     → How to work on the project
ROADMAP.md         → What comes next
HANDOFF.md         → Where development currently stopped
```

Keep these responsibilities separate to avoid duplicating large amounts of information across files.

## Maintenance

Update documentation when the corresponding project information changes.

In particular:

* update `DECISIONS.md` when an architectural decision changes
* update `DATA_MODEL.md` when database semantics change
* update `ROADMAP.md` when phases are completed or reprioritized
* update `HANDOFF.md` whenever the immediate development state changes

The documentation should allow development to continue without requiring access to previous ChatGPT conversations.
