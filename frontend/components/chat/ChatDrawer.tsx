'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { MessageSquare, X, RotateCcw, Send } from 'lucide-react';

import { streamChat, type ChatHistoryMessage, type SSEEvent } from '@/lib/api/chat';
import { ChatMessageBubble } from './ChatMessage';
import { cn } from '@/lib/utils';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const SUGGESTED: Record<string, string[]> = {
  default: [
    'Welche SMI-Titel sind 3a-geeignet mit BUY-Signal?',
    'Was ist der aktuelle SNB-Leitzins?',
    'Zeig mir die Top-5 SMI-Aktien',
  ],
};

export function ChatDrawer() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [toolHint, setToolHint] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, toolHint]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || streaming) return;

      const history: ChatHistoryMessage[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      setMessages((prev) => [...prev, { role: 'user', content: text }]);
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
      setStreaming(true);
      setInput('');

      abortRef.current = streamChat(
        text,
        history,
        (evt: SSEEvent) => {
          if (evt.type === 'token' && evt.content) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: updated[updated.length - 1].content + evt.content,
              };
              return updated;
            });
            setToolHint(null);
          } else if (evt.type === 'tool_call' && evt.tool) {
            setToolHint(`Fetching ${evt.tool.replace(/_/g, ' ')}...`);
          }
        },
        () => {
          setStreaming(false);
          setToolHint(null);
        },
        (msg) => {
          setStreaming(false);
          setToolHint(null);
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: `Fehler: ${msg}`,
            };
            return updated;
          });
        },
      );
    },
    [messages, streaming],
  );

  const reset = () => {
    abortRef.current?.();
    setMessages([]);
    setStreaming(false);
    setToolHint(null);
  };

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full flex items-center justify-center',
          'bg-purple-600 hover:bg-purple-500 text-white shadow-lg transition-all duration-200',
          open && 'rotate-180 bg-purple-800',
        )}
        style={{
          boxShadow: '0 0 0 0 rgba(168,85,247,0.4)',
          animation: open ? undefined : 'pulse-ring 2s infinite',
        }}
        aria-label="PRISMA Chat öffnen"
      >
        {open ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
      </button>

      {/* Drawer */}
      <div
        className={cn(
          'fixed bottom-24 right-6 z-50 w-[400px] rounded-2xl overflow-hidden',
          'border border-purple-500/20 shadow-2xl',
          'transition-all duration-300 origin-bottom-right',
          open ? 'scale-100 opacity-100' : 'scale-95 opacity-0 pointer-events-none',
        )}
        style={{
          background: 'rgba(8,8,20,0.92)',
          backdropFilter: 'blur(20px)',
          height: '570px',
          boxShadow: '0 0 40px rgba(168,85,247,0.15), 0 25px 50px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm font-semibold text-white">PRISMA Assistant</span>
          </div>
          <button onClick={reset} className="text-slate-500 hover:text-slate-300 transition-colors">
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-1" style={{ height: '390px' }}>
          {messages.length === 0 && (
            <div className="text-center pt-8 space-y-3">
              <p className="text-xs text-slate-600">Stell mir eine Frage über PRISMA-Daten</p>
              <div className="space-y-2">
                {SUGGESTED.default.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="block w-full text-left text-xs px-3 py-2 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-400 hover:border-purple-500/40 hover:text-slate-300 transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessageBubble
              key={i}
              role={msg.role}
              content={msg.content}
              isStreaming={streaming && i === messages.length - 1 && msg.role === 'assistant'}
              toolHint={streaming && i === messages.length - 1 && msg.role === 'assistant' ? toolHint ?? undefined : undefined}
            />
          ))}
        </div>

        {/* Session cost estimate */}
        {messages.length > 0 && (
          <div className="px-3 py-1 text-xs text-white/30 text-right border-t border-slate-800/40">
            Session: ~CHF {((messages.length / 2) * 0.0015).toFixed(3)}
          </div>
        )}

        {/* Tool capabilities hint */}
        <div className="flex flex-wrap gap-1.5 px-3 py-2 border-t border-slate-800/60">
          <span className="text-[10px] font-medium text-slate-500 self-center">Ich kann:</span>
          {[
            "🔍 Aktien suchen",
            "🔧 Aktien filtern",
            "📄 Factsheets laden",
            "📊 Aktien vergleichen",
            "🌍 Makrokontext abfragen",
            "🏆 Rankings anzeigen",
          ].map((cap) => (
            <span
              key={cap}
              className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800/60 border border-slate-700/50 text-slate-400"
            >
              {cap}
            </span>
          ))}
        </div>

        {/* Input */}
        <div className="px-3 pb-3 pt-2">
          <div className="flex items-center gap-2 bg-slate-800/60 rounded-xl px-3 py-2 border border-slate-700/60 focus-within:border-purple-500/40 transition-colors">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
              placeholder="Frag mich nach Aktien, Vergleichen, Makro oder Rankings..."
              disabled={streaming}
              className="flex-1 bg-transparent text-sm text-white placeholder-slate-600 outline-none"
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || streaming}
              className="text-purple-400 hover:text-purple-300 disabled:opacity-30 transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse-ring {
          0% { box-shadow: 0 0 0 0 rgba(168,85,247,0.4); }
          70% { box-shadow: 0 0 0 12px rgba(168,85,247,0); }
          100% { box-shadow: 0 0 0 0 rgba(168,85,247,0); }
        }
      `}</style>
    </>
  );
}
