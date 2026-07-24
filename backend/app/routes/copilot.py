from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from typing import Dict, Any, Optional

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
from app.services.timing import RequestMetrics
from app.services.benchmark.benchmark_models import BenchmarkRequest, BenchmarkResponse
from app.services.benchmark.benchmark_service import run_model_test, compare_results
from app.services.llm.prompts import build_system_prompt

router = APIRouter()

classifier = IntentClassifier()



# Direct-answer handler: maps keys from DIRECT_ANSWER_PATTERNS in routing.py
# to database queries that return simple counts, skipping the LLM entirely.
_DIRECT_ANSWER_HANDLERS = {
    "count_invoices": lambda: len(get_dataset_summary()["invoices"]),
    "count_transactions": lambda: len(get_dataset_summary()["transactions"]),
    "count_anomalies": lambda: len(get_dataset_summary()["anomalies"]),
    "count_high_severity": lambda: len(get_high_severity_anomalies(limit=10000)),
    "count_duplicate": lambda: len(get_duplicate_payments(limit=10000)),
    "count_missing": lambda: len(get_missing_payments(limit=10000)),
    "count_reconciliations": lambda: len(get_dataset_summary()["reconciliations"]),
}

# Response templates keyed by direct_answer_key
_DIRECT_ANSWER_TEMPLATES = {
    "count_invoices": "There are **{count}** invoices in the system.",
    "count_transactions": "There are **{count}** bank transactions recorded.",
    "count_anomalies": "There are **{count}** anomalies detected.",
    "count_high_severity": "There are **{count}** high-severity anomalies.",
    "count_duplicate": "There are **{count}** duplicate payments identified.",
    "count_missing": "There are **{count}** missing payments to investigate.",
    "count_reconciliations": "There are **{count}** reconciliation records.",
}


def _handle_direct_answer(answer_key: str, metrics: RequestMetrics) -> Optional[Dict[str, Any]]:
    """Execute a direct-answer query and return a response dict, or None if the key is unknown."""
    handler = _DIRECT_ANSWER_HANDLERS.get(answer_key)
    template = _DIRECT_ANSWER_TEMPLATES.get(answer_key)
    if handler is None or template is None:
        return None
    try:
        count = handler()
        answer = template.format(count=count)
        metrics.rows_retrieved = 1
        return {
            "answer": answer,
            "model": "direct-query",
            "tier": 0,
            "fallback_used": False,
            "response_time": 0.0,
            "cached": False,
            "pool": "Direct Query Pool",
            "provider": "database",
            "finish_reason": "stop",
            "prompt_token_estimate": 0,
            "completion_token_estimate": 0,
            "total_token_estimate": 0,
            "max_tokens": 0,
        }
    except Exception as e:
        logger.error("Direct answer handler '%s' failed: %s", answer_key, e)
        return None


def _table(table: str):
    return get_supabase_client().table(table)


