import { RespanTelemetry } from '@respan/tracing';
import OpenAI from 'openai';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

const respan = new RespanTelemetry({
    apiKey: process.env.RESPAN_API_KEY || 'demo-key',
    baseURL: process.env.RESPAN_BASE_URL,
    appName: 'advanced-tracing-example',
    instrumentModules: {
        openAI: OpenAI,
    },
    disableBatch: true,
    logLevel: 'info'
});

const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY || 'test-api-key',
});

const runAgentExample = async (query: string) => {
    return await respan.withAgent(
        { 
            name: 'research_assistant',
            associationProperties: { 
                'user_id': 'user_123',
                'session_id': 'session_abc' 
            }
        },
        async () => {
            console.log(`Agent received query: ${query}`);

            const analysis = await respan.withTool(
                { name: 'query_analyzer' },
                async () => {
                    console.log('Analyzing query...');
                    await new Promise(resolve => setTimeout(resolve, 300));
                    return {
                        topic: query.toLowerCase().includes('ai') ? 'technology' : 'general',
                        sentiment: 'neutral'
                    };
                }
            );

            const searchResults = await respan.withTool(
                { name: 'web_search' },
                async () => {
                    console.log('Searching the web...');
                    return `Found some information about ${analysis.topic}`;
                }
            );

            const finalResponse = await respan.withTask(
                { name: 'final_generation' },
                async () => {
                    console.log('Generating final response...');
                    try {
                        const completion = await openai.chat.completions.create({
                            model: 'gpt-3.5-turbo',
                            messages: [
                                { role: 'system', content: `You are a research assistant. Topic: ${analysis.topic}. Info: ${searchResults}` },
                                { role: 'user', content: query }
                            ],
                        });
                        return completion.choices[0].message.content;
                    } catch (e) {
                        return "Here is your simulated research result based on the analysis.";
                    }
                }
            );

            return {
                analysis,
                searchResults,
                finalResponse
            };
        }
    );
};

async function main() {
    try {
        await respan.initialize();
        console.log('Starting Advanced Tracing Example\n');

        const result = await runAgentExample('How is AI changing software development?');
        console.log('\nAgent Execution Result:', JSON.stringify(result, null, 2));

        console.log('\nExample completed. Shutting down...');
        await respan.shutdown();
    } catch (error) {
        console.error('Error:', error);
        await respan.shutdown();
    }
}

if (import.meta.url === `file://${process.argv[1]}`) {
    main();
}

export { runAgentExample };
