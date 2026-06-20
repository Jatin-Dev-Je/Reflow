import { CheckCircle2, FileCheck, Lock, ShieldCheck } from "lucide-react";

import { KpiCard } from "@/components/charts/kpi-card";
import { EventHash } from "@/components/trust/event-hash";
import { StatusChip } from "@/components/trust/status-chip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent, formatRelative } from "@/lib/utils/format";
import { mockTrust } from "@/lib/mock-data";

/**
 * Screen #6 — Trust Dashboard.
 *
 * The compliance + safety story in one screen: duplicate-charge guarantee,
 * policy enforcement, evidence coverage, audit chain liveness.
 */

export function TrustPage(): JSX.Element {
  const t = mockTrust;
  return (
    <div className="p-6 max-w-[1280px] mx-auto space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
            Compliance &amp; trust signals
          </p>
          <h2 className="mt-1 font-display text-h1 text-foreground">
            Trust dashboard
          </h2>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-success-surface px-3 py-1.5 text-body-sm text-success">
          <CheckCircle2 className="size-3.5" />
          All guarantees holding
        </span>
      </div>

      {/* KPI row */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Duplicate charges"
          value={t.duplicateCharges}
          hint="DB UNIQUE constraint enforced"
          delta={0}
          deltaLabel="0 ever"
          invertDelta
        />
        <KpiCard
          label="Evidence coverage"
          value={formatPercent(t.evidenceCoverage, 0)}
          hint={`${t.diagnosesWithEvidence}/${t.diagnosesTotal} diagnoses cite ≥1 source`}
        />
        <KpiCard
          label="Policy denials · 24h"
          value={t.policyDenialsLast24h}
          hint={`${t.policyApprovalsRequiredLast24h} required human approval`}
        />
        <KpiCard
          label="Audit chain anchors"
          value={t.auditChainAnchors}
          hint={`Last signed ${formatRelative(t.lastAnchorAt)}`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Audit chain status */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="size-4 text-primary" />
              Audit chain
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3 text-body-sm">
              <div>
                <p className="text-caption uppercase tracking-wider text-foreground-tertiary">
                  Algorithm
                </p>
                <p className="mt-1 font-mono text-foreground">Ed25519</p>
              </div>
              <div>
                <p className="text-caption uppercase tracking-wider text-foreground-tertiary">
                  Hash
                </p>
                <p className="mt-1 font-mono text-foreground">SHA-256</p>
              </div>
              <div>
                <p className="text-caption uppercase tracking-wider text-foreground-tertiary">
                  Key ID
                </p>
                <p className="mt-1 font-mono text-foreground">local-v1</p>
              </div>
            </div>
            <div className="rounded-md border border-border bg-inset p-3 space-y-1">
              <p className="text-caption uppercase tracking-wider text-foreground-tertiary">
                Latest Merkle root
              </p>
              <div className="flex items-center justify-between gap-2">
                <EventHash hash="0a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9" />
                <StatusChip status="active" label="Verified" tone="success" />
              </div>
            </div>
            <p className="text-body-sm text-foreground-secondary leading-relaxed">
              Every event is hash-chained on write. Periodic batches are signed
              with Ed25519; anyone holding the public key can verify any
              historical event offline.
            </p>
          </CardContent>
        </Card>

        {/* Recent policy decisions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-primary" />
              Recent policy decisions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-body-sm">
            {[
              { outcome: "allow", rule: null, reason: "No restrictive rule matched" },
              { outcome: "require_approval", rule: "high_value.requires_approval", reason: "Amount ≥ HITL threshold" },
              { outcome: "deny", rule: "duplicate_prevention.high_risk", reason: "Dup-charge probability 0.27" },
              { outcome: "allow", rule: null, reason: "No restrictive rule matched" },
              { outcome: "deny", rule: "retry_limit.exceeded", reason: "Attempt 4 > budget 3" },
            ].map((d, i) => (
              <div
                key={i}
                className="flex items-start justify-between gap-3 py-1.5 border-b border-border last:border-0"
              >
                <div className="min-w-0 space-y-0.5">
                  {d.rule ? (
                    <p className="font-mono text-caption text-foreground truncate">
                      {d.rule}
                    </p>
                  ) : (
                    <p className="text-caption text-foreground-tertiary italic">
                      default allow
                    </p>
                  )}
                  <p className="text-body-sm text-foreground-secondary truncate">
                    {d.reason}
                  </p>
                </div>
                <StatusChip status={d.outcome} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Pillars */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCheck className="size-4 text-primary" />
            Trust pillars
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 text-body-sm">
            {[
              {
                title: "Evidence-based",
                body: "Every diagnosis enforces ≥1 citation at the schema level. Bare claims are rejected.",
              },
              {
                title: "Policy-gated",
                body: "Agents propose; the policy engine decides. Every decision is logged with full context for replay.",
              },
              {
                title: "Idempotent",
                body: "Three layers — HTTP, command, gateway UNIQUE. Zero double charges in the simulator runs.",
              },
              {
                title: "Verifiable",
                body: "Hash-chained events + signed Merkle anchors. Offline verifiable with the public key.",
              },
            ].map((p) => (
              <div
                key={p.title}
                className="rounded-md border border-border bg-page p-4 space-y-2"
              >
                <p className="font-display text-h3 text-foreground">{p.title}</p>
                <p className="text-foreground-secondary leading-relaxed">{p.body}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
