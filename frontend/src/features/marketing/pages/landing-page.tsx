import {
  ArrowRight,
  CheckCircle2,
  FileSearch,
  Lock,
  Microscope,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { MarketingShell } from "@/components/layout/marketing-shell";
import { CitationBadge } from "@/components/trust/citation-badge";
import { StatusChip } from "@/components/trust/status-chip";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import * as routes from "@/lib/constants/routes";

/**
 * Screen #9 — Landing.
 *
 * Hero + product story + product preview + trust pillars + footer CTA.
 * Renders the Vellum design language at marketing pace (generous spacing,
 * serif headlines, restrained colour).
 */

export function LandingPage(): JSX.Element {
  return (
    <MarketingShell>
      {/* Hero */}
      <section className="border-b border-border">
        <div className="max-w-5xl mx-auto px-6 py-24 text-center space-y-8 animate-fade-in">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-citation-surface px-3 py-1 text-caption text-citation">
            <span className="size-1.5 rounded-full bg-citation" />
            Evidence-based recovery for failed payments
          </span>
          <h1 className="font-display text-[56px] leading-[1.05] tracking-[-0.02em] text-foreground">
            Every failed payment.
            <br />
            <span className="text-foreground-secondary">Investigated, explained, recovered.</span>
          </h1>
          <p className="max-w-2xl mx-auto text-body text-foreground-secondary leading-relaxed text-[17px]">
            Reflow is the autonomous payment-recovery platform with a
            cryptographic audit trail. Agents diagnose failures with cited
            evidence. A policy engine gates every action. Three layers of
            idempotency guarantee zero double charges.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <Button asChild size="lg">
              <Link to={routes.REGISTER}>
                Start free
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="secondary">
              <Link to={routes.DASHBOARD_EXECUTIVE}>See the dashboard</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Product preview — a Trust-View-shaped card */}
      <section className="border-b border-border bg-inset">
        <div className="max-w-5xl mx-auto px-6 py-20">
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary text-center">
            The signature interaction
          </p>
          <h2 className="mt-2 text-center font-display text-h1 text-foreground">
            Every decision is citable
          </h2>
          <Card className="mt-10 max-w-3xl mx-auto p-6 space-y-4 bg-card">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-caption text-foreground-tertiary">DiagnosisGenerated</p>
                <p className="mt-1 text-body text-foreground">
                  Diagnosed:&nbsp;
                  <span className="font-mono">issuer_decline</span>
                  &nbsp;(confidence 0.84)
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  <span className="text-caption text-foreground-tertiary">Citations:</span>
                  <CitationBadge index={1} title="Issuer success rate dropped 97% → 63%" />
                  <CitationBadge index={2} title="413 similar failures in last 15 min" />
                  <CitationBadge index={3} title="Historical recovery after 12-min cooldown" />
                </div>
              </div>
              <StatusChip status="approved" />
            </div>
            <div className="pt-4 border-t border-border space-y-2">
              <p className="text-caption uppercase tracking-wider text-foreground-tertiary">Evidence</p>
              <ol className="space-y-2 text-body-sm text-foreground">
                <li className="flex items-start gap-2">
                  <CitationBadge index={1} />
                  Issuer success rate dropped from 97% to 63% over the last 15 minutes
                </li>
                <li className="flex items-start gap-2">
                  <CitationBadge index={2} />
                  413 similar failures in last 15 minutes (pattern memory)
                </li>
                <li className="flex items-start gap-2">
                  <CitationBadge index={3} />
                  Historical recovery rate of 62% after a 12-minute delayed-retry cooldown
                </li>
              </ol>
            </div>
          </Card>
        </div>
      </section>

      {/* Trust pillars */}
      <section className="border-b border-border">
        <div className="max-w-5xl mx-auto px-6 py-24">
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary text-center">
            How we earn trust
          </p>
          <h2 className="mt-2 text-center font-display text-h1 text-foreground">
            Four guarantees, by construction
          </h2>
          <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: Microscope,
                title: "Evidence-based",
                body: "Every diagnosis is required by schema to cite ≥1 source. Bare claims are rejected.",
              },
              {
                icon: ShieldCheck,
                title: "Policy-gated",
                body: "Agents propose. A custom rule engine decides. Every decision is logged with full replay context.",
              },
              {
                icon: Workflow,
                title: "Idempotent",
                body: "HTTP, command, and DB-UNIQUE layers — zero double charges across any failure mode.",
              },
              {
                icon: Lock,
                title: "Verifiable",
                body: "Hash-chained events + Ed25519-signed Merkle anchors. Offline verifiable with the public key.",
              },
            ].map((p) => (
              <Card key={p.title} className="p-5 space-y-3">
                <span className="size-9 rounded-md grid place-items-center bg-primary-surface text-primary">
                  <p.icon className="size-4" />
                </span>
                <p className="font-display text-h3 text-foreground">{p.title}</p>
                <p className="text-body-sm text-foreground-secondary leading-relaxed">{p.body}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Numbers strip */}
      <section className="border-b border-border bg-primary-surface">
        <div className="max-w-5xl mx-auto px-6 py-16 grid gap-8 md:grid-cols-4 text-center">
          {[
            { value: "+9pp", label: "Success lift (50K txn sim)" },
            { value: "38%", label: "Recoverable declines recovered" },
            { value: "0", label: "Duplicate charges, ever" },
            { value: "<5ms", label: "Tier-0 decision latency" },
          ].map((stat) => (
            <div key={stat.label}>
              <p className="font-display text-h1 text-primary tabular-nums">{stat.value}</p>
              <p className="mt-1 text-body-sm text-foreground-secondary">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Closing CTA */}
      <section className="max-w-3xl mx-auto px-6 py-24 text-center space-y-6">
        <FileSearch className="mx-auto size-8 text-citation" />
        <h2 className="font-display text-h1 text-foreground">See it on your traffic</h2>
        <p className="text-body text-foreground-secondary leading-relaxed">
          Connect your gateway in five minutes. Start with shadow mode —
          Reflow proposes decisions without executing, so you can see the lift
          before you trust the system.
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button asChild size="lg">
            <Link to={routes.REGISTER}>
              Create account
              <ArrowRight className="size-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="ghost">
            <Link to="#">
              Talk to sales
            </Link>
          </Button>
        </div>
        <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-body-sm text-foreground-secondary">
          {["No credit card", "Shadow mode default", "5-min gateway setup"].map((it) => (
            <li key={it} className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-success" />
              {it}
            </li>
          ))}
        </ul>
      </section>
    </MarketingShell>
  );
}
