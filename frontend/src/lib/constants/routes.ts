/**
 * Single source of truth for every URL the app knows about.
 *
 * Pattern:
 *   - Static paths are exported as string constants in SCREAMING_SNAKE.
 *   - Parameterised paths are exported as builder functions taking typed args.
 *
 * Why centralise: refactoring a URL becomes one find-and-replace, links never
 * drift, and the router can import them without duplication.
 */

// ── Public ───────────────────────────────────────────────────────────────────
export const HOME = "/";
export const PRICING = "/pricing";
export const SECURITY = "/security";
export const CHANGELOG = "/changelog";

// ── Auth ─────────────────────────────────────────────────────────────────────
export const LOGIN = "/login";
export const REGISTER = "/register";
export const FORGOT_PASSWORD = "/forgot-password";
export const RESET_PASSWORD = "/reset-password";
export const VERIFY_EMAIL = "/verify-email";

// ── Onboarding ───────────────────────────────────────────────────────────────
export const ONBOARDING_WELCOME = "/onboarding/welcome";
export const ONBOARDING_ORG = "/onboarding/organization";
export const ONBOARDING_DONE = "/onboarding/done";

// ── App shell ────────────────────────────────────────────────────────────────
const APP = "/app";

// Dashboards
export const DASHBOARD_EXECUTIVE = `${APP}/dashboard/executive`;
export const DASHBOARD_OPERATIONS = `${APP}/dashboard/operations`;
export const DASHBOARD_TRUST = `${APP}/dashboard/trust`;

// Transactions
export const TRANSACTIONS = `${APP}/transactions`;
export const transaction = (id: string): string => `${APP}/transactions/${id}`;
export const transactionTimeline = (id: string): string =>
  `${APP}/transactions/${id}/timeline`;

// Recoveries
export const RECOVERIES = `${APP}/recoveries`;
export const recovery = (id: string): string => `${APP}/recoveries/${id}`;

// Agent artifacts
export const DIAGNOSES = `${APP}/diagnoses`;
export const diagnosis = (id: string): string => `${APP}/diagnoses/${id}`;
export const STRATEGIES = `${APP}/strategies`;
export const strategy = (id: string): string => `${APP}/strategies/${id}`;
export const riskAssessment = (id: string): string => `${APP}/risk-assessments/${id}`;

// Approvals
export const APPROVALS = `${APP}/approvals`;
export const approval = (id: string): string => `${APP}/approvals/${id}`;

// Policies
export const POLICIES = `${APP}/policies`;
export const policy = (id: string): string => `${APP}/policies/${id}`;
export const POLICY_DECISIONS = `${APP}/policies/decisions`;
export const policyDecision = (id: string): string => `${APP}/policies/decisions/${id}`;

// Audit
export const AUDIT_EVENTS = `${APP}/audit/events`;
export const auditEvent = (id: string): string => `${APP}/audit/events/${id}`;
export const auditVerify = (eventId: string): string => `${APP}/audit/verify/${eventId}`;
export const AUDIT_ANCHORS = `${APP}/audit/anchors`;

// Observability
export const AGENT_RUNS = `${APP}/observability/agent-runs`;
export const agentRun = (id: string): string => `${APP}/observability/agent-runs/${id}`;
export const LLM_CALLS = `${APP}/observability/llm-calls`;
export const COSTS = `${APP}/observability/costs`;

// Health intel
export const HEALTH_GATEWAYS = `${APP}/health-intel/gateways`;
export const HEALTH_ISSUERS = `${APP}/health-intel/issuers`;
export const OUTAGES = `${APP}/health-intel/outages`;

// Simulation
export const SIMULATIONS = `${APP}/simulations`;

// Flags
export const FLAGS = `${APP}/flags`;
export const KILL_SWITCHES = `${APP}/flags/kill-switches`;

// Settings (tabbed)
export const SETTINGS = `${APP}/settings`;
export const SETTINGS_PROFILE = `${APP}/settings/profile`;
export const SETTINGS_SECURITY = `${APP}/settings/security`;
export const SETTINGS_TENANT = `${APP}/settings/tenant`;
export const SETTINGS_TEAM = `${APP}/settings/team`;
export const SETTINGS_API_KEYS = `${APP}/settings/api-keys`;
export const SETTINGS_INTEGRATIONS = `${APP}/settings/integrations`;
export const SETTINGS_BILLING = `${APP}/settings/billing`;
