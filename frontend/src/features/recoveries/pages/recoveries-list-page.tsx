import { ArrowUpRight, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { StatusChip } from "@/components/trust/status-chip";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import * as routes from "@/lib/constants/routes";
import { formatCount, formatMoney, formatRelative } from "@/lib/utils/format";
import { mockRecoveries, type MockRecovery } from "@/lib/mock-data";
import { cn } from "@/lib/utils/cn";

/**
 * Screen #10 — Recoveries list.
 *
 * Filter chips on saga state + search. Each row links to the saga viewer.
 */

type StateFilter = "all" | "in_flight" | MockRecovery["state"];

const FILTERS: Array<{ id: StateFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "in_flight", label: "In flight" },
  { id: "awaiting_approval", label: "Awaiting approval" },
  { id: "recovered", label: "Recovered" },
  { id: "failed", label: "Failed" },
];

const IN_FLIGHT_STATES: MockRecovery["state"][] = [
  "created",
  "diagnosed",
  "strategy_proposed",
  "risk_assessed",
  "policy_evaluated",
  "approved",
  "executing",
  "executed",
];

export function RecoveriesListPage(): JSX.Element {
  const [filter, setFilter] = useState<StateFilter>("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(
    () =>
      mockRecoveries
        .filter((r) => {
          if (filter === "all") return true;
          if (filter === "in_flight") return IN_FLIGHT_STATES.includes(r.state);
          return r.state === filter;
        })
        .filter((r) =>
          search.trim() === ""
            ? true
            : [r.id, r.transactionExternalId, r.strategy]
                .filter(Boolean)
                .some((v) => v!.toLowerCase().includes(search.toLowerCase())),
        ),
    [filter, search],
  );

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-h1 text-foreground">Recoveries</h2>
          <p className="mt-1 text-body-sm text-foreground-secondary">
            {formatCount(filtered.length)} of {formatCount(mockRecoveries.length)} sagas
          </p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-foreground-tertiary" />
          <Input
            placeholder="Search recovery id, transaction…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={cn(
              "rounded-full px-3 h-7 text-caption font-medium",
              "border border-border bg-card",
              "transition-colors duration-200 ease-considered",
              "hover:bg-card-hover hover:border-border-strong",
              filter === f.id && "bg-primary-surface border-primary/30 text-primary",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-body-sm">
            <thead>
              <tr className="bg-inset border-b border-border">
                {["Recovery", "Transaction", "Amount", "Strategy", "Risk", "State", "Started", ""].map(
                  (h, i) => (
                    <th
                      key={h + i}
                      className="h-9 px-4 text-left text-caption font-medium uppercase tracking-wider text-foreground-tertiary"
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-16 text-center text-foreground-secondary">
                    No recoveries match your filter.
                  </td>
                </tr>
              ) : (
                filtered.map((r) => (
                  <tr
                    key={r.id}
                    className="border-b border-border last:border-0 transition-colors duration-200 ease-considered hover:bg-card-hover"
                  >
                    <td className="px-4 py-2.5 font-mono text-foreground">{r.id}</td>
                    <td className="px-4 py-2.5">
                      <Link
                        to={routes.transaction(r.transactionId)}
                        className="font-mono text-citation hover:underline underline-offset-4"
                      >
                        {r.transactionExternalId}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 font-mono tabular-nums text-foreground">
                      {formatMoney(r.amountCents, "USD")}
                    </td>
                    <td className="px-4 py-2.5 text-foreground-secondary">
                      {r.strategy ? (
                        <span className="font-mono text-caption">{r.strategy}</span>
                      ) : (
                        <span className="text-foreground-tertiary">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {r.riskLevel ? (
                        <StatusChip status={r.riskLevel} />
                      ) : (
                        <span className="text-foreground-tertiary">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusChip status={r.state} />
                    </td>
                    <td className="px-4 py-2.5 text-foreground-secondary whitespace-nowrap">
                      {formatRelative(r.startedAt)}
                    </td>
                    <td className="px-4 py-2.5">
                      <Link
                        to={routes.recovery(r.id)}
                        className="inline-flex items-center gap-1 text-citation hover:underline underline-offset-4"
                      >
                        Saga
                        <ArrowUpRight className="size-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
