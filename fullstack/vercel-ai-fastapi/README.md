# AI SDK, Next.js, and FastAPI Examples with Respan Telemetry

These examples show you how to use the [AI SDK](https://ai-sdk.dev/docs) with [Next.js](https://nextjs.org), [FastAPI](https://fastapi.tiangolo.com), and [Respan](https://respan.ai) for comprehensive AI observability and tracing.

## How to use

Execute [`create-next-app`](https://github.com/vercel/next.js/tree/canary/packages/create-next-app) with [npm](https://docs.npmjs.com/cli/init), [Yarn](https://yarnpkg.com/lang/en/docs/cli/create/), or [pnpm](https://pnpm.io) to bootstrap the example:

```bash
npx create-next-app --example https://github.com/respanai/respan-example-projects/tree/main/vercel_ai_next_fastapi next-fastapi-app
```

```bash
yarn create next-app --example https://github.com/respanai/respan-example-projects/tree/main/vercel_ai_next_fastapi next-fastapi-app
```

```bash
pnpm create next-app --example https://github.com/respanai/respan-example-projects/tree/main/vercel_ai_next_fastapi next-fastapi-app
```

You will also need [Python 3.6+](https://www.python.org/downloads) and [virtualenv](https://virtualenv.pypa.io/en/latest/installation.html) installed to run the FastAPI server.

## Setup Instructions

### 1. Get API Keys

1. **OpenAI**: Sign up at [OpenAI's Developer Platform](https://platform.openai.com/signup) and get your API key from [the dashboard](https://platform.openai.com/account/api-keys).
2. **Respan**: Sign up at [Respan](https://respan.ai) and get your API key from [API Keys page](https://platform.respan.ai/platform/api/api-keys).

### 2. Environment Configuration

Set the required environment variables as shown in [the example env file](./.env.local.example) but in a new file called `.env.local`:

```bash
cp .env.local.example .env.local
```

Then edit `.env.local` with your actual API keys:

```env
OPENAI_API_KEY=your_openai_api_key_here
RESPAN_API_KEY=your_respan_api_key_here
RESPAN_BASE_URL=https://api.respan.ai/api
```

### 3. Python Environment Setup

```bash
# Create and activate virtual environment
virtualenv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies (includes respan-tracing)
pip install -r requirements.txt
# OR if using Poetry:
poetry install
```

### 4. Node.js Dependencies

```bash
pnpm install
# OR
npm install
# OR
yarn install
```

### 5. Run the Application

```bash
pnpm dev
```

The application will be available at `http://localhost:3000`.

### Add Respan telemetry to trace the LLM calls (`api/index.py`)

The FastAPI backend includes:

```python
from respan_tracing import RespanTelemetry, workflow, get_client

# Initialize telemetry
telemetry = RespanTelemetry()

@workflow(name="stream_text") # <------------------------------------------- Add this decorator here!
async def stream_text(messages: List[ClientMessage], protocol: str = "data"):
    # Automatic tracing of LLM calls and tool usage
    respan_client = get_client()
    respan_client.update_current_span(
        respan_params={
            "metadata": {
                "project": "respan-fastapi-example"
            }
        }
    )
    # ... rest of the implementation
```

## Learn More

To learn more about the technologies used in this example:

- [AI SDK Docs](https://ai-sdk.dev/docs) - AI SDK documentation and reference
- [Vercel AI Playground](https://ai-sdk.dev/playground) - try different models and choose the best one for your use case
- [Next.js Docs](https://nextjs.org/docs) - learn about Next.js features and API
- [FastAPI Docs](https://fastapi.tiangolo.com) - learn about FastAPI features and API
- [Respan Docs](https://docs.respan.ai) - comprehensive AI observability and monitoring
- [Respan Tracing Guide](https://docs.respan.ai/features/monitoring/traces/traces) - detailed tracing setup and usage

## Troubleshooting

### Common Issues

1. **Missing API Keys**: Ensure both `OPENAI_API_KEY` and `RESPAN_API_KEY` are set in `.env.local`
2. **Python Environment**: Make sure you're using Python 3.6+ and have activated your virtual environment
3. **Dependencies**: Run `pip install -r requirements.txt` or `poetry install` to ensure all Python packages are installed
4. **Port Conflicts**: The default port is 3000; change it in `package.json` if needed

### Viewing Traces

1. Go to your [Respan Platform](https://platform.respan.ai/)
2. Navigate to the "Signals" -> "Traces" section
3. Look for traces with the project name "respan-fastapi-example"
4. Click on individual traces to see detailed execution flows

### No Traces Appearing?

If you don't see traces in your Respan dashboard:

1. **Check API Key**: Verify your `RESPAN_API_KEY` is correct
2. **Check Base URL**: Ensure `RESPAN_BASE_URL` is set to `https://api.respan.ai/api`
3. **Network Issues**: Check if your application can reach the Respan API
4. **Wait a moment**: Traces may take a few seconds to appear in the dashboard
5. **Check Console**: Look for any error messages in your terminal or browser console

## Contributing

Feel free to contribute to this example by submitting issues or pull requests to improve the integration between AI SDK, FastAPI, and Respan telemetry.
