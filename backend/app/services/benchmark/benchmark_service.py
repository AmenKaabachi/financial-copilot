from __future__ import annotations

import logging
import time
import json
import httpx
from typing import List, Dict, Any, Optional

from openai import (
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    APIStatusError,
)

from app.services.llm.client import get_openrouter_client
from app.services.llm.prompts import build_system_prompt, build_user_prompt, intent_result_from_route
from app.services.llm.routing import IntentClassifier, IntentType
from app.services.benchmark.benchmark_models import (
    BenchmarkRequest,
    BenchmarkResult,
    BenchmarkResponse,
    BenchmarkRanking,
)

logger = logging.getLogger(__name__)
classifier = IntentClassifier()

def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def run_model_test(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    temperature: float = 0.2,
) -> BenchmarkResult:
    """
    Executes a direct streaming call to the specific OpenRouter model without any fallback.
    Measures Time to First Token (TTFT), total response latency, token usage, and tokens/second.
    """
    client = get_openrouter_client()
    start_time = time.perf_counter()
    first_token_time: Optional[float] = None
    collected_tokens: List[str] = []

    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    try:
        stream_timeout = httpx.Timeout(60.0, connect=15.0)
        stream = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=stream_timeout,
            stream=True,
        )

        for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue
            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)
            if delta and delta.content:
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                collected_tokens.append(delta.content)

            if getattr(chunk, "usage", None) is not None:
                u = chunk.usage
                prompt_tokens = int(getattr(u, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(u, "completion_tokens", 0) or 0)
                total_tokens = int(getattr(u, "total_tokens", 0) or 0)

        end_time = time.perf_counter()
        response_time_sec = end_time - start_time
        response_time_ms = round(response_time_sec * 1000, 2)

        if first_token_time is not None:
            ttft_ms = round((first_token_time - start_time) * 1000, 2)
        else:
            ttft_ms = response_time_ms

        full_answer = "".join(collected_tokens).strip()

        if not full_answer:
            return BenchmarkResult(
                model=model_name,
                provider="OpenRouter",
                answer="",
                status="FAILED",
                response_time_ms=response_time_ms,
                ttft_ms=ttft_ms,
                error="Model returned empty response",
            )

        if not prompt_tokens:
            prompt_tokens = _estimate_tokens(system_prompt + user_prompt)
        if not completion_tokens:
            completion_tokens = _estimate_tokens(full_answer)
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens

        tps = round(completion_tokens / response_time_sec, 2) if response_time_sec > 0 else 0.0

        return BenchmarkResult(
            model=model_name,
            provider="OpenRouter",
            answer=full_answer,
            status="SUCCESS",
            response_time_ms=response_time_ms,
            ttft_ms=ttft_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            tokens_per_second=tps,
        )

    except RateLimitError as e:
        end_time = time.perf_counter()
        return BenchmarkResult(
            model=model_name,
            provider="OpenRouter",
            status="RATE_LIMIT",
            response_time_ms=round((end_time - start_time) * 1000, 2),
            error=str(e),
        )
    except (APITimeoutError, httpx.TimeoutException) as e:
        end_time = time.perf_counter()
        return BenchmarkResult(
            model=model_name,
            provider="OpenRouter",
            status="TIMEOUT",
            response_time_ms=round((end_time - start_time) * 1000, 2),
            error=str(e),
        )
    except APIStatusError as e:
        end_time = time.perf_counter()
        status_code = getattr(e, "status_code", None)
        status_label = "RATE_LIMIT" if status_code == 429 else "FAILED"
        return BenchmarkResult(
            model=model_name,
            provider="OpenRouter",
            status=status_label,
            response_time_ms=round((end_time - start_time) * 1000, 2),
            error=str(e),
        )
    except Exception as e:
        end_time = time.perf_counter()
        logger.error(f"Benchmark call for model {model_name} failed: {e}")
        return BenchmarkResult(
            model=model_name,
            provider="OpenRouter",
            status="FAILED",
            response_time_ms=round((end_time - start_time) * 1000, 2),
            error=str(e),
        )

def compare_results(results: List[BenchmarkResult]) -> BenchmarkRanking:
    """
    Calculates Rankings across all benchmark results:
    - Fastest Model (Lowest response time)
    - Best Latency (Lowest TTFT)
    - Most Token Efficient (Lowest total tokens among successful)
    - Most Reliable (Highest status rate)
    - Recommended Production Model (Weighted Score)
    """
    successful = [r for r in results if r.status == "SUCCESS"]
    if not successful:
        return BenchmarkRanking()

    fastest = min(successful, key=lambda r: r.response_time_ms)
    best_ttft = min(successful, key=lambda r: r.ttft_ms)
    most_efficient = min(successful, key=lambda r: r.total_tokens)

    # Weighted scoring formula:
    # 25% Latency (lower is better)
    # 15% Token Efficiency (lower total tokens is better)
    # 10% Speed (tokens/sec higher is better)
    # 20% TTFT (lower is better)
    # 30% Quality/Reliability (status == SUCCESS gets 1.0)
    
    max_response_time = max(r.response_time_ms for r in successful) or 1.0
    max_tokens = max(r.total_tokens for r in successful) or 1.0
    max_tps = max(r.tokens_per_second for r in successful) or 1.0
    max_ttft = max(r.ttft_ms for r in successful) or 1.0

    def calculate_score(r: BenchmarkResult) -> float:
        norm_latency = 1.0 - (r.response_time_ms / max_response_time)
        norm_tokens = 1.0 - (r.total_tokens / max_tokens)
        norm_tps = r.tokens_per_second / max_tps
        norm_ttft = 1.0 - (r.ttft_ms / max_ttft)
        
        score = (0.25 * norm_latency) + (0.15 * norm_tokens) + (0.10 * norm_tps) + (0.20 * norm_ttft) + (0.30 * 1.0)
        return score

    recommended = max(successful, key=calculate_score)

    return BenchmarkRanking(
        fastest_model=fastest.model,
        best_latency_model=best_ttft.model,
        best_quality_model=recommended.model,
        most_efficient_model=most_efficient.model,
        most_reliable_model=fastest.model if len(successful) == len(results) else None,
        recommended_production_model=recommended.model,
    )
