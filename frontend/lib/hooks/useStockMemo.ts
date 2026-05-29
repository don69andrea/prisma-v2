import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { getMemo, generateMemo, type Memo } from '@/lib/api/memos';

export interface UseStockMemoResult {
  memo: Memo | null | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  generate: () => Promise<Memo>;
  isGenerating: boolean;
}

/**
 * Lädt ein Memo für (stockId, runId) und stellt Generate-Mutation bereit.
 * Wenn stockId null ist (z.B. Legacy-Run ohne stock_id), wird kein Query ausgeführt.
 */
export function useStockMemo(stockId: string | null, runId: string): UseStockMemoResult {
  const queryClient = useQueryClient();
  const queryKey = ['memo', stockId, runId];

  const query = useQuery({
    queryKey,
    queryFn: () => getMemo(stockId!, runId),
    enabled: stockId !== null,
    staleTime: 5 * 60 * 1000,
  });

  const mutation = useMutation({
    mutationFn: () => generateMemo(stockId!, runId, 'de'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  return {
    memo: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error as Error | null,
    generate: () => mutation.mutateAsync(),
    isGenerating: mutation.isPending,
  };
}
