import { useCallback, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type StepEvent = {
  type: 'step';
  agent: string;
  status: string;
  result?: string;
};

export type CheckpointEvent = {
  type: 'checkpoint';
  checkpoint_id: string;
  message: string;
  options: string[];
};

export type DoneEvent = {
  type: 'done';
  run_id: string;
  signal: string;
  confidence: number;
  report: Record<string, unknown>;
};

export type DirectorEvent =
  | StepEvent
  | CheckpointEvent
  | DoneEvent
  | { type: 'error'; error: string };

export function useAnalysisStream() {
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [checkpoint, setCheckpoint] = useState<CheckpointEvent | null>(null);
  const [result, setResult] = useState<DoneEvent | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback((ticker: string, context = 'unknown') => {
    setSteps([]);
    setCheckpoint(null);
    setResult(null);
    setError(null);
    setRunning(true);

    const url = `${API_BASE}/api/v1/analyze/stream?ticker=${encodeURIComponent(ticker)}&context=${context}`;
    const source = new EventSource(url, { withCredentials: true });

    source.onmessage = (e) => {
      const event: DirectorEvent = JSON.parse(e.data as string);
      if (event.type === 'step') {
        setSteps((prev) => [...prev, event]);
      } else if (event.type === 'checkpoint') {
        setCheckpoint(event);
      } else if (event.type === 'done') {
        setResult(event);
        setRunning(false);
        source.close();
      } else if (event.type === 'error') {
        setError(event.error);
        setRunning(false);
        source.close();
      }
    };

    source.onerror = () => {
      setError('Verbindungsfehler');
      setRunning(false);
      source.close();
    };
  }, []);

  const answerCheckpoint = useCallback(async (cpId: string, answer: string) => {
    setCheckpoint(null);
    await fetch(`${API_BASE}/api/v1/analyze/checkpoint/${cpId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ answer }),
    });
  }, []);

  return { steps, checkpoint, result, running, error, start, answerCheckpoint };
}
