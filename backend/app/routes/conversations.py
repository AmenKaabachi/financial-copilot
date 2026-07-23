from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database.supabase_client import get_supabase_client
from app.services.conversation import generate_conversation_title

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Pydantic Models
# ============================================================

class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", max_length=255)
    user_id: Optional[str] = Field(default=None, max_length=255)


class ConversationResponse(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str
    preview: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    user_message: str
    ai_response: str
    created_at: str


class ConversationDetail(ConversationResponse):
    messages: List[MessageResponse]


class SaveMessageRequest(BaseModel):
    conversation_id: str
    user_message: str
    ai_response: str
    user_id: Optional[str] = Field(default=None, max_length=255)
    session_id: Optional[str] = Field(default=None, max_length=255)


class SaveMessageResponse(BaseModel):
    id: str
    conversation_id: str
    user_message: str
    ai_response: str
    created_at: str


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


# ============================================================
# Helper Functions
# ============================================================

def _table(table: str):
    return get_supabase_client().table(table)


def _format_datetime(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


# ============================================================
# Endpoints
# ============================================================

@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(request: ConversationCreate):
    """Create a new conversation."""
    try:
        result = (
            _table("conversations")
            .insert({
                "user_id": request.user_id,
                "title": request.title,
            })
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create conversation")

        conversation = result.data[0]
        return ConversationResponse(
            id=str(conversation["id"]),
            title=conversation["title"],
            message_count=0,
            created_at=_format_datetime(conversation["created_at"]),
            updated_at=_format_datetime(conversation["updated_at"]),
        )
    except Exception as exc:
        logger.exception("Failed to create conversation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(
    user_id: Optional[str] = Query(default=None, description="Filter by user ID (for future auth)"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum conversations to return"),
    offset: int = Query(default=0, ge=0, description="Number of conversations to skip"),
):
    """Retrieve user conversations ordered by most recent activity."""
    try:
        query = (
            _table("conversations")
            .select(
                "id, title, created_at, updated_at, "
                "chat_history(count)"
            )
            .order("updated_at", desc=True)
            .limit(limit)
            .offset(offset)
        )

        if user_id:
            query = query.eq("user_id", user_id)

        result = query.execute()
        conversations = result.data or []

        response: List[ConversationResponse] = []
        for conv in conversations:
            history = conv.get("chat_history", [])
            message_count = len(history) if isinstance(history, list) else 0

            # Generate preview from most recent message
            preview = None
            if message_count > 0 and isinstance(history, list) and len(history) > 0:
                last_msg = history[0]
                if isinstance(last_msg, dict):
                    preview_text = last_msg.get("user_message", "")
                    if len(preview_text) > 80:
                        preview_text = preview_text[:80].rstrip() + "..."
                    preview = preview_text or None

            response.append(ConversationResponse(
                id=str(conv["id"]),
                title=conv["title"],
                message_count=message_count,
                created_at=_format_datetime(conv["created_at"]),
                updated_at=_format_datetime(conv["updated_at"]),
                preview=preview,
            ))

        return response
    except Exception as exc:
        logger.exception("Failed to list conversations: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/conversations/{conversation_id}/messages", response_model=ConversationDetail)
def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500, description="Maximum messages to return"),
    offset: int = Query(default=0, ge=0, description="Number of messages to skip"),
):
    """Retrieve all messages from a specific conversation."""
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format") from exc

    try:
        # Fetch conversation details
        conv_result = (
            _table("conversations")
            .select("id, title, created_at, updated_at")
            .eq("id", str(conv_uuid))
            .limit(1)
            .execute()
        )

        if not conv_result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation = conv_result.data[0]

        # Fetch messages ordered by creation time
        msg_result = (
            _table("chat_history")
            .select("id, user_message, ai_response, created_at")
            .eq("conversation_id", str(conv_uuid))
            .order("created_at", desc=False)
            .limit(limit)
            .offset(offset)
            .execute()
        )

        messages = msg_result.data or []

        message_responses = [
            MessageResponse(
                id=str(msg["id"]),
                user_message=msg["user_message"],
                ai_response=msg["ai_response"],
                created_at=_format_datetime(msg["created_at"]),
            )
            for msg in messages
        ]

        return ConversationDetail(
            id=str(conversation["id"]),
            title=conversation["title"],
            message_count=len(messages),
            created_at=_format_datetime(conversation["created_at"]),
            updated_at=_format_datetime(conversation["updated_at"]),
            messages=message_responses,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get conversation messages: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chat/history", response_model=SaveMessageResponse)
def save_chat_message(request: SaveMessageRequest):
    """Save a new message pair to chat history and update conversation metadata."""
    try:
        conv_uuid = UUID(request.conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format") from exc

    try:
        # Verify conversation exists
        conv_result = (
            _table("conversations")
            .select("id, title")
            .eq("id", str(conv_uuid))
            .limit(1)
            .execute()
        )

        if not conv_result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation = conv_result.data[0]

        # Auto-title conversation from first message if still "New Conversation"
        if conversation["title"] == "New Conversation":
            new_title = generate_conversation_title(request.user_message, request.ai_response)
            _table("conversations").update({"title": new_title, "updated_at": datetime.utcnow().isoformat()}).eq("id", str(conv_uuid)).execute()

        # Insert message
        msg_result = (
            _table("chat_history")
            .insert({
                "conversation_id": str(conv_uuid),
                "user_message": request.user_message,
                "ai_response": request.ai_response,
                "user_id": request.user_id,
            })
            .execute()
        )

        if not msg_result.data:
            raise HTTPException(status_code=500, detail="Failed to save message")

        # Update conversation timestamp
        _table("conversations").update({"updated_at": datetime.utcnow().isoformat()}).eq("id", str(conv_uuid)).execute()

        message = msg_result.data[0]
        return SaveMessageResponse(
            id=str(message["id"]),
            conversation_id=str(message["conversation_id"]),
            user_message=message["user_message"],
            ai_response=message["ai_response"],
            created_at=_format_datetime(message["created_at"]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save chat message: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages."""
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format") from exc

    try:
        result = (
            _table("conversations")
            .delete()
            .eq("id", str(conv_uuid))
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete conversation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, request: RenameConversationRequest):
    """Rename a conversation."""
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation_id format") from exc

    try:
        result = (
            _table("conversations")
            .select("id")
            .eq("id", str(conv_uuid))
            .limit(1)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")

        _table("conversations").update({"title": request.title}).eq("id", str(conv_uuid)).execute()

        return {"message": "Conversation renamed successfully", "title": request.title}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to rename conversation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
