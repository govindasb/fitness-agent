# Fitness Dashboard V1 --- Implementation Requirements

## 1. Purpose

Build a polished, portfolio-quality, local-first Streamlit dashboard for
the existing fitness-agent project.

This is Dashboard V1. The dashboard must make the existing deterministic
fitness analytics easy to understand and use without redesigning or
weakening the working backend.

Primary goals: - Clean, minimal UI suitable for daily personal use and
portfolio presentation. - Read metrics from the existing SQLite database
through existing analytics/dashboard contracts. - Preserve conservative
data semantics: missing data is unknown, never zero unless zero was
actually recorded. - Support natural-language logging through the
existing ingestion/service layer. - Support on-demand grounded AI
coaching through the existing coaching pipeline. - Remain responsive on
desktop and phone-sized browser windows. - Keep the implementation
modular and maintainable.

The dashboard must not become a second analytics engine.

------------------------------------------------------------------------

## 2. Existing System --- Treat as Established Architecture

The project already has: - SQLite as the source of truth. - Raw input
preservation in `raw_events`. - Structured fitness tables for body
metrics, food, workouts, exercise sets, activity, and sleep. -
Deterministic analytics modules. - Deterministic adherence and
data-quality semantics. - A compact coaching context. - Provider-neutral
coaching interfaces. - Gemini coaching implementation. - Deterministic
grounding validation. - `FitnessAgentService` for logging, context, and
coaching. - `dashboard/metrics.py` as the dashboard metrics boundary. -
A working Streamlit shell. - Streamlit 1.64.0. - 244 passing tests
before this dashboard implementation.

Do not replace these layers with Streamlit-specific calculations or a
parallel data model.

------------------------------------------------------------------------

## 3. Core Data Principles --- Immutable

These rules are mandatory throughout the implementation.

1.  Missing data is not zero.
2.  Absence of a log is not proof that an activity, meal, workout, or
    behavior did not occur.
3.  Do not invent nutrition values.
4.  Do not invent measurements.
5.  Do not extrapolate sparse data.
6.  Recorded values and data completeness are separate concepts.
7.  UI wording must distinguish recorded observations from inferred
    trends.
8.  Database canonical units remain metric. Unit conversion is
    display-only.
9.  Dashboard rendering must not mutate fitness records.
10. Logging success must remain independent of coaching-provider
    availability.
11. AI coaching must only run when explicitly requested by the user.
12. Do not weaken deterministic grounding or tests to make AI output
    pass.

------------------------------------------------------------------------

## 4. Existing Dashboard Metrics Contract

The public V1 metrics contract is intentionally compact and should be
treated as stable unless a small, justified, tested extension is
necessary.

Top-level structure:

``` text
days_requested
goal
weight
steps
training
nutrition
sleep
coverage
```

Each relevant domain includes summary fields and `daily` chart data.

### Goal

Expected fields include: - `starting_weight_kg` - `target_weight_kg` -
`current_weight_kg` - `weight_lost_kg` - `remaining_kg` -
`progress_percent`

### Weight

Includes: - deterministic weight summary - `trend_eligible` -
`minimum_days_for_trend` - `daily`

An endpoint change may be displayed as recorded change even when a
reliable trend cannot be claimed.

### Steps

Includes: - logged-day summary - latest steps - total steps - average
steps on logged days - target-related metrics where already supported -
`daily`

### Training

Includes: - workout count - workout days - workout types - latest
workout - recorded sets - set logging completeness - volume - duration -
`daily`

Important semantics:

``` text
No workouts:
    total_sets = 0
    set_logging_complete = None

Workout logged but no set records:
    total_sets = 0
    set_logging_complete = False

Every logged workout has at least one set record:
    total_sets = recorded set count
    set_logging_complete = True
```

`set_logging_complete=True` is only a structural signal that each logged
workout has at least one set record. It does not prove every performed
set was logged and must not be used as proof of overall workout-log
completeness.

### Nutrition

Food logging and nutrient availability are separate.

A food entry without calorie/protein/macronutrient values must not
become zero calories or zero macros.

### Coverage

Coverage is a first-class dashboard concept and must remain visible to
the user.

------------------------------------------------------------------------

## 5. Scope

Implement Dashboard V1 with these navigation sections:

1.  Overview
2.  Weight
3.  Activity
4.  Training
5.  Nutrition
6.  Log
7.  Coach
8.  Data Quality

