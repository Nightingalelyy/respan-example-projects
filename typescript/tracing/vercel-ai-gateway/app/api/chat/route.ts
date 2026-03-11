import { generateText } from 'ai';

export async function POST(req: Request) {
  const { userId } = await req.json();
  const input = 'Tell me a joke';

  // Step 1: Classify intent
  const intentResult = await generateText({
    model: 'openai/gpt-5',
    prompt: `Classify this intent in one word: "${input}". Reply with just the category.`,
    experimental_telemetry: {
      isEnabled: true,
      functionId: 'classify_intent',
      metadata: {
        customer_identifier: userId ?? 'anonymous',
        thread_identifier: 'session-abc-123',
        environment: 'development',
        step: 'classification',
        workflow: 'joke_pipeline',
        provider: 'vercel-ai-gateway',
      },
    },
  });

  // Step 2: Generate response based on intent
  const responseResult = await generateText({
    model: 'openai/gpt-5',
    prompt: `The user intent is "${intentResult.text}". Tell me a short joke.`,
    experimental_telemetry: {
      isEnabled: true,
      functionId: 'generate_response',
      metadata: {
        customer_identifier: userId ?? 'anonymous',
        thread_identifier: 'session-abc-123',
        environment: 'development',
        step: 'generation',
        workflow: 'joke_pipeline',
        provider: 'vercel-ai-gateway',
        intent: intentResult.text,
      },
    },
  });

  // Step 3: Summarize
  const summaryResult = await generateText({
    model: 'openai/gpt-5',
    prompt: `Summarize this in one sentence: "${responseResult.text}"`,
    experimental_telemetry: {
      isEnabled: true,
      functionId: 'summarize',
      metadata: {
        customer_identifier: userId ?? 'anonymous',
        thread_identifier: 'session-abc-123',
        environment: 'development',
        step: 'summarization',
        workflow: 'joke_pipeline',
        provider: 'vercel-ai-gateway',
      },
    },
  });

  return Response.json({
    intent: intentResult.text,
    response: responseResult.text,
    summary: summaryResult.text,
  });
}
