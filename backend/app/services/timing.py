"""
Structured request timing and metrics collection.

Provides a RequestTimer context manager that captures per-stage latency,
request IDs, and token metrics for the full request lifecycle.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class StageTiming:
    name: str
    start: float
    end: float | None = None
    detail: str = ""

    @property
    def elapsed_ms(self) -> float:
        return round((self.end - self.start) * 1000, 1)


@dataclass
class RequestMetrics:
    request_id: str
    intent: str = ""
    model: str = ""
    provider: str = ""
    pool: str = ""
    finish_reason: str = ""
    cache_hit: bool = False
    fallback_used: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    max_tokens: int = 0
    prompt_size_chars: int = 0
    rows_retrieved: int = 0
    database_used: bool = False
    error: Optional[str] = None
    stages: List[StageTiming] = field(default_factory=list)
    _start: float = field(default_factory=time.perf_counter)
    _current_stage: Optional[StageTiming] = None

    @staticmethod
    def new() -> RequestMetrics:
        return RequestMetrics(request_id=uuid.uuid4().hex[:8].upper())

    def begin_stage(self, name: str, detail: Optional[str] = None) -> None:
        """Start timing a new stage. If a stage is already open, close it first."""
        if self._current_stage is not None:
            self.end_stage()
        self._current_stage = StageTiming(
            name=name,
            start=time.perf_counter(),
            detail=detail,
        )

    def end_stage(self) -> None:
        """Finish the current stage and record it."""
        if self._current_stage is not None:
            self._current_stage.end = time.perf_counter()
            self.stages.append(self._current_stage)
            self._current_stage = None

    def elapsed_since_start(self) -> float:
        return time.perf_counter() - self._start

    def get_stage_ms(self, name: str) -> float:
        """Get elapsed time for a specific stage by name."""
        for s in self.stages:
            if s.name == name:
                return s.elapsed_ms
        return 0.0

    def get_stage_detail(self, name: str) -> Optional[str]:
        for s in self.stages:
            if s.name == name:
                return s.detail
        return None

    def log_summary(self) -> None:
        """Log a structured summary of the entire request."""
        total_ms = round(self.elapsed_since_start() * 1000, 1)

        lines = [
            f"======== Request [{self.request_id}] ========",
            f"Intent             : {self.intent}",
        ]

        # Per-stage breakdown
        for stage in self.stages:
            detail = f" | {stage.detail}" if stage.detail else ""
            lines.append(f"  {stage.name:<18} : {stage.elapsed_ms:>8.1f}ms{detail}")

        # Model info
        lines.append(f"Model              : {self.model or 'N/A'}")
        lines.append(f"Provider           : {self.provider or 'N/A'}")
        lines.append(f"Pool               : {self.pool or 'N/A'}")
        lines.append(f"Finish Reason      : {self.finish_reason or 'N/A'}")

        # Token metrics
        lines.append(f"Prompt Tokens      : {self.prompt_tokens}")
        lines.append(f"Completion Tokens  : {self.completion_tokens}")
        lines.append(f"Total Tokens       : {self.total_tokens}")
        lines.append(f"Max Tokens         : {self.max_tokens}")
        if self.completion_tokens > 0 and total_ms > 0:
            tokens_per_sec = round(self.completion_tokens / (total_ms / 1000), 1)
            lines.append(f"Tokens/sec         : {tokens_per_sec}")

        # Context info
        lines.append(f"Prompt Size (chars): {self.prompt_size_chars}")
        lines.append(f"Rows Retrieved     : {self.rows_retrieved}")
        lines.append(f"Database Used      : {self.database_used}")

        # Cache / fallback
        lines.append(f"Cache Hit          : {self.cache_hit}")
        lines.append(f"Fallback Used      : {self.fallback_used}")

        # Error
        if self.error:
            lines.append(f"Error              : {self.error}")

        lines.append(f"Total Time         : {total_ms:>8.1f}ms")
        lines.append("=" * 50)

        logger.info("\n".join(lines))

    def to_dict(self) -> Dict[str, Any]:
        """Return metrics as a dict for embedding in SSE metadata."""
        total_ms = round(self.elapsed_since_start() * 1000, 1)
        return {
            "request_id": self.request_id,
            "intent": self.intent,
            "model": self.model,
            "provider": self.provider,
            "pool": self.pool,
            "finish_reason": self.finish_reason,
            "cache_hit": self.cache_hit,
            "fallback_used": self.fallback_used,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "max_tokens": self.max_tokens,
            "prompt_size_chars": self.prompt_size_chars,
            "rows_retrieved": self.rows_retrieved,
            "database_used": self.database_used,
            "total_time_ms": total_ms,
            "stages": {
                s.name: {"elapsed_ms": s.elapsed_ms, "detail": s.detail}
                for s in self.stages
            },
        }