/**
 * Identifier display helpers — UUIDs, hashes, opaque keys.
 *
 * Backend IDs are full UUIDs / hex digests; displaying them raw is hostile to
 * the eye. These helpers truncate while keeping enough characters that you
 * can still recognise + copy them.
 */

/**
 * Shorten a UUID to "abcd…wxyz" (first 4 + last 4 by default).
 *
 *   shortenId("3f50b8c6-1e07-4d4f-b2ef-1c9a7e9e4f12")  →  "3f50…4f12"
 */
export function shortenId(id: string | null | undefined, headLen = 4, tailLen = 4): string {
  if (!id) return "—";
  const flat = id.replace(/-/g, "");
  if (flat.length <= headLen + tailLen) return id;
  return `${flat.slice(0, headLen)}…${flat.slice(-tailLen)}`;
}

/**
 * Shorten a long hex hash (sha256, event_hash, merkle_root, signature).
 * Defaults to 8 head + 6 tail because hashes need a bit more entropy on screen.
 *
 *   shortenHash("a1b2c3d4e5f60718...c0d1e2")  →  "a1b2c3d4…c0d1e2"
 */
export function shortenHash(hash: string | null | undefined, headLen = 8, tailLen = 6): string {
  if (!hash) return "—";
  if (hash.length <= headLen + tailLen) return hash;
  return `${hash.slice(0, headLen)}…${hash.slice(-tailLen)}`;
}

/**
 * Type guard: looks like a UUID v4-ish string.
 * Strict enough to avoid false positives in user input; loose enough to
 * accept lowercase and uppercase mixes from different services.
 */
const UUID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}

/**
 * Stream identifier display.
 * Backend uses streams like "transaction-3f50b8c6-..." and "recovery-...".
 * The leading type plus a shortened UUID reads naturally.
 *
 *   formatStreamId("transaction-3f50b8c6-1e07-4d4f-b2ef-1c9a7e9e4f12")
 *     → "transaction · 3f50…4f12"
 */
export function formatStreamId(streamId: string): string {
  const dash = streamId.indexOf("-");
  if (dash < 0) return streamId;
  const type = streamId.slice(0, dash);
  const rest = streamId.slice(dash + 1);
  return `${type} · ${shortenId(rest)}`;
}
