"""Pydantic schemas for AI-generated report sections.

Defines structured output schemas for AI report generation,
ensuring consistent and validated JSON responses from LLMs.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Insight(BaseModel):
    """Individual insight in a report section."""
    title: str = Field(..., description="Title of the insight")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    explanation: str = Field(..., description="Detailed explanation of the insight")
    impact: str = Field(..., description="Business impact description")
    metrics_referenced: List[str] = Field(default_factory=list, description="KPIs or metrics referenced")


class Recommendation(BaseModel):
    """Individual recommendation in a report section."""
    action: str = Field(..., description="Recommended action to take")
    reason: str = Field(..., description="Reasoning behind the recommendation")
    priority: str = Field(..., description="Priority level: low, medium, high, urgent")
    estimated_impact: Optional[str] = Field(None, description="Estimated impact if implemented")


class ExecutiveSummarySection(BaseModel):
    """Executive summary section of a report."""
    summary: str = Field(..., description="Overall executive summary")
    key_highlights: List[str] = Field(default_factory=list, description="Key highlights from the period")
    overall_assessment: str = Field(..., description="Overall financial health assessment")


class KPIExplanationSection(BaseModel):
    """KPI explanation section."""
    kpi_name: str = Field(..., description="Name of the KPI")
    value: str = Field(..., description="Current value with unit")
    explanation: str = Field(..., description="Explanation of the KPI and its significance")
    trend: str = Field(..., description="Trend description: improving, stable, declining")
    comparison: Optional[str] = Field(None, description="Comparison with previous period")


class TrendAnalysisSection(BaseModel):
    """Trend analysis section."""
    metric_name: str = Field(..., description="Name of the metric analyzed")
    trend_description: str = Field(..., description="Description of the trend")
    pattern: str = Field(..., description="Pattern identified: upward, downward, cyclical, stable")
    key_drivers: List[str] = Field(default_factory=list, description="Key drivers of the trend")
    forecast: Optional[str] = Field(None, description="Short-term forecast if applicable")


class AnomalyExplanationSection(BaseModel):
    """Anomaly explanation section."""
    anomaly_type: str = Field(..., description="Type of anomaly")
    count: int = Field(..., description="Number of anomalies detected")
    explanation: str = Field(..., description="Explanation of the anomalies")
    potential_causes: List[str] = Field(default_factory=list, description="Potential causes")
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended actions")


class FinancialOutlookSection(BaseModel):
    """Financial outlook section."""
    outlook: str = Field(..., description="Overall financial outlook: positive, neutral, negative")
    short_term_forecast: str = Field(..., description="Short-term forecast (next 1-3 months)")
    long_term_forecast: str = Field(..., description="Long-term forecast (next 6-12 months)")
    key_opportunities: List[str] = Field(default_factory=list, description="Key opportunities identified")
    key_risks: List[str] = Field(default_factory=list, description="Key risks identified")


class AIReportSections(BaseModel):
    """Complete AI-generated report sections."""
    executive_summary: Optional[ExecutiveSummarySection] = None
    insights: List[Insight] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    kpi_explanations: List[KPIExplanationSection] = Field(default_factory=list)
    trend_analyses: List[TrendAnalysisSection] = Field(default_factory=list)
    anomaly_explanations: List[AnomalyExplanationSection] = Field(default_factory=list)
    financial_outlook: Optional[FinancialOutlookSection] = None
    language: str = Field(default="en", description="Language of the generated content")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")


class ReportGenerationRequest(BaseModel):
    """Request schema for AI report generation."""
    report_type: str = Field(..., description="Type of report: monthly_financial, quarterly_review, risk_analysis, etc.")
    date_from: Optional[str] = Field(None, description="Start date (ISO format)")
    date_to: Optional[str] = Field(None, description="End date (ISO format)")
    sections: List[str] = Field(..., description="List of section types to generate")
    language: str = Field(default="en", description="Language: en, fr, ar")
    user_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User preferences for generation")
    business_objectives: Optional[List[str]] = Field(None, description="Business objectives to focus on")
    # --- Report generation context (propagated end-to-end) ---
    period_start: Optional[str] = Field(None, description="Reporting period start (ISO format)")
    period_end: Optional[str] = Field(None, description="Reporting period end (ISO format)")
    audience: Optional[str] = Field(None, description="Target audience (e.g. CFO, Finance Team)")
    objective: Optional[str] = Field(None, description="Business objective / generation instruction")
    additional_instructions: Optional[str] = Field(None, description="Additional AI generation instructions")
    report_title: Optional[str] = Field(None, description="User-controlled report title")


class ValidationResult(BaseModel):
    """Result of validation on AI-generated content."""
    is_valid: bool = Field(..., description="Whether the content passed validation")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")
    corrected: bool = Field(default=False, description="Whether corrections were applied")
    corrected_fields: List[str] = Field(default_factory=list, description="Fields that were corrected")


class GenerationAuditLog(BaseModel):
    """Audit log entry for report generation."""
    report_id: Optional[str] = Field(None, description="Report ID if associated with a saved report")
    request: ReportGenerationRequest = Field(..., description="Generation request")
    model_used: str = Field(..., description="Model used for generation")
    generation_time_seconds: float = Field(..., description="Time taken to generate")
    token_usage: Dict[str, int] = Field(default_factory=dict, description="Token usage stats")
    validation_result: ValidationResult = Field(..., description="Validation result")
    fallback_used: bool = Field(default=False, description="Whether fallback was used")
    sections_generated: List[str] = Field(default_factory=list, description="Sections successfully generated")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")