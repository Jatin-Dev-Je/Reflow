import type { Middleware } from "openapi-fetch";

/**
 * Attach a fresh X-Request-Id header to every outgoing API call.
 *
 * The backend's RequestIdMiddleware honours an incoming X-Request-Id (rather
 * than generating one) and binds it to the structlog context for the whole
 * request. That means a single ID traces a UI action through:
 *
 *   browser console  ─►  FastAPI access log  ─►  domain events  ─►  audit
 *
 * Use a UUID v4-like ID; crypto.randomUUID is universal in modern browsers.
 */

function newRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Fallback (very old browsers, test environments without crypto)
  return `req_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

export const requestIdMiddleware: Middleware = {
  onRequest({ request }) {
    if (!request.headers.has("X-Request-Id")) {
      request.headers.set("X-Request-Id", newRequestId());
    }
    return request;
  },
};
