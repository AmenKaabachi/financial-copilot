"""
Test script for the Export Engine (Phase 1 verification).

This script tests the export engine by:
1. Creating a mock report with various section types
2. Calling the export engine directly
3. Verifying the PDF is generated with real data

Usage:
    python test_export_engine.py

Requires:
    - Backend dependencies installed (pip install -r requirements.txt)
    - Supabase database accessible with sample data
"""

import os
import sys
import json
import logging
import tempfile

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Ensure we can import from the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_test_report():
    """Create a mock report with all section types for testing."""
    return {
        "name": "Phase 1 Test Report - Financial Overview",
        "description": "This is a test report to verify the export engine renders real data from AnalyticsService.",
        "definition": {
            "sections": [
                # --- Title Section ---
                {
                    "type": "title",
                    "config": {
                        "title": "Executive Summary"
                    }
                },
                # --- Text Section ---
                {
                    "type": "text",
                    "config": {
                        "content": "This report provides a comprehensive financial overview based on the latest available data. All metrics are computed using the analytics engine."
                    }
                },
                # --- Financial Summary Section ---
                {
                    "type": "financial_summary",
                    "config": {
                        "title": "Financial Health Overview"
                    }
                },
                # --- KPI Section (using component_ids from AI generator) ---
                {
                    "type": "kpi",
                    "config": {
                        "component_ids": [
                            "kpi_revenue",
                            "kpi_expenses",
                            "kpi_profit",
                            "kpi_cash_flow",
                            "kpi_reconciliation_rate",
                            "kpi_matching_accuracy"
                        ],
                        "title": "Key Performance Indicators"
                    }
                },
                # --- KPI Section (single KPI via kpi_key) ---
                {
                    "type": "kpi",
                    "config": {
                        "kpi_key": "matching_accuracy",
                        "title": "Reconciliation Accuracy"
                    }
                },
                # --- Table Section (using component_id) ---
                {
                    "type": "table",
                    "config": {
                        "component_id": "table_reconciliations",
                        "title": "Reconciliation Records",
                        "limit": 10
                    }
                },
                # --- Table Section (using data_source directly) ---
                {
                    "type": "table",
                    "config": {
                        "data_source": "erp_transactions",
                        "title": "ERP Transactions",
                        "limit": 10
                    }
                },
                # --- Chart Section (using component_id) ---
                {
                    "type": "chart",
                    "config": {
                        "component_id": "chart_reconciliation_trend",
                        "title": "Reconciliation Trend"
                    }
                },
                # --- Chart Section (using chart_type directly) ---
                {
                    "type": "chart",
                    "config": {
                        "chart_type": "transaction_volume",
                        "title": "Transaction Volume"
                    }
                },
                # --- Recommendation Section ---
                {
                    "type": "recommendation",
                    "config": {
                        "content": "Based on the financial analysis, the following recommendations are proposed to improve financial performance and reconciliation accuracy.",
                        "recommendations": [
                            "Review and resolve outstanding reconciliations to improve matching rate",
                            "Investigate high-severity anomalies for potential fraud or system errors",
                            "Optimize cash flow management by reducing payment delays",
                            "Schedule regular financial health reviews with stakeholders"
                        ]
                    }
                },
                # --- AI Insight Section ---
                {
                    "type": "ai_insight",
                    "config": {
                        "content": "## AI-Generated Financial Insights\n\nBased on the analysis of your financial data, the following key insights have been identified:\n\n1. **Revenue Performance**: The company shows strong revenue generation with a healthy collection rate.\n2. **Reconciliation Health**: The matching accuracy indicates room for improvement in the reconciliation process.\n3. **Cash Flow Position**: Net cash flow appears stable, but monitoring payment delays is recommended.\n4. **Risk Factors**: Anomaly detection has identified transactions requiring further investigation."
                    }
                },
                # --- Divider ---
                {
                    "type": "divider",
                    "config": {}
                },
                # --- Title Section ---
                {
                    "type": "title",
                    "config": {
                        "title": "Detailed Analysis"
                    }
                },
                # --- Anomaly Stats KPI ---
                {
                    "type": "kpi",
                    "config": {
                        "component_id": "kpi_anomaly_stats",
                        "title": "Anomaly Statistics"
                    }
                },
                # --- Anomaly Table ---
                {
                    "type": "table",
                    "config": {
                        "component_id": "table_anomalies",
                        "title": "Anomaly Records",
                        "limit": 10
                    }
                },
                # --- Payment Status Chart ---
                {
                    "type": "chart",
                    "config": {
                        "chart_type": "payment_status",
                        "title": "Payment Status Distribution"
                    }
                }
            ]
        }
    }


