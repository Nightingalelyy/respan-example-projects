/**
 * OTel instrumentation — must be loaded before the app.
 *
 * Registers a NodeTracerProvider with RespanExporter so that
 * spans produced by the OtelBridge appear in Respan.
 */
import dotenv from "dotenv";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: resolve(__dirname, "../../../../.env"), override: true });

import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { RespanExporter } from "@respan/exporter-vercel";

const RESPAN_API_KEY =
  process.env.RESPAN_GATEWAY_API_KEY || process.env.RESPAN_API_KEY || "";

const exporter = new RespanExporter({
  apiKey: RESPAN_API_KEY,
  debug: true,
});

export const provider = new NodeTracerProvider({
  spanProcessors: [new BatchSpanProcessor(exporter)],
});

provider.register();
