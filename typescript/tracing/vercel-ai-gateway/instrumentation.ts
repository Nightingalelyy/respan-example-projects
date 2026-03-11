import { registerOTel } from '@vercel/otel';
import { RespanExporter } from '@respan/exporter-vercel';

export function register() {
  if (!process.env.RESPAN_API_KEY) return;

  registerOTel({
    serviceName: 'vercel-ai-gateway',
    traceExporter: new RespanExporter({
      apiKey: process.env.RESPAN_API_KEY,
      baseUrl: process.env.RESPAN_BASE_URL,
    }),
  });
}
