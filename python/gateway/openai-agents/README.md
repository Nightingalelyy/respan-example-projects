# OpenAI Agents SDK via Respan Gateway

Route OpenAI Agents SDK API calls through the Respan gateway for centralized API key management, cost tracking, and load balancing.

## How It Works

Instead of calling OpenAI directly, the agents SDK is configured to use the Respan gateway as a proxy:

```python
from openai import AsyncOpenAI
from agents import set_default_openai_client

client = AsyncOpenAI(
    api_key=os.getenv("RESPAN_API_KEY"),
    base_url="https://api.respan.ai/api",
)
set_default_openai_client(client)
```

All agent LLM calls are then routed through the gateway using your single Respan API key.

## Setup

1. Copy `.env.example` to `.env` and add your Respan API key:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies:
   ```bash
   pip install openai-agents python-dotenv
   ```

3. Run an example:
   ```bash
   python basic_gateway.py
   python multi_agent_gateway.py
   ```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `RESPAN_API_KEY` | Your Respan API key | Yes |
| `RESPAN_BASE_URL` | Gateway URL (default: `https://api.respan.ai/api`) | No |
| `PROMPT_ID` | Respan prompt ID (for `prompt_gateway.py`) | No |

## Examples

| File | Description |
|------|-------------|
| `basic_gateway.py` | Simple agent routed through the gateway |
| `multi_agent_gateway.py` | Multi-agent handoff via gateway |
| `prompt_gateway.py` | Prompt management with variables via gateway |
