from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def copilot_health():
    return {
        "module": "Financial Copilot",
        "status": "ready",
        "version": "1.0",
    }