import { Check, Clock, Inbox, X } from "lucide-react";
import { Link } from "react-router-dom";

import { StatusChip } from "@/components/trust/status-chip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import * as routes from "@/lib/constants/routes";
import { formatMoney, formatRelative } from "@/lib/utils/format";
import { mockApprovals } from "@/lib/mock-data";

/**
 * Screen #12 — Approvals queue (HITL).
 *
 * Top counter strip + queue list. Each approval surfaces amount + reason
 * with inline approve/reject actions. Click "Review" to drill into the
 * full recovery context.
 */

export function ApprovalsQueuePage(): JSX.Element {
  const approvals = mockApprovals;
  const totalCents = approvals.reduce((acc, a) => acc + a.amountCents, 0);

  return (
    <div className="p-6 max-w-[1100px] mx-auto space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
            Human-in-the-loop queue
          </p>
          <h2 className="mt-1 font-display text-h1 text-foreground">Pending approvals</h2>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-warning-surface px-3 py-1.5 text-body-sm text-warning">
          <Inbox className="size-3.5" />
          {approvals.length} awaiting
        </span>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-4">
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
            In queue
          </p>
          <p className="mt-2 font-display text-h2 text-foreground tabular-nums">
            {approvals.length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
            Total value
          </p>
          <p className="mt-2 font-display text-h2 text-foreground tabular-nums font-mono">
            {formatMoney(totalCents, "USD")}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
            Avg expires in
          </p>
          <p className="mt-2 font-display text-h2 text-foreground">~38 min</p>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Queue</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {approvals.length === 0 ? (
            <div className="p-12 text-center text-foreground-secondary">
              Queue is empty. Reflow will surface high-value or high-risk recoveries here for review.
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {approvals.map((a) => (
                <li
                  key={a.id}
                  className="px-5 py-4 grid gap-3 sm:grid-cols-[1fr_auto] items-start sm:items-center hover:bg-card-hover transition-colors duration-200 ease-considered"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-body-sm text-foreground">{a.id}</span>
                      <span className="text-foreground-tertiary">·</span>
                      <Link
                        to={routes.recovery(a.recoveryId)}
                        className="font-mono text-body-sm text-citation hover:underline underline-offset-4"
                      >
                        {a.transactionExternalId}
                      </Link>
                      <StatusChip status="awaiting_approval" />
                    </div>
                    <p className="text-body text-foreground">
                      <span className="font-mono tabular-nums">
                        {formatMoney(a.amountCents, "USD")}
                      </span>
                      <span className="text-foreground-secondary"> — {a.reason}</span>
                    </p>
                    <p className="flex items-center gap-2 text-caption text-foreground-tertiary">
                      <Clock className="size-3" />
                      requested {formatRelative(a.requestedAt)} · expires {formatRelative(a.expiresAt)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 sm:justify-end">
                    <Button variant="ghost" size="sm">
                      <X className="size-3.5" />
                      Reject
                    </Button>
                    <Button asChild variant="secondary" size="sm">
                      <Link to={routes.recovery(a.recoveryId)}>Review</Link>
                    </Button>
                    <Button size="sm">
                      <Check className="size-3.5" />
                      Approve
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
