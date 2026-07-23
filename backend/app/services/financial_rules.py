from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.analytics import (
    calculate_reconciliation_metrics,
    calculate_anomaly_statistics,
    calculate_payment_statistics,
    calculate_risk_score,
    calculate_severity,
    generate_recommendations,
)

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace(",", "").replace("USD", "").replace("$", "").strip()
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def analyze_invoice(
    invoice: Optional[Dict[str, Any]],
    transactions: Optional[List[Dict[str, Any]]],
    reconciliation: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []

    invoice_amount = _to_float(invoice.get("amount")) if invoice else None
    invoice_currency = _to_str(invoice.get("currency")) if invoice else ""
    invoice_status = _to_str(invoice.get("status")) if invoice else ""
    invoice_id = _to_str(invoice.get("invoice_id")) if invoice else ""
    invoice_supplier = _to_str(invoice.get("supplier")) if invoice else ""
    invoice_due_date = _to_str(invoice.get("due_date")) if invoice else ""

    transaction = transactions[0] if transactions else None
    transaction_amount = _to_float(transaction.get("amount")) if transaction else None
    transaction_id = _to_str(transaction.get("id")) if transaction else ""
    transaction_status = _to_str(transaction.get("status")) if transaction else ""

    reconciliation_status = _to_str(reconciliation.get("status")) if reconciliation else ""
    reconciliation_reason = _to_str(reconciliation.get("reason")) if reconciliation else ""

    severity_info = calculate_severity(invoice, transactions, reconciliation)

    if invoice_amount is not None and transaction_amount is not None:
        difference = invoice_amount - transaction_amount
        if difference > 0:
            insights.append(
                {
                    "type": "PAYMENT_SHORTFALL",
                    "severity": severity_info.get("severity", "MEDIUM"),
                    "message": f"Payment is missing {difference:.2f} {invoice_currency}".strip(),
                    "invoice_amount": invoice_amount,
                    "payment_amount": transaction_amount,
                    "difference": difference,
                    "currency": invoice_currency or "USD",
                    "difference_percentage": severity_info.get("difference_percentage", 0.0),
                }
            )
        elif difference < 0:
            insights.append(
                {
                    "type": "PAYMENT_OVERPAYMENT",
                    "severity": severity_info.get("severity", "LOW"),
                    "message": f"Payment exceeds invoice by {abs(difference):.2f} {invoice_currency}".strip(),
                    "invoice_amount": invoice_amount,
                    "payment_amount": transaction_amount,
                    "difference": difference,
                    "currency": invoice_currency or "USD",
                    "difference_percentage": severity_info.get("difference_percentage", 0.0),
                }
            )

    if reconciliation_status.upper() == "FAILED":
        message = "Bank transaction does not reconcile with invoice"
        if reconciliation_reason:
            message = f"Bank transaction does not reconcile with invoice: {reconciliation_reason}"
        insights.append(
            {
                "type": "RECONCILIATION_FAILURE",
                "severity": "HIGH",
                "message": message,
                "reconciliation_status": reconciliation_status,
            }
        )

    if invoice_status.upper() == "PAID" and any(
        insight["type"] in {"PAYMENT_SHORTFALL", "RECONCILIATION_FAILURE"} for insight in insights
    ):
        insights.append(
            {
                "type": "PAID_WITH_ISSUE",
                "severity": "HIGH",
                "message": (
                    "Invoice is marked PAID but payment or reconciliation issues were detected. "
                    "The accounting system record does not match the bank evidence."
                ),
            }
        )

    if invoice_status.upper() not in {"PAID", "PARTIALLY_PAID", "PENDING", "OVERDUE"} and invoice_status:
        insights.append(
            {
                "type": "UNUSUAL_STATUS",
                "severity": "LOW",
                "message": f"Invoice has an unexpected status: {invoice_status}",
            }
        )

    return insights


def build_financial_context(
    invoice: Optional[Dict[str, Any]],
    transactions: Optional[List[Dict[str, Any]]],
    reconciliation: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    insights = analyze_invoice(invoice, transactions, reconciliation)
    risk = calculate_risk_score(invoice, transactions, reconciliation)
    recommendations = generate_recommendations(invoice, transactions, reconciliation, risk)

    if not insights and not risk.get("risk_reasons") and not recommendations:
        return None

    return {
        "invoice": {
            "id": _to_str(invoice.get("invoice_id")) if invoice else "",
            "status": _to_str(invoice.get("status")) if invoice else "",
            "amount": _to_float(invoice.get("amount")) if invoice else None,
            "currency": _to_str(invoice.get("currency")) if invoice else "",
            "supplier": _to_str(invoice.get("supplier")) if invoice else "",
            "due_date": _to_str(invoice.get("due_date")) if invoice else "",
        },
        "transaction": {
            "id": _to_str(transactions[0].get("id")) if transactions else "",
            "amount": _to_float(transactions[0].get("amount")) if transactions else None,
            "status": _to_str(transactions[0].get("status")) if transactions else "",
        },
        "reconciliation": {
            "status": _to_str(reconciliation.get("status")) if reconciliation else "",
            "reason": _to_str(reconciliation.get("reason")) if reconciliation else "",
        },
        "analysis": [
            {
                "type": insight["type"],
                "severity": insight["severity"],
                "message": insight["message"],
                **{
                    k: v
                    for k, v in insight.items()
                    if k in {"difference", "invoice_amount", "payment_amount", "currency", "reconciliation_status", "difference_percentage"}
                },
            }
            for insight in insights
        ],
        "risk_assessment": risk,
        "recommendations": recommendations,
    }
