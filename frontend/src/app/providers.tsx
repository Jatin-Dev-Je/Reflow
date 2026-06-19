import { QueryClientProvider } from "@tanstack/react-query";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";
import { useEffect } from "react";

import { queryClient } from "@/app/query-client";
import { useThemeStore } from "@/stores/theme-store";

/**
 * Top-level providers wrapper.
 *
 * Order matters:
 *   1. QueryClientProvider     — server state, available to everything
 *   2. TooltipPrimitive.Provider — Radix tooltips share a portal; mount once
 *   3. ThemeBootstrapper        — applies the Vellum theme class + OS listener
 *
 * The router itself lives one level up (boot.tsx) so it can mount its own
 * loaders within these providers.
 */

interface ProvidersProps {
  children: ReactNode;
}

function ThemeBootstrapper(): null {
  // Run once on mount: apply the rehydrated theme to <html>, register the OS
  // pref listener, return the unsubscribe.
  const initialize = useThemeStore((state) => state.initialize);
  useEffect(() => {
    const cleanup = initialize();
    return cleanup;
  }, [initialize]);
  return null;
}

export function Providers({ children }: ProvidersProps): JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipPrimitive.Provider delayDuration={150} skipDelayDuration={300}>
        <ThemeBootstrapper />
        {children}
      </TooltipPrimitive.Provider>
    </QueryClientProvider>
  );
}
