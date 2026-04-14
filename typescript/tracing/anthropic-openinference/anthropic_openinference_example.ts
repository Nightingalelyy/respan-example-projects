/**
 * Anthropic + OpenInference example for Respan tracing.
 *
 * This mirrors the Python example:
 * 1. Initialize RespanTelemetry
 * 2. Activate OpenInferenceInstrumentor(AnthropicInstrumentation)
 * 3. Create and use the Anthropic client normally
 */

import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import Anthropic from "@anthropic-ai/sdk";
import { AnthropicInstrumentation } from "@arizeai/openinference-instrumentation-anthropic";
import { OpenInferenceInstrumentor } from "@respan/instrumentation-openinference";
import { RespanTelemetry, getClient } from "@respan/tracing";
import { config as loadDotenv } from "dotenv";

const __dirname = dirname(fileURLToPath(import.meta.url));
loadDotenv({ path: resolve(__dirname, ".env"), override: false });
loadDotenv({ path: resolve(__dirname, "../../../.env"), override: false });

const RESPAN_API_KEY =
  process.env.RESPAN_GATEWAY_API_KEY ?? process.env.RESPAN_API_KEY;
const RESPAN_BASE_URL = (
  process.env.RESPAN_GATEWAY_BASE_URL ??
  process.env.RESPAN_BASE_URL ??
  "https://api.respan.ai/api"
).replace(/\/+$/, "");
const ANTHROPIC_GATEWAY_URL = `${RESPAN_BASE_URL}/anthropic`;
const ANTHROPIC_MODEL = process.env.ANTHROPIC_MODEL ?? "claude-haiku-4-5";

async function main(): Promise<void> {
  console.log("=".repeat(60));
  console.log("Anthropic OpenInference Example (TypeScript)");
  console.log("=".repeat(60));

  if (!RESPAN_API_KEY) {
    console.log(
      "Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.",
    );
    return;
  }

  const telemetry = new RespanTelemetry({
    appName: "anthropic-openinference-example",
    apiKey: RESPAN_API_KEY,
    baseURL: RESPAN_BASE_URL,
    disabledInstrumentations: ["anthropic"],
    traceContent: true,
    logLevel: "error",
  });
  await telemetry.initialize();

  const anthropicOpenInference = new OpenInferenceInstrumentor(
    AnthropicInstrumentation,
    Anthropic,
  );
  anthropicOpenInference.activate();

  const anthropicClient = new Anthropic({
    apiKey: RESPAN_API_KEY,
    baseURL: ANTHROPIC_GATEWAY_URL,
  });

  try {
    const result = await telemetry.withWorkflow(
      { name: "anthropic_openinference_workflow" },
      async (prompt: string) => {
        const client = getClient();
        client.updateCurrentSpan({
          respanParams: {
            customerIdentifier: "anthropic-openinference-demo",
            metadata: { model: ANTHROPIC_MODEL },
          },
        });

        return telemetry.withTask(
          { name: "anthropic_completion" },
          async (taskPrompt: string) => {
            const response = await anthropicClient.messages.create({
              model: ANTHROPIC_MODEL,
              max_tokens: 120,
              messages: [{ role: "user", content: taskPrompt }],
            });

            const firstBlock = response.content[0];
            return firstBlock?.type === "text" ? firstBlock.text : "";
          },
          prompt,
        );
      },
      "Explain OpenInference tracing for Anthropic in two short sentences.",
    );

    console.log(result);
  } finally {
    await telemetry.shutdown();
    anthropicOpenInference.deactivate();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
