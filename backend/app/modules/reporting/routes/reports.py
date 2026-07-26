import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def reporting_health():
    """
    Health check for the Financial Reporting module.
    Proves the module is registered and ready.
    """
    return {
        "module": "Financial Reporting & Analytics",
        "status": "ready",
        "version": "1.0",
    }