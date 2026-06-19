import * as LabelPrimitive from "@radix-ui/react-label";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";

import { cn } from "@/lib/utils/cn";

/**
 * Vellum Label.
 *
 * Caption-sized, slightly tracked uppercase optional class. Pairs with Input
 * via Radix's controlled htmlFor link.
 */
export const Label = forwardRef<
  ElementRef<typeof LabelPrimitive.Root>,
  ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn(
      "text-body-sm font-medium leading-none text-foreground-secondary",
      "peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
Label.displayName = "Label";
