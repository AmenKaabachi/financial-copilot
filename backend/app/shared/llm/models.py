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


# Pools are ordered by speed and domain relevance to minimize latency and maximize financial reasoning.
# Fast models (Tier 1): inclusionai/ling-3.0-flash-fin, nvidia/nemotron-3.5-lightning, cohere/north-mini-code,
#                       google/gemma-4-26b-a4b-it, poolside/laguna-xs-2.1, liquid/lfm-2.5-2.6b, thinkingmachines/inkling-small
# Medium models (Tier 2): nvidia/nemotron-3-nano-omni-30b-a3b-reasoning, poolside/laguna-s-2.1, z-ai/glm-5.2, minimax/minimax-m2.7
# Large models (Tier 3): nvidia/nemotron-3-ultra-550b-a55b, nvidia/nemotron-3-super-120b-a12b, minimax/minimax-m3, google/gemma-4-31b-it

# Isolated safety model: not for general financial reasoning or normal pools
SAFETY_MODEL: str = "nvidia/nemotron-3.5-content-safety:free"

# ── Fastest models only (tier 1) ──
# Used for: simple lookups, accounting definitions, greetings, Report Architect
FAST_POOL: List[ModelConfig] = [
    ModelConfig(name="inclusionai/ling-3.0-flash-fin:free", tier=1, enabled=True),
    ModelConfig(name="nvidia/nemotron-3.5-lightning:free", tier=1, enabled=True),
    ModelConfig(name="cohere/north-mini-code:free", tier=1, enabled=True),
    ModelConfig(name="google/gemma-4-26b-a4b-it:free", tier=1, enabled=True),
    ModelConfig(name="poolside/laguna-xs-2.1:free", tier=1, enabled=True),
    ModelConfig(name="liquid/lfm-2.5-2.6b:free", tier=1, enabled=True),
    ModelConfig(name="thinkingmachines/inkling-small:free", tier=1, enabled=True),
]

