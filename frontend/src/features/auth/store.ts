import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/**
 * Auth token store.
 *
 * Holds the JWT access + refresh pair returned by /auth/login. Separate from
 * the tenant store so the API client can reach for the token without
 * importing user/role concepts.
 *
 * NOTE on storage: localStorage is the industry-standard B2B SaaS pattern
 * (Stripe Dashboard, Linear, etc.). httpOnly cookies are technically safer
 * against XSS but require a BFF; we make the trade-off documented and
 * deliberate. Mitigations elsewhere: CSP headers, sanitised LLM outputs,
 * no `dangerouslySetInnerHTML` on untrusted input.
 */

interface AuthTokenState {
  accessToken: string | null;
  refreshToken: string | null;
  /** Epoch millis when the access token is expected to expire. */
  accessExpiresAt: number | null;

  setTokens: (tokens: {
    accessToken: string;
    refreshToken: string;
    expiresInMinutes: number;
  }) => void;
  clearTokens: () => void;

  /** True if we have a token and it isn't expired (with 30 s margin). */
  hasValidAccessToken: () => boolean;
}

const STORAGE_KEY = "reflow.auth";

export const useAuthTokenStore = create<AuthTokenState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      accessExpiresAt: null,

      setTokens: ({ accessToken, refreshToken, expiresInMinutes }) =>
        set({
          accessToken,
          refreshToken,
          accessExpiresAt: Date.now() + expiresInMinutes * 60_000,
        }),

      clearTokens: () =>
        set({ accessToken: null, refreshToken: null, accessExpiresAt: null }),

      hasValidAccessToken: () => {
        const { accessToken, accessExpiresAt } = get();
        if (!accessToken || !accessExpiresAt) return false;
        return Date.now() < accessExpiresAt - 30_000;
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
    },
  ),
);

/**
 * Convenience accessor for non-React code (interceptors). Subscribes to the
 * latest state without going through useStore (which would need a hook
 * context).
 */
export const getAuthToken = (): string | null =>
  useAuthTokenStore.getState().accessToken;

export const getRefreshToken = (): string | null =>
  useAuthTokenStore.getState().refreshToken;
