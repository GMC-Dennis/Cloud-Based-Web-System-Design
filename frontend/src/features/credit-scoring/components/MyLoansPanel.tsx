"use client";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useLoanRepayments, useMyLoans } from "@/features/credit-scoring/api";
import type { Loan } from "@/features/credit-scoring/types";

// Statuses reached after a loan is disbursed -- the only ones where a
// repayment total is meaningful to show (PENDING/APPROVED/REJECTED loans
// never have repayment rows).
const REPAYMENT_STATUSES = new Set(["DISBURSED", "REPAID", "DEFAULTED"]);

function statusTone(status: string): BadgeProps["tone"] {
  if (status === "REPAID" || status === "DISBURSED") return "success";
  if (status === "PENDING" || status === "APPROVED") return "warning";
  if (status === "DEFAULTED" || status === "REJECTED") return "danger";
  return "neutral";
}

function RepaidTotal({ loanId }: { loanId: string }) {
  const { data: repayments, isLoading } = useLoanRepayments(loanId);
  if (isLoading) return <span className="text-slate-400">...</span>;
  const total = (repayments ?? []).reduce((sum, r) => sum + Number(r.amount), 0);
  return <>KES {total.toFixed(2)}</>;
}

function LoanRow({ loan }: { loan: Loan }) {
  return (
    <Tr>
      <Td>KES {loan.principal}</Td>
      <Td>{(Number(loan.interest_rate) * 100).toFixed(2)}%</Td>
      <Td>
        <Badge tone={statusTone(loan.status)}>{loan.status}</Badge>
      </Td>
      <Td>{loan.due_date ?? "—"}</Td>
      <Td>{loan.disbursed_at ? new Date(loan.disbursed_at).toLocaleDateString() : "—"}</Td>
      <Td>{REPAYMENT_STATUSES.has(loan.status) ? <RepaidTotal loanId={loan.id} /> : "—"}</Td>
    </Tr>
  );
}

export function MyLoansPanel() {
  const { data: loans, isLoading } = useMyLoans();

  if (isLoading) return <p className="text-sm text-slate-500">Loading loans...</p>;
  if (!loans?.length) return <p className="text-sm text-slate-500">You don&apos;t have any loans yet.</p>;

  return (
    <Table>
      <Thead>
        <Tr>
          <Th>Principal</Th>
          <Th>Interest rate</Th>
          <Th>Status</Th>
          <Th>Due date</Th>
          <Th>Disbursed</Th>
          <Th>Repaid so far</Th>
        </Tr>
      </Thead>
      <Tbody>
        {loans.map((loan) => (
          <LoanRow key={loan.id} loan={loan} />
        ))}
      </Tbody>
    </Table>
  );
}
