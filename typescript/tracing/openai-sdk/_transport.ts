// Intercept HTTP only: the real SDK still builds, parses, and streams requests.
export const FAILURE_SENTINEL = "RESPAN_EXPECTED_401";
export const MODEL = process.env.RESPAN_OPENAI_MODEL || "gpt-4.1-nano";
type Body = Record<string, any>;
const usage = { prompt_tokens: 13, completion_tokens: 7, total_tokens: 20 };

function chat(body: Body): Body {
  const toolResult = body.messages?.some(
    (message: Body) => message.role === "tool",
  );
  const message = body.response_format
    ? {
        role: "assistant",
        content: '{"city":"Paris","temperature":21}',
        refusal: null,
      }
    : body.tools && !toolResult
      ? {
          role: "assistant",
          content: null,
          tool_calls: [
            {
              id: "call_weather",
              type: "function",
              function: { name: "get_weather", arguments: '{"city":"Paris"}' },
            },
          ],
        }
      : {
          role: "assistant",
          content: toolResult
            ? "Paris is sunny."
            : "Observable OpenAI response.",
        };
  return {
    id: "chatcmpl_example",
    object: "chat.completion",
    created: 1_786_972_800,
    model: body.model,
    choices: [
      {
        index: 0,
        message,
        finish_reason: message.tool_calls ? "tool_calls" : "stop",
      },
    ],
    usage,
  };
}

function response(body: Body): Body {
  const toolResult =
    Array.isArray(body.input) &&
    body.input.some((item: Body) => item.type === "function_call_output");
  const text = body.text?.format
    ? '{"city":"Paris","temperature":21}'
    : toolResult
      ? "Paris is sunny."
      : "Observable Responses output.";
  const output =
    body.tools && !toolResult
      ? [
          {
            id: "fc_weather",
            type: "function_call",
            call_id: "call_weather",
            name: "get_weather",
            arguments: '{"city":"Paris"}',
            status: "completed",
          },
        ]
      : [
          {
            id: "msg_example",
            type: "message",
            status: "completed",
            role: "assistant",
            content: [
              { type: "output_text", text, annotations: [], logprobs: [] },
            ],
          },
        ];
  return {
    id: "resp_example",
    object: "response",
    created_at: 1_786_972_800,
    status: "completed",
    model: body.model,
    output,
    parallel_tool_calls: true,
    tool_choice: "auto",
    tools: body.tools || [],
    temperature: 1,
    top_p: 1,
    usage: { input_tokens: 11, output_tokens: 6, total_tokens: 17 },
    error: null,
    incomplete_details: null,
    instructions: body.instructions || null,
    metadata: {},
  };
}

function sse(events: Body[], named = false): Response {
  const chunks = events.map(
    (event) =>
      `${named ? `event: ${event.type}\n` : ""}data: ${JSON.stringify(event)}\n\n`,
  );
  chunks.push("data: [DONE]\n\n");
  let index = 0;
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    async pull(controller) {
      // Helpers consume eagerly. Yield separate network chunks so cancellation
      // happens before the final response/usage event reaches the SDK.
      await new Promise((resolve) => setTimeout(resolve, 5));
      if (cancelled) return;
      if (index === chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(new TextEncoder().encode(chunks[index++]));
    },
    cancel() {
      cancelled = true;
    },
  });
  return new Response(body, {
    headers: {
      "content-type": "text/event-stream",
      "x-request-id": "req_example_stream",
    },
  });
}

