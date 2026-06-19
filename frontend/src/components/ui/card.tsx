import { forwardRef, type HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

/**
 * Vellum Card — THE component that defines the design system.
 *
 * Default (static): white surface, warm border. No shadow at rest.
 * `interactive`: enables the Claude-style warm-shift hover:
 *   background  card  →  card-hover (#FFFFFF → #F4F1EB)
 *   border      border → border-strong
 *   NO transform, NO scale, NO box-shadow on hover
 *   200ms ease-considered — feels deliberate, not snappy
 *
 * Compose: <Card><CardHeader><CardTitle>…</CardTitle></CardHeader>…</Card>
 */

interface CardRootProps extends HTMLAttributes<HTMLDivElement> {
  /** Enable warm-shift hover + cursor change. */
  interactive?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardRootProps>(
  ({ className, interactive = false, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-md border border-border bg-card text-foreground",
        "transition-colors duration-200 ease-considered",
        interactive && [
          "cursor-pointer",
          "hover:bg-card-hover hover:border-border-strong",
        ],
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex flex-col gap-1.5 p-5", className)}
      {...props}
    />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn("font-display text-h3 leading-snug text-foreground", className)}
      {...props}
    />
  ),
);
CardTitle.displayName = "CardTitle";

export const CardDescription = forwardRef<
  HTMLParagraphElement,
  HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-body-sm text-foreground-secondary leading-relaxed", className)}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("px-5 pb-5", className)} {...props} />
  ),
);
CardContent.displayName = "CardContent";

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex items-center px-5 pb-5", className)}
      {...props}
    />
  ),
);
CardFooter.displayName = "CardFooter";
