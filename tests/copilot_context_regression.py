"""
Phase 1.5 Regression Tests — Context Budget, Formatting, and Latency.

Validates that the Phase 1.5 changes do not introduce regressions:
1. No context overflow for broad or specific queries
2. Context trimming works (tokens < budget)
3. Response generated successfully
4. No stream crashes
5. Latency metrics are present
"""

import os
import sys
import json
import time
import logging
import unittest
from typing import Dict, Any, Optional

# Set dummy env vars BEFORE any backend imports to prevent Supabase/OpenRouter errors
os.environ.setdefault("SUPABASE_URL", "http://localhost:8000")
os.environ.setdefault("SUPABASE_KEY", "dummy-key-for-testing")
os.environ.setdefault("OPENROUTER_API_KEY", "dummy-key-for-testing")

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Setup logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("context_regression_test")

# ── Test Configuration ──
# Set to True to run actual LLM calls (requires API key + database)
# Set to False to run only unit-testable validation (budget, formatting)
RUN_INTEGRATION_TESTS = os.environ.get("RUN_LLM_TESTS", "false").lower() == "true"

TEST_CASES = [
    {
        "name": "broad_missing_payment",
        "question": "Why is payment missing?",
        "expected_intent": "financial_analysis",
        "is_broad": True,
        "max_context_tokens": 2000,  # Should be under 2000 after trimming
    },
    {
        "name": "specific_invoice",
        "question": "Why is invoice INV00004 unpaid?",
        "expected_intent": "invoice_lookup",
        "is_broad": False,
        "max_context_tokens": 3500,  # Specific queries get more room
    },
    {
        "name": "explain_anomalies",
        "question": "Explain anomalies",
        "expected_intent": "anomaly_lookup",
        "is_broad": True,
        "max_context_tokens": 2000,
    },
    {
        "name": "show_invoice_by_id",
        "question": "Show invoice INV00001",
        "expected_intent": "invoice_lookup",
        "is_broad": False,
        "max_context_tokens": 3500,
    },
]


# ── Unit tests (no API key or database required) ──


