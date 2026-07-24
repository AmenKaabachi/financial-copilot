from __future__ import annotations

import logging
import time
import re
import httpx
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

from app.services.llm.client import get_openrouter_client
from app.services.llm.models import ModelConfig, ModelTier, get_enabled_models, get_model_tiers
from app.services.llm.prompts import build_system_prompt


logger = logging.getLogger(__name__)

MAX_RETRIES = 1
FAILURE_THRESHOLD = 3
MODEL_COOLDOWN_SECONDS = 60
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

# Fast definitional questions ("what is X") get a tighter budget.
# Complex financial analysis can use the full budget.
FAST_REQUEST_BUDGET_SECONDS = 12.0
COMPLEX_REQUEST_BUDGET_SECONDS = 25.0
REQUEST_BUDGET_SECONDS = 30.0

FAST_INTENTS = {"general_knowledge", "financial_general", "greeting", "goodbye", "thanks", "small_talk", "assistant_identity", "assistant_capabilities"}

# Streaming read timeouts (seconds) keyed by intent.
# Connection timeout is always 10s; read timeout varies by complexity.
# Simple definitions complete quickly; large dataset reviews need longer.
STREAM_READ_TIMEOUTS: Dict[str, float] = {
    "greeting": 15,
    "goodbye": 15,
    "thanks": 15,
    "small_talk": 15,
    "assistant_identity": 15,
    "assistant_capabilities": 15,
    "general_knowledge": 30,
    "financial_general": 30,
    "invoice_lookup": 45,
    "anomaly_lookup": 45,
    "reconciliation_analysis": 60,
    "report_summary": 60,
    "trend_analysis": 60,
    "comparison": 60,
    "recommendations": 60,
    "financial_analysis": 60,
    "dataset_review": 90,
}

TOKEN_LIMITS = {
    "invoice_lookup": 800,
    "anomaly_lookup": 800,
    "reconciliation_analysis": 800,
    "report_summary": 900,
    "dataset_review": 3000,
    "trend_analysis": 800,
    "comparison": 800,
    "recommendations": 800,
    "financial_analysis": 900,
    "general_knowledge": 384,
    "financial_general": 700,
    "greeting": 0,
    "goodbye": 0,
    "thanks": 0,
    "small_talk": 0,
    "assistant_identity": 0,
    "assistant_capabilities": 0,
}

MIN_RESPONSE_LENGTH = 20
MAX_CONTINUATION_ATTEMPTS = 1

INCOMPLETE_ENDINGS = (
    re.compile(r"Next Action:\s*$"),
    re.compile(r"\d+\.\s*$"),
    re.compile(r"The next action is\s*$"),
    re.compile(r"-\s*$"),
    re.compile(r"To be continued\s*$"),
    re.compile(r"and so on\.?\s*$", re.IGNORECASE),
    re.compile(r"(Formula|Purpose|Why it matters|Limitations|Examples?):\s*$", re.IGNORECASE),
)

MODEL_POOL_LABELS = {
    "conversation": "Conversation Pool",
    "general_knowledge": "General Knowledge Pool",
    "financial_analysis": "Financial Analysis Pool",
    "reasoning": "Reasoning Pool",
}


class GenerateAnswerResult(TypedDict):
    answer: str
    model: str
    tier: int
    fallback_used: bool
    attempts: int
    response_time: float
    cached: bool
    pool: str
    provider: str
    finish_reason: str
    prompt_token_estimate: int
    completion_token_estimate: int
    total_token_estimate: int
    max_tokens: int
    continuation_used: bool


class StreamMetadata(TypedDict):
    model: str
    tier: int
    fallback_used: bool
    attempts: int
    response_time: float
    cached: bool
    pool: str
    provider: str
    finish_reason: str
    prompt_token_estimate: int
    completion_token_estimate: int
    total_token_estimate: int
    max_tokens: int
    continuation_used: bool


class AIServiceUnavailableError(Exception):
    """Raised when every configured model fails to produce a response."""


class ModelHealthStats:
    __slots__ = (
        "model_name", "pool", "avg_latency", "success_count", "failure_count",
        "consecutive_failures", "cooldown_expires", "last_error",
    )

    def __init__(self, model_name: str, pool: str) -> None:
        self.model_name = model_name
        self.pool = pool
        self.avg_latency: float = 0.0
        self.success_count: int = 0
        self.failure_count: int = 0
        self.consecutive_failures: int = 0
        self.cooldown_expires: Optional[datetime] = None
        self.last_error: Optional[str] = None


