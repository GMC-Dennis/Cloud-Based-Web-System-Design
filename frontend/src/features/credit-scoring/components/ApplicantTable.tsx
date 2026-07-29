"use client";

import { Fragment, useState } from "react";

import { Badge, riskTierTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useApplicants, useCreateLoan, useLoanRepayments, useRecordRepayment } from "@/features/credit-scoring/api";

const PAGE_SIZE = 50;
const DEFAULT_INTEREST_RATE = "0.05";
const MAX_INTEREST_RATE = 0.5; // 50% -- a sane ceiling, not the column's raw Decimal(5,4) limit.

// Human-readable labels for the anomaly-flag heuristic (platform
// cross-cutting spec §3.4d) -- a triage aid, not a fraud verdict.
const ANOMALY_FLAG_LABELS: Record<string, string> = {
  VOLUME_SPIKE_LAST_3_DAYS: "Most revenue is from the last 3 days",
  IMPLAUSIBLY_SMOOTH_MARGIN: "Margin is suspiciously constant day to day",
};

function isValidInterestRate(value: string): boolean {
  const parsed = Number(value);
  return value !== "" && Number.isFinite(parsed) && parsed > 0 && parsed <= MAX_INTEREST_RATE;
}

function AnomalyFlagsBadge({ flags }: { flags: string[] }) {
  if (!flags.length) return null;
  const labels = flags.map((f) => ANOMALY_FLAG_LABELS[f] ?? f);
  return (
    <Badge tone="warning" title={`Triage flags (not a fraud verdict):\n${labels.join("\n")}`}>
      ⚠ {flags.length} flag{flags.length > 1 ? "s" : ""}
    </Badge>
  );
}

function RepaymentHistory({ loanId }: { loanId: string }) {
  const { data: repayments, isLoading } = useLoanRepayments(loanId);

  if (isLoading) return <p className="text-xs text-slate-500">Loading repayments...</p>;
  if (!repayments?.length) return <p className="text-xs text-slate-500">No repayments recorded yet.</p>;

  return (
    <ul className="space-y-1 text-xs text-slate-600">
      {repayments.map((r) => (
        <li key={r.id}>
          KES {r.amount} — {new Date(r.paid_at).toLocaleDateString()}
        </li>
      ))}
    </ul>
  );
}

function LoanRepaymentSection({ loanId }: { loanId: string }) {
  const recordRepayment = useRecordRepayment();
  const [amount, setAmount] = useState("");

  return (
    <div className="space-y-2 rounded-md border border-slate-200 p-3">
      <div className="flex items-center gap-2">
        <Input
          className="h-8 w-28"
          placeholder="Amount"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <Button
          size="sm"
          disabled={recordRepayment.isPending || !amount}
          onClick={async () => {
            await recordRepayment.mutateAsync({ loanId, amount });
            setAmount("");
          }}
        >
          Record repayment
        </Button>
      </div>

      <RepaymentHistory loanId={loanId} />
    </div>
  );
}

export function ApplicantTable() {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useApplicants({ limit: PAGE_SIZE, offset });
  const createLoan = useCreateLoan();
  const [principalByScore, setPrincipalByScore] = useState<Record<string, string>>({});
  const [interestRateByScore, setInterestRateByScore] = useState<Record<string, string>>({});
  const [expandedLoanId, setExpandedLoanId] = useState<string | null>(null);

  if (isLoading) return <p className="text-sm text-slate-500">Loading applicants...</p>;
  if (!data?.items.length) return <p className="text-sm text-slate-500">No applicants scored yet.</p>;

  const hasPrev = offset > 0;
  const hasNext = offset + data.items.length < data.total;

  return (
    <div className="space-y-3">
      <Table>
        <Thead>
          <Tr>
            <Th>Applicant</Th>
            <Th>Score</Th>
            <Th>Tier</Th>
            <Th>Limit</Th>
            <Th>Status</Th>
            <Th>Flags</Th>
            <Th>Disburse</Th>
          </Tr>
        </Thead>
        <Tbody>
          {data.items.map((a) => {
            const interestRate = interestRateByScore[a.credit_score_id] ?? DEFAULT_INTEREST_RATE;
            return (
              <Fragment key={a.credit_score_id}>
                <Tr>
                  <Td>{a.applicant_name ?? "Anonymized until approval"}</Td>
                  <Td>{a.credit_score}</Td>
                  <Td>
                    <Badge tone={riskTierTone(a.risk_tier)}>{a.risk_tier}</Badge>
                  </Td>
                  <Td>KES {a.recommended_limit}</Td>
                  <Td>{a.status ?? "No loan yet"}</Td>
                  <Td>
                    <AnomalyFlagsBadge flags={a.anomaly_flags} />
                  </Td>
                  <Td>
                    {a.loan_id ? (
                      <Button size="sm" variant="secondary" onClick={() => setExpandedLoanId(expandedLoanId === a.loan_id ? null : a.loan_id)}>
                        {expandedLoanId === a.loan_id ? "Hide loan" : "View loan"}
                      </Button>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Input
                          className="h-8 w-24"
                          placeholder="Principal"
                          value={principalByScore[a.credit_score_id] ?? ""}
                          onChange={(e) => setPrincipalByScore((s) => ({ ...s, [a.credit_score_id]: e.target.value }))}
                        />
                        <Input
                          className="h-8 w-20"
                          placeholder="Rate (0.05)"
                          inputMode="decimal"
                          value={interestRate}
                          onChange={(e) => setInterestRateByScore((s) => ({ ...s, [a.credit_score_id]: e.target.value }))}
                        />
                        <Button
                          size="sm"
                          disabled={createLoan.isPending || !principalByScore[a.credit_score_id] || !isValidInterestRate(interestRate)}
                          onClick={() =>
                            createLoan.mutate({
                              // No borrower_id here on purpose -- the backend resolves it
                              // from credit_score_id, since this view is anonymized.
                              credit_score_id: a.credit_score_id,
                              underwriting_method: "ALGORITHMIC",
                              principal: principalByScore[a.credit_score_id],
                              interest_rate: interestRate,
                            })
                          }
                        >
                          Approve
                        </Button>
                      </div>
                    )}
                  </Td>
                </Tr>
                {a.loan_id && expandedLoanId === a.loan_id && (
                  <Tr>
                    <Td colSpan={7}>
                      <LoanRepaymentSection loanId={a.loan_id} />
                    </Td>
                  </Tr>
                )}
              </Fragment>
            );
          })}
        </Tbody>
      </Table>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>
          {offset + 1}-{offset + data.items.length} of {data.total}
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled={!hasPrev} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
            Previous
          </Button>
          <Button variant="secondary" size="sm" disabled={!hasNext} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
