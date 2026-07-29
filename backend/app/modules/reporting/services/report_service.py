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
        report_type: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = _table("report_definitions").select(
            "id, name, description, report_type, owner_id, status, definition, is_favorite, created_at, updated_at"
        )
        if status:
            query = query.eq("status", status)
        if report_type:
            query = query.eq("report_type", report_type)
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
                .select("id, name, description, report_type, owner_id, status, definition, is_favorite, created_at, updated_at")
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
                "report_type": data.get("report_type", "custom"),
                "owner_id": data.get("owner_id"),
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
            # Get current version count from report_versions table
            versions_result = (
                _table("report_versions")
                .select("version_number")
                .eq("report_id", report_id)
                .order("version_number", desc=True)
                .limit(1)
                .execute()
            )
            current_max = versions_result.data[0]["version_number"] if versions_result.data else 0
            new_version = current_max + 1
            record = {
                "report_id": report_id,
                "version_number": new_version,
                "definition": definition,
                "change_note": change_note,
                "created_by": created_by,
                "created_at": now,
            }
            result = _table("report_versions").insert(record).execute()
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

    # --- Template Methods ---

    @staticmethod
    def list_templates(
        category: Optional[str] = None,
        scope: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        try:
            query = _table("report_templates").select(
                "id, name, category, scope, definition, thumbnail_url, created_by, is_favorite, created_at, updated_at"
            )
            if category:
                query = query.eq("category", category)
            if scope:
                query = query.eq("scope", scope)
            query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
            result = query.execute()
            return result.data or []
        except Exception as exc:
            logger.warning("Failed to list templates: %s", exc)
            return []

    @staticmethod
    def get_template(template_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = (
                _table("report_templates")
                .select("id, name, category, scope, definition, thumbnail_url, created_by, is_favorite, created_at, updated_at")
                .eq("id", template_id)
                .single()
                .execute()
            )
            return result.data
        except Exception as exc:
            logger.warning("Failed to get template %s: %s", template_id, exc)
            return None

    # --- Export Methods ---

    @staticmethod
    def create_export(
        report_id: str,
        format: str = "pdf",
        version_id: Optional[str] = None,
        requested_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            now = datetime.now(timezone.utc).isoformat()
            # If no version specified, get the latest version
            if not version_id:
                versions = ReportService.list_versions(report_id, limit=1)
                version_id = versions[0]["id"] if versions else None
            record = {
                "report_id": report_id,
                "version_id": version_id,
                "format": format,
                "status": "queued",
                "file_url": "",
                "requested_at": now,
                "completed_at": None,
            }
            result = _table("report_exports").insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to create export for report %s: %s", report_id, exc)
            return None

    @staticmethod
    def list_exports(
        report_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        try:
            result = (
                _table("report_exports")
                .select("id, report_id, version_id, format, status, file_url, requested_at, completed_at")
                .eq("report_id", report_id)
                .order("requested_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.warning("Failed to list exports for report %s: %s", report_id, exc)
            return []
