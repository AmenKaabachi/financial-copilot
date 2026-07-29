"""Test that all modified modules import correctly."""
import sys
sys.path.insert(0, '.')

print("Testing module imports...")

try:
    from app.modules.reporting.analytics.kpi_calculators import calculate_revenue
    print("  OK: kpi_calculators")
except Exception as e:
    print(f"  ERROR: kpi_calculators: {e}")

try:
    from app.modules.reporting.analytics.trend_engine import get_time_bucketed_series
    print("  OK: trend_engine")
except Exception as e:
    print(f"  ERROR: trend_engine: {e}")

try:
    from app.modules.reporting.analytics.heatmap_engine import get_heatmap_data
    print("  OK: heatmap_engine")
except Exception as e:
    print(f"  ERROR: heatmap_engine: {e}")

try:
    from app.modules.reporting.analytics.pivot_engine import pivot_aggregate
    print("  OK: pivot_engine")
except Exception as e:
    print(f"  ERROR: pivot_engine: {e}")

try:
    from app.modules.reporting.services.report_service import ReportService
    print("  OK: report_service")
except Exception as e:
    print(f"  ERROR: report_service: {e}")

try:
    from app.modules.reporting.services.dashboard_service import DashboardService
    print("  OK: dashboard_service")
except Exception as e:
    print(f"  ERROR: dashboard_service: {e}")

try:
    from app.modules.reporting.routes.builder import router as builder_router
    print("  OK: builder_routes")
except Exception as e:
    print(f"  ERROR: builder_routes: {e}")

try:
    from app.modules.reporting.routes.analytics import router as analytics_router
    print("  OK: analytics_routes")
except Exception as e:
    print(f"  ERROR: analytics_routes: {e}")

print("\nDone.")