import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.modules.copilot.services.routing import IntentType, conversation_memory, IntentClassifier
from app.modules.copilot.prompts.copilot_prompts import intent_result_from_route
from app.shared.database.retrieval import retrieve_context
from app.shared.database.supabase_client import get_supabase_client
from app.shared.financial_rules import build_financial_context
from app.shared.llm.prompts import build_system_prompt
from app.modules.copilot.benchmark.benchmark_models import BenchmarkRequest, BenchmarkResponse
from app.modules.copilot.benchmark.benchmark_service import run_model_test, compare_results

router = APIRouter()

classifier = IntentClassifier()


def _table(table: str):
    return get_supabase_client().table(table)


@router.post("/benchmark", response_model=BenchmarkResponse)
def run_benchmark(request: BenchmarkRequest):
    if not request.models:
        raise HTTPException(status_code=400, detail="At least one model must be selected for benchmarking.")

    session_id = "benchmark_session"

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

    context, _ = _build_context(request.question, intent_result, session_id=session_id)

    user_prompt = build_user_prompt(context=context, question=request.question, intent=intent_result.intent)
    context_str = json.dumps(context) if isinstance(context, dict) else (context or "")
    system_prompt = build_system_prompt(context=context_str, intent=intent_name)

    max_tokens = request.max_tokens or 800
    temperature = request.temperature if request.temperature is not None else 0.2

    benchmark_results = []
    for model_name in request.models:
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
            "invoice": _get_invoice(invoice_id),
            "transactions": _get_invoice_transactions(invoice_id),
            "reconciliation": _get_invoice_reconciliation(invoice_id),
        }
        enriched = build_financial_context(
            invoice=base.get("invoice"),
            transactions=base.get("transactions"),
            reconciliation=base.get("reconciliation"),
        )
        if enriched:
            base.update(enriched)
        return base, True

    if intent == IntentType.ANOMALY_LOOKUP and anomaly_id:
        raw = {"anomaly": _get_anomaly(anomaly_id)}
        return raw, True

    if intent in {IntentType.DATASET_REVIEW, IntentType.REPORT_SUMMARY, IntentType.RECOMMENDATIONS}:
        context = retrieve_context(intent.value, question, entities)
        return context, True

    if intent == IntentType.COMPARISON:
        context = retrieve_context(intent.value, question, entities)
        return context, True

    if intent == IntentType.TREND_ANALYSIS:
        context = retrieve_context(intent.value, question, entities)
        return context, True

    if invoice_id:
        base = {
            "invoice": _get_invoice(invoice_id),
            "transactions": _get_invoice_transactions(invoice_id),
            "reconciliation": _get_invoice_reconciliation(invoice_id),
        }
        enriched = build_financial_context(
            invoice=base.get("invoice"),
            transactions=base.get("transactions"),
            reconciliation=base.get("reconciliation"),
        )
        if enriched:
            base.update(enriched)
        return base, True

    if anomaly_id:
        raw = {"anomaly": _get_anomaly(anomaly_id)}
        return raw, True

    context = retrieve_context(intent.value, question, entities)
    return context, True


def _get_invoice(invoice_id: str) -> dict | None:
    try:
        result = _table("invoices").select("*").eq("id", invoice_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def _get_invoice_transactions(invoice_id: str) -> list:
    try:
        result = _table("invoice_transactions").select("*").eq("invoice_id", invoice_id).execute()
        return result.data or []
    except Exception:
        return []


def _get_invoice_reconciliation(invoice_id: str) -> dict | None:
    try:
        result = _table("reconciliations").select("*").eq("invoice_id", invoice_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def _get_anomaly(anomaly_id: str) -> dict | None:
    try:
        result = _table("anomalies").select("*").eq("id", anomaly_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def build_user_prompt(context: dict, question: str, intent: IntentType) -> str:
    if context is None:
        return f"User question:\n\n{question}\n\nNo financial context was retrieved. Answer using your training knowledge."

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

    parts.append("Answer using only the supplied context. If a requested detail is not present, say that it is unavailable. Do not invent invoice, anomaly, payment, or reconciliation details.")
    return "\n\n".join(parts)