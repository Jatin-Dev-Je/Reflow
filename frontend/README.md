# Reflow Frontend

> The Vellum design system — Trustworthy Autonomous Payment Recovery, made visible.

## Stack

| Layer | Choice |
|---|---|
| Build / dev | Vite 5 + React 18 |
| Language | TypeScript 5 (strict, noUncheckedIndexedAccess) |
| Routing | React Router v7 (declarative) |
| UI primitives | shadcn/ui on Radix |
| Styling | Tailwind CSS v3 + Vellum CSS variables |
| Server state | TanStack Query v5 |
| Client state | Zustand |
| Tables | TanStack Table v8 |
| Forms | React Hook Form + Zod |
| Charts | Recharts + Tremor |
| WebSocket | react-use-websocket |
| Icons | Lucide |
| Animation | Framer Motion |
| API contract | openapi-typescript + openapi-fetch (codegen from backend) |
| Lint + format | Biome |
| Tests | Vitest + RTL + Playwright + MSW |
| Package mgr | pnpm |

## Architectural principles

1. **Vertical slicing.** Every feature owns its `api/`, `components/`, `hooks/`, `pages/`, `types.ts`, `index.ts`. Mirrors the backend's bounded contexts.
2. **Codegen the API.** Backend OpenAPI → `pnpm gen:api` → typed client everywhere. No hand-maintained API types.
3. **Tokens, not values.** Every colour, spacing unit, radius lives in `src/styles/globals.css` as a CSS variable. Tailwind references them. One file = whole theme.
4. **Three layouts.** `MarketingShell`, `AuthShell`, `AppShell`. 52 screens, 3 layouts.
5. **Co-location.** A component lives next to its test, its types, its query hook.

## Folder structure

```
src/
├── api/                  HTTP/WS integration + OpenAPI codegen output
├── app/                  Wiring (router, providers, query client, boot)
├── components/           Shared/cross-feature components
│   ├── ui/               shadcn/ui primitives
│   ├── layout/           AppShell, Sidebar, Topbar, MarketingShell
│   ├── data/             DataTable, EmptyState, ErrorState, LoadingState
│   ├── trust/            CitationBadge ⭐, CitationDrawer, EventHash
│   └── charts/           KpiCard, TrendChart, ...
├── features/             Vertical slices — mirror backend domains
│   ├── auth/
│   ├── dashboard/
│   ├── transactions/         ← Trust View timeline page ⭐
│   ├── recoveries/
│   ├── diagnoses/
│   ├── strategies/
│   ├── risk/
│   ├── policies/
│   ├── approvals/
│   ├── audit/                ← Verify-proof page ⭐
│   ├── observability/
│   ├── health-intel/
│   ├── simulation/
│   ├── flags/
│   ├── settings/
│   ├── system/
│   ├── onboarding/
│   └── marketing/
├── stores/               App-wide Zustand stores (theme, UI, tenant)
├── lib/                  utils, constants, validation, generic hooks
├── styles/               globals.css (Vellum tokens), fonts.css, animations.css
├── types/                Cross-feature TS declarations
├── test/                 Vitest setup, MSW handlers, render helpers
└── main.tsx              Vite entrypoint
```

Each feature folder follows the same shape:

```
features/<name>/
├── api/        keys.ts (query-key factory), use-*.ts hooks
├── components/ feature-only components
├── hooks/      feature-only hooks
├── pages/      route components
├── types.ts    feature-local types
└── index.ts    public exports (what other features may import)
```

## The Vellum theme

Warm, considered, restrained. Light mode primary; dark mode is "the inside of a leather notebook."

```
SURFACES   #FAF9F7 page · #FFFFFF card · #F4F1EB card-hover
PRIMARY    #2E5D4F  deep forest (trust + money + premium)
CITATION   #C46A52  terracotta — the [1][2][3] signature
SEMANTIC   muted, not bright — success/warning/danger/info
TYPE       Fraunces (display) + Inter (body) + JetBrains Mono
```

See `src/styles/globals.css` for the full token set.

## Getting started

```bash
cd frontend

# 1. Install
pnpm install

# 2. Configure
cp .env.example .env

# 3. Generate API types from the running backend
pnpm gen:api         # requires backend at http://localhost:8000

# 4. Run
pnpm dev             # http://localhost:5173 (proxies /api → backend :8000)
```

## Scripts

```
pnpm dev              # Vite dev server
pnpm build            # Production build → dist/
pnpm preview          # Preview the production build
pnpm typecheck        # tsc --noEmit
pnpm lint             # biome check
pnpm lint:fix         # biome check --write
pnpm test             # Vitest (watch)
pnpm test:run         # Vitest (run once)
pnpm test:coverage    # Vitest with coverage
pnpm e2e              # Playwright
pnpm gen:api          # OpenAPI → src/api/generated/schema.d.ts
```

## Status

Scaffolding in place. Implementation begins next.
