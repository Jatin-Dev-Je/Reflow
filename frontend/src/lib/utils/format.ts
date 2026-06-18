/**
 * Display formatters for money, percentages, dates, durations, and large numbers.
 *
 * Conventions:
 * - Money values arrive from the backend in integer cents.
 * - Percentages arrive in [0, 1]; we render as 0–100 with one decimal.
 * - All formatters are locale-aware via Intl.* with a configurable fallback.
 */

import { formatDistanceToNowStrict, parseISO } from "date-fns";

const DEFAULT_LOCALE = "en-US";

// ─────────────────────────────────────────────────────────────────────────────
// Money
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Format integer cents as a currency string.
 *
 *   formatMoney(4999, "USD")   → "$49.99"
 *   formatMoney(1000000, "EUR") → "€10,000.00"
 *   formatMoney(0, "USD")      → "$0.00"
 */
export function formatMoney(
  amountCents: number,
  currency = "USD",
  locale = DEFAULT_LOCALE,
): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amountCents / 100);
}

/**
 * Compact money for KPI cards. Drops decimals over $1,000 and switches to
 * compact notation over $1M.
 *
 *   formatMoneyCompact(4999, "USD")     → "$49.99"
 *   formatMoneyCompact(125000, "USD")   → "$1,250"
 *   formatMoneyCompact(125000000, "USD") → "$1.25M"
 */
export function formatMoneyCompact(
  amountCents: number,
  currency = "USD",
  locale = DEFAULT_LOCALE,
): string {
  const amount = amountCents / 100;
  if (Math.abs(amount) >= 1_000_000) {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 2,
    }).format(amount);
  }
  if (Math.abs(amount) >= 1_000) {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  }
  return formatMoney(amountCents, currency, locale);
}

// ─────────────────────────────────────────────────────────────────────────────
// Percentages
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Format a [0, 1] fraction as a percent.
 *
 *   formatPercent(0.875)        → "87.5%"
 *   formatPercent(0.034, 0)     → "3%"
 *   formatPercent(1)            → "100.0%"
 */
export function formatPercent(value: number, fractionDigits = 1): string {
  return `${(value * 100).toFixed(fractionDigits)}%`;
}

/**
 * Percentage-point delta (e.g. success_lift_pp from the dashboard).
 *
 *   formatPp(0.09)   → "+9.0 pp"
 *   formatPp(-0.03)  → "-3.0 pp"
 */
export function formatPp(value: number, fractionDigits = 1): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(fractionDigits)} pp`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Numbers
// ─────────────────────────────────────────────────────────────────────────────

/** Thousands-separated integer.  formatCount(123456) → "123,456" */
export function formatCount(value: number, locale = DEFAULT_LOCALE): string {
  return new Intl.NumberFormat(locale).format(value);
}

/** Compact count.  formatCountCompact(1500) → "1.5K", 1_250_000 → "1.25M" */
export function formatCountCompact(value: number, locale = DEFAULT_LOCALE): string {
  return new Intl.NumberFormat(locale, {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

// ─────────────────────────────────────────────────────────────────────────────
// Dates + durations
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Relative time from now: "5 minutes ago", "in 2 hours".
 * Accepts ISO string or Date.
 */
export function formatRelative(iso: string | Date): string {
  const date = typeof iso === "string" ? parseISO(iso) : iso;
  return formatDistanceToNowStrict(date, { addSuffix: true });
}

/** Absolute timestamp, e.g. "Jun 18, 2026, 10:24 AM" */
export function formatTimestamp(iso: string | Date, locale = DEFAULT_LOCALE): string {
  const date = typeof iso === "string" ? parseISO(iso) : iso;
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

/**
 * Latency in ms → human-friendly.
 *   formatLatency(82)     → "82 ms"
 *   formatLatency(1240)   → "1.24 s"
 *   formatLatency(120000) → "2 min"
 */
export function formatLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)} min`;
  return `${(ms / 3_600_000).toFixed(1)} h`;
}
