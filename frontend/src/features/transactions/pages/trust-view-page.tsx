import { ArrowLeft, ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";
import { Link } from "react-router-dom";

import { CitationBadge } from "@/components/trust/citation-badge";
import { EventHash } from "@/components/trust/event-hash";
import { StatusChip } from "@/components/trust/status-chip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import * as routes from "@/lib/constants/routes";
import { formatMoney, formatTimestamp } from "@/lib/utils/format";
import { mockTimeline, mockTransactions } from "@/lib/mock-data";
import { cn } from "@/lib/utils/cn";

/**
 * Screen #8 — Trust View Timeline ⭐
 *
 * THE killer screen. For a single transaction, render the full event chain
 * with one-line summaries, citation badges, hash chips, and expandable
 * payload drawers. This is the screen the whole architecture exists to
 * serve — proves "evidence-based, citable, replayable" out loud.
 */

export function TrustViewPage(): JSX.Element {
  // For the demo we always render the first transaction. Routing will pass
  // an :id param once useQuery is wired.
  const txn = mockTransactions[0]!;
  const events = mockTimeline;
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <div className="p-6 max-w-[1100px] mx-auto space-y-6">
      <Link
        to={routes.TRANSACTIONS}
        className="inline-flex items-center gap-1 text-body-sm text-foreground-secondary hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        Back to transactions
      </Link>

      {/* Transaction summary header */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="text-caption font-medium uppercase tracking-wider text-foreground-tertiary">
                Transaction
              </p>
              <CardTitle className="font-mono text-h2">{txn.externalId}</CardTitle>
            </div>
            <StatusChip status={txn.status} />
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-body-sm">
          <Detail label="Amount" value={formatMoney(txn.amountCents, txn.currency)} mono />
          <Detail label="Card" value={`${txn.cardBrand} · ${txn.cardLast4}`} />
          <Detail label="Gateway" value={txn.gatewayId} mono />
          <Detail label="Issuer" value={txn.issuerId} mono />
        </CardContent>
      </Card>

      {/* Timeline */}
      <section className="space-y-4">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="font-display text-h2 text-foreground">Timeline</h2>
            <p className="mt-1 text-body-sm text-foreground-secondary">
              Every event in causal order. Click an entry to inspect the raw
              payload. Click a [N] badge to drill into the citation source.
            </p>
          </div>
          <Button variant="secondary" size="sm" asChild>
            <Link to={routes.auditVerify(events[0]!.eventHash)}>
              Verify chain
              <ChevronRight className="size-3.5" />
            </Link>
          </Button>
        </div>

        <ol className="relative space-y-3 pl-7">
          {/* Vertical rail */}
          <span
            className="absolute left-[12px] top-2 bottom-2 w-px bg-border"
            aria-hidden
          />

          {events.map((ev, i) => {
            const open = expanded === i;
            const dotTone = ev.eventType.includes("Failed")
              ? "bg-danger"
              : ev.eventType.includes("Recovered") || ev.eventType.includes("Succeeded")
                ? "bg-success"
                : ev.eventType.includes("Approval") || ev.eventType.includes("Risk")
                  ? "bg-warning"
                  : "bg-primary";

            return (
              <li key={i} className="relative">
                {/* Timeline dot */}
                <span
                  className={cn(
                    "absolute left-[-19px] top-4 size-2.5 rounded-full ring-4 ring-page",
                    dotTone,
                  )}
                  aria-hidden
                />

                <Card
                  interactive
                  onClick={() => setExpanded(open ? null : i)}
                  className="overflow-hidden"
                >
                  <CardContent className="p-4 space-y-2">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-caption font-medium text-foreground-secondary">
                            {ev.eventType}
                          </span>
                          <span className="text-caption text-foreground-tertiary">
                            {formatTimestamp(ev.occurredAt)}
                          </span>
                        </div>
                        <p className="text-body text-foreground">{ev.summary}</p>

                        {ev.citations && ev.citations.length > 0 ? (
                          <div className="flex flex-wrap items-center gap-1.5 pt-1">
                            <span className="text-caption text-foreground-tertiary">
                              Citations:
                            </span>
                            {ev.citations.map((c) => (
                              <CitationBadge
                                key={c.index}
                                index={c.index}
                                title={c.observation}
                                onClick={(e) => {
                                  e.stopPropagation();
                                }}
                              />
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <EventHash hash={ev.eventHash} />
                    </div>

                    {open ? (
                      <div className="mt-3 pt-3 border-t border-border space-y-3">
                        {ev.citations && ev.citations.length > 0 ? (
                          <div className="space-y-2">
                            <p className="text-caption uppercase tracking-wider text-foreground-tertiary">
                              Evidence
                            </p>
                            <ol className="space-y-1.5">
                              {ev.citations.map((c) => (
                                <li
                                  key={c.index}
                                  className="flex items-start gap-2 text-body-sm"
                                >
                                  <CitationBadge index={c.index} />
                                  <div className="flex-1 min-w-0">
                                    <p className="text-foreground">{c.observation}</p>
                                    <p className="text-caption font-mono text-foreground-tertiary mt-0.5">
                                      source: {c.sourceKind}
                                    </p>
                                  </div>
                                </li>
                              ))}
                            </ol>
                          </div>
                        ) : null}

                        <div className="space-y-2">
                          <p className="text-caption uppercase tracking-wider text-foreground-tertiary">
                            Payload
                          </p>
                          <pre className="rounded-md bg-inset border border-border p-3 overflow-x-auto text-code text-foreground">
                            {JSON.stringify(ev.payload, null, 2)}
                          </pre>
                        </div>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}

interface DetailProps {
  label: string;
  value: string;
  mono?: boolean;
}
function Detail({ label, value, mono = false }: DetailProps): JSX.Element {
  return (
    <Fragment>
      <div>
        <p className="text-caption uppercase tracking-wider text-foreground-tertiary">
          {label}
        </p>
        <p
          className={cn(
            "mt-1 text-foreground",
            mono ? "font-mono tabular-nums" : "",
          )}
        >
          {value}
        </p>
      </div>
    </Fragment>
  );
}
