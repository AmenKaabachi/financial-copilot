"""AI Report Service - Main orchestration for AI-powered report generation.

This service orchestrates the existing Copilot LLM infrastructure to generate
intelligent financial report sections. It does NOT duplicate AI capabilities -
it leverages the existing LLM manager, model pools, and fallback mechanisms.

Architecture:
    ReportService -> AIReportService -> Existing LLM Manager -> Generated Sections
"""

import logging
import time
from typing import Any, Dict, List, Optional

from app.modules.reporting.services.financial_context_builder import FinancialContextBuilder
from app.modules.reporting.prompts.report_prompts import (
    build_report_system_prompt,
    build_executive_summary_prompt,
    build_kpi_explanation_prompt,
    build_trend_analysis_prompt,
    build_anomaly_explanation_prompt,
    build_recommendations_prompt,
    build_financial_outlook_prompt,
    get_correction_prompt,
)
from app.modules.reporting.services.report_validators import ReportValidators
from app.modules.reporting.services.fallback_handler import FallbackHandler
from app.modules.reporting.services.audit_logger import AuditLogger
from app.modules.reporting.schemas.ai_report_schemas import (
    ReportGenerationRequest,
    ValidationResult,
)

# Import existing LLM manager from shared infrastructure
from app.shared.llm.manager import generate_answer

logger = logging.getLogger(__name__)

# Map section types to existing Copilot intents for model selection
SECTION_TO_INTENT = {
    "executive_summary": "report_summary",
    "kpi_explanation": "financial_analysis",
    "trend_analysis": "trend_analysis",
    "anomaly_explanation": "financial_analysis",
    "recommendations": "recommendations",
    "financial_outlook": "financial_analysis",
}

# Max tokens per section type
SECTION_MAX_TOKENS = {
    "executive_summary": 800,
    "kpi_explanation": 600,
    "trend_analysis": 700,
    "anomaly_explanation": 700,
    "recommendations": 900,
    "financial_outlook": 800,
}