def test_pdf_export():
    """Test PDF generation with the export engine."""
    from app.modules.reporting.services.export_engine import ExportEngine

    report = create_test_report()
    logger.info("=" * 60)
    logger.info("TEST: PDF Export with Real Data")
    logger.info("=" * 60)
    logger.info(f"Report: {report['name']}")
    logger.info(f"Sections: {len(report['definition']['sections'])}")

    # Generate PDF
    file_path = ExportEngine.generate_export_file(report, "pdf")

    if not file_path:
        logger.error("FAILED: No file path returned")
        return False

    if not os.path.exists(file_path):
        logger.error(f"FAILED: File does not exist at {file_path}")
        return False

    file_size = os.path.getsize(file_path)
    logger.info(f"PDF generated: {file_path}")
    logger.info(f"File size: {file_size} bytes")

    if file_size < 1000:
        logger.warning(f"WARNING: PDF is very small ({file_size} bytes) — may be empty")
    else:
        logger.info(f"PASS: PDF is {file_size} bytes with content")

    # Read the PDF content to verify it's not empty
    with open(file_path, "rb") as f:
        content = f.read()

    # Check for placeholder values
    placeholders = [
        b"Column A",
        b"Column B",
        b"Data 1",
        b"Data 2",
        b"Enter recommendation here",
        b"matching_accuracy",  # Should not be printed as ID
    ]
    has_placeholders = False
    for ph in placeholders:
        if ph in content:
            logger.warning(f"PLACEHOLDER FOUND: '{ph.decode()}' in PDF")
            has_placeholders = True

    if not has_placeholders:
        logger.info("PASS: No placeholder values found in PDF")
    else:
        logger.warning("SOME PLACEHOLDERS STILL PRESENT — needs investigation")

    # Check for real data indicators
    indicators = [
        b"Total Revenue",
        b"Total Expenses",
        b"Cash Flow",
        b"Reconciliation",
        b"Recommendations",
        b"AI Insights",
        b"Key Performance",
    ]
    found_indicators = 0
    for ind in indicators:
        if ind in content:
            found_indicators += 1
            logger.info(f"  Found indicator: {ind.decode()}")

    logger.info(f"Real data indicators found: {found_indicators}/{len(indicators)}")

    if found_indicators >= 3:
        logger.info("PASS: Real data indicators present in PDF")
    else:
        logger.warning("WARNING: Few real data indicators found — check the output")

    # Cleanup
    os.remove(file_path)
    logger.info(f"Cleaned up test file: {file_path}")

    return True


def test_excel_export():
    """Test Excel generation with the export engine."""
    from app.modules.reporting.services.export_engine import ExportEngine

    report = create_test_report()
    logger.info("=" * 60)
    logger.info("TEST: Excel Export with Real Data")
    logger.info("=" * 60)

    file_path = ExportEngine.generate_export_file(report, "xlsx")

    if not file_path or not os.path.exists(file_path):
        logger.error("FAILED: Excel file not generated")
        return False

    file_size = os.path.getsize(file_path)
    logger.info(f"Excel generated: {file_path}")
    logger.info(f"File size: {file_size} bytes")

    if file_size < 500:
        logger.warning("WARNING: Excel file is very small")
    else:
        logger.info("PASS: Excel file has content")

    # Read and verify it's a valid Excel file
    try:
        import pandas as pd
        df = pd.read_excel(file_path)
        logger.info(f"Excel rows: {len(df)}, columns: {list(df.columns)}")
    except Exception as e:
        logger.error(f"FAILED: Could not read Excel file: {e}")
        return False

    os.remove(file_path)
    return True


