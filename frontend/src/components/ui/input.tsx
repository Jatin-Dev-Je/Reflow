import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

/**
 * Vellum Input.
 *
 * Sits on the warm vellum page. Border is the considered warm-gray; focus
 * ring is a tinted forest halo (handled globally in globals.css via the
 * :focus-visible rule, so no harsh blue browser default).
 */

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "flex h-10 w-full rounded-md border border-input bg-card",
          "px-3 py-2 text-body text-foreground",
          "transition-colors duration-200 ease-considered",
          "placeholder:text-foreground-tertiary",
          "hover:border-border-strong",
          "focus:outline-none focus:border-primary",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "file:border-0 file:bg-transparent file:font-medium file:text-foreground",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";
