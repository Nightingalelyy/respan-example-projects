#!/usr/bin/env python3
"""Bare-minimum CrewAI sanity check: one agent, one task, one crew."""

from __future__ import annotations

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
        app_name="crewai-hello-world",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        instrumentations=[CrewAIInstrumentor()],
        metadata={"example": "crewai-hello-world"},
    )
    try:
        from crewai import Agent, Crew, Task

        agent = Agent(
            role="Product Explainer",
            goal="Explain one CrewAI concept clearly.",
            backstory="You write concise onboarding notes for engineers.",
            llm=RESPAN_MODEL,
            verbose=False,
        )
        task = Task(
            description="Explain what a CrewAI Agent does in one sentence.",
            expected_output="One sentence.",
            agent=agent,
        )
        result = Crew(agents=[agent], tasks=[task], verbose=False).kickoff()
        print("\n=== CrewAI hello world result ===")
        print(result.raw)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
