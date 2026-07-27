from typing import Any, Dict, List, Optional

from app.shared.database.retrieval import retrieve_context
from app.shared.financial_rules import build_financial_context
from app.shared.analytics import (
    calculate_reconciliation_metrics,
    calculate_anomaly_statistics,
    calculate_payment_statistics,
)


def calculate_revenue(
    invoices: Optional[List[Dict[str, Any]]] = None,
    transactions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if invoices is None:
        invoices = retrieve_context("financial_analysis", "", {}).get("sample_invoices", [])
    if transactions is None:
        transactions = retrieve_context("financial_analysis", "", {}).get("sample_transactions", [])

    total = sum(
        float(inv.get("amount", 0) or 0)
        for inv in invoices
        if inv.get("status") == "paid"
    )
    outstanding = sum(
        float(inv.get("amount", 0) or 0)
        for inv in invoices
        if inv.get("status") != "paid"
    )

    return {
        "total_revenue": round(total, 2),
        "outstanding_revenue": round(outstanding, 2),
        "invoice_count": len(invoices),
        "paid_invoice_count": sum(1 for inv in invoices if inv.get("status") == "paid"),
    }


def calculate_expenses(
    transactions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if transactions is None:
        transactions = retrieve_context("financial_analysis", "", {}).get("sample_transactions", [])

    total = sum(
        float(tx.get("amount", 0) or 0)
        for tx in transactions
        if tx.get("type") == "expense"
    )

    return {
        "total_expenses": round(total, 2),
        "expense_count": sum(1 for tx in transactions if tx.get("type") == "expense"),
    }


def calculate_profit(
    revenue: Optional[Dict[str, Any]] = None,
    expenses: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if revenue is None:
        revenue = calculate_revenue()
    if expenses is None:
        expenses = calculate_expenses()

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


def calculate_cash_flow(
    transactions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if transactions is None:
        transactions = retrieve_context("financial_analysis", "", {}).get("sample_transactions", [])

    inflows = sum(
        float(tx.get("amount", 0) or 0)
        for tx in transactions
        if tx.get("type") in ("income", "receipt", "payment_received")
    )
    outflows = sum(
        float(tx.get("amount", 0) or 0)
        for tx in transactions
        if tx.get("type") in ("expense", "payment_made", "disbursement")
    )

    return {
        "total_inflows": round(inflows, 2),
        "total_outflows": round(outflows, 2),
        "net_cash_flow": round(inflows - outflows, 2),
    }


def calculate_outstanding_invoices(
    invoices: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if invoices is None:
        invoices = retrieve_context("financial_analysis", "", {}).get("sample_invoices", [])

    outstanding = [inv for inv in invoices if inv.get("status") != "paid"]
    total_outstanding = sum(float(inv.get("amount", 0) or 0) for inv in outstanding)

    return {
        "outstanding_count": len(outstanding),
        "total_outstanding": round(total_outstanding, 2),
        "average_outstanding": round(total_outstanding / len(outstanding), 2) if outstanding else 0.0,
    }


def calculate_payment_delays(
    invoices: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if invoices is None:
        invoices = retrieve_context("financial_analysis", "", {}).get("sample_invoices", [])

    delayed = [inv for inv in invoices if inv.get("status") == "overdue"]
    total_delayed = sum(float(inv.get("amount", 0) or 0) for inv in delayed)

    return {
        "delayed_count": len(delayed),
        "total_delayed_amount": round(total_delayed, 2),
    }


def calculate_reconciliation_rate(
    invoices: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if invoices is None:
        invoices = retrieve_context("financial_analysis", "", {}).get("sample_invoices", [])

    metrics = calculate_reconciliation_metrics(invoices)
    total = len(invoices)
    reconciled = metrics.get("reconciled_count", 0) if isinstance(metrics, dict) else 0
    rate = (reconciled / total * 100) if total > 0 else 0.0

    return {
        "reconciliation_rate": round(rate, 2),
        "total_invoices": total,
        "reconciled_count": reconciled,
        "unreconciled_count": total - reconciled,
    }


KPI_CALCULATORS = {
    "revenue": calculate_revenue,
    "expenses": calculate_expenses,
    "profit": calculate_profit,
    "cash_flow": calculate_cash_flow,
    "outstanding_invoices": calculate_outstanding_invoices,
    "payment_delays": calculate_payment_delays,
    "reconciliation_rate": calculate_reconciliation_rate,
}