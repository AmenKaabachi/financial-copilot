from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from typing import Dict, Any, Optional

import time
import json
import logging

logger = logging.getLogger(__name__)

from app.modules.copilot.services.conversation import ConversationService
from app.shared.database.retrieval import (
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
    retrieve_context,
)
from app.shared.database.supabase_client import get_supabase_client
from app.shared.financial_rules import build_financial_context
from app.modules.copilot.services.context_formatter import format_financial_context, estimate_context_tokens
from app.shared.llm import AIServiceUnavailableError, generate_answer, stream_answer
from app.shared.llm.manager import get_all_health, MODEL_POOL_LABELS
from app.shared.llm.prompts import build_system_prompt
from app.modules.copilot.prompts.copilot_prompts import intent_result_from_route, build_user_prompt
from app.modules.copilot.services.routing import IntentType, conversation_memory, IntentClassifier
from app.modules.copilot.services.conversation_state import conversation_state_manager, get_conversation_state
from app.modules.copilot.services.continuation_state import (
    continuation_state_manager,
    get_continuation_state,
    is_continue_request,
    FinishReason,
)
from app.shared.analytics import (
    calculate_reconciliation_metrics,
    calculate_anomaly_statistics,
    calculate_payment_statistics,
)
from app.shared.timing import RequestMetrics

router = APIRouter()

classifier = IntentClassifier()


_DIRECT_ANSWER_HANDLERS = {
    "count_invoices": lambda: retrieve_context("financial_analysis", "", {}).get("summary", {}).get("invoice_count", 0),
    "count_transactions": lambda: retrieve_context("financial_analysis", "", {}).get("summary", {}).get("payment_count", 0),
    "count_anomalies": lambda: retrieve_context("financial_analysis", "", {}).get("summary", {}).get("anomaly_count", 0),
    "count_high_severity": lambda: len(get_high_severity_anomalies(limit=10000)),
    "count_duplicate": lambda: len(get_duplicate_payments(limit=10000)),
    "count_missing": lambda: len(get_missing_payments(limit=10000)),
    "count_reconciliations": lambda: retrieve_context("financial_analysis", "", {}).get("summary", {}).get("reconciliation_count", 0),
}

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
    max_tokens: Optional[int] = None


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


def _dataset_review_context(question: str, entities: dict = None) -> dict:
    if entities is None:
        entities = {}
    context = retrieve_context("dataset_review", question, entities)
    if "sample_invoices" in context and "sample_transactions" in context:
        context["analytics"] = {
            "reconciliation_metrics": calculate_reconciliation_metrics(context.get("sample_invoices", [])),
            "anomaly_statistics": calculate_anomaly_statistics(context.get("high_severity_anomalies", [])),
            "payment_statistics": calculate_payment_statistics(
                context.get("sample_invoices", []),
                context.get("sample_transactions", [])
            ),
        }
    context["messages"] = [
        "Executive dashboard assembled from aggregated metrics and sample data."
    ]
    return context


def _is_broad_query(question: str) -> bool:
    import re
    if re.search(r'\b(INV\d{4,8}|TX\d{4,8}|ANM\d{4,8})\b', question, re.IGNORECASE):
        return False
    broad_indicators = [
        r'\bwhy\s+is\b',
        r'\bexplain\b',
        r'\bgive\s+me\s+an\s+overview\b',
        r'\bsummarize\b',
        r'\bwhat\s+anomal',
        r'\breview\b',
        r'\banalyze\b',
        r'\bhow\s+many\b',
        r'\btell\s+me\s+about\b',
    ]
    for pattern in broad_indicators:
        if re.search(pattern, question, re.IGNORECASE):
            return True
    return False


