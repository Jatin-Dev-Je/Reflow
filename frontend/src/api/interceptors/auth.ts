import type { Middleware } from "openapi-fetch";

import { getAuthToken, getRefreshToken, useAuthTokenStore } from "@/features/auth/store";
import { useTenantStore } from "@/stores/tenant-store";

/**
 * Auth middleware — attaches the access token, refreshes on 401, retries.
 *
 * Behaviour:
 *   1. onRequest: attach Authorization: Bearer <access>
 *   2. onResponse: if status 401 AND this isn't the refresh endpoint AND we
 *      have a refresh token, call /auth/refresh exactly once for this
 *      request (singleflight). On success, retry the original request once.
 *   3. On refresh failure: clear tokens, clear tenant, return 401 to caller.
 *      The router's protected guard observes the cleared store and bounces
 *      to /login.
 *
 * Auth-exempt paths: /auth/login, /auth/register, /auth/refresh, /healthz,
 * /readyz, /system/info. These never get a token attached and aren't
 * retried on 401.
 */

const AUTH_EXEMPT = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/refresh",
  "/api/v1/auth/forgot-password",
  "/api/v1/auth/reset-password",
  "/healthz",
  "/readyz",
  "/api/v1/system/info",
]);

let inflightRefresh: Promise<string | null> | null = null;

async function refreshAccessToken(refreshBaseUrl: string): Promise<string | null> {
  if (inflightRefresh) return inflightRefresh;
  const refresh = getRefreshToken();
  if (!refresh) return null;

  inflightRefresh = (async () => {
    try {
      const res = await fetch(`${refreshBaseUrl}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) return null;
      const body = (await res.json()) as {
        access_token: string;
        refresh_token: string;
        expires_in_minutes: number;
      };
      useAuthTokenStore.getState().setTokens({
        accessToken: body.access_token,
        refreshToken: body.refresh_token,
        expiresInMinutes: body.expires_in_minutes,
      });
      return body.access_token;
    } catch {
      return null;
    } finally {
      inflightRefresh = null;
    }
  })();

  return inflightRefresh;
}

function pathOf(url: URL | string): string {
  try {
    return new URL(url, "http://placeholder").pathname;
  } catch {
    return String(url);
  }
}

export function createAuthMiddleware({ baseUrl }: { baseUrl: string }): Middleware {
  return {
    onRequest({ request }) {
      const path = pathOf(request.url);
      if (AUTH_EXEMPT.has(path)) return request;

      const token = getAuthToken();
      if (token) {
        request.headers.set("Authorization", `Bearer ${token}`);
      }
      return request;
    },

    async onResponse({ request, response }) {
      if (response.status !== 401) return response;

      const path = pathOf(request.url);
      if (AUTH_EXEMPT.has(path)) return response;

      // Avoid infinite retry loops — we stamp a flag on the request when we
      // retry, and skip refresh the second time around.
      if (request.headers.get("X-Auth-Retried") === "1") {
        useAuthTokenStore.getState().clearTokens();
        useTenantStore.getState().clearSession();
        return response;
      }

      const newAccess = await refreshAccessToken(baseUrl);
      if (!newAccess) {
        useAuthTokenStore.getState().clearTokens();
        useTenantStore.getState().clearSession();
        return response;
      }

      // Replay the original request with the new token.
      const retried = new Request(request, {
        headers: new Headers(request.headers),
      });
      retried.headers.set("Authorization", `Bearer ${newAccess}`);
      retried.headers.set("X-Auth-Retried", "1");
      return fetch(retried);
    },
  };
}
