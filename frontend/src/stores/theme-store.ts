import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/**
 * Theme store — Vellum's light/dark switch.
 *
 * Three values:
 *   "light"  → force light, ignore system
 *   "dark"   → force dark, ignore system
 *   "system" → follow prefers-color-scheme, react to OS changes
 *
 * The "resolved" theme is whichever of light/dark is actually applied right
 * now. Components that care about the rendered colour (e.g. recharts series
 * colours) read `resolved`. Components that render the picker UI read `mode`.
 *
 * The DOM mutation (toggling `.dark` on <html>) happens here so the rest of
 * the app doesn't have to.
 */

export type ThemeMode = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

interface ThemeState {
  mode: ThemeMode;
  resolved: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
  /** Call once at app boot — wires the system-pref listener and applies the class. */
  initialize: () => () => void;
}

const STORAGE_KEY = "reflow.theme";

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || !window.matchMedia) return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolve(mode: ThemeMode): ResolvedTheme {
  return mode === "system" ? getSystemTheme() : mode;
}

function applyToDocument(theme: ResolvedTheme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.remove("light", "dark");
  root.classList.add(theme);
  root.style.colorScheme = theme;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: "system",
      resolved: getSystemTheme(),

      setMode: (mode: ThemeMode) => {
        const resolved = resolve(mode);
        applyToDocument(resolved);
        set({ mode, resolved });
      },

      initialize: () => {
        applyToDocument(get().resolved);

        if (typeof window === "undefined" || !window.matchMedia) {
          return () => {
            /* no-op */
          };
        }
        const mql = window.matchMedia("(prefers-color-scheme: dark)");
        const onChange = (event: MediaQueryListEvent): void => {
          if (get().mode !== "system") return;
          const next: ResolvedTheme = event.matches ? "dark" : "light";
          applyToDocument(next);
          set({ resolved: next });
        };
        mql.addEventListener("change", onChange);
        return () => {
          mql.removeEventListener("change", onChange);
        };
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ mode: state.mode }),
      onRehydrateStorage: () => (state) => {
        // After rehydration, recompute resolved from the rehydrated mode.
        if (state) {
          const resolved = resolve(state.mode);
          state.resolved = resolved;
          applyToDocument(resolved);
        }
      },
    },
  ),
);
