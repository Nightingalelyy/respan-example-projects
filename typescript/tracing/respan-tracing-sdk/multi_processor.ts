import { RespanTelemetry } from '@respan/tracing';
import { updateCurrentSpan, addSpanEvent } from '@respan/tracing';
import * as fs from 'fs';
import * as path from 'path';
import dotenv from 'dotenv';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

/**
 * This example demonstrates span tracking and custom logging:
 * 1. Tracking different types of tasks (normal, debug, analytics, slow)
 * 2. Adding custom attributes and events (via `updateCurrentSpan`, `addSpanEvent`)
 * 3. Demonstrating a multi-processor pipeline with:
 *    - routing (different processors handle different span types)
 *    - filters (processors decide which spans they accept)
 *    - multiple exporters (console + file exporters)
 *
 * Note: The public README references an `addProcessor` API, but not all SDK
 * versions expose a stable processor hook yet. To keep the example accurate and
 * runnable across versions, this file implements a small "processor pipeline"
 * in userland that consumes the same span metadata we attach via the SDK.
 */

type SpanExportRecord = {
  name: string;
  type: string;
  durationMs: number;
  startedAtIso: string;
  endedAtIso: string;
  attributes?: Record<string, unknown>;
  events?: Array<{
    name: string;
    attributes?: Record<string, unknown>;
    timestampMs: number;
  }>;
};

type SpanExporter = {
  name: string;
  export: (record: SpanExportRecord) => void | Promise<void>;
};

type SpanProcessor = {
  name: string;
  /** Return true when this processor should receive the span record. */
  matches: (record: SpanExportRecord) => boolean;
  exporters: SpanExporter[];
};

