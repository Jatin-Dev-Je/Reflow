import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

/**
 * Vellum Button.
 *
 * - "primary"   : solid forest, white text, soft shadow on hover (no lift)
 * - "secondary" : white surface, warm border, warm-shift on hover
 * - "ghost"     : transparent, warm-shift on hover
 * - "destructive": muted danger
 * - "link"      : underline-on-hover only
 *
 * No scale/translate animations. The Vellum interaction grammar: background
 * shifts, borders darken, shadows are minimal.
 */

const buttonVariants = cva(
  // Base styles applied to every variant.
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "rounded-md font-medium text-body-sm",
    "transition-colors duration-200 ease-considered",
    "focus-visible:outline-none focus-visible:ring-0",
    "disabled:opacity-50 disabled:pointer-events-none",
    "[&_svg]:size-4 [&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        primary: [
          "bg-primary text-primary-foreground",
          "hover:bg-primary-hover hover:shadow-sm",
        ].join(" "),
        secondary: [
          "bg-card text-foreground border border-border",
          "hover:bg-card-hover hover:border-border-strong",
        ].join(" "),
        ghost: [
          "bg-transparent text-foreground",
          "hover:bg-card-hover",
        ].join(" "),
        destructive: [
          "bg-danger text-danger-foreground",
          "hover:opacity-90",
        ].join(" "),
        outline: [
          "bg-transparent text-foreground border border-border-strong",
          "hover:bg-card-hover",
        ].join(" "),
        link: [
          "bg-transparent text-primary",
          "underline-offset-4 hover:underline",
        ].join(" "),
      },
      size: {
        sm: "h-8 px-3 text-caption",
        md: "h-9 px-4",
        lg: "h-11 px-6 text-body",
        icon: "size-9 px-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as a different element (e.g. an `<a>`) while keeping the styles. */
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Component = asChild ? Slot : "button";
    return (
      <Component
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
