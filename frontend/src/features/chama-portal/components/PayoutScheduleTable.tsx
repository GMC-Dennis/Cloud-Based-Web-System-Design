"use client";

import { Badge } from "@/components/ui/badge";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { usePayouts } from "@/features/chama-portal/api";

export function PayoutScheduleTable({ chamaId }: { chamaId: string }) {
  const { data: payouts, isLoading } = usePayouts(chamaId);

  if (isLoading) return <p className="text-sm text-slate-500">Loading payout schedule...</p>;
  if (!payouts?.length) return <p className="text-sm text-slate-500">No payouts scheduled yet.</p>;

  return (
    <Table>
      <Thead>
        <Tr>
          <Th>Recipient member</Th>
          <Th>Amount</Th>
          <Th>Scheduled date</Th>
          <Th>Status</Th>
        </Tr>
      </Thead>
      <Tbody>
        {payouts.map((p) => (
          <Tr key={p.id}>
            <Td>{p.recipient_member_id}</Td>
            <Td>KES {p.payout_amount}</Td>
            <Td>{p.scheduled_date}</Td>
            <Td>
              {p.paid_out_at ? (
                <Badge tone="success">Paid {new Date(p.paid_out_at).toLocaleDateString()}</Badge>
              ) : (
                <Badge tone="warning">Pending</Badge>
              )}
            </Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}
