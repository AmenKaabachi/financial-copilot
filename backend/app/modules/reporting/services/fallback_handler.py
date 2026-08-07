"""Fallback handler for AI report generation.

Provides layered fallback strategy when LLM generation fails:
1. Database templates (if configured)
2. Static default templates
3. Dynamic fallback based on analytics data

Ensures report generation never completely fails.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FallbackHandler:
    """Handles fallback content generation when LLM fails."""

    # Static default templates for each section type
    DEFAULT_TEMPLATES = {
        "executive_summary": {
            "summary": "Financial report generated for the specified period. Key metrics and trends are analyzed in the following sections.",
            "key_highlights": [
                "Review the KPI section for detailed performance metrics",
                "Analyze trend data for pattern identification",
                "Check anomaly section for any detected issues",
            ],
            "overall_assessment": "Data available for review; detailed analysis requires AI generation",
        },
        "kpi_explanation": {
            "kpi_name": "N/A",
            "value": "N/A",
            "explanation": "KPI explanation unavailable due to AI generation failure. Please review the raw KPI values in the analytics section.",
            "trend": "stable",
            "comparison": None,
        },
        "trend_analysis": {
            "metric_name": "N/A",
            "trend_description": "Trend analysis unavailable due to AI generation failure. Please review the chart data in the analytics section.",
            "pattern": "stable",
            "key_drivers": ["Review historical data for pattern identification"],
            "forecast": None,
        },
        "anomaly_explanation": {
            "anomaly_type": "various",
            "count": 0,
            "explanation": "Anomaly analysis unavailable due to AI generation failure. Please review the anomaly statistics in the analytics section.",
            "potential_causes": ["Data quality issues", "Process variations"],
            "recommended_actions": ["Review anomaly details manually"],
        },
        "recommendations": {
            "recommendations": [
                {
                    "action": "Review financial data manually",
                    "reason": "AI generation unavailable - manual review required",
                    "priority": "medium",
                    "estimated_impact": "Ensures data accuracy",
                },
                {
                    "action": "Check for data anomalies",
                    "reason": "Identify potential issues requiring attention",
                    "priority": "high",
                    "estimated_impact": "Prevents financial errors",
                },
            ],
        },
        "financial_outlook": {
            "outlook": "neutral",
            "short_term_forecast": "Forecast unavailable due to AI generation failure. Base decisions on current trend data.",
            "long_term_forecast": "Forecast unavailable due to AI generation failure. Monitor trends regularly.",
            "key_opportunities": ["Review performance metrics for improvement areas"],
            "key_risks": ["Monitor for anomalies or data quality issues"],
        },
    }

    @staticmethod
    def get_fallback_section(section_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get fallback content for a section type.

        Args:
            section_type: Type of section (executive_summary, kpi_explanation, etc.)
            context: Financial context for dynamic fallback

        Returns:
            Fallback content dictionary
        """
        logger.warning(f"Using fallback for section: {section_type}")

        # Try database template first (if configured)
        db_template = FallbackHandler._try_database_template(section_type, context)
        if db_template:
            logger.info(f"Using database template for {section_type}")
            return db_template

        # Try dynamic fallback based on context
        dynamic_content = FallbackHandler._try_dynamic_fallback(section_type, context)
        if dynamic_content:
            logger.info(f"Using dynamic fallback for {section_type}")
            return dynamic_content

        # Fall back to static default template
        logger.info(f"Using static default template for {section_type}")
        return FallbackHandler.DEFAULT_TEMPLATES.get(section_type, {})

    @staticmethod
    def _try_database_template(section_type: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Try to load template from database.

        Args:
            section_type: Type of section
            context: Financial context

        Returns:
            Template dictionary if found, None otherwise
        """
        # TODO: Implement database template retrieval
        # This would query a report_templates table for custom templates
        # For now, return None to skip to next fallback layer
        return None

    @staticmethod
    def _try_dynamic_fallback(section_type: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate dynamic fallback based on analytics data.

        Args:
            section_type: Type of section
            context: Financial context

        Returns:
            Dynamic content dictionary if possible, None otherwise
        """
        if section_type == "executive_summary":
            return FallbackHandler._dynamic_executive_summary(context)
        elif section_type == "kpi_explanation":
            return FallbackHandler._dynamic_kpi_explanation(context)
        elif section_type == "recommendations":
            return FallbackHandler._dynamic_recommendations(context)
        elif section_type == "financial_outlook":
            return FallbackHandler._dynamic_financial_outlook(context)

        return None

    @staticmethod
    def _dynamic_executive_summary(context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate dynamic executive summary from context."""
        kpis = context.get("kpis", {})
        period = context.get("period", {})

        # Extract key metrics
        revenue = kpis.get("revenue", {}).get("value", "N/A")
        expenses = kpis.get("expenses", {}).get("value", "N/A")
        profit = kpis.get("profit", {}).get("value", "N/A")

        highlights = []
        if revenue != "N/A":
            highlights.append(f"Revenue: {revenue}")
        if expenses != "N/A":
            highlights.append(f"Expenses: {expenses}")
        if profit != "N/A":
            highlights.append(f"Profit: {profit}")

        return {
            "summary": f"Financial report for period {period.get('from', 'N/A')} to {period.get('to', 'N/A')}. Key metrics are available in the analytics section.",
            "key_highlights": highlights or ["Review analytics section for detailed metrics"],
            "overall_assessment": "Financial data available for review. Detailed analysis requires AI generation.",
        }

    @staticmethod
    def _dynamic_kpi_explanation(context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate dynamic KPI explanation from context."""
        kpis = context.get("kpis", {})
        
        # Get first available KPI
        for kpi_name, kpi_data in kpis.items():
            if isinstance(kpi_data, dict) and "value" in kpi_data:
                return {
                    "kpi_name": kpi_name.replace("_", " ").title(),
                    "value": str(kpi_data.get("value", "N/A")),
                    "explanation": f"KPI value is {kpi_data.get('value', 'N/A')}. Detailed explanation requires AI generation.",
                    "trend": kpi_data.get("trend", "stable"),
                    "comparison": kpi_data.get("change", None),
                }

        return FallbackHandler.DEFAULT_TEMPLATES["kpi_explanation"]

    @staticmethod
    def _dynamic_recommendations(context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate dynamic recommendations from context."""
        kpis = context.get("kpis", {})
        anomalies = context.get("anomalies", {})
        recommendations = []

        # Check for anomalies
        anomaly_count = anomalies.get("total_count", 0)
        if anomaly_count > 0:
            recommendations.append({
                "action": f"Investigate {anomaly_count} detected anomalies",
                "reason": f"Anomalies may indicate data quality or process issues",
                "priority": "high",
                "estimated_impact": "Improves data accuracy and process reliability",
            })

        # Check for negative trends
        for kpi_name, kpi_data in kpis.items():
            if isinstance(kpi_data, dict) and kpi_data.get("trend") == "declining":
                recommendations.append({
                    "action": f"Review declining {kpi_name.replace('_', ' ')}",
                    "reason": "Negative trend requires investigation",
                    "priority": "medium",
                    "estimated_impact": "Addresses performance decline",
                })

        # Add generic recommendation if none specific
        if not recommendations:
            recommendations.append({
                "action": "Review all financial metrics",
                "reason": "Regular review ensures financial health",
                "priority": "medium",
                "estimated_impact": "Maintains financial awareness",
            })

        return {"recommendations": recommendations}

    @staticmethod
    def _dynamic_financial_outlook(context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate dynamic financial outlook from context."""
        kpis = context.get("kpis", {})
        trends = context.get("trends", {})

        # Determine outlook based on trends
        outlook = "neutral"
        positive_indicators = 0
        negative_indicators = 0

        for kpi_name, kpi_data in kpis.items():
            if isinstance(kpi_data, dict):
                trend = kpi_data.get("trend", "stable")
                if trend == "improving":
                    positive_indicators += 1
                elif trend == "declining":
                    negative_indicators += 1

        if positive_indicators > negative_indicators:
            outlook = "positive"
        elif negative_indicators > positive_indicators:
            outlook = "negative"

        return {
            "outlook": outlook,
            "short_term_forecast": f"Based on current trends, outlook is {outlook}. Detailed forecasting requires AI generation.",
            "long_term_forecast": "Monitor trends regularly for accurate long-term forecasting.",
            "key_opportunities": ["Review improving metrics for optimization opportunities"] if positive_indicators > 0 else ["Review performance for improvement opportunities"],
            "key_risks": ["Monitor declining metrics for risk mitigation"] if negative_indicators > 0 else ["Monitor for emerging risks"],
        }

    @staticmethod
    def get_fallback_for_all_sections(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get fallback content for all sections at once.

        Args:
            context: Financial context

        Returns:
            Dictionary with all section types as keys
        """
        fallback_sections = {}
        for section_type in FallbackHandler.DEFAULT_TEMPLATES.keys():
            fallback_sections[section_type] = FallbackHandler.get_fallback_section(section_type, context)
        return fallback_sections
