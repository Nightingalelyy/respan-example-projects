#!/usr/bin/env python3
"""
Multi-Agent Gateway — Multi-agent handoff via Respan gateway.

Demonstrates multiple agents with handoff routing, all API calls
proxied through the Respan gateway with a single API key.
"""

import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, set_default_openai_client

load_dotenv(override=True)

# Route all OpenAI calls through Respan gateway
client = AsyncOpenAI(
    api_key=os.getenv("RESPAN_API_KEY"),
    base_url=os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api"),
)
set_default_openai_client(client)

# Specialized agents
billing_agent = Agent(
    name="Billing Agent",
    instructions="You handle billing and payment questions. Be concise and professional.",
)

technical_agent = Agent(
    name="Technical Agent",
    instructions="You handle technical support questions. Be concise and helpful.",
)

triage_agent = Agent(
    name="Triage Agent",
    instructions=(
        "You are the first point of contact. Route the user to the appropriate agent:\n"
        "- Billing Agent: for payment, invoice, or subscription questions\n"
        "- Technical Agent: for technical issues, bugs, or how-to questions"
    ),
    handoffs=[billing_agent, technical_agent],
)


async def main():
    # This will route through the gateway and trigger a handoff
    result = await Runner.run(
        triage_agent, "I'm having trouble connecting to the API. Can you help?"
    )
    print(f"Handled by: {result.last_agent.name}")
    print(f"Response: {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
