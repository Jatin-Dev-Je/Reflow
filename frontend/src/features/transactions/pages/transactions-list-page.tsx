import { ArrowUpRight, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { StatusChip } from "@/components/trust/status-chip";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import * as routes from "@/lib/constants/routes";
import { formatCount, formatMoney, formatRelative } from "@/lib/utils/format";
import { mockTransactions, type MockTransaction } from "@/lib/mock-data";
import { cn } from "@/lib/utils/cn";

/**
 * Screen #7 — Transactions list.
 *
 * Filter chips across the top + searchable table. Each row links to the
 * Trust View timeline for that transaction. Vellum table styling: no
 * stripes, warm hover, mono for IDs.
 */

type StatusFilter = "all" | MockTransaction["status"];

const FILTERS: Array<{ id: StatusFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "failed", label: "Failed" },
  { id: "recovering", label: "Recovering" },
  { id: "recovered", label: "Recovered" },
  { id: "succeeded", label: "Succeeded" },
  { id: "abandoned", label: "Abandoned" },
];

export function TransactionsListPage(): JSX.Element {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    return mockTransactions
      .filter((t) => filter === "all" || t.status === filter)
      .filter((t) =>
        search.trim() === ""
          ? true
          : [t.externalId, t.declineCode, t.issuerId, t.cardLast4]
              .filter(Boolean)
              .some((v) => v!.toLowerCase().includes(search.toLowerCase())),
      );
  }, [filter, search]);

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-5">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-h1 text-foreground">Transactions</h2>
          <p className="mt-1 text-body-sm text-foreground-secondary">
            {formatCount(filtered.length)} of {formatCount(mockTransactions.length)} shown
          </p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-foreground-tertiary" />
          <Input
            placeholder="Search id, decline, issuer…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Filter chips */}
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

      {/* Table */}
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-body-sm">
            <thead>
              <tr className="bg-inset border-b border-border">
                {["External ID", "Amount", "Card", "Gateway", "Issuer", "Decline", "Status", "Age", ""].map(
                  (h, i) => (
                    <th
                      key={h + i}
                      scope="col"
                      className={cn(
                        "h-9 px-4 text-left font-medium text-foreground-tertiary",
                        "text-caption uppercase tracking-wider",
                      )}
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
                  <td colSpan={9} className="px-4 py-16 text-center text-foreground-secondary">
                    No transactions match your filter.
                  </td>
                </tr>
              ) : (
                filtered.map((t) => (
                  <tr
                    key={t.id}
                    className={cn(
                      "border-b border-border last:border-0",
                      "transition-colors duration-200 ease-considered",
                      "hover:bg-card-hover",
                    )}
                  >
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-foreground">{t.externalId}</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono tabular-nums text-foreground">
                      {formatMoney(t.amountCents, t.currency)}
                    </td>
                    <td className="px-4 py-2.5 text-foreground-secondary">
                      {t.cardBrand} · {t.cardLast4}
                    </td>
                    <td className="px-4 py-2.5 text-foreground-secondary">{t.gatewayId}</td>
                    <td className="px-4 py-2.5 text-foreground-secondary">
                      <span className="font-mono text-caption">{t.issuerId}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      {t.declineCode ? (
                        <span className="font-mono text-caption text-danger">
                          {t.declineCode}
                        </span>
                      ) : (
                        <span className="text-foreground-tertiary">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusChip status={t.status} />
                    </td>
                    <td className="px-4 py-2.5 text-foreground-secondary whitespace-nowrap">
                      {formatRelative(t.createdAt)}
                    </td>
                    <td className="px-4 py-2.5">
                      <Link
                        to={routes.transactionTimeline(t.id)}
                        className={cn(
                          "inline-flex items-center gap-1 text-citation",
                          "hover:underline underline-offset-4",
                        )}
                      >
                        Trust View
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
