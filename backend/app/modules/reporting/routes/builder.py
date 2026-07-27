import logging
from typing import Optional

from fastapi import APIRouter, Query, Request

from app.modules.reporting.services.report_service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/reports")
def list_reports(
    status: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    owner_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    reports = ReportService.list_reports(
        status=status, source=source, owner_id=owner_id, limit=limit, offset=offset
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
    report = ReportService.create_report(body)
    if not report:
        return {"status": "error", "message": "Failed to create report"}
    return {"status": "ok", "data": report}


@router.put("/reports/{report_id}")
async def update_report(report_id: str, request: Request):
    body = await request.json()
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