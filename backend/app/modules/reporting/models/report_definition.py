from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ReportDefinition(BaseModel):
    id: Optional[str]
    name: str
    description: str = ''
    version: int = 1
    tags: List[str] = []
    owner_id: Optional[str] = None
    source: str = 'manual'
    status: str = 'draft'
    definition: Dict[str, Any] = {}
    is_favorite: bool = False


class ReportDefinitionCreate(BaseModel):
    name: str
    description: str = ''
    tags: List[str] = []
    source: str = 'manual'
    definition: Dict[str, Any] = {}


class ReportDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    is_favorite: Optional[bool] = None


class ReportVersion(BaseModel):
    id: Optional[str]
    report_id: str
    version_number: int
    definition: Dict[str, Any]
    change_note: str = ''
    created_by: Optional[str] = None


class ReportVersionCreate(BaseModel):
    report_id: str
    version_number: int
    definition: Dict[str, Any]
    change_note: str = ''