Sleep is intentionally excluded from the visible V1 dashboard. Existing
sleep backend functionality should remain untouched.

Use sidebar navigation.

------------------------------------------------------------------------

## 6. Visual Design

Style: - Clean and minimal. - Portfolio-quality, not visually
overloaded. - Automatically follow the Streamlit/system theme rather
than forcing light or dark mode. - Responsive for desktop and
phone-sized browser windows. - Favor whitespace, clear hierarchy,
restrained use of icons, concise labels, and readable charts. - Avoid
decorative complexity that does not improve comprehension.

The Overview should remain concise. Detailed analysis belongs on domain
pages.

------------------------------------------------------------------------

## 7. Date Range and Aggregation

Support: - Useful preset ranges such as 7, 14, and 30 days. - Custom
date ranges.

Aggregation rule for charts:

``` text
Range <= 31 calendar days:
    daily

Range 32–120 calendar days:
    weekly

Range > 120 calendar days:
    monthly
```

If the existing analytics layer does not support date-range aggregation
needed by the UI, add a small deterministic analytics/dashboard-layer
extension with tests. Do not calculate domain semantics ad hoc inside
Streamlit page code.

For weekly/monthly target comparisons, target values may be derived from
the configured daily target multiplied by the number of calendar days
represented by that bucket.

However, missing observations must remain missing. Do not fabricate
zeros to make aggregation visually convenient.

------------------------------------------------------------------------

## 8. Units

Provide a global sidebar toggle:

``` text
Metric / Imperial
```

Metric display: - kg - cm

Imperial display: - lb - ft/in where applicable

Exercise weights should also display in the selected system.

Steps, calories, grams of protein/macronutrients, percentages, dates,
and counts remain unchanged.

The database must continue storing canonical metric values. Unit
conversion is presentation-only.

------------------------------------------------------------------------

## 9. Overview Page

Show clean KPI cards for the most useful available metrics:

-   Current Weight
-   Goal Progress
-   Weight Lost
-   Average Steps
-   Workouts
-   Average Calories
-   Average Protein

Sleep is excluded from V1.

If a KPI cannot be computed because data is unavailable, show an
explicit unavailable/insufficient-data state instead of `0`.

Below the KPI cards, show compact previews for: - Weight - Steps -
Nutrition

Detailed versions belong on their domain pages.

Coverage/data-quality information should be visible without overwhelming
the Overview. A compact coverage summary or expandable panel is
acceptable.

------------------------------------------------------------------------

## 10. Weight Page

Include: - Current weight - Starting weight - Target weight - Recorded
weight change - Goal progress percentage - Remaining weight - Weight
measurements chart - Starting-weight reference - Target-weight reference

Trend behavior: - A trend may only be presented as a trend when
`trend_eligible=True`. - When `trend_eligible=False`, measurements may
still be plotted. - Clearly state that more measurements are required
before interpreting the series as a reliable trend. - Do not interpolate
missing days. - Do not connect sparse data in a way that implies
measurements occurred on missing dates. - Recorded endpoint change may
be shown, but label it as recorded change rather than a reliable trend
when coverage is insufficient.

------------------------------------------------------------------------

## 11. Activity Page

Primary V1 activity metric: steps.

Show: - Actual steps - Configured target - Difference between actual and
target where the observation is available - Average steps on logged
days - Total recorded steps - Logged-day coverage

Charts must follow the selected aggregation period.

For daily views: - compare actual daily steps against the daily target.

For weekly/monthly views: - compare recorded actuals and the
corresponding target carefully. - display coverage. - do not imply that
unlogged days contained zero steps. - if incomplete coverage makes a
target comparison misleading, label the comparison as partial or
withhold an adherence conclusion.

Configured target currently expected: - 10,000 steps/day

Read the configured target rather than hard-coding it into page logic.

------------------------------------------------------------------------

## 12. Training Page

Show: - Workout count - Workout days - Workouts by type - Latest
workout - Total recorded sets - `set_logging_complete` status - Recorded
training volume - Recorded duration

When `set_logging_complete=False`, clearly communicate that zero or low
recorded set counts do not mean zero or low sets were performed.

Do not use `set_logging_complete` as proof of complete workout logging.

### Exercise History

Provide an exercise selector/dropdown when exercise-set data exists.

