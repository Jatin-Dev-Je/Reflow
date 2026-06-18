import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names with Tailwind-aware deduplication.
 *
 * `clsx` handles conditional / array / object syntax.
 * `twMerge` resolves Tailwind conflicts (later class wins, semantically):
 *   cn("px-2", "px-4")      → "px-4"
 *   cn("text-sm", isLarge && "text-lg")
 *
 * Used by every shadcn/ui primitive and every custom component.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
