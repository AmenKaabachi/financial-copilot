import os

class BankMatchConfig:
    """Configuration settings for BankMatch API integration."""
    API_BASE_URL: str = os.getenv("BANKMATCH_API_BASE_URL", "")
    USE_MOCK_DATA: bool = os.getenv("BANKMATCH_USE_MOCK_DATA", "true").lower() in ("true", "1", "t", "yes")

config = BankMatchConfig()
