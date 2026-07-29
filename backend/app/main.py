from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.copilot.routes.chat import router as copilot_router
from app.modules.copilot.routes.conversations import router as conversations_router
from app.modules.copilot.routes.benchmark import router as benchmark_router
from app.modules.copilot.routes.health import router as copilot_health_router

from app.modules.reporting.routes.reports import router as reporting_router
from app.modules.reporting.routes.dashboard import router as dashboard_router
from app.modules.reporting.routes.analytics import router as analytics_router
from app.modules.reporting.routes.builder import router as builder_router


app = FastAPI(
    title="AI Financial Copilot API",
    description="Intelligent financial assistant",
    version="1.0"
)


origins = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# Copilot API Routes
# =========================

app.include_router(
    copilot_router,
    prefix="/api/copilot",
    tags=["Financial Copilot"]
)

app.include_router(
    conversations_router,
    prefix="/api/copilot",
    tags=["Conversation History"]
)

app.include_router(
    benchmark_router,
    prefix="/api/copilot",
    tags=["Benchmark"]
)

app.include_router(
    copilot_health_router,
    prefix="/api/copilot",
    tags=["Copilot Health"]
)


# =========================
# Reporting API Routes
# =========================

app.include_router(
    reporting_router,
    prefix="/api/reporting",
    tags=["Financial Reporting"]
)

app.include_router(
    dashboard_router,
    prefix="/api/reporting",
    tags=["Reporting Dashboard"]
)

app.include_router(
    analytics_router,
    prefix="/api/reporting/analytics",
    tags=["Analytics Workspace"]
)

app.include_router(
    builder_router,
    prefix="/api/reporting/builder",
    tags=["Report Builder"]
)


# =========================
# Root Health Check
# =========================

@app.get("/")
def home():
    return {
        "message": "AI Financial Copilot API running"
    }