import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { ForgotPasswordPage } from "@/features/auth/pages/forgot-password-page";
import { LoginPage } from "@/features/auth/pages/login-page";
import { RegisterPage } from "@/features/auth/pages/register-page";
import { ExecutivePage } from "@/features/dashboard/pages/executive-page";
import { OperationsPage } from "@/features/dashboard/pages/operations-page";
import { TrustPage } from "@/features/dashboard/pages/trust-page";
import { TransactionsListPage } from "@/features/transactions/pages/transactions-list-page";
import { TrustViewPage } from "@/features/transactions/pages/trust-view-page";
import * as routes from "@/lib/constants/routes";

/**
 * Declarative route tree.
 *
 * /app/* routes share the AppShell layout (sidebar + topbar + outlet).
 * Public + auth routes have their own shells, mounted at the top level.
 */
export const router = createBrowserRouter([
  // ── Public root ─────────────────────────────────────────────────────────
  {
    path: routes.HOME,
    element: <Navigate to={routes.DASHBOARD_EXECUTIVE} replace />,
  },

  // ── Auth ────────────────────────────────────────────────────────────────
  { path: routes.LOGIN, element: <LoginPage /> },
  { path: routes.REGISTER, element: <RegisterPage /> },
  { path: routes.FORGOT_PASSWORD, element: <ForgotPasswordPage /> },

  // ── Authenticated app — wrapped in AppShell ─────────────────────────────
  {
    element: <AppShell />,
    children: [
      // Dashboards
      { path: routes.DASHBOARD_EXECUTIVE, element: <ExecutivePage /> },
      { path: routes.DASHBOARD_OPERATIONS, element: <OperationsPage /> },
      { path: routes.DASHBOARD_TRUST, element: <TrustPage /> },

      // Transactions
      { path: routes.TRANSACTIONS, element: <TransactionsListPage /> },
      { path: "/app/transactions/:id", element: <TrustViewPage /> },
      { path: "/app/transactions/:id/timeline", element: <TrustViewPage /> },

      // Placeholders for screens we haven't built yet — render the
      // executive dashboard so the sidebar nav still works.
      { path: routes.RECOVERIES, element: <ExecutivePage /> },
      { path: routes.APPROVALS, element: <ExecutivePage /> },
      { path: routes.SIMULATIONS, element: <ExecutivePage /> },
      { path: routes.DIAGNOSES, element: <ExecutivePage /> },
      { path: routes.POLICIES, element: <ExecutivePage /> },
      { path: routes.AGENT_RUNS, element: <ExecutivePage /> },
      { path: routes.AUDIT_EVENTS, element: <ExecutivePage /> },
      { path: routes.HEALTH_GATEWAYS, element: <ExecutivePage /> },
      { path: routes.OUTAGES, element: <ExecutivePage /> },
      { path: routes.FLAGS, element: <ExecutivePage /> },
      { path: routes.SETTINGS, element: <ExecutivePage /> },
    ],
  },

  // Catch-all → executive dashboard.
  { path: "*", element: <Navigate to={routes.DASHBOARD_EXECUTIVE} replace /> },
]);