For the selected exercise, display available historical metrics such
as: - weight used - reps - recorded sets - volume over time

Only display metrics supported by stored data.

Do not implement estimated 1RM in V1.

Do not implement special Upper A / Upper B classification logic for V1.
The user intends to provide cleaner, detailed workout logs going
forward.

------------------------------------------------------------------------

## 13. Nutrition Page

Nutrition values will be supplied by the user, typically after
separately obtaining a nutrition breakdown from a meal/photo workflow.

Example future input:

``` text
Lunch: chicken rice bowl — 720 kcal, 52g protein, 78g carbs, 21g fat.
```

Dashboard V1 must NOT estimate nutrition from vague food descriptions.

If nutrition values are supplied in the log and persisted by the
existing system, display them.

If values are absent: - keep them unknown - do not estimate them - do
not convert them to zero

Do not retroactively estimate nutrition for historical records.

Show available: - Calories - Protein - Carbohydrates - Fat - Nutrient
coverage - Relevant configured targets

Configured targets currently expected include: - 2,450 kcal/day - 170 g
protein/day

Read configured targets from the application configuration instead of
hard-coding them into page logic.

### Nutrition Charts

Follow an actual-versus-target pattern.

Examples: - actual calorie intake vs calorie target - actual protein
intake vs protein target

The target may be represented as a reference line or equivalent clear
visual treatment.

Actual intake is allowed to be below or above the target.

For weekly/monthly aggregation: - preserve incomplete-data semantics -
show coverage - do not compare a partial recorded week/month to a
complete target period as though intake logging were complete - do not
make adherence claims unless existing deterministic completeness rules
support them

------------------------------------------------------------------------

## 14. Logging Page

Add a natural-language logging UI using the existing service/ingestion
architecture.

Suggested UX: - Multiline text area - `Log Entry` button - concise
success/error result

The UI must call the existing logging service, preferably:

``` text
FitnessAgentService.log(...)
```

Do not create a second Streamlit-specific parser or write directly to
database tables.

After logging: - show a concise summary of what was extracted/persisted
where the existing result supports it - if a value was not supplied or
could not be determined, make that visible rather than inventing it

Example:

``` text
Steps: 11,786 ✓
Weight: 96.5 kg ✓
Chicken: quantity/nutrition not supplied → nutrition unavailable
```

Exact wording can differ.

Logging must continue working if the AI coaching provider is
unavailable.

Do not insert test/demo data into the production `fitness.db`.

------------------------------------------------------------------------

## 15. Coach Page

Provide an explicit button such as:

``` text
Generate Coaching
```

Do not invoke coaching simply because the dashboard page renders or
refreshes.

On click: - use the existing `FitnessAgentService.get_coaching(...)` /
grounded coaching pipeline - do not bypass deterministic grounding -
render structured output cleanly

Display sections such as: - Summary - Observations - Recommendations -
Data Gaps - Safety information when applicable

If the coaching provider fails or is unavailable: - show a clear
temporary-unavailability/error message - do not crash the dashboard - do
not affect logging - do not fabricate fallback coaching

No silent model-output repair should be introduced.

------------------------------------------------------------------------

## 16. Data Quality Page

Make data completeness understandable.

Show coverage such as: - weight days logged / requested - step days
logged / requested - food days logged / requested - calorie days
available - protein days available - workout count -
classified/unclassified workouts where supported - set logging
completeness

Use human-readable explanations.

Example:

``` text
Weight: 1 / 7 days
Steps: 1 / 7 days
Food: 1 / 7 days
Calories: 0 / 7 days
Protein: 0 / 7 days
```

Explain important semantics such as: - missing != zero - food logged !=
calories/macros available - workout logged != complete set details -
sparse weight data does not establish a reliable trend

This page is part of the product, not just a debugging screen.

------------------------------------------------------------------------

## 17. Empty and Partial States

Every dashboard section must handle: - no records - one record - partial
coverage - complete coverage - unavailable optional metrics

Prefer explicit messages such as: -
`No weight measurements are available for this period.` -
`More measurements are needed before interpreting this as a reliable trend.` -
`Calories unavailable because nutrition values were not recorded.` -
`Workout logged, but exercise-set details were not recorded.`

Avoid blank charts and misleading zeros.

------------------------------------------------------------------------

## 18. Refresh Behavior

