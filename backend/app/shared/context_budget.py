"""Context budget management for LLM requests."""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from app.shared.token_counter import (
    count_tokens,
    estimate_prompt_tokens,
    get_model_context_limit,
)

logger = logging.getLogger(__name__)

# ── Intent-aware minimum output tokens ──
# Simple lookups need less, complex analysis needs more.
MIN_OUTPUT_BY_INTENT: Dict[str, int] = {
    "invoice_lookup": 300,
    "anomaly_lookup": 300,
    "anomaly_explanation": 500,
    "reconciliation_analysis": 500,
    "report_summary": 600,
    "dataset_review": 800,
    "trend_analysis": 500,
    "comparison": 500,
    "recommendations": 400,
    "financial_analysis": 600,
    "general_knowledge": 400,
    "financial_general": 400,
    "greeting": 0,
    "goodbye": 0,
    "thanks": 0,
    "small_talk": 0,
    "assistant_identity": 0,
    "assistant_capabilities": 0,
}

# Default minimum for unknown intents
DEFAULT_MIN_OUTPUT_TOKENS = 300


def get_min_output_for_intent(intent: str) -> int:
    """Get the minimum output token budget for a given intent."""
    return MIN_OUTPUT_BY_INTENT.get(intent, DEFAULT_MIN_OUTPUT_TOKENS)


@dataclass
class ContextBudget:
    """Budget allocation for a single LLM request."""
    model_limit: int
    available_context: int  # 80% of model limit
    output_budget: int  # intent-aware minimum, capped by model limit
    input_budget: int  # available_context - output_budget
    estimated_input_tokens: int
    budget_status: str  # "OK", "WARNING", "EXCEEDED"
    utilization_percent: float


class ContextOverflowError(Exception):
    """Raised when estimated tokens exceed the input budget."""
    pass


def calculate_budget(
    model_name: str,
    system_prompt: str = "",
    user_prompt: str = "",
    context: str = "",
    requested_output_tokens: Optional[int] = None,
    safety_margin: float = 0.8,
    output_reservation: float = 0.25,
    intent: str = "unknown",
) -> ContextBudget:
    """
    Calculate context budget for a request.
    
    Uses intent-aware minimum output tokens to ensure the model has enough
    room for complete responses (explanation + evidence + recommendations).
    
    Args:
        model_name: Name of the model being used
        system_prompt: System instructions
        user_prompt: User question/request
        context: Retrieved database context
        requested_output_tokens: Desired output token limit (optional)
        safety_margin: Fraction of context to use (default: 0.8 = 80%)
        output_reservation: Fraction reserved for output (default: 0.25 = 25%)
        intent: Intent string for intent-aware minimum output
    
    Returns:
        ContextBudget with allocation details
    """
    model_limit = get_model_context_limit(model_name)
    
    # Calculate available context (80% of limit by default)
    available_context = int(model_limit * safety_margin)
    
    # Calculate output budget:
    # 1. Start with the requested output tokens (if provided)
    # 2. Apply the intent-aware minimum floor
    # 3. Cap at the model's output reservation limit
    intent_min = get_min_output_for_intent(intent)
    
    if requested_output_tokens:
        # Use the larger of requested or intent minimum, capped by model limit
        output_budget = min(
            max(requested_output_tokens, intent_min),
            int(model_limit * output_reservation),
        )
    else:
        # Use intent minimum, capped by model limit
        output_budget = min(
            intent_min,
            int(model_limit * output_reservation),
        )
    
    # Input budget is what's left after reserving output
    input_budget = available_context - output_budget
    
    # Estimate actual input tokens
    estimated_input_tokens = estimate_prompt_tokens(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context=context,
    )
    
    # Determine budget status
    utilization_percent = (estimated_input_tokens / input_budget) * 100 if input_budget > 0 else 100
    
    if estimated_input_tokens > input_budget:
        budget_status = "EXCEEDED"
    elif utilization_percent > 90:
        budget_status = "WARNING"
    else:
        budget_status = "OK"
    
    return ContextBudget(
        model_limit=model_limit,
        available_context=available_context,
        output_budget=output_budget,
        input_budget=input_budget,
        estimated_input_tokens=estimated_input_tokens,
        budget_status=budget_status,
        utilization_percent=round(utilization_percent, 2),
    )


