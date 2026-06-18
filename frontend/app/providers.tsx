'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect, type ReactNode } from 'react';

import { LoadingScreen } from '@/components/LoadingScreen';
import { ColdStartBanner } from '@/components/ui/ColdStartBanner';
import { AuthProvider } from '@/hooks/useAuth';

const LOADING_DURATION_MS = 4000;
const FADE_OUT_MS = 400;

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            gcTime: 5 * 60 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: 0,
          },
        },
      })
  );

  const [showLoading, setShowLoading] = useState(true);
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    const fadeTimer = setTimeout(() => setFadeOut(true), LOADING_DURATION_MS);
    const hideTimer = setTimeout(() => setShowLoading(false), LOADING_DURATION_MS + FADE_OUT_MS);
    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(hideTimer);
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {showLoading && <LoadingScreen fadeOut={fadeOut} />}
        <ColdStartBanner />
        {children}
      </AuthProvider>
    </QueryClientProvider>
  );
}