// Helper to log span information to file
function logSpanToFile(filepath: string, spanInfo: any) {
  try {
    const dir = path.dirname(filepath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.appendFileSync(filepath, JSON.stringify(spanInfo) + '\n');
    console.log(`  Logged to ${filepath}`);
  } catch (error) {
    console.error('  File logging error:', error);
  }
}

// Helper to log span information to console
function logSpanToConsole(prefix: string, spanInfo: any) {
  console.log(`  [${prefix}] ${spanInfo.name} - ${spanInfo.type}`);
}

function createFileExporter(filepath: string): SpanExporter {
  return {
    name: `file:${filepath}`,
    export: (record) => logSpanToFile(filepath, record),
  };
}

function createConsoleExporter(prefix: string): SpanExporter {
  return {
    name: `console:${prefix}`,
    export: (record) => logSpanToConsole(prefix, record),
  };
}

async function processWithProcessors(
  processors: SpanProcessor[],
  record: SpanExportRecord,
) {
  const matched = processors.filter((p) => {
    try {
      return p.matches(record);
    } catch {
      return false;
    }
  });

  if (matched.length === 0) {
    return;
  }

  // Fan-out: one record can be exported by multiple processors/exporters.
  await Promise.all(
    matched.flatMap((p) =>
      p.exporters.map(async (e) => {
        try {
          await e.export(record);
        } catch (error) {
          console.error(`  Exporter error (${p.name} -> ${e.name}):`, error);
        }
      }),
    ),
  );
}

async function runMultiProcessorDemo() {
  console.log('Starting Span Tracking & Logging Demo\n');

  const respan = new RespanTelemetry({
    apiKey: process.env.RESPAN_API_KEY || 'demo-key',
    baseURL: process.env.RESPAN_BASE_URL,
    appName: 'span-tracking-demo',
    logLevel: 'info',
    disableBatch: true,
  });

  await respan.initialize();
  console.log('Tracing initialized\n');

  // Processor setup: routing + filters + multiple exporters.
  const processors: SpanProcessor[] = [
    {
      name: 'debug-processor',
      matches: (r) => r.type === 'debug',
      exporters: [createFileExporter('./debug-spans.jsonl')],
    },
    {
      name: 'analytics-processor',
      matches: (r) => r.type === 'analytics',
      exporters: [
        createConsoleExporter('Analytics'),
        createFileExporter('./analytics-spans.jsonl'),
      ],
    },
    {
      name: 'slow-processor',
      matches: (r) => r.type === 'slow' || r.durationMs >= 150,
      exporters: [
        createConsoleExporter('SlowSpans'),
        createFileExporter('./slow-spans.jsonl'),
      ],
    },
    {
      name: 'default-console-processor',
      matches: (_r) => true,
      exporters: [createConsoleExporter('Default')],
    },
  ];

  await respan.withWorkflow({ name: 'span_tracking_workflow' }, async () => {
    // Normal task - standard tracing
    console.log('1. Normal Task:');
    await respan.withTask({ name: 'normal_task' }, async () => {
      const startTime = Date.now();
      updateCurrentSpan({
        attributes: {
          'task.type': 'normal',
          'task.priority': 'medium',
        },
      });
      addSpanEvent('task.started', { timestampMs: Date.now() });
      await new Promise((resolve) => setTimeout(resolve, 50));
      addSpanEvent('task.completed', { timestampMs: Date.now() });

      const now = Date.now();
      const record: SpanExportRecord = {
        name: 'normal_task',
        type: 'normal',
        durationMs: now - startTime,
        startedAtIso: new Date(startTime).toISOString(),
        endedAtIso: new Date(now).toISOString(),
        attributes: { 'task.type': 'normal', 'task.priority': 'medium' },
        events: [
          { name: 'task.started', timestampMs: startTime },
          { name: 'task.completed', timestampMs: now },
        ],
      };

      await processWithProcessors(processors, record);
      console.log('  Completed (processed via routing pipeline)');
    });

    // Debug task - with debug logging
    console.log('\n2. Debug Task:');
    await respan.withTask({ name: 'debug_task' }, async () => {
      const startTime = Date.now();
      updateCurrentSpan({
        attributes: {
          'task.type': 'debug',
          'task.priority': 'low',
          'debug.enabled': true,
        },
      });
      addSpanEvent('debug.started', { level: 'verbose' });
      
      await new Promise((resolve) => setTimeout(resolve, 50));
      
      const endTime = Date.now();
      const spanInfo = {
        name: 'debug_task',
        type: 'debug',
        durationMs: endTime - startTime,
        startedAtIso: new Date(startTime).toISOString(),
        endedAtIso: new Date(endTime).toISOString(),
        attributes: {
          'task.type': 'debug',
          'task.priority': 'low',
          'debug.enabled': true,
        },
      };
      
      await processWithProcessors(processors, spanInfo);
      addSpanEvent('debug.logged', { file: 'debug-spans.jsonl' });
      console.log('  Completed (processed by debug processor)');
    });

    // Analytics task - with console analytics
    console.log('\n3. Analytics Task:');
    await respan.withTask({ name: 'analytics_task' }, async () => {
      const startTime = Date.now();
      updateCurrentSpan({
        attributes: {
          'task.type': 'analytics',
          'task.priority': 'high',
          'analytics.enabled': true,
        },
      });
      addSpanEvent('analytics.started', { metrics: 'enabled' });
      
      await new Promise((resolve) => setTimeout(resolve, 80));
      
      const endTime = Date.now();
      const spanInfo = {
        name: 'analytics_task',
        type: 'analytics',
        durationMs: endTime - startTime,
        metrics: { processed: 42, errors: 0 },
        startedAtIso: new Date(startTime).toISOString(),
        endedAtIso: new Date(endTime).toISOString(),
        attributes: {
          'task.type': 'analytics',
          'task.priority': 'high',
          'analytics.enabled': true,
        },
      };
      
      await processWithProcessors(processors, spanInfo);
      addSpanEvent('analytics.completed', { records: 42 });
      console.log('  Completed (processed by analytics processor)');
    });

    // Slow task - demonstrates long-running operation
    console.log('\n4. Slow Task (long-running):');
    await respan.withTask({ name: 'slow_task' }, async () => {
      const startTime = Date.now();
      updateCurrentSpan({
        attributes: {
          'task.type': 'slow',
          'task.priority': 'low',
          'performance.warning': true,
        },
      });
      addSpanEvent('slow.task.started', { expected_duration: '200ms' });
      
      await new Promise((resolve) => setTimeout(resolve, 200));
      
      const endTime = Date.now();
      const duration = endTime - startTime;
      const spanInfo = {
        name: 'slow_task',
        type: 'slow',
        durationMs: duration,
        warning: duration > 100 ? 'Exceeded threshold' : null,
        startedAtIso: new Date(startTime).toISOString(),
        endedAtIso: new Date(endTime).toISOString(),
        attributes: {
          'task.type': 'slow',
          'task.priority': 'low',
          'performance.warning': true,
        },
      };
      
      await processWithProcessors(processors, spanInfo);
      addSpanEvent('slow.task.completed', { actual_duration: duration });
      console.log(`  Completed in ${duration}ms (processed by slow processor)`);
    });
  });

  console.log('\nShutting down...');
  await respan.shutdown();
  console.log('Span tracking demo completed.');
  console.log('\nCheck these files for logged spans:');
  console.log('   - ./debug-spans.jsonl');
  console.log('   - ./analytics-spans.jsonl');
  console.log('   - ./slow-spans.jsonl');
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runMultiProcessorDemo().catch(console.error);
}

export { runMultiProcessorDemo, logSpanToFile, logSpanToConsole };
