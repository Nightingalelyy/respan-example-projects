/**
 * AWS Bedrock — Chat completion with Respan tracing via OpenInference.
 *
 * The @aws-sdk/client-bedrock-runtime SDK sends requests to
 *   https://bedrock-runtime.{region}.amazonaws.com/model/{modelId}/converse
 *
 * Since we route LLM calls through the Respan gateway (OpenAI format),
 * a local HTTP proxy translates the Bedrock Converse API to OpenAI and back.
 *
 * The @arizeai/openinference-instrumentation-bedrock patches
 * BedrockRuntimeClient.prototype.send to create OpenInference-format spans.
 */

import "dotenv/config";
import http from "node:http";
import https from "node:https";
import { URL } from "node:url";
import { trace } from "@opentelemetry/api";
import { BedrockInstrumentation } from "@arizeai/openinference-instrumentation-bedrock";
import * as BedrockModule from "@aws-sdk/client-bedrock-runtime";
import {
  BedrockRuntimeClient,
  ConverseCommand,
} from "@aws-sdk/client-bedrock-runtime";
import { Respan } from "@respan/respan";
import { OpenInferenceInstrumentor } from "@respan/instrumentation-openinference";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY!;
const RESPAN_BASE_URL = (
  process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api"
).replace(/\/+$/, "");

// ── 1. Initialize Respan tracing with OpenInference instrumentor ──────
const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
  instrumentations: [
    new OpenInferenceInstrumentor(BedrockInstrumentation),
  ],
});
await respan.initialize();

// ── 2. Manually instrument @aws-sdk/client-bedrock-runtime ────────────
const bedrockInst = new BedrockInstrumentation();
bedrockInst.setTracerProvider(trace.getTracerProvider());
bedrockInst.manuallyInstrument(BedrockModule);

// ── 3. Local proxy: Bedrock Converse → OpenAI → Respan gateway ───────
function startProxy(targetBase: string, apiKey: string): Promise<string> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const chunks: Buffer[] = [];
      req.on("data", (c: Buffer) => chunks.push(c));
      req.on("end", () => {
        try {
          const body = JSON.parse(Buffer.concat(chunks).toString());

          // Convert Bedrock Converse messages → OpenAI messages
          const messages = (body.messages ?? []).map(
            (m: { role: string; content: { text: string }[] }) => ({
              role: m.role === "assistant" ? "assistant" : "user",
              content:
                m.content
                  ?.map((c: { text?: string }) => c.text)
                  .filter(Boolean)
                  .join("") ?? "",
            })
          );

          // Add system message if present
          if (body.system?.length) {
            messages.unshift({
              role: "system",
              content: body.system
                .map((s: { text?: string }) => s.text)
                .filter(Boolean)
                .join("\n"),
            });
          }

          const openaiBody = JSON.stringify({
            model: "gpt-4o-mini",
            messages,
            temperature:
              body.inferenceConfig?.temperature ?? 0,
            max_tokens:
              body.inferenceConfig?.maxTokens ?? 256,
          });

          const target = new URL(`${targetBase}/chat/completions`);
          const options: https.RequestOptions = {
            hostname: target.hostname,
            port:
              target.port ||
              (target.protocol === "https:" ? 443 : 80),
            path: target.pathname,
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Content-Length": Buffer.byteLength(openaiBody),
              Authorization: `Bearer ${apiKey}`,
            },
          };

          const transport =
            target.protocol === "https:" ? https : http;
          const upstream = transport.request(options, (upRes) => {
            const respChunks: Buffer[] = [];
            upRes.on("data", (c: Buffer) => respChunks.push(c));
            upRes.on("end", () => {
              try {
                const openaiResp = JSON.parse(
                  Buffer.concat(respChunks).toString()
                );
                const choice = openaiResp.choices?.[0];

                // Convert OpenAI response → Bedrock Converse format
                const bedrockResp = {
                  output: {
                    message: {
                      role: "assistant",
                      content: [
                        {
                          text: choice?.message?.content ?? "",
                        },
                      ],
                    },
                  },
                  stopReason: "end_turn",
                  usage: {
                    inputTokens:
                      openaiResp.usage?.prompt_tokens ?? 0,
                    outputTokens:
                      openaiResp.usage?.completion_tokens ?? 0,
                    totalTokens:
                      openaiResp.usage?.total_tokens ?? 0,
                  },
                  metrics: {
                    latencyMs: 0,
                  },
                };

                const payload = JSON.stringify(bedrockResp);
                res.writeHead(200, {
                  "Content-Type": "application/json",
                });
                res.end(payload);
              } catch {
                res.writeHead(502);
                res.end(
                  JSON.stringify({
                    error: "Failed to parse upstream response",
                  })
                );
              }
            });
          });
          upstream.on("error", (e) => {
            res.writeHead(502);
            res.end(JSON.stringify({ error: e.message }));
          });
          upstream.write(openaiBody);
          upstream.end();
        } catch {
          res.writeHead(400);
          res.end(JSON.stringify({ error: "Bad request" }));
        }
      });
    });

    server.listen(0, () => {
      const port = (server.address() as any).port;
      (globalThis as any).__bedrockProxy = server;
      resolve(`http://localhost:${port}`);
    });
  });
}

const proxyUrl = await startProxy(RESPAN_BASE_URL, RESPAN_API_KEY);

// ── 4. Create Bedrock client pointing at local proxy ──────────────────
const client = new BedrockRuntimeClient({
  region: "us-east-1",
  endpoint: proxyUrl,
  credentials: {
    accessKeyId: "proxy-passthrough",
    secretAccessKey: "proxy-passthrough",
  },
});

const command = new ConverseCommand({
  modelId: "anthropic.claude-3-haiku-20240307-v1:0",
  messages: [
    {
      role: "user",
      content: [
        { text: "Write a haiku about recursion in programming." },
      ],
    },
  ],
  inferenceConfig: {
    temperature: 0,
    maxTokens: 256,
  },
});

const result = await client.send(command);

const responseText = result.output?.message?.content
  ?.map((c) => c.text)
  .join("");
console.log(responseText);

// ── 5. Flush and cleanup ──────────────────────────────────────────────
await respan.flush();
((globalThis as any).__bedrockProxy as http.Server).close();
