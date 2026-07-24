from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class FinishReason(Enum):
    """Reason why a generation ended."""
    COMPLETED = "completed"
    STOPPED_BY_USER = "stopped_by_user"
    MAX_TOKENS = "max_tokens"
    MODEL_TIMEOUT = "model_timeout"
    PROVIDER_ERROR = "provider_error"
    RATE_LIMIT = "rate_limit"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class GenerationState:
    """State for an ongoing or interrupted generation."""
    session_id: str
    conversation_id: Optional[str]
    original_user_prompt: str
    final_prompt_sent: str
    conversation_history: list
    accumulated_text: str = ""
    current_model: Optional[str] = None
    generation_status: str = "in_progress"  # in_progress, completed, interrupted
    finish_reason: FinishReason = FinishReason.COMPLETED
    request_id: Optional[str] = None
    intent: Optional[str] = None
    context: Optional[str] = None
    max_tokens: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_incomplete(self) -> bool:
        """Check if the generation was incomplete."""
        return self.finish_reason != FinishReason.COMPLETED
    
    def can_continue(self) -> bool:
        """Check if this generation can be continued."""
        return (
            self.is_incomplete() and 
            self.accumulated_text and 
            self.generation_status == "interrupted"
        )


class ContinuationStateManager:
    """Manages continuation state for interrupted generations."""
    
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._states: Dict[str, GenerationState] = {}
    
    def get_state(self, session_id: str) -> Optional[GenerationState]:
        """Get the current continuation state for a session."""
        with self._lock:
            return self._states.get(session_id)
    
    def start_generation(
        self,
        session_id: str,
        conversation_id: Optional[str],
        original_user_prompt: str,
        final_prompt_sent: str,
        conversation_history: list,
        request_id: Optional[str] = None,
        intent: Optional[str] = None,
        context: Optional[str] = None,
        max_tokens: int = 0,
    ) -> GenerationState:
        """Start tracking a new generation."""
        with self._lock:
            state = GenerationState(
                session_id=session_id,
                conversation_id=conversation_id,
                original_user_prompt=original_user_prompt,
                final_prompt_sent=final_prompt_sent,
                conversation_history=conversation_history,
                request_id=request_id,
                intent=intent,
                context=context,
                max_tokens=max_tokens,
                generation_status="in_progress",
                finish_reason=FinishReason.COMPLETED,
            )
            self._states[session_id] = state
            logger.info(
                "[Continuation] Started generation for session %s (request_id=%s, intent=%s)",
                session_id, request_id, intent,
            )
            return state
    
    def update_accumulated_text(self, session_id: str, text: str) -> None:
        """Update the accumulated text for a generation."""
        with self._lock:
            state = self._states.get(session_id)
            if state:
                state.accumulated_text = text
    
    def update_model(self, session_id: str, model: str) -> None:
        """Update the current model for a generation."""
        with self._lock:
            state = self._states.get(session_id)
            if state:
                state.current_model = model
    
    def mark_completed(
        self,
        session_id: str,
        finish_reason: FinishReason = FinishReason.COMPLETED,
    ) -> None:
        """Mark a generation as completed."""
        with self._lock:
            state = self._states.get(session_id)
            if state:
                state.generation_status = "completed"
                state.finish_reason = finish_reason
                logger.info(
                    "[Continuation] Marked generation as completed for session %s (reason=%s)",
                    session_id, finish_reason.value,
                )
                # Clear the state after completion
                self._states.pop(session_id, None)
    
    def mark_interrupted(
        self,
        session_id: str,
        finish_reason: FinishReason,
    ) -> None:
        """Mark a generation as interrupted (can be continued)."""
        with self._lock:
            state = self._states.get(session_id)
            if state:
                state.generation_status = "interrupted"
                state.finish_reason = finish_reason
                logger.info(
                    "[Continuation] Marked generation as interrupted for session %s (reason=%s, text_length=%s)",
                    session_id, finish_reason.value, len(state.accumulated_text),
                )
    
    def clear_state(self, session_id: str) -> None:
        """Clear continuation state for a session."""
        with self._lock:
            self._states.pop(session_id, None)
            logger.info("[Continuation] Cleared state for session %s", session_id)
    
    def reset_all(self) -> None:
        """Clear all continuation states (e.g., on server restart)."""
        with self._lock:
            self._states.clear()
            logger.info("[Continuation] Cleared all states")


continuation_state_manager = ContinuationStateManager()


def get_continuation_state(session_id: str) -> Optional[GenerationState]:
    """Get continuation state for a session."""
    return continuation_state_manager.get_state(session_id)


def is_continue_request(user_message: str) -> bool:
    """Check if the user message is a continuation request."""
    continue_phrases = [
        "continue",
        "continue please",
        "go on",
        "finish your answer",
        "keep going",
        "continue where you stopped",
        "continue where you left off",
        "resume",
        "complete your answer",
    ]
    message_lower = user_message.lower().strip()
    return any(phrase in message_lower for phrase in continue_phrases)
