from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import copilot
from app.routes import conversations

app = FastAPI(
    title="AI Financial Copilot API",
    description="Intelligent financial assistant",
    version="1.0"
)

# Allow Angular frontend
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
    copilot.router,
    prefix="/copilot",
    tags=["Financial Copilot"]
)

app.include_router(
    conversations.router,
    prefix="/copilot",
    tags=["Conversation History"]
)

@app.get("/")
def home():
    return {
        "message": "AI Financial Copilot API running"
    }