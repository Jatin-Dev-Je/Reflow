import { useMutation } from "@tanstack/react-query";

import { toApiError } from "@/api/interceptors/error";
import { useAuthTokenStore } from "@/features/auth/store";
import type { LoginInput, TokenPair } from "@/features/auth/types";

/**
 * Mutation: POST /api/v1/auth/login
 *
 * Success path:
 *   1. Backend returns a TokenPair.
 *   2. We persist it via the auth token store.
 *   3. Caller chains onSuccess to fetch /auth/me + navigate.
 *
 * Failure path: backend returns 401 with detail "Invalid credentials"
 * (same shape for missing-user and wrong-password — email enumeration
 * defence). We surface as a `ReflowApiError`.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function loginRequest(input: LoginInput): Promise<TokenPair> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as TokenPair;
}

export function useLogin() {
  const setTokens = useAuthTokenStore((s) => s.setTokens);

  return useMutation<TokenPair, Error, LoginInput>({
    mutationFn: loginRequest,
    onSuccess: (tokens) => {
      setTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        expiresInMinutes: tokens.expires_in_minutes,
      });
    },
  });
}
