import { RespanTelemetry } from '@respan/tracing';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

const respan = new RespanTelemetry({
    apiKey: process.env.RESPAN_API_KEY,
    baseURL: process.env.RESPAN_BASE_URL,
    appName: 'basic-example',
    disableBatch: true,
    logLevel: 'info'
});

const generateResponse = async (prompt: string) => {
    return await respan.withTask(
        { name: 'generate_response', version: 1 },
        async () => {
            await new Promise(resolve => setTimeout(resolve, 100));
            return `Response to: ${prompt}`;
        }
    );
};

const chatWorkflow = async (userMessage: string) => {
    return await respan.withWorkflow(
        { 
            name: 'chat_workflow', 
            version: 1,
            associationProperties: { 'user_type': 'demo' }
        },
        async () => {
            const response = await generateResponse(userMessage);
            
            await respan.withTask(
                { name: 'log_interaction' },
                async () => {
                    console.log(`User: ${userMessage}`);
                    console.log(`Assistant: ${response}`);
                    return 'logged';
                }
            );
            
            return response;
        }
    );
};

const assistantAgent = async (query: string) => {
    return await respan.withAgent(
        { 
            name: 'assistant_agent',
            associationProperties: { 'agent_type': 'general' }
        },
        async () => {
            const analysis = await respan.withTool(
                { name: 'query_analyzer' },
                async () => {
                    return {
                        intent: query.includes('?') ? 'question' : 'statement',
                        length: query.length,
                        complexity: query.split(' ').length > 10 ? 'high' : 'low'
                    };
                }
            );
            
            const response = await respan.withTool(
                { name: 'response_generator' },
                async () => {
                    await new Promise(resolve => setTimeout(resolve, 100));
                    return `Response based on analysis: ${JSON.stringify(analysis)}`;
                }
            );
            
            return {
                analysis,
                response
            };
        }
    );
};

async function main() {
    try {
        await respan.initialize();
        
        console.log('=== Basic Task Example ===');
        const basicResponse = await generateResponse('Hello, how are you?');
        console.log('Response:', basicResponse);
        
        console.log('\n=== Workflow Example ===');
        const workflowResponse = await chatWorkflow('What is the weather like?');
        console.log('Workflow Response:', workflowResponse);
        
        console.log('\n=== Agent Example ===');
        const agentResponse = await assistantAgent('Can you explain quantum computing?');
        console.log('Agent Response:', agentResponse);
        
        console.log('\n=== All examples completed ===');
        
        await respan.shutdown();
        
    } catch (error) {
        console.error('Error:', error);
        await respan.shutdown();
    }
}

if (import.meta.url === `file://${process.argv[1]}`) {
    main();
}

export { respan, generateResponse, chatWorkflow, assistantAgent };
