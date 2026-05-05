#!/usr/bin/env python3
"""CrewAI structured output variants: output_json and response_model."""

from __future__ import annotations

from common import print_raw_result, start_respan

from pydantic import BaseModel, ConfigDict, Field


class OwnerDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str = Field(description="Owning engineering team.")
    severity: str = Field(description="low, medium, high, or critical.")
    notify_customer: bool = Field(description="Whether a customer update is needed.")


def main() -> None:
    settings, respan = start_respan(
        "crewai-output-json-response-model",
        metadata={"example": "crewai-output-json-response-model"},
    )
    try:
        from crewai import Agent, Crew, Task

        agent = Agent(
            role="Structured Decision Maker",
            goal="Return typed incident routing decisions.",
            backstory="You convert incidents into strict handoff fields.",
            llm=settings.model,
            verbose=True,
        )
        json_task = Task(
            description=(
                "Return a structured routing decision for a checkout outage. "
                "Owner must be payments-platform and severity must be critical."
            ),
            expected_output="An OwnerDecision JSON object.",
            agent=agent,
            output_json=OwnerDecision,
        )
        native_task = Task(
            description=(
                "Return a native structured decision for a search latency issue. "
                "Owner must be discovery-platform and severity must be high."
            ),
            expected_output="An OwnerDecision object.",
            agent=agent,
            response_model=OwnerDecision,
        )

        result = Crew(
            agents=[agent],
            tasks=[json_task, native_task],
            verbose=True,
        ).kickoff()

        print_raw_result("CrewAI output_json and response_model result", result)
        print("\n=== Structured task outputs ===")
        for task_output in result.tasks_output:
            if task_output.json_dict is not None:
                print(task_output.json_dict)
            elif task_output.pydantic is not None:
                print(task_output.pydantic.model_dump())
            else:
                print(task_output.raw)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
