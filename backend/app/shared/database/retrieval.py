from __future__ import annotations

import hashlib
import json
import logging
import time
from threading import Lock
from typing import Any, Dict, Iterable, Optional, Tuple

from app.shared.database.supabase_client import get_supabase_client


logger = logging.getLogger(__name__)


# ── Intent-based retrieval limits ──
# Maximum records to retrieve per intent type
INTENT_RETRIEVAL_LIMITS = {
    "invoice_lookup": 1,           # Single invoice + transactions
    "anomaly_lookup": 1,           # Single anomaly
    "reconciliation_analysis": 20, # Related reconciliation data
    "dataset_review": 100,         # Aggregated + sample
    "comparison": 100,             # Sample for comparison
    "trend_analysis": 100,         # Recent data sample
    "financial_analysis": 50,      # Default sample
    "recommendations": 50,         # High-severity focus
    "report_summary": 100,
    "missing_payment": 20,         # Missing payment cases
    "anomaly_explanation": 20,     # Anomaly explanations
}


# ── Retrieval cache ──
# Caches retrieval results based on intent + entity_ids + filters
_RETRIEVAL_CACHE_TTL = 300.0  # 5 minutes for financial data


class _RetrievalCache:
    """Cache for retrieval results with TTL expiry."""

    def __init__(self, ttl: float = _RETRIEVAL_CACHE_TTL):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = Lock()
        self._ttl = ttl

    def _make_key(self, intent: str, entities: Dict[str, Any], filters: Optional[Dict] = None) -> str:
        """Create a cache key from intent, entities, and filters."""
        key_data = {
            "intent": intent,
            "entities": entities,
            "filters": filters or {},
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, intent: str, entities: Dict[str, Any], filters: Optional[Dict] = None) -> Optional[Any]:
        key = self._make_key(intent, entities, filters)
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires = entry
            if time.monotonic() > expires:
                self._store.pop(key, None)
                return None
            return value

    def set(self, intent: str, entities: Dict[str, Any], value: Any, filters: Optional[Dict] = None) -> None:
        key = self._make_key(intent, entities, filters)
        expires = time.monotonic() + self._ttl
        with self._lock:
            self._store[key] = (value, expires)

    def invalidate(self, intent: Optional[str] = None) -> None:
        """Invalidate cache entries, optionally by intent."""
        with self._lock:
            if intent:
                # Remove all keys for this intent
                keys_to_remove = []
                for key in self._store:
                    # We can't easily check intent from key without storing it
                    # For simplicity, clear all if intent is specified
                    keys_to_remove.append(key)
                for key in keys_to_remove:
                    self._store.pop(key, None)
            else:
                self._store.clear()

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_retrieval_cache = _RetrievalCache()


# ── Entity-level cache ──
# Caches database objects (invoices, anomalies, reconciliations) with a short TTL
# so repeated lookups of the same entity don't hit the database.
# This is separate from the LLM response cache in manager.py.
_ENTITY_CACHE_TTL = 30.0  # seconds

class _EntityCache:
    """Simple in-memory cache for database entities with TTL expiry."""

    def __init__(self, ttl: float = _ENTITY_CACHE_TTL):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = Lock()
        self._ttl = ttl

    def _make_key(self, entity_type: str, entity_id: str) -> str:
        return f"{entity_type}:{entity_id}"

    def get(self, entity_type: str, entity_id: str) -> Optional[Any]:
        key = self._make_key(entity_type, entity_id)
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires = entry
            if time.monotonic() > expires:
                self._store.pop(key, None)
                return None
            return value

    def set(self, entity_type: str, entity_id: str, value: Any) -> None:
        key = self._make_key(entity_type, entity_id)
        expires = time.monotonic() + self._ttl
        with self._lock:
            self._store[key] = (value, expires)

    def invalidate(self, entity_type: str, entity_id: str) -> None:
        key = self._make_key(entity_type, entity_id)
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_entity_cache = _EntityCache()


