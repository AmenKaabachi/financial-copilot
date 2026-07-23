from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    session_id: str = "default"
    active_intent: Optional[str] = None
    active_entity: Optional[Dict[str, str]] = None
    last_analysis_type: Optional[str] = None
    last_tool_used: Optional[str] = None
    last_response_status: Optional[str] = None
    previous_intent: Optional[str] = None


class ConversationStateManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._states: Dict[str, ConversationState] = {}

    def get_state(self, session_id: str = "default") -> ConversationState:
        with self._lock:
            if session_id not in self._states:
                self._states[session_id] = ConversationState(session_id=session_id)
            return self._states[session_id]

    def update_state(
        self,
        session_id: str,
        *,
        active_intent: Optional[str] = None,
        active_entity: Optional[Dict[str, str]] = None,
        last_analysis_type: Optional[str] = None,
        last_tool_used: Optional[str] = None,
        last_response_status: Optional[str] = None,
    ) -> ConversationState:
        with self._lock:
            state = self.get_state(session_id)
            if active_intent is not None:
                state.previous_intent = state.active_intent
                state.active_intent = active_intent
            if active_entity is not None:
                state.active_entity = active_entity
            if last_analysis_type is not None:
                state.last_analysis_type = last_analysis_type
            if last_tool_used is not None:
                state.last_tool_used = last_tool_used
            if last_response_status is not None:
                state.last_response_status = last_response_status
            return state

    def reset(self, session_id: str = "default") -> None:
        with self._lock:
            self._states[session_id] = ConversationState(session_id=session_id)


conversation_state_manager = ConversationStateManager()


def get_conversation_state(session_id: str = "default") -> ConversationState:
    return conversation_state_manager.get_state(session_id)
