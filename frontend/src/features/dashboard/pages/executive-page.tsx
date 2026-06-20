import { Sparkles } from "lucide-react";

import { KpiCard } from "@/components/charts/kpi-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusChip } from "@/components/trust/status-chip";
import { formatCount, formatMoneyCompact, formatPercent, formatPp } from "@/lib/utils/format";
import { mockExecutive } from "@/lib/mock-data";

/**
 * Screen #4 — Executive Dashboard.
 *
 * KPIs across the top, success-lift breakdown, sparkline placeholder for
 * the trend chart. Backend already exposes /dashboard/executive — swap mock
 * for useQuery when wiring.
 */

export function ExecutivePage(): JSX.Element {
  const k = mockExecutive;

  // Build a fake 7-day series so the chart looks alive.
  const series = Array.from({ length: 7 }, (_, i) => {
    const t = i / 6;
    const base = 0.78 + Math.sin(t * Math.PI) * 0.05;
    const reflow = base + 0.05 + Math.cos(t * Math.PI) * 0.02;
    return { day: i, baseline: base, reflow };
  });
  const maxV = Math.max(...series.flatMap((s) => [s.baseline, s.reflow]));
  const minV = Math.min(...series.flatMap((s) => [s.baseline, s.reflow]));

  return (
    <div className="p-6 max-w-[1280px] mx-auto space-y-6">
      {/* Heading row */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
            Last {k.windowDays} days
          </p>
          <h2 className="mt-1 font-display text-h1 text-foreground">
            How Reflow is performing
          </h2>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-citation-surface px-3 py-1.5 text-body-sm text-citation">
          <Sparkles className="size-3.5" />
          {formatPp(k.successLiftPp)} success lift
        </span>
      </div>

      {/* KPI row */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Reflow success rate"
          value={formatPercent(k.reflowSuccessRate)}
          hint={`Baseline ${formatPercent(k.baselineSuccessRate)} · lift ${formatPp(k.successLiftPp)}`}
          delta={Math.round(k.successLiftPp * 1000) / 10}
          deltaLabel={`${formatPp(k.successLiftPp)}`}
        />
        <KpiCard
          label="Revenue recovered"
          value={formatMoneyCompact(k.revenueRecoveredCents, "USD")}
          hint={`Across ${formatCount(k.recoveriesSucceeded)} recoveries`}
          delta={12.4}
          deltaLabel="+12.4%"
        />
        <KpiCard
          label="Recovery rate"
          value={formatPercent(k.recoveryRate)}
          hint={`${formatCount(k.recoveriesSucceeded)} / ${formatCount(k.recoveriesAttempted)}`}
          delta={3.1}
          deltaLabel="+3.1pp"
        />
        <KpiCard
          label="Duplicate charges"
          value={k.duplicateCharges}
          hint="DB UNIQUE guarantees this stays zero"
          delta={0}
          deltaLabel="—"
          invertDelta
        />
      </div>

      {/* Trend + breakdown */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Success rate · baseline vs Reflow</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="relative h-48">
              <svg
                viewBox="0 0 700 200"
                preserveAspectRatio="none"
                className="absolute inset-0 w-full h-full"
                aria-hidden
              >
                {/* Axis */}
                <line
                  x1="0"
                  x2="700"
                  y1="180"
                  y2="180"
                  className="stroke-border"
                  strokeWidth="1"
                />
                {/* Baseline */}
                <polyline
                  fill="none"
                  className="stroke-foreground-tertiary"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                  points={series
                    .map((p, i) => {
                      const x = (i / (series.length - 1)) * 700;
                      const norm = (p.baseline - minV) / (maxV - minV || 1);
                      const y = 180 - norm * 160;
                      return `${x},${y}`;
                    })
                    .join(" ")}
                />
                {/* Reflow */}
                <polyline
                  fill="none"
                  className="stroke-primary"
                  strokeWidth="2.5"
                  points={series
                    .map((p, i) => {
                      const x = (i / (series.length - 1)) * 700;
                      const norm = (p.reflow - minV) / (maxV - minV || 1);
                      const y = 180 - norm * 160;
                      return `${x},${y}`;
                    })
                    .join(" ")}
                />
                {/* Reflow dots */}
                {series.map((p, i) => {
                  const x = (i / (series.length - 1)) * 700;
                  const norm = (p.reflow - minV) / (maxV - minV || 1);
                  const y = 180 - norm * 160;
                  return (
                    <circle
                      key={i}
                      cx={x}
                      cy={y}
                      r={3}
                      className="fill-primary"
                    />
                  );
                })}
              </svg>
            </div>
            <div className="mt-3 flex items-center gap-4 text-caption text-foreground-secondary">
              <span className="inline-flex items-center gap-1.5">
                <span className="block w-3 h-px bg-primary" />
                Reflow
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="block w-3 h-px bg-foreground-tertiary border-t border-dashed" />
                Baseline
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Status breakdown</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-body-sm">
            {[
              { label: "Recovered", status: "recovered", count: 884 },
              { label: "Succeeded (first try)", status: "succeeded", count: 10535 },
              { label: "Recovering", status: "recovering", count: 23 },
              { label: "Failed", status: "failed", count: 1378 },
              { label: "Abandoned", status: "abandoned", count: 27 },
            ].map((row) => (
              <div key={row.status} className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <StatusChip status={row.status} />
                  <span className="text-foreground-secondary">{row.label}</span>
                </div>
                <span className="font-mono tabular-nums text-foreground">
                  {formatCount(row.count)}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
