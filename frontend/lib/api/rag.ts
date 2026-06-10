import { apiFetch } from './client';

// ---- SEC Filings RAG -------------------------------------------------------

export interface SecChunkResult {
  chunk_id: string;
  document_id: string;
  chunk_idx: number;
  content: string;
  similarity: number;
  ticker: string;
  doc_type: string;
}

export interface SecRetrieveRequest {
  query: string;
  k?: number;
  ticker?: string;
}

export interface SecRetrieveResponse {
  results: SecChunkResult[];
  total: number;
}

export async function retrieveSecFilings(req: SecRetrieveRequest): Promise<SecRetrieveResponse> {
  return apiFetch<SecRetrieveResponse>('/api/v1/rag/retrieve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}

// ---- Swiss Annual Reports RAG ---------------------------------------------

export interface SwissChunkResult {
  chunk_id: string;
  chunk_idx: number;
  url: string;
  ticker: string;
  source: string;
  language: string;
  filing_date: string;
  doc_type: string;
  content: string;
  similarity: number;
}

export interface SwissRetrieveRequest {
  query: string;
  k?: number;
  ticker?: string;
  language?: 'de' | 'en' | 'fr';
}

export interface SwissRetrieveResponse {
  results: SwissChunkResult[];
  total: number;
}

export async function retrieveSwissFilings(req: SwissRetrieveRequest): Promise<SwissRetrieveResponse> {
  return apiFetch<SwissRetrieveResponse>('/api/v1/rag/swiss/retrieve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
