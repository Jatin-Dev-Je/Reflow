import { Check, Copy } from "lucide-react";

import { useCopy } from "@/lib/hooks/use-copy";
import { shortenHash } from "@/lib/utils/identifiers";
import { cn } from "@/lib/utils/cn";

/**
 * Mono-displayed hash with click-to-copy. Used in the Trust View timeline
 * to surface event_hash + previous_hash without overwhelming the eye.
 */

interface EventHashProps {
  hash: string | null | undefined;
  /** Override the abbreviated display. Default: shortenHash(hash). */
  label?: string;
  className?: string;
}

export function EventHash({ hash, label, className }: EventHashProps): JSX.Element {
  const { copy, copied } = useCopy();
  const display = label ?? shortenHash(hash);

  if (!hash) {
    return (
      <span
        className={cn("font-mono text-caption text-foreground-tertiary", className)}
      >
        —
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={() => {
        void copy(hash);
      }}
      title={hash}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm",
        "px-1.5 py-0.5",
        "font-mono text-caption text-foreground-tertiary",
        "transition-colors duration-200 ease-considered",
        "hover:bg-card-hover hover:text-foreground",
        className,
      )}
      aria-label={copied ? "Copied" : "Copy hash"}
    >
      {display}
      {copied ? (
        <Check className="size-3 text-success" />
      ) : (
        <Copy className="size-3 opacity-50" />
      )}
    </button>
  );
}
