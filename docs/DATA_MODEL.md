# Data Model

## Overview

Fitness Agent stores permanent fitness history in SQLite.

The current data model contains:

```text
raw_events
body_metrics
food_entries
activity_entries
sleep_entries
workout_sessions
exercise_sets
```

The central relationship is:

```text
raw_events
    │
    ├── body_metrics
    ├── food_entries
    ├── activity_entries
    ├── sleep_entries
    └── workout_sessions
            │
            └── exercise_sets
```

A natural-language message creates one raw event.

Structured records derived from that message reference the raw event through `source_event_id`.

---

## Raw Events

Table:

```text
raw_events
```

### Purpose

Stores the original natural-language input exactly as provided by the user.

Example:

```text
"I weighed 97 kg, walked 9000 steps and trained chest."
```

This record is the permanent audit trail for information extracted from the message.

### Important Fields

```text
id
raw_text
event_type
processing_status
parser_version
event_time
created_at
```

### Field Meaning

`id`

Unique identifier for the raw event.

`raw_text`

Original user input. It should be preserved verbatim.

`event_type`

Classification of the processed event.

A message containing several categories may use:

```text
mixed
```

`processing_status`

Indicates whether processing has completed.

`parser_version`

Identifies the parser or agent version responsible for interpreting the event.

Current mixed ingestion uses:

```text
codex-v1
```

`event_time`

Represents the relevant time associated with the reported event when available.

When populated, this is stored as UTC-naive in SQLite and returned by the
application as UTC-aware.

`created_at`

Represents when the raw event was stored.

### Invariants

* Natural-language fitness input must be preserved.
* One user message creates one raw event.
* Raw events must not be silently deleted or overwritten.
* Structured records should remain traceable to their source event.

---

## Body Metrics

Table:

```text
body_metrics
```

### Purpose

Stores body measurements.

Current supported measurements include:

```text
weight_kg
waist_cm
body_fat_percent
resting_heart_rate
```

### Important Fields

```text
id
measured_at
weight_kg
waist_cm
body_fat_percent
resting_heart_rate
source_event_id
```

### Field Meaning

`measured_at`

When the measurement was actually taken.

`weight_kg`

Body weight in kilograms.

`waist_cm`

Waist measurement in centimeters.

`body_fat_percent`

Body-fat percentage.

`resting_heart_rate`

Resting heart rate in beats per minute.

`source_event_id`

Raw event from which the measurement was derived.

### Validation

Current validation includes reasonable bounds such as:

* weight must be positive
* waist measurement must be positive
* body-fat percentage must be between 0 and 100
* resting heart rate must remain within configured bounds

### Future Use

Body metrics will support:

* weight trends
* rolling weight averages
* progress toward target weight
* body-composition trends
* resting-heart-rate trends

---

## Food Entries

Table:

```text
food_entries
```

### Purpose

Stores individual food items.

A single meal may create several food entries.

Example:

```text
"I ate chicken, rice and vegetables for lunch."
```

may create:

```text
food_entry: chicken
food_entry: rice
food_entry: vegetables
```

All may reference the same raw event.

### Important Fields

```text
id
consumed_at
meal_type
food_name
quantity
unit
estimated_calories
protein_g
carbs_g
fat_g
fiber_g
is_estimated
source_event_id
```

### Field Meaning

`consumed_at`

When the food was consumed.

`meal_type`

Optional classification such as breakfast, lunch, dinner, or snack.

`food_name`

Name of the food.

`quantity`

Amount consumed.

`unit`

Unit associated with quantity.

Examples:

```text
g
kg
ml
piece
cup
serving
```

`estimated_calories`

Calories associated with the entry when available.

`protein_g`

Protein in grams.

`carbs_g`

Carbohydrates in grams.

`fat_g`

Fat in grams.

`fiber_g`

Fiber in grams.

`is_estimated`

Indicates whether nutrition information is estimated rather than directly known or measured.

`source_event_id`

Raw event from which the food entry was derived.

### Data Quality Rule

Missing nutrition values must remain missing.

For example:

```text
estimated_calories = null
protein_g = null
```

is preferable to inventing values.

Estimated nutrition information must be identifiable as estimated.

### Future Use

Food entries will support:

* daily calorie totals
* daily protein totals
* carbohydrate/fat/fiber totals
* nutrition completeness
* adherence to nutrition targets
* nutrition trends

---

## Activity Entries

Table:

```text
activity_entries
```

### Purpose

Stores general physical activity outside structured workout sessions.

### Important Fields

```text
id
recorded_at
steps
distance_km
active_minutes
calories_burned
source_event_id
```

### Field Meaning

`recorded_at`

Time or date associated with the activity.

`steps`

Step count.

`distance_km`

Distance traveled in kilometers.

`active_minutes`

Active minutes.

`calories_burned`

Calories burned when available.

