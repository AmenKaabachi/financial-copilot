"""Quick syntax check for modified reporting module files."""
import py_compile
import os

files = [
    "app/modules/reporting/analytics/kpi_calculators.py",
    "app/modules/reporting/analytics/trend_engine.py",
    "app/modules/reporting/analytics/heatmap_engine.py",
    "app/modules/reporting/analytics/pivot_engine.py",
    "app/modules/reporting/services/report_service.py",
    "app/modules/reporting/services/dashboard_service.py",
    "app/modules/reporting/routes/builder.py",
]

errors = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"  ERROR: {f}: {e}")
        errors += 1

print(f"\n{'ALL OK' if errors == 0 else f'FAILED ({errors} errors)'}")