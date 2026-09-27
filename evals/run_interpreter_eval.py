from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from evals.comparator import aggregate_results, compare_case


DATASET_PATH = Path(__file__).with_name("fitness_interpreter_cases.json")
RESULTS_DIR = Path(__file__).with_name("results")
GEMINI_DEFAULT_DELAY_SECONDS = 5.0
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 2.0


def load_cases(path: Path = DATASET_PATH) -> list[dict]:
    return json.loads(path.read_text())["cases"]


def create_interpreter(provider: str, model: str | None = None):
    if provider == "openai":
        from agent.openai_interpreter import OpenAIFitnessInterpreter

        return OpenAIFitnessInterpreter(model=model)
    if provider == "gemini":
        from agent.gemini_interpreter import GeminiFitnessInterpreter

        return GeminiFitnessInterpreter(model=model)
    raise ValueError(f"Unsupported provider: {provider}")


def _usage(interpreter) -> dict[str, int | None]:
    return interpreter.last_usage or {}


def default_delay_seconds(provider: str) -> float:
    return GEMINI_DEFAULT_DELAY_SECONDS if provider == "gemini" else 0.0


def _is_rate_limit_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        for target in (current, getattr(current, "response", None)):
            if target is None:
                continue
            if getattr(target, "status_code", None) == 429:
                return True
            if getattr(target, "status", None) == 429:
                return True
            if getattr(target, "code", None) == 429:
                return True
        message = str(current).lower()
        if (
            "429" in message
            or "resource_exhausted" in message
            or "rate limit" in message
            or "rate_limit" in message
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


def _retry_after_seconds(error: BaseException) -> float | None:
    def as_seconds(value) -> float | None:
        if isinstance(value, dict):
            value = value.get("seconds", value.get("retryDelay"))
        else:
            value = getattr(value, "seconds", value)
        if isinstance(value, str) and value.endswith("s"):
            value = value[:-1]
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    current: BaseException | None = error
    while current is not None:
        for name in ("retry_after", "retry_delay", "retry_delay_seconds"):
            value = getattr(current, name, None)
            if value is not None:
                delay = as_seconds(value)
                if delay is not None:
                    return delay
        response = getattr(current, "response", None)
        headers = getattr(response, "headers", None)
        if headers is not None:
            value = headers.get("retry-after") or headers.get("Retry-After")
            if value is not None:
                delay = as_seconds(value)
                if delay is not None:
                    return delay
        current = current.__cause__ or current.__context__
    return None


def _retry_delay(error: BaseException, retry_index: int) -> float:
    indicated = _retry_after_seconds(error)
    if indicated is not None:
        return indicated
    return RETRY_BACKOFF_SECONDS * (2**retry_index)


def run_case(
    case: dict,
    interpreter,
    *,
    max_retries: int = MAX_RETRIES,
    sleep_fn=time.sleep,
) -> dict:
    started = time.perf_counter()
    retry_count = 0
    while True:
        try:
            actual = interpreter.interpret(
                case["raw_text"],
                reference=datetime.fromisoformat(case["reference"]),
            )
            break
        except Exception as exc:
            if not _is_rate_limit_error(exc) or retry_count >= max_retries:
                return {
                    "id": case["id"],
                    "passed": False,
                    "status": "api_error",
                    "error": str(exc),
                    "retry_count": retry_count,
                    "latency_seconds": round(time.perf_counter() - started, 3),
                    "usage": _usage(interpreter),
                }
            sleep_fn(_retry_delay(exc, retry_count))
            retry_count += 1
    result = compare_case(case, actual)
    result.update(
        status="passed" if result["passed"] else "semantic_failure",
        retry_count=retry_count,
        latency_seconds=round(time.perf_counter() - started, 3),
        usage=_usage(interpreter),
        actual=actual.model_dump(mode="json"),
    )
    return result


def run_cases(
    cases: list[dict],
    interpreter,
    *,
    delay_seconds: float = 0.0,
    sleep_fn=time.sleep,
) -> list[dict]:
    results = []
    for index, case in enumerate(cases):
        if index and delay_seconds > 0:
            sleep_fn(delay_seconds)
        results.append(run_case(case, interpreter, sleep_fn=sleep_fn))
    return results


def _print_failure(result: dict):
    if result["status"] == "api_error":
        print(f"  provider error: {result['error']}")
        return
    labels = (
        ("hallucinated", "hallucinated"),
        ("missed", "missed"),
        ("incorrect", "incorrect"),
        ("unexpected_domains", "unexpected domains"),
        ("missing_domains", "missing domains"),
        ("metadata_failures", "metadata"),
    )
    for key, label in labels:
        if result.get(key):
            print(f"  {label}: {json.dumps(result[key], default=str)}")


def _aggregate_usage(results: list[dict]) -> dict[str, int | None]:
    aggregate = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        values = [
            result.get("usage", {}).get(key)
            for result in results
            if result.get("usage", {}).get(key) is not None
        ]
        aggregate[key] = sum(values) if values else None
    return aggregate


def _write_report(
    provider: str,
    model: str,
    cases: list[dict],
    results: list[dict],
    metrics: dict,
) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_model = "".join(character if character.isalnum() else "-" for character in model)
    path = RESULTS_DIR / f"{timestamp}-{provider}-{safe_model}.json"
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "case_ids": [case["id"] for case in cases],
        "case_results": results,
        "metrics": metrics,
        "usage": _aggregate_usage(results),
    }
    path.write_text(json.dumps(report, indent=2) + "\n")
    return path


