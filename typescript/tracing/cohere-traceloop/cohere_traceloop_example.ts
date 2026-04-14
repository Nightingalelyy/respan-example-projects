/**
 * Cohere — Chat completion with Respan tracing via Traceloop.
 *
 * The cohere-ai SDK sends requests to POST /v1/chat with a Cohere-specific
 * body format: { message, model, stream }.
 *
 * Since we route LLM calls through the Respan gateway (OpenAI format),
 * a local HTTP proxy translates the Cohere chat request to OpenAI and back.
 *
 * The @traceloop/instrumentation-cohere patches CohereClient.prototype.chat
 * (and generate, rerank, etc.) to create Traceloop-format OTel spans.
 */

import "dotenv/config";
import http from "node:http";
import https from "node:https";
import { URL } from "node:url";
import { trace } from "@opentelemetry/api";
import { CohereInstrumentation } from "@traceloop/instrumentation-cohere";
import * as CohereModule from "cohere-ai";
import { CohereClient } from "cohere-ai";
import { Respan } from "@respan/respan";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY!;
const RESPAN_BASE_URL = (
  process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api"
).replace(/\/+$/, "");

// ── 1. Initialize Respan tracing ──────────────────────────────────────
const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
});
await respan.initialize();

// ── 2. Manually instrument cohere-ai ──────────────────────────────────
const instrumentation = new CohereInstrumentation();
instrumentation.setTracerProvider(trace.getTracerProvider());
instrumentation.manuallyInstrument(CohereModule);

// ── 3. Local proxy: Cohere chat → OpenAI → Respan gateway ────────────
function startProxy(targetBase: string, apiKey: string): Promise<string> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const chunks: Buffer[] = [];
      req.on("data", (c: Buffer) => chunks.push(c));
      req.on("end", () => {
        try {
          const body = JSON.parse(Buffer.concat(chunks).toString());

          // Convert Cohere chat → OpenAI messages
          const messages: { role: string; content: string }[] = [];

          // Add chat history if present
          if (body.chat_history?.length) {
            for (const msg of body.chat_history) {
              messages.push({
                role: msg.role === "CHATBOT" ? "assistant" : "user",
                content: msg.message,
              });
            }
          }

          // Add current message
          messages.push({ role: "user", content: body.message });

          const openaiBody = JSON.stringify({
            model: "gpt-4o-mini",
            messages,
            temperature: body.temperature ?? 0,
            max_tokens: body.max_tokens ?? 256,
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

                // Convert OpenAI response → Cohere format
                const cohereResp = {
                  id: openaiResp.id ?? "cohere-proxy",
                  text: choice?.message?.content ?? "",
                  generation_id: openaiResp.id ?? "gen-proxy",
                  chat_history: [
                    { role: "USER", message: body.message },
                    {
                      role: "CHATBOT",
                      message: choice?.message?.content ?? "",
                    },
                  ],
                  finish_reason: "COMPLETE",
                  meta: {
                    api_version: { version: "1" },
                    tokens: {
                      input_tokens:
                        openaiResp.usage?.prompt_tokens ?? 0,
                      output_tokens:
                        openaiResp.usage?.completion_tokens ?? 0,
                    },
                  },
                };

                const payload = JSON.stringify(cohereResp);
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
      (globalThis as any).__cohereProxy = server;
      resolve(`http://localhost:${port}`);
    });
  });
}

const proxyUrl = await startProxy(RESPAN_BASE_URL, RESPAN_API_KEY);

// ── 4. Create Cohere client pointing at local proxy ───────────────────
const cohere = new CohereClient({
  token: RESPAN_API_KEY,
  environment: proxyUrl,
});

const result = await cohere.chat({
  message: "Write a haiku about recursion in programming.",
  model: "command-r-plus",
});

console.log(result.text);

// ── 5. Flush and cleanup ──────────────────────────────────────────────
await respan.flush();
((globalThis as any).__cohereProxy as http.Server).close();
