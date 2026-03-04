/**
 * Hello World — Anthropic Agent SDK + Respan tracing.
 *
 * The simplest possible example: ask Claude a question, see the trace in Respan.
 *
 * Setup:
 *   npm install (or yarn install)
 *
 * Run:
 *   npx tsx hello_world_test.ts
 */

import "dotenv/config";
import { RespanAnthropicAgentsExporter } from "@respan/exporter-anthropic-agents";
import { queryForResult } from "./_sdk_runtime";

const API_KEY = process.env.RESPAN_API_KEY;
const BASE_URL = process.env.RESPAN_BASE_URL;

const exporter = new RespanAnthropicAgentsExporter({
  apiKey: API_KEY ?? undefined,
  endpoint: BASE_URL ? `${BASE_URL.replace(/\/+$/, "")}/v1/traces/ingest` : undefined,
});

async function main(): Promise<void> {
    console.log("Asking Claude a question...\n");

  if (!API_KEY) {
    throw new Error("Set RESPAN_API_KEY to run this example.");
  }

  const options = exporter.withOptions({
    permissionMode: "bypassPermissions",
    maxTurns: 1,
  });

  const { result, sessionId } = await queryForResult({
    prompt: "What is 2 + 2? Reply in one word.",
    options,
    onMessage: async (message, context) => {
      await exporter.trackMessage({ message, sessionId: context.sessionId });
      console.log(`  ${String(message.type ?? "unknown")}`);
    },
  });

  console.log(
    `  Result: subtype=${String(result.subtype)}, turns=${String(result.num_turns)}`,
  );

  console.log(`\nSession: ${sessionId}`);
  console.log("View trace at: https://platform.respan.ai/platform/traces");
}

main().catch(console.error);