class ResponseCache:
    __slots__ = ("_store", "_lock", "_ttl")

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self._store: Dict[str, Tuple[Any, datetime]] = {}
        self._lock = Lock()
        self._ttl = ttl_seconds

    def _make_key(self, prompt: str, max_tokens: int, intent: str) -> str:
        return f"{intent}:{max_tokens}:{hash(prompt)}"

    def get(self, prompt: str, max_tokens: int, intent: str) -> Optional[Any]:
        key = self._make_key(prompt, max_tokens, intent)
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires = entry
            if datetime.now(timezone.utc) > expires:
                self._store.pop(key, None)
                return None
            return value

    def set(self, prompt: str, max_tokens: int, intent: str, value: Any) -> None:
        key = self._make_key(prompt, max_tokens, intent)
        expires = datetime.now(timezone.utc) + timedelta(seconds=self._ttl)
        with self._lock:
            self._store[key] = (value, expires)

    def invalidate(self, prompt: str, max_tokens: int, intent: str) -> None:
        key = self._make_key(prompt, max_tokens, intent)
        with self._lock:
            self._store.pop(key, None)


_response_cache = ResponseCache(ttl_seconds=300.0)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_pool_for_intent(intent: str) -> str:
    if intent in ("greeting", "thanks", "small_talk"):
        return "conversation"
    if intent in ("assistant_identity", "assistant_capabilities"):
        return "conversation"
    if intent in ("general_knowledge", "financial_general"):
        return "general_knowledge"
    if intent in (
        "anomaly_lookup",
        "reconciliation_analysis",
        "report_summary",
        "dataset_review",
        "trend_analysis",
        "comparison",
        "recommendations",
        "financial_analysis",
    ):
        return "financial_analysis"
    if intent in ("invoice_lookup",):
        return "financial_analysis"
    return "financial_analysis"


def _is_model_in_cooldown(model_name: str) -> bool:
    with _health_lock:
        stats = _model_health.get(model_name)
        if not stats or not stats.cooldown_expires:
            return False
        if stats.cooldown_expires > _utcnow():
            return True
        stats.cooldown_expires = None
        stats.consecutive_failures = 0
        return False


def _record_success(model_name: str, latency: float) -> None:
    with _health_lock:
        stats = _model_health.setdefault(model_name, ModelHealthStats(model_name, "unknown"))
        stats.success_count += 1
        stats.consecutive_failures = 0
        stats.cooldown_expires = None
        stats.last_error = None
        if stats.avg_latency == 0.0:
            stats.avg_latency = latency
        else:
            stats.avg_latency = (stats.avg_latency * (stats.success_count - 1) + latency) / stats.success_count


def _record_failure(model_name: str, error: Exception, pool: str) -> None:
    is_rate_limit = isinstance(error, RateLimitError) or (
        isinstance(error, APIStatusError) and getattr(error, "status_code", None) == 429
    )
    cooldown_seconds = MODEL_COOLDOWN_SECONDS if is_rate_limit else MODEL_COOLDOWN_SECONDS * 2

    with _health_lock:
        stats = _model_health.setdefault(model_name, ModelHealthStats(model_name, pool))
        stats.failure_count += 1
        stats.consecutive_failures += 1
        stats.last_error = str(error)
        stats.pool = pool

        if stats.consecutive_failures >= FAILURE_THRESHOLD:
            stats.cooldown_expires = _utcnow() + timedelta(seconds=cooldown_seconds)
            stats.consecutive_failures = 0
            logger.warning(
                "Model %s reached failure threshold (%s). Cooling down for %ss (rate_limit=%s)",
                model_name, FAILURE_THRESHOLD, cooldown_seconds, is_rate_limit,
            )


def _is_retryable_error(error: Exception) -> bool:
    if isinstance(error, (APITimeoutError, APIConnectionError)):
        return True
    if isinstance(error, APIStatusError):
        return getattr(error, "status_code", None) in RETRYABLE_STATUS_CODES
    return False


def _select_next_model(
    models: List[ModelConfig],
    tried: set,
    intent: str,
) -> Optional[ModelConfig]:
    now = _utcnow()

    for model in models:
        if model.name in tried:
            continue
        if model.name in _disabled_by_config:
            continue
        with _health_lock:
            stats = _model_health.get(model.name)
            if stats and stats.cooldown_expires and stats.cooldown_expires > now:
                continue
        return model

    return None


