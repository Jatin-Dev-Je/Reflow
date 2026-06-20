import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import * as routes from "@/lib/constants/routes";

/**
 * MarketingShell — public-facing layout for landing, pricing, security pages.
 *
 * Minimal top nav with wordmark + a couple of links + auth CTAs. Big quiet
 * footer at the bottom.
 */

interface MarketingShellProps {
  children: ReactNode;
}

export function MarketingShell({ children }: MarketingShellProps): JSX.Element {
  return (
    <div className="min-h-screen bg-page text-foreground flex flex-col">
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto h-16 px-6 flex items-center justify-between">
          <Link to={routes.HOME} className="font-display text-h3 tracking-tight">
            Reflow
          </Link>
          <nav className="hidden md:flex items-center gap-7 text-body-sm text-foreground-secondary">
            <Link to={routes.PRICING} className="hover:text-foreground">Pricing</Link>
            <Link to={routes.SECURITY} className="hover:text-foreground">Security</Link>
            <Link to={routes.CHANGELOG} className="hover:text-foreground">Changelog</Link>
          </nav>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link to={routes.LOGIN}>Sign in</Link>
            </Button>
            <Button asChild size="sm">
              <Link to={routes.REGISTER}>Get started</Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 py-10 grid gap-8 md:grid-cols-4 text-body-sm">
          <div>
            <p className="font-display text-h3 tracking-tight">Reflow</p>
            <p className="mt-2 text-foreground-secondary leading-relaxed">
              Trustworthy autonomous payment recovery. Evidence-based, policy-gated,
              cryptographically auditable.
            </p>
          </div>
          {[
            { heading: "Product", items: ["Features", "Pricing", "Changelog", "Roadmap"] },
            { heading: "Trust", items: ["Security", "Audit chain", "Compliance", "Status"] },
            { heading: "Company", items: ["About", "Careers", "Contact", "Press"] },
          ].map((col) => (
            <div key={col.heading}>
              <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
                {col.heading}
              </p>
              <ul className="mt-3 space-y-1.5">
                {col.items.map((it) => (
                  <li key={it}>
                    <a href="#" className="text-foreground-secondary hover:text-foreground">
                      {it}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="max-w-6xl mx-auto px-6 pb-8 text-caption text-foreground-tertiary flex items-center justify-between">
          <span>© Reflow</span>
          <span className="font-mono">Vellum design system</span>
        </div>
      </footer>
    </div>
  );
}