def _build_context(question: str, intent_result, session_id: str = "default") -> tuple[dict | None, bool]:
    intent = intent_result.intent
    entities = intent_result.extracted_entities
    invoice_id = entities.get("invoice_id")
    anomaly_id = entities.get("anomaly_id")
    is_broad = _is_broad_query(question)

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
        base = format_financial_context(base, intent=intent.value, is_broad_query=is_broad)
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
        raw = {"anomaly": get_anomaly(anomaly_id)}
        return format_financial_context(raw, intent=intent.value, is_broad_query=is_broad), True

    if intent in {IntentType.DATASET_REVIEW, IntentType.REPORT_SUMMARY, IntentType.RECOMMENDATIONS}:
        context = retrieve_context(intent.value, question, entities)
        if "sample_invoices" in context and "sample_transactions" in context:
            context["analytics"] = {
                "reconciliation_metrics": calculate_reconciliation_metrics(context.get("sample_invoices", [])),
                "anomaly_statistics": calculate_anomaly_statistics(context.get("high_severity_anomalies", [])),
                "payment_statistics": calculate_payment_statistics(
                    context.get("sample_invoices", []),
                    context.get("sample_transactions", [])
                ),
            }
        context["messages"] = ["Recommend action based on the retrieved dataset summary."]
        context = format_financial_context(context, intent=intent.value, is_broad_query=is_broad)
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            last_analysis_type=intent.value,
            last_tool_used="dataset_review",
            last_response_status="completed",
        )
        return context, True

    if intent == IntentType.COMPARISON:
        context = retrieve_context(intent.value, question, entities)
        if "sample_invoices" in context and "sample_transactions" in context:
            context["analytics"] = {
                "reconciliation_metrics": calculate_reconciliation_metrics(context.get("sample_invoices", [])),
                "anomaly_statistics": calculate_anomaly_statistics(context.get("high_severity_anomalies", [])),
                "payment_statistics": calculate_payment_statistics(
                    context.get("sample_invoices", []),
                    context.get("sample_transactions", [])
                ),
            }
        context = format_financial_context(context, intent=intent.value, is_broad_query=is_broad)
        conversation_state_manager.update_state(
            session_id,
            active_intent=intent.value,
            last_analysis_type=intent.value,
            last_tool_used="comparison",
            last_response_status="completed",
        )
        return context, True

    if intent == IntentType.TREND_ANALYSIS:
        context = retrieve_context(intent.value, question, entities)
        if "sample_invoices" in context and "sample_transactions" in context:
            context["analytics"] = {
                "reconciliation_metrics": calculate_reconciliation_metrics(context.get("sample_invoices", [])),
                "anomaly_statistics": calculate_anomaly_statistics(context.get("high_severity_anomalies", [])),
                "payment_statistics": calculate_payment_statistics(
                    context.get("sample_invoices", []),
                    context.get("sample_transactions", [])
                ),
            }
        context = format_financial_context(context, intent=intent.value, is_broad_query=is_broad)
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
        base = format_financial_context(base, intent=intent.value, is_broad_query=is_broad)
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
        raw = {"anomaly": get_anomaly(anomaly_id)}
        return format_financial_context(raw, intent=intent.value, is_broad_query=is_broad), True

    context = retrieve_context(intent.value, question, entities)
    if "sample_invoices" in context and "sample_transactions" in context:
        context["analytics"] = {
            "reconciliation_metrics": calculate_reconciliation_metrics(context.get("sample_invoices", [])),
            "anomaly_statistics": calculate_anomaly_statistics(context.get("high_severity_anomalies", [])),
            "payment_statistics": calculate_payment_statistics(
                context.get("sample_invoices", []),
                context.get("sample_transactions", [])
            ),
        }
    context = format_financial_context(context, intent=intent.value, is_broad_query=is_broad)
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

    t_retrieval_start = time.perf_counter()

    metrics.begin_stage("Context Retrieval")
    context, database_used = _build_context(request.question, intent_result, session_id=session_id)
    metrics.database_used = database_used
    metrics.end_stage()
    retrieval_ms = round((time.perf_counter() - t_retrieval_start) * 1000)

    t_prompt_start = time.perf_counter()
    metrics.begin_stage("Prompt Construction")
    prompt = build_user_prompt(context=context, question=request.question, intent=intent_result.intent)
    metrics.prompt_size_chars = len(prompt)
    metrics.end_stage()
    prompt_build_ms = round((time.perf_counter() - t_prompt_start) * 1000)

    rows_retrieved = 0
    if isinstance(context, dict):
        for value in context.values():
            if isinstance(value, list):
                rows_retrieved += len(value)
            elif value is not None:
                rows_retrieved += 1
    metrics.rows_retrieved = rows_retrieved

    context_tokens_est = estimate_context_tokens(context) if context else 0
    logger.warning(
        "[LATENCY BREAKDOWN] retrieval=%sms | prompt_build=%sms | context_tokens_est=%s | rows_retrieved=%s",
        retrieval_ms, prompt_build_ms, context_tokens_est, rows_retrieved,
    )

    try:
        t_llm_start = time.perf_counter()
        metrics.begin_stage("LLM Generation")
        context_str = json.dumps(context, ensure_ascii=False) if context else ""
        result = generate_answer(
            prompt,
            max_tokens=intent_result.recommended_max_tokens,
            intent=intent_result.intent.value,
            context=context_str,
        )
        metrics.end_stage()
        llm_total_ms = round((time.perf_counter() - t_llm_start) * 1000)
        total_ms = round((time.perf_counter() - t_retrieval_start) * 1000)
        logger.warning(
            "[LATENCY BREAKDOWN] llm_generation=%sms | total=%sms | model=%s | finish_reason=%s",
            llm_total_ms, total_ms, result.get("model", "unknown"), result.get("finish_reason", "unknown"),
        )
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
    t_request_start = time.perf_counter()
    session_id = request.session_id or "default"

    metrics.begin_stage("Intent Classification")

    continuation_state = get_continuation_state(session_id)
    is_continuation = is_continue_request(request.question)

    if is_continuation and continuation_state and continuation_state.can_continue():
        logger.info(
            "[Continuation] Detected continue request for session %s (original_prompt=%s, accumulated_length=%s)",
            session_id, continuation_state.original_user_prompt[:50], len(continuation_state.accumulated_text),
        )
        route = classifier.classify(continuation_state.original_user_prompt, session_id=session_id)
    else:
        if continuation_state:
            continuation_state_manager.clear_state(session_id)

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

    effective_max_tokens = request.max_tokens or intent_result.recommended_max_tokens

    if is_continuation and continuation_state and continuation_state.can_continue():
        context_str = continuation_state.context
        context = json.loads(context_str) if context_str else None
        database_used = True
        prompt = continuation_state.final_prompt_sent
        if request.max_tokens is None and continuation_state.max_tokens:
            effective_max_tokens = continuation_state.max_tokens
        retrieval_ms = 0
        prompt_build_ms = 0
        overhead_time = 0
        rows_retrieved = 0
        logger.info(
            "[Continuation] Using stored context for session %s (context_length=%s, prompt_length=%s)",
            session_id, len(context_str) if context_str else 0, len(prompt),
        )
    else:
        t_retrieval_start = time.perf_counter()

        metrics.begin_stage("Context Retrieval")
        context, database_used = _build_context(request.question, intent_result, session_id=session_id)
        metrics.database_used = database_used
        metrics.end_stage()
        retrieval_ms = round((time.perf_counter() - t_retrieval_start) * 1000)

        t_prompt_start = time.perf_counter()
        metrics.begin_stage("Prompt Construction")
        prompt = build_user_prompt(context=context, question=request.question, intent=intent_result.intent)
        metrics.prompt_size_chars = len(prompt)
        metrics.end_stage()
        prompt_build_ms = round((time.perf_counter() - t_prompt_start) * 1000)

        context_str = json.dumps(context, ensure_ascii=False) if context else ""

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

        context_tokens_est = estimate_context_tokens(context) if context else 0
        logger.warning(
            "[LATENCY BREAKDOWN] retrieval=%sms | prompt_build=%sms | context_tokens_est=%s | rows_retrieved=%s",
            retrieval_ms, prompt_build_ms, context_tokens_est, rows_retrieved,
        )

    def _event_stream():
        nonlocal overhead_time, retrieval_ms, prompt_build_ms
        nonlocal context_str, context, database_used, prompt
        nonlocal status_messages, is_continuation, continuation_state
        nonlocal metrics, session_id, request, intent_result
        nonlocal rows_retrieved

        full_answer = ""
        chunk_count = 0
        metadata_emitted = False
        done_emitted = False
        cancelled = False
        llm_first_token_ms = 0

        if not (is_continuation and continuation_state and continuation_state.can_continue()):
            continuation_state_manager.start_generation(
                session_id=session_id,
                conversation_id=request.conversation_id,
                original_user_prompt=request.question,
                final_prompt_sent=prompt,
                conversation_history=[],
                request_id=metrics.request_id,
                intent=intent_result.intent.value,
                context=context_str,
                max_tokens=effective_max_tokens,
            )

        for msg in status_messages:
            yield f"data: {_json({'type': 'status', 'message': msg})}\n\n"

        t_llm_start = time.perf_counter()

        try:
            if is_continuation and continuation_state and continuation_state.can_continue():
                full_answer = continuation_state.accumulated_text
                yield f"data: {_json({'type': 'token', 'content': full_answer})}\n\n"
                logger.info(
                    "[Continuation] Prepending accumulated text (%s chars) for session %s",
                    len(full_answer), session_id,
                )

            for chunk, meta in stream_answer(
                prompt,
                max_tokens=effective_max_tokens,
                intent=intent_result.intent.value,
                context=context_str,
                model_override=request.model,
                previous_answer=full_answer if is_continuation and continuation_state else None,
            ):
                if chunk and llm_first_token_ms == 0:
                    llm_first_token_ms = round((time.perf_counter() - t_llm_start) * 1000)
                    total_ms = round((time.perf_counter() - t_request_start) * 1000)
                    logger.warning(
                        "[LATENCY BREAKDOWN] retrieval=%sms | prompt_build=%sms | llm_first_token=%sms | total=%sms",
                        retrieval_ms, prompt_build_ms, llm_first_token_ms, total_ms,
                    )

                if meta is not None:
                    if meta.get("type") == "metadata":
                        logger.info("[SSE] Emitting metadata event: model=%s, ttft=%s", meta.get("model"), meta.get("time_to_first_token_ms"))
                        continuation_state_manager.update_model(session_id, meta.get("model", ""))
                        yield f"data: {_json(meta)}\n\n"
                        continue

                    if meta.get("type") == "warning":
                        logger.info("[SSE DIAGNOSTIC] Emitting warning event: %s", meta.get("message"))
                        yield f"data: {_json(meta)}\n\n"
                        continue

                    metadata_emitted = True
                    meta["response_time"] = meta.get("response_time", 0) + overhead_time / 1000
                    meta["intent"] = intent_result.intent.value
                    meta["database_used"] = database_used
                    meta["rows_retrieved"] = rows_retrieved
                    meta["prompt_size"] = len(prompt)
                    meta["request_id"] = metrics.request_id
                    meta["retrieval_ms"] = retrieval_ms
                    meta["prompt_build_ms"] = prompt_build_ms
                    meta["llm_first_token_ms"] = llm_first_token_ms
                    meta["fallback_count"] = meta.get("attempts", 1) - 1
                    meta["total_ms"] = round(metrics.elapsed_since_start() * 1000)

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

                    if meta.get("error"):
                        metrics.error = meta.get("message", "Unknown error")
                        metrics.log_summary()
                        logger.info(
                            "[SSE DIAGNOSTIC] Metadata indicates error (no model fallback available). "
                            "error=%s | chunks_streamed=%s | chars_streamed=%s",
                            meta.get("message"), chunk_count, len(full_answer),
                        )
                        continuation_state_manager.mark_interrupted(session_id, FinishReason.PROVIDER_ERROR)
                        yield f"data: {_json({'type': 'done', 'error': True, 'message': meta.get('message', 'Unknown error'), 'request_id': metrics.request_id})}\n\n"
                        done_emitted = True
                        return

                    metrics.log_summary()

                    full_answer = meta.get("answer", full_answer)
                    done_emitted = True

                    finish_reason_str = meta.get("finish_reason", "stop")
                    if finish_reason_str == "length":
                        continuation_state_manager.mark_interrupted(session_id, FinishReason.MAX_TOKENS)
                        meta["interrupted"] = True
                    elif finish_reason_str == "stop":
                        continuation_state_manager.mark_completed(session_id, FinishReason.COMPLETED)
                    else:
                        continuation_state_manager.mark_completed(session_id, FinishReason(finish_reason_str))

                    yield f"data: {_json({'type': 'done', **meta})}\n\n"
                else:
                    if is_continuation and continuation_state and continuation_state.can_continue() and chunk:
                        from app.shared.llm.manager import _merge_with_overlap_detection
                        merged = _merge_with_overlap_detection(full_answer, chunk)
                        if merged != full_answer + chunk:
                            new_part = merged[len(full_answer):]
                            if new_part:
                                chunk = new_part
                                logger.info("[Continuation] Removed duplicate text (%s chars -> %s chars)", len(chunk), len(new_part))

                    full_answer += chunk
                    chunk_count += 1
                    continuation_state_manager.update_accumulated_text(session_id, full_answer)
                    yield f"data: {_json({'type': 'token', 'content': chunk})}\n\n"

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


@router.post("/continuation/clear")
def clear_continuation_state(request: QuestionRequest):
    session_id = request.session_id or "default"
    continuation_state_manager.clear_state(session_id)
    logger.info("[Continuation] Cleared state for session %s", session_id)
    return {"status": "cleared", "session_id": session_id}


@router.post("/chat/continuation/clear")
def clear_continuation_state_alt(
    session_id: Optional[str] = None,
):
    sid = session_id or "default"
    continuation_state_manager.clear_state(sid)
    logger.info("[Continuation] Cleared state for session %s (via /chat/continuation/clear)", sid)
    return {"status": "cleared", "session_id": sid}