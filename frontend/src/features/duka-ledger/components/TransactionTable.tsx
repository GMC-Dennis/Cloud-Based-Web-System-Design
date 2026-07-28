"use client";

import { Badge } from "@/components/ui/badge";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useTransactions } from "@/features/duka-ledger/api";

export function TransactionTable() {
  const { data, isLoading, error } = useTransactions();

  if (isLoading) return <p className="text-sm text-slate-500">Loading transactions...</p>;
  if (error) return <p className="text-sm text-red-600">Could not load transactions.</p>;
  if (!data?.length) return <p className="text-sm text-slate-500">No transactions yet.</p>;

  return (
    <Table>
      <Thead>
        <Tr>
          <Th>#</Th>
          <Th>Type</Th>
          <Th>Amount</Th>
          <Th>Credit</Th>
          <Th>Date</Th>
        </Tr>
      </Thead>
      <Tbody>
        {data.map((txn) => (
          <Tr key={txn.id}>
            <Td>{txn.sequence_no}</Td>
            <Td>
              <Badge tone={txn.transaction_type === "SALE" ? "success" : "neutral"}>{txn.transaction_type}</Badge>
            </Td>
            <Td>
              {txn.currency} {txn.amount}
            </Td>
            <Td>{txn.is_credit ? "Yes" : "No"}</Td>
            <Td>{new Date(txn.created_at).toLocaleString()}</Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}
