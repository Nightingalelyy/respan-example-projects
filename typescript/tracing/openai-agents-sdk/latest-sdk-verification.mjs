import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { Agent, Runner, MemorySession, OpenAIProvider, tool, withTrace, withMCPListToolsSpan,
  withSpeechGroupSpan, withTranscriptionSpan, withSpeechSpan, MCPServerStdio, withResponseSpan, OpenAIResponsesModel } from '@openai/agents';
import { Respan } from '@respan/respan';
import { OpenAIAgentsInstrumentor } from '@respan/instrumentation-openai-agents';
import { z } from 'zod';
import dotenv from 'dotenv';
dotenv.config({ path: process.env.RESPAN_ENV_FILE ?? '.env', quiet: true });
const marker = process.env.RESPAN_EXAMPLE_RUN_ID ?? `openai-js-latest-${randomUUID()}`;
const respan = new Respan({ apiKey: process.env.RESPAN_API_KEY,
  baseURL: process.env.RESPAN_BASE_URL ?? 'https://api.respan.ai',
  appName: 'openai-agents-latest-js', instrumentations: [new OpenAIAgentsInstrumentor()],
  traceContent: process.env.RESPAN_EXAMPLE_TRACE_CONTENT !== 'false', silenceInitializationMessage: true });
await respan.initialize();
const provider = new OpenAIProvider({apiKey: process.env.RESPAN_GATEWAY_API_KEY ?? process.env.RESPAN_API_KEY,
  baseURL: process.env.RESPAN_GATEWAY_BASE_URL ?? 'https://api.respan.ai/api', useResponses: false});
const runner = new Runner({modelProvider: provider});
const model = process.env.RESPAN_MODEL ?? 'gpt-4o-mini';
const forecast = tool({name:'forecast', description:'Return the weather for a city.', parameters:z.object({city:z.string()}),
  execute: async ({city}) => `Sunny in ${city}; 22 C.`});
