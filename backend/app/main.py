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

app.include_router(
    copilot_router,
    prefix="/copilot",
    tags=["Financial Copilot"]
)

app.include_router(
    conversations_router,
    prefix="/copilot",
    tags=["Conversation History"]
)

app.include_router(
    benchmark_router,
    prefix="/copilot",
    tags=["Benchmark"]
)

app.include_router(
    copilot_health_router,
    prefix="/copilot",
    tags=["Copilot Health"]
)

app.include_router(
    reporting_router,
    prefix="/reporting",
    tags=["Financial Reporting"]
)

app.include_router(
    dashboard_router,
    prefix="/reporting",
    tags=["Reporting Dashboard"]
)

app.include_router(
    analytics_router,
    prefix="/reporting/analytics",
    tags=["Analytics Workspace"]
)

app.include_router(
    builder_router,
    prefix="/reporting/builder",
    tags=["Report Builder"]
)

@app.get("/")
def home():
    return {
        "message": "AI Financial Copilot API running"
    }