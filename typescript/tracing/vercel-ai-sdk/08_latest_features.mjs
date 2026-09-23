import assert from "node:assert/strict";
import { generateText, rerank, Output, jsonSchema, tool } from "ai";
import { MockLanguageModelV4, MockRerankingModelV4 } from "ai/test";
import { runVercelCase } from "./vercel-common.mjs";

// SDK test providers make rare content/error/privacy cases deterministic while
// exercising the real SDK telemetry, instrumentation, exporter, and ingestion.
const usage = {
  inputTokens: { total: 12, noCache: 10, cacheRead: 2, cacheWrite: 0 },
  outputTokens: { total: 7, text: 5, reasoning: 2 },
};
const response = {
  content: [
    { type: "reasoning", text: "Fixture reasoning for attachment verification." },
    { type: "text", text: "Fixture answer with an attached image." },
    { type: "file", mediaType: "image/png", data: { type: "data", data: "aGVsbG8=" } },
  ],
  finishReason: { unified: "stop", raw: "stop" },
  usage,
  warnings: [],
};

await runVercelCase("latest_features", async ({ runId, telemetry }) => {
  const result = await generateText({
    model: new MockLanguageModelV4({ modelId: "respan-media-fixture", doGenerate: response }),
    instructions: `System instruction ${runId}: retain the file and reasoning.`,
    messages: [{ role: "user", content: [
      { type: "text", text: `Input attachment ${runId}` },
      { type: "file", mediaType: "image/png", data: Buffer.from("hello") },
    ] }],
    telemetry: telemetry("mixed_media"),
  });
  assert.equal(result.files.length, 1);
  assert.equal(result.reasoningText, "Fixture reasoning for attachment verification.");

  const ranked = await rerank({
    model: new MockRerankingModelV4({ modelId: "respan-rerank-fixture", doRerank: async () => ({
      ranking: [{ index: 1, relevanceScore: 0.9 }, { index: 0, relevanceScore: 0.1 }],
    }) }),
    query: "tracing",
    documents: [`unrelated ${runId}`, `tracing ${runId}`],
    telemetry: telemetry("rerank"),
  });
  assert.equal(ranked.ranking[0].originalIndex, 1);

  const structured = await generateText({
    model: new MockLanguageModelV4({ modelId: "respan-structured-fixture", doGenerate: { ...response, content: [{ type: "text", text: '{"answer":42}' }] } }),
    prompt: `Structured output ${runId}`,
    output: Output.object({ schema: jsonSchema({ type: "object", properties: { answer: { type: "number" } }, required: ["answer"], additionalProperties: false }) }),
    telemetry: telemetry("structured_output"),
  });
  assert.deepEqual(structured.output, { answer: 42 });

  let executed = false;
  const approval = await generateText({
    model: new MockLanguageModelV4({ modelId: "respan-approval-fixture", doGenerate: { ...response, content: [{ type: "tool-call", toolCallId: "approval-call", toolName: "lookup", input: "{}" }], finishReason: { unified: "tool-calls", raw: "tool_calls" } } }),
    prompt: `Tool approval ${runId}`,
    tools: { lookup: tool({ inputSchema: jsonSchema({ type: "object", properties: {} }), execute: async () => { executed = true; return "ok"; } }) },
    toolApproval: { lookup: "user-approval" },
    telemetry: telemetry("tool_approval"),
  });
  assert.equal(executed, false);
  assert.ok(approval.content.some(part => part.type === "tool-approval-request"));

  await generateText({
    model: new MockLanguageModelV4({ modelId: "respan-private-fixture", doGenerate: response }),
    instructions: "PRIVATE_SYSTEM_SENTINEL",
    prompt: "PRIVATE_PROMPT_SENTINEL",
    telemetry: { ...telemetry("private"), recordInputs: false, recordOutputs: false },
  });

  await assert.rejects(generateText({
    model: new MockLanguageModelV4({ modelId: "respan-error-fixture", doGenerate: async () => { throw new Error("Expected SDK fixture error"); } }),
    prompt: `Expected error ${runId}`,
    maxRetries: 0,
    telemetry: telemetry("error"),
  }), /Expected SDK fixture error/);
  console.log("mixed media, reasoning, rerank, content privacy, and expected error completed");
});