const records=[];
async function scenario(name, action) {
  if(process.env.RESPAN_SCENARIOS && !process.env.RESPAN_SCENARIOS.split(",").includes(name)) return;
  let sdkTraceId;
  const result = await withTrace(`openai-js-latest.${name}`, async trace => { sdkTraceId=trace.traceId; return action(); },
    {groupId:marker, metadata:{run_id:marker, scenario:name}});
  const record={scenario:name,sdk_trace_id:sdkTraceId,result}; records.push(record);
  await respan.flush(); console.log(JSON.stringify(record));
}
try {
  await scenario('tools_stream', async () => {
    const agent=new Agent({name:'Weather', model, instructions:'Always call forecast for Paris then report the result.',tools:[forecast]});
    const result=await runner.run(agent,'What is the weather in Paris?',{stream:true});
    let events=0; for await (const event of result) events++;
    await result.completed; assert.match(result.finalOutput,/Paris/); assert.ok(events>0);
    return {output:result.finalOutput,events};
  });
  await scenario('handoff', async () => {
    const specialist=new Agent({name:'Specialist',model,instructions:'Reply: specialist verified.'});
    const triage=new Agent({name:'Triage',model,instructions:'Always transfer to Specialist immediately.',handoffs:[specialist]});
    const result=await runner.run(triage,'Transfer to Specialist.');
    assert.equal(result.lastAgent.name,'Specialist'); return result.finalOutput;
  });
  await scenario('structured_session', async () => {
    const session=new MemorySession({sessionId:marker});
    const agent=new Agent({name:'Structured',model,outputType:z.object({city:z.string(),weather:z.string()})});
    await runner.run(agent,'Remember the city Paris and sunny weather.',{session});
    const result=await runner.run(agent,'Repeat the city and weather from before.',{session});
    assert.equal(result.finalOutput.city,'Paris');return result.finalOutput;
  });
  await scenario('guardrail', async () => {
    const agent=new Agent({name:'Blocked',model,inputGuardrails:[{name:'block',runInParallel:false,
      execute:async()=>({tripwireTriggered:true,outputInfo:{reason:'verification'}})}]});
    try {await runner.run(agent,'Block this test.');}
    catch(error) {assert.equal(error.name,'InputGuardrailTripwireTriggered');return {expected_error:error.name};}
    throw new Error('guardrail did not trigger');
  });
  await scenario('approval', async () => {
    const action=tool({name:'approve_action',description:'Execute an approved sample action.',parameters:z.object({note:z.string()}),needsApproval:true,
      execute:async({note})=>`Approved: ${note}`});
    const agent=new Agent({name:'Approval',model,instructions:'Call approve_action with note verify once, then return the result.',tools:[action]});
    const first=await runner.run(agent,'Execute the sample action.');assert.ok(first.interruptions.length);
    for(const item of first.interruptions)first.state.approve(item);
    const result=await runner.run(agent,first.state);assert.equal(result.interruptions.length,0);return result.finalOutput;
  });
  await scenario('tool_error', async () => {
    const fail=tool({name:'fail',description:'Raise the expected verification error.',parameters:z.object({}),errorFunction:null,execute:async()=>{throw new Error('Expected verification tool failure');}});
    try {await runner.run(new Agent({name:'Failure',model,instructions:'Always call fail.',tools:[fail]}),'Call fail now.');}
    catch(error) {assert.match(error.message,/Expected verification tool failure/);return {expected_error:error.message};}
    throw new Error('tool error did not happen');
  });
  await scenario('mcp', async()=>{
    const server=new MCPServerStdio({name:'verification-weather',command:process.execPath,args:[fileURLToPath(new URL('./verification-mcp-server.mjs',import.meta.url))]});
    await server.connect();
    try {
      const result=await runner.run(new Agent({name:'MCP Weather',model,instructions:'Always call forecast_mcp for Paris then report the result.',mcpServers:[server]}),'Use the MCP tool to get weather for Paris.');
      assert.match(result.finalOutput,/Paris/);return result.finalOutput;
    } finally {await server.close();}
  });
  await scenario('native_hosted', async()=>{
    await withResponseSpan(async(span)=>{
      span.spanData._input=[{role:'user',content:'Hosted fixture'}];
      span.spanData._response={model:'gpt-4o-mini',tools:[],output:[
        {type:'file_search_call',id:'fs_fixture',queries:['hello']},
        {type:'code_interpreter_call',id:'ci_fixture',code:'print(42)',container_id:'c',outputs:[{type:'logs',logs:'42'}]},
        {type:'image_generation_call',id:'img_fixture',revised_prompt:'cat',result:'BASE64'},
      ]};
    });
    return {mode:'native SDK hosted response payload fixture'};
  });
  await scenario('privacy_responses_native', async()=>{
    const native=new OpenAIResponsesModel({baseURL:'https://api.openai.com/v1'},'gpt-4o-mini');
    native._fetchResponse=async()=>({id:'resp_private',object:'response',created_at:1,status:'completed',model:'gpt-4o-mini',
      output:[{id:'msg',type:'message',role:'assistant',status:'completed',content:[{type:'output_text',text:'PRIVATE_OUTPUT',annotations:[]}]}],
      usage:{input_tokens:1,output_tokens:1,total_tokens:2,input_tokens_details:{cached_tokens:0},output_tokens_details:{reasoning_tokens:0}}});
    await native.getResponse({input:[{type:'message',role:'user',content:'PRIVATE_INPUT'}],modelSettings:{},tools:[],handoffs:[],outputType:'text',tracing:'enabled_without_data'});
    return {mode:'native SDK model with deterministic transport'};
  });
  await scenario('privacy_sdk', async()=>{
    const privateRunner=new Runner({modelProvider:provider,traceIncludeSensitiveData:false});
    const result=await privateRunner.run(new Agent({name:'Private',model,tools:[forecast],instructions:'Call forecast for Paris then report the result.'}),'PRIVATE_CONTENT: weather in Paris?');
    return {completed:!!result.finalOutput};
  });
  await scenario('native_voice_mcp', async () => {
    await withMCPListToolsSpan(async()=>{}, {data:{server:'weather',result:['forecast']}});
    await withSpeechGroupSpan(async()=>{
      await withTranscriptionSpan(async()=>{}, {data:{input:{data:'YXVkaW8=',format:'pcm'},output:'Hello',model:'whisper-1'}});
      await withSpeechSpan(async()=>{}, {data:{input:'Hello',output:{data:'YXVkaW8=',format:'pcm'},model:'tts-1'}});
    },{data:{input:'Hello'}});
    return {mode:'native SDK tracing surface'};
  });
} finally {await respan.flush();await provider.close();await respan.shutdown();}
console.log(JSON.stringify({run_id:marker,sdk_version:'0.18.0',records}));
