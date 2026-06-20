import { GitBranch, Plus } from "lucide-react";

import { StatusChip } from "@/components/trust/status-chip";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatCount, formatRelative } from "@/lib/utils/format";
import { mockPolicies } from "@/lib/mock-data";

/**
 * Screen #14 — Policies list.
 *
 * Single source of policy state: current version, decisions in last 24h,
 * lifecycle (draft / active / retired). New-policy CTA at top-right.
 */

export function PoliciesListPage(): JSX.Element {
  const active = mockPolicies.filter((p) => p.status === "active").length;
  const drafts = mockPolicies.filter((p) => p.status === "draft").length;

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-h1 text-foreground">Policies</h2>
          <p className="mt-1 text-body-sm text-foreground-secondary">
            {formatCount(active)} active · {formatCount(drafts)} draft · {formatCount(mockPolicies.length)} total
          </p>
        </div>
        <Button>
          <Plus className="size-3.5" />
          New policy
        </Button>
      </div>

      <div className="grid gap-4">
        {mockPolicies.map((p) => (
          <Card key={p.id} interactive className="p-5">
            <div className="grid gap-4 sm:grid-cols-[1fr_auto] items-start">
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <GitBranch className="size-4 text-foreground-tertiary" />
                  <p className="font-mono text-body text-foreground">{p.name}</p>
                  <StatusChip status={p.status} />
                </div>
                <p className="text-body-sm text-foreground-secondary leading-relaxed">
                  {p.description}
                </p>
                <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-caption text-foreground-tertiary">
                  <span>
                    v{p.currentVersion} of {p.versionCount}
                  </span>
                  <span>·</span>
                  <span>
                    <span className="font-mono tabular-nums text-foreground-secondary">
                      {formatCount(p.decisionsLast24h)}
                    </span>{" "}
                    decisions · last 24h
                  </span>
                  <span>·</span>
                  <span>updated {formatRelative(p.updatedAt)}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 sm:justify-end">
                <Button variant="secondary" size="sm">
                  Versions
                </Button>
                <Button variant="secondary" size="sm">
                  Simulate
                </Button>
                <Button size="sm">Edit</Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
