"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/table";
import { useTransactions } from "@/features/duka-ledger/api";

const PAGE_SIZE = 50;

export function TransactionTable() {
  const [offset, setOffset] = useState(0);
  const { data, isLoading, error } = useTransactions({ limit: PAGE_SIZE, offset });

  if (isLoading) return <p className="text-sm text-slate-500">Loading transactions...</p>;
  if (error) return <p className="text-sm text-red-600">Could not load transactions.</p>;
  if (!data?.items.length) return <p className="text-sm text-slate-500">No transactions yet.</p>;

  const hasPrev = offset > 0;
  const hasNext = offset + data.items.length < data.total;

  return (
    <div className="space-y-3">
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
          {data.items.map((txn) => (
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
