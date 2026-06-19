import { StrictMode } from "react";

import { Providers } from "@/app/providers";

/**
 * Root <App />. Until the router is fully wired, render a minimal Vellum
 * "boot" screen that confirms the design system is loaded correctly.
 *
 * Once `app/router.tsx` ships, this becomes `<RouterProvider router={router} />`.
 */
export function App(): JSX.Element {
  return (
    <StrictMode>
      <Providers>
        <BootScreen />
      </Providers>
    </StrictMode>
  );
}

function BootScreen(): JSX.Element {
  return (
    <main className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-xl text-center space-y-6 animate-fade-in">
        <p className="font-mono text-caption uppercase tracking-widest text-foreground-tertiary">
          Reflow · Vellum design system
        </p>
        <h1 className="font-display text-display text-foreground">
          Trustworthy autonomous payment recovery.
        </h1>
        <p className="text-body text-foreground-secondary leading-relaxed">
          Every decision is evidence-based, policy-gated, and cryptographically
          auditable. The frontend boots here. The router ships next.
        </p>
        <div className="flex items-center justify-center gap-2 pt-4">
          <span className="inline-flex items-center gap-2 rounded-full bg-success-surface px-3 py-1 text-body-sm text-success">
            <span className="size-1.5 rounded-full bg-success" />
            Providers wired
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-citation-surface px-3 py-1 text-body-sm text-citation">
            <span className="size-1.5 rounded-full bg-citation" />
            Vellum loaded
          </span>
        </div>
      </div>
    </main>
  );
}
