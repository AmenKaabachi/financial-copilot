import logging
import io
import os
import uuid
import tempfile
from typing import Dict, Any, Optional, List
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Image
)

from app.modules.reporting.services.analytics_service import AnalyticsService
from app.modules.reporting.analytics.component_registry import (
    get_component_by_id,
    get_all_components,
)
from app.modules.reporting.services.chart_renderer import (
    ChartRenderer,
    MATPLOTLIB_AVAILABLE,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KPI display labels and formatting
# ---------------------------------------------------------------------------
KPI_LABELS: Dict[str, str] = {
    "total_revenue": "Total Revenue",
    "collected_revenue": "Collected Revenue",
    "outstanding_revenue": "Outstanding Revenue",
    "invoice_count": "Total Invoices",
    "paid_invoice_count": "Paid Invoices",
    "unpaid_invoice_count": "Unpaid Invoices",
    "total_expenses": "Total Expenses",
    "expense_count": "Expense Count",
    "net_cash_result": "Net Cash Result",
    "cash_margin": "Cash Margin",
    "total_inflows": "Total Inflows",
    "total_outflows": "Total Outflows",
    "net_cash_flow": "Net Cash Flow",
    "outstanding_count": "Outstanding Count",
    "total_outstanding": "Total Outstanding",
    "average_outstanding": "Average Outstanding",
    "delayed_count": "Delayed Count",
    "total_delayed_amount": "Total Delayed Amount",
    "reconciliation_rate": "Reconciliation Rate",
    "total_invoices": "Total Invoices",
    "reconciled_count": "Reconciled Count",
    "unreconciled_count": "Unreconciled Count",
    "erp_count": "ERP Count",
    "bank_count": "Bank Count",
    "total_count": "Total Count",
    "erp_volume": "ERP Volume",
    "bank_volume": "Bank Volume",
    "total_volume": "Total Volume",
    "total_anomalies": "Total Anomalies",
    "high_severity_count": "High Severity",
    "medium_severity_count": "Medium Severity",
    "low_severity_count": "Low Severity",
    "matching_accuracy": "Matching Accuracy",
    "total_reconciliations": "Total Reconciliations",
    "matched_count": "Matched Count",
    "unmatched_count": "Unmatched Count",
    "pending_count": "Pending Count",
    "partial_count": "Partial Count",
}

KPI_FORMATTERS: Dict[str, str] = {
    "total_revenue": "currency",
    "collected_revenue": "currency",
    "outstanding_revenue": "currency",
    "total_expenses": "currency",
    "net_cash_result": "currency",
    "total_inflows": "currency",
    "total_outflows": "currency",
    "net_cash_flow": "currency",
    "total_outstanding": "currency",
    "average_outstanding": "currency",
    "total_delayed_amount": "currency",
    "erp_volume": "currency",
    "bank_volume": "currency",
    "total_volume": "currency",
    "reconciliation_rate": "percent",
    "matching_accuracy": "percent",
    "cash_margin": "percent",
    "invoice_count": "integer",
    "paid_invoice_count": "integer",
    "unpaid_invoice_count": "integer",
    "expense_count": "integer",
    "outstanding_count": "integer",
    "delayed_count": "integer",
    "total_invoices": "integer",
    "reconciled_count": "integer",
    "unreconciled_count": "integer",
    "erp_count": "integer",
    "bank_count": "integer",
    "total_count": "integer",
    "total_anomalies": "integer",
    "high_severity_count": "integer",
    "medium_severity_count": "integer",
    "low_severity_count": "integer",
    "total_reconciliations": "integer",
    "matched_count": "integer",
    "unmatched_count": "integer",
    "pending_count": "integer",
    "partial_count": "integer",
}


def _format_kpi_value(key: str, value: Any) -> str:
    """Format a KPI value according to its type."""
    if value is None:
        return "N/A"
    fmt = KPI_FORMATTERS.get(key, "auto")
    try:
        if fmt == "currency":
            return f"${value:,.2f}"
        elif fmt == "percent":
            return f"{value:.2f}%"
        elif fmt == "integer":
            return f"{int(value):,}"
        else:
            if isinstance(value, float):
                return f"{value:,.2f}"
            return str(value)
    except (ValueError, TypeError):
        return str(value)


def _get_kpi_label(key: str) -> str:
    """Get a human-readable label for a KPI key."""
    return KPI_LABELS.get(key, key.replace("_", " ").title())


def _get_component_name(component_id: str) -> str:
    """Look up the human-readable name for a component ID."""
    comp = get_component_by_id(component_id)
    if comp:
        return comp.get("name", component_id)
    return component_id.replace("_", " ").title()


def _parse_date_range(config: Dict[str, Any]) -> tuple:
    """Extract date_from and date_to from a section config."""
    date_from = config.get("date_from") or config.get("analytics_params", {}).get("date_from")
    date_to = config.get("date_to") or config.get("analytics_params", {}).get("date_to")
    return date_from, date_to


class ExportEngine:
    """Section-based rendering engine for financial reports.

    Architecture:
        AnalyticsService (provides computed data)
            ↓
        ExportEngine (renders sections)
            ↓
        ReportLab PDF

    The export engine NEVER calculates business metrics itself.
    It only renders data provided by the analytics layer.
    """

    @staticmethod
    def generate_export_file(report_data: Dict[str, Any], format_type: str = "pdf") -> Optional[str]:
        """
        Generates a file based on report data and returns the local file path.
        In a production app, this might upload to S3/Supabase directly,
        but returning a path allows the storage service to handle the upload.
        """
        try:
            filename = f"Report_{uuid.uuid4().hex[:8]}.{format_type}"
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)
            logger.info(f"[EXPORT] Generating {format_type} export to path: {file_path}")

            if format_type.lower() == "pdf":
                ExportEngine._generate_pdf(report_data, file_path)
            elif format_type.lower() in ("xls", "xlsx", "excel"):
                ExportEngine._generate_excel(report_data, file_path)
            elif format_type.lower() == "csv":
                ExportEngine._generate_csv(report_data, file_path)
            else:
                logger.error(f"[EXPORT] Unsupported export format: {format_type}")
                return None

            if os.path.exists(file_path):
                logger.info(f"[EXPORT] File successfully generated and exists at: {file_path}")
            else:
                logger.error(f"[EXPORT] File was not found at {file_path} after generation!")
                return None

            return file_path
        except Exception as e:
            logger.error(f"[EXPORT] Error generating {format_type} export: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # PDF Generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pdf(report_data: Dict[str, Any], file_path: str):
        """Generate a PDF by rendering each section in the report definition."""
        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        temp_images: List[str] = []

        title_style = styles['Title']
        normal_style = styles['Normal']
        heading_style = styles['Heading2']

        report_name = report_data.get('name', 'Financial Report')
        story.append(Paragraph(report_name, title_style))
        story.append(Spacer(1, 12))

        if report_data.get('description'):
            story.append(Paragraph(report_data.get('description'), normal_style))
            story.append(Spacer(1, 12))

        definition = report_data.get('definition', {})
        sections = definition.get('sections', []) or report_data.get('sections', [])

        if not sections:
            logger.warning("[EXPORT] No sections found in report definition")
            story.append(Paragraph("<i>No sections in this report.</i>", normal_style))
            doc.build(story)
            return

        logger.info(f"[EXPORT] Rendering {len(sections)} sections")

        for section in sections:
            ExportEngine._render_section(section, story, styles, temp_images)

        logger.info(f"[EXPORT] Building PDF with {len(story)} elements...")
        doc.build(story)
        logger.info(f"[EXPORT] PDF build completed successfully.")

        for img_path in temp_images:
            try:
                if os.path.exists(img_path):
                    os.remove(img_path)
                    logger.info(f"[EXPORT] Cleaned up temp image: {img_path}")
            except Exception as exc:
                logger.warning(f"[EXPORT] Failed to clean up temp image {img_path}: {exc}")

    # ------------------------------------------------------------------
    # Section Dispatcher
    # ------------------------------------------------------------------

    @staticmethod
    def _render_section(section: Dict[str, Any], story: List, styles, temp_images: Optional[List[str]] = None):
        """Dispatch a single section to its appropriate render method."""
        sec_type = section.get('type', 'text')
        config = section.get('config', {})
        component_id = config.get('component_id')

        logger.info(f"[EXPORT] Rendering section type='{sec_type}' component_id='{component_id}'")

        try:
            if sec_type == 'title':
                ExportEngine._render_title(config, story, styles)
            elif sec_type == 'text':
                ExportEngine._render_text(config, story, styles)
            elif sec_type == 'financial_summary':
                ExportEngine._render_financial_summary(config, story, styles)
            elif sec_type == 'kpi':
                ExportEngine._render_kpi(config, story, styles)
            elif sec_type == 'table':
                ExportEngine._render_table(config, story, styles)
            elif sec_type == 'chart':
                ExportEngine._render_chart(config, story, styles, temp_images)
            elif sec_type == 'recommendation':
                ExportEngine._render_recommendation(config, story, styles)
            elif sec_type == 'ai_insight':
                ExportEngine._render_ai_insight(config, story, styles)
            elif sec_type == 'divider':
                story.append(Spacer(1, 24))
            else:
                logger.warning(f"[EXPORT] Unknown section type: '{sec_type}' — skipping")
                story.append(Paragraph(
                    f"<i>Unsupported section type: {sec_type}</i>",
                    styles['Normal']
                ))
        except Exception as exc:
            logger.error(f"[EXPORT] Failed to render section type='{sec_type}': {exc}", exc_info=True)
            story.append(Paragraph(
                f"<i>Error rendering section: {exc}</i>",
                styles['Normal']
            ))

    # ------------------------------------------------------------------
    # Title Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_title(config: Dict[str, Any], story: List, styles):
        title = config.get('title', 'Section')
        heading_style = styles['Heading2']
        story.append(Paragraph(title, heading_style))
        story.append(Spacer(1, 6))
        logger.info(f"[EXPORT] Rendered title: '{title}'")

    # ------------------------------------------------------------------
    # Text Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_text(config: Dict[str, Any], story: List, styles):
        content = config.get('content', '')
        if not content:
            logger.warning("[EXPORT] Text section has no content — skipping")
            return
        normal_style = styles['Normal']
        content_html = content.replace('\n', '<br/>')
        story.append(Paragraph(content_html, normal_style))
        story.append(Spacer(1, 12))
        logger.info(f"[EXPORT] Rendered text section ({len(content)} chars)")

    # ------------------------------------------------------------------
    # Financial Summary Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_financial_summary(config: Dict[str, Any], story: List, styles):
        logger.info("[EXPORT] Rendering financial_summary section — fetching all KPIs")
        date_from, date_to = _parse_date_range(config)
        all_kpis = AnalyticsService.get_all_kpis(date_from=date_from, date_to=date_to)
        logger.info(f"[EXPORT] Financial summary data received: {len(all_kpis)} KPI groups")

        if not all_kpis:
            story.append(Paragraph("<i>Financial data unavailable.</i>", styles['Normal']))
            return

        normal_style = styles['Normal']
        heading_style = styles['Heading2']

        revenue = all_kpis.get("revenue", {})
        if revenue:
            story.append(Paragraph("Revenue Summary", heading_style))
            data = [
                ["Metric", "Value"],
                ["Total Revenue", _format_kpi_value("total_revenue", revenue.get("total_revenue"))],
                ["Collected Revenue", _format_kpi_value("collected_revenue", revenue.get("collected_revenue"))],
                ["Outstanding Revenue", _format_kpi_value("outstanding_revenue", revenue.get("outstanding_revenue"))],
                ["Paid Invoices", _format_kpi_value("paid_invoice_count", revenue.get("paid_invoice_count"))],
                ["Unpaid Invoices", _format_kpi_value("unpaid_invoice_count", revenue.get("unpaid_invoice_count"))],
            ]
            ExportEngine._add_styled_table(data, story)
            story.append(Spacer(1, 12))

        expenses = all_kpis.get("expenses", {})
        if expenses:
            story.append(Paragraph("Expenses Summary", heading_style))
            data = [
                ["Metric", "Value"],
                ["Total Expenses", _format_kpi_value("total_expenses", expenses.get("total_expenses"))],
                ["Expense Count", _format_kpi_value("expense_count", expenses.get("expense_count"))],
            ]
            ExportEngine._add_styled_table(data, story)
            story.append(Spacer(1, 12))

        cash_flow = all_kpis.get("cash_flow", {})
        if cash_flow:
            story.append(Paragraph("Cash Flow Summary", heading_style))
            data = [
                ["Metric", "Value"],
                ["Total Inflows", _format_kpi_value("total_inflows", cash_flow.get("total_inflows"))],
                ["Total Outflows", _format_kpi_value("total_outflows", cash_flow.get("total_outflows"))],
                ["Net Cash Flow", _format_kpi_value("net_cash_flow", cash_flow.get("net_cash_flow"))],
            ]
            ExportEngine._add_styled_table(data, story)
            story.append(Spacer(1, 12))

        reconciliation = all_kpis.get("reconciliation_rate", {})
        if reconciliation:
            story.append(Paragraph("Reconciliation Summary", heading_style))
            data = [
                ["Metric", "Value"],
                ["Reconciliation Rate", _format_kpi_value("reconciliation_rate", reconciliation.get("reconciliation_rate"))],
                ["Total Invoices", _format_kpi_value("total_invoices", reconciliation.get("total_invoices"))],
                ["Reconciled", _format_kpi_value("reconciled_count", reconciliation.get("reconciled_count"))],
                ["Unreconciled", _format_kpi_value("unreconciled_count", reconciliation.get("unreconciled_count"))],
            ]
            ExportEngine._add_styled_table(data, story)
            story.append(Spacer(1, 12))

        anomalies = all_kpis.get("anomaly_stats", {})
        if anomalies and anomalies.get("total_anomalies", 0) > 0:
            story.append(Paragraph("Anomaly Summary", heading_style))
            data = [
                ["Metric", "Value"],
                ["Total Anomalies", _format_kpi_value("total_anomalies", anomalies.get("total_anomalies"))],
                ["High Severity", _format_kpi_value("high_severity_count", anomalies.get("high_severity_count"))],
                ["Medium Severity", _format_kpi_value("medium_severity_count", anomalies.get("medium_severity_count"))],
                ["Low Severity", _format_kpi_value("low_severity_count", anomalies.get("low_severity_count"))],
            ]
            ExportEngine._add_styled_table(data, story)
            story.append(Spacer(1, 12))

        logger.info("[EXPORT] Financial summary rendered successfully")

    # ------------------------------------------------------------------
    # KPI Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_kpi(config: Dict[str, Any], story: List, styles):
        date_from, date_to = _parse_date_range(config)
        component_ids = config.get("component_ids", [])
        if not component_ids:
            cid = config.get("component_id")
            if cid:
                component_ids = [cid]
        kpi_key = config.get("kpi_key")

        if component_ids:
            logger.info(f"[EXPORT] Rendering KPI section with components: {component_ids}")
            for cid in component_ids:
                logger.info(f"[EXPORT]   Fetching data for component: {cid}")
                preview = AnalyticsService.get_component_preview(cid, {
                    "date_from": date_from,
                    "date_to": date_to,
                })
                if not preview:
                    logger.warning(f"[EXPORT]   No data returned for component: {cid}")
                    story.append(Paragraph(
                        f"<i>Data unavailable for {_get_component_name(cid)}</i>",
                        styles['Normal']
                    ))
                    continue
                data = preview.get("data", {})
                logger.info(f"[EXPORT]   Data received: {data}")
                if not data:
                    story.append(Paragraph(
                        f"<i>No KPI data for {_get_component_name(cid)}</i>",
                        styles['Normal']
                    ))
                    continue
                comp_name = _get_component_name(cid)
                table_data = [["Metric", "Value"]]
                for key, value in data.items():
                    if isinstance(value, (int, float)):
                        table_data.append([_get_kpi_label(key), _format_kpi_value(key, value)])
                if len(table_data) > 1:
                    story.append(Paragraph(f"<b>{comp_name}</b>", styles['Heading2']))
                    ExportEngine._add_styled_table(table_data, story)
                    story.append(Spacer(1, 12))
                sev_dist = data.get("severity_distribution", {})
                if sev_dist:
                    dist_data = [["Severity Level", "Count"]]
                    for level, count in sorted(sev_dist.items()):
                        dist_data.append([level.capitalize(), str(count)])
                    ExportEngine._add_styled_table(dist_data, story)
                    story.append(Spacer(1, 6))
                type_dist = data.get("type_distribution", {})
                if type_dist:
                    dist_data = [["Anomaly Type", "Count"]]
                    for atype, count in sorted(type_dist.items()):
                        dist_data.append([atype.capitalize(), str(count)])
                    ExportEngine._add_styled_table(dist_data, story)
                    story.append(Spacer(1, 12))

        elif kpi_key:
            logger.info(f"[EXPORT] Rendering single KPI: {kpi_key}")
            data = AnalyticsService.get_single_kpi(kpi_key, date_from=date_from, date_to=date_to)
            logger.info(f"[EXPORT] KPI data received: {data}")
            if not data:
                story.append(Paragraph(
                    f"<i>KPI data unavailable for '{kpi_key}'</i>",
                    styles['Normal']
                ))
                return
            table_data = [["Metric", "Value"]]
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    table_data.append([_get_kpi_label(key), _format_kpi_value(key, value)])
            if len(table_data) > 1:
                story.append(Paragraph(f"<b>{_get_kpi_label(kpi_key)}</b>", styles['Heading2']))
                ExportEngine._add_styled_table(table_data, story)
                story.append(Spacer(1, 12))
        else:
            logger.warning("[EXPORT] KPI section has no component_ids or kpi_key — skipping")
            story.append(Paragraph("<i>KPI section: no data source specified.</i>", styles['Normal']))

    # ------------------------------------------------------------------
    # Table Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_table(config: Dict[str, Any], story: List, styles):
        date_from, date_to = _parse_date_range(config)
        component_id = config.get("component_id")
        data_source = config.get("data_source") or config.get("analytics_source")
        rows = []
        title = config.get("title", "Data Table")

        if component_id:
            logger.info(f"[EXPORT] Rendering table section with component: {component_id}")
            preview = AnalyticsService.get_component_preview(component_id, {
                "date_from": date_from,
                "date_to": date_to,
                "limit": config.get("limit", 50),
            })
            logger.info(f"[EXPORT] Table data received: {preview}")
            if preview:
                data = preview.get("data", [])
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict):
                    rows = [data]
                title = _get_component_name(component_id)
            else:
                logger.warning(f"[EXPORT] No data returned for table component: {component_id}")

        elif data_source:
            logger.info(f"[EXPORT] Rendering table section with data_source: {data_source}")
            rows = AnalyticsService.get_table_data(
                data_source, date_from=date_from, date_to=date_to, limit=config.get("limit", 50),
            )
            logger.info(f"[EXPORT] Table data received: {len(rows)} rows")

        analytics_params = config.get("analytics_params", {})
        if not rows and analytics_params.get("data_source"):
            ds = analytics_params.get("data_source")
            logger.info(f"[EXPORT] Falling back to analytics_params data_source: {ds}")
            rows = AnalyticsService.get_table_data(
                ds, date_from=date_from, date_to=date_to, limit=config.get("limit", 50),
            )

        if not rows:
            logger.warning("[EXPORT] No table data available — showing fallback message")
            story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
            story.append(Paragraph("<i>No data available for this table.</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        if isinstance(rows, list) and len(rows) > 0:
            all_keys: List[str] = []
            for row in rows:
                for key in row.keys():
                    if key not in all_keys:
                        all_keys.append(key)
            display_keys = all_keys[:10]
            header = [key.replace("_", " ").title() for key in display_keys]
            table_data = [header]
            for row in rows[:50]:
                row_data = []
                for key in display_keys:
                    val = row.get(key, "")
                    if val is None:
                        val = ""
                    elif isinstance(val, float):
                        val = f"{val:,.2f}"
                    else:
                        val = str(val)
                    row_data.append(val)
                table_data.append(row_data)
            story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
            ExportEngine._add_styled_table(table_data, story, col_widths=None)
            story.append(Paragraph(
                f"<i>Showing {min(len(rows), 50)} of {len(rows)} records</i>",
                styles['Normal']
            ))
            story.append(Spacer(1, 12))
            logger.info(f"[EXPORT] Table rendered: {len(table_data)-1} rows, {len(display_keys)} columns")

    # ------------------------------------------------------------------
    # Chart Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_chart(config: Dict[str, Any], story: List, styles, temp_images: Optional[List[str]] = None):
        date_from, date_to = _parse_date_range(config)
        component_id = config.get("component_id")
        chart_type = config.get("chart_type") or config.get("analytics_params", {}).get("chart_type")
        title = config.get("title", "Chart")
        chart_data = None

        if component_id:
            logger.info(f"[EXPORT] Rendering chart section with component: {component_id}")
            preview = AnalyticsService.get_component_preview(component_id, {
                "date_from": date_from,
                "date_to": date_to,
                "bucket": config.get("bucket", "month"),
            })
            logger.info(f"[EXPORT] Chart data received: {preview}")
            if preview:
                chart_data = preview.get("data")
                title = _get_component_name(component_id)

        elif chart_type:
            logger.info(f"[EXPORT] Rendering chart section with chart_type: {chart_type}")
            chart_data = AnalyticsService.get_chart_data(
                chart_type, date_from=date_from, date_to=date_to, bucket=config.get("bucket", "month"),
            )
            logger.info(f"[EXPORT] Chart data received: {chart_data}")

        if not chart_data:
            logger.warning("[EXPORT] No chart data available — showing fallback message")
            story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
            story.append(Paragraph("<i>Chart data is not available for this period.</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        chart_image_path = None
        if MATPLOTLIB_AVAILABLE:
            try:
                chart_image_path = ChartRenderer.render_chart(chart_data)
            except Exception as exc:
                logger.warning(f"[EXPORT] Failed to render chart image: {exc}")

        story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))

        if chart_image_path and os.path.exists(chart_image_path):
            try:
                img = Image(chart_image_path, width=6.0 * inch, height=3.5 * inch)
                story.append(img)
                story.append(Spacer(1, 6))
                logger.info(f"[EXPORT] Chart image embedded: {chart_image_path}")
                if temp_images is not None:
                    temp_images.append(chart_image_path)
            except Exception as exc:
                logger.warning(f"[EXPORT] Failed to embed chart image: {exc}")
                ExportEngine._render_chart_as_table(chart_data, story, styles)
                try:
                    if os.path.exists(chart_image_path):
                        os.remove(chart_image_path)
                except Exception:
                    pass
        else:
            logger.info("[EXPORT] matplotlib not available — rendering chart as data table")
            ExportEngine._render_chart_as_table(chart_data, story, styles)

        story.append(Spacer(1, 12))

    @staticmethod
    def _render_chart_as_table(chart_data: Dict[str, Any], story: List, styles):
        labels = chart_data.get("labels", [])
        datasets = chart_data.get("datasets", [])
        if not labels or not datasets:
            story.append(Paragraph("<i>Chart data format not supported.</i>", styles['Normal']))
            return
        header = ["Period"]
        for ds in datasets:
            header.append(ds.get("label", "Value"))
        table_data = [header]
        for i, label in enumerate(labels):
            row = [str(label)]
            for ds in datasets:
                vals = ds.get("data", [])
                val = vals[i] if i < len(vals) else ""
                if isinstance(val, float):
                    val = f"{val:,.2f}"
                row.append(str(val))
            table_data.append(row)
        chart_type_label = chart_data.get("chart_type", "chart").capitalize()
        story.append(Paragraph(
            f"<i>Chart type: {chart_type_label} (data table preview)</i>",
            styles['Normal']
        ))
        ExportEngine._add_styled_table(table_data, story)
        logger.info(f"[EXPORT] Chart rendered as data table: {len(table_data)-1} data points")

    # ------------------------------------------------------------------
    # Recommendation Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_recommendation(config: Dict[str, Any], story: List, styles):
        content = config.get('content', '')
        recommendations = config.get('recommendations', [])
        if not content and not recommendations:
            logger.warning("[EXPORT] Recommendation section has no content — skipping")
            return
        normal_style = styles['Normal']
        heading_style = styles['Heading2']
        story.append(Paragraph("Recommendations", heading_style))
        if content:
            content_html = content.replace('\n', '<br/>')
            story.append(Paragraph(content_html, normal_style))
            story.append(Spacer(1, 6))
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                rec_html = f"{i}. {rec}".replace('\n', '<br/>')
                story.append(Paragraph(rec_html, normal_style))
                story.append(Spacer(1, 3))
        story.append(Spacer(1, 12))
        logger.info(f"[EXPORT] Rendered recommendation section ({len(recommendations)} items)")

    # ------------------------------------------------------------------
    # AI Insight Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_ai_insight(config: Dict[str, Any], story: List, styles):
        content = config.get('content', '')
        if not content:
            logger.warning("[EXPORT] AI insight section has no content — skipping")
            return
        normal_style = styles['Normal']
        heading_style = styles['Heading2']
        story.append(Paragraph("AI Insights", heading_style))
        content_html = content.replace('\n', '<br/>')
        story.append(Paragraph(content_html, normal_style))
        story.append(Spacer(1, 12))
        logger.info(f"[EXPORT] Rendered AI insight section ({len(content)} chars)")

    # ------------------------------------------------------------------
    # Shared Table Styling
    # ------------------------------------------------------------------

    @staticmethod
    def _add_styled_table(data: List[List[str]], story: List, col_widths: Optional[List[float]] = None):
        if not data or len(data) < 2:
            return
        if col_widths is None:
            available_width = 6.5 * inch
            col_count = len(data[0])
            if col_count <= 3:
                col_widths = [available_width * 0.4, available_width * 0.3, available_width * 0.3][:col_count]
            else:
                col_widths = [available_width / col_count] * col_count
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DEE2E6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        for i in range(1, len(data)):
            if i % 2 == 0:
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FFFFFF')),
                ]))
        story.append(t)

    # ------------------------------------------------------------------
    # Excel Generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_excel(report_data: Dict[str, Any], file_path: str):
        data = []
        definition = report_data.get('definition', {})
        sections = definition.get('sections', []) or report_data.get('sections', [])
        for section in sections:
            sec_type = section.get('type')
            config = section.get('config', {})
            component_id = config.get('component_id')
            if sec_type == 'kpi':
                if component_id:
                    preview = AnalyticsService.get_component_preview(component_id)
                    if preview and preview.get("data"):
                        kpi_data = preview["data"]
                        for key, value in kpi_data.items():
                            if isinstance(value, (int, float)):
                                data.append({
                                    "Section": "KPI",
                                    "Detail": _get_kpi_label(key),
                                    "Value": _format_kpi_value(key, value),
                                })
                elif config.get("kpi_key"):
                    kpi_data = AnalyticsService.get_single_kpi(config["kpi_key"])
                    if kpi_data:
                        for key, value in kpi_data.items():
                            if isinstance(value, (int, float)):
                                data.append({
                                    "Section": "KPI",
                                    "Detail": _get_kpi_label(key),
                                    "Value": _format_kpi_value(key, value),
                                })
            elif sec_type in ('text', 'recommendation', 'ai_insight'):
                content = config.get('content', '')
                if sec_type == 'recommendation':
                    content = "\n".join(config.get('recommendations', []))
                data.append({
                    "Section": sec_type.replace("_", " ").title(),
                    "Detail": "Content",
                    "Value": str(content)[:200],
                })
            elif sec_type == 'table':
                if component_id:
                    preview = AnalyticsService.get_component_preview(component_id)
                    if preview and preview.get("data"):
                        rows = preview["data"]
                        if isinstance(rows, list):
                            for row in rows[:100]:
                                row_copy = {"Section": "Table"}
                                for k, v in row.items():
                                    row_copy[str(k)] = str(v)[:100] if v is not None else ""
                                data.append(row_copy)
                elif config.get("data_source"):
                    rows = AnalyticsService.get_table_data(config["data_source"])
                    for row in rows[:100]:
                        row_copy = {"Section": "Table"}
                        for k, v in row.items():
                            row_copy[str(k)] = str(v)[:100] if v is not None else ""
                        data.append(row_copy)
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame([{"Report": report_data.get('name', 'Report'), "Status": "Empty"}])
        df.to_excel(file_path, index=False)
        logger.info(f"[EXPORT] Excel generated with {len(df)} rows")

    # ------------------------------------------------------------------
    # CSV Generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_csv(report_data: Dict[str, Any], file_path: str):
        rows = []
        definition = report_data.get('definition', {})
        sections = definition.get('sections', []) or report_data.get('sections', [])
        for section in sections:
            sec_type = section.get('type')
            config = section.get('config', {})
            if sec_type in ('text', 'recommendation', 'ai_insight'):
                content = config.get('content', '')
                if sec_type == 'recommendation':
                    content = "\n".join(config.get('recommendations', []))
                rows.append({
                    "Section": sec_type.replace("_", " ").title(),
                    "Content": str(content)[:200],
                })
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame([{"Report Name": report_data.get('name', 'Report')}])
        df.to_csv(file_path, index=False)
        logger.info(f"[EXPORT] CSV generated with {len(df)} rows")