export const deterministicFetch: typeof fetch = async (input, init) => {
  const request = new Request(input, init);
  const body = (await request.json()) as Body;
  const endpoint = new URL(request.url).pathname;
  if (JSON.stringify(body).includes(FAILURE_SENTINEL)) {
    return Response.json(
      {
        error: {
          message: "deterministic credential rejected",
          type: "authentication_error",
        },
      },
      { status: 401 },
    );
  }
  if (endpoint.endsWith("/chat/completions")) {
    const result = chat(body);
    if (!body.stream)
      return Response.json(result, {
        headers: { "x-request-id": "req_example_chat" },
      });
    const toolCalls = result.choices[0].message.tool_calls;
    const deltas = toolCalls
      ? [
          {
            role: "assistant",
            tool_calls: [
              {
                index: 0,
                id: "call_weather",
                type: "function",
                function: { name: "get_weather", arguments: '{"city":' },
              },
            ],
          },
          { tool_calls: [{ index: 0, function: { arguments: '"Paris"}' } }] },
        ]
      : [
          { role: "assistant", content: "Observable " },
          { content: "OpenAI response." },
        ];
    return sse([
      ...deltas.map((delta, index) => ({
        id: result.id,
        object: "chat.completion.chunk",
        created: result.created,
        model: result.model,
        choices: [
          {
            index: 0,
            delta,
            finish_reason: index ? (toolCalls ? "tool_calls" : "stop") : null,
          },
        ],
      })),
      {
        id: result.id,
        object: "chat.completion.chunk",
        created: result.created,
        model: result.model,
        choices: [],
        usage,
      },
    ]);
  }
  if (endpoint.endsWith("/responses")) {
    const result = response(body);
    if (!body.stream)
      return Response.json(result, {
        headers: { "x-request-id": "req_example_responses" },
      });
    const item = result.output[0];
    const events: Body[] = [
      {
        type: "response.created",
        response: { ...result, status: "in_progress", output: [], usage: null },
      },
      {
        type: "response.output_item.added",
        output_index: 0,
        item: {
          ...item,
          status: "in_progress",
          ...(item.type === "message" ? { content: [] } : { arguments: "" }),
        },
      },
    ];
    if (item.type === "function_call") {
      events.push(
        {
          type: "response.function_call_arguments.delta",
          item_id: item.id,
          output_index: 0,
          delta: '{"city":',
        },
        {
          type: "response.function_call_arguments.delta",
          item_id: item.id,
          output_index: 0,
          delta: '"Paris"}',
        },
        {
          type: "response.function_call_arguments.done",
          item_id: item.id,
          output_index: 0,
          arguments: item.arguments,
        },
      );
    } else {
      events.push(
        {
          type: "response.content_part.added",
          item_id: item.id,
          output_index: 0,
          content_index: 0,
          part: {
            type: "output_text",
            text: "",
            annotations: [],
            logprobs: [],
          },
        },
        {
          type: "response.output_text.delta",
          item_id: item.id,
          output_index: 0,
          content_index: 0,
          delta: item.content[0].text.slice(0, 11),
          logprobs: [],
        },
        {
          type: "response.output_text.delta",
          item_id: item.id,
          output_index: 0,
          content_index: 0,
          delta: item.content[0].text.slice(11),
          logprobs: [],
        },
        {
          type: "response.output_text.done",
          item_id: item.id,
          output_index: 0,
          content_index: 0,
          text: item.content[0].text,
          logprobs: [],
        },
        {
          type: "response.content_part.done",
          item_id: item.id,
          output_index: 0,
          content_index: 0,
          part: item.content[0],
        },
      );
    }
    events.push(
      { type: "response.output_item.done", output_index: 0, item },
      { type: "response.completed", response: result },
    );
    return sse(
      events.map((event, sequence_number) => ({ ...event, sequence_number })),
      true,
    );
  }
  if (endpoint.endsWith("/embeddings")) {
    return Response.json({
      object: "list",
      model: body.model,
      data: [{ object: "embedding", index: 0, embedding: [0.1, 0.2, 0.3] }],
      usage: { prompt_tokens: 4, total_tokens: 4 },
    });
  }
  if (endpoint.endsWith("/completions")) {
    const result = {
      id: "cmpl_example",
      object: "text_completion",
      created: 1_786_972_800,
      model: body.model,
      choices: [
        {
          index: 0,
          text: "Observable text completion.",
          finish_reason: "stop",
          logprobs: null,
        },
      ],
      usage,
    };
    return body.stream ? sse([result]) : Response.json(result);
  }
  throw new Error(`Unhandled deterministic endpoint: ${endpoint}`);
};
