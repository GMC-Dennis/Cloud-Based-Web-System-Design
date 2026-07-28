"use client";

import { useState } from "react";

import { Badge, riskTierTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useApplicants, useCreateLoan } from "@/features/credit-scoring/api";

const PAGE_SIZE = 50;

export function ApplicantTable() {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useApplicants({ limit: PAGE_SIZE, offset });
  const createLoan = useCreateLoan();
  const [principalByScore, setPrincipalByScore] = useState<Record<string, string>>({});

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
            <Th>Disburse</Th>
          </Tr>
        </Thead>
        <Tbody>
          {data.items.map((a) => (
            <Tr key={a.credit_score_id}>
              <Td>{a.applicant_name ?? "Anonymized until approval"}</Td>
              <Td>{a.credit_score}</Td>
              <Td>
                <Badge tone={riskTierTone(a.risk_tier)}>{a.risk_tier}</Badge>
              </Td>
              <Td>KES {a.recommended_limit}</Td>
              <Td>{a.status ?? "No loan yet"}</Td>
              <Td>
                {!a.loan_id && (
                  <div className="flex items-center gap-2">
                    <Input
                      className="h-8 w-24"
                      placeholder="Principal"
                      value={principalByScore[a.credit_score_id] ?? ""}
                      onChange={(e) => setPrincipalByScore((s) => ({ ...s, [a.credit_score_id]: e.target.value }))}
                    />
                    <Button
                      size="sm"
                      disabled={createLoan.isPending || !principalByScore[a.credit_score_id]}
                      onClick={() =>
                        createLoan.mutate({
                          // No borrower_id here on purpose -- the backend resolves it
                          // from credit_score_id, since this view is anonymized.
                          credit_score_id: a.credit_score_id,
                          underwriting_method: "ALGORITHMIC",
                          principal: principalByScore[a.credit_score_id],
                          interest_rate: "0.05",
                        })
                      }
                    >
                      Approve
                    </Button>
                  </div>
                )}
              </Td>
            </Tr>
          ))}
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
