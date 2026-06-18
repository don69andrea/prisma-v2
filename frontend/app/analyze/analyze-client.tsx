'use client';

import { useState } from 'react';
import { useAnalysisStream } from '@/hooks/useAnalysisStream';

export default function AnalyzeClient() {
  const [ticker, setTicker] = useState('');
  const { steps, checkpoint, result, running, error, start, answerCheckpoint } =
    useAnalysisStream();

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Investment-Analyse</h1>

      <div className="flex gap-3">
        <input
          className="flex-1 border rounded-lg px-4 py-2 text-sm bg-background"
          placeholder="Ticker (z.B. NESN.SW)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          disabled={running}
        />
        <button
          className="px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
          onClick={() => start(ticker)}
          disabled={running || !ticker}
        >
          {running ? 'Analysiert…' : 'Analysieren'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {steps.length > 0 && (
        <div className="space-y-2">
          {steps.map((s, i) => (
            <div key={i} className="flex items-start gap-3 text-sm">
              <span
                className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                  s.status === 'done'
                    ? 'bg-green-500'
                    : s.status === 'error'
                      ? 'bg-red-500'
                      : 'bg-yellow-400 animate-pulse'
                }`}
              />
              <span className="font-medium w-36 shrink-0">{s.agent}</span>
              <span className="text-muted-foreground">{s.result ?? s.status}</span>
            </div>
          ))}
        </div>
      )}

      {checkpoint && (
        <div className="border rounded-xl p-5 bg-muted/40 space-y-3">
          <p className="font-medium text-sm">{checkpoint.message}</p>
          <div className="flex flex-wrap gap-2">
            {checkpoint.options.map((opt) => (
              <button
                key={opt}
                className="px-4 py-2 rounded-lg border text-sm hover:bg-accent transition-colors"
                onClick={() => answerCheckpoint(checkpoint.checkpoint_id, opt)}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      )}

      {result && (
        <div className="border rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xl font-bold">{result.signal}</span>
            <span className="text-sm text-muted-foreground">
              Konfidenz: {(result.confidence * 100).toFixed(0)}%
            </span>
          </div>
          {result.report && (
            <div className="text-sm space-y-1 text-muted-foreground">
              {result.report.macro_reasoning && (
                <p>{String(result.report.macro_reasoning)}</p>
              )}
              {Array.isArray(result.report.steuer_hinweise) && (
                <ul className="list-disc list-inside">
                  {(result.report.steuer_hinweise as string[]).map((h, i) => (
                    <li key={i}>{h}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
