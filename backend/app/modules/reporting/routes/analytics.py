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
    KPI_CALCULATORS,
)
from app.modules.reporting.analytics.trend_engine import (
    get_time_bucketed_series,
    calculate_period_over_period,
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
    revenue = calculate_revenue()
    expenses = calculate_expenses()
    profit = calculate_profit(revenue, expenses)
    cash_flow = calculate_cash_flow()
    outstanding = calculate_outstanding_invoices()
    delays = calculate_payment_delays()
    reconciliation = calculate_reconciliation_rate()

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
        },
    }


@router.get("/trends")
def get_trends(
    metric: Optional[str] = Query(default="amount"),
    bucket: Optional[str] = Query(default="month"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
):
    series = get_time_bucketed_series(bucket=bucket, value_key=metric)
    return {
        "status": "ok",
        "data": {
            "series": series,
            "bucket": bucket,
            "metric": metric,
        },
    }


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