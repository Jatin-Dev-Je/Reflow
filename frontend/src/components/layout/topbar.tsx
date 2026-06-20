import { Bell, Moon, Search, Sun, User } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useThemeStore } from "@/stores/theme-store";
import { useUiStore } from "@/stores/ui-store";
import { useTenantStore } from "@/stores/tenant-store";
import { cn } from "@/lib/utils/cn";

/**
 * Vellum top bar — sits above main content in every authenticated screen.
 *
 *   [ page title ]  [ search ]  [ theme ]  [ notifications ]  [ user ]
 */

interface TopbarProps {
  /** Rendered on the left — usually breadcrumbs or a page title. */
  title?: string;
}

export function Topbar({ title }: TopbarProps): JSX.Element {
  const openCommand = useUiStore((s) => s.openCommandPalette);
  const resolvedTheme = useThemeStore((s) => s.resolved);
  const setMode = useThemeStore((s) => s.setMode);
  const user = useTenantStore((s) => s.user);

  return (
    <header
      className={cn(
        "h-14 shrink-0 px-6 flex items-center gap-3",
        "bg-page border-b border-border",
      )}
    >
      <div className="flex-1 min-w-0">
        {title ? (
          <h1 className="font-display text-h3 truncate text-foreground">{title}</h1>
        ) : null}
      </div>

      <button
        type="button"
        onClick={openCommand}
        className={cn(
          "hidden md:flex items-center gap-2 h-9 w-64 px-3 rounded-md",
          "bg-card border border-border text-foreground-tertiary",
          "transition-colors duration-200 ease-considered",
          "hover:bg-card-hover hover:border-border-strong",
        )}
        aria-label="Open command palette"
      >
        <Search className="size-3.5 shrink-0" />
        <span className="flex-1 text-left text-body-sm truncate">Search anything…</span>
        <kbd className="font-mono text-caption px-1.5 py-0.5 rounded bg-inset border border-border">
          ⌘K
        </kbd>
      </button>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Toggle theme"
        onClick={() => setMode(resolvedTheme === "dark" ? "light" : "dark")}
      >
        {resolvedTheme === "dark" ? <Sun /> : <Moon />}
      </Button>

      <Button type="button" variant="ghost" size="icon" aria-label="Notifications">
        <Bell />
      </Button>

      <button
        type="button"
        className={cn(
          "flex items-center gap-2 h-9 pl-1.5 pr-2.5 rounded-full",
          "bg-card border border-border",
          "transition-colors duration-200 ease-considered",
          "hover:bg-card-hover hover:border-border-strong",
        )}
        aria-label="Account menu"
      >
        <span className="size-6 rounded-full bg-primary-surface text-primary grid place-items-center">
          <User className="size-3.5" />
        </span>
        <span className="text-body-sm text-foreground truncate max-w-[120px]">
          {user?.display_name ?? user?.email ?? "Account"}
        </span>
      </button>
    </header>
  );
}
