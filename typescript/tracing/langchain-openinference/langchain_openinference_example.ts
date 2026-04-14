/** LangChain — Chat completion with Respan tracing via OpenInference. */

import "dotenv/config";
import { ChatOpenAI } from "@langchain/openai";
import { LangChainInstrumentation } from "@arizeai/openinference-instrumentation-langchain";
import * as CallbackManagerModule from "@langchain/core/callbacks/manager";
import { Respan } from "@respan/respan";
import { OpenInferenceInstrumentor } from "@respan/instrumentation-openinference";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY;
const RESPAN_BASE_URL = (process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api").replace(/\/+$/, "");

const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
  instrumentations: [
    new OpenInferenceInstrumentor(LangChainInstrumentation, CallbackManagerModule),
  ],
});
await respan.initialize();

const model = new ChatOpenAI({
  modelName: "gpt-4o-mini",
  temperature: 0,
  openAIApiKey: RESPAN_API_KEY,
  configuration: {
    baseURL: RESPAN_BASE_URL,
  },
});

const response = await model.invoke("Write a haiku about recursion in programming.");

console.log(response.content);

await respan.flush();
