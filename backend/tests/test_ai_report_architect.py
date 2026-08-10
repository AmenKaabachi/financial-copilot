"""Unit tests for the AI Report Architect pipeline.

Tests cover:
    Test 1: Exact scenario prompt parsing into structured JSON
    Test 2: Prompt-echo detector (preventing instructions inside PDF body text)
    Test 3: Section Normalizer (enriching data sources, chart types, visible_columns)
    Test 4: Strict Schema Validation (rejecting invalid section types)
    Test 5: Full ReportService structure generation with [AI_BUILDER] logging
    Test 6: Different prompts produce different report structures
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
        report_title = "Q2 Financial Performance Review"
        
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
        definition = ai_service.generate_report_definition_from_prompt(
            user_prompt,
            title=report_title,
            architect_context={
                "report_title": report_title,
                "objective": user_prompt,
                "audience": "CFO / Executive Management",
                "language": "en",
                "period_start": "2026-04-01",
                "period_end": "2026-06-30",
                "additional_instructions": "",
            },
        )

        # User title is authoritative
        self.assertEqual(definition["name"], report_title)
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

        # Generation metadata must indicate real LLM was used
        self.assertTrue(definition["_generation"]["ai_generated"])
        self.assertFalse(definition["_generation"]["fallback_used"])

        # Report context must preserve title/audience/language/period
        rc = definition["report_context"]
        self.assertEqual(rc["report_title"], report_title)
        self.assertEqual(rc["audience"], "CFO / Executive Management")
        self.assertEqual(rc["language"], "en")
        self.assertEqual(rc["period_start"], "2026-04-01")
        self.assertEqual(rc["period_end"], "2026-06-30")

    # ------------------------------------------------------------------
    # Test 5: Full ReportService Structure Generation & Debug Payload
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.ai_report_service.generate_answer")
    def test_5_report_service_structure_gen(self, mock_llm):
        """Test ReportService.generate_ai_report_structure returns debug_info for frontend visibility."""
        report_title = "Q2 Financial Performance Review"
        user_prompt = "Analyze revenue growth, profitability, and cash flow for senior management."
        mock_llm.return_value = {
            "answer": """{
              "name": "Q2 Financial Review",
              "description": "Analysis",
              "sections": [
                { "type": "kpi", "config": { "title": "Revenue", "data_source": "revenue" } }
              ]
            }"""
        }

        result = ReportService.generate_ai_report_structure({
            "title": report_title,
            "objective": user_prompt,
            "audience": "CFO / Executive Management",
            "language": "English",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "additional_instructions": "Keep the executive summary under 150 words.",
        })
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], report_title)
        self.assertIn("debug_info", result)

        di = result["debug_info"]
        # AI generation attempted and succeeded (LLM was mocked to succeed)
        self.assertTrue(di["ai_generation_attempted"])
        self.assertTrue(di["ai_generation_success"])
        self.assertFalse(di["fallback_used"])
        self.assertEqual(di["model"], "unknown")  # mocked without model field
        self.assertEqual(di["language"], "en")
        self.assertEqual(di["audience"], "CFO / Executive Management")
        self.assertEqual(di["period_start"], "2026-04-01")
        self.assertEqual(di["period_end"], "2026-06-30")
        self.assertIn("kpi", di["sections_generated"])

    # ------------------------------------------------------------------
    # Test 5B: Fallback is explicitly reported
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.ai_report_service.generate_answer")
    def test_5b_fallback_is_explicitly_reported(self, mock_llm):
        """Test that when LLM fails, fallback_used=True and fallback_reason is exposed."""
        mock_llm.side_effect = Exception("Request exceeded time budget of 45.0s")

        result = ReportService.generate_ai_report_structure({
            "title": "Q2 Review",
            "objective": "Analyze revenue growth.",
            "audience": "CFO",
            "language": "English",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "additional_instructions": "",
        })
        self.assertIsNotNone(result)

        di = result["debug_info"]
        self.assertTrue(di["fallback_used"])
        self.assertFalse(di["ai_generation_success"])
        self.assertIn("fallback_reason", di)
        self.assertIn("Request exceeded time budget", di["fallback_reason"])

    # ------------------------------------------------------------------
    # Test 6: Different prompts produce different report structures
    # ------------------------------------------------------------------

    @patch("app.modules.reporting.services.ai_report_service.generate_answer")
    def test_6_different_prompts_produce_different_structures(self, mock_llm):
        """Test that distinct user prompts yield distinct report structures (section types, titles)."""
        ai_service = AIReportService()

        # Prompt A: Revenue- and KPI-focused monthly review
        prompt_a = "Create a monthly revenue performance report with revenue KPIs and comparisons."
        response_a = {
            "answer": """```json
            {
              "name": "Monthly Revenue Performance",
              "description": "Revenue-focused monthly review",
              "sections": [
                { "type": "kpi", "config": { "title": "Revenue KPIs", "data_source": "revenue" } },
                { "type": "chart", "config": { "title": "Revenue Trend", "chart_type": "revenue_trend" } },
                { "type": "text", "config": { "title": "Revenue Analysis", "content": "Summary of revenue performance." } }
              ]
            }
            
```"""
        }

        # Prompt B: Expense- and anomaly-focused review
        prompt_b = "Investigate expense anomalies and reconciliation accuracy for the quarter."
        response_b = {
            "answer": """```json
            {
              "name": "Expense & Anomaly Investigation",
              "description": "Expense anomaly and reconciliation review",
              "sections": [
                { "type": "kpi", "config": { "title": "Expense KPIs", "data_source": "expenses" } },
                { "type": "kpi", "config": { "title": "Reconciliation Rate", "data_source": "reconciliation_rate" } },
                { "type": "table", "config": { "title": "Anomaly Records", "data_source": "anomaly_records" } },
                { "type": "recommendation", "config": { "title": "Anomaly Mitigation" } }
              ]
            }
            
```"""
        }

        mock_llm.side_effect = [response_a, response_b]

        definition_a = ai_service.generate_report_definition_from_prompt(
            prompt_a,
            title="Monthly Revenue Performance",
            architect_context={"report_title": "Monthly Revenue Performance", "objective": prompt_a, "audience": "CFO", "language": "en"},
        )
        definition_b = ai_service.generate_report_definition_from_prompt(
            prompt_b,
            title="Expense & Anomaly Investigation",
            architect_context={"report_title": "Expense & Anomaly Investigation", "objective": prompt_b, "audience": "Finance Team", "language": "en"},
        )

        # Different names should be produced
        self.assertNotEqual(definition_a["name"], definition_b["name"])

        types_a = [sec["type"] for sec in definition_a["sections"]]
        types_b = [sec["type"] for sec in definition_b["sections"]]

        # Both generate valid structures
        self.assertGreater(len(types_a), 0)
        self.assertGreater(len(types_b), 0)

        # The two prompts must NOT produce identical section structure
        self.assertNotEqual(types_a, types_b, "Different prompts should yield different section type sequences")

        # Prompt A should contain revenue KPI and chart; Prompt B should contain anomaly table
        self.assertIn("kpi", types_a)
        self.assertIn("revenue", [sec.get("config", {}).get("data_source") for sec in definition_a["sections"]])
        self.assertIn("table", types_b)
        self.assertIn("anomaly_records", [sec.get("config", {}).get("data_source") for sec in definition_b["sections"]])

        # Section normalization must enrich the chart type (fuzzy "revenue trend" -> canonical "revenue_trend")
        chart_sections_a = [sec for sec in definition_a["sections"] if sec["type"] == "chart"]
        self.assertTrue(chart_sections_a)
        self.assertEqual(chart_sections_a[0].get("config", {}).get("chart_type"), "revenue_trend")


if __name__ == "__main__":
    unittest.main()