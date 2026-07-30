import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request, BackgroundTasks
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import os

from app.modules.reporting.services.report_service import ReportService
from app.modules.reporting.services.analytics_service import AnalyticsService
from app.modules.reporting.analytics.component_registry import (
    get_all_components,
    get_component_by_id,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Existing CRUD Endpoints ---

@router.get("/reports")
def list_reports(
    status: Optional[str] = Query(default=None),
    report_type: Optional[str] = Query(default=None),
    owner_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    reports = ReportService.list_reports(
        status=status, report_type=report_type, owner_id=owner_id, limit=limit, offset=offset
    )
    return {"status": "ok", "data": reports, "total": len(reports)}


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    logger.info(f"[Builder API] GET /reports/{report_id} called")
    report = ReportService.get_report(report_id)
    if not report:
        logger.warning(f"[Builder API] GET /reports/{report_id} - Report not found in DB")
        return {"status": "error", "message": "Report not found"}
    logger.info(f"[Builder API] GET /reports/{report_id} - Successfully retrieved report {report_id}")
    return {"status": "ok", "data": report}


@router.post("/reports")
async def create_report(request: Request):
    body = await request.json()
    # Map frontend 'source' field to 'report_type' for DB compatibility
    if "source" in body and "report_type" not in body:
        body["report_type"] = body.pop("source")
    report = ReportService.create_report(body)
    if not report:
        return {"status": "error", "message": "Failed to create report"}
    return {"status": "ok", "data": report}


@router.put("/reports/{report_id}")
async def update_report(report_id: str, request: Request):
    body = await request.json()
    # Map frontend 'source' field to 'report_type' for DB compatibility
    if "source" in body and "report_type" not in body:
        body["report_type"] = body.pop("source")
    report = ReportService.update_report(report_id, body)
    if not report:
        return {"status": "error", "message": "Failed to update report"}
    return {"status": "ok", "data": report}


@router.delete("/reports/{report_id}")
def delete_report(report_id: str):
    success = ReportService.delete_report(report_id)
    return {"status": "ok" if success else "error", "data": {"deleted": success}}


@router.post("/reports/{report_id}/favorite")
def toggle_favorite(report_id: str):
    report = ReportService.toggle_favorite(report_id)
    if not report:
        return {"status": "error", "message": "Report not found"}
    return {"status": "ok", "data": report}


# --- New: AI Report Generation Endpoints ---

@router.post("/ai/generate-structure")
async def ai_generate_structure(request: Request):
    """Generate a report structure based on user prompt (AI)."""
    body = await request.json()
    result = ReportService.generate_ai_report_structure(body)
    if not result:
        return {"status": "error", "message": "Failed to generate report structure"}
    return {"status": "ok", "data": result}


@router.post("/ai/create-report")
async def ai_create_report(request: Request):
    """Create a report using AI generation."""
    body = await request.json()
    report = ReportService.create_ai_report(body)
    if not report:
        return {"status": "error", "message": "Failed to create AI report"}
    return {"status": "ok", "data": report}


# --- New: Manual Builder Endpoints ---

@router.post("/manual/create-report")
async def manual_create_report(request: Request):
    """Create a report using the manual builder."""
    body = await request.json()
    report = ReportService.create_manual_report(body)
    if not report:
        return {"status": "error", "message": "Failed to create manual report"}
    return {"status": "ok", "data": report}


@router.put("/reports/{report_id}/sections")
async def update_report_sections(report_id: str, request: Request):
    """Update the sections of a report."""
    body = await request.json()
    sections = body.get("sections", [])
    report = ReportService.update_sections(report_id, sections)
    if not report:
        return {"status": "error", "message": "Failed to update sections"}
    return {"status": "ok", "data": report}


@router.post("/reports/{report_id}/publish")
def publish_report(report_id: str):
    """Publish a report (change status to PUBLISHED)."""
    report = ReportService.publish_report(report_id)
    if not report:
        return {"status": "error", "message": "Failed to publish report"}
    return {"status": "ok", "data": report}


@router.post("/reports/{report_id}/save-template")
async def save_report_as_template(report_id: str, request: Request):
    """Save a report as a template."""
    body = await request.json()
    category = body.get("category", "custom")
    template = ReportService.save_as_template(report_id, category)
    if not template:
        return {"status": "error", "message": "Failed to save template"}
    return {"status": "ok", "data": template}


# --- Version Endpoints ---

@router.post("/reports/{report_id}/versions")
async def create_version(report_id: str, request: Request):
    body = await request.json()
    version = ReportService.create_version(
        report_id=report_id,
        definition=body.get("definition", {}),
        change_note=body.get("change_note", ""),
        created_by=body.get("created_by"),
    )
    if not version:
        return {"status": "error", "message": "Failed to create version"}
    return {"status": "ok", "data": version}


@router.get("/reports/{report_id}/versions")
def list_versions(report_id: str, limit: int = Query(default=20, ge=1, le=100)):
    versions = ReportService.list_versions(report_id, limit=limit)
    return {"status": "ok", "data": versions}


@router.get("/reports/{report_id}/versions/{version_number}")
def get_version(report_id: str, version_number: int):
    version = ReportService.get_version(report_id, version_number)
    if not version:
        return {"status": "error", "message": "Version not found"}
    return {"status": "ok", "data": version}


# --- Template Endpoints ---

@router.get("/templates")
def list_templates(
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    templates = ReportService.list_templates(
        category=category, limit=limit, offset=offset
    )
    return {"status": "ok", "data": templates, "total": len(templates)}


@router.get("/templates/{template_id}")
def get_template(template_id: str):
    template = ReportService.get_template(template_id)
    if not template:
        return {"status": "error", "message": "Template not found"}
    return {"status": "ok", "data": template}


# --- Export Endpoints ---

@router.post("/reports/{report_id}/export")
async def create_export(report_id: str, request: Request):
    body = await request.json()
    format_type = body.get("format", "pdf")
    
    report = ReportService.get_report(report_id)
    if not report:
        return {"status": "error", "message": "Report not found"}
        
    from app.modules.reporting.services.export_engine import ExportEngine
    file_path = ExportEngine.generate_export_file(report, format_type)
    
    if not file_path or not os.path.exists(file_path):
        return {"status": "error", "message": "Failed to generate export file"}
        
    # Log the successful export generation in the database
    export = ReportService.create_export(
        report_id=report_id,
        format=format_type,
        requested_by=body.get("requested_by"),
    )
    if export:
        # Mark it completed since we generated it synchronously
        from app.shared.database.supabase_client import get_supabase_client
        from datetime import datetime, timezone
        get_supabase_client().table("report_exports").update({
            "status": "completed", 
            "completed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", export["id"]).execute()
        
    filename = os.path.basename(file_path)
    content_type = "application/pdf"
    if format_type in ["xls", "xlsx", "excel"]:
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif format_type == "csv":
        content_type = "text/csv"

    # Return FileResponse. The BackgroundTask ensures the temp file is deleted after being sent.
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=content_type,
        background=BackgroundTask(os.remove, file_path)
    )


@router.get("/reports/{report_id}/exports")
def list_exports(
    report_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    exports = ReportService.list_exports(report_id, limit=limit, offset=offset)
    return {"status": "ok", "data": exports, "total": len(exports)}

@router.get("/exports/{export_id}")
def get_export(export_id: str):
    try:
        from app.shared.database.supabase_client import get_supabase_client
        result = get_supabase_client().table("report_exports").select("id, report_id, format, status, file_url, requested_at, completed_at").eq("id", export_id).single().execute()
        return {"status": "ok", "data": result.data}
    except Exception as exc:
        return {"status": "error", "message": "Export not found"}

# --- Analytics Component Registry Endpoints ---

@router.get("/analytics-components")
def list_analytics_components(
    group: Optional[str] = Query(default=None, description="Filter by component group (kpis, charts, tables, analytics_widgets)"),
    component_type: Optional[str] = Query(default=None, description="Filter by type (kpi, chart, table, heatmap, pivot, trend)"),
):
    """List all available analytics components for the report builder."""
    if group:
        from app.modules.reporting.analytics.component_registry import get_components_by_group
        components = get_components_by_group(group)
    elif component_type:
        from app.modules.reporting.analytics.component_registry import get_components_by_type
        components = get_components_by_type(component_type)
    else:
        components = get_all_components()
    return {"status": "ok", "data": components, "total": len(components)}


@router.get("/analytics-components/{component_id}")
def get_analytics_component(component_id: str):
    """Get a single analytics component by ID."""
    component = get_component_by_id(component_id)
    if not component:
        return {"status": "error", "message": f"Component '{component_id}' not found"}
    return {"status": "ok", "data": component}


@router.get("/analytics-components/{component_id}/preview")
def preview_analytics_component(
    component_id: str,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    bucket: str = Query(default="month"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get live preview data for an analytics component."""
    params = {
        "date_from": date_from,
        "date_to": date_to,
        "bucket": bucket,
        "limit": limit,
    }
    result = AnalyticsService.get_component_preview(component_id, params)
    if not result:
        return {"status": "error", "message": f"Failed to get preview for component '{component_id}'"}
    return {"status": "ok", "data": result}
