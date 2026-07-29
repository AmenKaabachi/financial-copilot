import logging
from typing import Optional

from fastapi import APIRouter, Query, Request

from app.modules.reporting.services.report_service import ReportService

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
    report = ReportService.get_report(report_id)
    if not report:
        return {"status": "error", "message": "Report not found"}
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
    scope: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    templates = ReportService.list_templates(
        category=category, scope=scope, limit=limit, offset=offset
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
    export = ReportService.create_export(
        report_id=report_id,
        format=body.get("format", "pdf"),
        version_id=body.get("version_id"),
        requested_by=body.get("requested_by"),
    )
    if not export:
        return {"status": "error", "message": "Failed to create export job"}
    return {"status": "ok", "data": export}


@router.get("/reports/{report_id}/exports")
def list_exports(
    report_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    exports = ReportService.list_exports(report_id, limit=limit, offset=offset)
    return {"status": "ok", "data": exports, "total": len(exports)}