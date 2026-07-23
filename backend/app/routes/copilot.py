from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from typing import Optional

import time
import json
import logging

logger = logging.getLogger(__name__)

from app.services.conversation import ConversationService
from app.services.database import (
    get_anomaly,
    get_dataset_summary,
    get_duplicate_payments,
    get_high_severity_anomalies,
    get_invoice,
    get_invoice_reconciliation,
    get_invoice_transactions,
    get_missing_payments,
    get_recent_reconciliation,
    get_recommendation_context,
    get_supabase_client,
)
from app.services.financial_rules import build_financial_context
from app.services.llm import AIServiceUnavailableError, build_user_prompt, generate_answer, stream_answer, IntentClassifier
from app.services.llm.prompts import intent_result_from_route
from app.services.llm.routing import IntentType, conversation_memory
from app.services.conversation_state import conversation_state_manager, get_conversation_state
from app.services.analytics import (
    calculate_reconciliation_metrics,
    calculate_anomaly_statistics,
    calculate_payment_statistics,
)
from app.services.llm.manager import get_all_health, MODEL_POOL_LABELS

router = APIRouter()
classifier = IntentClassifier()


def _table(table: str):
    return get_supabase_client().table(table)


class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default"
    conversation_id: Optional[str] = None


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _save_chat_history(conversation_id: Optional[str], user_message: str, ai_response: str) -> None:
    ConversationService.save_message(conversation_id, user_message, ai_response)


def _fast_conversational_response(intent_result):
    response_time = 0.0
    return {
        "question": None,
        "answer": intent_result.fast_response,
        "model": "conversational",
        "tier": 0,
        "fallback_used": False,
        "response_time": response_time,
        "intent": intent_result.intent.value,
        "database_used": False,
        "cache_used": False,
        "pool": "Conversation Pool",
        "provider": "rule-based",
        "time_to_first_token_ms": 0,
    }


def _dataset_review_context(question: str) -> dict:
    summary = get_dataset_summary()
    return {
        "summary": summary["metrics"],
        "invoices": summary["invoices"],
        "transactions": summary["transactions"],
        "anomalies": summary["anomalies"],
        "reconciliations": summary["reconciliations"],
        "analytics": {
            "reconciliation_metrics": calculate_reconciliation_metrics(summary["reconciliations"]),
            "anomaly_statistics": calculate_anomaly_statistics(summary["anomalies"]),
            "payment_statistics": calculate_payment_statistics(summary["invoices"], summary["transactions"]),
        },
        "high_severity_anomalies": get_high_severity_anomalies(limit=5),
        "duplicate_payments": get_duplicate_payments(limit=5),
        "missing_payments": get_missing_payments(limit=5),
        "recent_reconciliation": get_recent_reconciliation(limit=3),
        "messages": [
            "Executive dashboard assembled from invoices, payments, anomalies, and reconciliation records."
        ],
    }


