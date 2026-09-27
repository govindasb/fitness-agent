from __future__ import annotations

from datetime import datetime
import math
import re
from typing import Any


DOMAINS = (
    "body_metrics",
    "food_entries",
    "activities",
    "sleep_entries",
    "workouts",
)
MISSING = object()


def _tokens(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for name, index in re.findall(r"([^.\[\]]+)|\[(\d+)\]", path):
        tokens.append(int(index) if index else name)
    return tokens


def get_path(value: Any, path: str) -> Any:
    current = value
    for token in _tokens(path):
        try:
            current = current[token]
        except (KeyError, IndexError, TypeError):
            return MISSING
    return current


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def values_equal(expected: Any, actual: Any) -> bool:
    expected_time = _as_datetime(expected)
    actual_time = _as_datetime(actual)
    if expected_time is not None and actual_time is not None:
        return expected_time.timestamp() == actual_time.timestamp()
    if (
        isinstance(expected, (int, float))
        and not isinstance(expected, bool)
        and isinstance(actual, (int, float))
        and not isinstance(actual, bool)
    ):
        return math.isclose(float(expected), float(actual), abs_tol=1e-9)
    return expected == actual


def _non_null_leaves(value: Any, path: str):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _non_null_leaves(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _non_null_leaves(child, f"{path}[{index}]")
    elif value is not None:
        yield path, value


def _compare_exact(expected: Any, actual: Any, path: str, result: dict):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            for key, value in expected.items():
                child_path = f"{path}.{key}" if path else key
                _compare_exact(value, MISSING, child_path, result)
            return
        for key, value in expected.items():
            child_path = f"{path}.{key}" if path else key
            _compare_exact(value, actual.get(key, MISSING), child_path, result)
        return

    if isinstance(expected, list):
        if not isinstance(actual, list):
            for index, value in enumerate(expected):
                _compare_exact(value, MISSING, f"{path}[{index}]", result)
            return
        for index, value in enumerate(expected):
            child = actual[index] if index < len(actual) else MISSING
            _compare_exact(value, child, f"{path}[{index}]", result)
        for index in range(len(expected), len(actual)):
            for leaf_path, value in _non_null_leaves(actual[index], f"{path}[{index}]"):
                result["hallucinated"].append(
                    {"path": leaf_path, "expected": None, "actual": value}
                )
        return

    result["exact_fields"] += 1
    if actual is MISSING or (expected is not None and actual is None):
        result["missed"].append({"path": path, "expected": expected})
    elif values_equal(expected, actual):
        result["matched_fields"] += 1
    else:
        result["incorrect"].append(
            {"path": path, "expected": expected, "actual": actual}
        )


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def compare_case(case: dict, actual: Any) -> dict:
    if hasattr(actual, "model_dump"):
        actual = actual.model_dump(mode="json")
    expected = case["expected"]
    actual_parsed = actual.get("parsed_input", {})
    expected_parsed = expected.get("parsed_input", {})
    result = {
        "id": case["id"],
        "passed": False,
        "exact_fields": 0,
        "matched_fields": 0,
        "hallucinated": [],
        "missed": [],
        "incorrect": [],
        "unexpected_domains": [],
        "missing_domains": [],
        "metadata_failures": [],
    }

    for domain in DOMAINS:
        expected_records = expected_parsed.get(domain, [])
        actual_records = actual_parsed.get(domain, [])
        if expected_records and not actual_records:
            result["missing_domains"].append(domain)
        if not expected_records and actual_records:
            result["unexpected_domains"].append(domain)
            if domain not in expected_parsed:
                for leaf_path, value in _non_null_leaves(
                    actual_records,
                    f"parsed_input.{domain}",
                ):
                    result["hallucinated"].append(
                        {"path": leaf_path, "expected": None, "actual": value}
                    )

    _compare_exact(expected_parsed, actual_parsed, "parsed_input", result)

    for path in expected.get("null_required", []):
        full_path = path if path.startswith("parsed_input.") else f"parsed_input.{path}"
        value = get_path(actual, full_path)
        if value is not MISSING and value is not None:
            result["hallucinated"].append(
                {"path": full_path, "expected": None, "actual": value}
            )

    if expected.get("warning_required") and not actual.get("warnings"):
        result["metadata_failures"].append("warning required")

    actual_fragments = _normalize_text(" ".join(actual.get("unparsed_fragments", [])))
    for fragment in expected.get("unparsed_contains", []):
        normalized = _normalize_text(fragment)
        if not actual_fragments or (
            normalized not in actual_fragments
            and actual_fragments not in normalized
        ):
            result["metadata_failures"].append(
                f"unparsed fragment missing: {fragment}"
            )

    result["passed"] = not any(
        result[key]
        for key in (
            "hallucinated",
            "missed",
            "incorrect",
            "unexpected_domains",
            "missing_domains",
            "metadata_failures",
        )
    )
    return result


def aggregate_results(cases: list[dict], results: list[dict]) -> dict:
    semantic = [result for result in results if result.get("status") != "api_error"]
    passed = sum(bool(result.get("passed")) for result in semantic)
    exact_fields = sum(result.get("exact_fields", 0) for result in semantic)
    matched_fields = sum(result.get("matched_fields", 0) for result in semantic)
    hallucinated = sum(len(result.get("hallucinated", [])) for result in semantic)

    by_tag = {}
    cases_by_id = {case["id"]: case for case in cases}
    for result in results:
        for tag in cases_by_id[result["id"]].get("tags", []):
            bucket = by_tag.setdefault(tag, {"total": 0, "passed": 0})
            bucket["total"] += 1
            bucket["passed"] += int(bool(result.get("passed")))
    for bucket in by_tag.values():
        bucket["pass_rate"] = round(bucket["passed"] / bucket["total"], 4)

    return {
        "total_cases": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "failed_case_ids": [
            result["id"] for result in results if not result.get("passed")
        ],
        "api_error_count": sum(result.get("status") == "api_error" for result in results),
        "average_latency_seconds": (
            round(
                sum(result.get("latency_seconds", 0.0) for result in results)
                / len(results),
                3,
            )
            if results
            else None
        ),
        "exact_structured_field_accuracy": (
            round(matched_fields / exact_fields, 4) if exact_fields else None
        ),
        "hallucinated_field_count": hallucinated,
        "hallucination_rate": (
            round(hallucinated / (exact_fields + hallucinated), 4)
            if exact_fields + hallucinated
            else 0.0
        ),
        "missed_field_count": sum(len(result.get("missed", [])) for result in semantic),
        "incorrect_value_count": sum(len(result.get("incorrect", [])) for result in semantic),
        "unexpected_domain_count": sum(len(result.get("unexpected_domains", [])) for result in semantic),
        "missing_domain_count": sum(len(result.get("missing_domains", [])) for result in semantic),
        "by_tag": dict(sorted(by_tag.items())),
    }
