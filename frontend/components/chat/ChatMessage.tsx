'use client';

import { parseMessageWithTickers } from './TickerChip';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  toolHint?: string;
}

export function ChatMessageBubble({ role, content, isStreaming, toolHint }: Props) {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
          isUser
            ? 'bg-purple-900/60 text-white'
            : 'bg-slate-900/80 border border-purple-500/20 text-slate-200'
        }`}
        style={isUser ? undefined : { boxShadow: '0 0 12px rgba(168,85,247,0.1)' }}
      >
        {toolHint && (
          <p className="text-[11px] text-slate-500 italic mb-1">{toolHint}</p>
        )}
        <p className="leading-relaxed whitespace-pre-wrap">
          {isUser ? content : parseMessageWithTickers(content)}
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-purple-400 ml-0.5 animate-pulse align-middle" />
          )}
        </p>
      </div>
    </div>
  );
}
