from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from agent.coach import CoachingStructureError, FitnessCoach
from agent.coaching_grounding import CoachingGroundingError
from agent.coaching_grounding import validate_coaching_response
from models.coaching_response import CoachingResponse
from pydantic import ValidationError


DATASET_PATH = Path(__file__).with_name("coaching_cases.json")
RESULTS_DIR = Path(__file__).with_name("results")


def load_cases(path: Path = DATASET_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def create_coach(provider: str, model: str | None = None) -> FitnessCoach:
    if provider == "gemini":
        from agent.gemini_coach import GeminiFitnessCoach

        return GeminiFitnessCoach(model=model)
    raise ValueError(f"Unsupported provider: {provider}")


def _semantic_failures(case: dict, response: CoachingResponse) -> list[dict]:
    expected = case.get("expectations", {})
    failures = []
    for observation in response.observations:
        domain = getattr(observation.domain, "value", observation.domain)
        evidence_status = getattr(observation.evidence_status, "value", observation.evidence_status)
        if expected.get("weight_sufficient_forbidden") and domain == "weight" and evidence_status == "sufficient":
            failures.append({"code": "sparse_weight_sufficient", "message": "Sparse weight evidence cannot be sufficient."})
    if expected.get("forbid_adherence_dependencies"):
        for index, recommendation in enumerate(response.recommendations):
            if recommendation.requires_adherence_evidence:
                failures.append({"code": "adherence_dependency_forbidden", "index": index})
    allowed_bases = expected.get("allowed_bases")
    if allowed_bases is not None:
        for index, recommendation in enumerate(response.recommendations):
            basis = getattr(recommendation.basis, "value", recommendation.basis)
            if basis not in allowed_bases:
                failures.append({"code": "recommendation_basis_not_allowed", "index": index})
    required_gaps = set(expected.get("required_data_gap_domains", []))
    actual_gaps = {getattr(gap.domain, "value", gap.domain) for gap in response.data_gaps}
    for domain in sorted(required_gaps - actual_gaps):
        failures.append({"code": "required_data_gap_missing", "domain": domain})
    if "expected_medical_escalation" in expected and response.safety.medical_escalation_needed != expected["expected_medical_escalation"]:
        failures.append({"code": "unexpected_safety_escalation"})
    return failures


def evaluate_case(case: dict, coach: FitnessCoach) -> dict:
    started = time.perf_counter()
    result = {
        "id": case["id"],
        "status": "passed",
        "passed": False,
        "expectations": case.get("expectations", {}),
    }
    try:
        raw_response = coach.coach(case["context"])
        try:
            response = CoachingResponse.model_validate(raw_response)
        except ValidationError as exc:
            raise CoachingStructureError(exc) from exc
        validate_coaching_response(case["context"], response)
    except CoachingStructureError as exc:
        result.update(status="structural_failure", error=str(exc))
    except CoachingGroundingError as exc:
        result.update(
            status="grounding_failure",
            violations=[v.__dict__ for v in exc.violations],
            response=response.model_dump(mode="json"),
        )
    except Exception as exc:
        result.update(status="provider_error", error=str(exc))
    else:
        failures = _semantic_failures(case, response)
        if failures:
            result.update(status="semantic_failure", failures=failures)
        else:
            result["passed"] = True
        result["response"] = response.model_dump(mode="json")
    result["latency_seconds"] = round(time.perf_counter() - started, 4)
    return result


def run_cases(cases: list[dict], coach: FitnessCoach) -> list[dict]:
    return [evaluate_case(case, coach) for case in cases]


def summarize(results: list[dict]) -> dict:
    counts = {status: sum(result["status"] == status for result in results) for status in ("passed", "provider_error", "structural_failure", "grounding_failure", "semantic_failure")}
    total = len(results)
    grounding_violations = [violation for result in results for violation in result.get("violations", [])]
    semantic_failures = [failure for result in results for failure in result.get("failures", [])]
    return {
        "total_cases": total,
        "passed": counts["passed"],
        "failed": total - counts["passed"],
        "pass_rate": round(counts["passed"] / total, 4) if total else 0,
        **counts,
        "adherence_permission_violations": sum(v.get("code") == "adherence_permission_denied" for v in grounding_violations),
        "unsupported_safety_escalations": sum(f.get("code") == "unexpected_safety_escalation" for f in semantic_failures),
        "average_latency_seconds": round(sum(result.get("latency_seconds", 0) for result in results) / total, 4) if total else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate structured fitness coaching output (live only when explicitly invoked).")
    parser.add_argument("--provider", choices=("gemini",), default="gemini")
    parser.add_argument("--model")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case")
    parser.add_argument("--json-report", action="store_true")
    args = parser.parse_args()
    cases = load_cases()
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error(f"unknown case: {args.case}")
    if args.limit is not None:
        cases = cases[:args.limit]
    coach = create_coach(args.provider, args.model)
    print("Coaching Eval (LIVE API)")
    print("Calls the selected coach provider directly; does not write RawEvents, structured records, or fitness.db.")
    results = run_cases(cases, coach)
    for result in results:
        print(("PASS " if result["passed"] else "FAIL ") + result["id"])
    metrics = summarize(results)
    print(json.dumps(metrics, indent=2))
    if args.json_report:
        RESULTS_DIR.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = RESULTS_DIR / f"{stamp}-coaching-{args.provider}.json"
        path.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "provider": args.provider, "results": results, "metrics": metrics}, indent=2) + "\n", encoding="utf-8")
        print(f"Report: {path}")


if __name__ == "__main__":
    main()
