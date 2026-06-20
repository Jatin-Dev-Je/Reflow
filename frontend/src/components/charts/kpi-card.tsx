import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils/cn";

interface KpiCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  delta?: number;
  deltaLabel?: string;
  invertDelta?: boolean;
  chart?: ReactNode;
  className?: string;
}

export function KpiCard({
  label,
  value,
  hint,
  delta,
  deltaLabel,
  invertDelta = false,
  chart,
  className,
}: KpiCardProps): JSX.Element {
  const trend = delta === undefined || delta === 0 ? "flat" : delta > 0 ? "up" : "down";
  const positive = invertDelta ? trend === "down" : trend === "up";
  const tone =
    trend === "flat"
      ? { bg: "bg-inset", text: "text-foreground-secondary" }
      : positive
        ? { bg: "bg-success-surface", text: "text-success" }
        : { bg: "bg-danger-surface", text: "text-danger" };
  const Icon = trend === "flat" ? Minus : trend === "up" ? ArrowUpRight : ArrowDownRight;
  const displayDelta =
    deltaLabel ?? (delta !== undefined ? `${delta > 0 ? "+" : ""}${delta}` : "");

  return (
    <Card className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
          {label}
        </p>
        {displayDelta ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5",
              "text-caption font-medium",
              tone.bg,
              tone.text,
            )}
          >
            <Icon className="size-3" />
            {displayDelta}
          </span>
        ) : null}
      </div>
      <div className="mt-3 font-display text-h1 leading-tight text-foreground tabular-nums">
        {value}
      </div>
      {hint ? (
        <p className="mt-1 text-body-sm text-foreground-secondary">{hint}</p>
      ) : null}
      {chart ? <div className="mt-4">{chart}</div> : null}
    </Card>
  );
}
