import logging
from fastapi import APIRouter

from app.modules.reporting.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard")
def reporting_dashboard():
    """
    GET /reporting/dashboard
    Returns summary widgets for the Reporting Dashboard Home.
    """
    try:
        summary = DashboardService.get_summary()
        return {
            "status": "ok",
            "data": summary,
        }
    except Exception as exc:
        logger.exception("Dashboard query failed: %s", exc)
        return {
            "status": "error",
            "data": {
                "total_reports": 0,
                "draft_reports": 0,
                "published_reports": 0,
                "total_templates": 0,
                "total_exports": 0,
                "recent_reports": [],
                "favorite_reports": [],
            },
        }