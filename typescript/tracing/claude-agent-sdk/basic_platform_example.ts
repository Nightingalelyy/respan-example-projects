import * as _ClaudeAgentSDK from "@anthropic-ai/claude-agent-sdk";
import type { SDKMessage } from "@anthropic-ai/claude-agent-sdk";

import {
  buildBaseQueryOptions,
  createRespan,
  printCommonSummary,
} from "./_shared.js";

const ClaudeAgentSDK = { ..._ClaudeAgentSDK };

const BASIC_PROMPT =
  'Reply with exactly "hello_from_claude_agent_sdk_basic_example".';
const CUSTOMER_IDENTIFIER = "claude-agent-sdk-basic-example";
const EXAMPLE_NAME = "claude_agent_sdk_basic_platform_example";
const APP_NAME = "claude-agent-sdk-basic-example";

function isResultMessage(message: SDKMessage): message is Extract<SDKMessage, { type: "result" }> {
  return message.type === "result";
}

async function runBasicQuery(): Promise<string> {
  let resultText: string | undefined;

  const stream = await ClaudeAgentSDK.query({
    prompt: BASIC_PROMPT,
    options: buildBaseQueryOptions({
      maxTurns: 1,
      tools: [],
    }),
  });

  for await (const message of stream) {
    if (isResultMessage(message)) {
      resultText = "result" in message ? message.result : "";
    }
  }

  if (resultText === undefined) {
    throw new Error("Claude Agent SDK query completed without a result message.");
  }

  return resultText;
}

async function main(): Promise<void> {
  const respan = createRespan({
    appName: APP_NAME,
    sdkModule: ClaudeAgentSDK,
  });

  await respan.initialize();

  try {
    const resultText = await respan.propagateAttributes(
      {
        customer_identifier: CUSTOMER_IDENTIFIER,
        metadata: {
          example_name: EXAMPLE_NAME,
          sdk: "claude-agent-sdk",
          example_type: "basic",
          local_instrumentation: true,
        },
      },
      async () => runBasicQuery(),
    );

    console.log("\n=== Claude Agent SDK Basic Example ===");
    console.log(`Prompt:              ${BASIC_PROMPT}`);
    console.log(`Claude result:       ${resultText}`);
    printCommonSummary({
      title: "Trace Lookup",
      customerIdentifier: CUSTOMER_IDENTIFIER,
      exampleName: EXAMPLE_NAME,
    });
  } finally {
    await respan.flush();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