class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default"
    conversation_id: Optional[str] = None
    model: Optional[str] = None


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
    metrics = RequestMetrics.new()
    session_id = request.session_id or "default"

    metrics.begin_stage("Intent Classification")
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
    metrics.intent = intent_result.intent.value
    metrics.end_stage()

    if not intent_result.requires_llm:
        # Check for direct-answer (SQL-only) queries first
        if intent_result.direct_answer_key:
            metrics.begin_stage("Direct Query")
            direct_result = _handle_direct_answer(intent_result.direct_answer_key, metrics)
            metrics.end_stage()
            if direct_result is not None:
                metrics.model = "direct-query"
                metrics.provider = "database"
                metrics.pool = "Direct Query Pool"
                metrics.log_summary()
                return {
                    "question": request.question,
                    "answer": direct_result["answer"],
                    "model": "direct-query",
                    "tier": 0,
                    "fallback_used": False,
                    "response_time": round(metrics.elapsed_since_start(), 3),
                    "intent": intent_result.intent.value,
                    "database_used": True,
                    "cache_used": False,
                    "pool": "Direct Query Pool",
                    "provider": "database",
                    "time_to_first_token_ms": 0,
                    "request_id": metrics.request_id,
                }

        response = _fast_conversational_response(intent_result)
        response["question"] = request.question
        response["request_id"] = metrics.request_id
        metrics.log_summary()
        return response

    metrics.begin_stage("Context Retrieval")
    context, database_used = _build_context(request.question, intent_result, session_id=session_id)
    metrics.database_used = database_used
    metrics.end_stage()

    metrics.begin_stage("Prompt Construction")
    prompt = build_user_prompt(context=context, question=request.question, intent=intent_result.intent)
    metrics.prompt_size_chars = len(prompt)
    metrics.end_stage()

    rows_retrieved = 0
    if isinstance(context, dict):
        for value in context.values():
            if isinstance(value, list):
                rows_retrieved += len(value)
            elif value is not None:
                rows_retrieved += 1
    metrics.rows_retrieved = rows_retrieved

    try:
        metrics.begin_stage("LLM Generation")
        context_str = json.dumps(context, ensure_ascii=False) if context else ""
        result = generate_answer(
            prompt,
            max_tokens=intent_result.recommended_max_tokens,
            intent=intent_result.intent.value,
            context=context_str,
        )
        metrics.end_stage()
    except AIServiceUnavailableError as exc:
        metrics.error = "All models failed"
        metrics.end_stage()
        metrics.log_summary()
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable. All models failed.",
        ) from exc

    result = dict(result)
    metrics.model = result["model"]
    metrics.provider = result.get("provider", "OpenRouter")
    metrics.pool = result.get("pool", "unknown")
    metrics.finish_reason = result.get("finish_reason", "stop")
    metrics.cache_hit = result.get("cached", False)
    metrics.fallback_used = result.get("fallback_used", False)
    metrics.prompt_tokens = result.get("prompt_token_estimate", 0)
    metrics.completion_tokens = result.get("completion_token_estimate", 0)
    metrics.total_tokens = result.get("total_token_estimate", 0)
    metrics.max_tokens = result.get("max_tokens", intent_result.recommended_max_tokens)

    metrics.log_summary()

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
        "time_to_first_token_ms": 0,
        "request_id": metrics.request_id,
    }

    _save_chat_history(
        conversation_id=request.conversation_id,
        user_message=request.question,
        ai_response=result["answer"],
    )

    return response


