import logging
from fastapi import APIRouter, Query
from typing import Optional

from app.modules.reporting.analytics.kpi_calculators import (
    calculate_revenue,
    calculate_expenses,
    calculate_profit,
    calculate_cash_flow,
    calculate_outstanding_invoices,
    calculate_payment_delays,
    calculate_reconciliation_rate,
    calculate_total_transactions,
    calculate_anomaly_stats,
    calculate_matching_accuracy,
    KPI_CALCULATORS,
)
from app.modules.reporting.analytics.trend_engine import (
    get_time_bucketed_series,
    calculate_period_over_period,
    get_reconciliation_trend,
    get_anomaly_trend,
    get_bank_vs_erp_trend,
)
from app.modules.reporting.analytics.pivot_engine import (
    pivot_aggregate,
    pivot_group_by,
)
from app.modules.reporting.analytics.heatmap_engine import get_heatmap_data
from app.modules.reporting.analytics.forecast_placeholder import forecast_stub

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/kpis")
def get_kpis(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    company: Optional[str] = Query(default=None),
):
    revenue = calculate_revenue(date_from=date_from, date_to=date_to)
    expenses = calculate_expenses(date_from=date_from, date_to=date_to)
    profit = calculate_profit(revenue, expenses, date_from=date_from, date_to=date_to)
    cash_flow = calculate_cash_flow(date_from=date_from, date_to=date_to)
    outstanding = calculate_outstanding_invoices(date_from=date_from, date_to=date_to)
    delays = calculate_payment_delays(date_from=date_from, date_to=date_to)
    reconciliation = calculate_reconciliation_rate(date_from=date_from, date_to=date_to)
    total_txns = calculate_total_transactions(date_from=date_from, date_to=date_to)
    anomaly_stats = calculate_anomaly_stats(date_from=date_from, date_to=date_to)
    matching_accuracy = calculate_matching_accuracy(date_from=date_from, date_to=date_to)

    return {
        "status": "ok",
        "data": {
            "revenue": revenue,
            "expenses": expenses,
            "profit": profit,
            "cash_flow": cash_flow,
            "outstanding_invoices": outstanding,
            "payment_delays": delays,
            "reconciliation_rate": reconciliation,
            "total_transactions": total_txns,
            "anomaly_stats": anomaly_stats,
            "matching_accuracy": matching_accuracy,
        },
    }


@router.get("/trends")
def get_trends(
    metric: Optional[str] = Query(default="amount"),
    bucket: Optional[str] = Query(default="month"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    series = get_time_bucketed_series(bucket=bucket, value_key=metric, date_from=date_from, date_to=date_to)
    return {
        "status": "ok",
        "data": {
            "series": series,
            "bucket": bucket,
            "metric": metric,
        },
    }


@router.get("/chart-data")
def get_chart_data(
    chart_type: str = Query(..., description="Chart type: reconciliation_trend, anomaly_distribution, anomaly_type, transaction_volume, bank_vs_erp, payment_status"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    bucket: Optional[str] = Query(default="month"),
):
    """Get pre-formatted chart data for various chart types."""
    if chart_type == "reconciliation_trend":
        data = get_reconciliation_trend(bucket=bucket, date_from=date_from, date_to=date_to)
        return {"status": "ok", "data": {"chart_type": "line", "labels": [d["period"] for d in data], "datasets": [
            {"label": "Successful", "data": [d["successful"] for d in data]},
            {"label": "Failed", "data": [d["failed"] for d in data]},
        ]}}
    elif chart_type == "anomaly_distribution":
        stats = calculate_anomaly_stats(date_from=date_from, date_to=date_to)
        sev_dist = stats.get("severity_distribution", {})
        type_dist = stats.get("type_distribution", {})
        return {"status": "ok", "data": {"chart_type": "donut", "severity": {
            "labels": list(sev_dist.keys()),
            "data": list(sev_dist.values()),
        }, "type": {
            "labels": list(type_dist.keys()),
            "data": list(type_dist.values()),
        }}}
    # ✅ ADDED: New anomaly_type endpoint
    elif chart_type == "anomaly_type":
        stats = calculate_anomaly_stats(date_from=date_from, date_to=date_to)
        type_dist = stats.get("type_distribution", {})
        return {
            "status": "ok",
            "data": {
                "chart_type": "bar",
                "labels": list(type_dist.keys()),
                "datasets": [
                    {
                        "label": "Anomaly Types",
                        "data": list(type_dist.values())
                    }
                ]
            }
        }
    elif chart_type == "transaction_volume":
        series = get_time_bucketed_series(bucket=bucket, value_key="amount", date_from=date_from, date_to=date_to)
        return {"status": "ok", "data": {"chart_type": "bar", "labels": [d["period"] for d in series], "datasets": [
            {"label": "Transaction Volume", "data": [d["value"] for d in series]},
        ]}}
    elif chart_type == "bank_vs_erp":
        data = get_bank_vs_erp_trend(bucket=bucket, date_from=date_from, date_to=date_to)
        return {"status": "ok", "data": {"chart_type": "grouped_bar", "labels": [d["period"] for d in data], "datasets": [
            {"label": "ERP Volume", "data": [d["erp_volume"] for d in data]},
            {"label": "Bank Volume", "data": [d["bank_volume"] for d in data]},
        ]}}
    elif chart_type == "payment_status":
        revenue = calculate_revenue(date_from=date_from, date_to=date_to)
        paid = revenue.get("paid_invoice_count", 0)
        total = revenue.get("invoice_count", 0)
        outstanding = total - paid
        return {"status": "ok", "data": {"chart_type": "pie", "labels": ["Paid", "Outstanding"], "datasets": [
            {"data": [paid, outstanding]},
        ]}}
    else:
        return {"status": "error", "message": f"Unknown chart_type: {chart_type}"}


@router.get("/heatmap")
def get_heatmap(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    data = get_heatmap_data()
    return {
        "status": "ok",
        "data": data,
    }


@router.post("/drilldown")
def drilldown(
    dimension: Optional[str] = Query(default="category"),
    value_field: Optional[str] = Query(default="amount"),
):
    result = pivot_group_by(group_by=dimension, value_field=value_field)
    return {
        "status": "ok",
        "data": result,
    }


@router.get("/pivot")
def get_pivot(
    row_field: Optional[str] = Query(default="category"),
    column_field: Optional[str] = Query(default="month"),
    value_field: Optional[str] = Query(default="amount"),
    agg_func: Optional[str] = Query(default="sum"),
):
    result = pivot_aggregate(
        row_field=row_field,
        column_field=column_field,
        value_field=value_field,
        agg_func=agg_func,
    )
    return {
        "status": "ok",
        "data": result,
    }


@router.get("/forecast")
def get_forecast(
    periods: Optional[int] = Query(default=3),
    metric: Optional[str] = Query(default="revenue"),
):
    result = forecast_stub(periods=periods, metric=metric)
    return {
        "status": "ok",
        "data": result,
    }