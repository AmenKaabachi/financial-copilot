"""Unit tests for the AI Report Architect pipeline.

Tests cover:
    Test 1: Exact scenario prompt parsing into structured JSON
    Test 2: Prompt-echo detector (preventing instructions inside PDF body text)
    Test 3: Section Normalizer (enriching data sources, chart types, visible_columns)
    Test 4: Strict Schema Validation (rejecting invalid section types)
    Test 5: Full ReportService structure generation with [AI_BUILDER] logging
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.reporting.schemas.report_definition_schema import validate_report_definition_schema
from app.modules.reporting.services.report_section_mapper import SectionNormalizer, CHART_MAPPING, TABLE_MAPPING, KPI_MAPPING
from app.modules.reporting.services.report_validators import ReportValidators
from app.modules.reporting.services.ai_report_service import AIReportService
from app.modules.reporting.services.report_service import ReportService


class TestAIReportArchitect(unittest.TestCase):
    """Test suite for the AI Report Architect refactoring."""

    # ------------------------------------------------------------------
    # Test 1: Strict Schema Validation
    # ------------------------------------------------------------------

    def test_1_schema_validation(self):
        """Test schema validator accepts valid section types and rejects invalid ones."""
        valid_definition = {
            "name": "Q2 Review",
            "description": "Executive Overview",
            "sections": [
                {"type": "title", "config": {"title": "Q2 Performance"}},
                {"type": "text", "config": {"content": "Summary text"}},
                {"type": "kpi", "config": {"data_source": "revenue"}},
                {"type": "chart", "config": {"chart_type": "reconciliation_trend"}},
                {"type": "table", "config": {"data_source": "erp_transactions"}},
                {"type": "ai_insight", "config": {"insight_type": "trend_analysis"}},
            ],
        }
        res_valid = validate_report_definition_schema(valid_definition)
        self.assertTrue(res_valid["is_valid"], f"Valid schema rejected: {res_valid['errors']}")

        invalid_definition = {
            "name": "Invalid Report",
            "sections": [
                {"type": "invalid_custom_widget", "config": {}},
            ],
        }
        res_invalid = validate_report_definition_schema(invalid_definition)
        self.assertFalse(res_invalid["is_valid"], "Invalid schema section type was allowed")

    # ------------------------------------------------------------------
    # Test 2: Section Normalization
    # ------------------------------------------------------------------

    def test_2_section_normalizer(self):
        """Test SectionNormalizer enriches missing chart types, table columns, and titles."""
        raw_sections = [
            {"type": "chart", "config": {"title": "Reconciliation Report"}},
            {"type": "table", "config": {"title": "ERP Records"}},
            {"type": "recommendation", "config": {}},
        ]
        norm = SectionNormalizer.normalize_sections(raw_sections)
        self.assertEqual(len(norm), 3)

        # Chart should be mapped to reconciliation_trend
        chart_cfg = norm[0]["config"]
        self.assertEqual(chart_cfg["chart_type"], "reconciliation_trend")

        # Table should have default visible columns
        table_cfg = norm[1]["config"]
        self.assertEqual(table_cfg["data_source"], "erp_transactions")
        self.assertTrue("visible_columns" in table_cfg)
        self.assertIn("invoice_id", table_cfg["visible_columns"])

        # Recommendation should have items
        rec_cfg = norm[2]["config"]
        self.assertTrue("recommendations" in rec_cfg or "items" in rec_cfg)

    # ------------------------------------------------------------------
    # Test 3: Prompt Echo Detection
    # ------------------------------------------------------------------

    def test_3_prompt_echo_detector(self):
        """Test prompt-echo detector identifies and cleans echoed prompt instructions."""
        prompt = "Create a professional executive financial report called Q2 Financial Performance Review."
        echoing_definition = {
            "name": "Report",
            "sections": [
                {
                    "type": "text",
                    "config": {
                        "title": "Create a professional executive financial report called Q2 Financial Performance Review.",
                        "content": "Create a professional executive financial report called Q2 Financial Performance Review.",
                    },
                }
            ],
        }
        val_res = ReportValidators.validate_ai_report_definition(echoing_definition, original_prompt=prompt)
        self.assertTrue(val_res.corrected, "Prompt echo was not detected/corrected")
        
        # Verify content was sanitized
        clean_content = echoing_definition["sections"][0]["config"]["content"]
        self.assertNotIn("Create a professional executive financial report", clean_content)

    # ------------------------------------------------------------------
    # Test 4: End-to-End Prompt Parsing Scenario
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.ai_report_service.generate_answer")
    def test_4_e2e_prompt_architect(self, mock_llm):
        """Test full prompt parsing produces structured JSON without copying user prompt."""
        user_prompt = "Create Q2 Financial Performance Review. Include Revenue KPIs, Reconciliation Trend chart, ERP Transactions table, AI insights."
        
        # Simulate LLM Report Architect returning clean JSON structure
        mock_llm.return_value = {
            "answer": """```json
            {
              "name": "Q2 Financial Performance Review",
              "description": "Executive Financial Analysis",
              "sections": [
                { "type": "text", "config": { "title": "Executive Overview", "content": "Financial review of Q2 metrics." } },
                { "type": "kpi", "config": { "title": "Revenue KPIs", "data_source": "revenue" } },
                { "type": "chart", "config": { "title": "Reconciliation Trend", "chart_type": "reconciliation_trend" } },
                { "type": "table", "config": { "title": "ERP Transactions", "data_source": "erp_transactions" } },
                { "type": "ai_insight", "config": { "insight_type": "trend_analysis" } }
              ]
            }
            ```"""
        }

        ai_service = AIReportService()
        definition = ai_service.generate_report_definition_from_prompt(user_prompt)

        self.assertEqual(definition["name"], "Q2 Financial Performance Review")
        sections = definition["sections"]
        sec_types = [s["type"] for s in sections]

        self.assertIn("kpi", sec_types)
        self.assertIn("chart", sec_types)
        self.assertIn("table", sec_types)
        self.assertIn("ai_insight", sec_types)

        # Check prompt string is NOT in text section content
        for sec in sections:
            content = sec.get("config", {}).get("content", "")
            self.assertNotIn("Create Q2 Financial Performance Review. Include Revenue KPIs", content)

    # ------------------------------------------------------------------
    # Test 5: Full ReportService Structure Generation & Debug Payload
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.ai_report_service.generate_answer")
    def test_5_report_service_structure_gen(self, mock_llm):
        """Test ReportService.generate_ai_report_structure returns debug_info for frontend visibility."""
        user_prompt = "Create Q2 Financial Performance Review"
        mock_llm.return_value = {
            "answer": """{
              "name": "Q2 Financial Review",
              "description": "Analysis",
              "sections": [
                { "type": "kpi", "config": { "title": "Revenue", "data_source": "revenue" } }
              ]
            }"""
        }

        result = ReportService.generate_ai_report_structure({"objective": user_prompt})
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Q2 Financial Review")
        self.assertIn("debug_info", result)
        self.assertEqual(result["debug_info"]["user_prompt"], user_prompt)
        self.assertIn("kpi", result["debug_info"]["generated_types"])


if __name__ == "__main__":
    unittest.main()
