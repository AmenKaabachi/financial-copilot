import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.shared.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def _table(table: str):
    return get_supabase_client().table(table)


class ReportService:
    @staticmethod
    def list_reports(
        status: Optional[str] = None,
        source: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = _table("report_definitions").select(
            "id, name, description, version, tags, owner_id, source, status, definition, is_favorite, created_at, updated_at"
        )
        if status:
            query = query.eq("status", status)
        if source:
            query = query.eq("source", source)
        if owner_id:
            query = query.eq("owner_id", owner_id)
        query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
        try:
            result = query.execute()
            return result.data or []
        except Exception as exc:
            logger.warning("Failed to list reports: %s", exc)
            return []

    @staticmethod
    def get_report(report_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = (
                _table("report_definitions")
                .select("id, name, description, version, tags, owner_id, source, status, definition, is_favorite, created_at, updated_at")
                .eq("id", report_id)
                .single()
                .execute()
            )
            return result.data
        except Exception as exc:
            logger.warning("Failed to get report %s: %s", report_id, exc)
            return None

    @staticmethod
    def create_report(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            now = datetime.now(timezone.utc).isoformat()
            record = {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "version": 1,
                "tags": data.get("tags", []),
                "owner_id": data.get("owner_id"),
                "source": data.get("source", "manual"),
                "status": data.get("status", "draft"),
                "definition": data.get("definition", {}),
                "is_favorite": data.get("is_favorite", False),
                "created_at": now,
                "updated_at": now,
            }
            result = _table("report_definitions").insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to create report: %s", exc)
            return None

    @staticmethod
    def update_report(report_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            now = datetime.now(timezone.utc).isoformat()
            update_data = {k: v for k, v in data.items() if k not in ("id", "created_at")}
            update_data["updated_at"] = now
            result = (
                _table("report_definitions")
                .update(update_data)
                .eq("id", report_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to update report %s: %s", report_id, exc)
            return None

    @staticmethod
    def delete_report(report_id: str) -> bool:
        try:
            _table("report_definitions").delete().eq("id", report_id).execute()
            return True
        except Exception as exc:
            logger.warning("Failed to delete report %s: %s", report_id, exc)
            return False

    @staticmethod
    def toggle_favorite(report_id: str) -> Optional[Dict[str, Any]]:
        report = ReportService.get_report(report_id)
        if not report:
            return None
        new_value = not report.get("is_favorite", False)
        return ReportService.update_report(report_id, {"is_favorite": new_value})

    @staticmethod
    def create_version(
        report_id: str,
        definition: Dict[str, Any],
        change_note: str = "",
        created_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            report = ReportService.get_report(report_id)
            if not report:
                return None
            now = datetime.now(timezone.utc).isoformat()
            new_version = report.get("version", 0) + 1
            record = {
                "report_id": report_id,
                "version_number": new_version,
                "definition": definition,
                "change_note": change_note,
                "created_by": created_by,
                "created_at": now,
            }
            result = _table("report_versions").insert(record).execute()
            ReportService.update_report(report_id, {"version": new_version, "definition": definition})
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to create version for report %s: %s", report_id, exc)
            return None

    @staticmethod
    def list_versions(report_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            result = (
                _table("report_versions")
                .select("id, report_id, version_number, definition, change_note, created_by, created_at")
                .eq("report_id", report_id)
                .order("version_number", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.warning("Failed to list versions for report %s: %s", report_id, exc)
            return []

    @staticmethod
    def get_version(report_id: str, version_number: int) -> Optional[Dict[str, Any]]:
        try:
            result = (
                _table("report_versions")
                .select("id, report_id, version_number, definition, change_note, created_by, created_at")
                .eq("report_id", report_id)
                .eq("version_number", version_number)
                .single()
                .execute()
            )
            return result.data
        except Exception as exc:
            logger.warning("Failed to get version %d for report %s: %s", version_number, report_id, exc)
            return None