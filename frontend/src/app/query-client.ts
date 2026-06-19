import { QueryClient } from "@tanstack/react-query";

import { ReflowApiError } from "@/api/client";

/**
 * Single shared QueryClient.
 *
 * Defaults tuned for an operator dashboard:
 *
 *  - staleTime 30 s  — most queries are still fresh after navigating between
 *                      a list and a detail page. Aggressive zero-stale-time
 *                      causes obvious flicker on the Trust View.
 *  - gcTime    10 min — keep cached data around so going back is instant.
 *  - retry 2         — typed user errors are NOT retried. Network / 5xx are.
 *  - refetchOnWindowFocus: true — operators leave tabs open; refocusing
 *                                 should reflect any changes from other
 *                                 sessions.
 *  - retryDelay: exponential with jitter, capped at 8 s — same shape we use
 *                on the backend.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 10 * 60_000,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      retry: (failureCount, error) => {
        // Never retry typed client errors (validation, conflict, not found).
        if (error instanceof ReflowApiError) {
          if (error.status >= 400 && error.status < 500) return false;
        }
        return failureCount < 2;
      },
      retryDelay: (attempt) => {
        const base = Math.min(1000 * 2 ** attempt, 8000);
        const jitter = base * 0.2 * Math.random();
        return base + jitter;
      },
    },
    mutations: {
      // Mutations are user-initiated — surface failures immediately, never retry.
      retry: false,
    },
  },
});
