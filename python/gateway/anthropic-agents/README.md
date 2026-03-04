# Claude Agent SDK via Respan Gateway

Route Claude Agent SDK API calls through the Respan gateway — only a single `RESPAN_API_KEY` is needed for both the LLM call and trace export. No Anthropic API key required.

## How It Works

The Anthropic SDK appends `/v1/messages` to `ANTHROPIC_BASE_URL`, so point it at the gateway's `/anthropic` passthrough path:

```python
gateway_url = f"{BASE_URL}/anthropic"
# Final URL: https://api.respan.ai/api/anthropic/v1/messages

options = ClaudeAgentOptions(
    env={
        "ANTHROPIC_BASE_URL": gateway_url,
        "ANTHROPIC_AUTH_TOKEN": RESPAN_API_KEY,
        "ANTHROPIC_API_KEY": RESPAN_API_KEY,
    },
)
```

## Setup

1. Copy `.env.example` to `.env` and add your Respan API key:
   ```bash
   cp .env.example .env
   ```

2. Install dependencies:
   ```bash
   pip install claude-agent-sdk respan-exporter-anthropic-agents python-dotenv
   ```

3. Run an example:
   ```bash
   python basic_gateway.py
   python tool_use_gateway.py
   ```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `RESPAN_API_KEY` | Your Respan API key (used for both gateway and tracing) | Yes |
| `RESPAN_BASE_URL` | Gateway URL (default: `https://api.respan.ai/api`) | No |

## Examples

| File | Description |
|------|-------------|
| `basic_gateway.py` | Simple agent query routed through the gateway |
| `tool_use_gateway.py` | Agent with tools (Read, Glob, Grep) via gateway |
