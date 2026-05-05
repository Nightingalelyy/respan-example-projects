#!/usr/bin/env python3
"""CrewAI complex edge cases with local Respan instrumentation.

This example exercises a multi-agent CrewAI workflow with tool calls, nested
tool payloads, empty outputs, long-ish text, structured task output, and Respan
workflow/task decorators. LLM calls are routed through the Respan gateway and
CrewAI spans are captured by the local ``respan-instrumentation-crewai`` package.

Run:
    python complex_edge_cases.py
"""

from __future__ import annotations

import json
import os
import uuid
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
RUN_ID = os.getenv("RESPAN_CREWAI_RUN_ID", f"crewai-{uuid.uuid4().hex[:12]}")
CUSTOM_PARAMS = {
    "customer_identifier": f"crewai-customer-{RUN_ID}",
    "customer_email": f"crewai+{RUN_ID}@example.com",
    "customer_name": "CrewAI Complex Params",
    "thread_identifier": f"crewai-thread-{RUN_ID}",
    "custom_identifier": f"crewai-custom-{RUN_ID}",
    "trace_group_identifier": f"crewai-trace-group-{RUN_ID}",
    "evaluation_identifier": f"crewai-eval-{RUN_ID}",
    "environment": "test",
    "metadata": {
        "custom_params_case": "crewai-complex-edge-cases",
        "custom_params_run_id": RUN_ID,
        "custom_params_plan": "enterprise",
    },
}

os.environ["OPENAI_API_KEY"] = RESPAN_API_KEY
os.environ["OPENAI_BASE_URL"] = RESPAN_BASE_URL
os.environ.setdefault("CREWAI_TRACING_ENABLED", "true")

from respan import Respan, task, workflow  # noqa: E402
from respan_instrumentation_crewai import CrewAIInstrumentor  # noqa: E402


respan = Respan(
    app_name="crewai-complex-edge-cases",
    api_key=RESPAN_API_KEY,
    base_url=RESPAN_BASE_URL,
    instrumentations=[
        CrewAIInstrumentor(
            use_event_listener=True,
            create_llm_spans=True,
        )
    ],
    metadata={
        "example": "crewai-complex-edge-cases",
        "run_id": RUN_ID,
        "instrumentation": "local-respan-instrumentation-crewai",
    },
)

from crewai import Agent, Crew, Process, Task  # noqa: E402
from crewai.tools import tool  # noqa: E402


class EvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_from_runbook: str = Field(description="Owner returned by the runbook tool.")
    peak_p95_ms: int = Field(description="Highest p95 latency from the metrics tool.")
    retry_rate: float = Field(description="Observed retry rate for the degraded region.")
    empty_context_seen: bool = Field(description="Whether the empty-context tool was used.")
    tools_used: list[str] = Field(description="CrewAI tools used by the triage agent.")
    notable_payloads: list[str] = Field(description="Short notes about unusual payloads.")


class IncidentBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: str = Field(description="One of low, medium, high, or critical.")
    owner: str = Field(description="Team that should own the incident.")
    customer_impact: str = Field(description="One sentence impact summary.")
    next_steps: list[str] = Field(description="Ordered mitigation steps.")
    evidence: EvidenceSummary = Field(description="Tool evidence used by the crew.")


@tool("incident_runbook_lookup")
def incident_runbook_lookup(service: str) -> str:
    """Return runbook guidance for a service."""
    runbooks = {
        "checkout": {
            "owner": "payments-platform",
            "severity": "high",
            "threshold": "p95 latency > 2s for 5m",
            "steps": [
                "shift traffic from the degraded region",
                "disable non-critical recommendations",
                "page the database on-call",
            ],
        },
        "billing": {
            "owner": "finance-systems",
            "severity": "medium",
            "threshold": "retry rate > 2 percent",
            "steps": ["reconcile provider errors", "inspect queue lag"],
        },
    }
    return json.dumps(runbooks.get(service, runbooks["checkout"]), sort_keys=True)


