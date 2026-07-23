from __future__ import annotations

import logging
import re
from typing import Optional

from database.supabase_client import get_supabase_client
from app.services.llm import generate_answer


logger = logging.getLogger(__name__)


def _fallback_title(text: str, max_length: int = 60) -> str:
    """Fallback title generation without LLM."""
    first_sentence = text.split('.')[0].split('?')[0].strip()
    if len(first_sentence) > max_length:
        first_sentence = first_sentence[:max_length].rstrip() + '...'
    return first_sentence or "New Conversation"


def generate_conversation_title(user_message: str, ai_response: str) -> str:
    text = user_message.strip()
    if not text:
        return "New Conversation"

    lower = text.lower()

    invoice_match = re.search(r'(INV\w+)', text, re.IGNORECASE)
    if invoice_match:
        return f"Invoice {invoice_match.group(1)} Analysis"

    if "reconciliation" in lower:
        return "Reconciliation Overview"

    if "anomaly" in lower:
        return "Anomaly Analysis"

    if "duplicate payment" in lower:
        return "Duplicate Payment Review"

    if "missing payment" in lower:
        return "Missing Payment Review"

    try:
        prompt = (
            "You are generating a conversation title. "
            "Return ONLY a short title between 3 and 6 words. "
            "No punctuation. No quotes. No markdown."
        )
        result = generate_answer(prompt, max_tokens=20, intent="general_knowledge")
        title = result.get("answer", "").strip()
        title = re.sub(r'^["\']+|["\']+$', "", title)
        title = title.split("\n")[0].strip()
        if not title or len(title.split()) < 3:
            return _fallback_title(text)
        return title
    except Exception:
        return _fallback_title(text)


class ConversationService:
    @staticmethod
    def save_message(
        conversation_id: Optional[str],
        user_message: str,
        ai_response: str,
    ) -> None:
        if not conversation_id:
            return
        try:
            get_supabase_client().table("chat_history").insert({
                "conversation_id": conversation_id,
                "user_message": user_message,
                "ai_response": ai_response,
            }).execute()

            ConversationService._auto_title_conversation(conversation_id, user_message, ai_response)

            logger.info("Chat history saved successfully")
        except Exception as exc:
            logger.warning("Failed to save chat history: %s", exc)

    @staticmethod
    def _auto_title_conversation(conversation_id: str, user_message: str, ai_response: str) -> None:
        try:
            result = (
                get_supabase_client()
                .table("conversations")
                .select("title")
                .eq("id", conversation_id)
                .limit(1)
                .execute()
            )
            if not result.data:
                return
            current_title = result.data[0].get("title", "")
            if current_title != "New Conversation":
                return

            new_title = generate_conversation_title(user_message, ai_response)
            get_supabase_client().table("conversations").update({
                "title": new_title,
                "updated_at": "now()"
            }).eq("id", conversation_id).execute()
        except Exception as exc:
            logger.warning("Failed to auto-title conversation: %s", exc)
