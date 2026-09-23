/** One bounded hosted Claude request using the current SDK and Respan Gateway. */
import assert from 'node:assert/strict';
import * as SDK from '@anthropic-ai/claude-agent-sdk';
import { ClaudeAgentSDKInstrumentor } from '@respan/instrumentation-claude-agent-sdk';
import { Respan } from '@respan/respan';
import dotenv from 'dotenv';

dotenv.config({ path: process.env.RESPAN_ENV_FILE, quiet: true });
const runId = process.env.RESPAN_EXAMPLE_RUN_ID ?? `claude-js-live-${Date.now()}`;
const sdk = { ...SDK };
const key = process.env.RESPAN_API_KEY;
const baseURL = process.env.RESPAN_BASE_URL ?? 'https://api.respan.ai/api';
const respan = new Respan({ apiKey: key, baseURL, instrumentations: [new ClaudeAgentSDKInstrumentor({ sdkModule: sdk, agentName: 'claude-sdk-live-js' })], traceContent: true, silenceInitializationMessage: true });
await respan.initialize();
const abortController = new AbortController();
const timer = setTimeout(() => abortController.abort(), 70000);
try {
  const query = sdk.query({ prompt: `Reply exactly audit_ok. Audit marker: ${runId}`, options: {
    abortController, model: 'claude-sonnet-4-5', maxTurns: 1, tools: [], cwd: '/private/tmp', verbatimPrompts: true, includePartialMessages: true,
    env: { ANTHROPIC_BASE_URL: baseURL.replace(/\/$/, '') + '/anthropic', ANTHROPIC_API_KEY: key, ANTHROPIC_AUTH_TOKEN: key, CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: '1' },
  } });
  let result;
  let partials = 0;
  for await (const message of query) {
    if (message.type === 'stream_event') partials++;
    if (message.type === 'result') result = message;
  }
  assert.equal(result?.is_error, false);
  assert.equal(result?.result, 'audit_ok');
  console.log(JSON.stringify({ runId, result: result.result, sessionId: result.session_id, partials, usage: result.usage }));
} finally { clearTimeout(timer); await respan.shutdown(); }
