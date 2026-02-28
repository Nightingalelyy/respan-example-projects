import { RespanTelemetry } from "@respan/tracing";
import OpenAI from "openai";
import * as dotenv from "dotenv";

// Load environment variables
dotenv.config({ path: ".env.local", override: true });

// Initialize Respan telemetry singleton
const respan = new RespanTelemetry({
  apiKey: process.env.RESPAN_API_KEY || "",
  baseURL: process.env.RESPAN_BASE_URL || "",
  logLevel: "debug",
  instrumentModules: {
    openAI: OpenAI, // This enables OpenAI tracing
  },
  disableBatch: true,
});

// Initialize the telemetry singleton
respan.initialize();

export { respan }; 