class AIReportService:
    """Main orchestration service for AI-powered report generation."""

    def __init__(self):
        self.context_builder = FinancialContextBuilder()
        self.validators = ReportValidators()
        self.fallback_handler = FallbackHandler()
        self.audit_logger = AuditLogger()

    def generate_report_definition_from_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Act as a Financial Reporting Architect: parse prompt into a structured JSON report definition.
        
        The user prompt is strictly an instruction for report layout/sections,
        and MUST NOT be copied into titles or text section contents.
        """
        import json
        import re
        from app.modules.reporting.services.report_section_mapper import SectionNormalizer

        system_prompt = (
            "You are a Senior Financial Reporting Architect.\n"
            "Your task is NOT to write report body paragraphs.\n"
            "Your task is to design the report structure as valid JSON matching the schema.\n\n"
            "CRITICAL RULES:\n"
            "1. NEVER repeat user instructions, summarize the user prompt, or put user requirements inside text section contents.\n"
            "2. ALWAYS return JSON containing 'name', 'description', and 'sections'.\n"
            "3. Each item in 'sections' MUST have 'type' and 'config' keys.\n"
            "4. Allowed section types ONLY: 'title', 'text', 'kpi', 'chart', 'table', 'ai_insight', 'page_break', 'image', 'recommendation'.\n"
            "5. Map user requests into appropriate sections:\n"
            "   - 'Revenue KPIs' -> type: 'kpi', config: { 'title': 'Revenue KPIs', 'data_source': 'revenue' }\n"
            "   - 'Reconciliation Trend chart' -> type: 'chart', config: { 'title': 'Reconciliation Trend', 'chart_type': 'reconciliation_trend' }\n"
            "   - 'ERP Transactions table' -> type: 'table', config: { 'title': 'ERP Transactions', 'data_source': 'erp_transactions' }\n"
            "   - 'AI insights / analysis' -> type: 'ai_insight', config: { 'insight_type': 'trend_analysis' }\n"
            "   - 'Image section' -> type: 'image', config: { 'url': '...', 'caption': 'Overview' }\n\n"
            "Example JSON output:\n"
            "{\n"
            '  "name": "Q2 Financial Performance Review",\n'
            '  "description": "Executive Financial Analysis",\n'
            '  "sections": [\n'
            '    { "type": "text", "config": { "title": "Executive Summary", "content": "This report summarizes financial performance for the period." } },\n'
            '    { "type": "kpi", "config": { "title": "Revenue KPIs", "data_source": "revenue" } },\n'
            '    { "type": "chart", "config": { "title": "Reconciliation Trend", "chart_type": "reconciliation_trend" } },\n'
            '    { "type": "table", "config": { "title": "ERP Transactions", "data_source": "erp_transactions" } },\n'
            '    { "type": "ai_insight", "config": { "insight_type": "trend_analysis" } }\n'
            '  ]\n'
            "}"
        )

        user_instruction = f"Design a financial report structure based on this request: {prompt}"

        try:
            result = generate_answer(
                prompt=user_instruction,
                system_prompt=system_prompt,
                max_tokens=1000,
                intent="financial_analysis",
            )
            raw_answer = result.get("answer", "").strip()

            # Clean JSON code fences
            fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw_answer, re.DOTALL)
            if fenced:
                raw_answer = fenced.group(1).strip()
            else:
                raw_answer = raw_answer.strip()

            # Parse JSON
            raw_def = json.loads(raw_answer)
            name = raw_def.get("name") or "Executive Financial Report"
            description = raw_def.get("description") or "AI-generated financial report structure"
            raw_sections = raw_def.get("sections", [])

            # Normalize sections through SectionNormalizer
            norm_sections = SectionNormalizer.normalize_sections(raw_sections)

            definition = {
                "name": name,
                "description": description,
                "sections": norm_sections,
            }

            # Validate definition against schema and prompt echo
            val_res = self.validators.validate_ai_report_definition(definition, original_prompt=prompt)
            if not val_res.is_valid:
                logger.warning(f"[AI_BUILDER] Validation errors found in architect definition: {val_res.errors}")

            return definition

        except Exception as exc:
            logger.warning(f"[AI_BUILDER] AI Report Architect generation failed ({exc}) — building heuristic fallback definition")
            # Fallback heuristic normalization directly from prompt
            fallback_sections = []
            prompt_low = prompt.lower()

            fallback_sections.append({
                "type": "text",
                "config": {
                    "title": "Executive Summary",
                    "content": "This executive report summarizes overall financial performance, transaction metrics, and key analytical highlights.",
                },
            })

            if "kpi" in prompt_low or "revenue" in prompt_low or "metric" in prompt_low:
                fallback_sections.append({
                    "type": "kpi",
                    "config": {"title": "Key Metrics", "data_source": "revenue"},
                })

            if "chart" in prompt_low or "trend" in prompt_low or "reconciliation" in prompt_low:
                fallback_sections.append({
                    "type": "chart",
                    "config": {"title": "Reconciliation Trend", "chart_type": "reconciliation_trend"},
                })

            if "table" in prompt_low or "transaction" in prompt_low or "erp" in prompt_low:
                fallback_sections.append({
                    "type": "table",
                    "config": {
                        "title": "ERP Transactions",
                        "data_source": "erp_transactions",
                        "visible_columns": ["invoice_id", "supplier", "invoice_date", "due_date", "amount", "currency", "status"],
                        "limit": 20,
                    },
                })

            if "insight" in prompt_low or "ai" in prompt_low or "analysis" in prompt_low:
                fallback_sections.append({
                    "type": "ai_insight",
                    "config": {"title": "AI Financial Insights", "insight_type": "trend_analysis"},
                })

            norm_sections = SectionNormalizer.normalize_sections(fallback_sections)
            return {
                "name": "Financial Performance Report",
                "description": "Executive Financial Analysis",
                "sections": norm_sections,
            }


    def generate_report_sections(
        self,
        request: ReportGenerationRequest,
        report_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate all requested report sections using AI.

        Args:
            request: Report generation request
            report_id: Optional report ID for audit logging

        Returns:
            Dictionary with generated sections
        """
        start_time = time.time()
        sections = {}
        sections_generated = []
        fallback_used = False
        total_token_usage = {}
        model_used = "unknown"

        logger.info(
            "Starting AI report generation for report_type=%s, sections=%s",
            request.report_type,
            request.sections,
        )

        try:
            # Build financial context from AnalyticsService
            context = self.context_builder.build(request.dict())
            logger.info("Financial context built successfully")

            # Generate each section
            for section_type in request.sections:
                try:
                    section_result = self._generate_single_section(
                        section_type=section_type,
                        context=context,
                        language=request.language,
                    )
                    
                    sections[section_type] = section_result["content"]
                    sections_generated.append(section_type)
                    
                    # Track token usage
                    if "token_usage" in section_result:
                        total_token_usage[section_type] = section_result["token_usage"]
                    
                    # Track model used
                    if "model" in section_result:
                        model_used = section_result["model"]

                except Exception as e:
                    logger.warning(
                        "Failed to generate section %s with AI, using fallback: %s",
                        section_type,
                        e,
                    )
                    self.audit_logger.log_error(section_type, e, context)
                    
                    # Use fallback
                    fallback_content = self.fallback_handler.get_fallback_section(
                        section_type, context
                    )
                    sections[section_type] = fallback_content
                    fallback_used = True

            generation_time = time.time() - start_time

            # Log generation audit
            validation_result = ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                corrected=False,
                corrected_fields=[],
            )

            self.audit_logger.log_generation(
                request=request,
                model_used=model_used,
                generation_time_seconds=generation_time,
                token_usage={"total_tokens": sum(total_token_usage.values())},
                validation_result=validation_result,
                fallback_used=fallback_used,
                sections_generated=sections_generated,
                report_id=report_id,
            )

            logger.info(
                "AI report generation completed in %.2fs, sections=%s, fallback=%s",
                generation_time,
                sections_generated,
                fallback_used,
            )

            return {
                "sections": sections,
                "context": context,
                "metadata": {
                    "generation_time_seconds": generation_time,
                    "model_used": model_used,
                    "token_usage": total_token_usage,
                    "fallback_used": fallback_used,
                    "sections_generated": sections_generated,
                },
            }

        except Exception as e:
            logger.error("AI report generation failed completely: %s", e, exc_info=True)
            
            # Complete fallback
            context = self.context_builder.build(request.dict())
            all_fallback = self.fallback_handler.get_fallback_for_all_sections(context)
            
            return {
                "sections": all_fallback,
                "context": context,
                "metadata": {
                    "generation_time_seconds": time.time() - start_time,
                    "model_used": "fallback",
                    "token_usage": {},
                    "fallback_used": True,
                    "sections_generated": [],
                    "error": str(e),
                },
            }

    def _generate_single_section(
        self,
        section_type: str,
        context: Dict[str, Any],
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Generate a single report section using LLM.

        Args:
            section_type: Type of section to generate
            context: Financial context
            language: Language code

        Returns:
            Dictionary with content and metadata
        """
        start_time = time.time()

        # Build prompt based on section type
        user_prompt = self._build_prompt_for_section(section_type, context, language)
        system_prompt = build_report_system_prompt(language)

        # Get intent for model selection
        intent = SECTION_TO_INTENT.get(section_type, "financial_analysis")
        max_tokens = SECTION_MAX_TOKENS.get(section_type, 800)

        # Call existing LLM manager (non-streaming for reports)
        try:
            result = generate_answer(
                prompt=user_prompt,
                max_tokens=max_tokens,
                intent=intent,
                context=str(context),
            )

            # Validate output
            parsed_output, validation_result = self.validators.validate_and_parse(
                result["answer"], context, section_type
            )

            if not validation_result.is_valid:
                logger.warning(
                    "Validation failed for %s, attempting correction: %s",
                    section_type,
                    validation_result.errors,
                )

                # Try correction
                correction_prompt = get_correction_prompt(
                    str(validation_result.errors), language
                )
                correction_result = generate_answer(
                    prompt=correction_prompt,
                    max_tokens=max_tokens,
                    intent=intent,
                    context=str(context),
                )

                parsed_output, validation_result = self.validators.validate_and_parse(
                    correction_result["answer"], context, section_type
                )

                if not validation_result.is_valid:
                    logger.error("Correction also failed for %s", section_type)
                    raise ValueError(f"Validation failed after correction: {validation_result.errors}")

            generation_time = time.time() - start_time

            # Log section generation
            self.audit_logger.log_section_generation(
                section_type=section_type,
                model_used=result["model"],
                generation_time_seconds=generation_time,
                token_usage={
                    "prompt_tokens": result.get("prompt_token_estimate", 0),
                    "completion_tokens": result.get("completion_token_estimate", 0),
                    "total_tokens": result.get("total_token_estimate", 0),
                },
                validation_result=validation_result,
                fallback_used=result.get("fallback_used", False),
            )

            return {
                "content": parsed_output,
                "model": result["model"],
                "token_usage": result.get("total_token_estimate", 0),
                "validation": validation_result.dict(),
            }

        except Exception as e:
            logger.error("LLM generation failed for %s: %s", section_type, e)
            raise

    def _build_prompt_for_section(
        self,
        section_type: str,
        context: Dict[str, Any],
        language: str,
    ) -> str:
        """Build the appropriate prompt for a section type."""
        if section_type == "executive_summary":
            return build_executive_summary_prompt(context, language)
        elif section_type == "kpi_explanation":
            # Get first KPI for explanation
            kpis = context.get("kpis", {})
            if kpis:
                kpi_name = list(kpis.keys())[0]
                kpi_data = kpis[kpi_name]
                return build_kpi_explanation_prompt(kpi_name, kpi_data, language)
            return build_kpi_explanation_prompt("revenue", {}, language)
        elif section_type == "trend_analysis":
            trends = context.get("trends", {})
            if trends:
                metric_name = list(trends.keys())[0]
                trend_data = trends[metric_name]
                return build_trend_analysis_prompt(metric_name, trend_data, language)
            return build_trend_analysis_prompt("revenue", {}, language)
        elif section_type == "anomaly_explanation":
            anomalies = context.get("anomalies", {})
            return build_anomaly_explanation_prompt(anomalies, language)
        elif section_type == "recommendations":
            return build_recommendations_prompt(context, language)
        elif section_type == "financial_outlook":
            return build_financial_outlook_prompt(context, language)
        else:
            logger.warning("Unknown section type: %s", section_type)
            return build_executive_summary_prompt(context, language)

    def generate_single_section(
        self,
        section_type: str,
        request: ReportGenerationRequest,
        report_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a single report section.

        Args:
            section_type: Type of section to generate
            request: Report generation request
            report_id: Optional report ID for audit logging

        Returns:
            Dictionary with generated section
        """
        logger.info("Generating single section: %s", section_type)

        # Build context
        context = self.context_builder.build(request.dict())

        # Generate section
        try:
            section_result = self._generate_single_section(
                section_type=section_type,
                context=context,
                language=request.language,
            )

            return {
                "section_type": section_type,
                "content": section_result["content"],
                "metadata": {
                    "model": section_result["model"],
                    "token_usage": section_result["token_usage"],
                    "validation": section_result["validation"],
                },
            }

        except Exception as e:
            logger.warning("AI generation failed for %s, using fallback", section_type)
            self.audit_logger.log_error(section_type, e, context)

            fallback_content = self.fallback_handler.get_fallback_section(
                section_type, context
            )

            return {
                "section_type": section_type,
                "content": fallback_content,
                "metadata": {
                    "model": "fallback",
                    "token_usage": 0,
                    "validation": {"is_valid": True, "errors": [], "warnings": []},
                    "fallback_used": True,
                },
            }