def _build_context(question: str, intent_result, session_id: str = "default") -> tuple[dict | None, bool]:
    intent = intent_result.intent
    entities = intent_result.extracted_entities
    invoice_id = entities.get("invoice_id")
    anomaly_id = entities.get("anomaly_id")

    if intent in {IntentType.GREETING, IntentType.GOODBYE, IntentType.THANKS, IntentType.SMALL_TALK, IntentType.ASSISTANT_IDENTITY, IntentType.ASSISTANT_CAPABILITIES}:
        return None, False

    if intent == IntentType.GENERAL_KNOWLEDGE or intent == IntentType.FINANCIAL_GENERAL:
        return None, False

    if intent in {IntentType.INVOICE_LOOKUP, IntentType.RECONCILIATION_ANALYSIS} and invoice_id:
        base = {
            "invoice": get_invoice(invoice_id),
            "transactions": get_invoice_transactions(invoice_id),
            "reconciliation": get_invoice_reconciliation(invoice_id),
        }
        enriched = build_financial_context(
            invoice=base.get("invoice"),
            transactions=base.get("transactions"),
            reconciliation=base.get("reconciliation"),
        )
        if enriched:
            base.update(enriched)
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            active_entity={"type": "invoice", "id": invoice_id},
            last_analysis_type=intent.value,
            last_tool_used="invoice_lookup",
            last_response_status="completed",
        )
        return base, True

    if intent == IntentType.ANOMALY_LOOKUP and anomaly_id:
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            active_entity={"type": "anomaly", "id": anomaly_id},
            last_analysis_type=intent.value,
            last_tool_used="anomaly_lookup",
            last_response_status="completed",
        )
        return {
            "anomaly": get_anomaly(anomaly_id),
        }, True

    if intent in {IntentType.DATASET_REVIEW, IntentType.REPORT_SUMMARY, IntentType.RECOMMENDATIONS}:
        if intent == IntentType.RECOMMENDATIONS:
            summary = get_dataset_summary()
            context = {
                "summary": summary["metrics"],
                "analytics": {
                    "reconciliation_metrics": calculate_reconciliation_metrics(summary["reconciliations"]),
                    "anomaly_statistics": calculate_anomaly_statistics(summary["anomalies"]),
                    "payment_statistics": calculate_payment_statistics(summary["invoices"], summary["transactions"]),
                },
                "high_severity_anomalies": get_high_severity_anomalies(limit=5),
                "duplicate_payments": get_duplicate_payments(limit=5),
                "missing_payments": get_missing_payments(limit=5),
                "recent_reconciliation": get_recent_reconciliation(limit=3),
                "messages": ["Recommend action based on the retrieved dataset summary."],
            }
            conversation_state_manager.update_state(
                session_id,
                active_intent=intent.value,
                last_analysis_type=intent.value,
                last_tool_used="recommendations",
                last_response_status="completed",
            )
            return context, True
        context = _dataset_review_context(question)
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            last_analysis_type=intent.value,
            last_tool_used="dataset_review",
            last_response_status="completed",
        )
        return context, True

    if intent == IntentType.COMPARISON:
        context = {
            "summary": get_dataset_summary()["metrics"],
            "analytics": {
                "reconciliation_metrics": calculate_reconciliation_metrics(get_dataset_summary()["reconciliations"]),
                "anomaly_statistics": calculate_anomaly_statistics(get_dataset_summary()["anomalies"]),
                "payment_statistics": calculate_payment_statistics(get_dataset_summary()["invoices"], get_dataset_summary()["transactions"]),
            },
            "recent_reconciliation": get_recent_reconciliation(limit=3),
            "high_severity_anomalies": get_high_severity_anomalies(limit=5),
        }
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            last_analysis_type=intent.value,
            last_tool_used="comparison",
            last_response_status="completed",
        )
        return context, True

    if intent == IntentType.TREND_ANALYSIS:
        context = {
            "summary": get_dataset_summary()["metrics"],
            "analytics": {
                "reconciliation_metrics": calculate_reconciliation_metrics(get_dataset_summary()["reconciliations"]),
                "anomaly_statistics": calculate_anomaly_statistics(get_dataset_summary()["anomalies"]),
                "payment_statistics": calculate_payment_statistics(get_dataset_summary()["invoices"], get_dataset_summary()["transactions"]),
            },
            "recent_reconciliation": get_recent_reconciliation(limit=3),
        }
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            last_analysis_type=intent.value,
            last_tool_used="trend_analysis",
            last_response_status="completed",
        )
        return context, True

    if invoice_id:
        base = {
            "invoice": get_invoice(invoice_id),
            "transactions": get_invoice_transactions(invoice_id),
            "reconciliation": get_invoice_reconciliation(invoice_id),
        }
        enriched = build_financial_context(
            invoice=base.get("invoice"),
            transactions=base.get("transactions"),
            reconciliation=base.get("reconciliation"),
        )
        if enriched:
            base.update(enriched)
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            active_entity={"type": "invoice", "id": invoice_id},
            last_analysis_type=intent.value,
            last_tool_used="invoice_lookup",
            last_response_status="completed",
        )
        return base, True

    if anomaly_id:
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            active_entity={"type": "anomaly", "id": anomaly_id},
            last_analysis_type=intent.value,
            last_tool_used="anomaly_lookup",
            last_response_status="completed",
        )
        return {"anomaly": get_anomaly(anomaly_id)}, True

    summary = get_dataset_summary()
    context = {
        "summary": summary["metrics"],
        "analytics": {
            "reconciliation_metrics": calculate_reconciliation_metrics(summary["reconciliations"]),
            "anomaly_statistics": calculate_anomaly_statistics(summary["anomalies"]),
            "payment_statistics": calculate_payment_statistics(summary["invoices"], summary["transactions"]),
        },
        "high_severity_anomalies": get_high_severity_anomalies(limit=5),
        "duplicate_payments": get_duplicate_payments(limit=5),
        "missing_payments": get_missing_payments(limit=5),
        "recent_reconciliation": get_recent_reconciliation(limit=3),
    }
    conversation_state_manager.update_state(
        session_id,
        active_intent=intent.value,
        last_analysis_type=intent.value,
        last_tool_used="financial_analysis",
        last_response_status="completed",
    )
    return context, True


