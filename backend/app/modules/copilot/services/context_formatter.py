"""Context formatting and trimming for LLM-ready financial context.

This module sits between database retrieval and prompt construction.
It trims verbose database records to essential fields, reducing token
usage while preserving the information needed for LLM reasoning.

Architecture:
  database.py  →  context_formatter.py  →  prompts.py
  (raw records)    (trimmed context)       (LLM-ready)
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Target token budgets per query type ──
# Broad/general questions: ~1500 tokens (summary, not full records)
# Specific/investigation questions: ~3000 tokens (need detail for analysis)
# Dataset review: ~4000 tokens (aggregated metrics)
BROAD_QUERY_MAX_TOKENS = 1500
SPECIFIC_QUERY_MAX_TOKENS = 3000
DATASET_REVIEW_MAX_TOKENS = 4000

# ── Key fields for each record type ──
# Only these fields are retained when trimming context.
# This eliminates verbose/irrelevant fields like timestamps, metadata, etc.
INVOICE_KEY_FIELDS = [
    "invoice_id",
    "amount",
    "due_date",
    "payment_status",
    "vendor_name",
    "description",
    "issue",
    "severity",
]

TRANSACTION_KEY_FIELDS = [
    "transaction_id",
    "amount",
    "transaction_date",
    "type",
    "status",
    "description",
]

ANOMALY_KEY_FIELDS = [
    "anomaly_id",
    "invoice_id",
    "anomaly_type",
    "severity",
    "status",
    "amount",
    "description",
    "detected_date",
]

RECONCILIATION_KEY_FIELDS = [
    "reconciliation_id",
    "invoice_id",
    "erp_amount",
    "bank_amount",
    "difference",
    "status",
    "match_status",
]


def _trim_record(record: Dict[str, Any], key_fields: list) -> Dict[str, Any]:
    """Trim a single record to only the key fields that exist."""
    if not record or not isinstance(record, dict):
        return record
    trimmed = {}
    for field in key_fields:
        if field in record and record[field] is not None:
            trimmed[field] = record[field]
    return trimmed


def _trim_invoice(invoice: Any) -> Any:
    """Trim a single invoice record or list of invoices."""
    if isinstance(invoice, list):
        return [_trim_record(inv, INVOICE_KEY_FIELDS) for inv in invoice if inv]
    if isinstance(invoice, dict):
        return _trim_record(invoice, INVOICE_KEY_FIELDS)
    return invoice


def _trim_transactions(transactions: Any) -> Any:
    """Trim transaction records."""
    if isinstance(transactions, list):
        return [_trim_record(tx, TRANSACTION_KEY_FIELDS) for tx in transactions if tx]
    if isinstance(transactions, dict):
        return _trim_record(transactions, TRANSACTION_KEY_FIELDS)
    return transactions


def _trim_anomalies(anomalies: Any) -> Any:
    """Trim anomaly records."""
    if isinstance(anomalies, list):
        return [_trim_record(anom, ANOMALY_KEY_FIELDS) for anom in anomalies if anom]
    if isinstance(anomalies, dict):
        return _trim_record(anomalies, ANOMALY_KEY_FIELDS)
    return anomalies


def _trim_reconciliations(reconciliations: Any) -> Any:
    """Trim reconciliation records."""
    if isinstance(reconciliations, list):
        return [_trim_record(rec, RECONCILIATION_KEY_FIELDS) for rec in reconciliations if rec]
    if isinstance(reconciliations, dict):
        return _trim_record(reconciliations, RECONCILIATION_KEY_FIELDS)
    return reconciliations


def format_financial_context(context: Dict[str, Any], intent: str = "unknown", is_broad_query: bool = False) -> Dict[str, Any]:
    """
    Format raw financial context into LLM-ready context with trimmed records.

    This is the main entry point for context formatting.

    Args:
        context: Raw context dict from database.py retrieve_context()
        intent: Intent string for token budget decisions
        is_broad_query: If True, apply more aggressive trimming for summary questions

    Returns:
        Formatted context dict with trimmed records and token budget info
    """
    if not context:
        return {}

    formatted = {}

    # Trim invoices
    if "invoice" in context:
        formatted["invoice"] = _trim_invoice(context["invoice"])
    if "sample_invoices" in context:
        formatted["sample_invoices"] = _trim_invoice(context["sample_invoices"])

    # Trim transactions
    if "transactions" in context:
        formatted["transactions"] = _trim_transactions(context["transactions"])
    if "sample_transactions" in context:
        formatted["sample_transactions"] = _trim_transactions(context["sample_transactions"])

    # Trim anomalies
    if "anomaly" in context:
        formatted["anomaly"] = _trim_anomalies(context["anomaly"])
    if "high_severity_anomalies" in context:
        formatted["high_severity_anomalies"] = _trim_anomalies(context["high_severity_anomalies"])

    # Trim reconciliations
    if "reconciliation" in context:
        formatted["reconciliation"] = _trim_reconciliations(context["reconciliation"])
    if "recent_reconciliation" in context:
        formatted["recent_reconciliation"] = _trim_reconciliations(context["recent_reconciliation"])

    # Pass through analytics and summary (already aggregated)
    if "analytics" in context:
        formatted["analytics"] = context["analytics"]
    if "summary" in context:
        formatted["summary"] = context["summary"]

    # Pass through messages/notes
    if "messages" in context:
        formatted["messages"] = context["messages"]

    # Pass through analysis
    if "analysis" in context:
        formatted["analysis"] = context["analysis"]

    # Pass through duplicate/missing payment details (already concise)
    if "duplicate_payments" in context:
        formatted["duplicate_payments"] = context["duplicate_payments"]
    if "missing_payments" in context:
        formatted["missing_payments"] = context["missing_payments"]

    target = get_target_token_budget(intent, is_broad_query)
    logger.info(
        "[ContextFormatter] Formatted context for intent=%s | broad=%s | target_budget=%s tokens",
        intent, is_broad_query, target,
    )

    return formatted


def get_target_token_budget(intent: str, is_broad_query: bool = False) -> int:
    """
    Get the target context token budget for a given intent and query type.

    Broad queries (e.g., "Why is payment missing?") → concise summary
    Specific queries (e.g., "Why is invoice INV00004 unpaid?") → detailed records
    """
    if is_broad_query:
        return BROAD_QUERY_MAX_TOKENS

    intent_budgets = {
        "invoice_lookup": SPECIFIC_QUERY_MAX_TOKENS,
        "anomaly_lookup": SPECIFIC_QUERY_MAX_TOKENS,
        "anomaly_explanation": SPECIFIC_QUERY_MAX_TOKENS,
        "reconciliation_analysis": SPECIFIC_QUERY_MAX_TOKENS,
        "dataset_review": DATASET_REVIEW_MAX_TOKENS,
        "report_summary": DATASET_REVIEW_MAX_TOKENS,
        "comparison": SPECIFIC_QUERY_MAX_TOKENS,
        "trend_analysis": SPECIFIC_QUERY_MAX_TOKENS,
        "recommendations": SPECIFIC_QUERY_MAX_TOKENS,
        "financial_analysis": SPECIFIC_QUERY_MAX_TOKENS,
    }

    return intent_budgets.get(intent, BROAD_QUERY_MAX_TOKENS)


def estimate_context_tokens(context: Dict[str, Any]) -> int:
    """Roughly estimate the token count of a context dict by character count."""
    if not context:
        return 0
    text = str(context)
    return len(text) // 4  # Rough character-to-token ratio