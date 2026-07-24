from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class BenchmarkRequest(BaseModel):
    question: str
    models: List[str]
    max_tokens: Optional[int] = 800
    temperature: Optional[float] = 0.2
    intent: Optional[str] = None

class BenchmarkResult(BaseModel):
    model: str
    provider: str = "OpenRouter"
    answer: str = ""
    status: str = "SUCCESS" # SUCCESS, FAILED, TIMEOUT, RATE_LIMIT
    response_time_ms: float = 0.0
    ttft_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    quality_score: Optional[int] = 0
    error: Optional[str] = None

class BenchmarkRanking(BaseModel):
    fastest_model: Optional[str] = None
    best_latency_model: Optional[str] = None
    best_quality_model: Optional[str] = None
    most_efficient_model: Optional[str] = None
    most_reliable_model: Optional[str] = None
    recommended_production_model: Optional[str] = None

class BenchmarkResponse(BaseModel):
    question: str
    intent: str
    results: List[BenchmarkResult]
    rankings: Optional[BenchmarkRanking] = None
