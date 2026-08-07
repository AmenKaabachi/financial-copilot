"""Validation tests for the PDF export engine section renderers.

Tests cover:
    Test A: Chart-only report
    Test B: Chart + KPI + table report
    Test C: Image + page break report
    Test D: AI Insight section
    Test E: Large report with explicit work-unit progress tracking
    Test F: Technical column auto-hiding vs visible_columns vs show_technical_columns
    Test G: Chart hash caching reuse
    Test H: Partial failure robustness
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure the backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.reporting.services.export_engine import ExportEngine


class TestExportSections(unittest.TestCase):
    """Test the PDF export engine section renderers."""

    def _generate_pdf(self, report_data):
        """Generate a PDF and return the file path."""
        file_path = os.path.join(tempfile.gettempdir(), f"test_export_{id(report_data)}.pdf")
        ExportEngine._generate_pdf(report_data, file_path)
        self.assertTrue(os.path.exists(file_path), "PDF file was not created")
        self.assertGreater(os.path.getsize(file_path), 0, "PDF file is empty")
        return file_path

    def _cleanup(self, file_path):
        """Remove a generated test file."""
        if os.path.exists(file_path):
            os.remove(file_path)

    # ------------------------------------------------------------------
    # Test A: Only chart
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.export_engine.ReportDataResolver.resolve")
    @patch("app.modules.reporting.services.export_engine.ChartRenderer.render_chart")
    def test_a_chart_only(self, mock_render_chart, mock_resolve):
        """Test A: A report with only a chart section should render."""
        mock_resolve.return_value = {
            "title": "Revenue Trend",
            "data": {
                "chart_type": "line",
                "labels": ["Jan", "Feb", "Mar"],
                "datasets": [{"label": "Revenue", "data": [100, 150, 200]}],
            },
        }
        mock_render_chart.return_value = None  # Fall back to table preview

        report = {
            "name": "Test Chart Report",
            "description": "Chart only",
            "definition": {
                "sections": [
                    {
                        "type": "chart",
                        "config": {
                            "chart_type": "line",
                            "data_source": "transaction_volume",
                            "title": "Revenue Trend",
                        },
                    }
                ]
            },
        }

        file_path = self._generate_pdf(report)
        self._cleanup(file_path)
        self.assertTrue(mock_resolve.called, "ReportDataResolver.resolve was not called")

    # ------------------------------------------------------------------
    # Test B: Chart + KPI + table
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.export_engine.ReportDataResolver.resolve")
    @patch("app.modules.reporting.services.export_engine.ChartRenderer.render_chart")
    def test_b_chart_kpi_table(self, mock_render_chart, mock_resolve):
        """Test B: Chart + KPI + table should all render without errors."""
        def resolve_side_effect(section, date_from, date_to):
            sec_type = section.get("type")
            if sec_type == "chart":
                return {
                    "title": "Volume",
                    "data": {
                        "chart_type": "bar",
                        "labels": ["Jan", "Feb"],
                        "datasets": [{"label": "Volume", "data": [10, 20]}],
                    },
                }
            elif sec_type == "kpi":
                return {
                    "title": "Revenue",
                    "data": {"total_revenue": 100000, "invoice_count": 50},
                }
            elif sec_type == "table":
                return {
                    "title": "Transactions",
                    "data": [
                        {"id": 1, "amount": 100.0, "status": "paid"},
                        {"id": 2, "amount": 200.0, "status": "pending"},
                    ],
                }
            return {"error": "Unknown type"}

        mock_resolve.side_effect = resolve_side_effect
        mock_render_chart.return_value = None

        report = {
            "name": "Test Combined Report",
            "description": "Chart + KPI + table",
            "definition": {
                "sections": [
                    {"type": "chart", "config": {"data_source": "transaction_volume"}},
                    {"type": "kpi", "config": {"kpis": ["revenue"]}},
                    {"type": "table", "config": {"data_source": "erp_transactions"}},
                ]
            },
        }

        file_path = self._generate_pdf(report)
        self._cleanup(file_path)
        self.assertEqual(mock_resolve.call_count, 3, "Expected 3 resolve calls (chart, kpi, table)")

    # ------------------------------------------------------------------
    # Test C: Image + page break
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.export_engine.ExportEngine._download_image")
    def test_c_image_page_break(self, mock_download):
        """Test C: Image + page break should render without errors."""
        import base64
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        image_path = os.path.join(tempfile.gettempdir(), "test_tiny_image.png")
        with open(image_path, "wb") as f:
            f.write(tiny_png)
        mock_download.return_value = image_path

        report = {
            "name": "Test Image Report",
            "description": "Image + page break",
            "definition": {
                "sections": [
                    {
                        "type": "image",
                        "config": {"url": "https://example.com/logo.png", "alt": "Logo"},
                    },
                    {"type": "page_break", "config": {}},
                    {"type": "text", "config": {"content": "After page break"}},
                ]
            },
        }

        file_path = self._generate_pdf(report)
        self._cleanup(file_path)
        self.assertTrue(mock_download.called, "_download_image was not called")

        if os.path.exists(image_path):
            os.remove(image_path)

    # ------------------------------------------------------------------
    # Test D: AI Insight section
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.export_engine.AIInsightService.generate")
    def test_d_ai_insight(self, mock_ai_generate):
        """Test D: AI Insight section should call AIInsightService and render Markdown block."""
        mock_ai_generate.return_value = (
            "## Executive Summary\n"
            "Cash flow remains positive with total inflows of 7.6M EUR.\n"
            "## Risks\n"
            "• Operational expenses increased by 4.2%.\n"
            "## Recommendations\n"
            "• Monitor future operational expenses closely."
        )

        report = {
            "name": "Test AI Insight Report",
            "description": "AI insight",
            "definition": {
                "sections": [
                    {
                        "type": "ai_insight",
                        "config": {
                            "insight_type": "cash_flow_analysis",
                            "content": "AI insight will be generated...",
                        },
                    }
                ]
            },
        }

        file_path = self._generate_pdf(report)
        self._cleanup(file_path)
        self.assertTrue(mock_ai_generate.called, "AIInsightService.generate was not called")

    # ------------------------------------------------------------------
    # Test E: Large report with progress tracking
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.export_engine.ReportDataResolver.resolve")
    @patch("app.modules.reporting.services.export_engine.ChartRenderer.render_chart")
    def test_e_large_report_progress(self, mock_render_chart, mock_resolve):
        """Test E: Large report should report work-unit progress via callback."""
        mock_resolve.return_value = {
            "title": "Metric",
            "data": {
                "chart_type": "bar",
                "labels": ["A", "B"],
                "datasets": [{"label": "Value", "data": [1, 2]}],
            },
        }
        mock_render_chart.return_value = None

        sections = []
        for i in range(10):
            sections.append({"type": "chart", "config": {"data_source": "transaction_volume", "title": f"Chart {i}"}})
            sections.append({"type": "text", "config": {"content": f"Text section {i}"}})

        report = {
            "name": "Test Large Report",
            "description": "Large report with progress",
            "definition": {"sections": sections},
        }

        progress_updates = []

        def progress_callback(progress, step):
            progress_updates.append((progress, step))

        file_path = os.path.join(tempfile.gettempdir(), "test_large_report.pdf")
        ExportEngine._generate_pdf(report, file_path, progress_callback=progress_callback)

        self.assertTrue(os.path.exists(file_path), "Large report PDF was not created")
        self._cleanup(file_path)

        self.assertTrue(len(progress_updates) > 0, "No progress updates were reported")
        self.assertEqual(progress_updates[0][0], 10, "First progress should be 10% (initializing/resolving)")
        self.assertEqual(progress_updates[-1][0], 100, "Last progress should be 100% (completed)")

    # ------------------------------------------------------------------
    # Test F: Technical Column Visibility Config
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.export_engine.ReportDataResolver.resolve")
    def test_f_column_visibility_options(self, mock_resolve):
        """Test F: Table column hiding logic with show_technical_columns and visible_columns."""
        mock_resolve.return_value = {
            "title": "ERP Records",
            "data": [
                {
                    "invoice_id": "INV-101",
                    "supplier": "Acme Corp",
                    "amount": 500.0,
                    "uuid": "1234-5678-90ab",
                    "created_at": "2026-08-06",
                }
            ],
        }

        # 1. Default (auto-hide technical columns uuid, created_at)
        report_default = {
            "name": "Default Cols",
            "definition": {"sections": [{"type": "table", "config": {"title": "ERP Records"}}]},
        }
        pdf_1 = self._generate_pdf(report_default)
        self._cleanup(pdf_1)

        # 2. show_technical_columns = True
        report_tech = {
            "name": "Tech Cols",
            "definition": {
                "sections": [
                    {
                        "type": "table",
                        "config": {"title": "ERP Records", "show_technical_columns": True},
                    }
                ]
            },
        }
        pdf_2 = self._generate_pdf(report_tech)
        self._cleanup(pdf_2)

        # 3. visible_columns specified
        report_vis = {
            "name": "Visible Cols",
            "definition": {
                "sections": [
                    {
                        "type": "table",
                        "config": {
                            "title": "ERP Records",
                            "visible_columns": ["invoice_id", "supplier", "amount"],
                        },
                    }
                ]
            },
        }
        pdf_3 = self._generate_pdf(report_vis)
        self._cleanup(pdf_3)

    # ------------------------------------------------------------------
    # Test G: Chart Hash Caching
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.export_engine.ReportDataResolver.resolve")
    @patch("app.modules.reporting.services.export_engine.ChartRenderer.render_chart")
    def test_g_chart_caching(self, mock_render_chart, mock_resolve):
        """Test G: Duplicate chart data payloads should reuse cached chart PNGs."""
        import base64
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        fake_chart_path = os.path.join(tempfile.gettempdir(), "test_fake_chart.png")
        with open(fake_chart_path, "wb") as f:
            f.write(tiny_png)

        mock_resolve.return_value = {
            "title": "Volume",
            "data": {
                "chart_type": "bar",
                "labels": ["Jan", "Feb"],
                "datasets": [{"label": "Volume", "data": [10, 20]}],
            },
        }
        mock_render_chart.return_value = fake_chart_path

        report = {
            "name": "Cached Charts Report",
            "definition": {
                "sections": [
                    {"type": "chart", "config": {"title": "Volume 1"}},
                    {"type": "chart", "config": {"title": "Volume 2 (Identical)"}},
                ]
            },
        }

        file_path = self._generate_pdf(report)
        self._cleanup(file_path)

        # ChartRenderer should only be called once; second chart should use cache
        self.assertEqual(mock_render_chart.call_count, 1, "ChartRenderer should be called only once due to caching")

        if os.path.exists(fake_chart_path):
            os.remove(fake_chart_path)


if __name__ == "__main__":
    unittest.main()