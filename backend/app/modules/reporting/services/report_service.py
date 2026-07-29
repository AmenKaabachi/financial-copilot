import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.shared.database.supabase_client import get_supabase_client
from app.modules.reporting.services.analytics_service import AnalyticsService
from app.modules.reporting.analytics.component_registry import (
    get_all_components,
    get_component_by_id,
    select_components_for_prompt,
)

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
                "status": data.get("status", "DRAFT"),
                "definition": data.get("definition", {}),
                "is_favorite": data.get("is_favorite", False),
                "created_at": now,
                "updated_at": now,
            }
            # Add new fields if present
            if "creation_method" in data:
                record["creation_method"] = data["creation_method"]
            if "prompt_used" in data:
                record["prompt_used"] = data["prompt_used"]
            if "report_structure" in data:
                record["report_structure"] = data["report_structure"]
            if "sections" in data:
                record["sections"] = data["sections"]
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

    # --- AI Report Generation ---

    @staticmethod
    def generate_ai_report_structure(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze the user's prompt and generate an appropriate report structure.
        Uses the component registry to select relevant analytics components
        based on intent-based matching of the user's prompt.
        """
        try:
            objective = (request.get("objective", "") or "").lower()
            title = request.get("title", "Financial Report")

            # Use the component registry to select relevant components
            selected_components = select_components_for_prompt(objective)

            # Build structure nodes from selected components
            structure = []
            sections = []
            position = 1

            # Add executive summary section
            structure.append({"id": "executive_summary", "label": "Executive Summary", "children": []})
            sections.append({
                "id": f"sec_exec_summary_{uuid.uuid4().hex[:6]}",
                "type": "text",
                "position": position,
                "config": {
                    "content": f"## Executive Summary\n\nThis report provides a comprehensive analysis based on your request: {request.get('objective', '')}",
                    "ai_generated": True,
                },
            })
            position += 1

            # Group selected components by type
            kpi_comps = [c for c in selected_components if c["type"] == "kpi"]
            chart_comps = [c for c in selected_components if c["type"] == "chart"]
            table_comps = [c for c in selected_components if c["type"] == "table"]
            widget_comps = [c for c in selected_components if c["type"] in ("heatmap", "pivot", "trend")]

            # Add KPI section
            if kpi_comps:
                structure.append({"id": "key_metrics", "label": "Key Metrics", "children": []})
                sections.append({
                    "id": f"sec_kpis_{uuid.uuid4().hex[:6]}",
                    "type": "kpi",
                    "position": position,
                    "config": {
                        "component_ids": [c["id"] for c in kpi_comps],
                        "analytics_source": "kpi",
                        "ai_generated": True,
                    },
                })
                position += 1

            # Add chart sections
            if chart_comps:
                structure.append({"id": "charts_analysis", "label": "Charts & Visualizations", "children": []})
                for comp in chart_comps:
                    sections.append({
                        "id": f"sec_chart_{uuid.uuid4().hex[:6]}",
                        "type": "chart",
                        "position": position,
                        "config": {
                            "component_id": comp["id"],
                            "analytics_source": "chart_data",
                            "analytics_params": comp.get("analytics_params", {}),
                            "title": comp["name"],
                            "ai_generated": True,
                        },
                    })
                    position += 1

            # Add table sections
            if table_comps:
                structure.append({"id": "detailed_data", "label": "Detailed Data", "children": []})
                for comp in table_comps:
                    sections.append({
                        "id": f"sec_table_{uuid.uuid4().hex[:6]}",
                        "type": "table",
                        "position": position,
                        "config": {
                            "component_id": comp["id"],
                            "analytics_source": "table_data",
                            "analytics_params": comp.get("analytics_params", {}),
                            "title": comp["name"],
                            "ai_generated": True,
                        },
                    })
                    position += 1

            # Add analytics widget sections
            if widget_comps:
                structure.append({"id": "advanced_analytics", "label": "Advanced Analytics", "children": []})
                for comp in widget_comps:
                    sections.append({
                        "id": f"sec_widget_{uuid.uuid4().hex[:6]}",
                        "type": comp["type"],
                        "position": position,
                        "config": {
                            "component_id": comp["id"],
                            "analytics_source": comp["analytics_source"],
                            "analytics_params": comp.get("analytics_params", {}),
                            "title": comp["name"],
                            "ai_generated": True,
                        },
                    })
                    position += 1

            # Add recommendations section
            structure.append({"id": "recommendations", "label": "Recommendations", "children": []})
            sections.append({
                "id": f"sec_recommendations_{uuid.uuid4().hex[:6]}",
                "type": "text",
                "position": position,
                "config": {
                    "content": "## Recommendations\n\nBased on the analysis, the following recommendations are suggested:\n1. Review key metrics for actionable insights\n2. Investigate any anomalies or discrepancies\n3. Monitor trends for proactive decision-making",
                    "ai_generated": True,
                },
            })

            return {
                "title": title,
                "structure": structure,
                "sections": sections,
                "selected_components": [c["id"] for c in selected_components],
            }
        except Exception as exc:
            logger.warning("Failed to generate AI report structure: %s", exc)
            return None

    @staticmethod
    def create_ai_report(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a report using AI generation."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            record = {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "report_type": "ai",
                "owner_id": data.get("owner_id"),
                "status": "GENERATED",
                "creation_method": "AI_GENERATED",
                "prompt_used": data.get("prompt_used"),
                "report_structure": data.get("report_structure", []),
                "sections": data.get("sections", []),
                "definition": {"sections": data.get("sections", [])},
                "is_favorite": False,
                "created_at": now,
                "updated_at": now,
            }
            result = _table("report_definitions").insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to create AI report: %s", exc)
            return None

    @staticmethod
    def create_manual_report(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a report using the manual builder."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            record = {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "report_type": "manual",
                "owner_id": data.get("owner_id"),
                "status": "DRAFT",
                "creation_method": "MANUAL_BUILDER",
                "sections": data.get("sections", []),
                "definition": {"sections": data.get("sections", [])},
                "is_favorite": False,
                "created_at": now,
                "updated_at": now,
            }
            result = _table("report_definitions").insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to create manual report: %s", exc)
            return None

    @staticmethod
    def update_sections(report_id: str, sections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update the sections of a report."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            result = (
                _table("report_definitions")
                .update({"sections": sections, "definition": {"sections": sections}, "updated_at": now})
                .eq("id", report_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to update sections for report %s: %s", report_id, exc)
            return None

    @staticmethod
    def publish_report(report_id: str) -> Optional[Dict[str, Any]]:
        """Change report status to PUBLISHED."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            result = (
                _table("report_definitions")
                .update({"status": "PUBLISHED", "updated_at": now})
                .eq("id", report_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to publish report %s: %s", report_id, exc)
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

    @staticmethod
    def save_as_template(report_id: str, category: str = "custom") -> Optional[Dict[str, Any]]:
        """Save an existing report as a template."""
        try:
            report = ReportService.get_report(report_id)
            if not report:
                return None
            now = datetime.now(timezone.utc).isoformat()
            record = {
                "name": report.get("name", "Untitled Template"),
                "category": category,
                "scope": "user",
                "definition": report.get("definition", {}),
                "thumbnail_url": "",
                "created_by": report.get("owner_id"),
                "is_favorite": False,
                "created_at": now,
                "updated_at": now,
            }
            result = _table("report_templates").insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to save template from report %s: %s", report_id, exc)
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