def validate_budget(budget: ContextBudget) -> None:
    """
    Validate that the request fits within the budget.
    
    Raises:
        ContextOverflowError: If estimated tokens exceed input budget
    """
    if budget.budget_status == "EXCEEDED":
        raise ContextOverflowError(
            f"Context overflow: estimated {budget.estimated_input_tokens} tokens "
            f"exceeds input budget of {budget.input_budget} tokens "
            f"({budget.utilization_percent}% utilization)"
        )
    
    if budget.budget_status == "WARNING":
        logger.warning(
            "Context budget warning: %s tokens estimated (%.1f%% of input budget %s)",
            budget.estimated_input_tokens,
            budget.utilization_percent,
            budget.input_budget,
        )


def log_diagnostics(
    model_name: str,
    budget: ContextBudget,
    system_prompt: str = "",
    user_prompt: str = "",
    context: str = "",
) -> None:
    """
    Log detailed prompt diagnostics for debugging.
    
    Args:
        model_name: Name of the model
        budget: Calculated context budget
        system_prompt: System instructions
        user_prompt: User question
        context: Retrieved context
    """
    system_tokens = count_tokens(system_prompt)
    context_tokens = count_tokens(context)
    user_tokens = count_tokens(user_prompt)
    
    logger.warning(
        "========== PROMPT DIAGNOSTICS ==========\n"
        "Model: %s\n"
        "Model context limit: %s\n"
        "Available context (80%%): %s\n"
        "Output reservation (intent-aware): %s\n"
        "Input budget: %s\n"
        "----------------------------------------\n"
        "System instructions tokens: %s (chars: %s)\n"
        "Retrieved database context tokens: %s (chars: %s)\n"
        "Current user question tokens: %s (chars: %s)\n"
        "Estimated total input tokens: %s\n"
        "----------------------------------------\n"
        "Budget status: %s\n"
        "Utilization: %.1f%%\n"
        "========================================",
        model_name,
        budget.model_limit,
        budget.available_context,
        budget.output_budget,
        budget.input_budget,
        system_tokens,
        len(system_prompt),
        context_tokens,
        len(context),
        user_tokens,
        len(user_prompt),
        budget.estimated_input_tokens,
        budget.budget_status,
        budget.utilization_percent,
    )
    
    # If context is suspiciously large, log a sample
    if context_tokens > 5000:
        logger.warning(
            "LARGE CONTEXT DETECTED (tokens=%s). First 500 chars:\n%s\n...\nLast 500 chars:\n%s",
            context_tokens,
            context[:500],
            context[-500:] if len(context) > 500 else context,
        )


def get_safe_max_tokens(
    model_name: str,
    estimated_input_tokens: int,
    default_max: int = 900,
    intent: str = "unknown",
) -> int:
    """
    Get a safe max_tokens value that won't cause context overflow.
    
    Uses intent-aware minimum output to ensure meaningful responses.
    
    Args:
        model_name: Name of the model
        estimated_input_tokens: Estimated input token count
        default_max: Default max_tokens if no constraints
        intent: Intent string for intent-aware minimum
    
    Returns:
        Safe max_tokens value
    """
    model_limit = get_model_context_limit(model_name)
    safety_margin = 0.8
    available_context = int(model_limit * safety_margin)
    
    # Reserve space for input
    max_output = available_context - estimated_input_tokens
    
    # If input already exceeds budget, return minimal output
    if max_output <= 0:
        logger.warning(
            "Input tokens (%s) exceed available context (%s), using minimal output",
            estimated_input_tokens,
            available_context,
        )
        return 100
    
    # Get intent-aware minimum
    intent_min = get_min_output_for_intent(intent)
    
    # Use the larger of intent_min or default_max, but capped by available space
    target = max(intent_min, default_max)
    return min(target, max_output)