from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ModelConfig:
    name: str
    tier: int
    enabled: bool = True


@dataclass
class ModelTier:
    models: List[ModelConfig]
    timeout: float  # seconds per model attempt


# Pools are ordered by speed (fastest first) to minimize latency.
# Fast models: openai/gpt-oss-20b, google/gemma-4-26b-a4b-it, poolside/laguna-xs-2.1
# Medium models: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning, nvidia/nemotron-3-nano-30b-a3b
# Slow models: nvidia/nemotron-nano-9b-v2, google/gemma-4-31b-it, nvidia/nemotron-3-ultra-550b-a55b, nvidia/nemotron-3-super-120b-a12b

# ── Fastest models only (tier 1) ──
# Used for: simple lookups, definitions, greetings
FAST_POOL: List[ModelConfig] = [
    ModelConfig(name="openai/gpt-oss-20b:free", tier=1, enabled=True),
    ModelConfig(name="google/gemma-4-26b-a4b-it:free", tier=1, enabled=True),
    ModelConfig(name="poolside/laguna-xs-2.1:free", tier=1, enabled=True),
]

# ── Fast + medium models (tiers 1-2) ──
# Used for: invoice/anomaly lookups, reconciliation analysis, comparisons
MEDIUM_POOL: List[ModelConfig] = [
    ModelConfig(name="openai/gpt-oss-20b:free", tier=1, enabled=True),
    ModelConfig(name="google/gemma-4-26b-a4b-it:free", tier=1, enabled=True),
    ModelConfig(name="poolside/laguna-xs-2.1:free", tier=1, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", tier=2, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-nano-30b-a3b:free", tier=2, enabled=True),
]

# ── All models including large reasoning models (tiers 1-3) ──
# Used for: dataset review, report summary, recommendations, complex analysis
FULL_POOL: List[ModelConfig] = [
    ModelConfig(name="openai/gpt-oss-20b:free", tier=1, enabled=True),
    ModelConfig(name="google/gemma-4-26b-a4b-it:free", tier=1, enabled=True),
    ModelConfig(name="poolside/laguna-xs-2.1:free", tier=1, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", tier=2, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-nano-30b-a3b:free", tier=2, enabled=True),
    ModelConfig(name="nvidia/nemotron-nano-9b-v2:free", tier=2, enabled=True),
    ModelConfig(name="google/gemma-4-31b-it:free", tier=3, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-ultra-550b-a55b:free", tier=3, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-super-120b-a12b:free", tier=3, enabled=True),
]

# Backward-compatible aliases
CONVERSATION_POOL = FAST_POOL
ACCOUNTING_KNOWLEDGE_POOL = FAST_POOL
GENERAL_KNOWLEDGE_POOL = MEDIUM_POOL
FINANCIAL_ANALYSIS_POOL = FULL_POOL
REASONING_POOL = FULL_POOL

ALL_MODELS: List[ModelConfig] = list({
    m.name: m for pool in [FAST_POOL, MEDIUM_POOL, FULL_POOL]
    for m in pool
}.values())


# Intent-to-pool mapping: simple lookups use fast models,
# analysis/review use medium, complex synthesis uses full pool.
MODEL_ROUTING = {
    # Simple lookups — fast models only (tier 1)
    "INVOICE_LOOKUP": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "poolside/laguna-xs-2.1:free"],
    "ANOMALY_LOOKUP": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "poolside/laguna-xs-2.1:free"],
    # Medium complexity — fast + medium models (tiers 1-2)
    "RECONCILIATION_ANALYSIS": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"],
    "COMPARISON": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"],
    "TREND_ANALYSIS": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"],
    # Complex analysis — full pool (tiers 1-3)
    "FINANCIAL_ANALYSIS": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "google/gemma-4-31b-it:free"],
    "DATASET_REVIEW": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-ultra-550b-a55b:free", "google/gemma-4-31b-it:free"],
    "REPORT_SUMMARY": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-ultra-550b-a55b:free", "google/gemma-4-31b-it:free"],
    "RECOMMENDATIONS": ["openai/gpt-oss-20b:free", "google/gemma-4-26b-a4b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "google/gemma-4-31b-it:free"],
}


def _filter_enabled(models: List[ModelConfig]) -> List[ModelConfig]:
    return [m for m in models if m.enabled]


def _get_pool_for_intent(intent: Optional[str] = None) -> List[ModelConfig]:
    """Returns the primary model pool for the given intent."""
    if intent in ("assistant_identity", "assistant_capabilities", "greeting", "goodbye", "thanks", "small_talk"):
        return CONVERSATION_POOL
    elif intent in ("general_knowledge", "financial_general"):
        # Accounting definitions ("what is EBITDA", "explain depreciation") use fastest pool
        return ACCOUNTING_KNOWLEDGE_POOL
    elif intent in (
        "anomaly_lookup",
        "reconciliation_analysis",
        "report_summary",
        "dataset_review",
        "trend_analysis",
        "comparison",
        "recommendations",
        "financial_analysis",
        "invoice_lookup",
    ):
        return FINANCIAL_ANALYSIS_POOL
    else:
        return FINANCIAL_ANALYSIS_POOL


def get_enabled_models(intent: Optional[str] = None) -> List[ModelConfig]:
    """Returns the primary enabled models for the given intent, respecting routing overrides."""
    routed_names = []
    if intent and intent in MODEL_ROUTING:
        routed_names = MODEL_ROUTING[intent]

    pool = _get_pool_for_intent(intent)
    enabled = _filter_enabled(pool)

    if routed_names:
        name_to_model = {m.name: m for m in enabled}
        available = []
        for name in routed_names:
            if name in name_to_model:
                available.append(name_to_model[name])

        for m in enabled:
            if m.name not in [x.name for x in available]:
                available.append(m)

        return available

    return enabled


def get_model_tiers(intent: Optional[str] = None) -> List[ModelTier]:
    """
    Returns a list of ModelTier objects for the given intent.
    Each tier is tried in order, with its own per-model timeout.
    The last tier always includes ALL_MODELS as a catch-all fallback.
    """
    primary_pool = _get_pool_for_intent(intent)
    primary_enabled = _filter_enabled(primary_pool)
    all_enabled = _filter_enabled(ALL_MODELS)

    # Build tiered fallback list
    tiers = []

    # Tier 1: Primary pool with 8s timeout
    if primary_enabled:
        tiers.append(ModelTier(models=primary_enabled, timeout=8.0))

    # Tier 2: General knowledge pool (for conversation intents) or financial pool (for general)
    # as a middle ground
    if intent in ("assistant_identity", "assistant_capabilities", "greeting", "goodbye", "thanks", "small_talk"):
        general_enabled = _filter_enabled(GENERAL_KNOWLEDGE_POOL)
        if general_enabled and general_enabled != primary_enabled:
            tiers.append(ModelTier(models=general_enabled, timeout=15.0))
    elif intent in ("general_knowledge", "financial_general"):
        financial_enabled = _filter_enabled(FINANCIAL_ANALYSIS_POOL)
        if financial_enabled and financial_enabled != primary_enabled:
            tiers.append(ModelTier(models=financial_enabled, timeout=15.0))

    # Final tier: ALL_MODELS as catch-all with 25s timeout
    if all_enabled:
        tiers.append(ModelTier(models=all_enabled, timeout=25.0))

    return tiers