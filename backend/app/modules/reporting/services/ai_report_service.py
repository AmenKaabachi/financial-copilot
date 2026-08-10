"""AI Report Service - Main orchestration for AI-powered report generation.

This service orchestrates the existing Copilot LLM infrastructure to generate
intelligent financial report sections. It does NOT duplicate AI capabilities -
it leverages the existing LLM manager, model pools, and fallback mechanisms.

Architecture:
    ReportService -> AIReportService -> Existing LLM Manager -> Generated Sections
"""

import json
import logging
import re
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

# Accept both UI labels and short language codes
LANGUAGE_CODE_MAP = {
    "english": "en",
    "en": "en",
    "french": "fr",
    "fr": "fr",
    "arabic": "ar",
    "ar": "ar",
}


def _normalize_language(language: Optional[str]) -> str:
    if not language:
        return "en"
    return LANGUAGE_CODE_MAP.get(str(language).strip().lower(), "en")


def _format_period_for_description(period_start: Optional[str], period_end: Optional[str]) -> str:
    if period_start and period_end:
        return f"{period_start} to {period_end}"
    if period_start:
        return f"from {period_start}"
    if period_end:
        return f"through {period_end}"
    return "the selected reporting period"


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

    def generate_report_definition_from_prompt(
        self,
        prompt: str,
        title: Optional[str] = None,
        architect_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Act as a Financial Reporting Architect: parse prompt into a structured JSON report definition.
        
        The user prompt is strictly an instruction for report layout/sections,
        and MUST NOT be copied into titles or text section contents.
        
        Args:
            prompt: The user's objective/instruction for the report
            title: User-controlled report title
            architect_context: Structured generation contract
            
        Returns:
            Dictionary with name, description, and sections
        """
        contract = architect_context or {}
        report_title = title or contract.get("report_title") or "Financial Report"
        language = _normalize_language(contract.get("language"))
        audience = contract.get("audience") or "Finance Team"
        period_start = contract.get("period_start")
        period_end = contract.get("period_end")
        additional_instructions = (contract.get("additional_instructions") or "").strip()
        report_type = contract.get("report_type") or "monthly_financial"

        logger.info("[AI_ARCHITECT] ====== Begin prompt-to-definition generation ======")
        logger.info("[AI_ARCHITECT] Input objective received (len=%d)", len(prompt))
        logger.info("[AI_ARCHITECT] User title: %s", report_title)

        system_prompt = (
            "You are a Senior Financial Reporting Architect.\n"
            "Transform a structured report configuration into a structured report definition.\n"
            "The user configuration is instructions and metadata, not report content.\n"
            "CRITICAL RULES:\n"
            "1. Return ONLY valid JSON.\n"
            "2. Never copy/quote user instructions or configuration into the report content.\n"
            "3. Never use instruction-oriented phrases like: 'Based on your request', 'The user requested', 'Create a report'.\n"
            "4. The report title is user-controlled and MUST NOT be rewritten.\n"
            "5. Generate all human-readable content in the requested language.\n"
            "6. Audience must control tone/detail/section depth.\n"
            "7. Reporting period controls data scope.\n"
            "8. Additional instructions influence design but must never appear verbatim.\n"
            "9. Never invent financial values.\n"
            "10. Use only these section types: 'title', 'text', 'kpi', 'chart', 'table', 'ai_insight', 'page_break', 'image', 'recommendation'.\n"
            "11. Return 4-8 sections with a professional flow.\n"
            "OUTPUT SCHEMA:\n"
            '{"description":"Short business report description","sections":[{"type":"text","config":{"title":"...","content":"..."}},{"type":"kpi","config":{"title":"...","data_source":"revenue"}}]}'
        )

        contract_payload = {
            "report_title": report_title,
            "objective": prompt,
            "audience": audience,
            "language": language,
            "period_start": period_start,
            "period_end": period_end,
            "additional_instructions": additional_instructions,
            "report_type": report_type,
            "table_limit": contract.get("table_limit"),
            "available_data_sources": [
                "erp_transactions",
                "reconciliation_records",
                "anomaly_records",
                "expense_records",
                "revenue_kpis",
                "cash_flow_kpis",
            ],
            "report_builder_capabilities": [
                "section_types: title,text,kpi,chart,table,ai_insight,recommendation,image,page_break",
                "kpi data sources are computed by analytics service",
                "charts and tables are resolved from analytics engines",
                "pdf renderer consumes structured definition + resolved data",
            ],
        }
        user_instruction = "Design a structured financial report architecture from this JSON contract:\n" + json.dumps(
            contract_payload, ensure_ascii=False
        )

        try:
            logger.info("[AI_ARCHITECT] Calling LLM generate_answer (intent=financial_analysis, max_tokens=900)")
            
            # Call with reduced max_tokens for faster JSON generation
            result = generate_answer(
                prompt=user_instruction,
                system_prompt=system_prompt,
                max_tokens=900,
                intent="financial_analysis",
            )
            
            raw_answer = result.get("answer", "").strip()
            logger.info(
                "[AI_ARCHITECT] LLM response received | model=%s | raw_answer_len=%d | fallback_used=%s | response_time=%ss",
                result.get("model", "unknown"),
                len(raw_answer),
                result.get("fallback_used", False),
                result.get("response_time", 0),
            )
            logger.info("[AI_ARCHITECT] Raw LLM answer (first 500 chars): %s", raw_answer[:500])

            # Clean JSON code fences
            fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw_answer, re.DOTALL)
            if fenced:
                raw_answer = fenced.group(1).strip()
            else:
                raw_answer = raw_answer.strip()
            logger.info("[AI_ARCHITECT] JSON code fences cleaned, raw_answer_len=%d", len(raw_answer))

            # Parse JSON
            raw_def = json.loads(raw_answer)
            
            # User title is authoritative
            name = report_title
            description = raw_def.get("description") or f"Executive financial analysis for {_format_period_for_description(period_start, period_end)}."
            raw_sections = raw_def.get("sections", [])
            
            raw_section_types = [sec.get("type") for sec in raw_sections if isinstance(sec, dict)]
            logger.info(
                "[AI_ARCHITECT] Parsed raw definition | name=%s | description=%s | raw_section_count=%d | raw_section_types=%s",
                name,
                description,
                len(raw_sections),
                raw_section_types,
            )

            # Normalize sections through SectionNormalizer
            from app.modules.reporting.services.report_section_mapper import SectionNormalizer
            norm_sections = SectionNormalizer.normalize_sections(raw_sections)
            norm_section_types = [sec.get("type") for sec in norm_sections if isinstance(sec, dict)]
            logger.info(
                "[AI_ARCHITECT] Sections normalized | count=%d | types=%s",
                len(norm_sections),
                norm_section_types,
            )

            definition = {
                "name": name,
                "description": description,
                "sections": norm_sections,
                "report_context": {
                    "report_title": report_title,
                    "objective": prompt,
                    "audience": audience,
                    "language": language,
                    "period_start": period_start,
                    "period_end": period_end,
                    "additional_instructions": additional_instructions,
                    "report_type": report_type,
                },
                "_generation": {
                    "generation_mode": "llm",
                    "ai_generated": True,
                    "fallback_used": bool(result.get("fallback_used", False)),
                    "model": result.get("model", "unknown"),
                    "response_time": result.get("response_time", 0),
                },
            }

            # Validate definition against schema and prompt echo
            val_res = self.validators.validate_ai_report_definition(
                definition,
                original_prompt=prompt,
                architect_context=contract_payload,
            )
            logger.info(
                "[AI_ARCHITECT] Definition validation | is_valid=%s | errors=%s | warnings=%s | corrected=%s",
                val_res.is_valid,
                val_res.errors,
                val_res.warnings,
                val_res.corrected,
            )
            
            if not val_res.is_valid:
                logger.warning(f"[AI_BUILDER] Validation errors found in architect definition: {val_res.errors}")
                # Try to fix common issues
                definition["name"] = report_title
                if not definition.get("sections"):
                    definition["sections"] = self._generate_heuristic_sections(prompt, language=language)

            logger.info(
                "[AI_ARCHITECT] Final definition | name=%s | description=%s | section_count=%d | section_types=%s",
                definition["name"],
                definition["description"],
                len(definition["sections"]),
                [sec.get("type") for sec in definition["sections"]],
            )
            logger.info("[AI_ARCHITECT] ====== End prompt-to-definition generation ======")
            return definition

        except json.JSONDecodeError as exc:
            logger.warning(f"[AI_BUILDER] JSON parsing failed ({exc}) — building heuristic fallback definition")
            logger.info("[AI_ARCHITECT] Building intelligent heuristic fallback from prompt keywords")
            return self._generate_intelligent_fallback(
                prompt,
                title=report_title,
                language=language,
                context=contract_payload,
                fallback_reason=f"JSON parsing failed: {exc}",
            )
            
        except Exception as exc:
            logger.warning(f"[AI_BUILDER] AI Report Architect generation failed ({exc}) — building heuristic fallback definition")
            logger.info("[AI_ARCHITECT] Building intelligent heuristic fallback from prompt keywords")
            return self._generate_intelligent_fallback(
                prompt,
                title=report_title,
                language=language,
                context=contract_payload,
                fallback_reason=str(exc),
            )

    def _generate_heuristic_sections(self, prompt: str, language: str = "en") -> List[Dict[str, Any]]:
        """Generate sections based on prompt keywords (used as fallback or enhancement)."""
        sections = []
        prompt_lower = prompt.lower()
        localized = {
            "en": {
                "executive_summary": "Executive Summary",
                "kpis": "Key Performance Indicators",
                "trends": "Performance Trends",
                "transactions": "Transaction Overview",
                "risk": "Risk Assessment & Analysis",
                "recommendations": "Strategic Recommendations",
            },
            "fr": {
                "executive_summary": "Résumé exécutif",
                "kpis": "Indicateurs clés de performance",
                "trends": "Tendances de performance",
                "transactions": "Aperçu des transactions",
                "risk": "Évaluation des risques",
                "recommendations": "Recommandations stratégiques",
            },
            "ar": {
                "executive_summary": "الملخص التنفيذي",
                "kpis": "مؤشرات الأداء الرئيسية",
                "trends": "اتجاهات الأداء",
                "transactions": "نظرة عامة على المعاملات",
                "risk": "تقييم المخاطر",
                "recommendations": "توصيات استراتيجية",
            },
        }.get(language, {})
        
        # Always include executive summary
        sections.append({
            "type": "text",
            "config": {
                "title": localized.get("executive_summary", "Executive Summary"),
                "content": "This report provides a concise financial analysis and management-oriented overview."
            }
        })
        
        # Check for KPIs/metrics
        if any(word in prompt_lower for word in ['kpi', 'metric', 'performance', 'revenue', 'sales', 'growth']):
            sections.append({
                "type": "kpi",
                "config": {"title": localized.get("kpis", "Key Performance Indicators"), "data_source": "revenue"}
            })
        
        # Check for trends/charts
        if any(word in prompt_lower for word in ['trend', 'chart', 'graph', 'visualization', 'reconciliation']):
            sections.append({
                "type": "chart",
                "config": {"title": localized.get("trends", "Performance Trends"), "chart_type": "reconciliation_trend"}
            })
        
        # Check for transactions/data
        if any(word in prompt_lower for word in ['transaction', 'erp', 'data', 'table', 'list']):
            sections.append({
                "type": "table",
                "config": {
                    "title": localized.get("transactions", "Transaction Overview"),
                    "data_source": "erp_transactions",
                    "visible_columns": ["invoice_id", "supplier", "invoice_date", "due_date", "amount", "currency", "status"],
                }
            })
        
        # Check for risk/operational
        if any(word in prompt_lower for word in ['risk', 'operational', 'compliance', 'audit']):
            sections.append({
                "type": "ai_insight",
                "config": {"title": localized.get("risk", "Risk Assessment & Analysis"), "insight_type": "financial_analysis"}
            })
        
        # Always include recommendations
        sections.append({
            "type": "recommendation",
            "config": {"title": localized.get("recommendations", "Strategic Recommendations")}
        })
        
        return sections

    def _generate_intelligent_fallback(
        self,
        prompt: str,
        title: Optional[str] = None,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None,
        fallback_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate an intelligent fallback definition based on prompt analysis."""
        sections = self._generate_heuristic_sections(prompt, language=language)
        
        # Try to extract a better title from the prompt
        if not title:
            # Look for common patterns
            title_patterns = [
                r'(?:report|analysis|review|assessment)\s+(?:on|of|for)\s+([^.]+)',
                r'([^.]+)\s+(?:report|analysis|review|assessment)',
            ]
            for pattern in title_patterns:
                match = re.search(pattern, prompt, re.IGNORECASE)
                if match:
                    title = match.group(1).strip().title()
                    break
            
            if not title:
                # Use first 50 characters of prompt as title
                title = prompt[:50].strip()
                if len(title) < 10:
                    title = "Financial Performance Report"
        
        # Normalize sections
        from app.modules.reporting.services.report_section_mapper import SectionNormalizer
        norm_sections = SectionNormalizer.normalize_sections(sections)
        
        return {
            "name": title or "Financial Performance Report",
            "description": "Executive financial analysis generated from fallback architecture.",
            "sections": norm_sections,
            "report_context": {
                "report_title": title or "Financial Performance Report",
                "objective": prompt,
                "audience": (context or {}).get("audience", "Finance Team"),
                "language": language,
                "period_start": (context or {}).get("period_start"),
                "period_end": (context or {}).get("period_end"),
                "additional_instructions": (context or {}).get("additional_instructions"),
                "report_type": (context or {}).get("report_type", "monthly_financial"),
            },
            "_generation": {
                "generation_mode": "fallback",
                "ai_generated": False,
                "fallback_used": True,
                "model": "fallback",
                "fallback_reason": fallback_reason or "AI generation failed",
            },
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
                system_prompt=system_prompt,
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
                    system_prompt=system_prompt,
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
            base_prompt = build_executive_summary_prompt(context, language)
        elif section_type == "kpi_explanation":
            # Get first KPI for explanation
            kpis = context.get("kpis", {})
            if kpis:
                kpi_name = list(kpis.keys())[0]
                kpi_data = kpis[kpi_name]
                base_prompt = build_kpi_explanation_prompt(kpi_name, kpi_data, language)
            else:
                base_prompt = build_kpi_explanation_prompt("revenue", {}, language)
        elif section_type == "trend_analysis":
            trends = context.get("trends", {})
            if trends:
                metric_name = list(trends.keys())[0]
                trend_data = trends[metric_name]
                base_prompt = build_trend_analysis_prompt(metric_name, trend_data, language)
            else:
                base_prompt = build_trend_analysis_prompt("revenue", {}, language)
        elif section_type == "anomaly_explanation":
            anomalies = context.get("anomalies", {})
            base_prompt = build_anomaly_explanation_prompt(anomalies, language)
        elif section_type == "recommendations":
            base_prompt = build_recommendations_prompt(context, language)
        elif section_type == "financial_outlook":
            base_prompt = build_financial_outlook_prompt(context, language)
        else:
            logger.warning("Unknown section type: %s", section_type)
            base_prompt = build_executive_summary_prompt(context, language)

        # Append the full generation context contract so the LLM knows the
        # audience, objective, additional instructions, and reporting period.
        # These are instructions/metadata, NOT report content — never echo them.
        period = context.get("period", {}) or {}
        period_from = period.get("from") or context.get("date_from")
        period_to = period.get("to") or context.get("date_to")
        audience = context.get("audience") or "Finance Team"
        objective = (context.get("objective") or "").strip()
        additional_instructions = (context.get("additional_instructions") or "").strip()
        report_title = context.get("report_title") or ""

        contract_parts = ["\n\nGENERATION CONTEXT (instructions, not report content):"]
        contract_parts.append(f"- Generate all content in language: {language}.")
        contract_parts.append(f"- Target audience: {audience}. Adjust tone, detail depth, KPI selection, terminology, and analytical focus accordingly.")
        if period_from or period_to:
            contract_parts.append(f"- Reporting period: {period_from} to {period_to}. Analyse data ONLY within this period unless explicitly asked for historical comparison.")
        if report_title:
            contract_parts.append(f"- Report title: {report_title}")
        if objective:
            contract_parts.append(f"- Objective: {objective}")
        if additional_instructions:
            contract_parts.append(f"- Additional instructions: {additional_instructions}")
        contract_parts.append("- Never echo instructions verbatim. Never invent financial values. Base analysis only on the provided data.")

        return base_prompt + "\n".join(contract_parts)

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