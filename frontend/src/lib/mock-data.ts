/**
 * Demo data so frontend screens render before the backend is wired.
 * Replace with real useQuery hooks as endpoints come online.
 */

export const mockExecutive = {
  windowDays: 7,
  totalTransactions: 12_847,
  totalAmountCents: 4_206_300_00,
  baselineSucceeded: 10_535,
  reflowSucceeded: 11_419,
  baselineSuccessRate: 0.82,
  reflowSuccessRate: 0.889,
  successLiftPp: 0.069,
  recoveriesAttempted: 2_312,
  recoveriesSucceeded: 884,
  recoveryRate: 0.382,
  revenueRecoveredCents: 198_400_00,
  duplicateCharges: 0,
  policyViolations: 0,
};

export const mockOperations = {
  asOf: new Date().toISOString(),
  pendingApprovals: 7,
  recoveriesInFlight: 23,
  failuresLastHour: 41,
  recoveriesLastHour: 18,
  deadLetterCount: 0,
  activeKillSwitches: [] as string[],
};

export const mockTrust = {
  asOf: new Date().toISOString(),
  duplicateCharges: 0,
  policyDenialsLast24h: 12,
  policyApprovalsRequiredLast24h: 3,
  diagnosesWithEvidence: 1_847,
  diagnosesTotal: 1_847,
  evidenceCoverage: 1.0,
  auditChainAnchors: 142,
  lastAnchorAt: new Date(Date.now() - 5 * 60_000).toISOString(),
};

export interface MockTransaction {
  id: string;
  externalId: string;
  amountCents: number;
  currency: string;
  status: "failed" | "recovering" | "recovered" | "abandoned" | "succeeded";
  gatewayId: string;
  issuerId: string;
  declineCode: string | null;
  cardBrand: string;
  cardLast4: string;
  createdAt: string;
}

const STATUSES: MockTransaction["status"][] = [
  "failed",
  "recovering",
  "recovered",
  "failed",
  "abandoned",
  "succeeded",
];
const GATEWAYS = ["stripe", "adyen", "braintree", "checkout"];
const ISSUERS = ["VISA_TEST", "MC_GENERIC", "AMEX_TEST", "VISA_DEBIT", "DISCOVER_GENERIC"];
const DECLINES = [
  "FUNDS_INSUFFICIENT",
  "ISSUER_DO_NOT_HONOR",
  "AUTH_3DS_REQUIRED",
  "GATEWAY_TIMEOUT",
  "FRAUD_SUSPECTED",
  "CARD_EXPIRED",
];
const BRANDS = ["Visa", "Mastercard", "Amex"];

function pad(value: number, len: number): string {
  return value.toString().padStart(len, "0");
}

export const mockTransactions: MockTransaction[] = Array.from({ length: 32 }, (_, i) => {
  const status = STATUSES[i % STATUSES.length] ?? "failed";
  const createdAt = new Date(Date.now() - i * 12 * 60_000).toISOString();
  return {
    id: `3f50b8c6-1e07-4d4f-b2ef-1c9a7e9e${pad(0x4f12 - i, 4)}`,
    externalId: `tx_${pad(10247 - i, 6)}`,
    amountCents: 4999 + i * 731,
    currency: "USD",
    status,
    gatewayId: GATEWAYS[i % GATEWAYS.length] ?? "stripe",
    issuerId: ISSUERS[i % ISSUERS.length] ?? "VISA_TEST",
    declineCode: status === "succeeded" ? null : DECLINES[i % DECLINES.length] ?? null,
    cardBrand: BRANDS[i % BRANDS.length] ?? "Visa",
    cardLast4: pad(4242 + i, 4),
    createdAt,
  };
});

export interface MockTimelineEvent {
  occurredAt: string;
  eventType: string;
  summary: string;
  payload: Record<string, unknown>;
  eventHash: string;
  citations?: Array<{
    index: number;
    observation: string;
    sourceKind: string;
  }>;
}

export const mockTimeline: MockTimelineEvent[] = [
  {
    occurredAt: new Date(Date.now() - 6 * 60_000).toISOString(),
    eventType: "TransactionCreated",
    summary: "Transaction created for 49.99 USD",
    payload: {
      external_id: "tx_010247",
      amount_cents: 4999,
      currency: "USD",
      card: { bin: "424242", last4: "4242", brand: "visa" },
      gateway_provider: "stripe",
    },
    eventHash:
      "a1b2c3d4e5f6071829304a5b6c7d8e9f0a1b2c3d4e5f6071829304a5b6c7d8e9",
  },
  {
    occurredAt: new Date(Date.now() - 5 * 60_000).toISOString(),
    eventType: "AttemptRecorded",
    summary: "Charge attempt #1 — soft_decline",
    payload: {
      attempt_number: 1,
      gateway_provider: "stripe",
      outcome: "soft_decline",
      decline: {
        code_normalized: "FUNDS_INSUFFICIENT",
        category: "funds",
        message: "Insufficient funds.",
      },
      latency_ms: 312,
    },
    eventHash:
      "b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1",
  },
  {
    occurredAt: new Date(Date.now() - 5 * 60_000 + 200).toISOString(),
    eventType: "PaymentFailed",
    summary: "Payment failed: FUNDS_INSUFFICIENT",
    payload: {
      triggering_attempt_id: "a1",
      decline: { code_normalized: "FUNDS_INSUFFICIENT", category: "funds" },
    },
    eventHash:
      "c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2",
  },
  {
    occurredAt: new Date(Date.now() - 4 * 60_000).toISOString(),
    eventType: "DiagnosisGenerated",
    summary: "Diagnosed: insufficient_funds (confidence 0.84)",
    payload: {
      root_cause_category: "insufficient_funds",
      is_recoverable: true,
      confidence: 0.84,
    },
    eventHash:
      "d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3",
    citations: [
      {
        index: 1,
        observation: "Decline code FUNDS_INSUFFICIENT in category funds",
        sourceKind: "rule_match",
      },
      {
        index: 2,
        observation: "issuer_recent_success_rate = 0.91",
        sourceKind: "issuer_health",
      },
    ],
  },
  {
    occurredAt: new Date(Date.now() - 3 * 60_000).toISOString(),
    eventType: "StrategyProposed",
    summary: "Strategy: payment_link_nudge (p=0.55)",
    payload: {
      action_type: "payment_link_nudge",
      expected_recovery_probability: 0.55,
    },
    eventHash:
      "e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
    citations: [
      {
        index: 1,
        observation: "Pattern memory recovery rate for payment_link_nudge = 0.55",
        sourceKind: "pattern_match",
      },
    ],
  },
  {
    occurredAt: new Date(Date.now() - 2 * 60_000).toISOString(),
    eventType: "RiskAssessed",
    summary: "Risk: low — dup p=0.02",
    payload: {
      overall_risk_level: "low",
      duplicate_charge_probability: 0.02,
    },
    eventHash:
      "f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5",
  },
  {
    occurredAt: new Date(Date.now() - 1 * 60_000).toISOString(),
    eventType: "PolicyDecided",
    summary: "Policy: allow",
    payload: {
      outcome: "allow",
      matched_rule_id: null,
      reason: "No restrictive rule matched.",
    },
    eventHash:
      "0718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f6",
  },
];
