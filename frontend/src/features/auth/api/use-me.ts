import { useQuery } from "@tanstack/react-query";

import { toApiError } from "@/api/interceptors/error";
import { useAuthTokenStore, getAuthToken } from "@/features/auth/store";
import type { AuthMeResponse, Role } from "@/features/auth/types";
import { useTenantStore } from "@/stores/tenant-store";

/**
 * Query: GET /api/v1/auth/me
 *
 * Runs after a token is present. On success, hydrates the tenant store
 * (user + tenant_id + roles). On 401, the auth interceptor clears tokens
 * and bounces; useMe re-runs and returns the error.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function meRequest(): Promise<AuthMeResponse> {
  const token = getAuthToken();
  if (!token) {
    throw new Error("No access token");
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as AuthMeResponse;
}

export function useMe(options: { enabled?: boolean } = {}) {
  const hasToken = useAuthTokenStore((s) => Boolean(s.accessToken));
  const setSession = useTenantStore((s) => s.setSession);

  return useQuery<AuthMeResponse, Error>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const data = await meRequest();
      setSession({
        user: {
          id: data.user.id,
          email: data.user.email,
          displayName: data.user.display_name,
          isSuperuser: data.user.is_superuser,
        },
        tenant: { id: data.tenant_id },
        roles: data.roles as Role[],
      });
      return data;
    },
    enabled: (options.enabled ?? true) && hasToken,
    staleTime: 5 * 60_000,
    retry: false,
  });
}
