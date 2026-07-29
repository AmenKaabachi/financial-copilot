"""
Analytics Service — Shared orchestration layer for analytics data.

This service routes component data requests to the appropriate analytics engine.
It is consumed by:
  - Analytics Routes (existing dashboard endpoints)
  - Report Builder (component preview, live data)
  - AI Report Generator (data for generated reports)

Engines remain independent and are called through this service.
"""

import logging
from typing import Any, Dict, List, Optional

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
from app.modules.reporting.analytics.heatmap_engine import get_heatmap_data
from app.modules.reporting.analytics.pivot_engine import pivot_aggregate, pivot_group_by
from app.modules.reporting.analytics.component_registry import (
    get_component_by_id,
    get_all_components,
    select_components_for_prompt,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Shared service for analytics data retrieval."""

    # ------------------------------------------------------------------
    # KPI Methods
    # ------------------------------------------------------------------

    @staticmethod
    def get_all_kpis(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all KPIs in a single call."""
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
        }

    @staticmethod
    def get_single_kpi(
        kpi_key: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get a single KPI by key."""
        calculator = KPI_CALCULATORS.get(kpi_key)
        if not calculator:
            return None
        if kpi_key == "profit":
            revenue = calculate_revenue(date_from=date_from, date_to=date_to)
            expenses = calculate_expenses(date_from=date_from, date_to=date_to)
            return calculate_profit(revenue, expenses, date_from=date_from, date_to=date_to)
        return calculator(date_from=date_from, date_to=date_to)

    # ------------------------------------------------------------------
    # Chart Data Methods
    # ------------------------------------------------------------------

    @staticmethod
    def get_chart_data(
        chart_type: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        bucket: str = "month",
    ) -> Optional[Dict[str, Any]]:
        """Get pre-formatted chart data for a specific chart type."""
        if chart_type == "reconciliation_trend":
            data = get_reconciliation_trend(bucket=bucket, date_from=date_from, date_to=date_to)
            return {
                "chart_type": "line",
                "labels": [d["period"] for d in data],
                "datasets": [
                    {"label": "Successful", "data": [d["successful"] for d in data]},
                    {"label": "Failed", "data": [d["failed"] for d in data]},
                ],
            }
        elif chart_type == "anomaly_distribution":
            stats = calculate_anomaly_stats(date_from=date_from, date_to=date_to)
            sev_dist = stats.get("severity_distribution", {})
            return {
                "chart_type": "donut",
                "labels": list(sev_dist.keys()),
                "datasets": [{"data": list(sev_dist.values())}],
            }
        elif chart_type == "anomaly_type":
            stats = calculate_anomaly_stats(date_from=date_from, date_to=date_to)
            type_dist = stats.get("type_distribution", {})
            return {
                "chart_type": "bar",
                "labels": list(type_dist.keys()),
                "datasets": [{"label": "Anomaly Types", "data": list(type_dist.values())}],
            }
        elif chart_type == "transaction_volume":
            series = get_time_bucketed_series(bucket=bucket, value_key="amount", date_from=date_from, date_to=date_to)
            return {
                "chart_type": "bar",
                "labels": [d["period"] for d in series],
                "datasets": [{"label": "Transaction Volume", "data": [d["value"] for d in series]}],
            }
        elif chart_type == "bank_vs_erp":
            data = get_bank_vs_erp_trend(bucket=bucket, date_from=date_from, date_to=date_to)
            return {
                "chart_type": "grouped_bar",
                "labels": [d["period"] for d in data],
                "datasets": [
                    {"label": "ERP Volume", "data": [d["erp_volume"] for d in data]},
                    {"label": "Bank Volume", "data": [d["bank_volume"] for d in data]},
                ],
            }
        elif chart_type == "payment_status":
            revenue = calculate_revenue(date_from=date_from, date_to=date_to)
            paid = revenue.get("paid_invoice_count", 0)
            total = revenue.get("invoice_count", 0)
            outstanding = total - paid
            return {
                "chart_type": "pie",
                "labels": ["Paid", "Outstanding"],
                "datasets": [{"data": [paid, outstanding]}],
            }
        return None

    # ------------------------------------------------------------------
    # Table Data Methods
    # ------------------------------------------------------------------

    @staticmethod
    def get_table_data(
        data_source: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get raw table data from a data source."""
        from app.shared.database.supabase_client import get_supabase_client

        client = get_supabase_client()
        table_map = {
            "reconciliations": "reconciliations",
            "anomalies": "anomalies",
            "erp_transactions": "erp_transactions",
        }
        table_name = table_map.get(data_source)
        if not table_name:
            return []

        try:
            query = client.table(table_name).select("*").limit(limit)
            if date_from:
                query = query.gte("created_at", date_from)
            if date_to:
                query = query.lte("created_at", date_to)
            result = query.execute()
            return result.data or []
        except Exception as exc:
            logger.warning("Failed to fetch table data for %s: %s", data_source, exc)
            return []

    # ------------------------------------------------------------------
    # Heatmap
    # ------------------------------------------------------------------

    @staticmethod
    def get_heatmap() -> Dict[str, Any]:
        """Get heatmap data."""
        return get_heatmap_data()

    # ------------------------------------------------------------------
    # Pivot
    # ------------------------------------------------------------------

    @staticmethod
    def get_pivot(
        row_field: str = "category",
        column_field: str = "month",
        value_field: str = "amount",
        agg_func: str = "sum",
    ) -> Dict[str, Any]:
        """Get pivot table data."""
        return pivot_aggregate(
            row_field=row_field,
            column_field=column_field,
            value_field=value_field,
            agg_func=agg_func,
        )

    # ------------------------------------------------------------------
    # Trends
    # ------------------------------------------------------------------

    @staticmethod
    def get_trends(
        metric: str = "amount",
        bucket: str = "month",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get time-bucketed trend series."""
        series = get_time_bucketed_series(
            bucket=bucket, value_key=metric, date_from=date_from, date_to=date_to
        )
        return {"series": series, "bucket": bucket, "metric": metric}

    # ------------------------------------------------------------------
    # Component Preview
    # ------------------------------------------------------------------

    @staticmethod
    def get_component_preview(
        component_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get preview data for a specific analytics component.
        
        This is the key method that the Report Builder uses to render
        live data for any analytics component.
        """
        component = get_component_by_id(component_id)
        if not component:
            return None

        params = params or {}
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        bucket = params.get("bucket", "month")

        source = component["analytics_source"]
        comp_params = component.get("analytics_params", {})

        if source == "kpi":
            kpi_key = comp_params.get("kpi_key")
            if kpi_key:
                data = AnalyticsService.get_single_kpi(kpi_key, date_from, date_to)
                return {"component_id": component_id, "data": data, "type": "kpi"}

        elif source == "chart_data":
            chart_type = comp_params.get("chart_type")
            if chart_type:
                data = AnalyticsService.get_chart_data(chart_type, date_from, date_to, bucket)
                return {"component_id": component_id, "data": data, "type": "chart"}

        elif source == "table_data":
            data_source = comp_params.get("data_source")
            if data_source:
                limit = params.get("limit", 50)
                data = AnalyticsService.get_table_data(data_source, date_from, date_to, limit)
                return {"component_id": component_id, "data": data, "type": "table"}

        elif source == "heatmap":
            data = AnalyticsService.get_heatmap()
            return {"component_id": component_id, "data": data, "type": "heatmap"}

        elif source == "pivot":
            data = AnalyticsService.get_pivot(
                row_field=params.get("row_field", comp_params.get("row_field", "category")),
                column_field=params.get("column_field", comp_params.get("column_field", "month")),
                value_field=params.get("value_field", comp_params.get("value_field", "amount")),
            )
            return {"component_id": component_id, "data": data, "type": "pivot"}

        elif source == "trend":
            data = AnalyticsService.get_trends(
                metric=params.get("metric", "amount"),
                bucket=bucket,
                date_from=date_from,
                date_to=date_to,
            )
            return {"component_id": component_id, "data": data, "type": "trend"}

        return None

    # ------------------------------------------------------------------
    # AI Component Selection
    # ------------------------------------------------------------------

    @staticmethod
    def select_components_for_report(prompt: str) -> List[Dict[str, Any]]:
        """
        Select analytics components relevant to a user's report prompt.
        Uses intent-based matching via the component registry.
        """
        return select_components_for_prompt(prompt)