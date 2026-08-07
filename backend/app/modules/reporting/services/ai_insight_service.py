"""AI Insight Service - Generates financial insights for Report Builder AI Insight sections.

This service is a THIN orchestration layer. It does NOT build a new LLM pipeline.
It reuses the existing Copilot infrastructure:

    FinancialContextBuilder (resolves analytics data)
        -> report_prompts.py (existing prompt builders)
        -> generate_answer() from app.shared.llm.manager (existing LLM Manager)
        -> Generated insight -> PDF

Architecture:
    Report Builder AI Insight Section -> AIInsightService -> Existing LLM Manager -> Generated Insight
"""

import logging
from typing import Any, Dict, Optional

from app.modules.reporting.services.financial_context_builder import FinancialContextBuilder
from app.modules.reporting.prompts.report_prompts import (
    build_report_system_prompt,
    build_executive_summary_prompt,
    build_trend_analysis_prompt,
    build_anomaly_explanation_prompt,
    build_financial_outlook_prompt,
    build_cash_flow_analysis_prompt,
)
from app.shared.llm.manager import generate_answer

logger = logging.getLogger(__name__)

import os

# Maps AI insight types to the existing report prompt builders
INSIGHT_TYPE_TO_PROMPT_BUILDER = {
    "trend_analysis": build_trend_analysis_prompt,
    "anomaly_detection": build_anomaly_explanation_prompt,
    "performance_review": build_executive_summary_prompt,
    "forecast": build_financial_outlook_prompt,
    "cash_flow_analysis": build_cash_flow_analysis_prompt,
    "cash_flow": build_cash_flow_analysis_prompt,
}

# Intent used for model selection through the existing LLM Manager
INSIGHT_INTENT = "financial_analysis"
INSIGHT_MAX_TOKENS = 800
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("REPORT_AI_TIMEOUT_SECONDS", "15"))



class AIInsightService:
    """Thin orchestration layer for AI Insight generation in exported reports."""

    @staticmethod
    def generate(section: Dict[str, Any]) -> Optional[str]:
        """
        Generate a financial insight for an AI Insight report section.

        Args:
            section: Section definition from the report builder, e.g.:
                {
                  "type": "ai_insight",
                  "config": {
                    "insight_type": "trend_analysis",
                    "content": "AI insight will be generated..."
                  }
                }

        Returns:
            Generated insight text, or None if generation failed.
        """
        config = section.get("config", {})
        insight_type = config.get("insight_type") or config.get("topic") or "trend_analysis"
        # The report builder may store a topic field like "cash_flow_analysis" directly
        # on the section, or in config.topic
        if not insight_type and section.get("topic"):
            insight_type = section.get("topic")

        # Map the insight type to the existing prompt builder
        prompt_builder = INSIGHT_TYPE_TO_PROMPT_BUILDER.get(insight_type)
        if not prompt_builder:
            logger.warning(
                "[AI_INSIGHT] Unknown insight_type='%s' - falling back to trend_analysis",
                insight_type,
            )
            prompt_builder = build_trend_analysis_prompt

        try:
            # ------------------------------------------------------------------
            # Build financial context using the existing FinancialContextBuilder.
            # It resolves KPIs (including cash flow) from AnalyticsService.
            # ------------------------------------------------------------------
            context_request = {
                "report_type": "monthly_financial",
                "date_from": config.get("date_from"),
                "date_to": config.get("date_to"),
                "language": config.get("language", "en"),
            }
            context = FinancialContextBuilder.build(context_request)

            # ------------------------------------------------------------------
            # Build the prompt using the existing report prompt builders.
            # ------------------------------------------------------------------
            if insight_type in ("trend_analysis",):
                # Use the first available trend metric from the context
                trends = context.get("trends", {})
                if trends:
                    metric_name = next(iter(trends))
                    user_prompt = prompt_builder(metric_name, trends[metric_name], "en")
                else:
                    user_prompt = prompt_builder("revenue", {}, "en")
            elif insight_type in ("anomaly_detection",):
                user_prompt = prompt_builder(context.get("anomalies", {}), "en")
            elif insight_type in ("cash_flow_analysis", "cash_flow"):
                # Pass the full context so the cash flow prompt can pull
                # total_inflows / total_outflows / net_cash_flow values.
                user_prompt = prompt_builder(context, "en")
            else:
                user_prompt = prompt_builder(context, "en")

            system_prompt = build_report_system_prompt("en")

            logger.info(
                "[AI_INSIGHT] Calling existing LLM Manager (intent=%s, max_tokens=%s)",
                INSIGHT_INTENT,
                INSIGHT_MAX_TOKENS,
            )

            # ------------------------------------------------------------------
            # Call the existing LLM infrastructure - non-streaming, with the
            # existing model pool selection, fallback, and retry logic.
            # ------------------------------------------------------------------
            result = generate_answer(
                prompt=user_prompt,
                max_tokens=INSIGHT_MAX_TOKENS,
                intent=INSIGHT_INTENT,
                context=str(context),
            )

            answer = result.get("answer", "").strip()
            if not answer:
                logger.warning("[AI_INSIGHT] LLM returned an empty answer")
                return None

            logger.info(
                "[AI_INSIGHT] Generated insight (%d chars, model=%s, fallback=%s)",
                len(answer),
                result.get("model", "unknown"),
                result.get("fallback_used", False),
            )

            # Clean up the answer: if the model wrapped it in markdown code
            # fences or returned JSON, extract the useful text.
            answer = AIInsightService._extract_insight_text(answer)
            return answer

        except Exception as exc:
            logger.error(f"[AI_INSIGHT] Generation failed: {exc}", exc_info=True)
            return None

    @staticmethod
    def _extract_insight_text(answer: str) -> str:
        """Extract readable text if the model returned JSON or markdown."""
        if not answer:
            return answer

        import re

        # If wrapped in code fences, strip them
        fenced = re.fullmatch(r"```(?:json|text)?\n(.*?)\n```", answer, re.DOTALL)
        if fenced:
            answer = fenced.group(1).strip()

        # If the answer looks like JSON, try to extract the most useful field
        stripped = answer.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                import json as json_module

                data = json_module.loads(stripped)
                # Prefer a summary/explanation field; fall back to stringifying dict
                for key in (
                    "summary",
                    "insight",
                    "explanation",
                    "trend_description",
                    "outlook",
                    "content",
                ):
                    if isinstance(data, dict) and data.get(key):
                        return str(data[key]).strip()
                if isinstance(data, dict):
                    # Join top-level string values
                    parts = [
                        str(v).strip()
                        for v in data.values()
                        if isinstance(v, str) and v.strip()
                    ]
                    if parts:
                        return "\n".join(parts)
            except (json_module.JSONDecodeError, TypeError):
                pass  # Not really JSON - return as-is

        return answer