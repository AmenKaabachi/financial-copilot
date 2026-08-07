"""Report Definition Schema and Section Validation rules.

Strictly enforces valid section types and report structure for the AI Report Builder.
"""

import logging
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

ALLOWED_SECTION_TYPES: Set[str] = {
    "title",
    "text",
    "kpi",
    "chart",
    "table",
    "ai_insight",
    "page_break",
    "image",
    "recommendation",
    "trend",
    "pivot",
    "heatmap",
    "financial_summary",
}


def validate_report_definition_schema(definition: Dict[str, Any]) -> Dict[str, Any]:
    """Validate raw report definition against strict schema rules.

    Returns dict: {"is_valid": bool, "errors": List[str]}
    """
    errors: List[str] = []

    if not isinstance(definition, dict):
        return {"is_valid": False, "errors": ["Report definition must be a dictionary"]}

    sections = definition.get("sections")
    if sections is None:
        # Check if sections is top-level in payload
        if isinstance(definition.get("sections"), list):
            sections = definition["sections"]
        else:
            errors.append("Report definition is missing required 'sections' list")
            return {"is_valid": False, "errors": errors}

    if not isinstance(sections, list):
        errors.append("'sections' must be a list")
        return {"is_valid": False, "errors": errors}

    for idx, sec in enumerate(sections):
        if not isinstance(sec, dict):
            errors.append(f"Section index {idx} is not an object")
            continue

        sec_type = sec.get("type")
        if not sec_type:
            errors.append(f"Section index {idx} is missing required 'type' field")
            continue

        if sec_type not in ALLOWED_SECTION_TYPES:
            errors.append(
                f"Section index {idx} has invalid section type '{sec_type}'. "
                f"Allowed types: {sorted(list(ALLOWED_SECTION_TYPES))}"
            )

        config = sec.get("config")
        if config is not None and not isinstance(config, dict):
            errors.append(f"Section index {idx} ({sec_type}) 'config' must be an object")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
    }