_disabled_by_config: set = set()
_health_lock = Lock()
_model_health: Dict[str, ModelHealthStats] = {}


def disable_model_config(model_name: str) -> None:
    _disabled_by_config.add(model_name)


def enable_model_config(model_name: str) -> None:
    _disabled_by_config.discard(model_name)


def get_model_health(model_name: str) -> Optional[Dict[str, Any]]:
    with _health_lock:
        stats = _model_health.get(model_name)
        if not stats:
            return None
        return {
            "model_name": stats.model_name,
            "pool": stats.pool,
            "avg_latency": round(stats.avg_latency, 3),
            "success_count": stats.success_count,
            "failure_count": stats.failure_count,
            "consecutive_failures": stats.consecutive_failures,
            "cooldown_expires": stats.cooldown_expires.isoformat() if stats.cooldown_expires else None,
            "last_error": stats.last_error,
        }


def get_all_health() -> Dict[str, Dict[str, Any]]:
    result = {}
    now = _utcnow()
    with _health_lock:
        for name, stats in _model_health.items():
            total = stats.success_count + stats.failure_count
            success_rate = round((stats.success_count / total) * 100) if total > 0 else 0
            result[name] = {
                "pool": stats.pool,
                "avg_latency": round(stats.avg_latency, 3),
                "success_rate": success_rate,
                "success_count": stats.success_count,
                "failure_count": stats.failure_count,
                "cooldown_active": stats.cooldown_expires > now if stats.cooldown_expires else False,
                "last_updated": now.isoformat(),
            }
    return result


def _is_incomplete_response(answer: str) -> bool:
    if not answer:
        return True
    for pattern in INCOMPLETE_ENDINGS:
        if pattern.search(answer):
            return True
    return False


def _is_truncated_response(answer: str, finish_reason: Optional[str] = None) -> bool:
    """Check if the response is too short to be a meaningful answer (likely truncated)."""
    if not answer:
        return True
    if finish_reason == "length":
        return True
    return len(answer.strip()) < MIN_RESPONSE_LENGTH


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _summarize_usage(usage: Any) -> Optional[Dict[str, int]]:
    if usage is None:
        return None
    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def _merge_with_overlap_detection(original: str, continuation: str) -> str:
    """Merge continuation into original, detecting and removing any duplicated prefix.

    If the continuation starts by repeating the end of the original response,
    only the non-duplicated suffix is appended.
    """
    if not original or not continuation:
        return (original + " " + continuation).strip()

    # Try to find overlap of at least 10 characters
    min_overlap = 10
    max_overlap = min(len(original), len(continuation))
    overlap_len = 0

    for i in range(min_overlap, max_overlap + 1):
        suffix = original[-i:].strip()
        prefix = continuation[:i].strip()
        if suffix and prefix and suffix.lower() == prefix.lower():
            overlap_len = i

    if overlap_len >= min_overlap:
        return (original + continuation[overlap_len:]).strip()
    return (original + " " + continuation).strip()


def _get_token_limit_for_intent(intent: str, requested_max_tokens: int) -> int:
    return TOKEN_LIMITS.get(intent, requested_max_tokens)


def _call_model(model: ModelConfig, system_prompt: str, user_prompt: str, max_tokens: int = 900, timeout: float = 15.0) -> Tuple[str, Optional[str], Optional[Dict[str, int]]]:
    client = get_openrouter_client()
    response = client.chat.completions.create(
        model=model.name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
        timeout=timeout,
    )

    answer = response.choices[0].message.content
    if not answer:
        raise ValueError(f"Model {model.name} returned an empty response")

    return answer, response.choices[0].finish_reason, _summarize_usage(getattr(response, "usage", None))


def _call_model_continuation(model: ModelConfig, system_prompt: str, previous_answer: str, max_tokens: int = 900, timeout: float = 15.0) -> Tuple[str, Optional[str], Optional[Dict[str, int]]]:
    """
    Request a continuation of a previous partial answer.
    
    Uses the assistant's partial answer as conversation history so the model
    continues from where it left off, rather than re-answering the original question.
    """
    client = get_openrouter_client()
    response = client.chat.completions.create(
        model=model.name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": previous_answer},
            {"role": "user", "content": "Continue."},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
        timeout=timeout,
    )

    answer = response.choices[0].message.content
    if not answer:
        raise ValueError(f"Model {model.name} returned an empty continuation response")

    return answer, response.choices[0].finish_reason, _summarize_usage(getattr(response, "usage", None))


