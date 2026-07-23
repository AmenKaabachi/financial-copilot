from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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


def calculate_reconciliation_metrics(reconciliations: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(reconciliations)
    matched = sum(1 for r in reconciliations if _to_str(r.get("status", "")).upper() == "MATCHED")
    failed = total - matched
    return {
        "total_reconciliations": total,
        "matched_reconciliations": matched,
        "failed_reconciliations": failed,
        "match_rate": round(matched / total, 4) if total else 0.0,
    }


def calculate_anomaly_statistics(anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
    severity_counts: Dict[str, int] = {}
    type_counts: Dict[str, int] = {}
    for row in anomalies:
        severity = _to_str(row.get("severity", "UNKNOWN")).upper()
        anomaly_type = _to_str(row.get("anomaly_type", "UNKNOWN")).upper()
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        type_counts[anomaly_type] = type_counts.get(anomaly_type, 0) + 1

    return {
        "total_anomalies": len(anomalies),
        "high_severity_count": severity_counts.get("HIGH", 0),
        "medium_severity_count": severity_counts.get("MEDIUM", 0),
        "low_severity_count": severity_counts.get("LOW", 0),
        "missing_payment_count": type_counts.get("MISSING_PAYMENT", 0),
        "duplicate_payment_count": type_counts.get("DUPLICATE_PAYMENT", 0),
        "late_payment_count": type_counts.get("LATE_PAYMENT", 0),
        "severity_distribution": severity_counts,
        "type_distribution": type_counts,
    }


def calculate_payment_statistics(
    invoices: List[Dict[str, Any]],
    transactions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total_invoices = len(invoices)
    paid_invoices = sum(1 for row in invoices if _to_str(row.get("status", "")).upper() == "PAID")
    pending_invoices = sum(1 for row in invoices if _to_str(row.get("status", "")).upper() == "PENDING")
    overdue_invoices = sum(1 for row in invoices if _to_str(row.get("status", "")).upper() == "OVERDUE")
    total_payments = len(transactions)

    payment_amounts = [_to_float(t.get("amount")) for t in transactions if _to_float(t.get("amount")) is not None]
    total_payment_value = sum(payment_amounts) if payment_amounts else 0.0

    invoice_amounts = [_to_float(i.get("amount")) for i in invoices if _to_float(i.get("amount")) is not None]
    total_invoice_value = sum(invoice_amounts) if invoice_amounts else 0.0

    return {
        "total_invoices": total_invoices,
        "paid_invoice_count": paid_invoices,
        "pending_invoice_count": pending_invoices,
        "overdue_invoice_count": overdue_invoices,
        "total_payment_count": total_payments,
        "total_payment_value": total_payment_value,
        "total_invoice_value": total_invoice_value,
        "payment_coverage": round(paid_invoices / total_invoices, 4) if total_invoices else 0.0,
    }


def calculate_risk_score(
    invoice: Optional[Dict[str, Any]],
    transactions: Optional[List[Dict[str, Any]]],
    reconciliation: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    score = 0
    reasons: List[str] = []

    if invoice:
        invoice_amount = _to_float(invoice.get("amount"))
        transaction_amount = _to_float(transactions[0].get("amount")) if transactions else None
        if invoice_amount is not None and transaction_amount is not None:
            difference = abs(invoice_amount - transaction_amount)
            if invoice_amount > 0:
                pct = difference / invoice_amount
                if pct > 0.2:
                    score += 40
                    reasons.append(f"Severe payment mismatch ({pct:.1%} difference)")
                elif pct > 0.05:
                    score += 20
                    reasons.append(f"Payment mismatch ({pct:.1%} difference)")

        reconciliation_status = _to_str(reconciliation.get("status", "")).upper() if reconciliation else ""
        if reconciliation_status == "FAILED":
            score += 30
            reasons.append("Failed reconciliation")

        invoice_status = _to_str(invoice.get("status", "")).upper()
        if invoice_status == "PAID" and reconciliation_status == "FAILED":
            score += 20
            reasons.append("Paid with reconciliation issue")

    if score >= 60:
        risk_level = "HIGH"
    elif score >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_score": min(score, 100),
        "risk_level": risk_level,
        "risk_reasons": reasons,
    }


def calculate_severity(
    invoice: Optional[Dict[str, Any]],
    transactions: Optional[List[Dict[str, Any]]],
    reconciliation: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    invoice_amount = _to_float(invoice.get("amount")) if invoice else None
    transaction_amount = _to_float(transactions[0].get("amount")) if transactions else None

    if invoice_amount is not None and transaction_amount is not None:
        difference = invoice_amount - transaction_amount
        if invoice_amount > 0:
            difference_pct = abs(difference) / invoice_amount
            if difference_pct < 0.05:
                return {"severity": "LOW", "difference_percentage": round(difference_pct, 4)}
            elif difference_pct <= 0.20:
                return {"severity": "MEDIUM", "difference_percentage": round(difference_pct, 4)}
            else:
                return {"severity": "HIGH", "difference_percentage": round(difference_pct, 4)}

    return {"severity": "LOW", "difference_percentage": 0.0}


def generate_recommendations(
    invoice: Optional[Dict[str, Any]],
    transactions: Optional[List[Dict[str, Any]]],
    reconciliation: Optional[Dict[str, Any]],
    risk: Dict[str, Any],
) -> List[Dict[str, str]]:
    recommendations: List[Dict[str, str]] = []

    if invoice:
        invoice_status = _to_str(invoice.get("status", "")).upper()
        invoice_amount = _to_float(invoice.get("amount"))
        transaction_amount = _to_float(transactions[0].get("amount")) if transactions else None

        if transaction_amount is None and invoice_status == "PAID":
            recommendations.append({"priority": "HIGH", "action": "Verify missing payment in bank statement"})

        if invoice_amount is not None and transaction_amount is not None:
            difference = invoice_amount - transaction_amount
            if difference > 0:
                recommendations.append({"priority": "HIGH", "action": f"Verify missing payment of {difference:.2f} USD"})
            elif difference < 0:
                recommendations.append({"priority": "MEDIUM", "action": f"Investigate overpayment of {abs(difference):.2f} USD"})

        reconciliation_status = _to_str(reconciliation.get("status", "")).upper() if reconciliation else ""
        if reconciliation_status == "FAILED":
            recommendations.append({"priority": "HIGH", "action": "Check bank statement and update invoice status"})

        if risk.get("risk_level") == "HIGH":
            recommendations.append({"priority": "HIGH", "action": "Escalate to finance manager for review"})

    if not recommendations:
        recommendations.append({"priority": "LOW", "action": "No immediate action required"})

    return recommendations
