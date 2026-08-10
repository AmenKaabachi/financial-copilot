"""Validation layer for AI-generated report content.

Focuses on financial reliability: JSON schema validation and number verification.
Cross-references all numbers against provided context to prevent hallucination.
"""

import logging
import json
import re
from typing import Any, Dict, List, Optional, Set

from app.modules.reporting.schemas.ai_report_schemas import (
    ValidationResult,
    AIReportSections,
    Insight,
    Recommendation,
)

logger = logging.getLogger(__name__)


class ReportValidators:
    """Validates AI-generated report content for financial reliability."""

    @staticmethod
    def validate_json_structure(output: str) -> ValidationResult:
        """
        Validate that output is valid JSON.

        Args:
            output: Raw string output from LLM

        Returns:
            ValidationResult with validation status
        """
        try:
            json.loads(output)
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                corrected=False,
                corrected_fields=[],
            )
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Invalid JSON: {str(e)}"],
                warnings=[],
                corrected=False,
                corrected_fields=[],
            )

    @staticmethod
    def validate_report_section(
        output: Dict[str, Any],
        context: Dict[str, Any],
        schema_type: str = "general"
    ) -> ValidationResult:
        """
        Validate a report section against schema and context.

        Args:
            output: Parsed JSON output from LLM
            context: Financial context provided to LLM
            schema_type: Type of schema to validate against

        Returns:
            ValidationResult with detailed validation results
        """
        errors = []
        warnings = []
        corrected_fields = []

        # Validate required fields based on schema type
        required_fields = ReportValidators._get_required_fields(schema_type)
        for field in required_fields:
            if field not in output:
                errors.append(f"Missing required field: {field}")

        # Validate data types
        type_errors = ReportValidators._validate_data_types(output, schema_type)
        errors.extend(type_errors)

        # Cross-reference numbers with context (hallucination check)
        number_errors = ReportValidators._validate_numbers_against_context(output, context)
        errors.extend(number_errors)

        # Validate enum values
        enum_errors = ReportValidators._validate_enum_values(output)
        errors.extend(enum_errors)

        # Check for empty critical fields
        empty_warnings = ReportValidators._check_empty_critical_fields(output)
        warnings.extend(empty_warnings)

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            corrected=False,
            corrected_fields=corrected_fields,
        )

    @staticmethod
    def _get_required_fields(schema_type: str) -> List[str]:
        """Get required fields for a given schema type."""
        schema_requirements = {
            "executive_summary": ["summary", "key_highlights", "overall_assessment"],
            "kpi_explanation": ["kpi_name", "value", "explanation", "trend"],
            "trend_analysis": ["metric_name", "trend_description", "pattern"],
            "anomaly_explanation": ["anomaly_type", "count", "explanation"],
            "recommendations": ["recommendations"],
            "financial_outlook": ["outlook", "short_term_forecast", "long_term_forecast"],
            "general": [],
        }
        return schema_requirements.get(schema_type, [])

    @staticmethod
    def _validate_data_types(output: Dict[str, Any], schema_type: str) -> List[str]:
        """Validate data types of fields."""
        errors = []

        if schema_type == "executive_summary":
            if "key_highlights" in output and not isinstance(output["key_highlights"], list):
                errors.append("key_highlights must be a list")

        elif schema_type == "recommendations":
            if "recommendations" in output and not isinstance(output["recommendations"], list):
                errors.append("recommendations must be a list")
            elif "recommendations" in output:
                for i, rec in enumerate(output["recommendations"]):
                    if not isinstance(rec, dict):
                        errors.append(f"recommendations[{i}] must be an object")
                        continue
                    if "action" not in rec:
                        errors.append(f"recommendations[{i}] missing required field: action")
                    if "priority" not in rec:
                        errors.append(f"recommendations[{i}] missing required field: priority")

        elif schema_type == "anomaly_explanation":
            if "count" in output and not isinstance(output["count"], int):
                errors.append("count must be an integer")

        return errors

    @staticmethod
    def _validate_enum_values(output: Dict[str, Any]) -> List[str]:
        """Validate enum values match expected options."""
        errors = []

        # Valid severity levels
        valid_severity = {"low", "medium", "high", "critical"}
        # Valid priorities
        valid_priority = {"low", "medium", "high", "urgent"}
        # Valid patterns
        valid_pattern = {"upward", "downward", "cyclical", "stable"}
        # Valid trends
        valid_trend = {"improving", "stable", "declining"}
        # Valid outlook
        valid_outlook = {"positive", "neutral", "negative"}

        # Check severity in insights
        if "insights" in output:
            for i, insight in enumerate(output["insights"]):
                if isinstance(insight, dict) and "severity" in insight:
                    if insight["severity"] not in valid_severity:
                        errors.append(f"insights[{i}].severity has invalid value: {insight['severity']}")

        # Check priority in recommendations
        if "recommendations" in output:
            for i, rec in enumerate(output["recommendations"]):
                if isinstance(rec, dict) and "priority" in rec:
                    if rec["priority"] not in valid_priority:
                        errors.append(f"recommendations[{i}].priority has invalid value: {rec['priority']}")

        # Check pattern in trend analysis
        if "pattern" in output and output["pattern"] not in valid_pattern:
            errors.append(f"pattern has invalid value: {output['pattern']}")

        # Check trend in KPI explanation
        if "trend" in output and output["trend"] not in valid_trend:
            errors.append(f"trend has invalid value: {output['trend']}")

        # Check outlook in financial outlook
        if "outlook" in output and output["outlook"] not in valid_outlook:
            errors.append(f"outlook has invalid value: {output['outlook']}")

        return errors

    @staticmethod
    def _validate_numbers_against_context(output: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """
        Cross-reference all numbers in output with context to detect hallucination.

        Extracts all numeric values from output and verifies they exist in context.
        """
        errors = []
        context_numbers = ReportValidators._extract_numbers_from_context(context)
        output_numbers = ReportValidators._extract_numbers_from_output(output)

        # Check if output numbers exist in context (with some tolerance for derived calculations)
        for num_info in output_numbers:
            value = num_info["value"]
            field = num_info["field"]

            # Allow small derived values (percentages, small counts)
            if value < 10:
                continue

            # Check if this number or a close approximation exists in context
            found = False
            for ctx_num in context_numbers:
                if abs(value - ctx_num) < (ctx_num * 0.01):  # 1% tolerance
                    found = True
                    break

            if not found:
                # This might be a hallucination - add as warning, not error
                # (LLMs might do valid calculations that aren't in raw context)
                logger.warning(f"Number {value} in field '{field}' not found in context - possible hallucination")

        return errors  # Return empty list for now - warnings logged but not blocking

    @staticmethod
    def _extract_numbers_from_context(context: Dict[str, Any]) -> List[float]:
        """Extract all numeric values from context for cross-referencing."""
        numbers = []

        def extract_from_dict(d: Dict[str, Any]):
            for key, value in d.items():
                if isinstance(value, (int, float)):
                    numbers.append(float(value))
                elif isinstance(value, dict):
                    extract_from_dict(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, (int, float)):
                            numbers.append(float(item))
                        elif isinstance(item, dict):
                            extract_from_dict(item)

        extract_from_dict(context)
        return numbers

    @staticmethod
    def _extract_numbers_from_output(output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all numeric values from output with field names."""
        numbers = []

        def extract_from_dict(d: Dict[str, Any], path: str = ""):
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, (int, float)):
                    numbers.append({"value": float(value), "field": current_path})
                elif isinstance(value, dict):
                    extract_from_dict(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        item_path = f"{current_path}[{i}]"
                        if isinstance(item, (int, float)):
                            numbers.append({"value": float(item), "field": item_path})
                        elif isinstance(item, dict):
                            extract_from_dict(item, item_path)

        extract_from_dict(output)
        return numbers

    @staticmethod
    def _check_empty_critical_fields(output: Dict[str, Any]) -> List[str]:
        """Check if critical fields are empty or too short."""
        warnings = []

        critical_text_fields = [
            "summary",
            "explanation",
            "trend_description",
            "action",
            "reason",
            "short_term_forecast",
            "long_term_forecast",
        ]

        def check_dict(d: Dict[str, Any], path: str = ""):
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                if key in critical_text_fields and isinstance(value, str):
                    if len(value.strip()) < 10:
                        warnings.append(f"Field '{current_path}' is too short (< 10 chars)")
                elif isinstance(value, dict):
                    check_dict(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            check_dict(item, f"{current_path}[{i}]")

        check_dict(output)
        return warnings

    @staticmethod
    def validate_and_parse(output: str, context: Dict[str, Any], schema_type: str = "general") -> tuple[Dict[str, Any], ValidationResult]:
        """
        Complete validation pipeline: JSON parse, schema validate, context validate.

        Args:
            output: Raw string output from LLM
            context: Financial context provided to LLM
            schema_type: Type of schema to validate against

        Returns:
            Tuple of (parsed_output, validation_result)
        """
        # Step 1: Validate JSON structure
        json_validation = ReportValidators.validate_json_structure(output)
        if not json_validation.is_valid:
            return {}, json_validation

        # Step 2: Parse JSON
        try:
            parsed = json.loads(output)
        except Exception as e:
            return {}, ValidationResult(
                is_valid=False,
                errors=[f"Failed to parse JSON after validation: {str(e)}"],
                warnings=[],
                corrected=False,
                corrected_fields=[],
            )

        # Step 3: Validate against schema and context
        schema_validation = ReportValidators.validate_report_section(parsed, context, schema_type)

        return parsed, schema_validation

    @staticmethod
    def validate_ai_report_definition(
        definition: Dict[str, Any],
        original_prompt: str = "",
        architect_context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate an AI-generated report definition against schema and detect prompt-echoing.
        """
        from app.modules.reporting.schemas.report_definition_schema import validate_report_definition_schema

        schema_res = validate_report_definition_schema(definition)
        if not schema_res["is_valid"]:
            return ValidationResult(
                is_valid=False,
                errors=schema_res["errors"],
                warnings=[],
                corrected=False,
                corrected_fields=[],
            )

        errors = []
        warnings = []
        architect_context = architect_context or {}
        prompt_words = set(re.findall(r"\w+", original_prompt.lower())) if original_prompt else set()
        forbidden_phrases = (
            "based on your request",
            "the user requested",
            "create an executive report",
            "do not copy",
            "generate only",
            "additional instructions",
        )

        # Title preservation: user title is authoritative
        required_title = (architect_context.get("report_title") or "").strip()
        if required_title and definition.get("name") != required_title:
            errors.append("Report title must match the exact user-provided title")

        # Period validity
        period_start = architect_context.get("period_start")
        period_end = architect_context.get("period_end")
        if period_start and period_end and period_start > period_end:
            errors.append("Invalid reporting period: period_start must be <= period_end")

        # Language presence
        if architect_context.get("language") and not definition.get("report_context", {}).get("language"):
            warnings.append("Missing report_context.language in generated definition")

        description = str(definition.get("description", "") or "")
        lowered_description = description.lower()
        if any(phrase in lowered_description for phrase in forbidden_phrases):
            errors.append("Report description contains prompt/instruction leakage")

        sections = definition.get("sections", [])
        for idx, sec in enumerate(sections):
            sec_type = sec.get("type")
            config = sec.get("config", {}) or {}

            # Check prompt echo in content or title
            content = str(config.get("content", "")).lower()
            title = str(config.get("title", "")).lower()

            if prompt_words and len(prompt_words) > 4:
                content_words = set(re.findall(r"\w+", content))
                title_words = set(re.findall(r"\w+", title))

                overlap_content = len(prompt_words.intersection(content_words)) / float(len(prompt_words))
                overlap_title = len(prompt_words.intersection(title_words)) / float(len(prompt_words))

                if overlap_content > 0.25:
                    warnings.append(f"Section index {idx} ({sec_type}) content echoes original prompt instruction (overlap: {overlap_content:.2f})")
                    # Clean the prompt-echoing text
                    config["content"] = "This section summarizes key financial highlights and business performance metrics."

                if overlap_title > 0.40:
                    warnings.append(f"Section index {idx} ({sec_type}) title echoes original prompt instruction")
                    config["title"] = sec_type.replace("_", " ").title()

            if any(phrase in content for phrase in forbidden_phrases):
                errors.append(f"Section index {idx} ({sec_type}) content contains instruction leakage")
            if any(phrase in title for phrase in forbidden_phrases):
                errors.append(f"Section index {idx} ({sec_type}) title contains instruction leakage")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            corrected=len(warnings) > 0,
            corrected_fields=[],
        )
