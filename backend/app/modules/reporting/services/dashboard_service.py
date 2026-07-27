import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.shared.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def _table(table: str):
    return get_supabase_client().table(table)


class DashboardService:
    @staticmethod
    def get_summary() -> Dict[str, Any]:
        total_reports = DashboardService._count("report_definitions")
        draft_reports = DashboardService._count("report_definitions", {"status": "draft"})
        published_reports = DashboardService._count("report_definitions", {"status": "published"})
        total_templates = DashboardService._count("report_templates")
        total_exports = DashboardService._count("report_exports")
        recent_reports = DashboardService._recent("report_definitions", limit=5)
        favorite_reports = DashboardService._favorites("report_definitions", limit=5)

        return {
            "total_reports": total_reports,
            "draft_reports": draft_reports,
            "published_reports": published_reports,
            "total_templates": total_templates,
            "total_exports": total_exports,
            "recent_reports": recent_reports,
            "favorite_reports": favorite_reports,
        }

    @staticmethod
    def get_recent(limit: int = 10) -> List[Dict[str, Any]]:
        return DashboardService._recent("report_definitions", limit=limit)

    @staticmethod
    def get_favorites(limit: int = 10) -> List[Dict[str, Any]]:
        return DashboardService._favorites("report_definitions", limit=limit)

    @staticmethod
    def _count(table_name: str, filters: Optional[Dict[str, Any]] = None) -> int:
        try:
            query = _table(table_name).select("id", count="exact")
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            result = query.execute()
            return result.count or 0
        except Exception as exc:
            logger.warning("Failed to count %s: %s", table_name, exc)
            return 0

    @staticmethod
    def _recent(table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            result = (
                _table(table_name)
                .select("id, name, description, status, source, created_at, updated_at")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.warning("Failed to fetch recent %s: %s", table_name, exc)
            return []

    @staticmethod
    def _favorites(table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            result = (
                _table(table_name)
                .select("id, name, description, status, source, created_at, updated_at")
                .eq("is_favorite", True)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.warning("Failed to fetch favorites %s: %s", table_name, exc)
            return []