"""Report-specific prompts for AI report generation.

Extends the existing Copilot prompt system with specialized prompts
for financial report sections. Enforces professional financial language,
prevents hallucination, and ensures structured JSON output.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Language-specific instructions
LANGUAGE_INSTRUCTIONS = {
    "en": {
        "output_language": "English",
        "currency_format": "USD",
    },
    "fr": {
        "output_language": "French",
        "currency_format": "EUR/USD",
    },
    "ar": {
        "output_language": "Arabic",
        "currency_format": "USD/Local",
    },
}

# Base system prompt for report generation
REPORT_SYSTEM_PROMPT = """
You are a Chief Financial Officer (CFO) and Senior Financial Analyst with 20+ years of experience in financial analysis and reporting.
Your role is to analyze financial data and generate executive-level, actionable insights.

## CRITICAL RULES

1. **Use Only Provided Data**: Base your analysis exclusively on the financial context provided. Never invent, guess, or assume numbers, dates, or metrics not present in the context.

2. **No Hallucination**: Do not create financial data, KPI values, or trends that are not explicitly in the provided context. If information is missing, state that it is unavailable.

3. **CFO-Level Analysis**: Provide executive-level insights that a CFO would present to the board or stakeholders. Be concise, strategic, and financially rigorous.

4. **Structured Output**: You must respond with valid JSON matching the requested schema. Do not include markdown formatting, explanations outside the JSON, or conversational text.

5. **Specific Data References**: When referencing metrics, ALWAYS cite the specific values from the context. For example: "Revenue of $50,000 shows a 10% increase" not "Revenue increased significantly."

6. **Identify Risks and Issues**: Proactively identify financial risks, anomalies, declining trends, and data quality issues. Do not present suspicious metrics as positive results.

7. **Actionable Recommendations**: Provide specific, data-driven recommendations that reference actual numbers and context. Avoid generic advice like "review metrics."

## FINANCIAL REASONING RULES

You must detect and flag the following situations:

- **Zero or Missing Expenses**: If expenses are 0 or unavailable, state that profitability assessment is incomplete. Do not present cash margin as 100% without qualification.
- **Missing Data**: If key metrics are missing, explicitly state this limitation in your analysis.
- **Unusual KPI Values**: If KPI values appear unrealistic (e.g., 100% margins, 0% costs), flag this as potential data quality issue.
- **Declining Trends**: If metrics show declining trends, highlight this as a concern requiring attention.
- **Reconciliation Problems**: If reconciliation rates are below 95% or unreconciled invoices are high, flag this as a risk.
- **Anomaly Detection**: If anomalies are present, explain their business impact and recommended actions.

## RESPONSE FORMAT

Your response must be valid JSON only. No markdown, no explanations outside the JSON structure.
""".strip()


def build_report_system_prompt(language: str = "en") -> str:
    """
    Build the system prompt for report generation with language support.

    Args:
        language: Language code (en, fr, ar)

    Returns:
        System prompt string
    """
    lang_config = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    
    prompt = REPORT_SYSTEM_PROMPT
    
    if language != "en":
        prompt += f"\n\n## LANGUAGE\nGenerate all content in {lang_config['output_language']}."
    
    return prompt


def build_executive_summary_prompt(context: Dict[str, str], language: str = "en") -> str:
    """
    Build prompt for executive summary generation.

    Args:
        context: Financial context dictionary
        language: Language code

    Returns:
        User prompt string
    """
    lang_config = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    
    # Extract key metrics for emphasis
    kpis = context.get("kpis", {})
    anomalies = context.get("anomalies", {})
    
    # Build metric emphasis section
    metric_emphasis = []
    if kpis:
        for kpi_name, kpi_data in kpis.items():
            if isinstance(kpi_data, dict):
                value = kpi_data.get("value", "N/A")
                trend = kpi_data.get("trend", "stable")
                metric_emphasis.append(f"- {kpi_name}: {value} (trend: {trend})")
    
    # Build anomaly emphasis
    anomaly_emphasis = ""
    if anomalies:
        anomaly_count = anomalies.get("total_count", 0)
        high_severity = anomalies.get("high_severity_count", 0)
        if anomaly_count > 0:
            anomaly_emphasis = f"WARNING: {anomaly_count} anomalies detected ({high_severity} high severity)"
    
    prompt = f"""Generate a CFO-level executive summary for the financial report.

