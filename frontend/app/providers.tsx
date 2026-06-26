'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, useEffect, type ReactNode } from 'react';
import { ApiError } from '@/lib/api/client';

import { LoadingScreen } from '@/components/LoadingScreen';
import { ColdStartBanner } from '@/components/ui/ColdStartBanner';
import { WelcomePopup } from '@/components/ui/WelcomePopup';
import { AuthProvider } from '@/hooks/useAuth';

const LOADING_DURATION_MS = 1800;
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
            retry: (failureCount, error) => {
              if (error instanceof ApiError && error.status === 401) return false;
              return failureCount < 1;
            },
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
        <WelcomePopup />
        <ColdStartBanner />
        {children}
      </AuthProvider>
    </QueryClientProvider>
  );
}
