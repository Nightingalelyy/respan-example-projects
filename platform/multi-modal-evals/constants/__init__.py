import os
from dotenv import load_dotenv

load_dotenv(override=True)

RESPAN_BASE_URL = os.getenv("RESPAN_BASE_URL")
RESPAN_API_KEY = os.getenv("RESPAN_API_KEY")
RESPAN_BASE_HEADERS = {
    "Authorization": f"Bearer {RESPAN_API_KEY}",
    "Content-Type": "application/json",
}

EVALUATION_IDENTIFIER = "traveling_agent_eval"
