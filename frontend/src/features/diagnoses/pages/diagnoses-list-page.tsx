import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { CitationBadge } from "@/components/trust/citation-badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatCount, formatRelative } from "@/lib/utils/format";
import { mockDiagnoses } from "@/lib/mock-data";
import { cn } from "@/lib/utils/cn";

/**
 * Screen #13 — Diagnoses list.
 *
 * Card grid of recent diagnoses. Each shows root cause, confidence, agent
 * provenance (LLM provider + cost), citation count badges.
 */

export function DiagnosesListPage(): JSX.Element {
  const [search, setSearch] = useState("");
  const filtered = useMemo(
    () =>
      mockDiagnoses.filter((d) =>
        search.trim() === ""
          ? true
          : [d.rootCause, d.rootCauseCategory, d.transactionExternalId]
              .some((v) => v.toLowerCase().includes(search.toLowerCase())),
      ),
    [search],
  );

  return (
    <div className="p-6 max-w-[1280px] mx-auto space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-h1 text-foreground">Diagnoses</h2>
          <p className="mt-1 text-body-sm text-foreground-secondary">
            {formatCount(filtered.length)} recent agent diagnoses · every claim cites ≥1 source
          </p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-foreground-tertiary" />
          <Input
            placeholder="Search root cause, txn…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((d) => (
          <Card key={d.id} interactive className="p-5 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1">
                <p className="font-mono text-caption text-foreground-tertiary truncate">
                  {d.rootCauseCategory}
                </p>
                <p className="text-body text-foreground leading-snug">{d.rootCause}</p>
              </div>
              <ConfidenceGauge value={d.confidence} />
            </div>

            <div className="flex items-center gap-1.5 pt-1">
              {Array.from({ length: d.citationCount }).map((_, i) => (
                <CitationBadge key={i} index={i + 1} />
              ))}
              <span className="text-caption text-foreground-tertiary ml-1">
                {d.citationCount} citation{d.citationCount === 1 ? "" : "s"}
              </span>
            </div>

            <div className="flex items-center justify-between text-caption text-foreground-tertiary pt-2 border-t border-border">
              <span className="font-mono">{d.transactionExternalId}</span>
              <span className="inline-flex items-center gap-1.5">
                {d.llmProvider} · ${d.costUsd.toFixed(5)}
              </span>
              <span>{formatRelative(d.createdAt)}</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ConfidenceGauge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone = pct >= 80 ? "text-success" : pct >= 60 ? "text-warning" : "text-danger";
  return (
    <div className="flex flex-col items-end shrink-0">
      <span className={cn("font-display text-h3 tabular-nums leading-none", tone)}>
        {pct}
      </span>
      <span className="text-caption text-foreground-tertiary mt-0.5">conf</span>
    </div>
  );
}
