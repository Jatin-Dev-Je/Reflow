import type { MouseEvent } from "react";

import { cn } from "@/lib/utils/cn";

/**
 * The [1] [2] [3] citation badge — Vellum's signature interaction.
 *
 * Pill, terracotta surface, terracotta text. Hover gets a slightly stronger
 * background. Clicking opens the citation drawer with source query + raw data.
 */

interface CitationBadgeProps {
  index: number;
  /** Click handler — wire to ui-store.openCitation in the page using it. */
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  /** Tooltip text — usually the observation. */
  title?: string;
  className?: string;
}

export function CitationBadge({
  index,
  onClick,
  title,
  className,
}: CitationBadgeProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={`Citation ${index}${title ? `: ${title}` : ""}`}
      className={cn(
        "inline-flex items-center justify-center",
        "min-w-[22px] h-[22px] px-1.5 rounded-full",
        "font-mono text-caption font-medium leading-none",
        "bg-citation-surface text-citation",
        "transition-colors duration-200 ease-considered",
        "hover:bg-citation/20",
        "focus-visible:bg-citation/20",
        className,
      )}
    >
      [{index}]
    </button>
  );
}
