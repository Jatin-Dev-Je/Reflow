import {
  Activity,
  AlertTriangle,
  BarChart3,
  ChevronLeft,
  ClipboardCheck,
  Compass,
  CreditCard,
  FileCheck,
  Flag,
  GitBranch,
  Microscope,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { NavLink } from "react-router-dom";

import { useUiStore } from "@/stores/ui-store";
import * as routes from "@/lib/constants/routes";
import { cn } from "@/lib/utils/cn";

/**
 * Vellum sidebar — left nav for every authenticated screen.
 *
 * Three sections: Overview, Operations, Trust + Settings.
 * Active route gets the citation-surface wash (subtle warm tint) with a
 * left forest accent bar. Hover follows the Vellum warm-shift rule.
 */

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

interface NavSection {
  heading: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    heading: "Overview",
    items: [
      { to: routes.DASHBOARD_EXECUTIVE, label: "Executive", icon: BarChart3 },
      { to: routes.DASHBOARD_OPERATIONS, label: "Operations", icon: Activity },
      { to: routes.DASHBOARD_TRUST, label: "Trust", icon: ShieldCheck },
    ],
  },
  {
    heading: "Recovery flow",
    items: [
      { to: routes.TRANSACTIONS, label: "Transactions", icon: CreditCard },
      { to: routes.RECOVERIES, label: "Recoveries", icon: Workflow },
      { to: routes.APPROVALS, label: "Approvals", icon: ClipboardCheck },
      { to: routes.SIMULATIONS, label: "Simulation", icon: Sparkles },
    ],
  },
  {
    heading: "Agents & policy",
    items: [
      { to: routes.DIAGNOSES, label: "Diagnoses", icon: Microscope },
      { to: routes.POLICIES, label: "Policies", icon: GitBranch },
      { to: routes.AGENT_RUNS, label: "Agent runs", icon: Compass },
    ],
  },
  {
    heading: "Trust",
    items: [
      { to: routes.AUDIT_EVENTS, label: "Audit log", icon: FileCheck },
      { to: routes.HEALTH_GATEWAYS, label: "Health intel", icon: Activity },
      { to: routes.OUTAGES, label: "Outages", icon: AlertTriangle },
    ],
  },
  {
    heading: "Workspace",
    items: [
      { to: routes.FLAGS, label: "Flags", icon: Flag },
      { to: routes.SETTINGS, label: "Settings", icon: SettingsIcon },
    ],
  },
];

export function Sidebar(): JSX.Element {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);

  return (
    <aside
      data-collapsed={collapsed || undefined}
      className={cn(
        "shrink-0 border-r border-border bg-page",
        "transition-[width] duration-200 ease-considered",
        collapsed ? "w-[60px]" : "w-[232px]",
        "flex flex-col",
      )}
    >
      {/* Wordmark */}
      <div className="h-14 px-4 flex items-center justify-between border-b border-border">
        <span
          className={cn(
            "font-display text-h3 tracking-tight text-foreground",
            collapsed && "opacity-0 pointer-events-none",
          )}
        >
          Reflow
        </span>
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "size-7 rounded-md flex items-center justify-center",
            "text-foreground-tertiary",
            "hover:bg-card-hover hover:text-foreground",
            "transition-colors duration-200 ease-considered",
          )}
        >
          <ChevronLeft
            className={cn(
              "size-4 transition-transform duration-200 ease-considered",
              collapsed && "rotate-180",
            )}
          />
        </button>
      </div>

      {/* Sections */}
      <nav className="flex-1 overflow-y-auto py-4">
        {SECTIONS.map((section) => (
          <div key={section.heading} className="px-3 mb-5">
            {!collapsed ? (
              <p className="px-2 mb-1.5 text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
                {section.heading}
              </p>
            ) : null}
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "group flex items-center gap-2.5 rounded-md px-2 h-8",
                        "text-body-sm text-foreground-secondary",
                        "transition-colors duration-200 ease-considered",
                        "hover:bg-card-hover hover:text-foreground",
                        isActive && [
                          "bg-primary-surface text-foreground",
                          "shadow-[inset_2px_0_0_hsl(var(--primary))]",
                        ],
                      )
                    }
                    end={item.to === routes.DASHBOARD_EXECUTIVE}
                  >
                    <item.icon className="size-4 shrink-0" />
                    {!collapsed ? (
                      <span className="truncate">{item.label}</span>
                    ) : null}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer wordmark line */}
      {!collapsed ? (
        <div className="px-4 py-3 border-t border-border">
          <p className="font-mono text-caption text-foreground-tertiary">
            Vellum 0.1
          </p>
        </div>
      ) : null}
    </aside>
  );
}
