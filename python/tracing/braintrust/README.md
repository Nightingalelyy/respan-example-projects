# Respan Braintrust Exporter Examples

These examples demonstrate how to use the [respan-exporter-braintrust](https://github.com/respanai/respan/tree/main/python-sdks/respan-exporter-braintrust) to send your Braintrust traces to Respan.

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```
2. Install the required dependencies:
   ```bash
   pip install respan-exporter-braintrust braintrust openai python-dotenv
   ```

## Examples

We provide five examples following our SDK conventions to demonstrate different ways to use the Respan Braintrust integration:

- **`1_hello_world.py`**: Bare minimum sanity check — verifies the integration works and traces are sent to Respan.
- **`2_gateway.py`**: Route LLM calls through Respan proxy (no separate vendor API key) while tracing with Braintrust's `wrap_openai`.
- **`3_tracing.py`**: Demonstrates workflow/task spans with parent and child spans.
- **`4_respan_params.py`**: Shows how to pass Respan-specific metadata like `customer_identifier`, environment, and custom tags.
- **`5_tool_use.py`**: Demonstrates a more complex scenario using OpenAI tool calling wrapped by Braintrust.

