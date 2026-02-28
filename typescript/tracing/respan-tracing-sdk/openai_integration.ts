import OpenAI from "openai";
import { RespanTelemetry } from "@respan/tracing";
import dotenv from "dotenv";
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

const respan = new RespanTelemetry({
  apiKey: process.env.RESPAN_API_KEY || "test-api-key",
  appName: "openai-integration-test",
  instrumentModules: {
    openAI: OpenAI,
  },
  logLevel: 'info'
});

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || "test-api-key",
});

async function runOpenAIIntegrationTest() {
  console.log("Starting OpenAI Integration Test with Respan\n");

  try {
    await respan.initialize();
    console.log("Respan initialized successfully\n");

    await respan.withWorkflow(
      { name: "openai_chat_completion" },
      async () => {
        console.log("Sending request to OpenAI...");
        
        try {
          const completion = await openai.chat.completions.create({
            model: "gpt-3.5-turbo",
            messages: [
                { role: "system", content: "You are a helpful assistant." },
                { role: "user", content: "Tell me a short joke about programming." }
            ],
          });

          console.log("OpenAI Response:", completion.choices[0].message.content);
        } catch (error) {
          if (process.env.OPENAI_API_KEY === undefined || process.env.OPENAI_API_KEY === "test-api-key") {
            console.log("Skipping real API call (no OPENAI_API_KEY found).");
            console.log("In a real scenario, the instrumentation would capture the request and response automatically.");
          } else {
            throw error;
          }
        }
      }
    );

    console.log("\nCleaning up...");
    await respan.shutdown();
    console.log("Done!");

  } catch (error) {
    console.error("Error:", error);
    await respan.shutdown();
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runOpenAIIntegrationTest().catch(console.error);
}

export { runOpenAIIntegrationTest };
