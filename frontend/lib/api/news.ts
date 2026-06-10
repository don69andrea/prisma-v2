import { apiFetch } from './client';

export interface NewsChunkResult {
  chunk_id: string;
  news_document_id: string;
  chunk_idx: number;
  content: string;
  similarity: number;
  title: string;
  source: string;
  tickers: string[];
  published_at: string | null;
}

export interface NewsRetrieveRequest {
  query: string;
  k?: number;
  ticker?: string;
}

export interface NewsRetrieveResponse {
  results: NewsChunkResult[];
  total: number;
}

export async function retrieveNews(req: NewsRetrieveRequest): Promise<NewsRetrieveResponse> {
  return apiFetch<NewsRetrieveResponse>('/api/v1/news/retrieve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
