#!/usr/bin/env python3
"""CrewAI knowledge source and memory example."""

from __future__ import annotations

from common import print_raw_result, start_respan


def main() -> None:
    settings, respan = start_respan(
        "crewai-knowledge-and-memory",
        metadata={"example": "crewai-knowledge-and-memory"},
    )
    try:
        from crewai import Agent, Crew, Task
        from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

        policy_source = StringKnowledgeSource(
            content=(
                "Checkout incidents are owned by payments-platform. "
                "Search incidents are owned by discovery-platform. "
                "Critical customer-facing incidents require a status-page update."
            )
        )
        agent = Agent(
            role="Policy-Aware Incident Assistant",
            goal="Answer ownership questions using attached knowledge.",
            backstory="You use local policy snippets before answering.",
            llm=settings.model,
            knowledge_sources=[policy_source],
            memory=True,
            verbose=True,
        )
        task = Task(
            description=(
                "Using the knowledge source, identify the owner for a checkout "
                "incident and whether a status-page update is required."
            ),
            expected_output="Owner and status-page decision.",
            agent=agent,
        )
        result = Crew(
            agents=[agent],
            tasks=[task],
            knowledge_sources=[policy_source],
            memory=True,
            verbose=True,
        ).kickoff()

        print_raw_result("CrewAI knowledge and memory result", result)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