def _call_model_stream(model: ModelConfig, system_prompt: str, user_prompt: str, max_tokens: int = 900, timeout: float = 12.0, intent: str = "unknown"):
    """
    Stream response from a model with separate connection and read timeouts.

    Connection timeout is always 10s (fast TCP/TLS handshake).
    Read timeout varies by intent complexity (see STREAM_READ_TIMEOUTS).
    """
    client = get_openrouter_client()
    stream_timeout = httpx.Timeout(45.0, connect=10.0)

    stream = client.chat.completions.create(
        model=model.name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
        timeout=stream_timeout,
        stream=True,
    )

    for chunk in stream:
        yield chunk


def _try_model_call(
    model: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    start_time: float,
    pool: str,
) -> Tuple[Optional[str], Optional[Exception], Optional[str], Optional[Dict[str, int]]]:
    latency: float = 0.0
    try:
        answer, finish_reason, usage = _call_model(model=model, system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens)
        latency = time.perf_counter() - start_time
        _record_success(model.name, latency)
        return answer, None, finish_reason, usage
    except Exception as error:
        latency = time.perf_counter() - start_time
        _record_failure(model.name, error, pool)
        return None, error, None, None


def _try_model_call_continuation(
    model: ModelConfig,
    system_prompt: str,
    previous_answer: str,
    max_tokens: int,
    start_time: float,
    pool: str,
) -> Tuple[Optional[str], Optional[Exception], Optional[str], Optional[Dict[str, int]]]:
    latency: float = 0.0
    try:
        answer, finish_reason, usage = _call_model_continuation(model=model, system_prompt=system_prompt, previous_answer=previous_answer, max_tokens=max_tokens)
        latency = time.perf_counter() - start_time
        _record_success(model.name, latency)
        return answer, None, finish_reason, usage
    except Exception as error:
        latency = time.perf_counter() - start_time
        _record_failure(model.name, error, pool)
        return None, error, None, None


def _try_model_stream(
    model: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    start_time: float,
    pool: str,
    timeout: float = 12.0,
    intent: str = "unknown",
):
    collected: List[str] = []
    stream_error: Optional[Exception] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    chunk_count = 0
    try:
        for chunk in _call_model_stream(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            timeout=timeout,
            intent=intent,
        ):
            if not getattr(chunk, "choices", None):
                continue
            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)
            if delta and delta.content:
                collected.append(delta.content)
                chunk_count += 1
                yield delta.content, None
            if getattr(choice, "finish_reason", None) is not None:
                finish_reason = choice.finish_reason
            if getattr(chunk, "usage", None) is not None:
                usage = _summarize_usage(chunk.usage)
    except Exception as error:
        stream_error = error

    if stream_error is not None:
        latency = time.perf_counter() - start_time
        _record_failure(model.name, stream_error, pool)
        logger.info(
            "[STREAM DIAGNOSTIC] Model=%s | intent=%s | finish_reason=%s | chunks=%s | collected_chars=%s | latency=%ss | ERROR=%s",
            model.name, intent, finish_reason, chunk_count, sum(len(c) for c in collected), round(latency, 3), stream_error,
        )
        yield "", stream_error
        return

    if not collected:
        latency = time.perf_counter() - start_time
        error = ValueError(f"Model {model.name} returned an empty streaming response")
        _record_failure(model.name, error, pool)
        logger.info(
            "[STREAM DIAGNOSTIC] Model=%s | intent=%s | finish_reason=%s | chunks=%s | collected_chars=0 | latency=%ss | RESULT=EMPTY",
            model.name, intent, finish_reason, chunk_count, round(latency, 3),
        )
        yield "", error
        return

    latency = time.perf_counter() - start_time
    _record_success(model.name, latency)
    full_response = "".join(collected).strip()
    prompt_token_estimate = usage["prompt_tokens"] if usage and usage.get("prompt_tokens") else _estimate_tokens(system_prompt + user_prompt)
    completion_token_estimate = usage["completion_tokens"] if usage and usage.get("completion_tokens") else _estimate_tokens(full_response)
    total_token_estimate = usage["total_tokens"] if usage and usage.get("total_tokens") else prompt_token_estimate + completion_token_estimate
    logger.info(
        "[STREAM DIAGNOSTIC] Model=%s | intent=%s | finish_reason=%s | chunks=%s | collected_chars=%s | latency=%ss | RESULT=SUCCESS",
        model.name, intent, finish_reason or "stop", chunk_count, len(full_response), round(latency, 3),
    )
    yield "", {
        "finish_reason": finish_reason or "stop",
        "prompt_token_estimate": prompt_token_estimate,
        "completion_token_estimate": completion_token_estimate,
        "total_token_estimate": total_token_estimate,
        "max_tokens": max_tokens,
    }


