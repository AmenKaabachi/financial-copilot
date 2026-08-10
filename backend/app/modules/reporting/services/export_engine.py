import logging
import io
import os
import uuid
import tempfile
import time
import hashlib
import json
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import requests
import pandas as pd
from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Image
)
import pprint

from app.modules.reporting.services.analytics_service import AnalyticsService
from app.modules.reporting.services.report_data_resolver import ReportDataResolver
from app.modules.reporting.analytics.component_registry import (
    get_component_by_id,
    get_all_components,
)
from app.modules.reporting.services.chart_renderer import (
    ChartRenderer,
    MATPLOTLIB_AVAILABLE,
)
from app.modules.reporting.services.ai_insight_service import AIInsightService
from app.modules.reporting.services.report_localization import ReportLocalization

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KPI display labels and formatting (now localized via ReportLocalization)
# ---------------------------------------------------------------------------
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

TECHNICAL_COLUMN_PATTERNS = {"uuid", "created_at", "updated_at", "metadata", "internal_id", "invoice_uuid"}

SECTION_WEIGHTS: Dict[str, int] = {
    "text": 1,
    "title": 1,
    "kpi": 1,
    "financial_summary": 2,
    "table": 2,
    "pivot": 2,
    "image": 2,
    "chart": 3,
    "trend": 3,
    "heatmap": 3,
    "recommendation": 2,
    "ai_insight": 5,
    "divider": 1,
    "page_break": 1,
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


def _get_kpi_label(key: str, language: str = "en") -> str:
    """Get a localized human-readable label for a KPI key."""
    return ReportLocalization.kpi_label(key, language)


def _parse_date_range(config: Dict[str, Any], report_context: Optional[Dict[str, Any]] = None) -> tuple:
    """Extract date_from/date_to from section config with report-level period fallback."""
    report_context = report_context or {}
    date_from = (
        config.get("date_from")
        or config.get("period_start")
        or config.get("analytics_params", {}).get("date_from")
        or report_context.get("period_start")
        or report_context.get("date_from")
    )
    date_to = (
        config.get("date_to")
        or config.get("period_end")
        or config.get("analytics_params", {}).get("date_to")
        or report_context.get("period_end")
        or report_context.get("date_to")
    )
    return date_from, date_to


def _normalize_language(language: Optional[str]) -> str:
    if not language:
        return "en"
    key = str(language).strip().lower()
    return {
        "en": "en",
        "english": "en",
        "fr": "fr",
        "french": "fr",
        "ar": "ar",
        "arabic": "ar",
    }.get(key, "en")


def _localize(label_key: str, language: str = "en") -> str:
    """Localize a label using the ReportLocalization service."""
    return ReportLocalization.summary_label(label_key, language)


class ExportEngine:
    """Section-based rendering engine for financial reports.

    Architecture:
        AnalyticsService (provides computed data)
            ↓
        ExportEngine (renders sections)
            ↓
        ReportLab PDF
    """

    _chart_cache: Dict[str, str] = {}

    @staticmethod
    def generate_export_file(
        report_data: Dict[str, Any],
        format_type: str = "pdf",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Optional[str]:
        """Generates a file based on report data and returns the local file path."""
        try:
            filename = f"Report_{uuid.uuid4().hex[:8]}.{format_type}"
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)
            logger.info(f"[EXPORT] Generating {format_type} export to path: {file_path}")

            if progress_callback:
                progress_callback(0, "[PROGRESS] Initializing export")

            if format_type.lower() == "pdf":
                ExportEngine._generate_pdf(report_data, file_path, progress_callback)
            elif format_type.lower() in ("xls", "xlsx", "excel"):
                if progress_callback:
                    progress_callback(50, "[PROGRESS] Building spreadsheet")
                ExportEngine._generate_excel(report_data, file_path)
                if progress_callback:
                    progress_callback(100, "[PROGRESS] Completed")
            elif format_type.lower() == "csv":
                if progress_callback:
                    progress_callback(50, "[PROGRESS] Building CSV")
                ExportEngine._generate_csv(report_data, file_path)
                if progress_callback:
                    progress_callback(100, "[PROGRESS] Completed")
            else:
                logger.error(f"[EXPORT] Unsupported export format: {format_type}")
                return None

            if os.path.exists(file_path):
                logger.info(f"[EXPORT] File successfully generated and exists at: {file_path}")
                if progress_callback:
                    progress_callback(100, "[PROGRESS] Completed")
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
    def _generate_pdf(
        report_data: Dict[str, Any],
        file_path: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ):
        """Generate a PDF by rendering each section in the report definition."""
        start_time = time.time()

        # Reduced margins for expanded printable page width (0.2 inch side margins)
        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            leftMargin=0.2 * inch,
            rightMargin=0.2 * inch,
            topMargin=0.4 * inch,
            bottomMargin=0.4 * inch,
        )

        styles = getSampleStyleSheet()
        story = []
        temp_images: List[str] = []

        title_style = styles['Title']
        normal_style = styles['Normal']

        report_name = report_data.get('name', 'Financial Report')
        story.append(Paragraph(report_name, title_style))
        story.append(Spacer(1, 12))

        if report_data.get('description'):
            story.append(Paragraph(report_data.get('description'), normal_style))
            story.append(Spacer(1, 12))

        definition = report_data.get('definition', {})
        report_context = definition.get("report_context") or report_data.get("report_context") or {}
        language = _normalize_language(report_context.get("language"))
        period_start = report_context.get("period_start") or report_context.get("date_from")
        period_end = report_context.get("period_end") or report_context.get("date_to")
        if period_start or period_end:
            if period_start and period_end:
                period_text = f"{period_start} - {period_end}"
            else:
                period_text = period_start or period_end
            story.append(Paragraph(f"<b>{_localize('reporting_period', language)}:</b> {period_text}", normal_style))
            story.append(Spacer(1, 10))
        sections = definition.get('sections', []) or report_data.get('sections', [])

        if not sections:
            logger.warning("[PDF] No sections found in report definition")
            story.append(Paragraph(f"<i>{_localize('no_sections', language)}</i>", normal_style))
            doc.build(story)
            return

        logger.info(f"[PDF] Rendering {len(sections)} sections (printable width: {doc.width:.2f}pt)")

        if progress_callback:
            progress_callback(10, "[PROGRESS] 10% - Resolving report sections")

        # Explicit Work-Unit Progress Calculation
        total_units = sum(SECTION_WEIGHTS.get(s.get('type', 'text'), 1) for s in sections) or 1
        completed_units = 0

        counts = {
            "sections": len(sections),
            "charts": 0,
            "cached_charts": 0,
            "tables": 0,
            "images": 0,
            "ai_insights": 0,
            "warnings": 0,
        }

        for index, section in enumerate(sections):
            sec_type = section.get('type', 'text')

            # Render section with partial failure protection
            try:
                ExportEngine._render_section(section, story, styles, temp_images, doc, counts, report_context=report_context)
            except Exception as exc:
                counts["warnings"] += 1
                logger.error(f"[EXPORT] Failed to render section {index + 1} type='{sec_type}': {exc}", exc_info=True)
                story.append(Paragraph(f"<i>Warning: Section could not be fully rendered ({exc})</i>", normal_style))
                story.append(Spacer(1, 12))

            completed_units += SECTION_WEIGHTS.get(sec_type, 1)

            # Update progress callback dynamically
            if progress_callback:
                progress_pct = 10 + int((completed_units / total_units) * 80)
                step_name = f"Rendering section {index + 1} of {len(sections)} ({sec_type})"
                progress_callback(min(progress_pct, 90), f"[PROGRESS] {progress_pct}% - {step_name}")
                logger.info(f"[PROGRESS] {progress_pct}% - {step_name}")

        logger.info(f"[PDF] Building PDF with {len(story)} story elements...")
        if progress_callback:
            progress_callback(92, "[PROGRESS] 92% - Compiling PDF document")

        doc.build(story)

        elapsed = round(time.time() - start_time, 2)
        page_count = getattr(doc, 'page', 'N/A')

        # Structured End-of-Export Summary Log
        summary_log = (
            f"\n[EXPORT] Completed successfully\n"
            f"  Pages: {page_count}\n"
            f"  Sections: {counts['sections']}\n"
            f"  Charts: {counts['charts']} (Cached: {counts['cached_charts']})\n"
            f"  Tables: {counts['tables']}\n"
            f"  Images: {counts['images']}\n"
            f"  AI Insights: {counts['ai_insights']}\n"
            f"  Warnings: {counts['warnings']}\n"
            f"  Elapsed Time: {elapsed}s\n"
            f"  Output: {file_path}"
        )
        logger.info(summary_log)

        if progress_callback:
            progress_callback(100, "[PROGRESS] 100% - Completed")

        # Temp image cleanup
        for img_path in temp_images:
            try:
                if os.path.exists(img_path) and img_path not in ExportEngine._chart_cache.values():
                    os.remove(img_path)
                    logger.info(f"[IMAGE] Cleaned up temp image: {img_path}")
            except Exception as exc:
                logger.warning(f"[IMAGE] Failed to clean up temp image {img_path}: {exc}")

    # ------------------------------------------------------------------
    # Section Dispatcher
    # ------------------------------------------------------------------

    @staticmethod
    def _render_section(
        section: Dict[str, Any],
        story: List,
        styles,
        temp_images: Optional[List[str]] = None,
        doc: Optional[SimpleDocTemplate] = None,
        counts: Optional[Dict[str, int]] = None,
        report_context: Optional[Dict[str, Any]] = None,
    ):
        """Dispatch a single section to its appropriate render method."""
        sec_type = section.get('type', 'text')
        config = section.get('config', {})
        component_id = config.get('component_id')

        logger.info(f"[EXPORT] Rendering section type='{sec_type}' component_id='{component_id}'")

        if sec_type == 'title':
            ExportEngine._render_title(section, story, styles)
        elif sec_type == 'text':
            ExportEngine._render_text(section, story, styles)
        elif sec_type == 'financial_summary':
            if counts is not None:
                counts['tables'] += 1
            ExportEngine._render_financial_summary(section, story, styles, doc, report_context=report_context)
        elif sec_type == 'kpi':
            ExportEngine._render_kpi(section, story, styles, doc, report_context=report_context)
        elif sec_type in ('table', 'pivot'):
            if counts is not None:
                counts['tables'] += 1
            ExportEngine._render_table(section, story, styles, doc, report_context=report_context)
        elif sec_type in ('chart', 'trend', 'heatmap'):
            if counts is not None:
                counts['charts'] += 1
            ExportEngine._render_chart(section, story, styles, temp_images, doc, counts, report_context=report_context)
        elif sec_type == 'recommendation':
            ExportEngine._render_recommendation(section, story, styles, report_context=report_context)
        elif sec_type == 'ai_insight':
            if counts is not None:
                counts['ai_insights'] += 1
            ExportEngine._render_ai_insight(section, story, styles, doc, report_context=report_context)
        elif sec_type == 'divider':
            story.append(Spacer(1, 24))
        elif sec_type == 'page_break':
            story.append(PageBreak())
            logger.info("[PDF] Rendered page break")
        elif sec_type == 'image':
            if counts is not None:
                counts['images'] += 1
            ExportEngine._render_image(section, story, styles, temp_images, doc)
        else:
            logger.warning(f"[EXPORT] Unknown section type: '{sec_type}' — skipping")
            story.append(Paragraph(f"<i>Unsupported section type: {sec_type}</i>", styles['Normal']))

    # ------------------------------------------------------------------
    # Title Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_title(section: Dict[str, Any], story: List, styles):
        config = section.get('config', {})
        title = config.get('title', 'Section')
        heading_style = styles['Heading2']
        story.append(Paragraph(title, heading_style))
        story.append(Spacer(1, 6))
        logger.info(f"[EXPORT] Rendered title: '{title}'")

    # ------------------------------------------------------------------
    # Text Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_text(section: Dict[str, Any], story: List, styles):
        config = section.get('config', {})
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
    # Image Section
    # ------------------------------------------------------------------

    @staticmethod
    def _download_image(source: str) -> Optional[str]:
        """Download an image from a URL or verify a local filesystem path."""
        if not source:
            logger.warning("[IMAGE] Image section has no source URL or path — skipping")
            return None

        logger.info(f"[IMAGE] Downloading or reading image source: {source[:100]}")

        # Handle file:// scheme or local paths
        if source.startswith("file://"):
            local_path = source[7:]
            if local_path.startswith("/") and len(local_path) > 2 and local_path[2] == ":":
                local_path = local_path[1:]
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                logger.info(f"[IMAGE] Local image verified at path: {local_path}")
                return local_path
            else:
                logger.warning(f"[IMAGE] Failed: local image file not found or empty at {local_path}")
                return None

        if os.path.exists(source) and os.path.getsize(source) > 0:
            logger.info(f"[IMAGE] Local image verified at path: {source}")
            return source

        # Handle remote HTTP / HTTPS URLs
        if source.startswith("http://") or source.startswith("https://"):
            try:
                headers = {"User-Agent": "Mozilla/5.0 (AI Financial Copilot Report Generator)"}
                logger.info(f"[IMAGE] Downloading {source[:100]}")
                response = requests.get(source, headers=headers, timeout=15, stream=True)
                logger.info(f"[IMAGE] Status: {response.status_code}")
                response.raise_for_status()

                content_type = response.headers.get('content-type', '')
                logger.info(f"[IMAGE] Content-Type: {content_type}")

                ext = 'png'
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = 'jpg'
                elif 'gif' in content_type:
                    ext = 'gif'
                elif 'webp' in content_type:
                    ext = 'webp'

                temp_path = os.path.join(tempfile.gettempdir(), f"image_{uuid.uuid4().hex[:8]}.{ext}")
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                    file_size = os.path.getsize(temp_path)
                    logger.info(f"[IMAGE] Saved to {temp_path} ({file_size} bytes)")
                    logger.info("[IMAGE] Successfully embedded into PDF")
                    return temp_path

                logger.warning(f"[IMAGE] Failed: downloaded file is empty at {temp_path}")
                return None

            except requests.exceptions.RequestException as exc:
                logger.warning(f"[IMAGE] Failed: reason: HTTP request exception: {exc}")
                return None
            except Exception as exc:
                logger.warning(f"[IMAGE] Failed: reason: {exc}")
                return None

        logger.warning(f"[IMAGE] Failed: unsupported image source format: {source}")
        return None

    @staticmethod
    def _render_image(
        section: Dict[str, Any],
        story: List,
        styles,
        temp_images: Optional[List[str]] = None,
        doc: Optional[SimpleDocTemplate] = None,
    ):
        """Render an external or local image section into the PDF with aspect ratio preservation."""
        config = section.get('config', {})
        source = config.get('url') or config.get('path') or config.get('source', '')
        caption = config.get('caption') or config.get('title') or config.get('alt')

        if not source:
            logger.warning("[IMAGE] Image section has no source URL/path — rendering placeholder")
            story.append(Paragraph("<i>Image unavailable</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        image_path = ExportEngine._download_image(source)

        if not image_path:
            logger.warning("[IMAGE] Image download/resolution failed — rendering 'Image unavailable' placeholder")
            story.append(Paragraph("<i>Image unavailable</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        try:
            with PILImage.open(image_path) as pil_img:
                orig_w, orig_h = pil_img.size

            avail_w = doc.width if doc else (7.5 * inch)
            avail_h = (doc.height * 0.45) if doc else (4.5 * inch)

            # Compute aspect ratio scaling dynamically
            scale = min(avail_w / float(orig_w), avail_h / float(orig_h), 1.0)
            draw_w = orig_w * scale
            draw_h = orig_h * scale

            img = Image(image_path, width=draw_w, height=draw_h)

            # Center horizontally by placing inside a centered table wrapper
            container_table = Table([[img]], colWidths=[avail_w])
            container_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))

            elements = [container_table]
            if caption:
                caption_style = ParagraphStyle(
                    'ImageCaption',
                    parent=styles['Normal'],
                    fontSize=8.5,
                    leading=11,
                    textColor=colors.HexColor('#64748B'),
                    alignment=1,  # Center alignment
                )
                elements.append(Spacer(1, 4))
                elements.append(Paragraph(f"<i>{caption}</i>", caption_style))

            elements.append(Spacer(1, 12))
            story.append(KeepTogether(elements))
            logger.info(f"[IMAGE] Embedded image into PDF: {draw_w:.1f}x{draw_h:.1f}pt")

            if temp_images is not None and image_path not in temp_images:
                temp_images.append(image_path)
        except Exception as exc:
            logger.warning(f"[IMAGE] Failed to embed image in PDF: {exc}")
            story.append(Paragraph("<i>Image unavailable</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Financial Summary Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_financial_summary(
        section: Dict[str, Any],
        story: List,
        styles,
        doc: Optional[SimpleDocTemplate] = None,
        report_context: Optional[Dict[str, Any]] = None,
    ):
        config = section.get('config', {})
        logger.info("[TABLE] Rendering financial_summary section — fetching all KPIs")
        date_from, date_to = _parse_date_range(config, report_context)
        language = _normalize_language((report_context or {}).get("language"))
        all_kpis = AnalyticsService.get_all_kpis(date_from=date_from, date_to=date_to)
        logger.info(f"[TABLE] Financial summary data received: {len(all_kpis)} KPI groups")

        if not all_kpis:
            story.append(Paragraph(f"<i>{ReportLocalization.summary_label('financial_data_unavailable', language)}</i>", styles['Normal']))
            return

        heading_style = styles['Heading2']
        metric_label = ReportLocalization.summary_label("metric", language)
        value_label = ReportLocalization.summary_label("value", language)

        revenue = all_kpis.get("revenue", {})
        if revenue:
            story.append(Paragraph(ReportLocalization.summary_label("revenue_summary", language), heading_style))
            data = [
                [metric_label, value_label],
                [ReportLocalization.kpi_label("total_revenue", language), _format_kpi_value("total_revenue", revenue.get("total_revenue"))],
                [ReportLocalization.kpi_label("collected_revenue", language), _format_kpi_value("collected_revenue", revenue.get("collected_revenue"))],
                [ReportLocalization.kpi_label("outstanding_revenue", language), _format_kpi_value("outstanding_revenue", revenue.get("outstanding_revenue"))],
                [ReportLocalization.kpi_label("paid_invoice_count", language), _format_kpi_value("paid_invoice_count", revenue.get("paid_invoice_count"))],
                [ReportLocalization.kpi_label("unpaid_invoice_count", language), _format_kpi_value("unpaid_invoice_count", revenue.get("unpaid_invoice_count"))],
            ]
            ExportEngine._add_styled_table(data, story, doc=doc)
            story.append(Spacer(1, 12))

        expenses = all_kpis.get("expenses", {})
        if expenses:
            story.append(Paragraph(ReportLocalization.summary_label("expenses_summary", language), heading_style))
            data = [
                [metric_label, value_label],
                [ReportLocalization.kpi_label("total_expenses", language), _format_kpi_value("total_expenses", expenses.get("total_expenses"))],
                [ReportLocalization.kpi_label("expense_count", language), _format_kpi_value("expense_count", expenses.get("expense_count"))],
            ]
            ExportEngine._add_styled_table(data, story, doc=doc)
            story.append(Spacer(1, 12))

        cash_flow = all_kpis.get("cash_flow", {})
        if cash_flow:
            story.append(Paragraph(ReportLocalization.summary_label("cash_flow_summary", language), heading_style))
            data = [
                [metric_label, value_label],
                [ReportLocalization.kpi_label("total_inflows", language), _format_kpi_value("total_inflows", cash_flow.get("total_inflows"))],
                [ReportLocalization.kpi_label("total_outflows", language), _format_kpi_value("total_outflows", cash_flow.get("total_outflows"))],
                [ReportLocalization.kpi_label("net_cash_flow", language), _format_kpi_value("net_cash_flow", cash_flow.get("net_cash_flow"))],
            ]
            ExportEngine._add_styled_table(data, story, doc=doc)
            story.append(Spacer(1, 12))

        reconciliation = all_kpis.get("reconciliation_rate", {})
        if reconciliation:
            story.append(Paragraph(ReportLocalization.summary_label("reconciliation_summary", language), heading_style))
            data = [
                [metric_label, value_label],
                [ReportLocalization.kpi_label("reconciliation_rate", language), _format_kpi_value("reconciliation_rate", reconciliation.get("reconciliation_rate"))],
                [ReportLocalization.kpi_label("total_invoices", language), _format_kpi_value("total_invoices", reconciliation.get("total_invoices"))],
                [ReportLocalization.kpi_label("reconciled_count", language), _format_kpi_value("reconciled_count", reconciliation.get("reconciled_count"))],
                [ReportLocalization.kpi_label("unreconciled_count", language), _format_kpi_value("unreconciled_count", reconciliation.get("unreconciled_count"))],
            ]
            ExportEngine._add_styled_table(data, story, doc=doc)
            story.append(Spacer(1, 12))

        logger.info("[TABLE] Financial summary rendered successfully")

    # ------------------------------------------------------------------
    # KPI Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_kpi(
        section: Dict[str, Any],
        story: List,
        styles,
        doc: Optional[SimpleDocTemplate] = None,
        report_context: Optional[Dict[str, Any]] = None,
    ):
        config = section.get('config', {})
        date_from, date_to = _parse_date_range(config, report_context)
        language = _normalize_language((report_context or {}).get("language"))

        resolved_data = ReportDataResolver.resolve(section, date_from, date_to)

        if "error" in resolved_data:
            logger.warning(f"[EXPORT] KPI resolution failed: {resolved_data['error']}")
            story.append(Paragraph(f"<i>{resolved_data['error']}</i>", styles['Normal']))
            return

        title = resolved_data.get("title", config.get("title", "KPI"))
        data = resolved_data.get("data", {})

        logger.info(f"[EXPORT] Rendering KPI: {title} with data: {data}")

        if not data:
            story.append(Paragraph(f"<i>No KPI data for {title}</i>", styles['Normal']))
            return

        table_data = [
            [ReportLocalization.summary_label("metric", language), ReportLocalization.summary_label("value", language)]
        ]
        for key, value in data.items():
            if isinstance(value, (int, float)):
                table_data.append([_get_kpi_label(key, language), _format_kpi_value(key, value)])

        if len(table_data) > 1:
            story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
            ExportEngine._add_styled_table(table_data, story, doc=doc)
            story.append(Spacer(1, 12))

    # ------------------------------------------------------------------
    # Table Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_table(
        section: Dict[str, Any],
        story: List,
        styles,
        doc: Optional[SimpleDocTemplate] = None,
        report_context: Optional[Dict[str, Any]] = None,
    ):
        """Render multi-page table with technical column auto-hiding, cell wrapping, and repeat headers."""
        config = section.get('config', {})
        date_from, date_to = _parse_date_range(config, report_context)
        language = _normalize_language((report_context or {}).get("language"))

        resolved_data = ReportDataResolver.resolve(section, date_from, date_to)

        if "error" in resolved_data:
            logger.warning(f"[TABLE] Table resolution failed: {resolved_data['error']}")
            story.append(Paragraph(f"<b>{config.get('title', 'Data Table')}</b>", styles['Heading2']))
            story.append(Paragraph(f"<i>{resolved_data['error']}</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        title = resolved_data.get("title", config.get("title", "Data Table"))
        rows = resolved_data.get("data", [])
        total_rows = len(rows) if isinstance(rows, list) else 0

        # Apply configured row limit (e.g. config["limit"] = 20)
        limit = config.get("limit")
        if limit and isinstance(rows, list):
            rows = rows[:limit]

        logger.info(f"[TABLE] Rendering table: '{title}' with {len(rows)} rows (total available: {total_rows})")

        if not rows:
            story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
            story.append(Paragraph(f"<i>{ReportLocalization.summary_label('no_data', language)}</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        if isinstance(rows, list) and len(rows) > 0:
            show_tech = config.get("show_technical_columns", False)
            vis_cols = config.get("visible_columns")

            # Collect all column keys from the rows
            all_keys: List[str] = []
            for row in rows:
                for key in row.keys():
                    if key not in all_keys:
                        all_keys.append(key)

            # Column Selection Rules
            if vis_cols and isinstance(vis_cols, list):
                display_keys = [k for k in vis_cols if k in all_keys]
                if not display_keys:
                    display_keys = all_keys[:10]
            elif show_tech:
                display_keys = all_keys[:12]
            else:
                # Default: Filter out technical UUID / internal metadata fields
                display_keys = []
                for key in all_keys:
                    k_lower = key.lower()
                    is_tech = any(pat in k_lower for pat in TECHNICAL_COLUMN_PATTERNS)
                    if not is_tech:
                        display_keys.append(key)
                if not display_keys:
                    display_keys = all_keys[:8]

            # Localize table headers
            headers = [ReportLocalization.field_label(key, language) for key in display_keys]

            # Cell styles with automatic text wrapping
            cell_style_left = ParagraphStyle(
                'TableCellLeft',
                parent=styles['Normal'],
                fontSize=8.5,
                leading=10.5,
                textColor=colors.HexColor('#1E293B'),
            )
            cell_style_right = ParagraphStyle(
                'TableCellRight',
                parent=cell_style_left,
                alignment=2,  # Right align
            )
            cell_style_center = ParagraphStyle(
                'TableCellCenter',
                parent=cell_style_left,
                alignment=1,  # Center align
            )
            header_style = ParagraphStyle(
                'TableHeaderCell',
                parent=styles['Normal'],
                fontSize=9,
                leading=11,
                fontName='Helvetica-Bold',
                textColor=colors.white,
            )

            header_row = [Paragraph(f"<b>{h}</b>", header_style) for h in headers]
            table_data = [header_row]

            for row in rows:
                row_data = []
                for key in display_keys:
                    val = row.get(key, "")
                    if val is None:
                        formatted_val = ""
                    elif isinstance(val, float):
                        formatted_val = f"${val:,.2f}" if any(c in key.lower() for c in ("amount", "price", "revenue", "expense", "cost", "total")) else f"{val:,.2f}"
                    else:
                        formatted_val = str(val)

                    k_low = key.lower()
                    if any(c in k_low for c in ("amount", "price", "revenue", "expense", "cost", "total", "volume")):
                        row_data.append(Paragraph(formatted_val, cell_style_right))
                    elif any(c in k_low for c in ("status", "date", "due", "created", "count", "id")):
                        row_data.append(Paragraph(formatted_val, cell_style_center))
                    else:
                        row_data.append(Paragraph(formatted_val, cell_style_left))

                table_data.append(row_data)

            story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))

            avail_w = doc.width if doc else (7.5 * inch)
            col_count = len(display_keys)
            col_widths = [avail_w / float(col_count)] * col_count if col_count > 0 else None

            # Multi-Page Table with Pagination and Repeating Headers
            t = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ]))

            for i in range(1, len(table_data)):
                bg = colors.HexColor('#FFFFFF') if i % 2 == 1 else colors.HexColor('#F8FAFC')
                t.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), bg)]))

            story.append(t)
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<i>{ReportLocalization.showing_records(len(rows), total_rows, language)}</i>",
                styles['Normal']
            ))
            story.append(Spacer(1, 12))
            logger.info(f"[TABLE] Table rendered successfully: {len(table_data)-1} rows, {len(display_keys)} columns")

    # ------------------------------------------------------------------
    # Chart Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_chart(
        section: Dict[str, Any],
        story: List,
        styles,
        temp_images: Optional[List[str]] = None,
        doc: Optional[SimpleDocTemplate] = None,
        counts: Optional[Dict[str, int]] = None,
        report_context: Optional[Dict[str, Any]] = None,
    ):
        config = section.get('config', {})
        date_from, date_to = _parse_date_range(config, report_context)

        resolved_data = ReportDataResolver.resolve(section, date_from, date_to)

        if "error" in resolved_data:
            logger.warning(f"[CHART] Chart resolution failed: {resolved_data['error']}")
            story.append(Paragraph(f"<b>{config.get('title', 'Chart')}</b>", styles['Heading2']))
            story.append(Paragraph(f"<i>{resolved_data['error']}</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        title = resolved_data.get("title", config.get("title", "Chart"))
        chart_data = resolved_data.get("data")

        logger.info(f"[CHART] Rendering chart: {title}")

        if not chart_data:
            story.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
            story.append(Paragraph("<i>Chart data is not available for this period.</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        chart_data = ExportEngine._apply_single_point_fallback(chart_data)

        # Temporary Chart Hash Cache
        chart_image_path = None
        chart_hash = hashlib.md5(json.dumps(chart_data, sort_keys=True, default=str).encode('utf-8')).hexdigest()

        if chart_hash in ExportEngine._chart_cache and os.path.exists(ExportEngine._chart_cache[chart_hash]):
            chart_image_path = ExportEngine._chart_cache[chart_hash]
            if counts is not None:
                counts["cached_charts"] += 1
            logger.info(f"[CHART] Reused cached chart image for hash {chart_hash[:8]}: {chart_image_path}")
        elif MATPLOTLIB_AVAILABLE:
            try:
                chart_image_path = ChartRenderer.render_chart(chart_data)
                if chart_image_path and os.path.exists(chart_image_path):
                    ExportEngine._chart_cache[chart_hash] = chart_image_path
                    logger.info(f"[CHART] Rendered and cached new chart image: {chart_image_path}")
            except Exception as exc:
                logger.error(f"[CHART] ChartRenderer.render_chart() error: {exc}", exc_info=True)
                chart_image_path = None

        if chart_image_path and os.path.exists(chart_image_path):
            try:
                avail_w = doc.width if doc else (7.5 * inch)
                draw_w = min(avail_w, 6.8 * inch)
                draw_h = draw_w * 0.52

                img = Image(chart_image_path, width=draw_w, height=draw_h)

                # Center horizontally in a 1x1 table
                chart_table = Table([[img]], colWidths=[avail_w])
                chart_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ]))

                chart_elements = [
                    Paragraph(f"<b>{title}</b>", styles['Heading2']),
                    Spacer(1, 6),
                    chart_table,
                    Spacer(1, 12),
                ]
                story.append(KeepTogether(chart_elements))
                logger.info(f"[CHART] Chart embedded in PDF: {chart_image_path}")
                if temp_images is not None and chart_image_path not in temp_images:
                    temp_images.append(chart_image_path)
            except Exception as exc:
                logger.error(f"[CHART] Failed to embed chart image in PDF: {exc}", exc_info=True)
                ExportEngine._render_chart_as_table(chart_data, story, styles, doc=doc)
        else:
            logger.warning("[CHART] Rendering chart preview data table as fallback")
            ExportEngine._render_chart_as_table(chart_data, story, styles, doc=doc)

    @staticmethod
    def _apply_single_point_fallback(chart_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a single-point line chart to a bar chart."""
        if not chart_data:
            return chart_data

        chart_type = chart_data.get("chart_type")
        labels = chart_data.get("labels", []) or []
        datasets = chart_data.get("datasets", []) or []

        is_line = chart_type == "line"
        has_single_point = len(labels) <= 1 or any(
            len(ds.get("data", []) or []) <= 1 for ds in datasets
        )

        if is_line and has_single_point:
            logger.info("[CHART] Single-point line chart detected — overriding chart_type to 'bar'")
            chart_data = dict(chart_data)
            chart_data["chart_type"] = "bar"

        return chart_data

    @staticmethod
    def _render_chart_as_table(chart_data: Dict[str, Any], story: List, styles, doc: Optional[SimpleDocTemplate] = None):
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
        story.append(Paragraph(f"<i>Chart type: {chart_type_label} (data table preview)</i>", styles['Normal']))
        ExportEngine._add_styled_table(table_data, story, doc=doc)
        logger.info(f"[CHART] Chart rendered as data table preview ({len(table_data)-1} rows)")

    # ------------------------------------------------------------------
    # Recommendation Section
    # ------------------------------------------------------------------

    @staticmethod
    def _render_recommendation(
        section: Dict[str, Any],
        story: List,
        styles,
        report_context: Optional[Dict[str, Any]] = None,
    ):
        config = section.get('config', {})
        language = _normalize_language((report_context or {}).get("language"))
        content = config.get('content', '')
        recommendations = config.get('recommendations', [])
        if not content and not recommendations:
            logger.warning("[EXPORT] Recommendation section has no content — skipping")
            return
        normal_style = styles['Normal']
        heading_style = styles['Heading2']
        story.append(Paragraph(_localize("recommendations", language), heading_style))
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
    def _render_ai_insight(
        section: Dict[str, Any],
        story: List,
        styles,
        doc: Optional[SimpleDocTemplate] = None,
        report_context: Optional[Dict[str, Any]] = None,
    ):
        """Render AI Insights inside an executive styled callout box with Markdown heading parsing."""
        config = section.get('config', {})
        effective_context = report_context or {}
        language = _normalize_language(effective_context.get("language") or config.get("language"))
        content = config.get('content', '')
        insight_type = config.get('insight_type') or config.get('topic', 'trend_analysis')

        is_placeholder = (
            not content
            or "AI insight will be generated" in str(content)
            or "will be generated" in str(content)
        )

        if is_placeholder:
            try:
                logger.info(f"[AI] Generating AI insight with insight_type='{insight_type}'")
                generated = AIInsightService.generate(section, report_context=effective_context)
                if generated:
                    content = generated
                    logger.info(f"[AI] AI insight generated ({len(generated)} chars)")
                else:
                    logger.warning("[AI] AI insight generation returned empty content")
                    content = None
            except Exception as exc:
                logger.error(f"[AI] AI insight generation failed: {exc}", exc_info=True)
                content = None

        if not content:
            story.append(Paragraph(f"<b>{_localize('ai_insights', language)}</b>", styles['Heading2']))
            story.append(Paragraph(f"<i>{_localize('ai_unavailable', language)}</i>", styles['Normal']))
            story.append(Spacer(1, 12))
            return

        avail_w = doc.width if doc else (7.5 * inch)
        box_elements = []

        h2_style = ParagraphStyle(
            'AIHeader',
            parent=styles['Heading2'],
            fontSize=11.5,
            leading=14.5,
            textColor=colors.HexColor('#1E3A8A'),
            spaceAfter=4,
        )
        h3_style = ParagraphStyle(
            'AISubHeader',
            parent=styles['Heading3'],
            fontSize=9.5,
            leading=12.5,
            textColor=colors.HexColor('#1D4ED8'),
            spaceBefore=5,
            spaceAfter=2,
        )
        body_style = ParagraphStyle(
            'AIBody',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor('#1F2937'),
        )

        box_elements.append(Paragraph(f"<b>{_localize('ai_financial_insights', language)}</b>", h2_style))
        box_elements.append(Spacer(1, 4))

        # Markdown Line Parser for Executive Section Formatting
        lines = content.split('\n')
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("### "):
                box_elements.append(Paragraph(f"<b>{stripped[4:]}</b>", h3_style))
            elif stripped.startswith("## "):
                box_elements.append(Paragraph(f"<b>{stripped[3:]}</b>", h3_style))
            elif stripped.startswith("# "):
                box_elements.append(Paragraph(f"<b>{stripped[2:]}</b>", h3_style))
            elif stripped.startswith("• ") or stripped.startswith("* ") or stripped.startswith("- "):
                box_elements.append(Paragraph(f"• {stripped[2:]}", body_style))
            else:
                box_elements.append(Paragraph(stripped, body_style))

        box_table = Table([[box_elements]], colWidths=[avail_w])
        box_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0F9FF')),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEBEFORE', (0, 0), (0, 0), 3.5, colors.HexColor('#2563EB')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#BAE6FD')),
        ]))

        story.append(box_table)
        story.append(Spacer(1, 12))
        logger.info(f"[AI] Rendered AI insight callout box ({len(content)} chars)")

    # ------------------------------------------------------------------
    # Shared Table Styling
    # ------------------------------------------------------------------

    @staticmethod
    def _add_styled_table(
        data: List[List[str]],
        story: List,
        col_widths: Optional[List[float]] = None,
        doc: Optional[SimpleDocTemplate] = None,
    ):
        if not data or len(data) < 2:
            return

        avail_w = doc.width if doc else (7.5 * inch)
        col_count = len(data[0])

        if col_widths is None:
            col_widths = [avail_w / float(col_count)] * col_count if col_count > 0 else None

        t = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9.5),
            ('FONTSIZE', (0, 1), (-1, -1), 8.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        for i in range(1, len(data)):
            bg = colors.HexColor('#FFFFFF') if i % 2 == 1 else colors.HexColor('#F8FAFC')
            t.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), bg)]))
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
                # Respect the configured limit (config["limit"]) instead of hard-coding 100
                table_limit = config.get("limit", 50)
                if component_id:
                    preview = AnalyticsService.get_component_preview(component_id, {"limit": table_limit})
                    if preview and preview.get("data"):
                        rows = preview["data"]
                        if isinstance(rows, list):
                            for row in rows[:table_limit]:
                                row_copy = {"Section": "Table"}
                                for k, v in row.items():
                                    row_copy[str(k)] = str(v)[:100] if v is not None else ""
                                data.append(row_copy)
                elif config.get("data_source"):
                    rows = AnalyticsService.get_table_data(config["data_source"], limit=table_limit)
                    for row in rows[:table_limit]:
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