import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import os

from app.shared.database.supabase_client import get_supabase_client
from app.modules.reporting.services.analytics_service import AnalyticsService
from app.modules.reporting.analytics.component_registry import (
    get_all_components,
    get_component_by_id,
    select_components_for_prompt,
)
from app.modules.reporting.services.ai_report_service import AIReportService
from app.modules.reporting.schemas.ai_report_schemas import ReportGenerationRequest

logger = logging.getLogger(__name__)


def _table(table: str):
    return get_supabase_client().table(table)


class ReportService:
    _FORBIDDEN_PROMPT_PHRASES = (
        "based on your request",
        "the user requested",
        "create an executive report",
        "additional instructions",
        "generate only",
        "do not copy",
    )

    @staticmethod
    def _normalize_language(language: Optional[str]) -> str:
        if not language:
            return "en"
        value = str(language).strip().lower()
        mapping = {
            "english": "en",
            "en": "en",
            "french": "fr",
            "fr": "fr",
            "arabic": "ar",
            "ar": "ar",
        }
        return mapping.get(value, "en")

    @staticmethod
    def _sanitize_description(description: str, objective: str, period_start: Optional[str], period_end: Optional[str]) -> str:
        clean = (description or "").strip()
        objective_text = (objective or "").strip()
        if clean and objective_text and clean.lower() == objective_text.lower():
            clean = ""
        if any(term in clean.lower() for term in ReportService._FORBIDDEN_PROMPT_PHRASES):
            clean = ""
        if not clean:
            period_text = f"{period_start} to {period_end}" if period_start and period_end else "the selected reporting period"
            clean = f"Executive assessment of financial performance, reconciliation quality, and operational risk for {period_text}."
        return clean

    @staticmethod
    def _validate_period(period_start: Optional[str], period_end: Optional[str]) -> None:
        if period_start and period_end and period_start > period_end:
            raise ValueError("period_start must be less than or equal to period_end")

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
                "status": data.get("status", "draft"),                "definition": data.get("definition", {}),
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
        Analyze the user's prompt and generate an appropriate report structure as a Report Architect.
        Does NOT copy the prompt into body text or titles.
        """
        try:
            report_title = (request.get("name") or request.get("title") or "").strip()
            prompt = (request.get("objective") or request.get("prompt") or "").strip()
            audience = (request.get("audience") or "Finance Team").strip()
            language = ReportService._normalize_language(request.get("language"))
            period_start = request.get("period_start")
            period_end = request.get("period_end")
            additional_instructions = (request.get("additional_instructions") or "").strip()
            report_type = request.get("report_type") or "monthly_financial"
            table_limit = request.get("table_limit")
            ReportService._validate_period(period_start, period_end)

            if not report_title:
                raise ValueError("Report title is required")
            if not prompt:
                raise ValueError("Report objective is required")

            architect_context = {
                "report_title": report_title,
                "objective": prompt,
                "audience": audience,
                "language": language,
                "period_start": period_start,
                "period_end": period_end,
                "additional_instructions": additional_instructions,
                "report_type": report_type,
                "table_limit": table_limit,
            }

            ai_service = AIReportService()
            definition = ai_service.generate_report_definition_from_prompt(
                prompt=prompt,
                title=report_title,
                architect_context=architect_context,
            )

            definition["name"] = report_title
            definition["description"] = ReportService._sanitize_description(
                definition.get("description", ""),
                prompt,
                period_start,
                period_end,
            )
            definition["report_context"] = {
                "report_title": report_title,
                "objective": prompt,
                "audience": audience,
                "language": language,
                "period_start": period_start,
                "period_end": period_end,
                "additional_instructions": additional_instructions,
                "report_type": report_type,
                "table_limit": table_limit,
            }

            sections = definition.get("sections", [])
            section_types = [sec.get("type") for sec in sections if isinstance(sec, dict)]

            # Apply global table_limit to table sections that have the normalizer
            # default limit (20). This preserves user-specified limits while not
            # overriding explicit values set by the LLM or manual builder.
            if table_limit is not None:
                for sec in sections:
                    if isinstance(sec, dict) and sec.get("type") == "table":
                        sec_config = sec.get("config") or {}
                        if sec_config.get("limit") == 20:
                            sec_config["limit"] = table_limit
                            sec["config"] = sec_config

            logger.info(f"[AI_BUILDER] Generated sections: {section_types}")
            logger.info("[AI_BUILDER] Validation passed")
            logger.info("[AI_BUILDER] Saving report definition")

            # Build UI structure representation
            structure = []
            for sec in sections:
                sec_type = sec.get("type", "section")
                sec_title = sec.get("config", {}).get("title", sec_type.replace("_", " ").title())
                structure.append({
                    "id": sec.get("id"),
                    "label": sec_title,
                    "type": sec_type,
                })

            generation_info = definition.get("_generation", {})
            ai_generation_attempted = generation_info.get("generation_mode") == "llm" or bool(generation_info.get("model", "unknown") != "fallback")
            ai_generation_success = bool(generation_info.get("ai_generated", True))
            fallback_used = bool(generation_info.get("fallback_used", False))

            # Log the full generation context for debugging
            logger.info("[AI_BUILDER] Reporting period: %s → %s", period_start, period_end)
            logger.info("[AI_BUILDER] Audience: %s", audience)
            logger.info("[AI_BUILDER] Language: %s", language)
            logger.info("[AI_BUILDER] Additional instructions: %s", additional_instructions)
            logger.info(
                "[AI_BUILDER] AI generation attempted=%s | success=%s | fallback_used=%s | model=%s",
                ai_generation_attempted,
                ai_generation_success,
                fallback_used,
                generation_info.get("model", "unknown"),
            )

            return {
                "title": report_title,
                "description": definition.get("description", "Executive Financial Analysis"),
                "structure": structure,
                "sections": sections,
                "definition": definition,
                "debug_info": {
                    "ai_generation_attempted": ai_generation_attempted,
                    "ai_generation_success": ai_generation_success,
                    "fallback_used": fallback_used,
                    "fallback_reason": generation_info.get("fallback_reason"),
                    "generation_mode": generation_info.get("generation_mode", "llm"),
                    "model": generation_info.get("model", "unknown"),
                    "language": language,
                    "audience": audience,
                    "period_start": period_start,
                    "period_end": period_end,
                    "sections_generated": section_types,
                },
            }
        except Exception as exc:
            logger.error(f"[AI_BUILDER] Failed to generate AI report structure: {exc}", exc_info=True)
            return None

    @staticmethod
    def create_ai_report(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a report using AI generation."""
        try:
            logger.info("[AI_BUILDER] Saving report definition to database")
            now = datetime.now(timezone.utc).isoformat()
            
            sections = data.get("sections", [])
            definition = data.get("definition") or {"sections": sections}
            if not definition.get("sections"):
                definition["sections"] = sections

            report_context = definition.get("report_context") or data.get("report_context") or {}
            objective = report_context.get("objective") or data.get("objective") or ""
            period_start = report_context.get("period_start") or data.get("period_start")
            period_end = report_context.get("period_end") or data.get("period_end")

            # User-provided report title is authoritative.
            ai_name = (data.get("name") or data.get("title") or definition.get("name") or "AI Financial Report").strip()
            definition["name"] = ai_name

            ai_description = ReportService._sanitize_description(
                definition.get("description") or data.get("description") or "",
                objective,
                period_start,
                period_end,
            )
            definition["description"] = ai_description
            definition["report_context"] = report_context

            record = {
                "name": ai_name,
                "description": ai_description,
                "report_type": "ai",
                "owner_id": data.get("owner_id"),
                "status": "draft",
                "creation_method": "AI_GENERATED",
                "prompt_used": data.get("prompt_used") or objective,
                "report_structure": data.get("report_structure") or data.get("structure", []),
                "sections": sections,
                "definition": definition,
                "is_favorite": False,
                "created_at": now,
                "updated_at": now,
            }
            result = _table("report_definitions").insert(record).execute()
            logger.info(f"[AI_BUILDER] Report saved successfully with ID: {result.data[0]['id'] if result.data else 'unknown'}")
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning(f"[AI_BUILDER] Failed to create AI report in DB: {exc}")
            return None


    @staticmethod
    def generate_ai_report_content(request: Dict[str, Any], report_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Generate AI-powered content for report sections.
        
        This method delegates to AIReportService to generate intelligent
        financial report content using the existing Copilot LLM infrastructure.
        
        Args:
            request: Dictionary containing:
                - report_type: Type of report (monthly_financial, quarterly_review, etc.)
                - date_from: Start date (ISO format)
                - date_to: End date (ISO format)
                - sections: List of section types to generate
                - language: Language code (en, fr, ar)
                - business_objectives: Optional list of business objectives
            report_id: Optional report ID for audit logging
        
        Returns:
            Dictionary with generated sections and metadata
        """
        try:
            # Map period_start/period_end to date_from/date_to for backward compatibility
            date_from = request.get("date_from") or request.get("period_start")
            date_to = request.get("date_to") or request.get("period_end")

            # Create request schema with full generation context propagated
            report_request = ReportGenerationRequest(
                report_type=request.get("report_type", "monthly_financial"),
                date_from=date_from,
                date_to=date_to,
                sections=request.get("sections", ["executive_summary", "recommendations"]),
                language=request.get("language", "en"),
                user_preferences=request.get("user_preferences", {}),
                business_objectives=request.get("business_objectives"),
                period_start=request.get("period_start") or date_from,
                period_end=request.get("period_end") or date_to,
                audience=request.get("audience"),
                objective=request.get("objective"),
                additional_instructions=request.get("additional_instructions"),
                report_title=request.get("report_title") or request.get("name") or request.get("title"),
            )

            # Use AIReportService to generate content
            ai_service = AIReportService()
            result = ai_service.generate_report_sections(report_request, report_id)

            logger.info(
                "AI report content generated successfully for report_type=%s, sections=%s",
                request.get("report_type"),
                request.get("sections"),
            )

            return result

        except Exception as exc:
            logger.warning("Failed to generate AI report content: %s", exc)
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
                "status": "draft",
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
                .update({"status": "published", "updated_at": now})
                .eq("id", report_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning("Failed to publish report %s: %s", report_id, exc)
            return None

    # --- Export Methods ---

    @staticmethod
    def create_export(
        report_id: str,
        format: str = "pdf",
        requested_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            now = datetime.now(timezone.utc).isoformat()
            record = {
                "report_id": report_id,
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
                .select("id, report_id, format, status, file_url, requested_at, completed_at")
                .eq("report_id", report_id)
                .order("requested_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.warning("Failed to list exports for report %s: %s", report_id, exc)
            return []

    @staticmethod
    def process_export_task(export_id: str, report_id: str, format_type: str):
        try:
            logger.info(f"Starting background export task for {export_id}")
            _table("report_exports").update({"status": "processing"}).eq("id", export_id).execute()
            
            report = ReportService.get_report(report_id)
            if not report:
                raise Exception(f"Report {report_id} not found")
                
            from app.modules.reporting.services.export_engine import ExportEngine
            file_path = ExportEngine.generate_export_file(report, format_type)
            if not file_path:
                raise Exception("Failed to generate export file")
                
            filename = os.path.basename(file_path)
            
            content_type = "application/pdf"
            if format_type in ["xls", "xlsx", "excel"]:
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif format_type == "csv":
                content_type = "text/csv"
                
            # Use supabase storage
            try:
                with open(file_path, "rb") as f:
                    get_supabase_client().storage.from_("exports").upload(
                        file=f.read(),
                        path=filename,
                        file_options={"content-type": content_type}
                    )
                public_url = get_supabase_client().storage.from_("exports").get_public_url(filename)
            except Exception as storage_exc:
                logger.warning(f"Failed to upload to Supabase storage (maybe 'exports' bucket is missing?): {storage_exc}")
                # Fallback to local URL for demo purposes if bucket doesn't exist
                public_url = f"/static/exports/{filename}"
            
            now = datetime.now(timezone.utc).isoformat()
            _table("report_exports").update({
                "status": "completed",
                "file_url": public_url,
                "completed_at": now
            }).eq("id", export_id).execute()
            
            logger.info(f"Export task {export_id} completed successfully. URL: {public_url}")
            
            # Cleanup temp file
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as exc:
            logger.error(f"Background export task failed for {export_id}: {exc}")
            _table("report_exports").update({"status": "failed"}).eq("id", export_id).execute()

    # --- Export Job Methods (async progress tracking) ---

    @staticmethod
    def create_export_job(report_id: str, format_type: str = "pdf") -> Optional[Dict[str, Any]]:
        """Create a new export job with progress tracking."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            record = {
                "report_id": report_id,
                "status": "queued",
                "progress": 0,
                "current_step": "Queued",
                "file_path": "",
                "created_at": now,
            }
            result = _table("report_export_jobs").insert(record).execute()
            return result.data[0] if result.data else None
        except Exception as exc:
            logger.warning(f"Failed to create export job for report {report_id}: {exc}")
            return None

    @staticmethod
    def update_export_job_progress(
        job_id: str,
        progress: int,
        current_step: str,
        status: Optional[str] = None,
    ) -> bool:
        """Update the progress of an export job."""
        try:
            update_data = {
                "progress": progress,
                "current_step": current_step,
            }
            if status:
                update_data["status"] = status
            _table("report_export_jobs").update(update_data).eq("id", job_id).execute()
            return True
        except Exception as exc:
            logger.warning(f"Failed to update export job {job_id}: {exc}")
            return False

    @staticmethod
    def complete_export_job(job_id: str, file_path: str) -> bool:
        """Mark an export job as completed."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            _table("report_export_jobs").update({
                "status": "completed",
                "progress": 100,
                "current_step": "Completed",
                "file_path": file_path,
                "completed_at": now,
            }).eq("id", job_id).execute()
            return True
        except Exception as exc:
            logger.warning(f"Failed to complete export job {job_id}: {exc}")
            return False

    @staticmethod
    def fail_export_job(job_id: str, error_message: str) -> bool:
        """Mark an export job as failed."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            _table("report_export_jobs").update({
                "status": "failed",
                "error_message": str(error_message)[:500],
                "completed_at": now,
            }).eq("id", job_id).execute()
            return True
        except Exception as exc:
            logger.warning(f"Failed to mark export job {job_id} as failed: {exc}")
            return False

    @staticmethod
    def get_export_job(job_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of an export job."""
        try:
            result = (
                _table("report_export_jobs")
                .select("id, report_id, status, progress, current_step, file_path, error_message, created_at, completed_at")
                .eq("id", job_id)
                .single()
                .execute()
            )
            return result.data
        except Exception as exc:
            logger.warning(f"Failed to get export job {job_id}: {exc}")
            return None
