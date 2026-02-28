import { registerOTel } from "@vercel/otel";
import { RespanExporter } from "@respan/exporter-vercel";
// import * as dotenv from "dotenv";

// dotenv.config({
//   path: ".env.local",
//   override: true,
// });

export function register() {
  console.log(
    "registering instrumentation, base url",
    process.env.RESPAN_BASE_URL,
    "api key",
    process.env.RESPAN_API_KEY?.slice(0, 4) + "..."
  );
  registerOTel({
    serviceName: "next-app",
    traceExporter: new RespanExporter({
      apiKey: process.env.RESPAN_API_KEY?.split(" ")[0],
      baseUrl: process.env.RESPAN_BASE_URL,
      debug: true,
    }),
  });
}
