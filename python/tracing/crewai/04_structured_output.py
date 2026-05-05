#!/usr/bin/env python3
"""CrewAI structured-output example using Task output_pydantic."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


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


class TriageDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: str = Field(description="One of low, medium, high, or critical.")
    owner: str = Field(description="Team that should own the issue.")
    confidence: float = Field(description="Confidence between 0 and 1.")
    next_steps: list[str] = Field(description="Ordered action items.")


def main() -> None:
    respan = Respan(
        app_name="crewai-structured-output",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        instrumentations=[CrewAIInstrumentor()],
        metadata={"example": "crewai-structured-output"},
    )
    try:
        from crewai import Agent, Crew, Task

        agent = Agent(
            role="Incident Classifier",
            goal="Classify incidents into structured handoff data.",
            backstory="You turn short incident notes into typed triage decisions.",
            llm=RESPAN_MODEL,
            verbose=True,
        )
        task = Task(
            description=(
                "Classify this incident: checkout p95 latency is 2400ms in "
                "us-east-1 and retry rate is 3.2 percent. Owner should be "
                "payments-platform."
            ),
            expected_output="A TriageDecision object.",
            agent=agent,
            output_pydantic=TriageDecision,
        )
        result = Crew(agents=[agent], tasks=[task], verbose=True).kickoff()
        structured = result.pydantic
        print("\n=== CrewAI structured output result ===")
        if structured is not None:
            print(structured.model_dump_json(indent=2))
        else:
            print(result.raw)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
