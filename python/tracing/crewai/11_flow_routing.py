#!/usr/bin/env python3
"""CrewAI Flow example using start, listen, router, and and_."""

from __future__ import annotations

from common import print_raw_result, start_respan


def build_incident_routing_flow_class():
    from crewai.flow import Flow, and_, listen, router, start

    class IncidentRoutingFlow(Flow):
        @start()
        def load_incident(self) -> str:
            self.state["service"] = "checkout"
            self.state["severity"] = "critical"
            return "incident_loaded"

        @listen(load_incident)
        def enrich_owner(self) -> str:
            self.state["owner"] = "payments-platform"
            return "owner_enriched"

        @listen(load_incident)
        def enrich_customer_impact(self) -> str:
            self.state["customer_impact"] = True
            return "impact_enriched"

        @listen(and_(enrich_owner, enrich_customer_impact))
        def build_route_context(self) -> str:
            return (
                f"{self.state['service']}:{self.state['severity']}:"
                f"{self.state['owner']}:{self.state['customer_impact']}"
            )

        @router(build_route_context)
        def choose_route(self) -> str:
            if self.state["severity"] == "critical" and self.state["customer_impact"]:
                return "ESCALATE"
            return "LOG_ONLY"

        @listen("ESCALATE")
        def escalate(self) -> str:
            return f"Escalate {self.state['service']} to {self.state['owner']}"

        @listen("LOG_ONLY")
        def log_only(self) -> str:
            return f"Log {self.state['service']} without paging."

    return IncidentRoutingFlow


def main() -> None:
    _, respan = start_respan(
        "crewai-flow-routing",
        metadata={"example": "crewai-flow-routing"},
    )
    try:
        IncidentRoutingFlow = build_incident_routing_flow_class()
        flow = IncidentRoutingFlow(initial_state={})
        result = flow.kickoff()
        print_raw_result("CrewAI flow routing result", result)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
