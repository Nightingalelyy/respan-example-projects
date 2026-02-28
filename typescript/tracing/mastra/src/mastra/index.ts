import { Mastra } from '@mastra/core';
import dotenv from 'dotenv';
import { weatherAgent } from './agents';
import { weatherWorkflow as legacyWeatherWorkflow } from './workflows';
import { weatherWorkflow, weatherWorkflow2 } from './workflows/new-workflow';
import { RespanExporter } from '@respan/exporter-vercel';

dotenv.config({
  path: '.env.local',
  override: true,
});

export const mastra = new Mastra({
  agents: { weatherAgent },
  legacy_workflows: { legacyWeatherWorkflow },
  workflows: { weatherWorkflow, weatherWorkflow2 },
  telemetry: {
    serviceName: "respan-mastra-example",
    enabled: true,
    export: {
      type: "custom",
      "exporter": new RespanExporter({
        apiKey: process.env.RESPAN_API_KEY,
        baseUrl: process.env.RESPAN_BASE_URL,
        debug: true,
      })
    }
  }
});
