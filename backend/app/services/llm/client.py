from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0


load_dotenv()


@lru_cache(maxsize=1)
def get_openrouter_client() -> OpenAI:
    """Create and cache a single OpenRouter client instance for the app process."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing from environment variables")

    base_url = os.getenv("OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL)
    timeout = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
    )
