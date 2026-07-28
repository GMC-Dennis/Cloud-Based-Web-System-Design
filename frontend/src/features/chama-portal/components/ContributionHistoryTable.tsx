"use client";

import { Badge } from "@/components/ui/badge";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useContributions } from "@/features/chama-portal/api";

export function ContributionHistoryTable({ memberId }: { memberId: string }) {
  const { data: contributions, isLoading } = useContributions(memberId);

  if (isLoading) return <p className="text-sm text-slate-500">Loading contribution history...</p>;
  if (!contributions?.length) return <p className="text-sm text-slate-500">No contributions recorded yet.</p>;

  return (
    <Table>
      <Thead>
        <Tr>
          <Th>Cycle due</Th>
          <Th>Amount due</Th>
          <Th>Amount paid</Th>
          <Th>Paid at</Th>
          <Th>On time</Th>
        </Tr>
      </Thead>
      <Tbody>
        {contributions.map((c) => (
          <Tr key={c.id}>
            <Td>{c.cycle_due_date}</Td>
            <Td>KES {c.amount_due}</Td>
            <Td>KES {c.amount_paid}</Td>
            <Td>{c.paid_at ? new Date(c.paid_at).toLocaleDateString() : "—"}</Td>
            <Td>
              {c.is_on_time === null ? "—" : <Badge tone={c.is_on_time ? "success" : "danger"}>{c.is_on_time ? "On time" : "Late"}</Badge>}
            </Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}
