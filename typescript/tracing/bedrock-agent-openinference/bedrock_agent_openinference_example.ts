/**
 * AWS Bedrock Agent Runtime — RetrieveAndGenerate with Respan tracing
 * via OpenInference.
 *
 * The @aws-sdk/client-bedrock-agent-runtime SDK sends requests to
 *   POST /retrieveAndGenerate
 *
 * Since we route LLM calls through the Respan gateway (OpenAI format),
 * a local HTTP proxy translates the Bedrock RAG request to an OpenAI
 * chat completion and translates the response back.
 *
 * The @arizeai/openinference-instrumentation-bedrock-agent-runtime
 * patches BedrockAgentRuntimeClient.prototype.send to create
 * OpenInference-format spans for RetrieveAndGenerate, InvokeAgent, etc.
 */

import "dotenv/config";
import http from "node:http";
import https from "node:https";
import { URL } from "node:url";
import { trace } from "@opentelemetry/api";
import { BedrockAgentInstrumentation } from "@arizeai/openinference-instrumentation-bedrock-agent-runtime";
import * as BedrockAgentModule from "@aws-sdk/client-bedrock-agent-runtime";
import {
  BedrockAgentRuntimeClient,
  RetrieveAndGenerateCommand,
} from "@aws-sdk/client-bedrock-agent-runtime";
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
    new OpenInferenceInstrumentor(BedrockAgentInstrumentation),
  ],
});
await respan.initialize();

// ── 2. Manually instrument @aws-sdk/client-bedrock-agent-runtime ──────
const instrumentation = new BedrockAgentInstrumentation();
instrumentation.setTracerProvider(trace.getTracerProvider());
instrumentation.manuallyInstrument(BedrockAgentModule);

// ── 3. Local proxy: Bedrock RAG → OpenAI → Respan gateway ────────────
function startProxy(targetBase: string, apiKey: string): Promise<string> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const chunks: Buffer[] = [];
      req.on("data", (c: Buffer) => chunks.push(c));
      req.on("end", () => {
        try {
          const body = JSON.parse(Buffer.concat(chunks).toString());

          // Extract query from Bedrock RAG request
          const queryText = body.input?.text ?? "Hello";

          const openaiBody = JSON.stringify({
            model: "gpt-4o-mini",
            messages: [{ role: "user", content: queryText }],
            temperature: 0,
            max_tokens: 256,
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
                const responseText =
                  choice?.message?.content ?? "";

                // Convert OpenAI response → Bedrock RAG format
                const bedrockResp = {
                  output: { text: responseText },
                  citations: [
                    {
                      generatedResponsePart: {
                        textResponsePart: {
                          text: responseText,
                          span: { start: 0, end: responseText.length },
                        },
                      },
                      retrievedReferences: [
                        {
                          content: { text: "Proxied via Respan gateway" },
                          location: {
                            type: "CUSTOM",
                            customDocumentLocation: {
                              id: "respan-proxy",
                            },
                          },
                        },
                      ],
                    },
                  ],
                  sessionId: "respan-session-001",
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
      (globalThis as any).__bedrockAgentProxy = server;
      resolve(`http://localhost:${port}`);
    });
  });
}

const proxyUrl = await startProxy(RESPAN_BASE_URL, RESPAN_API_KEY);

// ── 4. Create Bedrock Agent Runtime client pointing at local proxy ────
const client = new BedrockAgentRuntimeClient({
  region: "us-east-1",
  endpoint: proxyUrl,
  credentials: {
    accessKeyId: "proxy-passthrough",
    secretAccessKey: "proxy-passthrough",
  },
});

const command = new RetrieveAndGenerateCommand({
  input: { text: "Write a haiku about recursion in programming." },
  retrieveAndGenerateConfiguration: {
    type: "KNOWLEDGE_BASE",
    knowledgeBaseConfiguration: {
      knowledgeBaseId: "EXAMPLE_KB_ID",
      modelArn:
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
    },
  },
});

const result = await client.send(command);
console.log(result.output?.text);

// ── 5. Flush and cleanup ──────────────────────────────────────────────
await respan.flush();
((globalThis as any).__bedrockAgentProxy as http.Server).close();