def stream_answer(prompt: str, max_tokens: int = 900, intent: str = "unknown", context: str = "", model_override: Optional[str] = None):
    """
    Stream an answer from the configured LLM models with strict lifecycle enforcement.

    Core rules:
    1. Before the first chunk is yielded: model errors may trigger fallback to the next model.
    2. After the first chunk is yielded: the current model OWNS the response.
       - NEVER switch to another model.
       - NEVER request a continuation.
       - NEVER restart generation.
    3. If finish_reason == "length": append a truncation note and treat as SUCCESS.
    4. If an exception occurs after streaming has begun: log it, emit a graceful error,
       and terminate. Do NOT fallback.
    5. The "All models failed" error is only emitted when NO chunks were sent.
    
    If model_override is provided, only that specific model is used (no fallback).
    """
    start_time = time.perf_counter()
    total_attempts = 0
    model_errors: List[str] = []
    fallback_used = False
    max_tokens = _get_token_limit_for_intent(intent, max_tokens)

    system_prompt = build_system_prompt(context, intent=intent)

    # If a specific model is requested, create a single-tier config for that model
    if model_override:
        tiers = [ModelTier(models=[ModelConfig(name=model_override, tier=1, enabled=True)], timeout=30.0)]
    else:
        tiers = get_model_tiers(intent)
    tried: set = set()

    stream_started = False  # ⬅️ THE CRITICAL FLAG — once a chunk is yielded, no fallback allowed

    logger.info(
        "Model selection (streaming): intent=%s, tiers=%s, max_tokens=%s | Prompt size: %d words (~%d tokens)",
        intent, len(tiers), max_tokens, len(prompt.split()), _estimate_tokens(system_prompt + prompt),
    )

    for tier_index, tier in enumerate(tiers):
        tier_models = tier.models
        tier_timeout = tier.timeout
        tier_tried: set = set()

        logger.info(
            "Starting tier %s/%s with timeout %ss and %s models",
            tier_index + 1, len(tiers), tier_timeout, len(tier_models),
        )

        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed > REQUEST_BUDGET_SECONDS:
                if not stream_started:
                    logger.error("Streaming request exceeded time budget of %ss", REQUEST_BUDGET_SECONDS)
                    raise AIServiceUnavailableError(
                        f"Request exceeded time budget of {REQUEST_BUDGET_SECONDS}s"
                    )
                else:
                    # Stream already started — can't raise, just terminate gracefully
                    logger.error("Streaming request exceeded time budget after stream started")
                    return

            model = _select_next_model(tier_models, tier_tried, intent)
            if model is None:
                break  # No more models in this tier, move to next tier

            tier_tried.add(model.name)
            tried.add(model.name)
            fallback_used = fallback_used or len(tried) > 1
            total_attempts += 1

            pool = _get_pool_for_intent(intent)
            logger.info("Trying model %s (tier %s/%s, timeout=%ss)", model.name, tier_index + 1, len(tiers), tier_timeout)
            last_error: Optional[Exception] = None
            collected: List[str] = []
            first_token_recorded: bool = False
            finish_reason: Optional[str] = None
            prompt_token_estimate: int = _estimate_tokens(system_prompt + prompt)
            completion_token_estimate: int = 0
            total_token_estimate: int = 0

            try:
                for chunk, err in _try_model_stream(
                    model=model, system_prompt=system_prompt, user_prompt=prompt, max_tokens=max_tokens,
                    start_time=start_time, pool=pool, timeout=tier_timeout, intent=intent,
                ):
                    if err is not None:
                        last_error = err
                        model_errors.append(f"{model.name}: {err}")
                        if not stream_started:
                            # No chunks sent yet — allowed to fallback
                            logger.warning("Model %s failed before first chunk: %s", model.name, err)
                        else:
                            # Stream already started — cannot fallback
                            logger.error("Model %s failed AFTER streaming started: %s", model.name, err)
                        break
                    if isinstance(chunk, dict):
                        finish_reason = chunk.get("finish_reason", finish_reason)
                        prompt_token_estimate = chunk.get("prompt_token_estimate", prompt_token_estimate)
                        completion_token_estimate = chunk.get("completion_token_estimate", completion_token_estimate)
                        total_token_estimate = chunk.get("total_token_estimate", total_token_estimate)
                        continue
                    # Record time-to-first-token on the first non-empty chunk
                    if not first_token_recorded and chunk:
                        first_token_recorded = True
                        stream_started = True  # ⬅️ LOCK THE STREAM — no fallback after this point
                        time_to_first_token_sec = time.perf_counter() - start_time
                        time_to_first_token_ms = round(time_to_first_token_sec * 1000)
                        logger.info("Stream started from model %s (time_to_first_token=%sms)", model.name, time_to_first_token_ms)
                        # Emit dedicated metadata event BEFORE first content token
                        yield ("", {
                            "type": "metadata",
                            "model": model.name,
                            "provider": "OpenRouter",
                            "time_to_first_token_ms": time_to_first_token_ms,
                        })
                    collected.append(chunk)
                    yield chunk, None
            except Exception as error:
                last_error = error
                model_errors.append(f"{model.name}: {error}")
                if not stream_started:
                    logger.warning("Model %s failed with exception before first chunk: %s", model.name, error)
                    continue  # Allowed to fallback
                else:
                    logger.error("Model %s failed with exception AFTER streaming started: %s", model.name, error)
                    _record_failure(model.name, error, pool)
                    # Cannot fallback — terminate the stream gracefully but include model info for frontend
                    response_time = round(time.perf_counter() - start_time, 2)
                    yield ("", {
                        "error": True,
                        "message": f"Stream terminated due to model error: {error}",
                        "model": model.name,
                        "tier": model.tier,
                        "fallback_used": fallback_used,
                        "attempts": total_attempts,
                        "response_time": response_time,
                        "pool": MODEL_POOL_LABELS.get(pool, pool),
                    })
                    return

            # After stream generator completes (either naturally or via break)
            if last_error is not None:
                if not stream_started:
                    # No chunks were sent to the client — allowed to fallback to next model
                    _record_failure(model.name, last_error, pool)
                    continue  # Try next model in this tier
                else:
                    # Stream started but an error was encountered — cannot fallback
                    # This path is reached when the for loop above broke due to err being set
                    # but we've already yielded some chunks. Just return.
                    logger.error("Stream from model %s failed after some chunks were delivered, terminating.", model.name)
                    return

            if not collected:
                # No content was collected from this model
                if not stream_started:
                    error = ValueError(f"Model {model.name} returned an empty streaming response")
                    _record_failure(model.name, error, pool)
                    model_errors.append(f"{model.name}: {error}")
                    logger.warning("Model %s produced no tokens, trying next model", model.name)
                    continue
                else:
                    logger.error("Model %s stopped producing tokens after stream started (impossible state), terminating.", model.name)
                    return

            # At this point, we have collected tokens from a model.
            if finish_reason == "length":
                logger.info("Model %s hit finish_reason=length; yielding warning event.", model.name)
                yield "", {
                    "type": "warning",
                    "message": "Response truncated because maximum length was reached"
                }
                # Treat response as SUCCESS and proceed to metadata
            elif _is_truncated_response("".join(collected).strip(), finish_reason=finish_reason):
                # Response is too short to be meaningful (but not due to length — e.g. model stopped early)
                # This is a failure, but only if no stream started. Since we got tokens, stream_started is True,
                # so we just log and proceed anyway (better to deliver something than nothing).
                logger.warning("Model %s returned a short response (%s chars), but stream has started; delivering anyway.", model.name, len("".join(collected).strip()))

            # SUCCESS PATH — build metadata and finalize
            full_response = "".join(collected).strip()
            response_time = round(time.perf_counter() - start_time, 2)
            if not completion_token_estimate:
                completion_token_estimate = _estimate_tokens(full_response)
            if not total_token_estimate:
                total_token_estimate = prompt_token_estimate + completion_token_estimate
            output_tokens = len(full_response.split())
            logger.info(
                "Model=%s | Intent=%s | max_tokens=%s | finish_reason=%s | prompt_tokens~%s | completion_tokens~%s | total_tokens~%s | first_token=%sms | total_time=%ss | output_tokens=%s",
                model.name,
                intent,
                max_tokens,
                finish_reason or "stop",
                prompt_token_estimate,
                completion_token_estimate,
                total_token_estimate,
                time_to_first_token_ms if 'time_to_first_token_ms' in dir() else int(response_time * 1000),
                response_time,
                output_tokens,
            )

            yield (
                "",
                {
                    "model": model.name,
                    "tier": model.tier,
                    "fallback_used": fallback_used,
                    "attempts": total_attempts,
                    "response_time": response_time,
                    "cached": False,
                    "pool": MODEL_POOL_LABELS.get(pool, pool),
                    "finish_reason": finish_reason or "stop",
                    "prompt_token_estimate": prompt_token_estimate,
                    "completion_token_estimate": completion_token_estimate,
                    "total_token_estimate": total_token_estimate,
                    "max_tokens": max_tokens,
                    "continuation_used": False,
                },
            )
            return  # ⬅️ EXIT — successful response delivered

        # All models in this tier failed without streaming, log and continue to next tier
        logger.warning("Tier %s/%s exhausted, moving to next tier", tier_index + 1, len(tiers))

    # All models exhausted without sending any chunk
    logger.error("All tiers exhausted (streaming). Details: %s", " | ".join(model_errors))
    yield ("", {"error": True, "message": "AI service temporarily unavailable. All models failed."})


