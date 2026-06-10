export interface SSEEvent {
  type: 'token' | 'tool_call' | 'tool_result' | 'done' | 'error';
  content?: string;
  tool?: string;
  result?: string;
  message?: string;
}

export interface ChatHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export function streamChat(
  message: string,
  history: ChatHistoryMessage[],
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError: (msg: string) => void,
): () => void {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  const ctrl = new AbortController();

  fetch(`${API_BASE}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
    signal: ctrl.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt: SSEEvent = JSON.parse(line.slice(6));
            if (evt.type === 'done') onDone();
            else if (evt.type === 'error') onError(evt.message ?? 'Fehler');
            else onEvent(evt);
          } catch {
            // malformed line — skip
          }
        }
      }
    })
    .catch((e) => {
      if (e.name !== 'AbortError') onError(e.message);
    });

  return () => ctrl.abort();
}