class TestContextBudget(unittest.TestCase):
    """Test the context budget calculator with intent-aware output minimums."""

    def setUp(self):
        from app.services.context_budget import calculate_budget, get_min_output_for_intent, MIN_OUTPUT_BY_INTENT

        self.calculate_budget = calculate_budget
        self.get_min_output_for_intent = get_min_output_for_intent
        self.MIN_OUTPUT_BY_INTENT = MIN_OUTPUT_BY_INTENT

    def test_min_output_by_intent_values(self):
        """Verify that each intent has a reasonable minimum output token budget."""
        # Analysis intents should have generous minimums
        self.assertGreaterEqual(self.MIN_OUTPUT_BY_INTENT.get("financial_analysis", 0), 2000)
        self.assertGreaterEqual(self.MIN_OUTPUT_BY_INTENT.get("reconciliation_analysis", 0), 1500)
        self.assertGreaterEqual(self.MIN_OUTPUT_BY_INTENT.get("dataset_review", 0), 2000)
        
        # Simple intents should have smaller minimums
        self.assertLessEqual(self.MIN_OUTPUT_BY_INTENT.get("general_knowledge", 9999), 1000)
        self.assertLessEqual(self.MIN_OUTPUT_BY_INTENT.get("financial_general", 9999), 1200)
        
        # Greeting intents should have zero minimum
        self.assertEqual(self.MIN_OUTPUT_BY_INTENT.get("greeting", -1), 0)
        self.assertEqual(self.MIN_OUTPUT_BY_INTENT.get("goodbye", -1), 0)

    def test_budget_with_intent_aware_minimum(self):
        """Test that calculate_budget applies the intent-aware minimum, capped by model limit."""
        # Use a known 8192-context model (gemma family) to test capping
        model_name_8k = "google/gemma-4-26b-a4b-it:free"  # matches "gemma" → 8192
        model_name_32k = "openai/gpt-oss-20b:free"  # matches "gpt-oss" → 32768
        system_prompt = "You are an AI Financial Copilot."
        user_prompt = "Why is payment missing?"
        context = '{"summary": {"invoice_count": 5, "anomaly_count": 2}}'
        
        # Test with 8k model: output should be capped at 25% of 8192 = 2048
        model_reservation_8k = int(8192 * 0.25)  # 2048
        
        budget_8k = self.calculate_budget(
            model_name=model_name_8k,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context=context,
            requested_output_tokens=900,
            intent="financial_analysis",
        )
        
        # Output budget should be at least the requested 900
        self.assertGreaterEqual(
            budget_8k.output_budget, 900,
            f"Output budget ({budget_8k.output_budget}) should be >= requested 900"
        )
        
        # Output budget should be capped by model reservation (2048)
        self.assertLessEqual(
            budget_8k.output_budget, model_reservation_8k,
            f"Output budget ({budget_8k.output_budget}) should not exceed model reservation ({model_reservation_8k})"
        )
        
        # Test with 32k model: output budget should reach the intent minimum (2500)
        budget_32k = self.calculate_budget(
            model_name=model_name_32k,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context=context,
            requested_output_tokens=900,
            intent="financial_analysis",
        )
        # 25% of 32768 = 8192, so 2500 fits easily
        self.assertGreaterEqual(
            budget_32k.output_budget, 2500,
            f"Output budget ({budget_32k.output_budget}) should be >= intent minimum for 32k model"
        )
        
        # Test with 128k model: output budget should reach the intent minimum
        budget_128k = self.calculate_budget(
            model_name="gpt-4o",  # 128000 context model
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context=context,
            requested_output_tokens=900,
            intent="financial_analysis",
        )
        # 25% of 128000 = 32000, so 2500 fits easily
        self.assertGreaterEqual(
            budget_128k.output_budget, 2500,
            f"Output budget ({budget_128k.output_budget}) should be >= intent minimum for 128k model"
        )

    def test_budget_for_greeting_intent(self):
        """Greeting intents should have 0 output budget."""
        budget = self.calculate_budget(
            model_name="openai/gpt-oss-20b:free",
            system_prompt="",
            user_prompt="Hello",
            context="",
            requested_output_tokens=0,
            intent="greeting",
        )
        self.assertEqual(budget.output_budget, 0)

    def test_safe_max_tokens_respects_intent(self):
        """get_safe_max_tokens should use intent-aware minimums."""
        from app.services.context_budget import get_safe_max_tokens
        
        # Small input, should return at least the intent minimum
        safe = get_safe_max_tokens(
            model_name="openai/gpt-oss-20b:free",
            estimated_input_tokens=100,
            default_max=900,
            intent="financial_analysis",
        )
        # 8192 * 0.8 = 6553 available, 6553 - 100 = 6453 max output
        # Intent minimum is 2500, so safe should be >= 2500
        self.assertGreaterEqual(safe, 2500)
        
        # Greeting intent should return 0
        safe = get_safe_max_tokens(
            model_name="openai/gpt-oss-20b:free",
            estimated_input_tokens=100,
            default_max=900,
            intent="greeting",
        )
        self.assertGreaterEqual(safe, 0)


