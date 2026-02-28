import { RespanTelemetry } from '@respan/tracing';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

const respan = new RespanTelemetry({
    apiKey: process.env.RESPAN_API_KEY || "demo-key",
    appName: "span-buffering-demo",
    logLevel: 'info'
});

async function runSpanBufferingDemo() {
    await respan.initialize();
    console.log("Starting Span Buffering Demo\n");

    // Check if getSpanBufferManager is available
    if (typeof respan.getSpanBufferManager !== 'function') {
        console.log('getSpanBufferManager() is not available in this SDK version');
        console.log('This feature may require a newer version of @respan/tracing');
        await respan.shutdown();
        return;
    }

    const manager = respan.getSpanBufferManager();
    const traceId = "manual-trace-123";
    const buffer = manager.createBuffer(traceId);

    console.log(`Created buffer for trace: ${traceId}`);

    console.log("Creating spans manually in buffer...");
    buffer.createSpan("initial_step", {
        status: "completed",
        duration_ms: 150,
        attributes: { "step.type": "init" }
    });

    buffer.createSpan("processing_step", {
        status: "completed",
        duration_ms: 450,
        attributes: { "step.type": "compute", "complexity": "high" }
    });

    buffer.createSpan("final_step", {
        status: "completed",
        duration_ms: 50,
        attributes: { "step.type": "cleanup" }
    });

    const spans = buffer.getAllSpans();
    console.log(`Total spans in buffer: ${spans.length}`);
    console.log("Span names:", spans.map(s => s.name).join(", "));

    const shouldExport = true;
    if (shouldExport) {
        console.log("Manually processing (exporting) spans...");
        const success = await manager.processSpans(spans);
        console.log(`Processing ${success ? "succeeded" : "failed"}`);
    } else {
        console.log("Clearing spans without exporting...");
        buffer.clearSpans();
    }

    console.log("\nShutting down...");
    await respan.shutdown();
    console.log("Span buffering demo completed.");
}

if (import.meta.url === `file://${process.argv[1]}`) {
    runSpanBufferingDemo().catch(console.error);
}

export { runSpanBufferingDemo };