Use normal Streamlit rerun behavior.

A small manual Refresh control may be added where useful.

Do not add background polling in V1.

------------------------------------------------------------------------

## 19. No Export in V1

Do not add CSV/export/download functionality in Dashboard V1.

------------------------------------------------------------------------

## 20. Architecture and Code Organization

Do not put the entire dashboard into one large `app.py`.

Codex may introduce a clean modular structure, for example:

``` text
dashboard/
    app.py
    pages/
    components/
    charts.py
    formatting.py
    metrics.py
```

The exact structure may differ if there is a clear reason.

Responsibilities should remain separated: - analytics/domain logic:
deterministic analytics layer - dashboard metric assembly: dashboard
metrics layer - unit/display formatting: dashboard formatting/helpers -
charts: reusable visualization helpers - Streamlit pages: composition
and presentation - logging: existing service/ingestion layer - coaching:
existing service/coaching layer

Small justified refactors are allowed when they improve maintainability
and are covered by tests.

Substantial unrelated architectural rewrites are out of scope.

------------------------------------------------------------------------

## 21. Charting Requirements

Use Streamlit-native charting or a lightweight charting dependency
already compatible with the project. Avoid adding heavy dependencies
without a concrete need.

Charts must: - be responsive - have readable axes and units - handle
empty/partial data - preserve actual dates - not manufacture missing
observations - show targets/reference values where required - remain
readable in light and dark themes

Chart-specific transformation logic that changes fitness semantics
belongs in deterministic helpers, not scattered across page code.

------------------------------------------------------------------------

## 22. Dependency Management

Inspect the repository to determine its current dependency-management
mechanism (`requirements.txt`, `pyproject.toml`, or equivalent).

Update the appropriate existing dependency file for Streamlit and any
genuinely required dashboard dependency.

Do not introduce a second dependency-management system without
justification.

------------------------------------------------------------------------

## 23. README / Portfolio Documentation

Update the project README or appropriate documentation with a Dashboard
V1 section containing:

-   What the project does
-   Dashboard feature summary
-   Architecture summary
-   Local-first design
-   Deterministic analytics + grounded AI separation
-   Missing-data philosophy
-   Setup instructions
-   How to run the dashboard
-   How to run tests
-   Major dashboard pages
-   Screenshot placeholder/instructions
-   Short explanation of why the project is portfolio-relevant

Do not claim features that are not actually implemented.

------------------------------------------------------------------------

## 24. Testing Requirements

Before implementation, run the existing suite and establish the
baseline.

Expected pre-dashboard baseline at specification time:

``` text
244 passed
```

There is currently one known dependency deprecation warning from
`google-genai` under Python 3.14. It is not a project-code failure.

Add tests for new deterministic dashboard behavior.

At minimum, cover: - date-range/aggregation behavior - unit conversion -
missing-data handling - weight trend eligibility presentation inputs -
target comparison helpers - partial step coverage - partial nutrition
coverage - set logging completeness propagation - exercise-history
transformation where implemented - empty states at the data/helper
layer - any extensions to `dashboard/metrics.py`

Do not write brittle tests against Streamlit rendering internals when
deterministic helper tests provide better coverage.

The implementation is not complete until: - all original tests still
pass - all new tests pass - no production behavior was weakened merely
to satisfy tests

Never modify a test only because the implementation disagrees with an
established semantic contract. Determine whether the test or
implementation is wrong first.

------------------------------------------------------------------------

## 25. Database Safety

The production database contains real user data.

Requirements: - Do not delete or rewrite existing production records. -
Do not insert demo/test data into production `fitness.db`. - Tests must
use isolated/in-memory/test databases according to existing project
patterns. - Do not run destructive migrations without an explicit
requirement. - Nutrition estimation does not require a schema migration
in Dashboard V1 because the user will supply nutrition values
explicitly. - If a schema change unexpectedly becomes necessary, stop
and document why before performing a destructive or irreversible
migration.

------------------------------------------------------------------------

## 26. Security / External Services

No special network restriction needs to be added in V1.

However: - dashboard browsing must not automatically invoke the AI
coach - coaching should occur only after the user explicitly clicks the
coaching action - do not add unrelated telemetry or external services

------------------------------------------------------------------------

## 27. Allowed Autonomy

Autonomy level: B.