def generate_answer(prompt: str, max_tokens: int = 900, intent: str = "unknown", context: str = "") -> GenerateAnswerResult:
    start_time = time.perf_counter()
    total_attempts = 0
    model_errors: List[str] = []
    fallback_used = False
    continuation_used = False
    max_tokens = _get_token_limit_for_intent(intent, max_tokens)

    # Use tighter budget for simple definitional questions
    budget = FAST_REQUEST_BUDGET_SECONDS if intent in FAST_INTENTS else COMPLEX_REQUEST_BUDGET_SECONDS

    system_prompt = build_system_prompt(context, intent=intent)

    cached = _response_cache.get(prompt, max_tokens, intent)
    if cached is not None:
        logger.info("Returning cached response for intent=%s", intent)
        cached = dict(cached)
        cached["response_time"] = round(time.perf_counter() - start_time, 2)
        cached["cached"] = True
        return cached

    tiers = get_model_tiers(intent)
    tried: set = set()

    logger.info(
        "Model selection: intent=%s, tiers=%s, max_tokens=%s, budget=%ss",
        intent, len(tiers), max_tokens, budget,
    )

    for tier_index, tier in enumerate(tiers):
        tier_models = tier.models
        tier_tried: set = set()

        logger.info(
            "Starting tier %s/%s with %s models",
            tier_index + 1, len(tiers), len(tier_models),
        )

        while True:
            elapsed = time.perf_counter() - start_time
            if elapsed > budget:
                logger.error("Request exceeded time budget of %ss after %s attempts", budget, total_attempts)
                raise AIServiceUnavailableError(
                    f"Request exceeded time budget of {budget}s"
                )

            model = _select_next_model(tier_models, tier_tried, intent)
            if model is None:
                break  # No more models in this tier, move to next tier

            tier_tried.add(model.name)
            tried.add(model.name)
            fallback_used = fallback_used or len(tried) > 1

            pool = _get_pool_for_intent(intent)
            logger.info("Trying model %s (tier %s/%s, max_retries=%s)", model.name, tier_index + 1, len(tiers), MAX_RETRIES)

            # Try the model, with 1 retry only for retryable errors (timeout, 5xx)
            for attempt in range(MAX_RETRIES + 1):
                total_attempts += 1
                answer, error, finish_reason, usage = _try_model_call(
                    model=model, system_prompt=system_prompt, user_prompt=prompt, max_tokens=max_tokens,
                    start_time=start_time, pool=pool,
                )
                if answer is not None:
                    # Check for truncated responses (too short to be meaningful)
                    if _is_truncated_response(answer, finish_reason=finish_reason):
                        truncated_error = ValueError(
                            f"Model {model.name} returned a truncated response ({len(answer.strip())} chars, "
                            f"min expected {MIN_RESPONSE_LENGTH})"
                        )
                        _record_failure(model.name, truncated_error, pool)
                        model_errors.append(f"{model.name}: {truncated_error}")
                        logger.warning(
                            "Response from model %s is truncated (%s chars < %s minimum). Triggering fallback.",
                            model.name, len(answer.strip()), MIN_RESPONSE_LENGTH,
                        )
                        if finish_reason == "length" and not continuation_used:
                            continuation_used = True
                            logger.info("Model %s hit finish_reason=length; requesting one continuation.", model.name)
                            continuation_answer, continuation_error, continuation_finish_reason, continuation_usage = _try_model_call_continuation(
                                model=model,
                                system_prompt=system_prompt,
                                previous_answer=answer,
                                max_tokens=max_tokens,
                                start_time=start_time,
                                pool=pool,
                            )
                            if continuation_answer is not None and not _is_truncated_response(continuation_answer, finish_reason=continuation_finish_reason):
                                answer = _merge_with_overlap_detection(answer, continuation_answer)
                                finish_reason = continuation_finish_reason or "stop"
                                usage = continuation_usage or usage
                            else:
                                error = truncated_error if continuation_error is None else continuation_error
                        else:
                            # Treat as a failure to trigger the next model selection
                            error = truncated_error
                    else:
                        if _is_incomplete_response(answer):
                            logger.warning("Response from model %s appears incomplete. Attempting continuation.", model.name)
                            try:
                                continuation, cont_error, continuation_finish_reason, continuation_usage = _try_model_call_continuation(
                                    model=model, system_prompt=system_prompt, previous_answer=answer, max_tokens=max_tokens,
                                    start_time=start_time, pool=pool,
                                )
                                if continuation and not _is_incomplete_response(continuation):
                                    answer = _merge_with_overlap_detection(answer, continuation)
                                    finish_reason = continuation_finish_reason or finish_reason
                                    usage = continuation_usage or usage
                            except Exception:
                                pass

                        response_time = round(time.perf_counter() - start_time, 2)
                        prompt_token_estimate = usage["prompt_tokens"] if usage and usage.get("prompt_tokens") else _estimate_tokens(system_prompt + prompt)
                        completion_token_estimate = usage["completion_tokens"] if usage and usage.get("completion_tokens") else _estimate_tokens(answer)
                        total_token_estimate = usage["total_tokens"] if usage and usage.get("total_tokens") else prompt_token_estimate + completion_token_estimate
                        logger.info(
                            "Model=%s | Intent=%s | max_tokens=%s | finish_reason=%s | prompt_tokens~%s | completion_tokens~%s | total_tokens~%s | total_generation_time=%ss",
                            model.name,
                            intent,
                            max_tokens,
                            finish_reason or "stop",
                            prompt_token_estimate,
                            completion_token_estimate,
                            total_token_estimate,
                            response_time,
                        )
                        result: GenerateAnswerResult = {
                            "answer": answer,
                            "model": model.name,
                            "tier": model.tier,
                            "fallback_used": fallback_used,
                            "attempts": total_attempts,
                            "response_time": response_time,
                            "cached": False,
                            "pool": MODEL_POOL_LABELS.get(pool, pool),
                            "provider": "OpenRouter",
                            "finish_reason": finish_reason or "stop",
                            "prompt_token_estimate": prompt_token_estimate,
                            "completion_token_estimate": completion_token_estimate,
                            "total_token_estimate": total_token_estimate,
                            "max_tokens": max_tokens,
                            "continuation_used": continuation_used,
                        }
                        _response_cache.set(prompt, max_tokens, intent, result)
                        logger.info("Successful response from model %s (tier %s/%s)", model.name, tier_index + 1, len(tiers))
                        return result

                # Retry only for retryable errors (timeout, 5xx), not for truncation or non-retryable
                if error is not None and _is_retryable_error(error) and attempt < MAX_RETRIES:
                    wait_seconds = 1.0
                    logger.warning(
                        "Retryable error from model %s (attempt %s/%s). Retrying in %ss. Error: %s",
                        model.name, attempt + 1, MAX_RETRIES + 1, wait_seconds, error,
                    )
                    time.sleep(wait_seconds)
                    continue
                break

            if error is not None:
                model_errors.append(f"{model.name}: {error}")
                logger.warning("Model %s failed, switching to next model: %s", model.name, error)

        # All models in this tier failed, log and continue to next tier
        logger.warning("Tier %s/%s exhausted, moving to next tier", tier_index + 1, len(tiers))

    logger.error("All tiers exhausted. Details: %s", " | ".join(model_errors))
    raise AIServiceUnavailableError("AI service temporarily unavailable. All models failed.")