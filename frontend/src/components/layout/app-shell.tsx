import { Outlet, useLocation } from "react-router-dom";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import * as routes from "@/lib/constants/routes";

const TITLES: Record<string, string> = {
  [routes.DASHBOARD_EXECUTIVE]: "Executive dashboard",
  [routes.DASHBOARD_OPERATIONS]: "Operations dashboard",
  [routes.DASHBOARD_TRUST]: "Trust dashboard",
  [routes.TRANSACTIONS]: "Transactions",
  [routes.RECOVERIES]: "Recoveries",
  [routes.APPROVALS]: "Approvals",
  [routes.SIMULATIONS]: "Simulation",
  [routes.DIAGNOSES]: "Diagnoses",
  [routes.POLICIES]: "Policies",
  [routes.AGENT_RUNS]: "Agent runs",
  [routes.AUDIT_EVENTS]: "Audit log",
  [routes.HEALTH_GATEWAYS]: "Gateway health",
  [routes.OUTAGES]: "Outages",
  [routes.FLAGS]: "Feature flags",
  [routes.SETTINGS]: "Settings",
};

function titleFor(pathname: string): string {
  if (TITLES[pathname]) return TITLES[pathname];
  // Match dynamic transaction/recovery detail
  if (pathname.startsWith("/app/transactions/")) return "Transaction";
  if (pathname.startsWith("/app/recoveries/")) return "Recovery";
  if (pathname.startsWith("/app/diagnoses/")) return "Diagnosis";
  if (pathname.startsWith("/app/audit/")) return "Audit";
  return "Reflow";
}

export function AppShell(): JSX.Element {
  const { pathname } = useLocation();
  return (
    <div className="h-screen bg-page flex">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar title={titleFor(pathname)} />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
