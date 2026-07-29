from datetime import datetime
from typing import Any, Dict, List, Optional

from app.shared.database.supabase_client import get_supabase_client


def _table(table: str):
    return get_supabase_client().table(table)


def _apply_date_filter(query, date_field: str, date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Apply optional date range filter to a query."""
    if date_from:
        query = query.gte(date_field, date_from)
    if date_to:
        query = query.lte(date_field, date_to)
    return query


def _parse_date(val: str) -> Optional[str]:
    """Try to parse a date value into ISO format string for filtering."""
    if not val:
        return None
    try:
        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y/%m/%d"):
            try:
                return datetime.strptime(val, fmt).isoformat()
            except ValueError:
                continue
        return val
    except Exception:
        return val


def calculate_revenue(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate revenue from erp_transactions with optional date filtering."""
    try:
        query = _table("erp_transactions").select("*", count="exact")
        query = _apply_date_filter(query, "invoice_date", date_from, date_to)
        result = query.execute()
        invoices = result.data or []
        total_count = result.count or len(invoices)

        total_revenue = sum(
            float(inv.get("amount", 0) or 0)
            for inv in invoices
            if str(inv.get("status", "")).upper() == "PAID"
        )
        outstanding = sum(
            float(inv.get("amount", 0) or 0)
            for inv in invoices
            if str(inv.get("status", "")).upper() != "PAID"
        )
        paid_count = sum(1 for inv in invoices if str(inv.get("status", "")).upper() == "PAID")

        return {
            "total_revenue": round(total_revenue, 2),
            "outstanding_revenue": round(outstanding, 2),
            "invoice_count": total_count,
            "paid_invoice_count": paid_count,
        }
    except Exception as exc:
        return {
            "total_revenue": 0.0,
            "outstanding_revenue": 0.0,
            "invoice_count": 0,
            "paid_invoice_count": 0,
        }


def calculate_expenses(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate expenses from bank_transactions with optional date filtering."""
    try:
        query = _table("bank_transactions").select("*", count="exact")
        query = _apply_date_filter(query, "date", date_from, date_to)
        result = query.execute()
        bank_txns = result.data or []

        total = sum(
            float(tx.get("amount", 0) or 0)
            for tx in bank_txns
            if float(tx.get("amount", 0) or 0) < 0
        )

        return {
            "total_expenses": round(abs(total), 2),
            "expense_count": sum(1 for tx in bank_txns if float(tx.get("amount", 0) or 0) < 0),
        }
    except Exception as exc:
        return {"total_expenses": 0.0, "expense_count": 0}


def calculate_profit(
    revenue: Optional[Dict[str, Any]] = None,
    expenses: Optional[Dict[str, Any]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    if revenue is None:
        revenue = calculate_revenue(date_from=date_from, date_to=date_to)
    if expenses is None:
        expenses = calculate_expenses(date_from=date_from, date_to=date_to)

    total_revenue = revenue.get("total_revenue", 0)
    total_expenses = expenses.get("total_expenses", 0)
    net_profit = total_revenue - total_expenses
    margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0

    return {
        "net_profit": round(net_profit, 2),
        "profit_margin": round(margin, 2),
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
    }


def calculate_cash_flow(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate cash flow from bank_transactions with optional date filtering."""
    try:
        query = _table("bank_transactions").select("*", count="exact")
        query = _apply_date_filter(query, "date", date_from, date_to)
        result = query.execute()
        transactions = result.data or []

        inflows = sum(
            float(tx.get("amount", 0) or 0)
            for tx in transactions
            if float(tx.get("amount", 0) or 0) > 0
        )
        outflows = sum(
            abs(float(tx.get("amount", 0) or 0))
            for tx in transactions
            if float(tx.get("amount", 0) or 0) < 0
        )

        return {
            "total_inflows": round(inflows, 2),
            "total_outflows": round(outflows, 2),
            "net_cash_flow": round(inflows - outflows, 2),
        }
    except Exception as exc:
        return {"total_inflows": 0.0, "total_outflows": 0.0, "net_cash_flow": 0.0}


def calculate_outstanding_invoices(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate outstanding invoices from erp_transactions with optional date filtering."""
    try:
        query = _table("erp_transactions").select("*", count="exact")
        query = _apply_date_filter(query, "invoice_date", date_from, date_to)
        result = query.execute()
        invoices = result.data or []

        outstanding = [inv for inv in invoices if str(inv.get("status", "")).upper() != "PAID"]
        total_outstanding = sum(float(inv.get("amount", 0) or 0) for inv in outstanding)

        return {
            "outstanding_count": len(outstanding),
            "total_outstanding": round(total_outstanding, 2),
            "average_outstanding": round(total_outstanding / len(outstanding), 2) if outstanding else 0.0,
        }
    except Exception as exc:
        return {"outstanding_count": 0, "total_outstanding": 0.0, "average_outstanding": 0.0}


def calculate_payment_delays(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate payment delays from erp_transactions with optional date filtering."""
    try:
        query = _table("erp_transactions").select("*", count="exact")
        query = _apply_date_filter(query, "invoice_date", date_from, date_to)
        result = query.execute()
        invoices = result.data or []

        delayed = [inv for inv in invoices if str(inv.get("status", "")).upper() == "OVERDUE"]
        total_delayed = sum(float(inv.get("amount", 0) or 0) for inv in delayed)

        return {
            "delayed_count": len(delayed),
            "total_delayed_amount": round(total_delayed, 2),
        }
    except Exception as exc:
        return {"delayed_count": 0, "total_delayed_amount": 0.0}


def calculate_reconciliation_rate(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate reconciliation rate from the reconciliations table with optional date filtering."""
    try:
        query = _table("reconciliations").select("*", count="exact")
        query = _apply_date_filter(query, "created_at", date_from, date_to)
        result = query.execute()
        reconciliations = result.data or []
        total = len(reconciliations)

        matched = sum(1 for r in reconciliations if str(r.get("status", "")).upper() == "MATCHED")
        rate = (matched / total * 100) if total > 0 else 0.0

        return {
            "reconciliation_rate": round(rate, 2),
            "total_invoices": total,
            "reconciled_count": matched,
            "unreconciled_count": total - matched,
        }
    except Exception as exc:
        return {"reconciliation_rate": 0.0, "total_invoices": 0, "reconciled_count": 0, "unreconciled_count": 0}


def calculate_total_transactions(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate total transaction counts and volumes across all sources."""
    try:
        # ERP transactions
        erp_query = _table("erp_transactions").select("*", count="exact")
        erp_query = _apply_date_filter(erp_query, "invoice_date", date_from, date_to)
        erp_result = erp_query.execute()
        erp_data = erp_result.data or []

        # Bank transactions
        bank_query = _table("bank_transactions").select("*", count="exact")
        bank_query = _apply_date_filter(bank_query, "date", date_from, date_to)
        bank_result = bank_query.execute()
        bank_data = bank_result.data or []

        erp_volume = sum(float(t.get("amount", 0) or 0) for t in erp_data)
        bank_volume = sum(abs(float(t.get("amount", 0) or 0)) for t in bank_data)

        return {
            "erp_count": len(erp_data),
            "bank_count": len(bank_data),
            "total_count": len(erp_data) + len(bank_data),
            "erp_volume": round(erp_volume, 2),
            "bank_volume": round(bank_volume, 2),
            "total_volume": round(erp_volume + bank_volume, 2),
        }
    except Exception as exc:
        return {"erp_count": 0, "bank_count": 0, "total_count": 0, "erp_volume": 0.0, "bank_volume": 0.0, "total_volume": 0.0}


def calculate_anomaly_stats(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate anomaly statistics from the anomalies table."""
    try:
        query = _table("anomalies").select("*", count="exact")
        query = _apply_date_filter(query, "created_at", date_from, date_to)
        result = query.execute()
        anomalies = result.data or []

        severity_dist: Dict[str, int] = {}
        type_dist: Dict[str, int] = {}
        for item in anomalies:
            sev = str(item.get("severity", "UNKNOWN")).upper()
            typ = str(item.get("anomaly_type", "UNKNOWN")).upper()
            severity_dist[sev] = severity_dist.get(sev, 0) + 1
            type_dist[typ] = type_dist.get(typ, 0) + 1

        return {
            "total_anomalies": len(anomalies),
            "high_severity_count": severity_dist.get("HIGH", 0),
            "medium_severity_count": severity_dist.get("MEDIUM", 0),
            "low_severity_count": severity_dist.get("LOW", 0),
            "severity_distribution": severity_dist,
            "type_distribution": type_dist,
        }
    except Exception as exc:
        return {"total_anomalies": 0, "high_severity_count": 0, "medium_severity_count": 0, "low_severity_count": 0, "severity_distribution": {}, "type_distribution": {}}


def calculate_matching_accuracy(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Calculate detailed reconciliation matching accuracy."""
    try:
        query = _table("reconciliations").select("*", count="exact")
        query = _apply_date_filter(query, "created_at", date_from, date_to)
        result = query.execute()
        reconciliations = result.data or []
        total = len(reconciliations)

        matched = sum(1 for r in reconciliations if str(r.get("status", "")).upper() == "MATCHED")
        unmatched = sum(1 for r in reconciliations if str(r.get("status", "")).upper() == "UNMATCHED")
        pending = sum(1 for r in reconciliations if str(r.get("status", "")).upper() == "PENDING")
        partial = sum(1 for r in reconciliations if str(r.get("status", "")).upper() == "PARTIAL")

        accuracy = (matched / total * 100) if total > 0 else 0.0

        return {
            "matching_accuracy": round(accuracy, 2),
            "total_reconciliations": total,
            "matched_count": matched,
            "unmatched_count": unmatched,
            "pending_count": pending,
            "partial_count": partial,
        }
    except Exception as exc:
        return {"matching_accuracy": 0.0, "total_reconciliations": 0, "matched_count": 0, "unmatched_count": 0, "pending_count": 0, "partial_count": 0}


KPI_CALCULATORS = {
    "revenue": calculate_revenue,
    "expenses": calculate_expenses,
    "profit": calculate_profit,
    "cash_flow": calculate_cash_flow,
    "outstanding_invoices": calculate_outstanding_invoices,
    "payment_delays": calculate_payment_delays,
    "reconciliation_rate": calculate_reconciliation_rate,
    "total_transactions": calculate_total_transactions,
    "anomaly_stats": calculate_anomaly_stats,
    "matching_accuracy": calculate_matching_accuracy,
}
