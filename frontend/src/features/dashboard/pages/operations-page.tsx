import { AlertOctagon, AlertTriangle, Clock, Inbox, Workflow } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCount, formatRelative } from "@/lib/utils/format";
import { mockOperations } from "@/lib/mock-data";

/**
 * Screen #5 — Operations Dashboard.
 *
 * Live counters that the ops team watches. Each counter is a sparse card
 * with a single number — designed for at-a-glance reading.
 */

interface CounterProps {
  label: string;
  value: number;
  icon: LucideIcon;
  description: string;
  tone?: "neutral" | "warning" | "danger";
}

function Counter({ label, value, icon: Icon, description, tone = "neutral" }: CounterProps) {
  const toneClass =
    tone === "danger"
      ? "text-danger bg-danger-surface"
      : tone === "warning"
        ? "text-warning bg-warning-surface"
        : "text-primary bg-primary-surface";
  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <span className={`size-9 rounded-md grid place-items-center ${toneClass}`}>
          <Icon className="size-4" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
            {label}
          </p>
          <p className="mt-1 font-display text-h1 leading-none text-foreground tabular-nums">
            {formatCount(value)}
          </p>
          <p className="mt-1.5 text-body-sm text-foreground-secondary">{description}</p>
        </div>
      </div>
    </Card>
  );
}

export function OperationsPage(): JSX.Element {
  const o = mockOperations;
  return (
    <div className="p-6 max-w-[1280px] mx-auto space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
            Live · refreshed {formatRelative(o.asOf)}
          </p>
          <h2 className="mt-1 font-display text-h1 text-foreground">
            Operations dashboard
          </h2>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Counter
          label="Pending approvals"
          value={o.pendingApprovals}
          icon={Inbox}
          description="Awaiting HITL decision"
          tone={o.pendingApprovals > 0 ? "warning" : "neutral"}
        />
        <Counter
          label="In-flight recoveries"
          value={o.recoveriesInFlight}
          icon={Workflow}
          description="Non-terminal saga states"
        />
        <Counter
          label="Failures · last hour"
          value={o.failuresLastHour}
          icon={AlertTriangle}
          description="Initial declines arriving"
        />
        <Counter
          label="Recoveries · last hour"
          value={o.recoveriesLastHour}
          icon={Clock}
          description="Saga starts in last 60 minutes"
        />
        <Counter
          label="Dead-letter queue"
          value={o.deadLetterCount}
          icon={AlertOctagon}
          description="Outbox events exhausted retry"
          tone={o.deadLetterCount > 0 ? "danger" : "neutral"}
        />
        <Counter
          label="Active kill switches"
          value={o.activeKillSwitches.length}
          icon={AlertOctagon}
          description={o.activeKillSwitches.length === 0 ? "All systems nominal" : "Operator paused"}
          tone={o.activeKillSwitches.length > 0 ? "danger" : "neutral"}
        />
      </div>

      {/* Kill switch list */}
      <Card>
        <CardHeader>
          <CardTitle>Kill switches</CardTitle>
        </CardHeader>
        <CardContent>
          {o.activeKillSwitches.length === 0 ? (
            <div className="rounded-md border border-success/20 bg-success-surface px-4 py-3 text-body-sm text-success">
              No kill switches are active. All recovery paths and gateway integrations
              are running normally.
            </div>
          ) : (
            <ul className="space-y-2">
              {o.activeKillSwitches.map((key) => (
                <li
                  key={key}
                  className="flex items-center gap-3 rounded-md border border-danger/20 bg-danger-surface px-4 py-2 text-body-sm"
                >
                  <AlertOctagon className="size-4 text-danger" />
                  <code className="font-mono text-foreground">{key}</code>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
