# Mastra Weather Agent with Respan Observability

A quick setup guide for running a Mastra weather agent with Respan telemetry integration.

## Setup

### 1. Install Dependencies

```bash
pnpm install
```

The project includes the required `@respan/exporter-vercel` package for telemetry export.

### 2. Environment Variables

Copy the example environment file and add your API keys:

```bash
cp .env.local.example .env.local
```

Update `.env.local` with your credentials:

```env
OPENAI_API_KEY=your-openai-api-key
RESPAN_API_KEY=your-respan-api-key
RESPAN_BASE_URL=https://api.respan.ai
```

### 3. Run the Project

```bash
mastra dev
```

This opens the Mastra playground where you can interact with the weather agent.

## Observability

The project is configured with Respan telemetry in `src/mastra/index.ts`:

```typescript
telemetry: {
  serviceName: "keywordai-mastra-example",
  enabled: true,
  export: {
    type: "custom",
    exporter: new RespanExporter({
      apiKey: process.env.RESPAN_API_KEY,
      baseUrl: process.env.RESPAN_BASE_URL,
      debug: true,
    })
  }
}
```

Interact with the agent in the playground and view traces in your Respan dashboard. 