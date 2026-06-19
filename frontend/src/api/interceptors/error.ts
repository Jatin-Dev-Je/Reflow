/**
 * Error normalization for backend ReflowError responses.
 *
 * The backend's install_error_handlers maps every typed exception to a JSON
 * body of the shape:
 *
 *   { "error": { "error_code": "...", "message": "...", "context": {...} } }
 *
 * with the right HTTP status. This module converts a failed openapi-fetch
 * call into a typed `ReflowApiError` the rest of the app can switch on,
 * instead of every callsite re-parsing JSON and checking for shapes.
 */

export interface ReflowErrorBody {
  error_code: string;
  message: string;
  context?: Record<string, unknown>;
}

/**
 * Typed error thrown by query/mutation hooks when the backend returns a
 * structured ReflowError body. `code` mirrors the backend's `error_code`
 * field so callers can `if (err.code === 'auth.invalid_token') ...`.
 */
export class ReflowApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly context: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(args: {
    code: string;
    message: string;
    status: number;
    context?: Record<string, unknown>;
    requestId?: string | null;
  }) {
    super(args.message);
    this.name = "ReflowApiError";
    this.code = args.code;
    this.status = args.status;
    this.context = args.context ?? {};
    this.requestId = args.requestId ?? null;
  }

  is(code: string): boolean {
    return this.code === code;
  }
}

/** Best-effort: pull a ReflowError shape out of an unknown JSON body. */
function extractError(body: unknown): ReflowErrorBody | null {
  if (
    body !== null &&
    typeof body === "object" &&
    "error" in body &&
    typeof (body as { error: unknown }).error === "object" &&
    (body as { error: unknown }).error !== null
  ) {
    const inner = (body as { error: Record<string, unknown> }).error;
    if (typeof inner.error_code === "string" && typeof inner.message === "string") {
      return {
        error_code: inner.error_code,
        message: inner.message,
        context: typeof inner.context === "object" && inner.context !== null
          ? (inner.context as Record<string, unknown>)
          : undefined,
      };
    }
  }
  return null;
}

/**
 * Convert a failed openapi-fetch response into a `ReflowApiError`. When the
 * body doesn't match our error shape we synthesize a generic one so the
 * caller never has to handle "unknown shape" separately.
 */
export async function toApiError(response: Response): Promise<ReflowApiError> {
  const requestId = response.headers.get("X-Request-Id");
  let bodyText: string | null = null;
  let bodyJson: unknown = null;
  try {
    bodyText = await response.clone().text();
    if (bodyText) {
      bodyJson = JSON.parse(bodyText);
    }
  } catch {
    /* swallow — body might not be JSON */
  }

  const extracted = extractError(bodyJson);
  if (extracted) {
    return new ReflowApiError({
      code: extracted.error_code,
      message: extracted.message,
      status: response.status,
      context: extracted.context,
      requestId,
    });
  }

  // FastAPI's HTTPException has its own shape: { detail: "..." }
  if (
    bodyJson !== null &&
    typeof bodyJson === "object" &&
    "detail" in bodyJson &&
    typeof (bodyJson as { detail: unknown }).detail === "string"
  ) {
    return new ReflowApiError({
      code: `http.${response.status}`,
      message: (bodyJson as { detail: string }).detail,
      status: response.status,
      requestId,
    });
  }

  return new ReflowApiError({
    code: `http.${response.status}`,
    message: response.statusText || "Request failed",
    status: response.status,
    requestId,
  });
}
