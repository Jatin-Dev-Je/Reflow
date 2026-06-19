import { useMutation } from "@tanstack/react-query";

import { toApiError } from "@/api/interceptors/error";
import { useAuthTokenStore } from "@/features/auth/store";
import type { RegisterInput, TokenPair } from "@/features/auth/types";

/**
 * Mutation: POST /api/v1/auth/register
 *
 * The backend creates the user, assigns the operator role on the demo
 * tenant, and immediately issues a TokenPair so the user is logged in.
 * 409 Conflict on duplicate email.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function registerRequest(input: RegisterInput): Promise<TokenPair> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as TokenPair;
}

export function useRegister() {
  const setTokens = useAuthTokenStore((s) => s.setTokens);

  return useMutation<TokenPair, Error, RegisterInput>({
    mutationFn: registerRequest,
    onSuccess: (tokens) => {
      setTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        expiresInMinutes: tokens.expires_in_minutes,
      });
    },
  });
}
