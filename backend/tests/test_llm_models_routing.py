import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.shared.llm.models import (
    FAST_POOL,
    MEDIUM_POOL,
    FULL_POOL,
    ALL_MODELS,
    SAFETY_MODEL,
    CONVERSATION_POOL,
    ACCOUNTING_KNOWLEDGE_POOL,
    GENERAL_KNOWLEDGE_POOL,
    FINANCIAL_ANALYSIS_POOL,
    REASONING_POOL,
    MODEL_ROUTING,
    get_enabled_models,
    get_model_tiers,
    _get_pool_for_intent,
)
from app.shared.llm.manager import (
    _is_permanent_error,
    _is_temporary_provider_error,
    _is_retryable_error,
    _record_failure,
    _record_success,
    _select_next_model,
    _model_health,
    _health_lock,
    PERMANENT_COOLDOWN_SECONDS,
    MODEL_COOLDOWN_SECONDS,
)
from openai import APIStatusError, RateLimitError, APITimeoutError


class TestLLMModelsAndRouting(unittest.TestCase):

    def test_pool_deduplication(self):
        """Verify no duplicate model configs exist within any pool."""
        fast_names = [m.name for m in FAST_POOL]
        self.assertEqual(len(fast_names), len(set(fast_names)), "FAST_POOL contains duplicate models")

        medium_names = [m.name for m in MEDIUM_POOL]
        self.assertEqual(len(medium_names), len(set(medium_names)), "MEDIUM_POOL contains duplicate models")

        full_names = [m.name for m in FULL_POOL]
        self.assertEqual(len(full_names), len(set(full_names)), "FULL_POOL contains duplicate models")

        all_names = [m.name for m in ALL_MODELS]
        self.assertEqual(len(all_names), len(set(all_names)), "ALL_MODELS contains duplicate models")

    def test_obsolete_models_removed(self):
        """Verify obsolete 404 models are completely removed from all pools."""
        obsolete_models = {
            "openai/gpt-oss-20b:free",
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "nvidia/nemotron-nano-9b-v2:free",
        }
        all_names = {m.name for m in ALL_MODELS}
        for obsolete in obsolete_models:
            self.assertNotIn(obsolete, all_names, f"Obsolete model {obsolete} still present in ALL_MODELS")
            for intent, routed in MODEL_ROUTING.items():
                self.assertNotIn(obsolete, routed, f"Obsolete model {obsolete} still in MODEL_ROUTING[{intent}]")

    def test_safety_model_isolated(self):
        """Verify content-safety model is separate and excluded from general pools."""
        self.assertEqual(SAFETY_MODEL, "nvidia/nemotron-3.5-content-safety:free")
        all_names = {m.name for m in ALL_MODELS}
        self.assertNotIn(SAFETY_MODEL, all_names, "Safety model should not be in ALL_MODELS")
        self.assertNotIn(SAFETY_MODEL, {m.name for m in FAST_POOL})
        self.assertNotIn(SAFETY_MODEL, {m.name for m in MEDIUM_POOL})
        self.assertNotIn(SAFETY_MODEL, {m.name for m in FULL_POOL})

    def test_candidate_models_represented(self):
        """Verify candidate models are accurately represented."""
        expected_candidates = {
            "inclusionai/ling-3.0-flash-fin:free",
            "liquid/lfm-2.5-2.6b:free",
            "nvidia/nemotron-3.5-lightning:free",
            "thinkingmachines/inkling-small:free",
            "poolside/laguna-s-2.1:free",
            "poolside/laguna-xs-2.1:free",
            "cohere/north-mini-code:free",
            "z-ai/glm-5.2:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "minimax/minimax-m3:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "google/gemma-4-26b-a4b-it:free",
            "google/gemma-4-31b-it:free",
            "minimax/minimax-m2.7:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
        }
        all_names = {m.name for m in ALL_MODELS}
        self.assertEqual(all_names, expected_candidates, "ALL_MODELS does not match expected candidate list")

    def test_backward_compatible_aliases(self):
        """Ensure all pool aliases are preserved for backward compatibility."""
        self.assertEqual(CONVERSATION_POOL, FAST_POOL)
        self.assertEqual(ACCOUNTING_KNOWLEDGE_POOL, FAST_POOL)
        self.assertEqual(GENERAL_KNOWLEDGE_POOL, MEDIUM_POOL)
        self.assertEqual(FINANCIAL_ANALYSIS_POOL, FULL_POOL)
        self.assertEqual(REASONING_POOL, FULL_POOL)

    def test_report_architect_pool_and_timeout(self):
        """Verify Report Architect uses FAST_POOL with 12.0s per-model timeout (within 45s budget)."""
        tiers = get_model_tiers("report_architect")
        self.assertEqual(len(tiers), 1, "Report architect must only have 1 fast tier (no slow fallbacks)")
        self.assertEqual(tiers[0].timeout, 12.0, "Report architect per-model timeout must be 12.0s")
        for m in tiers[0].models:
            self.assertEqual(m.tier, 1, f"Report architect model {m.name} is not Tier 1")

    def test_reconciliation_and_trend_routing(self):
        """Reconciliation and trend intents should route to MEDIUM_POOL as primary."""
        for intent in ("reconciliation_analysis", "trend_analysis", "comparison"):
            pool = _get_pool_for_intent(intent)
            self.assertEqual(pool, MEDIUM_POOL, f"Intent {intent} should map to MEDIUM_POOL")

    def test_financial_analysis_routing(self):
        """Financial analysis and executive reporting should route to FULL_POOL."""
        for intent in ("financial_analysis", "dataset_review", "report_summary", "recommendations"):
            pool = _get_pool_for_intent(intent)
            self.assertEqual(pool, FULL_POOL, f"Intent {intent} should map to FULL_POOL")

    def test_all_routing_targets_exist(self):
        """Ensure every model named in MODEL_ROUTING exists in ALL_MODELS."""
        all_names = {m.name for m in ALL_MODELS}
        for intent, models in MODEL_ROUTING.items():
            for model_name in models:
                self.assertIn(model_name, all_names, f"Model {model_name} in {intent} routing not found in ALL_MODELS")

    def test_case_insensitive_intent_handling(self):
        """Verify get_enabled_models works with both upper and lower case intents."""
        upper_models = get_enabled_models("INVOICE_LOOKUP")
        lower_models = get_enabled_models("invoice_lookup")
        self.assertEqual([m.name for m in upper_models], [m.name for m in lower_models])


