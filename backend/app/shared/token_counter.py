"""Token counting service using tiktoken for accurate token estimation."""

import logging
from typing import Optional

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logging.warning("tiktoken not available, falling back to character-based estimation")

logger = logging.getLogger(__name__)

# Default encoding for most OpenAI models
DEFAULT_ENCODING = "cl100k_base"


def get_encoding(encoding_name: str = DEFAULT_ENCODING):
    """Get a tiktoken encoding instance."""
    if not TIKTOKEN_AVAILABLE:
        return None
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception as e:
        logger.error(f"Failed to get tiktoken encoding {encoding_name}: {e}")
        return None


def count_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """
    Count tokens in text using tiktoken for accurate estimation.
    
    Falls back to character-based estimation (len(text) // 4) if tiktoken is unavailable.
    
    Args:
        text: The text to count tokens for
        encoding_name: The tiktoken encoding name (default: cl100k_base)
    
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    if TIKTOKEN_AVAILABLE:
        try:
            encoding = get_encoding(encoding_name)
            if encoding:
                return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"tiktoken counting failed, falling back: {e}")
    
    # Fallback to character-based estimation
    return max(1, len(text) // 4)


def count_messages_tokens(messages: list, encoding_name: str = DEFAULT_ENCODING) -> int:
    """
    Count tokens for a list of messages (for chat completions).
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        encoding_name: The tiktoken encoding name
    
    Returns:
        Total token count for all messages
    """
    if not messages:
        return 0
    
    total = 0
    for message in messages:
        content = message.get("content", "")
        role = message.get("role", "")
        # Count both role and content
        total += count_tokens(role, encoding_name)
        total += count_tokens(content, encoding_name)
    
    return total


def estimate_prompt_tokens(
    system_prompt: str = "",
    user_prompt: str = "",
    context: str = "",
    encoding_name: str = DEFAULT_ENCODING,
) -> int:
    """
    Estimate total tokens for a complete prompt.
    
    Args:
        system_prompt: System instructions
        user_prompt: User question/request
        context: Retrieved database context
        encoding_name: The tiktoken encoding name
    
    Returns:
        Total estimated token count
    """
    total = 0
    total += count_tokens(system_prompt, encoding_name)
    total += count_tokens(user_prompt, encoding_name)
    total += count_tokens(context, encoding_name)
    return total


def get_model_context_limit(model_name: str) -> int:
    """
    Get the context limit for a given model.
    
    Args:
        model_name: Name of the model
    
    Returns:
        Maximum context window size in tokens
    """
    # Common model context limits
    MODEL_LIMITS = {
        # Anthropic
        "claude-sonnet": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-opus": 200000,
        "claude-3-haiku": 200000,
        # OpenAI
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-3.5-turbo": 16385,
        "gpt-oss": 32768,       # openai/gpt-oss-20b
        # Google
        "gemma": 8192,           # google/gemma-4-26b-a4b-it, google/gemma-4-31b-it
        # NVIDIA Nemotron
        "nemotron-3-nano": 32768,  # nvidia/nemotron-3-nano-omni-30b-a3b-reasoning, nvidia/nemotron-3-nano-30b-a3b
        "nemotron-nano": 32768,    # nvidia/nemotron-nano-9b-v2
        "nemotron-3-ultra": 131072, # nvidia/nemotron-3-ultra-550b-a55b
        "nemotron-3-super": 131072, # nvidia/nemotron-3-super-120b-a12b
        # Poolside
        "laguna": 32768,         # poolside/laguna-xs-2.1
        # Other common models
        "qwen": 32768,
        "qwen-turbo": 32768,
        "qwen-plus": 32768,
        "qwen-max": 32768,
        "kimi": 131072,
        "moonshot": 131072,
        "llama": 4096,
        "llama-2": 4096,
        "mistral": 32768,
        "mixtral": 32768,
    }
    
    # Try exact match first
    if model_name in MODEL_LIMITS:
        return MODEL_LIMITS[model_name]
    
    # Try partial match (e.g., "gpt-4-turbo-2024-04-09" -> "gpt-4-turbo")
    for key, limit in MODEL_LIMITS.items():
        if key in model_name.lower():
            return limit
    
    # Default conservative limit
    logger.warning(f"Unknown model {model_name}, using default limit of 8192")
    return 8192