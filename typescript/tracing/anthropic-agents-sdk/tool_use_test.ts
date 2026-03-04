/**
 * Tool Use — trace agent tool calls through Respan.
 *
 * Runs a query that uses Claude Code's built-in tools (Read, Glob, Grep),
 * then exports the full trace including tool spans.
 *
 * Setup:
 *   npm install (or yarn install)
 *
 * Run:
 *   npx tsx tool_use_test.ts
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
  console.log("Running query with tools (Read, Glob, Grep)...\n");

  if (!API_KEY) {
    throw new Error("Set RESPAN_API_KEY to run this example.");
  }

  const options = exporter.withOptions({
    permissionMode: "bypassPermissions",
    maxTurns: 3,
    allowedTools: ["Read", "Glob", "Grep"],
  } as any);

  const { result, sessionId } = await queryForResult({
    prompt: "List the files in the current directory. Just show filenames.",
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
  console.log("Check Respan traces to see tool spans (Read, Glob, etc.)");
}

main().catch(console.error);
