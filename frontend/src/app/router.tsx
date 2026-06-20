import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { ApprovalsQueuePage } from "@/features/approvals/pages/approvals-queue-page";
import { ForgotPasswordPage } from "@/features/auth/pages/forgot-password-page";
import { LoginPage } from "@/features/auth/pages/login-page";
import { RegisterPage } from "@/features/auth/pages/register-page";
import { ExecutivePage } from "@/features/dashboard/pages/executive-page";
import { OperationsPage } from "@/features/dashboard/pages/operations-page";
import { TrustPage } from "@/features/dashboard/pages/trust-page";
import { DiagnosesListPage } from "@/features/diagnoses/pages/diagnoses-list-page";
import { LandingPage } from "@/features/marketing/pages/landing-page";
import { PoliciesListPage } from "@/features/policies/pages/policies-list-page";
import { RecoveriesListPage } from "@/features/recoveries/pages/recoveries-list-page";
import { RecoveryDetailPage } from "@/features/recoveries/pages/recovery-detail-page";
import { TransactionsListPage } from "@/features/transactions/pages/transactions-list-page";
import { TrustViewPage } from "@/features/transactions/pages/trust-view-page";
import * as routes from "@/lib/constants/routes";

/**
 * Declarative route tree.
 *
 * - HOME → public landing page (marketing)
 * - /login, /register, /forgot-password → auth shells
 * - /app/* → authenticated AppShell (sidebar + topbar + outlet)
 */
export const router = createBrowserRouter([
  // ── Public ──────────────────────────────────────────────────────────────
  { path: routes.HOME, element: <LandingPage /> },

  // ── Auth ────────────────────────────────────────────────────────────────
  { path: routes.LOGIN, element: <LoginPage /> },
  { path: routes.REGISTER, element: <RegisterPage /> },
  { path: routes.FORGOT_PASSWORD, element: <ForgotPasswordPage /> },

  // ── Authenticated app ───────────────────────────────────────────────────
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

      // Recoveries
      { path: routes.RECOVERIES, element: <RecoveriesListPage /> },
      { path: "/app/recoveries/:id", element: <RecoveryDetailPage /> },

      // Approvals
      { path: routes.APPROVALS, element: <ApprovalsQueuePage /> },

      // Agents
      { path: routes.DIAGNOSES, element: <DiagnosesListPage /> },

      // Policies
      { path: routes.POLICIES, element: <PoliciesListPage /> },

      // Placeholders — render executive dashboard so the sidebar still works.
      { path: routes.SIMULATIONS, element: <ExecutivePage /> },
      { path: routes.AGENT_RUNS, element: <ExecutivePage /> },
      { path: routes.AUDIT_EVENTS, element: <ExecutivePage /> },
      { path: routes.HEALTH_GATEWAYS, element: <ExecutivePage /> },
      { path: routes.OUTAGES, element: <ExecutivePage /> },
      { path: routes.FLAGS, element: <ExecutivePage /> },
      { path: routes.SETTINGS, element: <ExecutivePage /> },
    ],
  },

  // Catch-all → landing.
  { path: "*", element: <Navigate to={routes.HOME} replace /> },
]);
