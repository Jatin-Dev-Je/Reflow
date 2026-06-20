import { ArrowLeft, Check, CircleDot, Clock } from "lucide-react";
import { Link } from "react-router-dom";

import { CitationBadge } from "@/components/trust/citation-badge";
import { StatusChip } from "@/components/trust/status-chip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import * as routes from "@/lib/constants/routes";
import { formatMoney, formatRelative } from "@/lib/utils/format";
import { getSagaSteps, mockRecoveries } from "@/lib/mock-data";
import { cn } from "@/lib/utils/cn";

/**
 * Screen #11 — Recovery saga viewer.
 *
 * Horizontal stepper showing every state the saga passed through, plus a
 * detail panel for each step with the agent telemetry / artifact link.
 */

export function RecoveryDetailPage(): JSX.Element {
  // Demo: pick the first non-completed recovery.
  const recovery =
    mockRecoveries.find((r) => r.state === "awaiting_approval") ?? mockRecoveries[0]!;
  const steps = getSagaSteps(recovery.state);

  return (
    <div className="p-6 max-w-[1100px] mx-auto space-y-6">
      <Link
        to={routes.RECOVERIES}
        className="inline-flex items-center gap-1 text-body-sm text-foreground-secondary hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        Back to recoveries
      </Link>

      {/* Header */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
                Recovery
              </p>
              <CardTitle className="font-mono text-h2">{recovery.id}</CardTitle>
            </div>
            <StatusChip status={recovery.state} />
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-body-sm">
          <Detail
            label="Transaction"
            value={
              <Link
                to={routes.transaction(recovery.transactionId)}
                className="font-mono text-citation hover:underline underline-offset-4"
              >
                {recovery.transactionExternalId}
              </Link>
            }
          />
          <Detail
            label="Amount"
            value={
              <span className="font-mono tabular-nums">
                {formatMoney(recovery.amountCents, "USD")}
              </span>
            }
          />
          <Detail
            label="Strategy"
            value={
              recovery.strategy ? (
                <span className="font-mono text-caption">{recovery.strategy}</span>
              ) : (
                <span className="text-foreground-tertiary">—</span>
              )
            }
          />
          <Detail
            label="Started"
            value={<span className="text-foreground">{formatRelative(recovery.startedAt)}</span>}
          />
        </CardContent>
      </Card>

      {/* Horizontal stepper */}
      <Card>
        <CardHeader>
          <CardTitle>Saga state machine</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <ol className="flex items-start gap-0 min-w-[700px]">
            {steps.map((step, i) => {
              const isCurrent = step.detail === "current";
              const isOk = step.reached && step.detail !== "current";
              return (
                <li key={step.state} className="flex-1 flex flex-col items-center text-center">
                  <div className="relative w-full flex items-center justify-center">
                    {i > 0 ? (
                      <span
                        className={cn(
                          "absolute left-0 right-1/2 top-1/2 -translate-y-1/2 h-px",
                          step.reached ? "bg-primary" : "bg-border",
                        )}
                      />
                    ) : null}
                    {i < steps.length - 1 ? (
                      <span
                        className={cn(
                          "absolute left-1/2 right-0 top-1/2 -translate-y-1/2 h-px",
                          steps[i + 1]?.reached ? "bg-primary" : "bg-border",
                        )}
                      />
                    ) : null}
                    <span
                      className={cn(
                        "relative z-10 size-6 rounded-full grid place-items-center",
                        isOk && "bg-primary text-primary-foreground",
                        isCurrent && "bg-citation-surface text-citation ring-2 ring-citation/30",
                        !step.reached && "bg-card border border-border text-foreground-tertiary",
                      )}
                    >
                      {isOk ? (
                        <Check className="size-3.5" />
                      ) : isCurrent ? (
                        <CircleDot className="size-3.5" />
                      ) : (
                        <span className="size-1.5 rounded-full bg-current opacity-50" />
                      )}
                    </span>
                  </div>
                  <p
                    className={cn(
                      "mt-2 text-caption capitalize whitespace-nowrap",
                      isCurrent ? "text-citation font-medium" : "text-foreground-secondary",
                    )}
                  >
                    {step.name}
                  </p>
                </li>
              );
            })}
          </ol>
        </CardContent>
      </Card>

      {/* Chain artifacts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Diagnosis</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-body-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-caption text-foreground-secondary">
                root_cause_category
              </span>
              <span className="font-mono text-foreground">issuer_decline</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-caption text-foreground-secondary">confidence</span>
              <span className="font-mono tabular-nums text-foreground">0.84</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-caption text-foreground-secondary">recoverable</span>
              <StatusChip status="active" label="Yes" tone="success" />
            </div>
            <div className="pt-2 border-t border-border space-y-2">
              <p className="text-caption uppercase tracking-wider text-foreground-tertiary">
                Citations
              </p>
              <div className="space-y-1.5">
                <p className="flex items-start gap-2 text-foreground-secondary">
                  <CitationBadge index={1} />
                  Issuer success rate 92% → 41% in last 15m
                </p>
                <p className="flex items-start gap-2 text-foreground-secondary">
                  <CitationBadge index={2} />
                  413 similar failures · pattern_match
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Strategy &amp; risk</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-body-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-caption text-foreground-secondary">
                strategy_kind
              </span>
              <span className="font-mono text-foreground">delayed_retry · 12min</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-caption text-foreground-secondary">
                expected_recovery_probability
              </span>
              <span className="font-mono tabular-nums text-foreground">0.62</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-caption text-foreground-secondary">risk_level</span>
              <StatusChip status="low" tone="success" />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-caption text-foreground-secondary">
                dup_charge_probability
              </span>
              <span className="font-mono tabular-nums text-foreground">0.02</span>
            </div>
            <div className="pt-2 border-t border-border flex items-center gap-2">
              <Clock className="size-3.5 text-foreground-tertiary" />
              <p className="text-caption text-foreground-tertiary">
                Awaiting human approval — value exceeds HITL threshold.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-caption uppercase tracking-wider text-foreground-tertiary">{label}</p>
      <p className="mt-1 text-foreground">{value}</p>
    </div>
  );
}