Codex may: - add dashboard modules/components - make small justified
refactors - add deterministic helpers - extend dashboard metrics where
necessary - add tests - update appropriate dependency/documentation
files - improve naming/organization when behavior is preserved

Codex must not: - redesign the entire backend - replace SQLite - bypass
`FitnessAgentService` - duplicate ingestion logic - duplicate core
analytics in UI code - weaken grounding - invent missing fitness
values - introduce nutrition estimation - add sleep UI in V1 - add
estimated 1RM - add export functionality - add background polling -
silently change established metric semantics

------------------------------------------------------------------------

## 28. Implementation Workflow for Codex

Work autonomously through the implementation.

1.  Inspect the repository before editing.
2.  Read the existing analytics, dashboard metrics, service, models,
    configuration, and tests.
3.  Run the full test suite and confirm the baseline.
4.  Identify the existing dependency-management approach.
5.  Create a concise implementation plan based on this specification.
6.  Implement Dashboard V1 incrementally.
7.  Reuse existing contracts instead of recreating them.
8.  Add deterministic helpers/tests as needed.
9.  Run targeted tests after meaningful changes.
10. Run the full suite before completion.
11. Fix regressions rather than leaving known failures.
12. Run/validate the Streamlit application sufficiently to catch
    import/startup errors.
13. Update documentation.
14. Provide a final implementation report.

Do not stop after every file for user approval. Continue autonomously
unless: - a destructive database/schema change becomes necessary - a
requirement is technically contradictory - a major architecture change
outside Autonomy B appears necessary - user data would be at risk

------------------------------------------------------------------------

## 29. Acceptance Criteria

Dashboard V1 is complete when all of the following are true:

### Application

-   Streamlit application launches successfully.
-   Sidebar navigation contains Overview, Weight, Activity, Training,
    Nutrition, Log, Coach, and Data Quality.
-   UI follows Streamlit/system theme.
-   Layout is clean, minimal, portfolio-quality, and reasonably
    responsive.
-   Preset and custom date ranges work.
-   Metric/Imperial display toggle works without changing stored data.

### Overview

-   KPI cards display supported values.
-   Missing KPIs display unavailable states, not false zeros.
-   Compact Weight, Activity, and Nutrition previews exist.

### Weight

-   Measurements display correctly.
-   Starting and target weights are represented.
-   Recorded change and goal progress display.
-   Trend language is only used when deterministic trend eligibility
    permits it.
-   Sparse measurements do not create false observations.

### Activity

-   Actual steps and configured target are visually comparable.
-   Difference/target relationship is available when supported.
-   Daily/weekly/monthly behavior follows the range rules.
-   Partial coverage is clearly represented.

### Training

-   Workout summary displays.
-   Set completeness semantics are visible.
-   Exercise history is available when set data exists.
-   No estimated 1RM.
-   No new Upper A/B classification logic.

### Nutrition

-   User-supplied nutrition values display when available.
-   Missing nutrition remains unknown.
-   Calories and protein can be compared to configured targets.
-   Partial nutrition coverage cannot masquerade as complete adherence.
-   No nutrition estimation is added.

### Log

-   Natural-language input uses the existing logging/service pipeline.
-   Successful logs are reflected after rerun/refresh.
-   Parsing/persistence errors are displayed safely.
-   No direct Streamlit-to-table persistence bypass.

### Coach

-   Coaching runs only on explicit button click.
-   Existing grounded pipeline is used.
-   Structured response is readable.
-   Provider failure is handled without breaking dashboard/logging.

### Data Quality

-   Coverage is visible and understandable.
-   Important missing-data semantics are explained.

### Engineering

-   Existing backend semantics remain intact.
-   No production data corruption.
-   All pre-existing tests pass.
-   All newly added tests pass.
-   Appropriate dependency file is updated.
-   README/documentation is updated.
-   No known application startup/import errors remain.

------------------------------------------------------------------------

## 30. Definition of Done / Final Report

When finished, Codex should report:

1.  What was implemented.
2.  Files added.
3.  Files modified.
4.  Any small architectural refactors and why.
5.  Dependencies added/changed.
6.  Test results, including total passing tests.
7.  Streamlit startup validation performed.
8.  Known limitations or intentionally deferred V1 features.
9.  Exact command to launch the dashboard.
10. Any manual visual checks the user should perform.

Do not declare completion while tests are failing.
