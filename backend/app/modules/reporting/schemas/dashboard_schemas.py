from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class DashboardSummaryResponse(BaseModel):
    status: str
    data: Dict[str, Any]


class ReportListResponse(BaseModel):
    status: str
    data: List[Dict[str, Any]]


class ReportDetailResponse(BaseModel):
    status: str
    data: Dict[str, Any]