`source_event_id`

Raw event from which the activity was derived.

### Validation

Values such as steps, distance, active minutes, and calories burned cannot be negative.

### Future Use

Activity entries will support:

* daily step totals
* 7-day step averages
* activity-target adherence
* active-minute trends
* distance trends

---

## Sleep Entries

Table:

```text
sleep_entries
```

### Purpose

Stores sleep information.

### Important Fields

```text
id
sleep_start
sleep_end
duration_minutes
quality_rating
notes
source_event_id
```

### Field Meaning

`sleep_start`

Beginning of the sleep period when known.

`sleep_end`

End of the sleep period when known.

`duration_minutes`

Total sleep duration.

`quality_rating`

Optional subjective sleep-quality rating.

Current accepted scale:

```text
1–10
```

`notes`

Optional information about sleep or recovery.

`source_event_id`

Raw event from which the sleep entry was derived.

### Future Use

Sleep entries will support:

* average sleep duration
* sleep-duration trends
* sleep-quality trends
* recovery context for workout recommendations

---

## Workout Sessions

Table:

```text
workout_sessions
```

### Purpose

Represents a completed workout session.

A workout session acts as the parent record for individual exercise sets.

### Important Fields

```text
id
started_at
workout_type
duration_minutes
notes
source_event_id
```

### Field Meaning

`started_at`

When the workout began.

`workout_type`

General workout classification.

Examples:

```text
chest
back
legs
arms
shoulders
cardio
full_body
```

For deterministic target adherence, `chest`, `back`, `legs`, `shoulders`,
`arms`, `biceps`, `triceps`, `push`, `pull`, `upper body`, and `lower body`
are classified as strength, alongside generic labels such as `strength`,
`weights`, `resistance`, `bodybuilding`, and `powerlifting`. Cardio is limited
to `cardio`, `running`, `cycling`, `swimming`, `walking`, `rowing`, and
`elliptical`; all other labels remain unclassified.

This field is currently flexible rather than a fixed enum.

`duration_minutes`

Total workout duration when available.

`notes`

Optional session-level notes.

`source_event_id`

Raw event from which the workout was derived.

### Relationship

```text
workout_session
      │
      ├── exercise_set
      ├── exercise_set
      └── exercise_set
```

### Future Use

Workout sessions will support:

* training frequency
* workout history
* body-part frequency
* session volume
* progression analysis
* planned-vs-actual comparison

---

## Exercise Sets

Table:

```text
exercise_sets
```

### Purpose

Stores individual exercise efforts belonging to a workout session.

### Important Fields

```text
id
workout_session_id
exercise_name
set_number
weight_kg
reps
duration_seconds
distance_km
rpe
```

### Field Meaning

`workout_session_id`

Parent workout session.

`exercise_name`

Exercise performed.

`set_number`

Optional set sequence within the exercise.

`weight_kg`

External resistance used.

`reps`

Number of repetitions.

`duration_seconds`

Duration for time-based exercises.

`distance_km`

Distance for distance-based exercises.

`rpe`

Rate of perceived exertion.

Current accepted range:

```text
0–10
```

### Supported Exercise Types

The model can represent resistance exercises:

```text
Bench Press
50 kg
10 reps
RPE 8
```

as well as duration or distance-based exercise:

```text
Running
1800 seconds
5 km
```

### Future Use

Exercise sets will support:

* training volume
* exercise progression
* load progression
* rep progression
* RPE trends
* strength retention during fat loss

---

## Source Event Relationships

Most structured records reference:

```text
source_event_id
```

This creates traceability from structured data back to natural-language input.

Example:

```text
raw_event #100
"I weighed 96.8 kg and walked 9200 steps."

        │
        ├── body_metric
        │     weight_kg = 96.8
        │     source_event_id = 100
        │
        └── activity_entry
              steps = 9200
              source_event_id = 100
```

Exercise sets are linked indirectly:

```text
raw_event
    ↓
workout_session
    ↓
exercise_sets
```

---

## Timestamp Model

The system distinguishes event timestamps from database insertion time.

The application timezone is:

```text
America/New_York
```

All new explicit domain timestamps must be timezone-aware. SQLAlchemy converts
them to UTC-naive values for SQLite storage and restores `timezone.utc` on
load. Calendar-day analytics must convert loaded values to
`America/New_York` before grouping by date.

Important domain timestamps include:

```text
raw_events.event_time
body_metrics.measured_at
food_entries.consumed_at
activity_entries.recorded_at
sleep_entries.sleep_start
sleep_entries.sleep_end
workout_sessions.started_at
```

These should represent when the real-world event occurred.

Example:

```text
User enters at:
September 12

User says:
"Yesterday I walked 8500 steps."
```

The activity should ultimately be associated with:

```text
September 11
```

not simply September 12.

Timestamp propagation and UTC normalization are implemented.

