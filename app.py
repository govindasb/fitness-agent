from config.profile import load_profile
from database.connection import Base, engine
from database import schema


def initialize_database():
    Base.metadata.create_all(bind=engine)


def build_service():
    from agent.gemini_coach import GeminiFitnessCoach
    from agent.gemini_interpreter import GeminiFitnessInterpreter
    from agent.service import FitnessAgentService

    return FitnessAgentService(
        GeminiFitnessInterpreter(),
        GeminiFitnessCoach(),
    )


def _render_log_result(result: dict, output_fn):
    output_fn(f"Logging {result.get('status')}.")

    if result.get("raw_event_id") is not None:
        output_fn(f"Raw event: {result['raw_event_id']}")

    stored = result.get("stored", {})
    categories = [
        name
        for name, records in stored.items()
        if records
    ]

    output_fn(
        "Stored: "
        + (", ".join(categories) if categories else "nothing")
    )

    if result.get("warnings"):
        output_fn(
            "Warnings: "
            + "; ".join(result["warnings"])
        )

    if result.get("unparsed_fragments"):
        output_fn(
            "Unparsed: "
            + "; ".join(result["unparsed_fragments"])
        )

    if result.get("status") != "processed" and result.get("error"):
        output_fn(f"Failure: {result['error']}")


def _render_coaching(response, output_fn):
    output_fn("Summary")
    output_fn(response.summary)

    sections = (
        (
            "Observations",
            response.observations,
            lambda item: f"[{item.domain.value}] {item.message}",
        ),
        (
            "Recommendations",
            response.recommendations,
            lambda item: f"[{item.priority.value}] {item.action}",
        ),
        (
            "Data gaps",
            response.data_gaps,
            lambda item: (
                f"[{item.domain.value}] "
                f"{item.missing_information}"
            ),
        ),
    )

    for title, items, formatter in sections:
        if items:
            output_fn(title)

            for item in items:
                output_fn(f"- {formatter(item)}")

    if response.safety.medical_escalation_needed:
        output_fn("Safety")

        if response.safety.reason:
            output_fn(response.safety.reason)


def _render_coaching_error(exc, output_fn):
    from agent.coach import CoachingStructureError
    from agent.coaching_grounding import CoachingGroundingError
    from agent.gemini_coach import GeminiCoachingError

    if isinstance(exc, GeminiCoachingError):
        label = "Provider failure"
    elif isinstance(exc, CoachingStructureError):
        label = "Structural validation failure"
    elif isinstance(exc, CoachingGroundingError):
        label = "Grounding failure"
    else:
        label = "Unexpected coaching error"

    output_fn(f"{label}: {exc}")

    if isinstance(exc, CoachingGroundingError):
        for violation in exc.violations:
            details = [
                f"section={violation.section}",
                f"code={violation.code}",
            ]

            if violation.domain is not None:
                details.append(
                    f"domain={violation.domain}"
                )

            if violation.metric is not None:
                details.append(
                    f"metric={violation.metric}"
                )

            if violation.index is not None:
                details.append(
                    f"index={violation.index}"
                )

            output_fn(
                f"- {', '.join(details)}: "
                f"{violation.message}"
            )


def run_cli(service, input_fn=input, output_fn=print):
    while True:
        try:
            user_input = input_fn("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            output_fn("Goodbye.")
            return

        if user_input.lower() == "exit":
            output_fn("Goodbye.")
            return

        if not user_input:
            continue

        if user_input.lower() == "coach":
            try:
                response = service.get_coaching()
                _render_coaching(response, output_fn)
            except Exception as exc:
                _render_coaching_error(exc, output_fn)

            continue

        try:
            result = service.log(user_input)
            _render_log_result(result, output_fn)
        except Exception as exc:
            output_fn(f"Logging failure: {exc}")


def main():
    print("Fitness Agent")

    initialize_database()
    print("Database initialized successfully.")

    profile = load_profile()

    print(
        f"Profile loaded: {profile['age']} year old "
        f"{profile['sex']}, target weight "
        f"{profile['target_weight_kg']} kg"
    )

    print(
        "Ready. Type 'exit' to stop or "
        "'coach' for grounded coaching."
    )

    run_cli(build_service())


if __name__ == "__main__":
    main()