@router.post("/chat/stream")
def chat_stream(request: QuestionRequest):
    metrics = RequestMetrics.new()
    session_id = request.session_id or "default"

    metrics.begin_stage("Intent Classification")
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
    metrics.intent = intent_result.intent.value
    metrics.end_stage()

    if not intent_result.requires_llm:
        # Check for direct-answer (SQL-only) queries first
        if intent_result.direct_answer_key:
            metrics.begin_stage("Direct Query")
            direct_result = _handle_direct_answer(intent_result.direct_answer_key, metrics)
            metrics.end_stage()
            if direct_result is not None:
                metrics.model = "direct-query"
                metrics.provider = "database"
                metrics.pool = "Direct Query Pool"
                metrics.log_summary()
                def _direct_answer_stream():
                    yield f"data: {_json({'type': 'token', 'content': direct_result['answer']})}\n\n"
                    yield f"data: {_json({'type': 'done', 'model': 'direct-query', 'provider': 'database', 'tier': 0, 'fallback_used': False, 'response_time': round(metrics.elapsed_since_start(), 3), 'intent': intent_result.intent.value, 'database_used': True, 'cache_used': False, 'pool': 'Direct Query Pool', 'request_id': metrics.request_id})}\n\n"
                return StreamingResponse(_direct_answer_stream(), media_type="text/event-stream")

        def _conversational():
            yield f"data: {_json({'type': 'token', 'content': intent_result.fast_response})}\n\n"
            yield f"data: {_json({'type': 'metadata', 'model': 'conversational', 'provider': 'OpenRouter', 'time_to_first_token_ms': 0})}\n\n"
            yield f"data: {_json({'type': 'done', 'model': 'conversational', 'provider': 'OpenRouter', 'tier': 0, 'fallback_used': False, 'response_time': round(metrics.elapsed_since_start(), 3), 'intent': intent_result.intent.value, 'database_used': False, 'cache_used': False, 'pool': 'Conversation Pool', 'request_id': metrics.request_id})}\n\n"
        return StreamingResponse(_conversational(), media_type="text/event-stream")

    # Intent-aware SSE status messages for immediate user feedback
    _STATUS_MESSAGES = {
        "invoice_lookup": [
            "Searching invoice records...",
            "Checking reconciliation...",
            "Preparing invoice analysis...",
        ],
        "anomaly_lookup": [
            "Finding anomaly records...",
            "Analyzing financial impact...",
            "Generating recommendations...",
        ],
        "dataset_review": [
            "Loading dataset summary...",
            "Computing statistics...",
            "Preparing overview...",
        ],
        "reconciliation_analysis": [
            "Checking reconciliation data...",
            "Comparing ERP vs bank records...",
            "Analyzing matches and mismatches...",
        ],
        "recommendations": [
            "Gathering financial data...",
            "Analyzing patterns...",
            "Formulating recommendations...",
        ],
        "report_summary": [
            "Loading report data...",
            "Aggregating metrics...",
            "Preparing summary...",
        ],
        "comparison": [
            "Loading data for comparison...",
            "Analyzing differences...",
            "Preparing comparison...",
        ],
        "trend_analysis": [
            "Loading historical data...",
            "Analyzing trends...",
            "Preparing trend analysis...",
        ],
        "financial_analysis": [
            "Analyzing your financial data...",
            "Processing context...",
            "Generating analysis...",
        ],
        "general_knowledge": [
            "Looking up accounting concepts...",
            "Preparing explanation...",
        ],
        "financial_general": [
            "Looking up financial concepts...",
            "Preparing explanation...",
        ],
    }

    intent_name = intent_result.intent.value
    status_messages = _STATUS_MESSAGES.get(intent_name, [
        "Analyzing your question...",
        "Searching financial records...",
        "Generating analysis...",
    ])

    metrics.begin_stage("Context Retrieval")
    context, database_used = _build_context(request.question, intent_result, session_id=session_id)
    metrics.database_used = database_used
    metrics.end_stage()

    metrics.begin_stage("Prompt Construction")
    prompt = build_user_prompt(context=context, question=request.question, intent=intent_result.intent)
    metrics.prompt_size_chars = len(prompt)
    metrics.end_stage()

    rows_retrieved = 0
    if isinstance(context, dict):
        for v in context.values():
            if isinstance(v, list):
                rows_retrieved += len(v)
            elif v:
                rows_retrieved += 1
    metrics.rows_retrieved = rows_retrieved

    overhead_time = metrics.get_stage_ms("Intent Classification") + metrics.get_stage_ms("Context Retrieval") + metrics.get_stage_ms("Prompt Construction")
    estimated_tokens = len(prompt) // 4

    def _event_stream(metrics=metrics, overhead_time=overhead_time, status_messages=status_messages):
        full_answer = ""
        chunk_count = 0
        context_str = json.dumps(context, ensure_ascii=False) if context else ""
        metadata_emitted = False
        done_emitted = False
        cancelled = False

        # Emit immediate SSE status events so the user sees progress before LLM starts
        for msg in status_messages:
            yield f"data: {_json({'type': 'status', 'message': msg})}\n\n"

        try:
            for chunk, meta in stream_answer(
                prompt,
                max_tokens=intent_result.recommended_max_tokens,
                intent=intent_result.intent.value,
                context=context_str,
                model_override=request.model,
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
                    meta["request_id"] = metrics.request_id

                    # Populate metrics from final metadata
                    metrics.model = meta.get("model", "")
                    metrics.provider = meta.get("provider", "OpenRouter")
                    metrics.pool = meta.get("pool", "")
                    metrics.finish_reason = meta.get("finish_reason", "")
                    metrics.cache_hit = meta.get("cached", False)
                    metrics.fallback_used = meta.get("fallback_used", False)
                    metrics.prompt_tokens = meta.get("prompt_token_estimate", 0)
                    metrics.completion_tokens = meta.get("completion_token_estimate", 0)
                    metrics.total_tokens = meta.get("total_token_estimate", 0)
                    metrics.max_tokens = meta.get("max_tokens", 0)

                    # Check for error metadata — still emit as done so frontend gets model info
                    if meta.get("error"):
                        metrics.error = meta.get("message", "Unknown error")
                        metrics.log_summary()
                        logger.info(
                            "[SSE DIAGNOSTIC] Metadata indicates error (no model fallback available). "
                            "error=%s | chunks_streamed=%s | chars_streamed=%s",
                            meta.get("message"), chunk_count, len(full_answer),
                        )
                        yield f"data: {_json({'type': 'done', 'error': True, 'message': meta.get('message', 'Unknown error'), 'request_id': metrics.request_id})}\n\n"
                        done_emitted = True
                        return

                    metrics.log_summary()

                    full_answer = meta.get("answer", full_answer)
                    done_emitted = True
                    yield f"data: {_json({'type': 'done', **meta})}\n\n"
                else:
                    full_answer += chunk
                    chunk_count += 1
                    yield f"data: {_json({'type': 'token', 'content': chunk})}\n\n"

            # If cancelled, emit cancelled event instead of saving history
            if cancelled:
                yield f"data: {_json({'type': 'cancelled', 'message': 'Generation stopped by user', 'request_id': metrics.request_id})}\n\n"
                return

            _save_chat_history(
                conversation_id=request.conversation_id,
                user_message=request.question,
                ai_response=full_answer.strip(),
            )
        except AIServiceUnavailableError:
            metrics.error = "All models failed"
            metrics.log_summary()
            yield f"data: {_json({'type': 'error', 'message': 'AI service temporarily unavailable. All models failed.', 'request_id': metrics.request_id})}\n\n"

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


@router.post("/benchmark", response_model=BenchmarkResponse)
def run_benchmark(request: BenchmarkRequest):
    """
    Executes a benchmark comparison across specified LLM models.
    Isolation Guarantee:
    - Bypasses model fallback logic.
    - Tests each requested model individually.
    - Measures exact response time, TTFT, token metrics, and tokens/sec.
    """
    if not request.models:
        raise HTTPException(status_code=400, detail="At least one model must be selected for benchmarking.")

    session_id = "benchmark_session"

    # Intent Classification or override
    if request.intent:
        intent_enum = IntentType.from_str(request.intent) if hasattr(IntentType, 'from_str') else None
        if not intent_enum:
            route = classifier.classify(request.question, session_id=session_id)
            intent_result = intent_result_from_route(route)
        else:
            route = classifier.classify(request.question, session_id=session_id)
            intent_result = intent_result_from_route(route)
            intent_result.intent = intent_enum
    else:
        route = classifier.classify(request.question, session_id=session_id)
        intent_result = intent_result_from_route(route)

    intent_name = intent_result.intent.value if hasattr(intent_result.intent, 'value') else str(intent_result.intent)

    # Financial Context Retrieval
    context, _ = _build_context(request.question, intent_result, session_id=session_id)

    # Prompt Construction
    user_prompt = build_user_prompt(context=context, question=request.question, intent=intent_result.intent)
    context_str = json.dumps(context, ensure_ascii=False) if context else ""
    system_prompt = build_system_prompt(context_str, intent=intent_name)

    max_tokens = request.max_tokens or 800
    temperature = request.temperature if request.temperature is not None else 0.2

    benchmark_results = []
    for model_name in request.models:
        logger.info(f"[Benchmark] Testing model: {model_name}...")
        res = run_model_test(
            model_name=model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        benchmark_results.append(res)

    rankings = compare_results(benchmark_results)

    return BenchmarkResponse(
        question=request.question,
        intent=intent_name,
        results=benchmark_results,
        rankings=rankings,
    )