def main():
    parser = argparse.ArgumentParser(description="Run live API fitness extraction evaluations.")
    parser.add_argument(
        "--provider",
        choices=("openai", "gemini"),
        default="openai",
        help="Explicit interpreter provider (default: openai)",
    )
    parser.add_argument("--model", help="Provider-specific model override")
    parser.add_argument("--limit", type=int, help="Run only the first N selected cases")
    parser.add_argument("--case", help="Run one case by ID")
    parser.add_argument(
        "--delay-seconds",
        type=float,
        help="Delay between cases; Gemini defaults to 5 seconds, OpenAI to 0.",
    )
    parser.add_argument("--json-report", action="store_true", help="Write an ignored JSON result")
    args = parser.parse_args()

    cases = load_cases()
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error(f"unknown case: {args.case}")
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be at least 1")
        cases = cases[: args.limit]

    if args.delay_seconds is not None and args.delay_seconds < 0:
        parser.error("--delay-seconds must be non-negative")
    delay_seconds = (
        args.delay_seconds
        if args.delay_seconds is not None
        else default_delay_seconds(args.provider)
    )
    interpreter = create_interpreter(args.provider, args.model)
    print("Fitness Interpreter Eval (LIVE API)")
    print(
        "Calls the selected model provider directly; does not write RawEvents, "
        "structured records, or fitness.db."
    )
    print(f"Provider: {args.provider}")
    print(f"Model: {interpreter.model}")
    print(f"Delay between cases: {delay_seconds:g} seconds")
    print(f"Cases: {len(cases)}\n")

    results = run_cases(
        cases,
        interpreter,
        delay_seconds=delay_seconds,
    )
    for case, result in zip(cases, results):
        print(f"{'PASS' if result['passed'] else 'FAIL'} {case['id']}")
        if not result["passed"]:
            _print_failure(result)

    metrics = aggregate_results(cases, results)
    metrics["total_retries"] = sum(
        result.get("retry_count", 0) for result in results
    )
    usage = _aggregate_usage(results)
    print("\nSummary:")
    print(f"Passed: {metrics['passed_cases']}/{metrics['total_cases']}")
    print(f"Pass rate: {metrics['passed_cases'] / metrics['total_cases']:.1%}")
    print(f"Exact structured-field accuracy: {metrics['exact_structured_field_accuracy']}")
    print(f"Hallucinated fields: {metrics['hallucinated_field_count']}")
    print(f"Hallucination rate: {metrics['hallucination_rate']:.1%}")
    print(f"Missed fields: {metrics['missed_field_count']}")
    print(f"Incorrect values: {metrics['incorrect_value_count']}")
    print(f"Unexpected domains: {metrics['unexpected_domain_count']}")
    print(f"Missing domains: {metrics['missing_domain_count']}")
    print(f"API errors: {metrics['api_error_count']}")
    print(f"Retries: {metrics['total_retries']}")
    print(f"Average latency: {metrics['average_latency_seconds']} seconds")
    if metrics["failed_case_ids"]:
        print(f"Failed case IDs: {', '.join(metrics['failed_case_ids'])}")
    print(
        "Usage: "
        f"{usage['input_tokens']} input / {usage['output_tokens']} output / "
        f"{usage['total_tokens']} total tokens"
    )
    print("\nBy tag:")
    for tag, values in metrics["by_tag"].items():
        print(f"  {tag}: {values['passed']}/{values['total']} ({values['pass_rate']:.1%})")

    if args.json_report:
        print(
            "\nJSON report: "
            f"{_write_report(args.provider, interpreter.model, cases, results, metrics)}"
        )


if __name__ == "__main__":
    main()
