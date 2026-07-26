from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.modules.copilot.services.routing import IntentRoute, IntentType


logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    intent: IntentType
    needs_database: bool
    requires_llm: bool
    recommended_max_tokens: int
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    fast_response: Optional[str] = None
    direct_answer_key: Optional[str] = None


def intent_result_from_route(route: IntentRoute) -> IntentResult:
    return IntentResult(
        intent=route.intent,
        needs_database=route.needs_database,
        requires_llm=route.requires_llm,
        recommended_max_tokens=route.recommended_max_tokens,
        extracted_entities=dict(route.retrieved_entities),
        fast_response=route.fast_response,
        direct_answer_key=route.direct_answer_key,
    )


def build_user_prompt(context: Any, question: str, intent: IntentType = IntentType.UNKNOWN) -> str:
    if intent in (IntentType.GENERAL_KNOWLEDGE, IntentType.FINANCIAL_GENERAL):
        return (
            f"User question:\n\n{question}\n\n"
            "Answer as a concise financial knowledge explanation. Do not query the database."
        )

    if context is None:
        return (
            f"User question:\n\n{question}\n\n"
            "No financial context was retrieved. Answer the question using your training knowledge."
        )

    parts = [f"User question:\n\n{question}"]

    if isinstance(context, dict):
        if context.get("invoice"):
            parts.append(f"Invoice details:\n{context['invoice']}")
        if context.get("anomaly"):
            parts.append(f"Anomaly details:\n{context['anomaly']}")
        if context.get("reconciliation"):
            parts.append(f"Reconciliation details:\n{context['reconciliation']}")
        if context.get("transactions"):
            parts.append(f"Related transactions:\n{context['transactions']}")
        if context.get("analysis"):
            parts.append(f"Financial analysis:\n{context['analysis']}")
        if context.get("summary"):
            parts.append(f"Dataset summary:\n{context['summary']}")
        if context.get("high_severity_anomalies"):
            parts.append(f"High severity anomalies:\n{context['high_severity_anomalies']}")
        if context.get("duplicate_payments"):
            parts.append(f"Duplicate payments:\n{context['duplicate_payments']}")
        if context.get("missing_payments"):
            parts.append(f"Missing payments:\n{context['missing_payments']}")
        if context.get("recent_reconciliation"):
            parts.append(f"Recent reconciliation:\n{context['recent_reconciliation']}")
        if context.get("messages"):
            parts.append(f"Notes:\n{context['messages']}")
    else:
        parts.append(f"Financial data:\n{context}")

    if intent in {IntentType.DATASET_REVIEW, IntentType.REPORT_SUMMARY}:
        parts.append(
            "Create an executive dashboard-style summary. Aggregate the records into short sections and prioritize counts, "
            "risk, anomalies, and recommendations over verbose narration. Use all provided records."
        )

    parts.append(
        "Answer using only the supplied context. If a requested detail is not present, say that it is unavailable. "
        "Do not invent invoice, anomaly, payment, or reconciliation details."
    )
    return "\n\n".join(parts)