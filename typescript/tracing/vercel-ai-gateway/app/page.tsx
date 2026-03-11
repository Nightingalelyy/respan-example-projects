'use client';

import { useState } from 'react';

export default function Home() {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const trigger = async () => {
    setResult(null);
    setLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: 'demo-user' }),
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ error: String(err) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ maxWidth: 600, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h1>Vercel AI Gateway + Respan Tracing</h1>
      <p style={{ color: '#666', fontSize: 14 }}>
        Triggers a workflow with 3 nested tasks, each making an LLM call.
      </p>
      <button
        onClick={trigger}
        disabled={loading}
        style={{ padding: '12px 24px', fontSize: 16, cursor: 'pointer', borderRadius: 4 }}
      >
        {loading ? 'Running...' : 'Trigger Workflow'}
      </button>

      {result && (
        <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 16, borderRadius: 4, marginTop: 16, fontSize: 13 }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </main>
  );
}
