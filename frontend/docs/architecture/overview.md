# Reflow Frontend — Architecture Overview

> Vellum is the brand. Vite + React is the runtime. Vertical slices are the organising principle.

---

## 1. Principles

These are non-negotiable. Every component must respect them.

| # | Principle | Implication |
|---|---|---|
| 1 | **Vertical slicing** | Each feature owns its components, hooks, queries, pages, types. No `components/`, `hooks/`, `pages/` top-level folders crammed with hundreds of files. |
| 2 | **Codegen the API contract** | OpenAPI → typed client. Backend drift becomes a TypeScript error, not a production bug. |
| 3 | **Tokens, not values** | All design decisions (colour, spacing, radius, motion) live in CSS variables. Tailwind references them. The whole theme is one file. |
| 4 | **Public API per feature** | Each feature has an `index.ts` that re-exports what other features may import. Internal helpers stay internal. |
| 5 | **Three shells** | `MarketingShell`, `AuthShell`, `AppShell`. 52 screens, 3 layouts. Patterns repeat. |
| 6 | **Co-location of test + source** | `Component.tsx` + `Component.test.tsx` together. Hunting for tests in a `__tests__/` folder is friction. |
| 7 | **Suspense-friendly data flow** | TanStack Query owns server state. Components read it; they don't trigger it. |
| 8 | **No global anything** | No global mutable state, no global event bus, no global `window.X`. Everything passes through React or Zustand stores. |

---

## 2. Layered model

```
┌──────────────────────────────────────────────────────────────┐
│                       Routes (URLs)                          │
│                  declared in app/router.tsx                  │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    Pages (features/*/pages)                  │
│   one file per route. composes feature components + queries  │
└──────────┬─────────────────────────────────┬─────────────────┘
           │                                 │
┌──────────▼─────────────────────────────────▼─────────────────┐
│  Feature components       │     Shared components             │
│  (features/*/components)  │     (components/{ui,layout,...})  │
└──────────┬────────────────┴──────────────┬──────────────────┘
           │                                │
┌──────────▼───────────────┐    ┌───────────▼──────────────────┐
│  Feature hooks +         │    │  Shared lib                  │
│  query keys              │    │  (utils, constants, hooks)   │
│  (features/*/api +       │    │                              │
│   features/*/hooks)      │    │                              │
└──────────┬───────────────┘    └──────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────────────┐
│              API client (openapi-fetch)                       │
│                src/api/client.ts                              │
└──────────┬───────────────────────────────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────────────┐
│           Generated TypeScript schema                         │
│           src/api/generated/schema.d.ts                       │
└──────────────────────────────────────────────────────────────┘
```

Rule of dependency: **outer depends on inner, never the reverse**. A feature may import from `components/`, `lib/`, `api/`. A shared component may NOT import from a feature.

---

## 3. Feature folder shape (repeated 18 times)

```
features/<name>/
├── api/
│   ├── keys.ts             query-key factory ⭐ — TanStack Query best practice
│   ├── use-<resource>s.ts  list query
│   ├── use-<resource>.ts   single query
│   └── use-<action>.ts     mutation
├── components/             feature-only React components
├── hooks/                  feature-only custom hooks
├── pages/                  route components (one per URL)
├── types.ts                feature-local TS types (not generated)
└── index.ts                public exports
```

### Why `api/keys.ts`?

TanStack Query cache invalidation goes wrong without a key factory. Pattern:

```ts
export const transactionKeys = {
  all: ["transactions"] as const,
  lists: () => [...transactionKeys.all, "list"] as const,
  list: (filters: TransactionFilters) =>
    [...transactionKeys.lists(), filters] as const,
  details: () => [...transactionKeys.all, "detail"] as const,
  detail: (id: string) => [...transactionKeys.details(), id] as const,
  timeline: (id: string) =>
    [...transactionKeys.detail(id), "timeline"] as const,
} as const;
```

Now `queryClient.invalidateQueries({ queryKey: transactionKeys.lists() })` only invalidates list queries, not detail queries. No stringly-typed keys. No drift.

---

## 4. Shared components — three buckets

| Bucket | Purpose | Examples |
|---|---|---|
| `components/ui/` | shadcn/ui primitives. Atoms. | Button, Card, Input, Dialog, Tabs |
| `components/layout/` | Shell pieces used by exactly one of the 3 layouts | AppShell, Sidebar, Topbar, MarketingShell |
| `components/data/` | Generic data display patterns | DataTable, EmptyState, ErrorState |
| `components/trust/` | The Reflow-specific brand patterns | CitationBadge ⭐, CitationDrawer, EventHash |
| `components/charts/` | Recharts wrappers with Vellum theming | KpiCard, TrendChart |

`components/trust/` is where the brand lives. The CitationBadge is the most-used component in the whole product — it's the visual signature of "evidence-based decisions."

---

## 5. App wiring (`src/app/`)

This folder contains exactly four files:

| File | Job |
|---|---|
| `boot.tsx` | Root `<App />`, top-level error boundary, Suspense fallback |
| `providers.tsx` | QueryClient, Theme, Router, Tooltip, Toast — every provider |
| `query-client.ts` | TanStack Query defaults: stale time, retry, refetch on focus |
| `router.tsx` | Declarative React Router v7 tree, importing pages from features |

Nothing else lives here. If you find yourself adding files to `app/`, that file probably belongs in a feature folder.

---

## 6. Vellum design system

See `src/styles/globals.css` for the full token set. The system:

- **Light primary, warm dark.** Light is Anthropic-paper. Dark is warm leather notebook.
- **One brand colour** (deep forest), **one signature accent** (terracotta for citations).
- **Three shadow tiers** kept minimal — borders carry weight in Vellum.
- **Two-family typography**: Fraunces (serif display) + Inter (sans body) + JetBrains Mono.
- **Motion**: 200–250ms ease-out. Considered, not snappy.

Tailwind config (`tailwind.config.ts`) maps these tokens to utility classes. Components use the utilities, not raw hex values.

---

## 7. What is explicitly NOT yet built

Being honest with the audit trail. Documented gaps:

| Gap | When |
|---|---|
| API codegen output (`src/api/generated/schema.d.ts`) | After backend is reachable; `pnpm gen:api` |
| shadcn/ui primitives | First batch alongside Trust View timeline |
| Storybook | Phase 2, after component library stabilizes |
| i18n | Phase 3, English-only for v1 |
| Sentry integration | When we deploy |
| OpenTelemetry browser SDK | When we have a real backend trace target |
| Accessibility audit | Continuous, but full WCAG 2.2 AA cert is post-MVP |