@router.post("/chat")
def chat(request: QuestionRequest):
    print("1 - Request received")
    t0 = time.perf_counter()
    session_id = request.session_id or "default"

    print("2 - Before intent detection")
    state = get_conversation_state(session_id)
    if state.active_intent and state.active_intent != "unknown":
        question_lower = request.question.lower().strip()
        if any(word in question_lower for word in ("continue", "more", "expand", "detail", "explain more", "tell me more")):
            if state.active_entity:
                entities = state.active_entity
                if entities.get("type") == "invoice":
                    question_with_entity = f"{request.question} {entities['id']}"
                    route = classifier.classify(question_with_entity, session_id=session_id)
                elif entities.get("type") == "anomaly":
                    question_with_entity = f"{request.question} {entities['id']}"
                    route = classifier.classify(question_with_entity, session_id=session_id)
                else:
                    route = classifier.classify(request.question, session_id=session_id)
            else:
                route = classifier.classify(request.question, session_id=session_id)
        else:
            route = classifier.classify(request.question, session_id=session_id)
    else:
        route = classifier.classify(request.question, session_id=session_id)

    intent_result = intent_result_from_route(route)
    print("3 - Intent detected:", intent_result.intent.value)
    t_class = time.perf_counter() - t0

    if not intent_result.requires_llm:
        response = _fast_conversational_response(intent_result)
        response["question"] = request.question
        logger.info(
            "Telemetry: intent=%s, database_query=No, rows_returned=0, prompt_size=0, selected_model=conversational, response_time=%.3f, cache_hit=No",
            intent_result.intent.value,
            response["response_time"],
        )
        return response

    t1 = time.perf_counter()
    print("4 - Before context building")
    context, database_used = _build_context(request.question, intent_result, session_id=session_id)
    print("5 - Context built")
    t_db = time.perf_counter() - t1

    t2 = time.perf_counter()
    prompt = build_user_prompt(context=context, question=request.question, intent=intent_result.intent)
    t_prompt = time.perf_counter() - t2

    rows_retrieved = 0
    if isinstance(context, dict):
        for value in context.values():
            if isinstance(value, list):
                rows_retrieved += len(value)
            elif value is not None:
                rows_retrieved += 1

    try:
        print("6 - Before LLM call")
        context_str = json.dumps(context, ensure_ascii=False) if context else ""
        result = generate_answer(
            prompt,
            max_tokens=intent_result.recommended_max_tokens,
            intent=intent_result.intent.value,
            context=context_str,
        )
        print("7 - LLM finished")
    except AIServiceUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable. All models failed.",
        ) from exc

    result = dict(result)
    result["response_time"] += (t_class + t_db + t_prompt)

    estimated_tokens = len(prompt) // 4

    logger.info(
        "Telemetry: intent=%s, database_query=%s, rows_returned=%s, prompt_size=%s, selected_model=%s, finish_reason=%s, max_tokens=%s, prompt_tokens~%s, completion_tokens~%s, total_tokens~%s, response_time=%s, cache_hit=%s",
        intent_result.intent.value,
        "Yes" if database_used else "No",
        rows_retrieved,
        len(prompt),
        result["model"],
        result.get("finish_reason", "unknown"),
        result.get("max_tokens", intent_result.recommended_max_tokens),
        result.get("prompt_token_estimate", 0),
        result.get("completion_token_estimate", 0),
        result.get("total_token_estimate", 0),
        result["response_time"],
        result["cached"],
    )

    response = {
        "question": request.question,
        "answer": result["answer"],
        "model": result["model"],
        "tier": result["tier"],
        "fallback_used": result["fallback_used"],
        "response_time": result["response_time"],
        "intent": intent_result.intent.value,
        "database_used": database_used,
        "cache_used": result["cached"],
        "pool": result.get("pool", "unknown"),
        "provider": result.get("provider", "OpenRouter"),
        "time_to_first_token_ms": 0,  # Non-streaming, no TTFT
    }

    _save_chat_history(
        conversation_id=request.conversation_id,
        user_message=request.question,
        ai_response=result["answer"],
    )

    return response