## Report Context
- Report Type: {context.get('report_type', 'N/A')}
- Period: {context.get('period', {}).get('from', 'N/A')} to {context.get('period', {}).get('to', 'N/A')}
- Language: {lang_config['output_language']}

## Key Metrics (MUST reference these specific values in your summary)
{chr(10).join(metric_emphasis) if metric_emphasis else "No KPI data available"}

## Risk Indicators
{anomaly_emphasis if anomaly_emphasis else "No anomalies detected"}

## Complete Financial Data
{format_context_for_prompt(context)}

## Executive Summary Requirements

Your summary MUST:
1. Reference actual KPI values with specific numbers (e.g., "Revenue of $50,000")
2. Mention trends and their business implications
3. Highlight any risks, anomalies, or declining trends
4. Identify data quality issues if present
5. Avoid generic statements like "comprehensive analysis"
6. Be specific and data-driven

## Required JSON Output
{{
  "summary": "2-3 sentences that reference actual KPI values, trends, and key findings. Must mention specific numbers from the data.",
  "key_highlights": [
    "3-5 bullet points with specific metrics and values",
    "Include both positive findings and concerns",
    "Reference actual numbers from the provided data"
  ],
  "overall_assessment": "Overall financial health assessment (positive/neutral/negative) with specific justification based on the metrics"
}}

Remember: You are writing for executives. Be specific, cite actual numbers, and identify real risks. Do not use generic filler text."""
    
    return prompt


def build_kpi_explanation_prompt(kpi_name: str, kpi_data: Dict, language: str = "en") -> str:
    """
    Build prompt for KPI explanation generation.

    Args:
        kpi_name: Name of the KPI
        kpi_data: KPI data dictionary
        language: Language code

    Returns:
        User prompt string
    """
    lang_config = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    
    prompt = f"""Explain the KPI: {kpi_name}

## KPI Data
{format_dict_for_prompt(kpi_data)}

## Required JSON Output
{{
  "kpi_name": "{kpi_name}",
  "value": "Current value with unit from the data",
  "explanation": "Clear explanation of what this KPI measures and why it matters",
  "trend": "Trend assessment: improving, stable, or declining based on the data",
  "comparison": "Comparison with previous period if available, otherwise null"
}}

Explain this KPI in business terms. What does it indicate about financial health?"""
    
    return prompt


def build_trend_analysis_prompt(metric_name: str, trend_data: Dict, language: str = "en") -> str:
    """
    Build prompt for trend analysis generation.

    Args:
        metric_name: Name of the metric
        trend_data: Trend data dictionary
        language: Language code

    Returns:
        User prompt string
    """
    lang_config = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    
    prompt = f"""Analyze the trend for: {metric_name}

## Trend Data
{format_dict_for_prompt(trend_data)}

## Required JSON Output
{{
  "metric_name": "{metric_name}",
  "trend_description": "Description of the observed trend",
  "pattern": "Pattern identified: upward, downward, cyclical, or stable",
  "key_drivers": ["2-4 potential drivers of this trend based on the data"],
  "forecast": "Short-term forecast if data supports it, otherwise null"
}}

Identify the pattern and explain what might be driving it based on the data provided."""
    
    return prompt


def build_anomaly_explanation_prompt(anomaly_data: Dict, language: str = "en") -> str:
    """
    Build prompt for anomaly explanation generation.

    Args:
        anomaly_data: Anomaly data dictionary
        language: Language code

    Returns:
        User prompt string
    """
    lang_config = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    
    prompt = f"""Explain the anomalies detected in the financial data.

## Anomaly Data
{format_dict_for_prompt(anomaly_data)}

## Required JSON Output
{{
  "anomaly_type": "Type of anomalies (e.g., duplicate payments, missing payments)",
  "count": "Total number of anomalies",
  "explanation": "What these anomalies indicate about the financial processes",
  "potential_causes": ["2-3 potential causes based on the data"],
  "recommended_actions": ["2-3 specific actions to address these anomalies"]
}}

