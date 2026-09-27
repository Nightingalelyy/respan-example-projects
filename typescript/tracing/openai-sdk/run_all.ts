import assert from "node:assert/strict";
import { AuthenticationError } from "openai";
import { zodResponseFormat, zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";
import {
  createClient,
  createRespan,
  MODEL,
  RUN_ID,
  scenario,
} from "./_shared.js";
import { FAILURE_SENTINEL } from "./_transport.js";
const weather = {
  name: "get_weather",
  description: "Get city weather",
  strict: true,
  parameters: {
    type: "object",
    properties: { city: { type: "string" } },
    required: ["city"],
    additionalProperties: false,
  },
};
const schema = z.object({ city: z.string(), temperature: z.number() });
const messages = [{ role: "user" as const, content: "Say hello." }];
async function main(): Promise<void> {
  const respan = createRespan();
  const failures: string[] = [];
  let completed = 0;
  await respan.initialize();
  const client = createClient();
  const cases: Array<[string, () => Promise<unknown>]> = [
    [
      "chat",
      async () => {
        const result = await client.chat.completions
          .create({ model: MODEL, messages })
          .withResponse();
        assert.equal(result.response.status, 200);
        assert.equal(
          result.data.choices[0]?.message.content,
          "Observable OpenAI response.",
        );
      },
    ],
    [
      "chat_stream",
      async () => {
        const stream = await client.chat.completions.create({
          model: MODEL,
          messages,
          stream: true,
          stream_options: { include_usage: true },
        });
        assert.ok(stream.controller);
        let text = "";
        for await (const chunk of stream)
          text += chunk.choices[0]?.delta.content || "";
        assert.equal(text, "Observable OpenAI response.");
      },
    ],
    [
      "chat_tools",
      async () => {
        const first = await client.chat.completions.create({
          model: MODEL,
          messages,
          tools: [{ type: "function", function: weather }],
        });
        const call = first.choices[0]?.message.tool_calls?.[0];
        assert.ok(call && call.type === "function");
        const toolResult = await respan.withTool(
          { name: "get_weather" },
          async (arguments_: { city: string }) => ({
            city: arguments_.city,
            weather: "sunny",
          }),
          JSON.parse(call.function.arguments),
        );
        const result = await client.chat.completions.create({
          model: MODEL,
          messages: [
            ...messages,
            first.choices[0].message,
            {
              role: "tool",
              tool_call_id: call.id,
              content: JSON.stringify(toolResult),
            },
          ],
          tools: [{ type: "function", function: weather }],
        });
        assert.equal(result.choices[0]?.message.content, "Paris is sunny.");
      },
    ],
    [
      "chat_stream_tools",
      async () => {
        const runner = client.chat.completions.stream({
          model: MODEL,
          messages,
          tools: [{ type: "function", function: weather }],
          stream_options: { include_usage: true },
        });
        const result = await runner.finalChatCompletion();
        const call = result.choices[0]?.message.tool_calls?.[0];
        assert.ok(call && call.type === "function");
        assert.deepEqual(JSON.parse(call.function.arguments), {
          city: "Paris",
        });
      },
    ],
    [
      "chat_parse",
      async () => {
        const result = await client.chat.completions.parse({
          model: MODEL,
          messages,
          response_format: zodResponseFormat(schema, "weather"),
        });
        assert.deepEqual(result.choices[0]?.message.parsed, {
          city: "Paris",
          temperature: 21,
        });
      },
    ],
    [
      "responses",
      async () => {
        const { data, response } = await client.responses
          .create({ model: MODEL, input: "Say hello." })
          .withResponse();
        assert.equal(response.status, 200);
        assert.equal(data.output_text, "Observable Responses output.");
      },
    ],
    [
      "responses_stream",
      async () => {
        const stream = await client.responses.create({
          model: MODEL,
          input: "Say hello.",
          stream: true,
        });
        let text = "";
        for await (const event of stream)
          if (event.type === "response.output_text.delta") text += event.delta;
        assert.equal(text, "Observable Responses output.");
      },
    ],
    [
      "responses_tools",
      async () => {
        const tools = [{ type: "function" as const, ...weather }];
        const first = await client.responses.create({
          model: MODEL,
          input: "Weather in Paris?",
          tools,
        });
        const call = first.output.find((item) => item.type === "function_call");
        assert.ok(call);
        const output = await respan.withTool(
          { name: "get_weather" },
          async (arguments_: { city: string }) => ({
            city: arguments_.city,
            weather: "sunny",
          }),
          JSON.parse(call.arguments),
        );
        const result = await client.responses.create({
          model: MODEL,
          input: [
            call,
            {
              type: "function_call_output",
              call_id: call.call_id,
              output: JSON.stringify(output),
            },
          ],
          tools,
        });
        assert.equal(result.output_text, "Paris is sunny.");
      },
    ],
    [
      "responses_stream_tools",
      async () => {
        const stream = client.responses.stream({
          model: MODEL,
          input: "Weather in Paris?",
          tools: [{ type: "function", ...weather }],
        });
        const result = await stream.finalResponse();
        const call = result.output.find(
          (item) => item.type === "function_call",
        );
        assert.ok(call);
        assert.deepEqual(JSON.parse(call.arguments), { city: "Paris" });
      },
    ],
    [
      "responses_parse",
      async () => {
        const result = await client.responses.parse({
          model: MODEL,
          input: "Weather in Paris?",
          text: { format: zodTextFormat(schema, "weather") },
        });
        assert.deepEqual(result.output_parsed, {
          city: "Paris",
          temperature: 21,
        });
      },
    ],
    [
      "embeddings",
      async () => {
        const result = await client.embeddings.create({
          model: "text-embedding-3-small",
          input: "observable request",
          encoding_format: "float",
        });
        assert.deepEqual(result.data[0].embedding, [0.1, 0.2, 0.3]);
      },
    ],
    [
      "completion",
      async () => {
        const result = await client.completions.create({
          model: "gpt-3.5-turbo-instruct",
          prompt: "Say hello.",
        });
        assert.equal(result.choices[0].text, "Observable text completion.");
      },
    ],
    [
      "responses_partial",
      async () => {
        const stream = await client.responses.create({
          model: MODEL,
          input: "Say hello.",
          stream: true,
        });
        for await (const event of stream) {
          if (event.type === "response.output_text.delta") {
            assert.equal(event.delta, "Observable ");
            break;
          }
        }
      },
    ],
    [
      "chat_helper_partial",
      async () => {
        const runner = client.chat.completions.stream({
          model: MODEL,
          messages,
        });
        for await (const chunk of runner) {
          if (chunk.choices[0]?.delta.content) {
            assert.equal(chunk.choices[0].delta.content, "Observable ");
            runner.abort();
            break;
          }
        }
      },
    ],
    [
      "responses_helper_partial",
      async () => {
        const runner = client.responses.stream({
          model: MODEL,
          input: "Say hello.",
        });
        for await (const event of runner) {
          if (event.type === "response.output_text.delta") {
            assert.equal(event.delta, "Observable ");
            runner.abort();
            break;
          }
        }
      },
    ],
    [
      "provider_error",
      async () => {
        await assert.rejects(
          client.chat.completions.create({
            model: MODEL,
            messages: [{ role: "user", content: FAILURE_SENTINEL }],
          }),
          (error: unknown) =>
            error instanceof AuthenticationError && error.status === 401,
        );
      },
    ],
  ];
  try {
    console.log(`RESPAN_EXAMPLE_RUN_ID=${RUN_ID}`);
    for (const [name, run] of cases) {
      try {
        await scenario(respan, name, run);
        completed += 1;
      } catch (error) {
        failures.push(name);
        console.error(name, error);
      }
    }
  } finally {
    await respan.flush();
    await respan.shutdown();
  }
  console.log(
    JSON.stringify({
      run_id: RUN_ID,
      completed,
      expected: cases.length,
      failures,
    }),
  );
  if (failures.length) process.exitCode = 1;
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