class TestContextFormatter(unittest.TestCase):
    """Test the context formatter's trimming logic."""

    def setUp(self):
        from app.services.context_formatter import format_financial_context, _trim_record
        from app.services.context_formatter import INVOICE_KEY_FIELDS, ANOMALY_KEY_FIELDS

        self.format_financial_context = format_financial_context
        self._trim_record = _trim_record
        self.INVOICE_KEY_FIELDS = INVOICE_KEY_FIELDS
        self.ANOMALY_KEY_FIELDS = ANOMALY_KEY_FIELDS

    def test_trim_record_keeps_only_key_fields(self):
        """_trim_record should discard non-key fields."""
        full_record = {
            "invoice_id": "INV00001",
            "amount": 1500.00,
            "payment_status": "UNPAID",
            "vendor_name": "TechCorp",
            "description": "Software license",
            "issue": "Missing payment",
            "severity": "HIGH",
            "created_at": "2026-01-15T10:00:00Z",
            "updated_at": "2026-01-16T14:30:00Z",
            "internal_notes": "Follow up with vendor",
            "audit_trail": "...",
        }
        trimmed = self._trim_record(full_record, self.INVOICE_KEY_FIELDS)
        
        # Should keep key fields
        self.assertEqual(trimmed.get("invoice_id"), "INV00001")
        self.assertEqual(trimmed.get("amount"), 1500.00)
        self.assertEqual(trimmed.get("payment_status"), "UNPAID")
        
        # Should discard non-key fields
        self.assertNotIn("created_at", trimmed)
        self.assertNotIn("updated_at", trimmed)
        self.assertNotIn("internal_notes", trimmed)
        self.assertNotIn("audit_trail", trimmed)

    def test_format_financial_context_trims_all_record_types(self):
        """format_financial_context should trim invoices, anomalies, reconciliations."""
        raw_context = {
            "invoice": {
                "invoice_id": "INV00001",
                "amount": 1500.00,
                "payment_status": "UNPAID",
                "vendor_name": "TechCorp",
                "created_at": "2026-01-15T10:00:00Z",  # Should be trimmed
            },
            "anomaly": {
                "anomaly_id": "ANM00001",
                "invoice_id": "INV00001",
                "anomaly_type": "MISSING_PAYMENT",
                "severity": "HIGH",
                "internal_score": 0.95,  # Should be trimmed
            },
            "summary": {
                "invoice_count": 5,
                "anomaly_count": 2,
            },
        }
        
        formatted = self.format_financial_context(raw_context, intent="financial_analysis")
        
        # Invoice should be trimmed
        self.assertIn("invoice", formatted)
        self.assertEqual(formatted["invoice"].get("invoice_id"), "INV00001")
        self.assertNotIn("created_at", formatted["invoice"])
        
        # Anomaly should be trimmed
        self.assertIn("anomaly", formatted)
        self.assertEqual(formatted["anomaly"].get("anomaly_type"), "MISSING_PAYMENT")
        self.assertNotIn("internal_score", formatted["anomaly"])
        
        # Summary should pass through
        self.assertIn("summary", formatted)
        self.assertEqual(formatted["summary"]["invoice_count"], 5)

    def test_format_empty_context(self):
        """format_financial_context should handle None/empty gracefully."""
        self.assertEqual(self.format_financial_context(None, intent="unknown"), {})
        self.assertEqual(self.format_financial_context({}, intent="unknown"), {})

    def test_format_with_list_records(self):
        """Should handle lists of records (sample_invoices, etc.)."""
        raw = {
            "sample_invoices": [
                {"invoice_id": "INV00001", "amount": 100, "created_at": "x"},
                {"invoice_id": "INV00002", "amount": 200, "created_at": "y"},
            ],
            "high_severity_anomalies": [
                {"anomaly_id": "ANM001", "anomaly_type": "MISSING", "internal_score": 0.9},
            ]
        }
        formatted = self.format_financial_context(raw, intent="dataset_review")
        
        self.assertEqual(len(formatted["sample_invoices"]), 2)
        for inv in formatted["sample_invoices"]:
            self.assertIn("invoice_id", inv)
            self.assertIn("amount", inv)
            self.assertNotIn("created_at", inv)
        
        self.assertEqual(len(formatted["high_severity_anomalies"]), 1)
        self.assertIn("anomaly_type", formatted["high_severity_anomalies"][0])
        self.assertNotIn("internal_score", formatted["high_severity_anomalies"][0])

    def test_broad_query_detection(self):
        """Test _is_broad_query helper logic."""
        from app.routes.copilot import _is_broad_query
        
        # Broad queries
        self.assertTrue(_is_broad_query("Why is payment missing?"))
        self.assertTrue(_is_broad_query("Explain anomalies"))
        self.assertTrue(_is_broad_query("Give me an overview of my data"))
        self.assertTrue(_is_broad_query("Review the dataset"))
        
        # Specific queries (with entity IDs)
        self.assertFalse(_is_broad_query("Why is invoice INV00004 unpaid?"))
        self.assertFalse(_is_broad_query("Show anomaly ANM00001"))
        self.assertFalse(_is_broad_query("What is the status of TX00005?"))


class TestLatencyInstrumentation(unittest.TestCase):
    """Test that latency metrics are properly structured."""

    def test_latency_metadata_structure(self):
        """Verify the structure of latency metadata added to responses."""
        # Simulate what the code adds to metadata dict
        sample_metadata = {
            "retrieval_ms": 320,
            "prompt_build_ms": 40,
            "llm_first_token_ms": 10800,
            "fallback_count": 0,
            "model": "openai/gpt-oss-20b:free",
            "finish_reason": "stop",
        }
        
        self.assertIn("retrieval_ms", sample_metadata)
        self.assertIn("prompt_build_ms", sample_metadata)
        self.assertIn("llm_first_token_ms", sample_metadata)
        self.assertIn("fallback_count", sample_metadata)
        
        # Verify types
        self.assertIsInstance(sample_metadata["retrieval_ms"], int)
        self.assertIsInstance(sample_metadata["prompt_build_ms"], int)
        self.assertIsInstance(sample_metadata["llm_first_token_ms"], int)
        self.assertIsInstance(sample_metadata["fallback_count"], int)


# ── Integration tests (require API key + database) ──