@tool("service_metrics_snapshot")
def service_metrics_snapshot(service: str) -> str:
    """Return nested metrics with unusual but serializable payload shapes."""
    payload = {
        "service": service,
        "window": "2026-05-03T08:00:00Z/2026-05-03T08:05:00Z",
        "regions": [
            {"name": "us-east-1", "p95_ms": 2380, "retry_rate": 0.034},
            {"name": "us-west-2", "p95_ms": 820, "retry_rate": 0.006},
        ],
        "labels": ["unicode-check", "checkout", "failover"],
        "note": "escaped unicode: \\u4f60\\u597d, newline\\ninside payload",
    }
    return json.dumps(payload, sort_keys=True)


@tool("empty_context_lookup")
def empty_context_lookup(topic: str) -> str:
    """Return an empty string to verify blank tool outputs do not break spans."""
    return ""


@tool("long_customer_digest")
def long_customer_digest(topic: str) -> str:
    """Return a larger text payload to exercise span output serialization."""
    sentence = (
        f"{topic}: checkout latency is elevated, retries are visible, "
        "and customer-facing payment confirmation is delayed. "
    )
    return sentence * 12


@task(name="build_crewai_complex_crew")
def build_crew() -> Crew:
    triage_agent = Agent(
        role="Incident Triage Specialist",
        goal=(
            "Classify checkout incidents using every available tool before "
            "handing evidence to the incident writer."
        ),
        backstory=(
            "You run production triage for commerce systems and keep compact, "
            "evidence-backed handoffs."
        ),
        tools=[
            incident_runbook_lookup,
            service_metrics_snapshot,
            empty_context_lookup,
            long_customer_digest,
        ],
        llm=RESPAN_MODEL,
        verbose=True,
    )
    writer_agent = Agent(
        role="Incident Communications Writer",
        goal="Convert triage evidence into a structured incident brief.",
        backstory="You write concise incident updates for support and engineering.",
        llm=RESPAN_MODEL,
        verbose=True,
    )

    triage_task = Task(
        description=(
            "Investigate checkout latency in us-east-1. You must call "
            "incident_runbook_lookup with checkout, service_metrics_snapshot "
            "with checkout, empty_context_lookup with checkout, and "
            "long_customer_digest with checkout. Return the evidence and a "
            "recommended owner."
        ),
        expected_output=(
            "A compact triage handoff with severity, owner, and evidence from "
            "each required tool."
        ),
        agent=triage_agent,
    )
    brief_task = Task(
        description=(
            "Create a structured incident brief from the triage handoff. "
            "Use severity high if checkout p95 latency exceeds 2 seconds. "
            "Include customer impact and ordered next steps."
        ),
        expected_output="A structured IncidentBrief object.",
        agent=writer_agent,
        context=[triage_task],
        output_pydantic=IncidentBrief,
    )

    return Crew(
        agents=[triage_agent, writer_agent],
        tasks=[triage_task, brief_task],
        process=Process.sequential,
        verbose=True,
    )


@workflow(name="crewai_complex_edge_cases")
def run_crewai_complex_edge_cases() -> IncidentBrief | str:
    crew = build_crew()
    result = crew.kickoff(
        inputs={
            "incident": "checkout latency in us-east-1 with elevated retries",
            "run_id": RUN_ID,
        }
    )
    raw = result.pydantic or result.raw
    print("\n=== CrewAI complex edge case result ===")
    if isinstance(raw, BaseModel):
        print(raw.model_dump_json(indent=2))
    else:
        print(raw)
    return raw


def main() -> None:
    try:
        print("\n=== CrewAI custom params expectation ===")
        print(json.dumps(CUSTOM_PARAMS, indent=2, sort_keys=True))
        with respan.propagate_attributes(**CUSTOM_PARAMS):
            run_crewai_complex_edge_cases()
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
