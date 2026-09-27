# Codex Dashboard V1 Prompt

Implement Dashboard V1 for this repository using
`DASHBOARD_REQUIREMENTS.md` as the authoritative specification.

Work autonomously until the specification's acceptance criteria and
definition of done are satisfied. Inspect the existing repository and
tests before editing. Preserve established backend/data semantics and
reuse the existing analytics, `dashboard/metrics.py`, ingestion,
`FitnessAgentService`, and grounded coaching pipeline rather than
duplicating them.

Start by running the existing test suite and confirming the baseline.
Then implement the dashboard incrementally, add appropriate tests, run
targeted tests during development, and finish with the complete test
suite plus a Streamlit startup/import validation.

You have Autonomy Level B: small justified refactors are allowed when
tested and behavior-preserving. Do not perform destructive
database/schema changes, write test/demo data to the production
database, weaken deterministic grounding, invent missing values, or
expand beyond Dashboard V1.

If a destructive schema/database change, user-data risk, contradictory
requirement, or major architecture change becomes necessary, stop and
explain the blocker instead of proceeding.

At completion, provide the final report requested by the requirements
document.