Legacy naive domain timestamps were audited for DST ambiguity/nonexistence,
interpreted as `America/New_York` wall time, and migrated to UTC-naive
storage. Historical `raw_events.created_at` values were intentionally left
unchanged because their original host-time semantics are uncertain.

---

## Current Analytics Limitation

Current summary functions primarily retrieve the latest N records.

For example:

```text
get_weight_summary(7)
```

currently means approximately:

```text
latest 7 weight measurements
```

not:

```text
weight measurements from the last 7 calendar days
```

Similarly, food totals currently operate over recent entries rather than true daily nutrition periods.

This behavior is temporary.

Date-aware analytics should be implemented after timestamp handling is corrected.

---

## Profile Data

User profile information is intentionally not stored as fitness events.

Current location:

```text
config/profile.json
```

Profile data includes:

```text
age
sex
height_cm
starting_weight_kg
target_weight_kg
goal
secondary_goals
average_daily_steps
training_days_per_week
```

Profile data provides relatively stable context.

## Coaching Targets

`CoachingTargets` is a typed, centrally configured object kept separate from
the profile because targets may change without changing the user's identity or
baseline. It currently defines daily calories, daily protein, daily steps,
weekly strength sessions, and weekly cardio sessions. The configuration lives
in `config/coaching_targets.json` and is validated when loaded. It is not a
database entity and does not alter historical fitness data. Future deterministic
adherence analytics will compare the production fitness context with these
targets before AI coaching is introduced.

The adherence output contains per-day nutrition and activity actuals, targets,
differences, percentages, and presence flags, plus period-level training
actuals versus proportionally scaled weekly targets and coverage counts.
Unknown days remain `null`; an unlogged day is not treated as zero or as a
target failure.

The compact coaching context combines this coverage with the production fitness
context and current `CoachingTargets`. Permission flags require majority
coverage (`ceil(days / 2)`) for nutrition and steps. Training adherence is
assessable only after a trustworthy workout-log completeness signal exists.
Classification completeness answers “can we classify the workout records we
have?”; logging completeness answers “do we have enough evidence about actual
workouts during the period?” They are different. Until that signal exists,
training assessment is disabled with reason
`workout_log_completeness_unknown`. These flags describe evidence sufficiency,
not qualitative performance; an absence of logs is never proof that behavior
did not occur.

Adherence coverage distinguishes a record existing, a specific metric being
available, and that metric being complete across all logged entries. A food
record with unknown calories remains a record, but calorie actuals and
percentages remain `null` when the day's logged entries are only partially
covered. Training counts are explicitly logged-session observations; they do
not prove that unlogged workouts did not occur. Classification coverage is
`null` when no sessions were logged.

Future coaching will consume `CoachingContext` and return the provider-neutral
`CoachingResponse` contract. It constrains domains, evidence status,
recommendation priority/basis, safety, text lengths, and list sizes. Matching
the schema does not establish factual grounding; a deterministic validator will
later check response claims and recommendations against context evidence and
permission flags.

The future coaching data flow is `CoachingContext` → provider → typed
`CoachingResponse` → deterministic grounding validator → approved response.
Grounding uses structured domains/metrics, evidence status, recommendation
basis, and context permission flags rather than keyword parsing. Pydantic
validation guarantees structure and vocabulary, not factual support; claims
that require unavailable adherence evidence are rejected.

Adherence percentages are rounded to one decimal place, summary averages to
two decimal places, and proportional weekly targets retain their decimal
values. Actual stored measurements are otherwise preserved.

Event tables represent observations and activities over time.

---

## Planned Future Entities

The current schema is not considered final.

Future requirements are expected to introduce entities for workout planning.

Conceptually:

```text
workout_plan
    │
    └── planned_exercises
```

These should remain separate from completed workout sessions.

This allows:

```text
planned workout
       ↓
completed workout
       ↓
comparison
       ↓
future recommendation
```

Additional schema changes should be introduced deliberately and documented through architecture decisions and migrations.

---

## Data Integrity Rules

The data model should continue to preserve the following invariants:

1. Raw natural-language input is preserved.
2. One user message creates one raw event.
3. Derived records remain traceable to their source event.
4. Structured values are validated before persistence.
5. Mixed ingestion is atomic.
6. Missing information remains missing.
7. Estimated information is identified as estimated.
8. Event timestamps represent real-world event time rather than merely insertion time.
9. Tests never write to the live fitness database.
10. AI-generated recommendations are not treated as measured historical facts.

The database represents **what happened**.

Analytics determine **what the history shows**.

The AI reasons about **what should happen next**.
Weight coverage is represented separately as `weight_days_logged` and
`weight_days_requested` (currently the 14-day context window). It describes
measurement evidence only, not adherence to a weight target or a weight-loss
rate. A gap is supported when logged days are fewer than requested; missing
measurements are never converted to zero.