Focus on the business impact and actionable next steps."""
    
    return prompt


def build_recommendations_prompt(context: Dict[str, str], language: str = "en") -> str:
    """
    Build prompt for recommendations generation.

    Args:
        context: Financial context dictionary
        language: Language code

    Returns:
        User prompt string
    """
    lang_config = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    
    business_objectives = context.get("business_objectives", [])
    objectives_text = "\n".join(f"- {obj}" for obj in business_objectives) if business_objectives else "None specified"
    
    # Extract specific data points for recommendation context
    kpis = context.get("kpis", {})
    anomalies = context.get("anomalies", {})
    trends = context.get("trends", {})
    
    # Build specific data context
    specific_context = []
    
    # KPI-specific recommendations
    if kpis:
        for kpi_name, kpi_data in kpis.items():
            if isinstance(kpi_data, dict):
                value = kpi_data.get("value", "N/A")
                trend = kpi_data.get("trend", "stable")
                if trend == "declining":
                    specific_context.append(f"- {kpi_name} is DECLINING (current: {value}) - requires investigation")
                elif trend == "improving":
                    specific_context.append(f"- {kpi_name} is IMPROVING (current: {value}) - consider optimizing further")
    
    # Anomaly-specific recommendations
    if anomalies:
        anomaly_count = anomalies.get("total_count", 0)
        if anomaly_count > 0:
            specific_context.append(f"- {anomaly_count} anomalies detected - requires investigation")
        high_severity = anomalies.get("high_severity_count", 0)
        if high_severity > 0:
            specific_context.append(f"- {high_severity} HIGH SEVERITY anomalies - urgent attention needed")
    
    # Reconciliation-specific recommendations
    if "kpis" in kpis:
        rec_rate = kpis.get("reconciliation_rate", {}).get("value", 0)
        if isinstance(rec_rate, (int, float)) and rec_rate < 95:
            specific_context.append(f"- Reconciliation rate is {rec_rate}% (below 95% threshold) - investigate unreconciled invoices")
    
    prompt = f"""Generate data-driven, actionable financial recommendations.

## Report Context
- Report Type: {context.get('report_type', 'N/A')}
- Period: {context.get('period', {}).get('from', 'N/A')} to {context.get('period', {}).get('to', 'N/A')}

## Business Objectives
{objectives_text}

## Specific Issues Identified (MUST address these in your recommendations)
{chr(10).join(specific_context) if specific_context else "No specific issues identified from data"}

## Complete Financial Data
{format_context_for_prompt(context)}

## Recommendation Requirements

Each recommendation MUST:
1. Reference specific numbers from the data (e.g., "reconciliation rate is 89.8%")
2. Be actionable and specific (not generic like "review metrics")
3. Address the actual issues identified above
4. Include the business impact
5. Provide clear priority based on data severity

## Examples of GOOD recommendations:
- "The reconciliation rate is 89.8%, with 102 unreconciled invoices. Investigate unmatched transactions before month closing to ensure accurate financial reporting."
- "Revenue declined by 15% compared to previous period. Analyze customer payment patterns and identify causes of revenue reduction."
- "High severity anomalies detected in payment processing. Review payment validation rules and implement additional controls."

## Examples of BAD recommendations (DO NOT use):
- "Review key metrics regularly"
- "Investigate anomalies"
- "Monitor trends"
- "Improve financial processes"

## Required JSON Output
{{
  "recommendations": [
    {{
      "action": "Specific action referencing actual numbers (e.g., 'Investigate 102 unreconciled invoices')",
      "reason": "Why this is important based on the specific data (e.g., 'Reconciliation rate of 89.8% is below 95% threshold')",
      "priority": "Priority level: low, medium, high, or urgent - based on data severity",
      "estimated_impact": "Expected impact with specific metrics if possible"
    }}
  ]
}}

Generate 3-5 prioritized recommendations. Each MUST reference actual numbers from the provided data."""
    
    return prompt


def build_financial_outlook_prompt(context: Dict[str, str], language: str = "en") -> str:
    """
    Build prompt for financial outlook generation.

    Args:
        context: Financial context dictionary
        language: Language code

    Returns:
        User prompt string
    """
    lang_config = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])
    
    prompt = f"""Generate a financial outlook based on the current data.

## Report Context
- Report Type: {context.get('report_type', 'N/A')}
- Period: {context.get('period', {}).get('from', 'N/A')} to {context.get('period', {}).get('to', 'N/A')}

## Financial Data
{format_context_for_prompt(context)}

## Required JSON Output
{{
  "outlook": "Overall outlook: positive, neutral, or negative",
  "short_term_forecast": "Forecast for next 1-3 months based on current trends",
  "long_term_forecast": "Forecast for next 6-12 months based on current trends",
  "key_opportunities": ["2-3 opportunities identified from the data"],
  "key_risks": ["2-3 risks identified from the data"]
}}

