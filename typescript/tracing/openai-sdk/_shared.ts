import { trace } from "@opentelemetry/api";
import { OpenAIInstrumentor } from "@respan/instrumentation-openai";
import { Respan } from "@respan/respan";
import dotenv from "dotenv";
import path from "node:path";
import { fileURLToPath } from "node:url";
import OpenAI from "openai";
import { deterministicFetch, MODEL } from "./_transport.js";

dotenv.config({
  path: path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../../../.env",
  ),
  override: false,
  quiet: true,
});
export const RUN_ID =
  process.env.RESPAN_EXAMPLE_RUN_ID ||
  `openai-ts-${new Date().toISOString().replace(/[-:.]/g, "")}`;
export { MODEL };
export function createRespan(): Respan {
  if (!process.env.RESPAN_API_KEY)
    throw new Error("Set RESPAN_API_KEY in the repository .env or shell.");
  return new Respan({
    apiKey: process.env.RESPAN_API_KEY,
    baseURL: process.env.RESPAN_BASE_URL,
    appName: "openai-sdk-typescript-examples",
    instrumentations: [new OpenAIInstrumentor()],
    logLevel: "error",
    silenceInitializationMessage: true,
  });
}
export function createClient(live = false): OpenAI {
  if (live) {
    if (!process.env.OPENAI_API_KEY)
      throw new Error("Live execution requires OPENAI_API_KEY.");
    return new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
      baseURL: process.env.OPENAI_BASE_URL,
      maxRetries: 0,
    });
  }
  return new OpenAI({
    apiKey: "deterministic-example-key",
    baseURL: "https://openai.example.invalid/v1",
    maxRetries: 0,
    fetch: deterministicFetch,
  });
}
export async function scenario<T>(
  respan: Respan,
  name: string,
  fn: () => Promise<T>,
): Promise<T> {
  return respan.propagateAttributes(
    {
      custom_identifier: `${RUN_ID}:${name}`,
      trace_group_identifier: RUN_ID,
      metadata: {
        integration: "openai",
        language: "typescript",
        run_id: RUN_ID,
        example_run_id: RUN_ID,
        scenario: name,
      },
    },
    () =>
      respan.withWorkflow({ name: `openai_ts_${name}` }, async () => {
        console.log(
          JSON.stringify({
            run_id: RUN_ID,
            scenario: name,
            trace_id: trace.getActiveSpan()?.spanContext().traceId,
          }),
        );
        return fn();
      }),
  );
}
