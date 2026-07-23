import os
from dotenv import load_dotenv
from supabase import create_client, Client


# Load .env variables
load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or os.getenv("SUPABASE_KEY")


if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL is missing from .env"
    )

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY is missing from .env")


# Create client once
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


def get_supabase_client() -> Client:
    """
    Returns the initialized Supabase client.
    Used by import scripts and backend services.
    """
    return supabase


print("Supabase connection initialized")