/**
 * Auth feature types.
 *
 * These mirror the backend's request/response shapes for
 *   POST /api/v1/auth/login
 *   POST /api/v1/auth/register
 *   POST /api/v1/auth/refresh
 *   GET  /api/v1/auth/me
 *
 * Once `pnpm gen:api` runs, these can be re-derived from the generated
 * schema. Hand-defining them here means the feature can compile and ship
 * before the codegen runs in CI.
 */

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  display_name?: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in_minutes: number;
}

export interface AuthMeUser {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface AuthMeResponse {
  user: AuthMeUser;
  tenant_id: string;
  roles: string[];
}
