'use client';

import Link from 'next/link';

const TICKER_REGEX = /\b([A-Z]{1,4}\.SW|[A-Z]{2,5})\b/g;

export function parseMessageWithTickers(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  TICKER_REGEX.lastIndex = 0;
  while ((match = TICKER_REGEX.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const ticker = match[0];
    parts.push(
      <Link
        key={`${ticker}-${match.index}`}
        href={`/stocks/${ticker}`}
        className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono bg-purple-900/60 border border-purple-500/40 text-purple-300 hover:bg-purple-800/60 hover:border-purple-400 transition-colors mx-0.5"
      >
        {ticker}
      </Link>
    );
    lastIndex = match.index + ticker.length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}
