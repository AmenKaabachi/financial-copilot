"""Financial Context Builder for AI Report Generation.

Builds clean, compact financial context from AnalyticsService for LLM consumption.
Never accesses raw database tables directly - uses processed analytics outputs.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.modules.reporting.services.analytics_service import AnalyticsService
from app.shared.context_budget import calculate_budget, validate_budget, ContextOverflowError
from app.shared.token_counter import count_tokens

logger = logging.getLogger(__name__)


class FinancialContextBuilder:
    """Builds financial context for AI report generation from AnalyticsService."""

    # Target context token budget for report generation
    TARGET_CONTEXT_TOKENS = 3500

    @staticmethod
    def build(request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build financial context from AnalyticsService for AI report generation.

        Args:
            request: Report generation request with date ranges, report type, etc.

        Returns:
            Structured financial context package ready for LLM consumption
        """
        date_from = request.get("date_from") or request.get("period_start")
        date_to = request.get("date_to") or request.get("period_end")
        report_type = request.get("report_type", "monthly_financial")
        language = request.get("language", "en")
        business_objectives = request.get("business_objectives", [])
        objective = request.get("objective")
        audience = request.get("audience")
        additional_instructions = request.get("additional_instructions")
        report_title = request.get("report_title")

        logger.info(
            "Building financial context for report_type=%s, period=%s to %s, language=%s",
            report_type, date_from, date_to, language
        )

        context = {
            "report_type": report_type,
            "period": {
                "from": date_from,
                "to": date_to,
            },
            "language": language,
            "business_objectives": business_objectives,
            "objective": objective,
            "audience": audience,
            "additional_instructions": additional_instructions,
            "report_title": report_title,
        }

        # Fetch KPIs from AnalyticsService
        try:
            kpis = AnalyticsService.get_all_kpis(date_from=date_from, date_to=date_to)
            context["kpis"] = FinancialContextBuilder._compress_kpis(kpis)
            logger.info("Retrieved KPIs for context")
        except Exception as e:
            logger.warning("Failed to retrieve KPIs: %s", e)
            context["kpis"] = {}

        # Fetch trend data based on report type
        if FinancialContextBuilder._needs_trends(report_type):
            try:
                trends = FinancialContextBuilder._get_trend_data(date_from, date_to, report_type)
                context["trends"] = trends
                logger.info("Retrieved trend data for context")
            except Exception as e:
                logger.warning("Failed to retrieve trends: %s", e)
                context["trends"] = {}

        # Fetch anomaly data for risk reports
        if FinancialContextBuilder._needs_anomalies(report_type):
            try:
                anomalies = FinancialContextBuilder._get_anomaly_data(date_from, date_to)
                context["anomalies"] = anomalies
                logger.info("Retrieved anomaly data for context")
            except Exception as e:
                logger.warning("Failed to retrieve anomalies: %s", e)
                context["anomalies"] = {}

        # Fetch chart data if needed
        if FinancialContextBuilder._needs_charts(report_type):
            try:
                charts = FinancialContextBuilder._get_chart_data(date_from, date_to, report_type)
                context["charts"] = charts
                logger.info("Retrieved chart data for context")
            except Exception as e:
                logger.warning("Failed to retrieve chart data: %s", e)
                context["charts"] = {}

        # Validate context token budget
        context_str = str(context)
        estimated_tokens = count_tokens(context_str)

        if estimated_tokens > FinancialContextBuilder.TARGET_CONTEXT_TOKENS:
            logger.warning(
                "Context exceeds target tokens (%s > %s), applying compression",
                estimated_tokens, FinancialContextBuilder.TARGET_CONTEXT_TOKENS
            )
            context = FinancialContextBuilder._compress_context(context)

        logger.info(
            "Final context size: %s tokens (target: %s)",
            count_tokens(str(context)), FinancialContextBuilder.TARGET_CONTEXT_TOKENS
        )

        return context

    @staticmethod
    def _compress_kpis(kpis: Dict[str, Any]) -> Dict[str, Any]:
        """Compress KPI data to essential fields only."""
        compressed = {}
        for key, value in kpis.items():
            if isinstance(value, dict):
                compressed[key] = {
                    "value": value.get("value"),
                    "change": value.get("change"),
                    "trend": value.get("trend"),
                }
            else:
                compressed[key] = value
        return compressed

    @staticmethod
    def _needs_trends(report_type: str) -> bool:
        """Determine if report type needs trend data."""
        trend_needing_reports = {
            "monthly_financial",
            "quarterly_review",
            "annual_report",
            "performance_analysis",
        }
        return report_type in trend_needing_reports

    @staticmethod
    def _needs_anomalies(report_type: str) -> bool:
        """Determine if report type needs anomaly data."""
        anomaly_needing_reports = {
            "risk_analysis",
            "audit_report",
            "reconciliation_report",
            "monthly_financial",  # Include anomalies in monthly reports
        }
        return report_type in anomaly_needing_reports

    @staticmethod
    def _needs_charts(report_type: str) -> bool:
        """Determine if report type needs chart data."""
        chart_needing_reports = {
            "monthly_financial",
            "quarterly_review",
            "performance_analysis",
        }
        return report_type in chart_needing_reports

    @staticmethod
    def _get_trend_data(date_from: Optional[str], date_to: Optional[str], report_type: str) -> Dict[str, Any]:
        """Get trend data from AnalyticsService."""
        trends = {}

        # Revenue trend
        revenue_trend = AnalyticsService.get_trends(
            metric="amount", bucket="month", date_from=date_from, date_to=date_to
        )
        trends["revenue"] = FinancialContextBuilder._summarize_trend(revenue_trend.get("series", []))

        # Reconciliation trend
        rec_trend = AnalyticsService.get_chart_data("reconciliation_trend", date_from, date_to)
        if rec_trend:
            trends["reconciliation"] = FinancialContextBuilder._summarize_chart_data(rec_trend)

        return trends

    @staticmethod
    def _get_anomaly_data(date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
        """Get anomaly data from AnalyticsService."""
        anomaly_stats = AnalyticsService.get_all_kpis(date_from=date_from, date_to=date_to)
        anomaly_stats = anomaly_stats.get("anomaly_stats", {})

        return {
            "total_count": anomaly_stats.get("total_count", anomaly_stats.get("total_anomalies", 0)),
            "severity_distribution": anomaly_stats.get("severity_distribution", {}),
            "type_distribution": anomaly_stats.get("type_distribution", {}),
            "high_severity_count": anomaly_stats.get("high_severity_count", anomaly_stats.get("severity_distribution", {}).get("high", 0)),
        }

    @staticmethod
    def _get_chart_data(date_from: Optional[str], date_to: Optional[str], report_type: str) -> Dict[str, Any]:
        """Get relevant chart data from AnalyticsService."""
        charts = {}

        # Anomaly distribution
        anomaly_dist = AnalyticsService.get_chart_data("anomaly_distribution", date_from, date_to)
        if anomaly_dist:
            charts["anomaly_distribution"] = anomaly_dist

        # Transaction volume
        tx_volume = AnalyticsService.get_chart_data("transaction_volume", date_from, date_to)
        if tx_volume:
            charts["transaction_volume"] = tx_volume

        return charts

    @staticmethod
    def _summarize_trend(series: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize trend series to key points."""
        if not series:
            return {}

        if len(series) <= 3:
            # Return all if small
            return {"data_points": series}

        # Return first, middle, last for compression
        return {
            "data_points": [
                series[0],
                series[len(series) // 2],
                series[-1],
            ],
            "total_points": len(series),
        }

    @staticmethod
    def _summarize_chart_data(chart_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize chart data to essential structure."""
        if not chart_data:
            return {}

        return {
            "chart_type": chart_data.get("chart_type"),
            "labels": chart_data.get("labels", [])[:10],  # Limit to 10 labels
            "datasets": [
                {
                    "label": ds.get("label"),
                    "data": ds.get("data", [])[:10],  # Limit to 10 data points
                }
                for ds in chart_data.get("datasets", [])
            ],
        }

    @staticmethod
    def _compress_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply aggressive compression to context to fit token budget."""
        compressed = dict(context)

        # Limit trend data points
        if "trends" in compressed:
            for trend_key, trend_data in compressed["trends"].items():
                if isinstance(trend_data, dict) and "data_points" in trend_data:
                    compressed["trends"][trend_key]["data_points"] = trend_data["data_points"][:5]

        # Limit chart labels
        if "charts" in compressed:
            for chart_key, chart_data in compressed["charts"].items():
                if isinstance(chart_data, dict) and "labels" in chart_data:
                    compressed["charts"][chart_key]["labels"] = chart_data["labels"][:5]
                if isinstance(chart_data, dict) and "datasets" in chart_data:
                    for dataset in compressed["charts"][chart_key]["datasets"]:
                        if "data" in dataset:
                            dataset["data"] = dataset["data"][:5]

        # Limit business objectives
        if "business_objectives" in compressed:
            compressed["business_objectives"] = compressed["business_objectives"][:3]

        return compressed