# ── Fast + medium models (tiers 1-2) ──
# Used for: reconciliation analysis, comparisons, trend analysis, anomaly interpretation
MEDIUM_POOL: List[ModelConfig] = [
    ModelConfig(name="inclusionai/ling-3.0-flash-fin:free", tier=1, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", tier=2, enabled=True),
    ModelConfig(name="poolside/laguna-s-2.1:free", tier=2, enabled=True),
    ModelConfig(name="z-ai/glm-5.2:free", tier=2, enabled=True),
    ModelConfig(name="minimax/minimax-m2.7:free", tier=2, enabled=True),
    ModelConfig(name="google/gemma-4-26b-a4b-it:free", tier=1, enabled=True),
    ModelConfig(name="nvidia/nemotron-3.5-lightning:free", tier=1, enabled=True),
]

# ── All models including large reasoning & executive reporting models (tiers 1-3) ──
# Used for: complex financial analysis, root cause analysis, dataset review, executive report summaries, recommendations
FULL_POOL: List[ModelConfig] = [
    ModelConfig(name="nvidia/nemotron-3-ultra-550b-a55b:free", tier=3, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-super-120b-a12b:free", tier=3, enabled=True),
    ModelConfig(name="minimax/minimax-m3:free", tier=3, enabled=True),
    ModelConfig(name="google/gemma-4-31b-it:free", tier=3, enabled=True),
    ModelConfig(name="z-ai/glm-5.2:free", tier=2, enabled=True),
    ModelConfig(name="minimax/minimax-m2.7:free", tier=2, enabled=True),
    ModelConfig(name="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", tier=2, enabled=True),
    ModelConfig(name="inclusionai/ling-3.0-flash-fin:free", tier=1, enabled=True),
    ModelConfig(name="google/gemma-4-26b-a4b-it:free", tier=1, enabled=True),
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
MODEL_ROUTING: Dict[str, List[str]] = {
    # Simple lookups & lightweight structured selection — fast models only (tier 1)
    "INVOICE_LOOKUP": [
        "inclusionai/ling-3.0-flash-fin:free",
        "nvidia/nemotron-3.5-lightning:free",
        "google/gemma-4-26b-a4b-it:free",
        "poolside/laguna-xs-2.1:free",
    ],
    "ANOMALY_LOOKUP": [
        "inclusionai/ling-3.0-flash-fin:free",
        "nvidia/nemotron-3.5-lightning:free",
        "google/gemma-4-26b-a4b-it:free",
        "poolside/laguna-xs-2.1:free",
    ],
    "REPORT_ARCHITECT": [
        "google/gemma-4-26b-a4b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
        "cohere/north-mini-code:free",
        "inclusionai/ling-3.0-flash-fin:free",
    ],
    # Medium complexity — financial analysis, reconciliation, trends, comparisons (tiers 1-2)
    "RECONCILIATION_ANALYSIS": [
        "inclusionai/ling-3.0-flash-fin:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "z-ai/glm-5.2:free",
        "poolside/laguna-s-2.1:free",
    ],
    "COMPARISON": [
        "inclusionai/ling-3.0-flash-fin:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "z-ai/glm-5.2:free",
        "minimax/minimax-m2.7:free",
    ],
    "TREND_ANALYSIS": [
        "inclusionai/ling-3.0-flash-fin:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "minimax/minimax-m2.7:free",
        "z-ai/glm-5.2:free",
    ],
    # Complex analysis & reports — full pool (tiers 1-3)
    "FINANCIAL_ANALYSIS": [
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "minimax/minimax-m3:free",
        "google/gemma-4-31b-it:free",
        "inclusionai/ling-3.0-flash-fin:free",
    ],
    "DATASET_REVIEW": [
        "minimax/minimax-m3:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "google/gemma-4-31b-it:free",
        "z-ai/glm-5.2:free",
    ],
    "REPORT_SUMMARY": [
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "minimax/minimax-m3:free",
        "google/gemma-4-31b-it:free",
        "minimax/minimax-m2.7:free",
    ],
    "RECOMMENDATIONS": [
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    ],
}


def _filter_enabled(models: List[ModelConfig]) -> List[ModelConfig]:
    return [m for m in models if m.enabled]


def _get_pool_for_intent(intent: Optional[str] = None) -> List[ModelConfig]:
    """Returns the primary model pool for the given intent."""
    norm = intent.lower() if intent else ""
    if norm in ("assistant_identity", "assistant_capabilities", "greeting", "goodbye", "thanks", "small_talk"):
        return CONVERSATION_POOL
    elif norm in ("general_knowledge", "financial_general"):
        # Accounting definitions ("what is EBITDA", "explain depreciation") use fastest pool
        return ACCOUNTING_KNOWLEDGE_POOL
    elif norm in ("report_architect", "anomaly_lookup", "invoice_lookup"):
        # Report architect and simple lookups use fast pool only
        return FAST_POOL
    elif norm in ("reconciliation_analysis", "trend_analysis", "comparison"):
        # Medium complexity reconciliation and trend tasks use medium pool
        return MEDIUM_POOL
    elif norm in (
        "report_summary",
        "dataset_review",
        "recommendations",
        "financial_analysis",
    ):
        return FINANCIAL_ANALYSIS_POOL
    else:
        return FINANCIAL_ANALYSIS_POOL


def get_enabled_models(intent: Optional[str] = None) -> List[ModelConfig]:
    """Returns the primary enabled models for the given intent, respecting routing overrides."""
    routed_names: List[str] = []
    if intent:
        if intent in MODEL_ROUTING:
            routed_names = MODEL_ROUTING[intent]
        elif intent.upper() in MODEL_ROUTING:
            routed_names = MODEL_ROUTING[intent.upper()]
        elif intent.lower() in MODEL_ROUTING:
            routed_names = MODEL_ROUTING[intent.lower()]

    pool = _get_pool_for_intent(intent)
    enabled = _filter_enabled(pool)

    if routed_names:
        name_to_model = {m.name: m for m in _filter_enabled(ALL_MODELS)}
        available: List[ModelConfig] = []
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
    primary_enabled = get_enabled_models(intent)
    all_enabled = _filter_enabled(ALL_MODELS)
    norm = intent.lower() if intent else ""

    # Build tiered fallback list
    tiers = []

    # Report architect uses fast pool with 12s per-model timeout to allow multiple attempts within 45s budget
    if norm == "report_architect":
        if primary_enabled:
            tiers.append(ModelTier(models=primary_enabled, timeout=12.0))
        return tiers

    # Tier 1: Primary pool with 8s timeout
    if primary_enabled:
        tiers.append(ModelTier(models=primary_enabled, timeout=8.0))

    # Tier 2: General knowledge pool (for conversation intents) or medium/full pool
    # as a middle ground
    if norm in ("assistant_identity", "assistant_capabilities", "greeting", "goodbye", "thanks", "small_talk"):
        general_enabled = _filter_enabled(GENERAL_KNOWLEDGE_POOL)
        if general_enabled and general_enabled != primary_enabled:
            tiers.append(ModelTier(models=general_enabled, timeout=15.0))
    elif norm in ("general_knowledge", "financial_general"):
        medium_enabled = _filter_enabled(MEDIUM_POOL)
        if medium_enabled and medium_enabled != primary_enabled:
            tiers.append(ModelTier(models=medium_enabled, timeout=15.0))
    elif norm in ("reconciliation_analysis", "trend_analysis", "comparison"):
        full_enabled = _filter_enabled(FULL_POOL)
        if full_enabled and full_enabled != primary_enabled:
            tiers.append(ModelTier(models=full_enabled, timeout=15.0))

    # Final tier: ALL_MODELS as catch-all with 25s timeout
    if all_enabled:
        tiers.append(ModelTier(models=all_enabled, timeout=25.0))

    return tiers