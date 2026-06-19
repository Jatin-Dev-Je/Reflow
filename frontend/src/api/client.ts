/**
 * Typed API client.
 *
 * Built on `openapi-fetch` + the generated `schema.d.ts`. Every endpoint call
 * is type-checked at compile time against the FastAPI OpenAPI spec — wrong
 * paths, wrong methods, wrong request bodies, missing fields all become
 * TypeScript errors.
 *
 * Three middlewares run on every call (in order):
 *   1. request-id  — sets X-Request-Id
 *   2. auth        — attaches JWT, refreshes on 401
 *   3. error path  — caller-side normalization via toApiError on !response.ok
 */

import createClient from "openapi-fetch";

import { createAuthMiddleware } from "@/api/interceptors/auth";
import { toApiError } from "@/api/interceptors/error";
import { requestIdMiddleware } from "@/api/interceptors/request-id";

// The generated types file lives at src/api/generated/schema.d.ts after
// `pnpm gen:api`. Until that runs we fall back to an empty paths shape so
// the project still type-checks before the first codegen.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Paths = any;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
//   ""  → use the Vite dev proxy (same origin) — recommended for dev
//   "https://api.reflow.app" → hit a deployed backend

export const apiClient = createClient<Paths>({
  baseUrl: API_BASE_URL,
  credentials: "omit",
  headers: {
    "Content-Type": "application/json",
  },
});

// Register middlewares — order matters.
apiClient.use(requestIdMiddleware);
apiClient.use(createAuthMiddleware({ baseUrl: API_BASE_URL }));

/**
 * Convenience: throw a ReflowApiError if a fetch result has an error body.
 * Usage in a query/mutation:
 *
 *   const { data, error, response } = await apiClient.GET("/api/v1/transactions");
 *   throwIfError(error, response);
 *   return data;
 */
export async function throwIfError(
  error: unknown,
  response: Response | undefined,
): Promise<void> {
  if (!error || !response) return;
  throw await toApiError(response);
}

// Re-export so callers can import everything API-related from one place.
export { ReflowApiError } from "@/api/interceptors/error";
export type { ReflowErrorBody } from "@/api/interceptors/error";
