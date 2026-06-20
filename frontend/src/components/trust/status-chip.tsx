import { cn } from "@/lib/utils/cn";

type Tone = "success" | "warning" | "danger" | "info" | "neutral" | "primary";

const TONE_MAP: Record<Tone, { dot: string; bg: string; text: string }> = {
  success: { dot: "bg-success", bg: "bg-success-surface", text: "text-success" },
  warning: { dot: "bg-warning", bg: "bg-warning-surface", text: "text-warning" },
  danger: { dot: "bg-danger", bg: "bg-danger-surface", text: "text-danger" },
  info: { dot: "bg-info", bg: "bg-info-surface", text: "text-info" },
  neutral: { dot: "bg-foreground-tertiary", bg: "bg-inset", text: "text-foreground-secondary" },
  primary: { dot: "bg-primary", bg: "bg-primary-surface", text: "text-primary" },
};

const STATUS_TONE: Record<string, Tone> = {
  pending: "neutral",
  succeeded: "success",
  recovered: "success",
  failed: "danger",
  recovering: "warning",
  abandoned: "neutral",
  created: "neutral",
  diagnosed: "info",
  strategy_proposed: "info",
  risk_assessed: "info",
  policy_evaluated: "primary",
  awaiting_approval: "warning",
  approved: "primary",
  executing: "warning",
  executed: "success",
  compensating: "warning",
  allow: "success",
  deny: "danger",
  require_approval: "warning",
  active: "success",
  inactive: "neutral",
};

interface StatusChipProps {
  status: string;
  tone?: Tone;
  label?: string;
  className?: string;
}

export function StatusChip({ status, tone, label, className }: StatusChipProps): JSX.Element {
  const resolved = tone ?? STATUS_TONE[status.toLowerCase()] ?? "neutral";
  const { dot, bg, text } = TONE_MAP[resolved];
  const displayLabel = label ?? status.replace(/_/g, " ");

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5",
        "text-caption font-medium capitalize",
        bg,
        text,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-[2px]", dot)} aria-hidden />
      {displayLabel}
    </span>
  );
}
