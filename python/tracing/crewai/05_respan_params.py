#!/usr/bin/env python3
"""CrewAI example showing Respan custom params propagation."""

from __future__ import annotations

import json
import os
import uuid
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
RUN_ID = os.getenv("RESPAN_CREWAI_RUN_ID", f"crewai-params-{uuid.uuid4().hex[:8]}")

os.environ["OPENAI_API_KEY"] = RESPAN_API_KEY
os.environ["OPENAI_BASE_URL"] = RESPAN_BASE_URL
os.environ.setdefault("XDG_DATA_HOME", "/tmp/respan-crewai-data")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "true")

from respan import Respan  # noqa: E402
from respan_instrumentation_crewai import CrewAIInstrumentor  # noqa: E402


CUSTOM_PARAMS = {
    "customer_identifier": f"customer-{RUN_ID}",
    "customer_email": f"crewai+{RUN_ID}@example.com",
    "customer_name": "CrewAI Example Customer",
    "thread_identifier": f"thread-{RUN_ID}",
    "custom_identifier": f"custom-{RUN_ID}",
    "trace_group_identifier": f"trace-group-{RUN_ID}",
    "evaluation_identifier": f"eval-{RUN_ID}",
    "environment": "test",
    "metadata": {
        "example": "crewai-respan-params",
        "run_id": RUN_ID,
        "plan": "example",
    },
}


def main() -> None:
    respan = Respan(
        app_name="crewai-respan-params",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        instrumentations=[CrewAIInstrumentor()],
        metadata={"example": "crewai-respan-params", "run_id": RUN_ID},
    )
    try:
        from crewai import Agent, Crew, Task

        agent = Agent(
            role="Customer Support Assistant",
            goal="Write short customer-facing updates.",
            backstory="You explain operational updates in clear language.",
            llm=RESPAN_MODEL,
            verbose=False,
        )
        task = Task(
            description=(
                "Write a two sentence customer update for a checkout latency "
                "incident that is being mitigated."
            ),
            expected_output="Two customer-facing sentences.",
            agent=agent,
        )
        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        print("\n=== Expected Respan params ===")
        print(json.dumps(CUSTOM_PARAMS, indent=2, sort_keys=True))
        with respan.propagate_attributes(**CUSTOM_PARAMS):
            result = crew.kickoff()

        print("\n=== CrewAI Respan params result ===")
        print(result.raw)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
