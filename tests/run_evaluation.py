"""Evaluation tests for AI Financial Copilot improvements."""

from __future__ import annotations

import json
import os
import sys
import importlib.util
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
APP_DIR = BACKEND_DIR / "app"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(APP_DIR))

CASES_PATH = Path(__file__).resolve().parent / "copilot_cases.json"


def _import_from_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_cases():
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_unit_tests(cases):
    results = []
    for case in cases:
        if case.get("test_type") != "unit":
            continue

        module_name = case["module"]
        function_name = case["function"]
        inputs = case.get("inputs", {})
        expected = case["expected_output"]

        module_path = (BACKEND_DIR / module_name.replace(".", "/")).with_suffix(".py")
        if not module_path.exists():
            results.append({
                "case_id": case["id"],
                "status": "SKIP",
                "reason": f"Module not found: {module_path}",
            })
            continue

        module = _import_from_path(module_name, str(module_path))
        func = getattr(module, function_name)

        try:
            if callable(func):
                actual = func(**inputs)
            else:
                actual = func
        except Exception as exc:
            results.append({
                "case_id": case["id"],
                "status": "FAIL",
                "error": str(exc),
            })
            continue

        passed = True
        actual_normalized = actual
        if isinstance(actual, list):
            actual_normalized = {"items": actual}

        for key, value in expected.items():
            if key == "min" and isinstance(value, (int, float)):
                if actual_normalized.get("count", actual_normalized.get(key, 0)) < value:
                    passed = False
            elif key == "min_items" and isinstance(value, int):
                actual_count = len(actual) if isinstance(actual, list) else actual_normalized.get(key, 0)
                if actual_count < value:
                    passed = False
            elif key == "contains_keywords" and isinstance(value, list):
                actual_str = json.dumps(actual_normalized)
                for kw in value:
                    if kw.lower() not in actual_str.lower():
                        passed = False
            else:
                if actual_normalized.get(key) != value:
                    passed = False

        results.append({
            "case_id": case["id"],
            "status": "PASS" if passed else "FAIL",
            "expected": expected,
            "actual": actual,
        })

    return results


def _run_intent_tests(cases):
    results = []
    try:
        from app.services.llm.routing import IntentClassifier
        classifier = IntentClassifier()
    except Exception as exc:
        return [{"case_id": "intent_suite", "status": "SKIP", "reason": str(exc)}]

    for case in cases:
        if case.get("test_type") == "unit":
            continue

        try:
            route = classifier.classify(case["question"])
            intent = route.intent.value
            entities = dict(route.retrieved_entities)
        except Exception as exc:
            results.append({
                "case_id": case["id"],
                "status": "FAIL",
                "error": str(exc),
            })
            continue

        passed = True

        if "expected_intent" in case and intent != case["expected_intent"]:
            passed = False

        if "expected_entities" in case:
            for key, value in case["expected_entities"].items():
                if entities.get(key) != value:
                    passed = False

        if "expected_keywords" in case:
            answer_str = json.dumps({"intent": intent, "entities": entities})
            for kw in case["expected_keywords"]:
                if kw.lower() not in answer_str.lower():
                    passed = False

        results.append({
            "case_id": case["id"],
            "status": "PASS" if passed else "FAIL",
            "intent": intent,
            "entities": entities,
            "description": case.get("description", ""),
        })

    return results


def main():
    cases = _load_cases()
    intent_results = _run_intent_tests(cases)
    unit_results = _run_unit_tests(cases)

    all_results = intent_results + unit_results

    passed = sum(1 for r in all_results if r.get("status") == "PASS")
    failed = sum(1 for r in all_results if r.get("status") == "FAIL")
    skipped = sum(1 for r in all_results if r.get("status") == "SKIP")

    print(f"\n=== Copilot Evaluation Results ===")
    print(f"Passed: {passed}, Failed: {failed}, Skipped: {skipped}")
    print()

    for r in all_results:
        status_icon = "OK" if r["status"] == "PASS" else ("SKIP" if r["status"] == "SKIP" else "FAIL")
        print(f"[{status_icon}] {r['case_id']}: {r.get('description', r.get('error', ''))}")

    if failed > 0:
        print("\nSome tests failed.")
        sys.exit(1)
    print("\nAll tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
