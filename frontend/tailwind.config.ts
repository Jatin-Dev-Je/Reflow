import type { Config } from "tailwindcss";
import animatePlugin from "tailwindcss-animate";

/**
 * Tailwind config — every brand color references a CSS variable defined in
 * src/styles/globals.css.  This means the Vellum theme is editable in one
 * file; light/dark swaps come for free; and shadcn/ui components are
 * compatible because they expect this CSS-variable convention.
 */
const config: Config = {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "./tests/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        // ── Vellum surfaces ──────────────────────────────────────────────
        page: "hsl(var(--page))",
        card: "hsl(var(--card))",
        "card-hover": "hsl(var(--card-hover))",
        inset: "hsl(var(--inset))",

        border: "hsl(var(--border))",
        "border-strong": "hsl(var(--border-strong))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",

        // ── Text ──────────────────────────────────────────────────────────
        foreground: "hsl(var(--text-primary))",
        "foreground-secondary": "hsl(var(--text-secondary))",
        "foreground-tertiary": "hsl(var(--text-tertiary))",

        // ── Brand ─────────────────────────────────────────────────────────
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
          hover: "hsl(var(--primary-hover))",
          surface: "hsl(var(--primary-surface))",
        },

        citation: {
          DEFAULT: "hsl(var(--citation))",
          surface: "hsl(var(--citation-surface))",
        },

        // ── Semantic ──────────────────────────────────────────────────────
        success: {
          DEFAULT: "hsl(var(--success))",
          surface: "hsl(var(--success-surface))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          surface: "hsl(var(--warning-surface))",
          foreground: "hsl(var(--warning-foreground))",
        },
        danger: {
          DEFAULT: "hsl(var(--danger))",
          surface: "hsl(var(--danger-surface))",
          foreground: "hsl(var(--danger-foreground))",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          surface: "hsl(var(--info-surface))",
          foreground: "hsl(var(--info-foreground))",
        },

        // shadcn/ui compatibility aliases
        background: "hsl(var(--page))",
        muted: {
          DEFAULT: "hsl(var(--inset))",
          foreground: "hsl(var(--text-secondary))",
        },
        accent: {
          DEFAULT: "hsl(var(--card-hover))",
          foreground: "hsl(var(--text-primary))",
        },
        popover: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--text-primary))",
        },
        secondary: {
          DEFAULT: "hsl(var(--inset))",
          foreground: "hsl(var(--text-primary))",
        },
        destructive: {
          DEFAULT: "hsl(var(--danger))",
          foreground: "hsl(var(--danger-foreground))",
        },
      },

      fontFamily: {
        sans: ["'Inter Variable'", "system-ui", "sans-serif"],
        display: ["'Fraunces Variable'", "Georgia", "serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },

      fontSize: {
        // (size, lineHeight, letterSpacing)
        display: ["2.5rem", { lineHeight: "3rem", letterSpacing: "-0.02em" }],
        h1: ["2rem", { lineHeight: "2.5rem", letterSpacing: "-0.015em" }],
        h2: ["1.5rem", { lineHeight: "2rem", letterSpacing: "-0.01em" }],
        h3: ["1.125rem", { lineHeight: "1.625rem", letterSpacing: "-0.005em" }],
        body: ["0.9375rem", { lineHeight: "1.5rem" }],
        "body-sm": ["0.8125rem", { lineHeight: "1.25rem" }],
        caption: ["0.75rem", { lineHeight: "1.125rem", letterSpacing: "0.01em" }],
        code: ["0.8125rem", { lineHeight: "1.25rem" }],
      },

      borderRadius: {
        lg: "12px",
        md: "10px",
        sm: "6px",
        xs: "4px",
      },

      boxShadow: {
        // Vellum keeps shadows minimal — borders do the work.
        sm: "0 1px 2px 0 rgb(31 29 26 / 0.04)",
        md: "0 2px 6px -1px rgb(31 29 26 / 0.06)",
        lg: "0 8px 24px -8px rgb(31 29 26 / 0.10)",
      },

      transitionTimingFunction: {
        considered: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      transitionDuration: {
        "200": "200ms",
        "250": "250ms",
      },

      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        "warm-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
      },
      animation: {
        "fade-in": "fade-in 250ms cubic-bezier(0.4, 0, 0.2, 1)",
        "slide-in-right": "slide-in-right 300ms cubic-bezier(0.4, 0, 0.2, 1)",
        "warm-pulse": "warm-pulse 1.5s ease-in-out infinite",
      },
    },
  },
  plugins: [animatePlugin],
};

export default config;
