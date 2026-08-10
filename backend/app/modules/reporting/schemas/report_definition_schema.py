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

ALLOWED_CHART_TYPES: Set[str] = {
    "line",
    "bar",
    "grouped_bar",
    "pie",
    "donut",
    "reconciliation_trend",
    "anomaly_distribution",
    "anomaly_type",
    "transaction_volume",
    "bank_vs_erp",
    "revenue_trend",
    "cash_flow_trend",
    "payment_status",
}

ALLOWED_TABLE_SOURCES: Set[str] = {
    "erp_transactions",
    "reconciliation_records",
    "reconciliations",
    "anomaly_records",
    "anomalies",
    "expense_records",
    "bank_transactions",
}

ALLOWED_KPI_KEYS: Set[str] = {
    "revenue",
    "expenses",
    "profit",
    "cash_flow",
    "outstanding_invoices",
    "payment_delays",
    "reconciliation_rate",
    "total_transactions",
    "anomaly_stats",
    "matching_accuracy",
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
            continue

        config = config or {}
        if sec_type == "chart":
            chart_key = config.get("data_source") or config.get("chart_type")
            if not chart_key:
                errors.append(f"Section index {idx} (chart) must define config.data_source or config.chart_type")
            elif chart_key not in ALLOWED_CHART_TYPES:
                errors.append(f"Section index {idx} (chart) has unsupported chart key '{chart_key}'")

        elif sec_type == "table":
            data_source = config.get("data_source")
            if not data_source:
                errors.append(f"Section index {idx} (table) must define config.data_source")
            elif data_source not in ALLOWED_TABLE_SOURCES:
                errors.append(f"Section index {idx} (table) has unsupported data_source '{data_source}'")
            limit = config.get("limit")
            if limit is not None:
                if not isinstance(limit, int):
                    errors.append(f"Section index {idx} (table) config.limit must be an integer")
                elif limit <= 0 or limit > 200:
                    errors.append(f"Section index {idx} (table) config.limit must be between 1 and 200")

        elif sec_type == "kpi":
            kpi_key = config.get("data_source") or config.get("kpi_key")
            if not kpi_key:
                errors.append(f"Section index {idx} (kpi) must define config.data_source or config.kpi_key")
            elif kpi_key not in ALLOWED_KPI_KEYS:
                errors.append(f"Section index {idx} (kpi) has unsupported key '{kpi_key}'")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
    }
