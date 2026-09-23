/** Real released SDK protocol + deterministic process fixture + live Respan export. */
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { PassThrough, Writable } from 'node:stream';
import { randomUUID } from 'node:crypto';
import * as SDK from '@anthropic-ai/claude-agent-sdk';
import { ClaudeAgentSDKInstrumentor } from '@respan/instrumentation-claude-agent-sdk';
import { Respan } from '@respan/respan';
import { JsonTraceSerializer } from '@opentelemetry/otlp-transformer';
import dotenv from 'dotenv';

dotenv.config({ path: process.env.RESPAN_ENV_FILE, quiet: true });
const runId = process.env.RESPAN_EXAMPLE_RUN_ID ?? `claude-js-latest-${Date.now()}`;
const module = { ...SDK };
const instrumentor = new ClaudeAgentSDKInstrumentor({ sdkModule: module, agentName: "claude-latest-sdk" });
const respan = new Respan({ apiKey: process.env.RESPAN_API_KEY, baseURL: process.env.RESPAN_BASE_URL ?? 'https://api.respan.ai', instrumentations: [instrumentor], traceContent: true, silenceInitializationMessage: true });
await respan.initialize();
const exported = [];
respan.addProcessor({ name: "compatibility-evidence", filter: () => true, disableBatch: true, exporter: {
  export(spans, callback) { exported.push(...spans); callback({ code: 0 }); },
  async shutdown() {},
  async forceFlush() {},
} });

class ProtocolProcess extends EventEmitter {
  stdout = new PassThrough();
  killed = false;
  exitCode = null;
  hooks = {};
  controls = [];
  constructor(scenario) {
    super();
    this.scenario = scenario;
    this.stdin = new Writable({ write: (chunk, encoding, callback) => {
      try { for (const line of String(chunk).trim().split('\n')) this.receive(JSON.parse(line)); callback(); }
      catch (error) { callback(error); }
    } });
    this.stdin.on('finish', () => this.finish());
  }
  send(message) { this.stdout.write(JSON.stringify(message) + '\n'); }
  receive(message) {
    if (message.type === 'control_request') {
      this.controls.push(message.request.subtype);
      if (message.request.subtype === 'initialize') this.hooks = message.request.hooks ?? {};
      let response = {};
      if (message.request.subtype === 'mcp_status') response = { mcpServers: [{ name: 'fixture', status: 'connected', tools: [{ name: 'Read', _meta: { ui: { resourceUri: 'ui://fixture' } } }] }] };
      this.send({ type: 'control_response', response: { subtype: 'success', request_id: message.request_id, response } });
      return;
    }
    if (message.type === 'user') {
      this.send({ type: 'system', subtype: 'init', uuid: randomUUID(), session_id: runId, model: 'claude-sonnet-4-5', tools: ['Read'] });
      const id = this.hooks.PreToolUse?.at(-1)?.hookCallbackIds?.[0];
      assert.ok(id, 'instrumentation hook must survive real SDK initialization');
      this.send({ type: 'control_request', request_id: 'fixture-pre', request: { subtype: 'hook_callback', callback_id: id, tool_use_id: 'tool-fixture', input: { hook_event_name: 'PreToolUse', session_id: runId, tool_name: 'Read', tool_use_id: 'tool-fixture', tool_input: { path: 'fixture.txt' } } } });
      return;
    }
    if (message.type === 'control_response' && message.response.request_id === 'fixture-pre') {
      this.send({ type: 'assistant', uuid: randomUUID(), session_id: runId, parent_tool_use_id: null, message: { id: 'message-fixture', model: 'claude-sonnet-4-5', role: 'assistant', content: [{ type: 'tool_use', id: 'tool-fixture', name: 'Read', input: { path: 'fixture.txt' } }], usage: { input_tokens: 9, output_tokens: 3 } } });
      this.send({ type: 'user', uuid: randomUUID(), session_id: runId, parent_tool_use_id: null, message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'tool-fixture', content: this.scenario === 'failure' ? 'fixture permission denied' : 'fixture content', is_error: this.scenario === 'failure' }] } });
      this.send({ type: 'system', subtype: 'task_notification', task_id: 'task-fixture', status: 'completed', summary: 'fixture task', output_file: '', uuid: randomUUID(), session_id: runId });
      this.send({ type: 'result', subtype: 'success', uuid: randomUUID(), session_id: runId, is_error: false, num_turns: 1, duration_ms: 10, duration_api_ms: 5, total_cost_usd: 0, usage: { input_tokens: 9, output_tokens: 3 }, modelUsage: {}, permission_denials: [], result: '', structured_output: { scenario: this.scenario, answer: 42 } });
    }
  }
  finish() { if (this.exitCode !== null) return; this.exitCode = 0; this.stdout.end(); this.emit('exit', 0, null); }
  kill() { this.killed = true; this.finish(); return true; }
}

try {
  for (const scenario of ['success', 'failure']) {
    const processFixture = new ProtocolProcess(scenario);
    const query = module.query({ prompt: `@literal /literal ${runId}`, options: { verbatimPrompts: true, includePartialMessages: true, resume: runId, spawnClaudeCodeProcess: () => processFixture } });
    assert.equal(query.then, undefined);
    assert.equal(typeof query.readMcpResource, 'function');
    assert.equal(typeof query.askSideQuestion, 'function');
    await query.setModel('claude-sonnet-4-5');
    await query.interrupt();
    let result;
    for await (const message of query) {
      if (message.type === 'result') { result = message; break; }
    }
    query.close();
    assert.deepEqual(result.structured_output, { scenario, answer: 42 });
    assert.ok(processFixture.controls.includes('set_model'));
    assert.ok(processFixture.controls.includes('interrupt'));
    console.log(JSON.stringify({ runId, scenario, controls: processFixture.controls, result: result.structured_output }));
  }
} finally {
  await respan.shutdown();
  const otlp = JSON.parse(Buffer.from(JsonTraceSerializer.serializeRequest(exported)).toString());
  console.log(JSON.stringify({ otlpStatus: otlp.resourceSpans.flatMap(resource => resource.scopeSpans.flatMap(scope => scope.spans.map(span => ({ traceId: span.traceId, spanId: span.spanId, name: span.name, status: span.status })))) }));
  console.log(JSON.stringify({ rawSpans: exported.map(span => ({
    traceId: span.spanContext().traceId, spanId: span.spanContext().spanId,
    name: span.name, status: span.status, input: span.attributes["traceloop.entity.input"], output: span.attributes["traceloop.entity.output"],
  })) }));
}