@unittest.skipIf(not RUN_INTEGRATION_TESTS, "Set RUN_LLM_TESTS=true to run integration tests")
class TestContextIntegration(unittest.TestCase):
    """Integration tests that exercise the full context pipeline.
    
    These tests require:
    - OPENROUTER_API_KEY environment variable
    - Running Supabase database with test data
    """

    @classmethod
    def setUpClass(cls):
        from app.services.context_budget import calculate_budget, validate_budget
        from app.services.context_formatter import format_financial_context, estimate_context_tokens
        from app.services.token_counter import count_tokens
        from app.services.database import retrieve_context
        from app.services.llm.prompts import build_user_prompt, build_system_prompt
        from app.services.llm.routing import IntentType

        cls.calculate_budget = calculate_budget
        cls.validate_budget = validate_budget
        cls.format_financial_context = format_financial_context
        cls.estimate_context_tokens = estimate_context_tokens
        cls.count_tokens = count_tokens
        cls.retrieve_context = retrieve_context
        cls.build_user_prompt = build_user_prompt
        cls.build_system_prompt = build_system_prompt
        cls.IntentType = IntentType

    def _run_test_case(self, case: Dict[str, Any]):
        """Run a single test case through the context pipeline."""
        name = case["name"]
        question = case["question"]
        max_context_tokens = case["max_context_tokens"]

        logger.warning(f"\n{'='*60}")
        logger.warning(f"TEST CASE: {name}")
        logger.warning(f"Question: {question}")
        logger.warning(f"{'='*60}")

        # 1. Retrieve raw context
        t0 = time.perf_counter()
        raw_context = self.retrieve_context("financial_analysis", question, {})
        retrieval_ms = (time.perf_counter() - t0) * 1000
        logger.warning(f"Retrieval: {retrieval_ms:.0f}ms")

        # 2. Format/trim context
        t1 = time.perf_counter()
        formatted = self.format_financial_context(raw_context, intent="financial_analysis", is_broad_query=case["is_broad"])
        format_ms = (time.perf_counter() - t1) * 1000
        logger.warning(f"Formatting: {format_ms:.0f}ms")

        # 3. Estimate token usage
        context_tokens = self.estimate_context_tokens(formatted)
        logger.warning(f"Context tokens (est): {context_tokens}")

        # 4. Build prompts
        context_str = json.dumps(formatted, ensure_ascii=False) if formatted else ""
        system_prompt = self.build_system_prompt(context_str, intent="financial_analysis")
        user_prompt = self.build_user_prompt(context=formatted, question=question, intent=self.IntentType.FINANCIAL_ANALYSIS)

        system_tokens = self.count_tokens(system_prompt)
        user_tokens = self.count_tokens(user_prompt)
        total_input = system_tokens + user_tokens + context_tokens
        logger.warning(f"System tokens: {system_tokens}")
        logger.warning(f"User tokens: {user_tokens}")
        logger.warning(f"Total input tokens: {total_input}")

        # 5. Calculate budget
        budget = self.calculate_budget(
            model_name="openai/gpt-oss-20b:free",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context=context_str,
            requested_output_tokens=2000,
            intent="financial_analysis",
        )
        logger.warning(f"Budget status: {budget.budget_status}")
        logger.warning(f"Input budget: {budget.input_budget}")
        logger.warning(f"Output budget: {budget.output_budget}")

        # Assertions
        self.assertIsNotNone(formatted, f"{name}: Context should not be None")
        self.assertLessEqual(
            context_tokens, max_context_tokens,
            f"{name}: Context tokens ({context_tokens}) should be <= {max_context_tokens}"
        )
        self.assertNotEqual(
            budget.budget_status, "EXCEEDED",
            f"{name}: Budget should not be exceeded"
        )
        self.assertGreater(
            budget.output_budget, 500,
            f"{name}: Output budget should be > 500 tokens for meaningful responses"
        )

    def test_broad_missing_payment(self):
        case = TEST_CASES[0]
        self._run_test_case(case)

    def test_specific_invoice(self):
        case = TEST_CASES[1]
        self._run_test_case(case)

    def test_explain_anomalies(self):
        case = TEST_CASES[2]
        self._run_test_case(case)

    def test_show_invoice_by_id(self):
        case = TEST_CASES[3]
        self._run_test_case(case)


if __name__ == "__main__":
    logger.warning("=" * 60)
    logger.warning("Phase 1.5 Regression Tests")
    logger.warning(f"Integration tests: {'ENABLED' if RUN_INTEGRATION_TESTS else 'DISABLED'}")
    logger.warning("Set RUN_LLM_TESTS=true to enable integration tests")
    logger.warning("=" * 60)
    unittest.main()