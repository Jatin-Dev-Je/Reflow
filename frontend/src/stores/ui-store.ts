import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/**
 * UI store — ambient app UI state that lots of components touch but isn't
 * "server state". Anything that ends up in TanStack Query should NOT live here.
 *
 * What's here:
 *   - Sidebar collapse (persisted — operators have preferences)
 *   - Command palette open (transient)
 *   - Help dialog open (transient)
 *   - Active citation drawer (the Trust View signature interaction)
 *
 * What's NOT here:
 *   - Form state (use React Hook Form)
 *   - Server data (use TanStack Query)
 *   - Theme (separate store for clarity)
 */

interface OpenCitationDrawer {
  artifactId: string;
  artifactType: "diagnosis" | "policy_decision" | "strategy" | "risk";
  citationIndex: number;
}

interface UiState {
  // Sidebar
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;

  // Command palette
  commandPaletteOpen: boolean;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  toggleCommandPalette: () => void;

  // Help dialog
  helpOpen: boolean;
  openHelp: () => void;
  closeHelp: () => void;

  // Citation drawer (the Vellum signature)
  citationDrawer: OpenCitationDrawer | null;
  openCitation: (drawer: OpenCitationDrawer) => void;
  closeCitation: () => void;
}

const STORAGE_KEY = "reflow.ui";

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      // Sidebar — persisted
      sidebarCollapsed: false,
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

      // Command palette — transient
      commandPaletteOpen: false,
      openCommandPalette: () => set({ commandPaletteOpen: true }),
      closeCommandPalette: () => set({ commandPaletteOpen: false }),
      toggleCommandPalette: () =>
        set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),

      // Help — transient
      helpOpen: false,
      openHelp: () => set({ helpOpen: true }),
      closeHelp: () => set({ helpOpen: false }),

      // Citation drawer — transient
      citationDrawer: null,
      openCitation: (drawer) => set({ citationDrawer: drawer }),
      closeCitation: () => set({ citationDrawer: null }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      // Only persist sidebar state. The rest is session-local.
      partialize: (state) => ({ sidebarCollapsed: state.sidebarCollapsed }),
    },
  ),
);
