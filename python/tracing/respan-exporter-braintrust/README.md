# Respan Braintrust Exporter Examples

These examples demonstrate how to use the [respan-exporter-braintrust](https://github.com/KeywordsAI/keywordsai/tree/main/python-sdks/respan-exporter-braintrust) to send your Braintrust traces to Respan.

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

- **`basic_usage.py`**: Demonstrates the core setup using the standard Braintrust logger, sending a parent span and a child span manually.
- **`openai_usage.py`**: Demonstrates how to use `wrap_openai` from Braintrust to automatically instrument OpenAI calls and export them to Respan.
