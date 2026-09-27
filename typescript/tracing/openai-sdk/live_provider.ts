import assert from "node:assert/strict";
import {
  createClient,
  createRespan,
  MODEL,
  RUN_ID,
  scenario,
} from "./_shared.js";
async function main(): Promise<void> {
  if (process.env.RESPAN_OPENAI_LIVE !== "1")
    throw new Error(
      "Set RESPAN_OPENAI_LIVE=1 to opt into a real provider request.",
    );
  const client = createClient(true);
  const respan = createRespan();
  await respan.initialize();
  try {
    const result = await scenario(respan, "live_provider", async () =>
      client.chat.completions.create({
        model: MODEL,
        messages: [
          {
            role: "user",
            content: "Reply with: OpenAI instrumentation is working.",
          },
        ],
      }),
    );
    assert.ok(result.choices[0]?.message.content);
    console.log(
      JSON.stringify({
        run_id: RUN_ID,
        model: result.model,
        output: result.choices[0].message.content,
      }),
    );
  } finally {
    await respan.flush();
    await respan.shutdown();
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
