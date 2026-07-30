from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from enum import Enum


class CreationMethod(str, Enum):
    AI_GENERATED = "AI_GENERATED"
    MANUAL_BUILDER = "MANUAL_BUILDER"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SectionType(str, Enum):
    TITLE = "title"
    TEXT = "text"
    KPI = "kpi"
    CHART = "chart"
    TABLE = "table"
    FINANCIAL_SUMMARY = "financial_summary"
    AI_INSIGHT = "ai_insight"
    RECOMMENDATION = "recommendation"
    IMAGE = "image"
    DIVIDER = "divider"
    PAGE_BREAK = "page_break"


class ReportSection(BaseModel):
    id: str
    type: SectionType
    position: int
    config: Dict[str, Any] = {}


class ReportStructureNode(BaseModel):
    id: str
    label: str
    children: Optional[List["ReportStructureNode"]] = None


# Allow recursive model
ReportStructureNode.model_rebuild()


class ReportDefinition(BaseModel):
    id: Optional[str]
    name: str
    description: str = ""
    version: int = 1
    tags: List[str] = []
    owner_id: Optional[str] = None
    source: str = "manual"  # legacy field
    creation_method: CreationMethod = CreationMethod.MANUAL_BUILDER
    status: ReportStatus = ReportStatus.DRAFT
    definition: Dict[str, Any] = {}
    prompt_used: Optional[str] = None
    report_structure: Optional[List[Dict[str, Any]]] = None
    sections: List[Dict[str, Any]] = []
    is_favorite: bool = False


class ReportDefinitionCreate(BaseModel):
    name: str
    description: str = ""
    tags: List[str] = []
    source: str = "manual"
    creation_method: CreationMethod = CreationMethod.MANUAL_BUILDER
    status: ReportStatus = ReportStatus.DRAFT
    definition: Dict[str, Any] = {}
    prompt_used: Optional[str] = None
    report_structure: Optional[List[Dict[str, Any]]] = None
    sections: List[Dict[str, Any]] = []


class ReportDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[ReportStatus] = None
    definition: Optional[Dict[str, Any]] = None
    prompt_used: Optional[str] = None
    report_structure: Optional[List[Dict[str, Any]]] = None
    sections: Optional[List[Dict[str, Any]]] = None
    is_favorite: Optional[bool] = None
    creation_method: Optional[CreationMethod] = None


class AiReportRequest(BaseModel):
    title: str
    objective: str
    audience: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    language: str = "English"
    additional_instructions: Optional[str] = None


class AiReportPreview(BaseModel):
    title: str
    structure: List[Dict[str, Any]]


class ReportVersion(BaseModel):
    id: Optional[str]
    report_id: str
    version_number: int
    definition: Dict[str, Any]
    change_note: str = ""
    created_by: Optional[str] = None


class ReportVersionCreate(BaseModel):
    report_id: str
    version_number: int
    definition: Dict[str, Any]
    change_note: str = ""