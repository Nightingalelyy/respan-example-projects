#!/usr/bin/env python3
"""CrewAI multi-agent example with sequential task context passing."""

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

from respan import Respan, workflow  # noqa: E402
from respan_instrumentation_crewai import CrewAIInstrumentor  # noqa: E402


@workflow(name="crewai_multi_agent_sequential")
def run_multi_agent_crew() -> str:
    from crewai import Agent, Crew, Process, Task

    researcher = Agent(
        role="Feature Researcher",
        goal="List practical benefits of tracing CrewAI workflows.",
        backstory="You help engineering teams evaluate observability workflows.",
        llm=RESPAN_MODEL,
        verbose=True,
    )
    writer = Agent(
        role="Release Notes Writer",
        goal="Turn research notes into short release notes.",
        backstory="You write crisp release notes for developer tools.",
        llm=RESPAN_MODEL,
        verbose=True,
    )

    research_task = Task(
        description="List three practical benefits of tracing a CrewAI workflow.",
        expected_output="Three bullet points.",
        agent=researcher,
    )
    writing_task = Task(
        description=(
            "Using the research context, write a two sentence release note "
            "for a CrewAI tracing integration."
        ),
        expected_output="Two concise release-note sentences.",
        agent=writer,
        context=[research_task],
    )

    result = Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        process=Process.sequential,
        verbose=True,
    ).kickoff()
    return result.raw


def main() -> None:
    respan = Respan(
        app_name="crewai-multi-agent-sequential",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        instrumentations=[CrewAIInstrumentor()],
        metadata={"example": "crewai-multi-agent-sequential"},
    )
    try:
        output = run_multi_agent_crew()
        print("\n=== CrewAI multi-agent result ===")
        print(output)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