@router.post("/chat/stream")
def chat_stream(request: QuestionRequest):
    t0 = time.perf_counter()
    session_id = request.session_id or "default"

    state = get_conversation_state(session_id)
    if state.active_intent and state.active_intent != "unknown":
        question_lower = request.question.lower().strip()
        if any(word in question_lower for word in ("continue", "more", "expand", "detail", "explain more", "tell me more")):
            if state.active_entity:
                entities = state.active_entity
                if entities.get("type") == "invoice":
                    question_with_entity = f"{request.question} {entities['id']}"
                    route = classifier.classify(question_with_entity, session_id=session_id)
                elif entities.get("type") == "anomaly":
                    question_with_entity = f"{request.question} {entities['id']}"
                    route = classifier.classify(question_with_entity, session_id=session_id)
                else:
                    route = classifier.classify(request.question, session_id=session_id)
            else:
                route = classifier.classify(request.question, session_id=session_id)
        else:
            route = classifier.classify(request.question, session_id=session_id)
    else:
        route = classifier.classify(request.question, session_id=session_id)

    intent_result = intent_result_from_route(route)
    t_class = time.perf_counter() - t0

    if not intent_result.requires_llm:
        def _conversational():
            yield f"data: {_json({'type': 'token', 'content': intent_result.fast_response})}\n\n"
            yield f"data: {_json({'type': 'metadata', 'model': 'conversational', 'provider': 'OpenRouter', 'time_to_first_token_ms': 0})}\n\n"
            yield f"data: {_json({'type': 'done', 'model': 'conversational', 'provider': 'OpenRouter', 'tier': 0, 'fallback_used': False, 'response_time': round(t_class, 3), 'intent': intent_result.intent.value, 'database_used': False, 'cache_used': False, 'pool': 'Conversation Pool'})}\n\n"
        return StreamingResponse(_conversational(), media_type="text/event-stream")

    t1 = time.perf_counter()
    context, database_used = _build_context(request.question, intent_result, session_id=session_id)
    t_db = time.perf_counter() - t1

    t2 = time.perf_counter()
    prompt = build_user_prompt(context=context, question=request.question, intent=intent_result.intent)
    t_prompt = time.perf_counter() - t2

    rows_retrieved = 0
    if isinstance(context, dict):
        for v in context.values():
            if isinstance(v, list):
                rows_retrieved += len(v)
            elif v:
                rows_retrieved += 1

    overhead_time = t_class + t_db + t_prompt
    estimated_tokens = len(prompt) // 4

    def _event_stream():
        full_answer = ""
        chunk_count = 0
        context_str = json.dumps(context, ensure_ascii=False) if context else ""
        metadata_emitted = False
        done_emitted = False
        try:
            for chunk, meta in stream_answer(
                prompt,
                max_tokens=intent_result.recommended_max_tokens,
                intent=intent_result.intent.value,
                context=context_str,
            ):
                if meta is not None:
                    # Handle dedicated metadata event (type: "metadata")
                    if meta.get("type") == "metadata":
                        logger.info("[SSE] Emitting metadata event: model=%s, ttft=%s", meta.get("model"), meta.get("time_to_first_token_ms"))
                        yield f"data: {_json(meta)}\n\n"
                        continue

                    if meta.get("type") == "warning":
                        logger.info("[SSE DIAGNOSTIC] Emitting warning event: %s", meta.get("message"))
                        yield f"data: {_json(meta)}\n\n"
                        continue

                    metadata_emitted = True
                    meta["response_time"] += overhead_time
                    meta["intent"] = intent_result.intent.value
                    meta["database_used"] = database_used
                    meta["rows_retrieved"] = rows_retrieved
                    meta["prompt_size"] = len(prompt)

                    # Check for error metadata — still emit as done so frontend gets model info
                    if meta.get("error"):
                        logger.info(
                            "[SSE DIAGNOSTIC] Metadata indicates error (no model fallback available). "
                            "error=%s | chunks_streamed=%s | chars_streamed=%s",
                            meta.get("message"), chunk_count, len(full_answer),
                        )
                        yield f"data: {_json({'type': 'done', 'error': True, 'message': meta.get('message', 'Unknown error')})}\n\n"
                        done_emitted = True
                        return

                    logger.info(
                        "=== Stream Request Trace ===\n"
                        "Question: %s\n"
                        "Intent: %s\n"
                        "Need DB: %s\n"
                        "Extracted entities: %s\n"
                        "Rows returned: %s\n"
                        "Prompt size: %s chars (~%s tokens)\n"
                        "Model pool selected: %s\n"
                        "Chosen model: %s\n"
                        "Fallback used: %s\n"
                        "Max tokens: %s\n"
                        "Finish reason: %s\n"
                        "Prompt tokens~: %s\n"
                        "Completion tokens~: %s\n"
                        "Total tokens~: %s\n"
                        "Response time: %ss\n"
                        "Cache hit: %s\n"
                        "Chunks streamed: %s\n"
                        "Chars streamed: %s\n"
                        "=============================",
                        request.question,
                        intent_result.intent.value,
                        database_used,
                        intent_result.extracted_entities,
                        rows_retrieved,
                        len(prompt),
                        estimated_tokens,
                        meta.get("pool", "unknown"),
                        meta.get("model", "unknown"),
                        meta.get("fallback_used", False),
                        meta.get("max_tokens", intent_result.recommended_max_tokens),
                        meta.get("finish_reason", "unknown"),
                        meta.get("prompt_token_estimate", 0),
                        meta.get("completion_token_estimate", 0),
                        meta.get("total_token_estimate", 0),
                        meta.get("response_time", 0),
                        meta.get("cached", False),
                        chunk_count,
                        len(full_answer),
                    )

                    full_answer = meta.get("answer", full_answer)
                    done_emitted = True
                    yield f"data: {_json({'type': 'done', **meta})}\n\n"
                else:
                    full_answer += chunk
                    chunk_count += 1
                    yield f"data: {_json({'type': 'token', 'content': chunk})}\n\n"

            _save_chat_history(
                conversation_id=request.conversation_id,
                user_message=request.question,
                ai_response=full_answer.strip(),
            )
        except AIServiceUnavailableError:
            yield f"data: {_json({'type': 'error', 'message': 'AI service temporarily unavailable. All models failed.'})}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.get("/health/models")
def model_health():
    return {
        "models": get_all_health(),
        "pools": MODEL_POOL_LABELS,
    }


@router.get("/models/health")
def models_health():
    """
    Per-model health summary with latency and success rate.
    Format designed for easy dynamic routing decisions.
    """
    health = get_all_health()
    result = {}
    for name, s in health.items():
        result[name] = {
            "avg_latency": s["avg_latency"],
            "success_rate": s["success_rate"],
            "success_count": s["success_count"],
            "failure_count": s["failure_count"],
            "cooldown_active": s["cooldown_active"],
            "last_updated": s["last_updated"],
        }
    return result
