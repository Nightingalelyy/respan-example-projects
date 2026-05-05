#!/usr/bin/env python3
"""CrewAI tool-use example: an agent must call a Python tool."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv


def load_env() -> None:
    current_dir = Path(__file__).resolve().parent
    candidates = [
        current_dir / ".env",
        current_dir.parents[2] / ".env",
        current_dir.parents[3] / "respan" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=True)
            return
    load_dotenv(override=True)


load_env()

RESPAN_API_KEY = os.environ["RESPAN_API_KEY"]
RESPAN_BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
RESPAN_MODEL = os.getenv("RESPAN_MODEL", "gpt-4o-mini")

os.environ["OPENAI_API_KEY"] = RESPAN_API_KEY
os.environ["OPENAI_BASE_URL"] = RESPAN_BASE_URL
os.environ.setdefault("XDG_DATA_HOME", "/tmp/respan-crewai-data")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "true")

from respan import Respan  # noqa: E402
from respan_instrumentation_crewai import CrewAIInstrumentor  # noqa: E402


def main() -> None:
    respan = Respan(
        app_name="crewai-tool-use",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        instrumentations=[CrewAIInstrumentor()],
        metadata={"example": "crewai-tool-use"},
    )
    try:
        from crewai import Agent, Crew, Task
        from crewai.tools import tool

        @tool("lookup_service_owner")
        def lookup_service_owner(service: str) -> str:
            """Return an owner and escalation policy for a service."""
            owners = {
                "checkout": {
                    "owner": "payments-platform",
                    "escalation": "page checkout-primary",
                },
                "search": {
                    "owner": "discovery-platform",
                    "escalation": "page search-primary",
                },
            }
            return json.dumps(owners.get(service, owners["checkout"]), sort_keys=True)

        agent = Agent(
            role="Service Ownership Router",
            goal="Use tools to identify the right service owner.",
            backstory="You route incidents to teams using service ownership data.",
            tools=[lookup_service_owner],
            llm=RESPAN_MODEL,
            verbose=True,
        )
        task = Task(
            description=(
                "Call lookup_service_owner with checkout. Return the owner and "
                "escalation policy exactly from the tool result."
            ),
            expected_output="Owner and escalation policy for checkout.",
            agent=agent,
        )
        result = Crew(agents=[agent], tasks=[task], verbose=True).kickoff()
        print("\n=== CrewAI tool-use result ===")
        print(result.raw)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
