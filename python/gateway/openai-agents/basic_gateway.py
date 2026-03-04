#!/usr/bin/env python3
"""
Basic Gateway — Simple agent via Respan gateway proxy.

Routes OpenAI API calls through the Respan gateway for centralized
API key management, cost tracking, and load balancing.
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

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant. Be concise.",
)


async def main():
    result = await Runner.run(agent, "What are the benefits of using an API gateway?")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
