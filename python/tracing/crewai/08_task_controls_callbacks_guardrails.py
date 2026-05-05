#!/usr/bin/env python3
"""CrewAI task controls: async task execution, callbacks, files, and guardrails."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import print_raw_result, start_respan


CALLBACK_EVENTS: list[str] = []
OUTPUT_FILE = Path("/tmp/respan-crewai-task-output.md")


def task_callback(output: Any) -> None:
    raw = getattr(output, "raw", "")
    CALLBACK_EVENTS.append(f"task_callback:{len(raw)}")


def step_callback(step: Any) -> None:
    CALLBACK_EVENTS.append(f"step_callback:{type(step).__name__}")


def must_mention_trace(output: Any):
    raw = getattr(output, "raw", "")
    if "trace" in raw.lower():
        return True, output
    return False, "The answer must mention trace or tracing."


def main() -> None:
    settings, respan = start_respan(
        "crewai-task-controls-callbacks-guardrails",
        metadata={"example": "crewai-task-controls-callbacks-guardrails"},
    )
    try:
        from crewai import Agent, Crew, Task

        writer = Agent(
            role="Async Draft Writer",
            goal="Write short tracing notes.",
            backstory="You draft small operational notes for engineering teams.",
            llm=settings.model,
            verbose=True,
            step_callback=step_callback,
        )
        reviewer = Agent(
            role="Trace Reviewer",
            goal="Ensure output mentions trace observability.",
            backstory="You reject answers that omit tracing context.",
            llm=settings.model,
            verbose=True,
        )

        draft = Task(
            description="Draft a short markdown note about CrewAI observability.",
            expected_output="A markdown note with two bullets.",
            agent=writer,
            async_execution=True,
            markdown=True,
            callback=task_callback,
            output_file=str(OUTPUT_FILE),
        )
        review = Task(
            description=(
                "Review the draft context and return a one sentence final answer "
                "that explicitly mentions trace data."
            ),
            expected_output="One sentence containing the word trace or tracing.",
            agent=reviewer,
            context=[draft],
            guardrail=must_mention_trace,
            guardrail_max_retries=2,
            callback=task_callback,
        )

        result = Crew(
            agents=[writer, reviewer],
            tasks=[draft, review],
            verbose=True,
            task_callback=task_callback,
            step_callback=step_callback,
        ).kickoff()

        print_raw_result("CrewAI task controls result", result)
        print("\n=== Callback events ===")
        for event in CALLBACK_EVENTS:
            print(event)
        print(f"\nTask output file: {OUTPUT_FILE}")
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
