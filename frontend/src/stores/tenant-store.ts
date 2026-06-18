import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/**
 * Tenant + current-user store.
 *
 * Populated after login by `/auth/me`. The X-Tenant-Id header sent on every
 * API call comes from here, so the source of truth for "who am I and where am
 * I" lives in one place.
 *
 * The user / tenant IDs persist so a hard refresh doesn't drop the user back
 * to the login screen before the token can be checked. We re-validate them
 * on app boot — if /auth/me fails we clear the store.
 */

export type Role = "owner" | "admin" | "operator" | "viewer" | "approver";

interface CurrentUser {
  id: string;
  email: string;
  displayName: string | null;
  isSuperuser: boolean;
}

interface CurrentTenant {
  id: string;
  name?: string;
  slug?: string;
}

interface TenantState {
  user: CurrentUser | null;
  tenant: CurrentTenant | null;
  roles: Role[];

  setSession: (input: { user: CurrentUser; tenant: CurrentTenant; roles: Role[] }) => void;
  clearSession: () => void;

  hasRole: (role: Role) => boolean;
  hasAnyRole: (roles: readonly Role[]) => boolean;
}

const STORAGE_KEY = "reflow.tenant";

export const useTenantStore = create<TenantState>()(
  persist(
    (set, get) => ({
      user: null,
      tenant: null,
      roles: [],

      setSession: ({ user, tenant, roles }) => set({ user, tenant, roles }),

      clearSession: () => set({ user: null, tenant: null, roles: [] }),

      hasRole: (role) => get().roles.includes(role),

      hasAnyRole: (roles) => {
        const mine = get().roles;
        return roles.some((r) => mine.includes(r));
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        tenant: state.tenant,
        roles: state.roles,
      }),
    },
  ),
);
