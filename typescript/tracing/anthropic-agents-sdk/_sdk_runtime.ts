import { query } from "@anthropic-ai/claude-agent-sdk";

export const QUERY_TIMEOUT_SECONDS = Number.parseInt(
  process.env.RESPAN_QUERY_TIMEOUT_SECONDS ?? "90",
  10,
);

type QueryMessage = Record<string, unknown>;
type MessageHandler = (
  message: QueryMessage,
  context: { sessionId?: string },
) => Promise<void> | void;

export function suppressStderr(): () => void {
  const originalWrite = process.stderr.write.bind(process.stderr);
  process.stderr.write = (() => true) as typeof process.stderr.write;
  return () => {
    process.stderr.write = originalWrite as typeof process.stderr.write;
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface QueryForResultOptions {
  prompt: string;
  options: unknown;
  onMessage?: MessageHandler;
  timeoutSeconds?: number;
}

interface QueryForResultResult {
  result: QueryMessage;
  sessionId?: string;
  messageTypes: string[];
}

export async function queryForResult(
  params: QueryForResultOptions,
): Promise<QueryForResultResult> {
  const timeoutSeconds = params.timeoutSeconds ?? QUERY_TIMEOUT_SECONDS;
  const messageTypes: string[] = [];
  let sessionId: string | undefined;
  let result: QueryMessage | undefined;
  let timedOut = false;

  const stream = query({
    prompt: params.prompt,
    options: params.options as any,
  }) as AsyncGenerator<unknown, void, unknown>;

  const restoreStderr = suppressStderr();
  const timeoutId = setTimeout(() => {
    timedOut = true;
    void stream.return?.(undefined);
  }, Math.max(1, timeoutSeconds) * 1000);

  try {
    try {
      for await (const rawMessage of stream) {
        const message = rawMessage as QueryMessage;
        const msgType = String(message.type ?? "unknown");
        messageTypes.push(msgType);

        if (message.type === "system") {
          const data = (message.data ?? {}) as Record<string, unknown>;
          const maybeSessionId = data.session_id ?? data.sessionId ?? sessionId;
          if (typeof maybeSessionId === "string") {
            sessionId = maybeSessionId;
          }
        }
        if (message.type === "result") {
          const maybeSessionId = message.session_id ?? sessionId;
          if (typeof maybeSessionId === "string") {
            sessionId = maybeSessionId;
          }
          result = message;
        }

        if (params.onMessage) {
          await params.onMessage(message, { sessionId });
        }
      }
    } catch (error) {
      // Claude Code subprocess can exit non-zero after already yielding result.
      if (!result) {
        throw error;
      }
    }
  } finally {
    clearTimeout(timeoutId);
    await sleep(250);
    restoreStderr();
  }

  if (timedOut) {
    throw new Error(`Timed out after ${timeoutSeconds}s waiting for query result.`);
  }
  if (!result) {
    throw new Error("Query completed without a result message.");
  }

  return {
    result,
    sessionId,
    messageTypes,
  };
}