class TestLLMFailureHandling(unittest.TestCase):

    def setUp(self):
        with _health_lock:
            _model_health.clear()

    def test_permanent_404_error_detection(self):
        """Verify 404 and unavailable messages are recognized as permanent errors."""
        mock_response = MagicMock(status_code=404)
        err_404 = APIStatusError(message="Not found", response=mock_response, body=None)
        self.assertTrue(_is_permanent_error(err_404))

        err_no_endpoints = Exception("404: No endpoints found")
        self.assertTrue(_is_permanent_error(err_no_endpoints))

        err_unavailable_free = Exception("This model is unavailable for free. The paid version is available now.")
        self.assertTrue(_is_permanent_error(err_unavailable_free))

    def test_temporary_error_detection(self):
        """Verify 429 and ResourceExhausted are recognized as temporary errors."""
        mock_response = MagicMock(status_code=429)
        err_429 = APIStatusError(message="Rate limit exceeded", response=mock_response, body=None)
        self.assertTrue(_is_temporary_provider_error(err_429))

        err_exhausted = Exception("ResourceExhausted: Worker local total request limit reached")
        self.assertTrue(_is_temporary_provider_error(err_exhausted))

        err_overload = Exception("Service temporarily overloaded")
        self.assertTrue(_is_temporary_provider_error(err_overload))

    def test_permanent_error_not_retryable(self):
        """Permanent 404 errors should never be retried."""
        mock_response = MagicMock(status_code=404)
        err_404 = APIStatusError(message="Not found", response=mock_response, body=None)
        self.assertFalse(_is_retryable_error(err_404))

    def test_permanent_error_triggers_immediate_24h_cooldown(self):
        """404 error should immediately place the model in long cooldown and skip it."""
        model_name = "test/unavailable-model:free"
        err = Exception("404 No endpoints found")

        _record_failure(model_name, err, "test_pool")

        with _health_lock:
            stats = _model_health.get(model_name)
            self.assertIsNotNone(stats)
            self.assertIsNotNone(stats.cooldown_expires)
            # Should be roughly 24 hours in future
            diff = (stats.cooldown_expires - datetime.now(timezone.utc)).total_seconds()
            self.assertGreater(diff, PERMANENT_COOLDOWN_SECONDS - 10)

        # _select_next_model should immediately skip this model
        from app.shared.llm.models import ModelConfig
        models = [ModelConfig(name=model_name, tier=1, enabled=True)]
        selected = _select_next_model(models, set(), "invoice_lookup")
        self.assertIsNone(selected, "Cooled-down model should be skipped by _select_next_model")

    def test_temporary_error_triggers_short_cooldown(self):
        """429 or ResourceExhausted should immediately place model in temporary 60s cooldown."""
        model_name = "test/rate-limited-model:free"
        err = Exception("ResourceExhausted: Worker local total request limit reached")

        _record_failure(model_name, err, "test_pool")

        with _health_lock:
            stats = _model_health.get(model_name)
            self.assertIsNotNone(stats)
            self.assertIsNotNone(stats.cooldown_expires)
            diff = (stats.cooldown_expires - datetime.now(timezone.utc)).total_seconds()
            self.assertGreater(diff, MODEL_COOLDOWN_SECONDS - 5)
    def test_build_system_prompt_supports_context_str(self):
        """Verify build_system_prompt accepts context_str keyword argument without error."""
        from app.shared.llm.prompts import build_system_prompt
        prompt1 = build_system_prompt(context="test context", intent="invoice_lookup")
        self.assertIsInstance(prompt1, str)
        prompt2 = build_system_prompt(context_str="test context", intent="invoice_lookup")
        self.assertIsInstance(prompt2, str)
        prompt3 = build_system_prompt()
        self.assertIsInstance(prompt3, str)


if __name__ == "__main__":
    unittest.main()