Base your outlook on the trends and patterns in the provided data. Be realistic and data-driven."""
    
    return prompt


def build_cash_flow_analysis_prompt(context: Dict[str, str], language: str = "en") -> str:
    """
    Build prompt for cash flow analysis insights.

    Args:
        context: Financial context dictionary (contains cash_flow KPIs)
        language: Language code

    Returns:
        User prompt string
    """
    lang_config = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])

    # Extract cash flow KPI data
    kpis = context.get("kpis", {}) if isinstance(context, dict) else {}
    cash_flow = {}
    if isinstance(kpis, dict):
        cash_flow = kpis.get("cash_flow", {})
        if not cash_flow:
            # Try direct cash_flow key from context (e.g. totals passed directly)
            for key in ("cash_flow", "cash_flow_data"):
                if isinstance(context.get(key), dict):
                    cash_flow = context[key]
                    break

    # Fallback: search for known cash flow fields anywhere in the context
    total_inflows = None
    total_outflows = None
    net_cash_flow = None
    if isinstance(cash_flow, dict):
        total_inflows = cash_flow.get("total_inflows")
        total_outflows = cash_flow.get("total_outflows")
        net_cash_flow = cash_flow.get("net_cash_flow")

    if total_inflows is None:
        # Search the top-level context for direct values
        total_inflows = context.get("total_inflows") if isinstance(context, dict) else None
        total_outflows = context.get("total_outflows") if isinstance(context, dict) else None
        net_cash_flow = context.get("net_cash_flow") if isinstance(context, dict) else None

    prompt = f"""You are a financial analyst specializing in cash flow analysis.

Analyze the cash flow position of the company based on the following data.

## Cash Flow Data
- Total Inflows: {total_inflows if total_inflows is not None else 'N/A'}
- Total Outflows: {total_outflows if total_outflows is not None else 'N/A'}
- Net Cash Flow: {net_cash_flow if net_cash_flow is not None else 'N/A'}

## Full Financial Context
{format_context_for_prompt(context) if isinstance(context, dict) else context}

## Analysis Requirements

Provide a professional cash flow analysis that includes:
1. **Important observations** about the cash flow position
2. **Potential risks** based on the inflow/outflow pattern
3. **Business interpretation** of what the numbers mean
4. **Recommendations** for maintaining or improving liquidity

Keep the answer concise and professional. Respond in {lang_config['output_language']}.

## Required Format
Respond with a plain-text analysis (no JSON) organized under these headings:
- Observations
- Risks
- Interpretation
- Recommendations"""

    return prompt


def format_context_for_prompt(context: Dict[str, str]) -> str:
    """Format context dictionary for prompt inclusion."""
    parts = []
    
    if "kpis" in context:
        parts.append("### Key Performance Indicators")
        parts.append(format_dict_for_prompt(context["kpis"]))
    
    if "trends" in context:
        parts.append("### Trends")
        parts.append(format_dict_for_prompt(context["trends"]))
    
    if "anomalies" in context:
        parts.append("### Anomalies")
        parts.append(format_dict_for_prompt(context["anomalies"]))
    
    if "charts" in context:
        parts.append("### Chart Data")
        parts.append(format_dict_for_prompt(context["charts"]))
    
    return "\n\n".join(parts) if parts else "No financial data provided"


def format_dict_for_prompt(data: Dict) -> str:
    """Format dictionary for prompt inclusion."""
    if not data:
        return "No data available"
    
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {sub_value}")
        elif isinstance(value, list):
            lines.append(f"{key}: {', '.join(str(v) for v in value[:5])}")
        else:
            lines.append(f"{key}: {value}")
    
    return "\n".join(lines)


def get_correction_prompt(original_error: str, language: str = "en") -> str:
    """
    Build a correction prompt for when validation fails.

    Args:
        original_error: The validation error message
        language: Language code

    Returns:
        Correction prompt string
    """
    return f"""Your previous response failed validation. Please correct it.

## Validation Error
{original_error}

## Correction Instructions
- Fix the specific error mentioned above
- Ensure your response is valid JSON
- Use only the financial data provided in the original context
- Do not invent or hallucinate any values

Please provide the corrected JSON response only."""
