from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any, Dict, Iterable, Optional, Tuple

from database.supabase_client import get_supabase_client


logger = logging.getLogger(__name__)


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


def get_dataset_summary() -> Dict[str, Any]:
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

    logger.info(
        "Dataset summary retrieved: invoices=%s, payments=%s, anomalies=%s, reconciliations=%s",
        len(invoices),
        len(transactions),
        len(anomalies),
        len(reconciliations),
    )
    return summary


def get_recommendation_context() -> Dict[str, Any]:
    summary = get_dataset_summary()
    return {
        "summary": summary["metrics"],
        "high_severity_anomalies": get_high_severity_anomalies(limit=5),
        "duplicate_payments": get_duplicate_payments(limit=5),
        "missing_payments": get_missing_payments(limit=5),
        "recent_reconciliation": get_recent_reconciliation(limit=3),
    }