def test_csv_export():
    """Test CSV generation with the export engine."""
    from app.modules.reporting.services.export_engine import ExportEngine

    report = create_test_report()
    logger.info("=" * 60)
    logger.info("TEST: CSV Export with Real Data")
    logger.info("=" * 60)

    file_path = ExportEngine.generate_export_file(report, "csv")

    if not file_path or not os.path.exists(file_path):
        logger.error("FAILED: CSV file not generated")
        return False

    file_size = os.path.getsize(file_path)
    logger.info(f"CSV generated: {file_path}")
    logger.info(f"File size: {file_size} bytes")

    os.remove(file_path)
    return True


def test_manual_report_sections():
    """Test that manual builder sections export correctly.

    This simulates sections created by the manual builder where
    users enter their own content and select data sources.
    """
    from app.modules.reporting.services.export_engine import ExportEngine

    logger.info("=" * 60)
    logger.info("TEST: Manual Builder Section Rendering")
    logger.info("=" * 60)

    manual_report = {
        "name": "Manual Builder Test Report",
        "description": "Report created via manual builder",
        "definition": {
            "sections": [
                {
                    "type": "title",
                    "config": {"title": "Manual Analysis Report"}
                },
                {
                    "type": "text",
                    "config": {"content": "This report was created manually by the user.\n\nIt contains custom analysis and selected data sources."}
                },
                {
                    "type": "kpi",
                    "config": {
                        "kpi_key": "revenue",
                        "title": "Revenue Overview"
                    }
                },
                {
                    "type": "kpi",
                    "config": {
                        "kpi_key": "reconciliation_rate",
                        "title": "Reconciliation Performance"
                    }
                },
                {
                    "type": "table",
                    "config": {
                        "data_source": "erp_transactions",
                        "title": "ERP Transaction Details",
                        "limit": 5
                    }
                },
                {
                    "type": "recommendation",
                    "config": {
                        "content": "User-created recommendations:",
                        "recommendations": [
                            "Follow up on outstanding invoices",
                            "Review unmatched bank transactions"
                        ]
                    }
                }
            ]
        }
    }

    file_path = ExportEngine.generate_export_file(manual_report, "pdf")

    if not file_path or not os.path.exists(file_path):
        logger.error("FAILED: Manual report PDF not generated")
        return False

    file_size = os.path.getsize(file_path)
    logger.info(f"Manual report PDF generated: {file_size} bytes")

    # Check for manual content
    with open(file_path, "rb") as f:
        content = f.read()

    manual_checks = [
        b"Manual Analysis Report",
        b"User-created recommendations",
        b"outstanding invoices",
        b"unmatched bank transactions",
        b"Revenue Overview",
        b"Total Revenue",
        b"ERP Transaction Details",
    ]

    for check in manual_checks:
        if check in content:
            logger.info(f"  Found: {check.decode()}")
        else:
            logger.warning(f"  MISSING: {check.decode()}")

    # Check no placeholders remain
    if b"Enter recommendation here" in content:
        logger.warning("PLACEHOLDER 'Enter recommendation here' still present")
    if b"Data 1" in content:
        logger.warning("PLACEHOLDER 'Data 1' still present")
    if b"Column A" in content:
        logger.warning("PLACEHOLDER 'Column A' still present")

    os.remove(file_path)
    return True


if __name__ == "__main__":
    results = []

    logger.info("\n")
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║     Export Engine Phase 1 Verification Suite    ║")
    logger.info("╚══════════════════════════════════════════════════╝")
    logger.info("")

    try:
        results.append(("PDF Export (AI Report)", test_pdf_export()))
    except Exception as e:
        logger.error(f"PDF test failed with exception: {e}", exc_info=True)
        results.append(("PDF Export (AI Report)", False))

    try:
        results.append(("Excel Export", test_excel_export()))
    except Exception as e:
        logger.error(f"Excel test failed with exception: {e}", exc_info=True)
        results.append(("Excel Export", False))

    try:
        results.append(("CSV Export", test_csv_export()))
    except Exception as e:
        logger.error(f"CSV test failed with exception: {e}", exc_info=True)
        results.append(("CSV Export", False))

    try:
        results.append(("Manual Builder Sections", test_manual_report_sections()))
    except Exception as e:
        logger.error(f"Manual builder test failed with exception: {e}", exc_info=True)
        results.append(("Manual Builder Sections", False))

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        logger.info(f"  [{status}] {name}")

    logger.info("")
    if all_passed:
        logger.info("ALL TESTS PASSED ✅")
    else:
        logger.info("SOME TESTS FAILED ❌")
    logger.info("")