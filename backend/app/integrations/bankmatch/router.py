from fastapi import APIRouter
from app.integrations.bankmatch.mock_data import BANKMATCH_MOCK_DATA

router = APIRouter()

@router.get("/enterprise-reporting/kpis")
def get_kpis():
    return BANKMATCH_MOCK_DATA["/api/enterprise-reporting/kpis"]

@router.get("/enterprise-reporting/trends")
def get_trends():
    return BANKMATCH_MOCK_DATA["/api/enterprise-reporting/trends"]

@router.get("/enterprise-reporting/match-rate-distribution")
def get_match_rate_distribution():
    return BANKMATCH_MOCK_DATA["/api/enterprise-reporting/match-rate-distribution"]

@router.get("/enterprise-reporting/top-anomalies")
def get_top_anomalies():
    return BANKMATCH_MOCK_DATA["/api/enterprise-reporting/top-anomalies"]

@router.get("/enterprise-reporting/exceptions")
def get_exceptions():
    return BANKMATCH_MOCK_DATA["/api/enterprise-reporting/exceptions"]

@router.get("/enterprise-reporting/exception-aging")
def get_exception_aging():
    return BANKMATCH_MOCK_DATA["/api/enterprise-reporting/exception-aging"]

@router.get("/enterprise-reporting/root-causes")
def get_root_causes():
    return BANKMATCH_MOCK_DATA["/api/enterprise-reporting/root-causes"]

@router.get("/enterprise-reporting/executive-overview")
def get_executive_overview():
    return BANKMATCH_MOCK_DATA["/api/enterprise-reporting/executive-overview"]

@router.get("/dashboard/comptable")
def get_dashboard_comptable():
    return BANKMATCH_MOCK_DATA["/api/dashboard/comptable"]

@router.get("/dashboard/admin")
def get_dashboard_admin():
    return BANKMATCH_MOCK_DATA["/api/dashboard/admin"]
