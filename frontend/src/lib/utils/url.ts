/**
 * URL helpers for query-string building + reading.
 *
 * We do this by hand instead of pulling `qs` because:
 * - URLSearchParams covers our 99% case (flat objects with primitives)
 * - We never serialise nested objects to the URL — they go in the body
 * - Saves a dependency
 */

export type QueryValue = string | number | boolean | null | undefined;
export type QueryRecord = Record<string, QueryValue | readonly QueryValue[]>;

/**
 * Build a query string from a flat record. Empty/null/undefined values are
 * dropped (so callers can build a single object with optional filters).
 *
 *   buildQuery({ status: "failed", limit: 50 }) → "?status=failed&limit=50"
 *   buildQuery({ status: undefined })           → ""
 *   buildQuery({ ids: ["a", "b"] })             → "?ids=a&ids=b"
 */
export function buildQuery(params: QueryRecord): string {
  const search = new URLSearchParams();

  for (const [key, raw] of Object.entries(params)) {
    if (raw === null || raw === undefined || raw === "") continue;

    if (Array.isArray(raw)) {
      for (const item of raw) {
        if (item === null || item === undefined || item === "") continue;
        search.append(key, String(item));
      }
    } else {
      search.append(key, String(raw));
    }
  }

  const qs = search.toString();
  return qs.length > 0 ? `?${qs}` : "";
}

/**
 * Parse a URLSearchParams into a typed record. Useful for reading filters
 * out of a URL in route loaders.
 *
 *   parseQuery(new URLSearchParams("?status=failed&limit=50"))
 *     → { status: "failed", limit: "50" }
 *
 * Coercion to numbers / booleans / arrays is the caller's responsibility
 * (do it with Zod in the page that reads it).
 */
export function parseQuery(search: URLSearchParams | string): Record<string, string> {
  const params =
    typeof search === "string"
      ? new URLSearchParams(search.startsWith("?") ? search.slice(1) : search)
      : search;
  const out: Record<string, string> = {};
  for (const [key, value] of params.entries()) {
    out[key] = value;
  }
  return out;
}

/**
 * Append params to an existing path, preserving the existing query string.
 *
 *   withQuery("/transactions?limit=50", { status: "failed" })
 *     → "/transactions?limit=50&status=failed"
 */
export function withQuery(path: string, params: QueryRecord): string {
  const [base, existingQs = ""] = path.split("?", 2);
  const merged = new URLSearchParams(existingQs);

  for (const [key, raw] of Object.entries(params)) {
    if (raw === null || raw === undefined || raw === "") {
      merged.delete(key);
      continue;
    }
    if (Array.isArray(raw)) {
      merged.delete(key);
      for (const item of raw) {
        if (item === null || item === undefined || item === "") continue;
        merged.append(key, String(item));
      }
    } else {
      merged.set(key, String(raw));
    }
  }

  const qs = merged.toString();
  return qs.length > 0 ? `${base}?${qs}` : base ?? "";
}
