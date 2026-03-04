/**
 * Gateway Integration — route through Respan, no Anthropic key needed.
 *
 * The Respan gateway proxies Claude API calls, so you only need a single
 * Respan API key for both the LLM call and trace export.
 *
 * Setup:
 *   npm install (or yarn install)
 *
 * Environment:
 *   RESPAN_API_KEY=your_key    # only key needed
 *
 * Run:
 *   npx tsx gateway_test.ts
 */

import "dotenv/config";
import { RespanAnthropicAgentsExporter } from "@respan/exporter-anthropic-agents";
import { queryForResult } from "./_sdk_runtime";

const API_KEY = process.env.RESPAN_API_KEY;
const BASE_URL = (
  process.env.RESPAN_GATEWAY_BASE_URL ||
  process.env.RESPAN_BASE_URL ||
  "https://api.respan.ai/api"
).replace(/\/+$/, "");
const QUERY_TIMEOUT_SECONDS = Number.parseInt(
  process.env.RESPAN_GATEWAY_QUERY_TIMEOUT_SECONDS ??
    process.env.RESPAN_QUERY_TIMEOUT_SECONDS ??
    "90",
  10,
);

if (!API_KEY) {
  console.error("ERROR: Set RESPAN_API_KEY (or RESPAN_API_KEY)");
  process.exit(1);
}

const exporter = new RespanAnthropicAgentsExporter({
  apiKey: API_KEY,
  endpoint: `${BASE_URL}/v1/traces/ingest`,
});

async function probeGateway(gatewayUrl: string): Promise<void> {
  const probeUrl = `${gatewayUrl}/v1/messages`;
  try {
    const response = await fetch(probeUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": API_KEY!,
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-5",
        max_tokens: 8,
        messages: [{ role: "user", content: "ping" }],
      }),
    });

    const bodyText = await response.text();
    const preview = bodyText.slice(0, 400).replace(/\n/g, " ");
    console.log(`Gateway probe -> ${response.status} ${response.statusText}: ${preview}`);
  } catch (error) {
    console.log(`Gateway probe failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function main(): Promise<void> {
  console.log(`Gateway: ${BASE_URL}`);
  console.log(`API key: ${API_KEY!.slice(0, 8)}...\n`);

  // Route Claude SDK through the Respan gateway — same key for auth + tracing
  // The Anthropic SDK appends /v1/messages to ANTHROPIC_BASE_URL,
  // so we point it at the /anthropic passthrough path.
  const gatewayUrl = `${BASE_URL}/anthropic`;
  const options = exporter.withOptions({
    permissionMode: "bypassPermissions",
    maxTurns: 1,
    env: {
      ...process.env,
      ANTHROPIC_BASE_URL: gatewayUrl,
      ANTHROPIC_AUTH_TOKEN: API_KEY,
      ANTHROPIC_API_KEY: API_KEY,
    },
  } as any);

  try {
    const { result, sessionId } = await queryForResult({
      prompt: "Reply with exactly: gateway_ok",
      options,
      timeoutSeconds: QUERY_TIMEOUT_SECONDS,
      onMessage: async (message, context) => {
        await exporter.trackMessage({ message, sessionId: context.sessionId });
        console.log(`  ${String(message.type ?? "unknown")}`);
      },
    });

    const usage = result.usage as Record<string, unknown> | undefined;
    console.log(
      `  Result: subtype=${String(result.subtype)}, turns=${String(result.num_turns)}`,
    );
    if (usage) {
      console.log(`  Usage: input=${usage.input_tokens}, output=${usage.output_tokens}`);
    }

    console.log(`\nSession: ${sessionId}`);
    console.log("View trace at: https://platform.respan.ai/platform/traces");
  } catch (err) {
    console.error(
      `Gateway query failed: ${err instanceof Error ? err.message : String(err)}`,
    );
    await probeGateway(gatewayUrl);
    throw err;
  }
}

main().catch(console.error);