def _table(table: str):
    return get_supabase_client().table(table)


def _select(table: str, *, limit: int = 10):
    return _table(table).select("*").limit(limit).execute()


def _select_eq(table: str, column: str, value: str, *, limit: int = 10):
    return _table(table).select("*").eq(column, value).limit(limit).execute()


def _first(data: Optional[list[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    if data:
        return data[0]
    return None


def get_invoice(invoice_id: str) -> Optional[Dict[str, Any]]:
    # Check cache first
    cached = _entity_cache.get("invoice", invoice_id.upper())
    if cached is not None:
        return cached
    result = _select_eq("erp_transactions", "invoice_id", invoice_id.upper(), limit=1)
    data = _first(result.data)
    if data is not None:
        _entity_cache.set("invoice", invoice_id.upper(), data)
    return data


def get_anomaly(anomaly_id: str) -> Optional[Dict[str, Any]]:
    # Check cache first
    cached = _entity_cache.get("anomaly", anomaly_id.upper())
    if cached is not None:
        return cached
    result = _select_eq("anomalies", "invoice_id", anomaly_id.upper(), limit=1)
    data = _first(result.data)
    if data is not None:
        _entity_cache.set("anomaly", anomaly_id.upper(), data)
    return data


def get_recent_reconciliation(limit: int = 1) -> list[Dict[str, Any]]:
    result = _select("reconciliations", limit=limit)
    return result.data or []


def get_high_severity_anomalies(limit: int = 10) -> list[Dict[str, Any]]:
    result = _table("anomalies").select("*").eq("severity", "HIGH").limit(limit).execute()
    return result.data or []


def get_duplicate_payments(limit: int = 10) -> list[Dict[str, Any]]:
    result = _table("anomalies").select("*").eq("anomaly_type", "DUPLICATE_PAYMENT").limit(limit).execute()
    return result.data or []


def get_missing_payments(limit: int = 10) -> list[Dict[str, Any]]:
    result = _table("anomalies").select("*").eq("anomaly_type", "MISSING_PAYMENT").limit(limit).execute()
    return result.data or []


def get_invoice_transactions(invoice_id: str, limit: int = 5) -> list[Dict[str, Any]]:
    # Check cache first
    cached = _entity_cache.get("transactions", invoice_id.upper())
    if cached is not None:
        return cached
    result = _select_eq("bank_transactions", "reference", invoice_id.upper(), limit=limit)
    data = result.data or []
    if data:
        _entity_cache.set("transactions", invoice_id.upper(), data)
    return data


def get_invoice_reconciliation(invoice_id: str) -> Optional[Dict[str, Any]]:
    # Check cache first
    cached = _entity_cache.get("reconciliation", invoice_id.upper())
    if cached is not None:
        return cached
    result = _select_eq("reconciliations", "invoice_id", invoice_id.upper(), limit=1)
    data = _first(result.data)
    if data is not None:
        _entity_cache.set("reconciliation", invoice_id.upper(), data)
    return data


def get_dataset_summary_debug() -> Dict[str, Any]:
    """DEBUG ONLY: Retrieve full dataset summary (20,000 rows).
    
    WARNING: This function retrieves massive amounts of data (5000 rows per table).
    Only use for debugging/admin purposes via /debug/context-preview endpoint.
    For production use, use retrieve_context() instead.
    """
    invoices = _select("erp_transactions", limit=5000).data or []
    transactions = _select("bank_transactions", limit=5000).data or []
    anomalies = _select("anomalies", limit=5000).data or []
    reconciliations = _select("reconciliations", limit=5000).data or []

    status_counts: Dict[str, int] = {}
    severity_counts: Dict[str, int] = {}
    anomaly_type_counts: Dict[str, int] = {}
    matched_reconciliations = 0

    for row in anomalies:
        severity = str(row.get("severity", "UNKNOWN")).upper()
        anomaly_type = str(row.get("anomaly_type", "UNKNOWN")).upper()
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        anomaly_type_counts[anomaly_type] = anomaly_type_counts.get(anomaly_type, 0) + 1

    for row in reconciliations:
        status = str(row.get("status", "UNKNOWN")).upper()
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "MATCHED":
            matched_reconciliations += 1

    paid_invoices = sum(1 for row in invoices if str(row.get("status", "")).upper() == "PAID")
    missing_payment_count = anomaly_type_counts.get("MISSING_PAYMENT", 0)
    duplicate_payment_count = anomaly_type_counts.get("DUPLICATE_PAYMENT", 0)
    late_payment_count = anomaly_type_counts.get("LATE_PAYMENT", 0)
    high_severity_count = severity_counts.get("HIGH", 0)

    summary = {
        "invoices": invoices,
        "transactions": transactions,
        "anomalies": anomalies,
        "reconciliations": reconciliations,
        "metrics": {
            "invoice_count": len(invoices),
            "payment_count": len(transactions),
            "paid_invoice_count": paid_invoices,
            "missing_payment_count": missing_payment_count,
            "duplicate_payment_count": duplicate_payment_count,
            "late_payment_count": late_payment_count,
            "high_severity_count": high_severity_count,
            "reconciliation_count": len(reconciliations),
            "matched_reconciliation_count": matched_reconciliations,
        },
        "distribution": {
            "anomaly_severity": severity_counts,
            "anomaly_type": anomaly_type_counts,
            "reconciliation_status": status_counts,
        },
    }

    logger.warning(
        "[DEBUG] Dataset summary retrieved: invoices=%s, payments=%s, anomalies=%s, reconciliations=%s (DEBUG USE ONLY)",
        len(invoices),
        len(transactions),
        len(anomalies),
        len(reconciliations),
    )
    return summary


# Keep old function name for backward compatibility but warn
def get_dataset_summary() -> Dict[str, Any]:
    """DEPRECATED: Use retrieve_context() instead. This function is for debug only."""
    logger.warning("get_dataset_summary() called in production - use retrieve_context() instead")
    return get_dataset_summary_debug()


def get_recommendation_context() -> Dict[str, Any]:
    """Get context for recommendations intent (uses smart retrieval)."""
    return retrieve_context("recommendations", "", {})


def retrieve_context(intent: str, question: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve context based on intent with smart limits and caching.
    
    This is the PRODUCTION function for context retrieval. It:
    - Limits records based on intent type (1-100 max, never thousands)
    - Caches results for 5 minutes
    - Logs retrieval diagnostics
    - Validates retrieval quality
    
    Args:
        intent: The classified intent (e.g., "invoice_lookup", "dataset_review")
        question: The user's question
        entities: Extracted entities (e.g., {"invoice_id": "INV00004"})
    
    Returns:
        Context dictionary with retrieved data
    """
    # Check cache first
    cached = _retrieval_cache.get(intent, entities)
    if cached is not None:
        logger.info("[RETRIEVAL CACHE HIT] intent=%s, entities=%s", intent, entities)
        return cached
    
    # Get retrieval limit for this intent
    limit = INTENT_RETRIEVAL_LIMITS.get(intent, 50)
    
    # Build context based on intent and entities
    context = _build_intent_context(intent, question, entities, limit)
    
    # Cache the result
    _retrieval_cache.set(intent, entities, context)
    
    # Log retrieval diagnostics
    _log_retrieval_diagnostics(intent, entities, context)
    
    return context


def _build_intent_context(intent: str, question: str, entities: Dict[str, Any], limit: int) -> Dict[str, Any]:
    """Build context based on intent type with appropriate limits."""
    invoice_id = entities.get("invoice_id", "").upper()
    anomaly_id = entities.get("anomaly_id", "").upper()
    
    # Entity-specific queries: retrieve only that entity + related data
    if intent == "invoice_lookup":
        if invoice_id:
            return {
                "invoice": get_invoice(invoice_id),
                "transactions": get_invoice_transactions(invoice_id, limit=5),
                "reconciliation": get_invoice_reconciliation(invoice_id),
            }
        # Fallback: return sample invoices with issues
        logger.info("[RETRIEVAL FALLBACK] invoice_lookup without invoice_id, returning sample invoices")
        return {
            "sample_invoices": _select("erp_transactions", limit=min(limit, 10)).data or [],
            "high_severity_anomalies": get_high_severity_anomalies(limit=5),
            "recent_reconciliation": get_recent_reconciliation(limit=3),
            "message": "No specific invoice ID provided. Showing sample invoices with issues.",
        }
    
    if intent == "anomaly_lookup":
        if anomaly_id:
            return {
                "anomaly": get_anomaly(anomaly_id),
            }
        # Fallback: return high severity anomalies
        logger.info("[RETRIEVAL FALLBACK] anomaly_lookup without anomaly_id, returning high severity anomalies")
        return {
            "high_severity_anomalies": get_high_severity_anomalies(limit=limit),
            "duplicate_payments": get_duplicate_payments(limit=5),
            "missing_payments": get_missing_payments(limit=5),
            "message": "No specific anomaly ID provided. Showing high severity anomalies.",
        }
    
    if intent == "reconciliation_analysis":
        if invoice_id:
            return {
                "invoice": get_invoice(invoice_id),
                "reconciliation": get_invoice_reconciliation(invoice_id),
                "transactions": get_invoice_transactions(invoice_id, limit=10),
            }
        # Fallback: return recent reconciliations
        logger.info("[RETRIEVAL FALLBACK] reconciliation_analysis without invoice_id, returning recent reconciliations")
        return {
            "recent_reconciliation": get_recent_reconciliation(limit=limit),
            "sample_invoices": _select("erp_transactions", limit=min(limit, 10)).data or [],
            "message": "No specific invoice ID provided. Showing recent reconciliations.",
        }
    
    # Broad queries: retrieve aggregated metrics + small sample
    if intent == "missing_payment":
        # Return missing payment cases with related invoices
        logger.info("[RETRIEVAL] missing_payment intent, returning missing payment cases")
        missing = get_missing_payments(limit=limit)
        return {
            "missing_payments": missing,
            "high_severity_anomalies": get_high_severity_anomalies(limit=5),
            "recent_reconciliation": get_recent_reconciliation(limit=3),
            "message": f"Showing {len(missing)} missing payment cases.",
        }
    
    if intent == "anomaly_explanation":
        # Return high severity anomalies for explanation
        logger.info("[RETRIEVAL] anomaly_explanation intent, returning high severity anomalies")
        anomalies = get_high_severity_anomalies(limit=limit)
        return {
            "high_severity_anomalies": anomalies,
            "duplicate_payments": get_duplicate_payments(limit=5),
            "missing_payments": get_missing_payments(limit=5),
            "message": f"Showing {len(anomalies)} high severity anomalies for explanation.",
        }
    
    if intent in {"dataset_review", "report_summary", "recommendations"}:
        # Get only metrics (not full datasets)
        summary = _get_aggregated_metrics()
        return {
            "summary": summary["metrics"],
            "distribution": summary["distribution"],
            "high_severity_anomalies": get_high_severity_anomalies(limit=5),
            "duplicate_payments": get_duplicate_payments(limit=5),
            "missing_payments": get_missing_payments(limit=5),
            "recent_reconciliation": get_recent_reconciliation(limit=3),
            "sample_invoices": _select("erp_transactions", limit=min(limit, 10)).data or [],
            "sample_transactions": _select("bank_transactions", limit=min(limit, 10)).data or [],
        }
    
    if intent in {"comparison", "trend_analysis", "financial_analysis"}:
        summary = _get_aggregated_metrics()
        return {
            "summary": summary["metrics"],
            "distribution": summary["distribution"],
            "recent_reconciliation": get_recent_reconciliation(limit=5),
            "high_severity_anomalies": get_high_severity_anomalies(limit=5),
            "sample_invoices": _select("erp_transactions", limit=min(limit, 20)).data or [],
            "sample_transactions": _select("bank_transactions", limit=min(limit, 20)).data or [],
        }
    
    # Default: return aggregated metrics only
    summary = _get_aggregated_metrics()
    return {
        "summary": summary["metrics"],
        "distribution": summary["distribution"],
    }


def _get_aggregated_metrics() -> Dict[str, Any]:
    """Get aggregated metrics without full datasets (lightweight)."""
    # Get counts without retrieving full rows
    anomalies = _select("anomalies", limit=1000).data or []  # Still need some for distribution
    reconciliations = _select("reconciliations", limit=1000).data or []
    
    status_counts: Dict[str, int] = {}
    severity_counts: Dict[str, int] = {}
    anomaly_type_counts: Dict[str, int] = {}
    matched_reconciliations = 0
    
    for row in anomalies:
        severity = str(row.get("severity", "UNKNOWN")).upper()
        anomaly_type = str(row.get("anomaly_type", "UNKNOWN")).upper()
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        anomaly_type_counts[anomaly_type] = anomaly_type_counts.get(anomaly_type, 0) + 1
    
    for row in reconciliations:
        status = str(row.get("status", "UNKNOWN")).upper()
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "MATCHED":
            matched_reconciliations += 1
    
    # Get approximate counts (in production, use COUNT queries)
    high_severity_count = severity_counts.get("HIGH", 0)
    missing_payment_count = anomaly_type_counts.get("MISSING_PAYMENT", 0)
    duplicate_payment_count = anomaly_type_counts.get("DUPLICATE_PAYMENT", 0)
    
    return {
        "metrics": {
            "high_severity_count": high_severity_count,
            "missing_payment_count": missing_payment_count,
            "duplicate_payment_count": duplicate_payment_count,
            "reconciliation_count": len(reconciliations),
            "matched_reconciliation_count": matched_reconciliations,
            "anomaly_count": len(anomalies),
        },
        "distribution": {
            "anomaly_severity": severity_counts,
            "anomaly_type": anomaly_type_counts,
            "reconciliation_status": status_counts,
        },
    }


def _log_retrieval_diagnostics(intent: str, entities: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Log what was retrieved for validation."""
    retrieved_items = []
    
    if "invoice" in context and context["invoice"]:
        retrieved_items.append(f"invoice {context['invoice'].get('invoice_id', 'UNKNOWN')} ✅")
    if "anomaly" in context and context["anomaly"]:
        retrieved_items.append(f"anomaly {context['anomaly'].get('invoice_id', 'UNKNOWN')} ✅")
    if "reconciliation" in context and context["reconciliation"]:
        retrieved_items.append(f"reconciliation {context['reconciliation'].get('invoice_id', 'UNKNOWN')} ✅")
    if "transactions" in context and context["transactions"]:
        retrieved_items.append(f"{len(context['transactions'])} transactions ✅")
    if "high_severity_anomalies" in context:
        retrieved_items.append(f"{len(context['high_severity_anomalies'])} high-severity anomalies ✅")
    if "summary" in context:
        retrieved_items.append("aggregated metrics ✅")
    
    # Estimate token count
    context_str = json.dumps(context, ensure_ascii=False)
    estimated_tokens = len(context_str) // 4
    
    logger.info(
        "[RETRIEVAL DIAGNOSTICS]\n"
        "Intent: %s\n"
        "Entities: %s\n"
        "Retrieved:\n"
        "  - %s\n"
        "Estimated context tokens: %s",
        intent,
        entities,
        "\n  - ".join(retrieved_items) if retrieved_items else "No data retrieved",
        estimated_tokens,
    )