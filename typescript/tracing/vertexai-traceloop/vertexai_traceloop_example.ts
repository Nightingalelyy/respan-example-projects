/**
 * Vertex AI — Chat completion with Respan tracing via Traceloop.
 *
 * The @google-cloud/vertexai SDK sends requests to Google's Vertex AI
 * endpoint format:
 *   https://{region}-aiplatform.googleapis.com/v1/{resourcePath}:generateContent
 *
 * Since we route LLM calls through the Respan gateway (OpenAI format),
 * a local HTTPS proxy translates Vertex AI requests to OpenAI format and back.
 * (The SDK always uses https://, so the proxy must serve TLS with a self-signed cert.)
 *
 * The @traceloop/instrumentation-vertexai patches
 * GenerativeModel.generateContent and GenerativeModel.generateContentStream
 * to create Traceloop-format OTel spans.
 */

import "dotenv/config";
import { execSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import { URL } from "node:url";
import { trace } from "@opentelemetry/api";
import { VertexAIInstrumentation } from "@traceloop/instrumentation-vertexai";
import * as VertexAIModule from "@google-cloud/vertexai";
import { VertexAI } from "@google-cloud/vertexai";
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

// ── 2. Manually instrument @google-cloud/vertexai ─────────────────────
const instrumentation = new VertexAIInstrumentation();
instrumentation.setTracerProvider(trace.getTracerProvider());
instrumentation.manuallyInstrument(VertexAIModule);

// ── 3. Local HTTPS proxy: Vertex AI → OpenAI → Respan gateway ────────
function startProxy(targetBase: string, apiKey: string): Promise<string> {
  return new Promise((resolve) => {
    const keyFile = `/tmp/vertexai-proxy-key-${process.pid}.pem`;
    const certFile = `/tmp/vertexai-proxy-cert-${process.pid}.pem`;

    execSync(
      `openssl req -x509 -newkey rsa:2048 -keyout ${keyFile} -out ${certFile} -days 1 -nodes -subj "/CN=localhost" 2>/dev/null`
    );
    const key = fs.readFileSync(keyFile, "utf8");
    const cert = fs.readFileSync(certFile, "utf8");
    fs.unlinkSync(keyFile);
    fs.unlinkSync(certFile);

    const server = https.createServer({ key, cert }, (req, res) => {
      const chunks: Buffer[] = [];
      req.on("data", (c: Buffer) => chunks.push(c));
      req.on("end", () => {
        const body = JSON.parse(Buffer.concat(chunks).toString());

        // Convert Vertex AI contents → OpenAI messages
        const messages = (body.contents ?? []).map(
          (c: { role: string; parts: { text: string }[] }) => ({
            role: c.role === "model" ? "assistant" : c.role,
            content: c.parts?.map((p: { text: string }) => p.text).join("") ?? "",
          })
        );

        // Route through an OpenAI model the gateway supports.
        // The instrumentation still records the original Vertex AI model name.
        const openaiBody = JSON.stringify({
          model: "gpt-4o-mini",
          messages,
          temperature: body.generationConfig?.temperature ?? 0,
          max_tokens: body.generationConfig?.maxOutputTokens ?? 256,
        });

        const target = new URL(`${targetBase}/chat/completions`);
        const options: https.RequestOptions = {
          hostname: target.hostname,
          port: target.port || (target.protocol === "https:" ? 443 : 80),
          path: target.pathname,
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(openaiBody),
            Authorization: `Bearer ${apiKey}`,
          },
        };

        const transport = target.protocol === "https:" ? https : http;
        const upstream = transport.request(options, (upRes) => {
          const respChunks: Buffer[] = [];
          upRes.on("data", (c: Buffer) => respChunks.push(c));
          upRes.on("end", () => {
            try {
              const openaiResp = JSON.parse(
                Buffer.concat(respChunks).toString()
              );
              const choice = openaiResp.choices?.[0];

              // Convert OpenAI response → Vertex AI format
              const vertexResp = {
                candidates: [
                  {
                    content: {
                      role: "model",
                      parts: [{ text: choice?.message?.content ?? "" }],
                    },
                    finishReason: "STOP",
                    index: 0,
                  },
                ],
                usageMetadata: {
                  promptTokenCount: openaiResp.usage?.prompt_tokens ?? 0,
                  candidatesTokenCount:
                    openaiResp.usage?.completion_tokens ?? 0,
                  totalTokenCount: openaiResp.usage?.total_tokens ?? 0,
                },
                modelVersion: "gemini-2.0-flash",
              };

              const payload = JSON.stringify(vertexResp);
              res.writeHead(200, { "Content-Type": "application/json" });
              res.end(payload);
            } catch {
              res.writeHead(502);
              res.end(JSON.stringify({ error: "Failed to parse response" }));
            }
          });
        });
        upstream.on("error", (e) => {
          res.writeHead(502);
          res.end(JSON.stringify({ error: e.message }));
        });
        upstream.write(openaiBody);
        upstream.end();
      });
    });

    server.listen(0, () => {
      const port = (server.address() as any).port;
      (globalThis as any).__vertexProxy = server;
      resolve(`localhost:${port}`);
    });
  });
}

const proxyHost = await startProxy(RESPAN_BASE_URL, RESPAN_API_KEY);

// Allow self-signed certs for local proxy
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

// ── 5. Create Vertex AI client pointing at local proxy ────────────────
const dummyAuthClient = {
  getAccessToken: async () => ({ token: "proxy-passthrough" }),
  getRequestHeaders: async () => ({
    Authorization: "Bearer proxy-passthrough",
  }),
};

// Suppress the deprecation warning from the SDK
const origWarn = console.warn;
console.warn = (...args: unknown[]) => {
  if (
    typeof args[0] === "string" &&
    args[0].includes("VertexAI class and all its dependencies are deprecated")
  )
    return;
  origWarn(...args);
};

const vertexAI = new VertexAI({
  project: "respan-example",
  location: "us-central1",
  apiEndpoint: proxyHost,
  googleAuthOptions: { authClient: dummyAuthClient as any },
});
console.warn = origWarn;

const model = vertexAI.getGenerativeModel({ model: "gemini-2.0-flash" });

const result = await model.generateContent({
  contents: [
    {
      role: "user",
      parts: [{ text: "Write a haiku about recursion in programming." }],
    },
  ],
});

console.log(result.response.candidates?.[0]?.content?.parts?.[0]?.text);

// ── 6. Flush and cleanup ──────────────────────────────────────────────
await respan.flush();
((globalThis as any).__vertexProxy as https.Server).close();
