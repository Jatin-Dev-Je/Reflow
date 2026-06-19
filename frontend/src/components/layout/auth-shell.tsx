import type { ReactNode } from "react";

/**
 * AuthShell — used by login, register, forgot-password, reset-password,
 * verify-email.
 *
 * The Vellum approach to an auth screen:
 *   - Full-bleed warm vellum page
 *   - Centred content with generous breathing room (Claude-style)
 *   - Mark above (wordmark) + body card + small subtle footer
 *   - No marketing copy in the auth shell — keep the focus on the form
 */

interface AuthShellProps {
  /** The form / interactive content. */
  children: ReactNode;
  /** The page heading rendered above the card. */
  title: string;
  /** Optional supporting copy below the title. */
  subtitle?: string;
  /** Footer slot — usually a "Don't have an account? Sign up" link row. */
  footer?: ReactNode;
}

export function AuthShell({
  children,
  title,
  subtitle,
  footer,
}: AuthShellProps): JSX.Element {
  return (
    <main className="min-h-screen bg-page flex flex-col">
      {/* Wordmark — top-left, restrained */}
      <header className="px-8 py-6">
        <span className="font-display text-h3 tracking-tight text-foreground">
          Reflow
        </span>
      </header>

      {/* Centred panel */}
      <section className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md space-y-8 animate-fade-in">
          <div className="text-center space-y-2">
            <h1 className="font-display text-h1 tracking-tight text-foreground">
              {title}
            </h1>
            {subtitle ? (
              <p className="text-body text-foreground-secondary leading-relaxed">
                {subtitle}
              </p>
            ) : null}
          </div>

          {/* The form itself sits on the warm vellum page directly — Claude-style
              auth forms feel calmer without an outer card. Inputs carry their
              own warm borders for definition. */}
          <div className="space-y-5">{children}</div>

          {footer ? (
            <div className="text-center text-body-sm text-foreground-secondary">
              {footer}
            </div>
          ) : null}
        </div>
      </section>

      {/* Quiet footer line */}
      <footer className="px-8 py-6 flex items-center justify-between text-caption text-foreground-tertiary">
        <span>© Reflow</span>
        <span className="font-mono">Vellum design system</span>
      </footer>
    </main>
  );
}
